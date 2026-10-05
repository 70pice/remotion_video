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
from videoagents.nodes.gates import AudioGateNode, ReviewGateNode, ScriptGateNode, TimelineGateNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.reviewers import ReviewersNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.script_reviewer import ScriptReviewerNode
from videoagents.nodes.voice import VoiceNode
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository


class VideoProductionGraph(AbstractContextManager):
    def __init__(self, repository: Repository, project_root: Path | None = None):
        self.repo = repository
        self.service = JobService(repository, project_root) if project_root else JobService(repository)
        self.connection = sqlite3.connect(repository.root / "checkpoints.sqlite", check_same_thread=False, timeout=15)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.checkpointer = SqliteSaver(self.connection)
        reviewers = ReviewersNode(repository, self.service)
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
        graph.add_node("timeline_gate", TimelineGateNode(repository))
        graph.add_node("editing", EditingNode(repository, self.service))
        graph.add_node("reviewers", reviewers)
        graph.add_node("review_gate", ReviewGateNode(repository))
        graph.add_node("await_input", AwaitInputNode(repository, self.service, reviewers))
        # Available for manual orchestration; no incoming edge by default.
        self.add_human_review(graph, "human_review", stage="script", title="文案人工审核",
                              confirmation_requirements=("文案表达与事实来源", "截图及素材与文案一致"), next_node="voice")
        self.add_human_review(graph, "human_review_script", stage="script", title="文案人工审核",
                              confirmation_requirements=("首句具体，尽早建立观看理由",
                                                         "主线清楚，结尾自然回应问题",
                                                         "事实表达有来源，素材引用能支撑文案",
                                                         "机器文案讨论已通过但仍需人工确认是否可进入配音"),
                              next_node="after_script_review", revise_node="screenwriter")
        self.add_human_review(graph, "human_review_timeline", stage="director", title="分镜人工审核",
                              confirmation_requirements=("导演已完成竖版组件学习并使用 1080×1920 抖音画面",
                                                         "每个镜头都匹配旁白节奏、字幕边界和真实素材",
                                                         "视频素材优先且画面可读、有冲击力"),
                              next_node="after_timeline_review", revise_node="director")
        self.add_human_review(graph, "human_review_render", stage="render", title="剪辑成片人工审核",
                              confirmation_requirements=("完整播放确认音频、字幕、画面节奏正常",
                                                         "竖屏成片信息足够清晰，真实素材没有错位或误用",
                                                         "阶段确认只允许进入机器审核，不等同发布批准"),
                              next_node="after_render_review", revise_node="director")
        graph.add_node("after_script_review", self.after_script_review)
        graph.add_node("after_timeline_review", self.after_timeline_review)
        graph.add_node("after_render_review", self.after_render_review)
        graph.add_edge(START, "materials")
        self.add_cleanup_edge(graph, "materials", {"screenwriter": "screenwriter", "await_input": "await_input"})
        self.add_cleanup_edge(graph, "screenwriter", {
            "script_reviewer": "script_reviewer", "script_gate": "script_gate", "await_input": "await_input",
        })
        self.add_cleanup_edge(graph, "script_reviewer", {
            "screenwriter": "screenwriter", "script_gate": "script_gate", "await_input": "await_input",
        })
        graph.add_conditional_edges("script_gate", self.route, {"voice": "human_review_script", "await_input": "await_input"})
        graph.add_conditional_edges("after_script_review", self.route, {"voice": "voice"})
        self.add_cleanup_edge(graph, "voice", {"audio_gate": "audio_gate", "await_input": "await_input"})
        graph.add_conditional_edges("audio_gate", self.route, {"director": "director", "await_input": "await_input", "end": END})
        self.add_cleanup_edge(graph, "director", {"timeline_gate": "timeline_gate", "await_input": "await_input"})
        graph.add_conditional_edges("timeline_gate", self.route, {"editing": "human_review_timeline", "await_input": "await_input", "end": "human_review_timeline", "reviewers": "human_review_timeline"})
        graph.add_conditional_edges("after_timeline_review", self.route, {"editing": "editing", "reviewers": "reviewers", "end": END})
        self.add_cleanup_edge(graph, "editing", {"reviewers": "human_review_render", "await_input": "await_input", "end": "human_review_render"})
        graph.add_conditional_edges("after_render_review", self.route, {"reviewers": "reviewers", "end": END})
        self.add_cleanup_edge(graph, "reviewers", {"review_gate": "review_gate", "await_input": "await_input"})
        graph.add_conditional_edges("review_gate", self.route, {"end": END, "await_input": "await_input"})
        graph.add_conditional_edges("await_input", self.route, {"materials": "materials", "screenwriter": "screenwriter", "script_reviewer": "script_reviewer", "voice": "voice", "director": "director", "editing": "editing", "reviewers": "reviewers", "await_input": "await_input", "end": END})
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

    def after_timeline_review(self, state: VideoState) -> dict[str, Any]:
        if state.get("action") == "storyboard":
            job = self.repo.get_job(state["job_id"])
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message="分镜已通过人工审核，本次执行结束")
            return state_context(self.repo, state, route="end")
        return state_context(self.repo, state, route="reviewers" if state.get("action") == "review" else "editing")

    def after_render_review(self, state: VideoState) -> dict[str, Any]:
        if state.get("action") == "preview":
            job = self.repo.get_job(state["job_id"])
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="render", progress=1,
                                 message="预览成片已通过人工审核，本次执行结束")
            return state_context(self.repo, state, route="end")
        return state_context(self.repo, state, route="reviewers")

    def __exit__(self, *exc):
        # The saver serializes background writes under this same lock. Closing
        # SQLite concurrently with a cursor can crash CPython on Windows.
        with self.checkpointer.lock:
            self.connection.close()

    @staticmethod
    def route(state: VideoState) -> str:
        return state["route"]

    def execute(self, command: dict[str, Any]) -> Any:
        payload = command["payload"]
        job = self.repo.get_job(command["job_id"])
        if job.status == "CANCELLED":
            return None
        if payload["base_revision"] != job.revision:
            raise Conflict("排队命令的版本已失效")
        if payload["action"] == "resume":
            pending = payload["pending_input"]
            thread_id = pending["thread_id"]
            config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}
            snapshot = self.graph.get_state(config)
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
