"""StateGraph registration, routing and durable command execution."""

import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from videoagents.nodes.await_input import AwaitInputNode
from videoagents.nodes.clear_tools import ClearToolsNode
from videoagents.nodes.common import state_context
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.gates import AudioGateNode, ScriptGateNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.script_reviewer import ScriptReviewerNode
from videoagents.nodes.voice import VoiceNode
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository

REMOVED_REVIEW_NODES = frozenset({
    "timeline_gate", "human_review_timeline", "human_review_render", "reviewers",
    "review_gate", "clear_reviewers", "after_timeline_review", "after_render_review",
})


class VideoProductionGraph(AbstractContextManager):
    def __init__(self, repository: Repository, project_root: Path | None = None):
        self.repo = repository
        self.service = JobService(repository, project_root) if project_root else JobService(repository)
        self.connection = sqlite3.connect(repository.root / "checkpoints.sqlite", check_same_thread=False, timeout=15)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.checkpointer = SqliteSaver(self.connection)
        # 与 TradingAgents 的 Msg Clear 一样，每个模型角色后先清理，再路由到下一阶段。
        # CLI 内部运行工具，图中只交接最终 JSON，不增加 ToolNode 或工具消息循环。
        graph = StateGraph(VideoState)
        graph.add_node("materials", MaterialsNode(repository, self.service))
        graph.add_node("screenwriter", ScreenwriterNode(repository, self.service))
        graph.add_node("script_reviewer", ScriptReviewerNode(repository, self.service))
        graph.add_node("script_gate", ScriptGateNode(repository))
        graph.add_node("voice", VoiceNode(repository, self.service))
        graph.add_node("audio_gate", AudioGateNode(repository))
        graph.add_node("director", DirectorNode(repository, self.service))
        graph.add_node("editing", EditingNode(repository, self.service))
        graph.add_node("await_input", AwaitInputNode(repository, self.service))
        # Available for manual orchestration; no incoming edge by default.
        self.add_human_review(graph, "human_review", stage="script", title="文案人工审核",
                              confirmation_requirements=("文案表达与事实来源", "截图及素材与文案一致"), next_node="voice")
        self.add_human_review(graph, "human_review_script", stage="script", title="文案人工审核",
                              confirmation_requirements=("首句具体，尽早建立观看理由",
                                                         "主线清楚，结尾自然回应问题",
                                                         "事实表达有来源，素材引用能支撑文案",
                                                         "核对机器审查意见与最终文案，人工确认后才可进入配音"),
                              next_node="after_script_review", revise_node="screenwriter")
        graph.add_node("after_script_review", self.after_script_review)
        graph.add_edge(START, "materials")
        self.add_cleanup_edge(graph, "materials", {"screenwriter": "screenwriter", "await_input": "await_input"})
        self.add_cleanup_edge(graph, "screenwriter", {
            "script_reviewer": "script_reviewer", "human_review_script": "human_review_script",
            "await_input": "await_input",
        })
        self.add_cleanup_edge(graph, "script_reviewer", {
            "screenwriter": "screenwriter", "human_review_script": "human_review_script",
            "await_input": "await_input",
        })
        # 旧 checkpoint 仍可恢复到 script_gate；新文案流程直接进入人工审核。
        graph.add_conditional_edges("script_gate", self.route, {"voice": "human_review_script", "await_input": "await_input"})
        graph.add_conditional_edges("after_script_review", self.route, {"voice": "voice"})
        self.add_cleanup_edge(graph, "voice", {"audio_gate": "audio_gate", "await_input": "await_input"})
        graph.add_conditional_edges("audio_gate", self.route, {"director": "director", "await_input": "await_input", "end": END})
        self.add_cleanup_edge(graph, "director", {
            "editing": "editing", "screenwriter": "screenwriter", "await_input": "await_input", "end": END,
        })
        self.add_cleanup_edge(graph, "editing", {"await_input": "await_input", "end": END})
        graph.add_conditional_edges("await_input", self.route, {"materials": "materials", "screenwriter": "screenwriter", "script_reviewer": "script_reviewer", "voice": "voice", "director": "director", "editing": "editing", "await_input": "await_input", "end": END})
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

    def __exit__(self, *exc):
        # The saver serializes background writes under this same lock. Closing
        # SQLite concurrently with a cursor can crash CPython on Windows.
        with self.checkpointer.lock:
            self.connection.close()

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
        if payload["base_revision"] != job.revision:
            raise Conflict("排队命令的版本已失效")
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
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}
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
            # Interrupt IDs also key the actual LangGraph resume map, so a
            # response can only be delivered to the selected recorded pause.
            result = self.graph.invoke(Command(update={"resume_command_id": command["command_id"]}, resume={target.id: decision}), config)
            self.sync_pending(config, job)
            return state_context(self.repo, result)
        thread_id = "job:" + job.job_id + ":run:" + command["command_id"]
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}
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
        state = state_context(self.repo, VideoState(job_id=job.job_id, revision=job.revision,
                              action=payload["action"], run_id=command["command_id"], thread_id=thread_id,
                              gate_issues=[], extras={}))
        result = self.graph.invoke(state, config)
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
