"""StateGraph registration, routing and durable command execution."""

import os
import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from videoagents.contracts import Job
from videoagents.nodes.await_input import AwaitInputNode
from videoagents.nodes.clear_tools import ClearToolsNode
from videoagents.nodes.common import current_job, request_input, state_context, validate_context_assets
from videoagents.nodes.component_demo import ComponentDemoNode
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.director_demo import DirectorDemoNode
from videoagents.nodes.director_review import validate_shot_refresh
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.gates import AudioGateNode, ScriptGateNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.script_review import (
    JOINT_REVIEW_NODE,
    JOINT_REVIEW_REQUIREMENTS,
    JOINT_REVIEW_TITLE,
    SCRIPT_REVIEW_NODE,
    SCRIPT_REVIEW_REQUIREMENTS,
    SCRIPT_REVIEW_TITLE,
    script_before_materials_is_approved,
)
from videoagents.nodes.voice import VoiceNode
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository

REMOVED_REVIEW_NODES = frozenset({
    "timeline_gate", "human_review_timeline", "human_review_render", "reviewers",
    "review_gate", "clear_reviewers", "after_timeline_review", "after_render_review",
    "script_reviewer", "clear_script_reviewer",
})


class VideoProductionGraph(AbstractContextManager):
    def __init__(self, repository: Repository, project_root: Path | None = None):
        self.repo = repository
        self.service = JobService(repository, project_root) if project_root else JobService(repository)
        self.connection = sqlite3.connect(repository.root / "checkpoints.sqlite", check_same_thread=False, timeout=15)
        if os.name != "nt":
            # Checkpoints carry the full business context; match application.sqlite.
            os.chmod(repository.root / "checkpoints.sqlite", 0o600)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.checkpointer = SqliteSaver(self.connection)
        # 与 TradingAgents 的 Msg Clear 一样，每个模型角色后先清理，再路由到下一阶段。
        # CLI 内部运行工具，图中只交接最终 JSON，不增加 ToolNode 或工具消息循环。
        graph = StateGraph(VideoState)
        graph.add_node("component_demo", ComponentDemoNode(repository, self.service))
        self.materials_node = MaterialsNode(repository, self.service)
        graph.add_node("materials", self.materials_after_script_review)
        graph.add_node("screenwriter", ScreenwriterNode(repository, self.service))
        graph.add_node("script_gate", ScriptGateNode(repository))
        graph.add_node("voice", VoiceNode(repository, self.service))
        graph.add_node("audio_gate", AudioGateNode(repository))
        graph.add_node("director", DirectorNode(repository, self.service))
        graph.add_node("director_demo", DirectorDemoNode(repository, self.service))
        graph.add_node("editing", EditingNode(repository, self.service))
        graph.add_node("await_input", AwaitInputNode(repository, self.service))
        # Available for manual orchestration; no incoming edge by default.
        self.add_human_review(graph, "human_review", stage="script", title="文案人工审核",
                              confirmation_requirements=("文案表达与事实来源", "截图及素材与文案一致"), next_node="voice")
        self.add_human_review(graph, SCRIPT_REVIEW_NODE, stage="script", title=SCRIPT_REVIEW_TITLE,
                              confirmation_requirements=SCRIPT_REVIEW_REQUIREMENTS,
                              next_node="materials", revise_node="screenwriter")
        self.add_human_review(graph, JOINT_REVIEW_NODE, stage="script", title=JOINT_REVIEW_TITLE,
                              confirmation_requirements=JOINT_REVIEW_REQUIREMENTS,
                              next_node="after_script_review", revise_node="screenwriter")
        self.add_human_review(graph, "director_human_gate", stage="director", title="摄影逐镜设计与代表帧审核",
                              confirmation_requirements=("逐段核对摄影表演设计是否贴合当前口播",
                                                         "逐镜代表帧 PNG、组件选择与画面动作可以代表本片方向",
                                                         "素材、案例、数字与当前旁白对应，没有用组件Demo词冒充事实",
                                                         "人工确认整包后才允许渲染完整成片"),
                              next_node="after_director_demo_review", revise_node="director")
        graph.add_node("after_script_review", self.after_script_review)
        graph.add_node("after_director_demo_review", self.after_director_demo_review)
        graph.add_conditional_edges(START, self.start_route, {
            "component_demo": "component_demo", "screenwriter": "screenwriter", "materials": "materials",
            "audio_gate": "audio_gate", "director_demo": "director_demo",
        })
        self.add_cleanup_edge(graph, "component_demo", {"director_demo": "director_demo", "await_input": "await_input"})
        self.add_cleanup_edge(graph, "screenwriter", {
            SCRIPT_REVIEW_NODE: SCRIPT_REVIEW_NODE,
            "materials": SCRIPT_REVIEW_NODE,  # Older saved writer outputs.
            "await_input": "await_input",
        })
        self.add_cleanup_edge(graph, "materials", {"human_review_script": "human_review_script",
                                                   SCRIPT_REVIEW_NODE: SCRIPT_REVIEW_NODE,
                                                   "await_input": "await_input"})
        # 旧 checkpoint 仍可恢复到 script_gate；新文案流程直接进入人工审核。
        graph.add_conditional_edges("script_gate", self.route, {"voice": "human_review_script", "await_input": "await_input"})
        graph.add_conditional_edges("after_script_review", self.route, {"voice": "voice"})
        self.add_cleanup_edge(graph, "voice", {"audio_gate": "audio_gate", "await_input": "await_input"})
        graph.add_conditional_edges("audio_gate", self.route, {"director": "director", "await_input": "await_input", "end": END})
        self.add_cleanup_edge(graph, "director", {
            "editing": "director_demo", "director_demo": "director_demo",
            "screenwriter": "screenwriter", "await_input": "await_input", "end": END,
        })
        graph.add_conditional_edges("director_demo", self.route, {
            "director_human_gate": "director_human_gate", "await_input": "await_input", "end": END,
        })
        graph.add_conditional_edges("after_director_demo_review", self.route, {"editing": "editing"})
        self.add_cleanup_edge(graph, "editing", {"director_demo": "director_demo", "await_input": "await_input", "end": END})
        graph.add_conditional_edges("await_input", self.route, {"component_demo": "component_demo", "materials": "materials", "screenwriter": "screenwriter", "voice": "voice", "director": "director", "director_demo": "director_demo", "editing": "editing", "await_input": "await_input", "end": END})
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def add_cleanup_edge(self, graph: StateGraph, source: str, routes: dict[str, str]) -> None:
        """角色输出 → 清理工具历史 → 原条件路由；route 标记和业务结果保持不变。"""
        name = "clear_" + source
        graph.add_node(name, ClearToolsNode())
        graph.add_edge(source, name)
        graph.add_conditional_edges(name, self.route, routes)

    def add_human_review(self, graph: StateGraph, name: str, *, stage: str, title: str,
                         confirmation_requirements: tuple[str, ...], next_node: str, min_note_length: int = 10,
                         revise_node: str | None = None) -> None:
        """Register a reusable approval node; replace its upstream edge to enable it."""
        graph.add_node(name, HumanReviewNode(self.repo, node_name=name, stage=stage, title=title,
                       confirmation_requirements=confirmation_requirements, min_note_length=min_note_length,
                       finish_on_confirm=next_node == END, revise_route=revise_node))
        routes = {"continue": next_node, "retry": name, "end": END}
        if revise_node:
            routes["revise"] = revise_node
        graph.add_conditional_edges(name, self.route, routes)

    def after_script_review(self, state: VideoState) -> dict[str, Any]:
        return state_context(self.repo, state, route="voice")

    def materials_after_script_review(self, state: VideoState) -> dict[str, Any]:
        """Guard old saved materials/retry routes as well as the normal edge."""
        job = current_job(self.repo, state)
        operation = self.repo.unsettled_operation(job.job_id, "llm:materials", job.revision)
        if operation:
            error = CapabilityMissing("素材提交结果仍未知，必须先核对或明确授权建立新版草稿",
                                      ["llm_operation"], operation_id=operation["operation_id"],
                                      operation_status=operation["status"])
            return request_input(self.repo, state, "materials", [str(error)], error.fields, error)
        if not script_before_materials_is_approved(self.repo, job):
            return state_context(self.repo, state, route=SCRIPT_REVIEW_NODE, stage_review_pending=None)
        return self.materials_node(state)

    def after_director_demo_review(self, state: VideoState) -> dict[str, Any]:
        return state_context(self.repo, state, route="editing")

    def __exit__(self, *exc):
        # The saver serializes background writes under this same lock. Closing
        # SQLite concurrently with a cursor can crash CPython on Windows.
        with self.checkpointer.lock:
            self.connection.close()

    def start_route(self, state: VideoState) -> str:
        # The writer designs segments first; a human approves them before
        # materials collects evidence and footage against the visual needs.
        if state.get("action") == "component_demo":
            return "component_demo"
        if state.get("action") == "refresh_shots":
            return "director_demo"
        job = current_job(self.repo, state)
        if self.repo.director_restart_receipt(job.job_id, job.revision):
            from videoagents.services.director_recovery import validate_director_restart

            validate_director_restart(self.repo, job)
            return "audio_gate"
        if self.repo.materials_restart_receipt(job.job_id, job.revision):
            if not script_before_materials_is_approved(self.repo, job):
                raise Conflict("仅素材重启的原文案批准依据无效")
            return "materials"
        return "screenwriter"

    @staticmethod
    def route(state: VideoState) -> str:
        return state["route"]

    def stop_removed_review(self, state: VideoState) -> VideoState:
        """Settle an old command without running retired checkpoint nodes."""
        job = self.repo.get_job(state["job_id"])
        self.repo.update_job(job.job_id, job.revision, status="DRAFT", pending_input=None,
                             message="该阶段审核已移除，请重新提交制作任务")
        return state_context(self.repo, state, route="end")

    @staticmethod
    def is_removed_review_checkpoint(snapshot: Any) -> bool:
        # Old role output may be saved before its still-existing cleanup node.
        # Final human review also used the retained generic await_input node.
        return (bool(set(snapshot.next) & REMOVED_REVIEW_NODES)
                or snapshot.values.get("route") in REMOVED_REVIEW_NODES
                or any(isinstance(item.value, dict) and (
                    item.value.get("node_name") in REMOVED_REVIEW_NODES
                    or item.value.get("kind") == "human_review"
                    or item.value.get("stage") == "review"
                ) for item in snapshot.interrupts))

    def execute(self, command: dict[str, Any]) -> Any:
        payload = command["payload"]
        job = self.repo.get_job(command["job_id"])
        if job.status == "CANCELLED":
            return None
        if command.get("status") == "DONE":
            return state_context(self.repo, VideoState(job_id=job.job_id, revision=job.revision, route="end"))
        if payload["base_revision"] != job.revision:
            raise Conflict("排队命令的版本已失效")
        if payload["action"] == "retry":
            return self.retry_failed_command(command, job)
        if payload.get("continue_from") == "voice" or payload.get("rebuild_from") == "director":
            return self.continue_after_voice(command, job)
        if payload["action"] == "review":
            return self.stop_removed_review(VideoState(job_id=job.job_id, revision=job.revision))
        if payload["action"] == "resume":
            pending = payload["pending_input"]
            if (pending.get("node_name") in REMOVED_REVIEW_NODES
                    or pending.get("kind") == "human_review" or pending.get("stage") == "review"):
                if payload.get("decision") == "cancel":
                    self.repo.cancel(job.job_id)
                    return state_context(self.repo, VideoState(job_id=job.job_id), route="end")
                return self.stop_removed_review(VideoState(job_id=job.job_id, revision=job.revision))
            thread_id = pending["thread_id"]
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}
            snapshot = self.graph.get_state(config)
            if self.is_removed_review_checkpoint(snapshot):
                return self.stop_removed_review(snapshot.values)
            current_interrupts = snapshot.interrupts
            target = next((item for item in current_interrupts if isinstance(item.value, dict) and item.value.get("pending_token") == payload["pending_token"]), None)
            if current_interrupts and not target:
                # This command already advanced the graph to a different
                # question before a worker crash. Never reuse the old answer.
                latest = current_interrupts[0].value
                if isinstance(latest, dict):
                    self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN" if latest.get("kind") in {"human_review", "stage_review"} else "NEEDS_INPUT", pending_input=latest,
                                         message="工作流已推进到新的待办，请重新查看并回答")
                return state_context(self.repo, snapshot.values) if snapshot.values else snapshot.values
            if not current_interrupts:
                if snapshot.next:
                    result = self.graph.invoke(None, config)
                    self.sync_pending(config, job)
                    return state_context(self.repo, result)
                return state_context(self.repo, snapshot.values) if snapshot.values else snapshot.values
            decision = {"decision": payload["decision"], "note": payload.get("note", ""), "pending_token": payload["pending_token"]}
            if payload.get("director_requirements") is not None:
                decision["director_requirements"] = payload["director_requirements"]
            if payload.get("reviewed_shot_ids") is not None:
                decision["reviewed_shot_ids"] = payload["reviewed_shot_ids"]
            if payload["decision"] == "select_materials":
                for field in ("base_revision", "idempotency_key", "accepted_asset_ids", "rejected_asset_ids"):
                    decision[field] = payload[field]
            # Interrupt IDs also key the actual LangGraph resume map, so a
            # response can only be delivered to the selected recorded pause.
            update = {"resume_command_id": command["command_id"]}
            if payload.get("stop_after") == "voice":
                update["action"] = "voice"
            result = self.graph.invoke(Command(update=update, resume={target.id: decision}), config)
            self.sync_pending(config, job)
            return state_context(self.repo, result)
        thread_id = "job:" + job.job_id + ":run:" + command["command_id"]
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}
        previous = self.graph.get_state(config)
        # A crash reclaims the same command, not a new run; graph resumes saved node work.
        if previous.values:
            if self.is_removed_review_checkpoint(previous):
                return self.stop_removed_review(previous.values)
            if previous.interrupts:
                return state_context(self.repo, previous.values)
            result = self.graph.invoke(None, config)
            self.sync_pending(config, job)
            return state_context(self.repo, result)
        if payload["action"] == "refresh_shots":
            pending = payload["pending_input"]
            source_thread = pending.get("thread_id", "")
            if not source_thread.startswith(f"job:{job.job_id}:run:"):
                raise Conflict("刷新镜头的原待办检查点不属于当前任务")
            source = self.graph.get_state({"configurable": {"thread_id": source_thread}})
            if (source.values.get("job_id") != job.job_id or source.values.get("revision") != job.revision
                    or not any(isinstance(item.value, dict)
                               and item.value.get("pending_token") == payload["pending_token"]
                               for item in source.interrupts)):
                raise Conflict("刷新镜头绑定的原工作流待办已失效")
            for name in ("brief", "script", "assets", "timeline", "director_requirements"):
                if source.values.get(name) != job.model_dump().get(name):
                    raise Conflict("刷新镜头的制作输入已变化")
            validate_shot_refresh(self.repo, job, payload, pending)
        extras = {"component_demo": payload["component_demo"]} if payload["action"] == "component_demo" else {}
        if payload["action"] == "refresh_shots":
            extras["shot_refresh"] = {"director_plan_artifact_id": payload["director_plan_artifact_id"],
                                      "director_plan_sha256": payload["director_plan_sha256"],
                                      "dependency_fingerprint": dependency_fingerprint(job)}
        state = state_context(self.repo, VideoState(job_id=job.job_id, revision=job.revision,
                              action=payload["action"], run_id=command["command_id"], thread_id=thread_id,
                              gate_issues=[], extras=extras))
        result = self.graph.invoke(state, config)
        self.sync_pending(config, job)
        return state_context(self.repo, result)

    def retry_failed_command(self, command: dict[str, Any], job: Job) -> Any:
        """Resume saved node work without supplying an approval or changing its route."""
        thread_id = command["payload"]["continuation_thread_id"]
        if not thread_id.startswith(f"job:{job.job_id}:run:"):
            raise Conflict("失败续跑的检查点不属于当前任务")
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 120}
        saved = self.graph.get_state(config)
        state = saved.values
        if not state or state.get("job_id") != job.job_id or state.get("revision") != job.revision:
            raise Conflict("失败续跑的工作流状态缺失或版本已变化")
        if self.is_removed_review_checkpoint(saved):
            raise Conflict("旧审核节点不能通过失败续跑恢复")
        for name in ("brief", "script", "assets", "director_requirements"):
            if state.get(name) != job.model_dump().get(name):
                raise Conflict("失败后的制作输入已变化，请保存新版本重新执行")
        validate_context_assets(self.repo, job)
        if saved.interrupts:
            # A worker may have reached a new question before its final SQL save.
            # Retrying a command never answers that question, even on reclaim.
            pending = saved.interrupts[0].value
            if not isinstance(pending, dict):
                raise Conflict("工作流待办格式无效")
            self.repo.update_job(job.job_id, job.revision,
                                 status="NEEDS_HUMAN" if pending.get("kind") in {"human_review", "stage_review"} else "NEEDS_INPUT",
                                 pending_input=dict(pending, interrupt_id=saved.interrupts[0].id),
                                 message="工作流已停在人工待办，请查看并回答")
            return state_context(self.repo, state)
        if not saved.next:
            # A completion recorded before the worker's command acknowledgement
            # must not schedule the graph's START node or render a second time.
            if state.get("route") != "end" or state.get("status") != "DRAFT":
                raise Conflict("失败续跑没有可恢复节点或有效完成记录")
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage=state.get("stage", job.stage),
                                 pending_input=None, message=state.get("message", "工作流已完成，未重复执行"),
                                 progress=state.get("progress"))
            return state_context(self.repo, state)
        result = self.graph.invoke(Command(update={"resume_command_id": command["command_id"]}), config)
        self.sync_pending(config, job)
        return state_context(self.repo, result)

    def continue_after_voice(self, command: dict[str, Any], job: Job) -> Any:
        """Continue frozen audio or rebuild visuals through existing graph nodes."""
        payload = command["payload"]
        rebuilding = payload.get("rebuild_from") == "director"
        config = {"configurable": {"thread_id": payload["continuation_thread_id"]}, "recursion_limit": 120}
        saved = self.graph.get_state(config)
        state = saved.values
        if not state or state.get("job_id") != job.job_id or state.get("revision") != job.revision:
            raise Conflict("续跑的工作流状态缺失或版本已变化")
        if state.get("resume_command_id") == command["command_id"]:
            # A reclaimed command resumes the nodes it already scheduled. Never
            # jump over a new input interrupt or repeat a completed render.
            result = self.graph.invoke(None, config) if saved.next and not saved.interrupts else state
            self.sync_pending(config, job)
            return state_context(self.repo, result)
        finished = (state.get("stage") in {"director", "render", "complete"}
                    and state.get("action") in {"produce", "storyboard", "preview", "final"}) if rebuilding else (
                    state.get("stage") == "voice" and state.get("action") == "voice")
        if saved.next or saved.interrupts or state.get("route") != "end" or not finished:
            raise Conflict("原工作流尚未完成画面制作" if rebuilding else "原工作流尚未在配音完成处结束")
        for name in (("brief", "script", "assets", "timeline") if rebuilding else ("brief", "script", "assets")):
            if state.get(name) != job.model_dump()[name]:
                raise Conflict("配音完成后的制作输入已变化，请重新制作并审核")
        validate_context_assets(self.repo, job)
        current = state_context(self.repo, state)
        for name in ("audio_asset_id", "alignment", "duration_seconds"):
            if not current.get(name) or current[name] != state.get(name):
                raise Conflict("配音或对齐元数据已变化，请重新核验")
        receipt_ids = {item.artifact_id for item in job.artifacts if item.kind == "stage_review" and item.revision == job.revision}
        approvals = [item for item in current["human_reviews"] if item.get("artifact_id") in receipt_ids and item.get("kind") == "stage_review"
                     and item.get("stage") == "script" and item.get("revision") == job.revision
                     and item.get("decision") == "confirm" and item.get("node_name") in {"human_review_script", "human_review"}]
        if not approvals or not any(item in state.get("human_reviews", []) for item in approvals):
            raise Conflict("续跑缺少已保存的文案人工确认")
        # Command.goto on the existing checkpoint schedules audio validation;
        # START/materials and the already completed voice node are not invoked.
        update = {"action": payload["action"], "resume_command_id": command["command_id"]}
        if rebuilding:
            update["extras"] = {"timeline_rebuild": True}
        result = self.graph.invoke(Command(update=update, goto="audio_gate"), config)
        self.sync_pending(config, job)
        return state_context(self.repo, result)

    def sync_pending(self, config, job):
        snapshot = self.graph.get_state(config)
        if snapshot.interrupts:
            pending = snapshot.interrupts[0].value
            if isinstance(pending, dict):
                pending = dict(pending, interrupt_id=snapshot.interrupts[0].id)
                current = self.repo.get_job(job.job_id)
                if current.status != "CANCELLED":
                    self.repo.update_job(job.job_id, job.revision, pending_input=pending)
