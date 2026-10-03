"""Durable five-role StateGraph with semantic gates and persisted interrupts."""

import sqlite3
import uuid
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from videoagents.agents.director import Director
from videoagents.agents.reviewers import Reviewers, dependency_fingerprint
from videoagents.agents.screenwriter import Screenwriter, script_issues
from videoagents.contracts import Alignment
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.voice import VoiceNode, validate_alignment
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.timeline import validate_timeline
from worker.process_manager import RenderCancelled


class VideoProductionGraph(AbstractContextManager):
    def __init__(self, repository: Repository, project_root: Path | None = None):
        self.repo = repository
        self.service = JobService(repository, project_root) if project_root else JobService(repository)
        self.connection = sqlite3.connect(repository.root / "checkpoints.sqlite", check_same_thread=False, timeout=15)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.checkpointer = SqliteSaver(self.connection)
        self.screenwriter = Screenwriter(repository, self.service)
        self.voice = VoiceNode(repository, self.service)
        self.director = Director(repository)
        self.editor = EditingNode(repository, self.service)
        self.reviewers = Reviewers(repository, self.service)
        graph = StateGraph(VideoState)
        for name in ("screenwriter", "script_gate", "voice", "audio_gate", "director", "timeline_gate", "editing", "reviewers", "review_gate", "await_input"):
            graph.add_node(name, getattr(self, "node_" + name))
        graph.add_edge(START, "screenwriter")
        graph.add_conditional_edges("screenwriter", self.route, {"script_gate": "script_gate", "await_input": "await_input"})
        graph.add_conditional_edges("script_gate", self.route, {"voice": "voice", "await_input": "await_input"})
        graph.add_conditional_edges("voice", self.route, {"audio_gate": "audio_gate", "await_input": "await_input"})
        graph.add_conditional_edges("audio_gate", self.route, {"director": "director", "await_input": "await_input", "end": END})
        graph.add_conditional_edges("director", self.route, {"timeline_gate": "timeline_gate", "await_input": "await_input"})
        graph.add_conditional_edges("timeline_gate", self.route, {"editing": "editing", "await_input": "await_input", "end": END, "reviewers": "reviewers"})
        graph.add_conditional_edges("editing", self.route, {"reviewers": "reviewers", "await_input": "await_input", "end": END})
        graph.add_conditional_edges("reviewers", self.route, {"review_gate": "review_gate", "await_input": "await_input"})
        graph.add_conditional_edges("review_gate", self.route, {"end": END, "await_input": "await_input"})
        graph.add_conditional_edges("await_input", self.route, {"screenwriter": "screenwriter", "voice": "voice", "director": "director", "editing": "editing", "reviewers": "reviewers", "await_input": "await_input", "end": END})
        self.graph = graph.compile(checkpointer=self.checkpointer)

    def __exit__(self, *exc):
        # The saver serializes background writes under this same lock. Closing
        # SQLite concurrently with a cursor can crash CPython on Windows.
        with self.checkpointer.lock:
            self.connection.close()

    @staticmethod
    def route(state: VideoState) -> str:
        return state["route"]

    def job(self, state):
        job = self.repo.get_job(state["job_id"])
        if job.revision != state["revision"]:
            raise Conflict("执行版本已失效")
        if job.status == "CANCELLED":
            raise RenderCancelled("任务已取消")
        return job

    def stage(self, state, stage, message):
        self.job(state)
        return self.repo.update_job(state["job_id"], state["revision"], status="RUNNING", stage=stage, message=message, progress=None, pending_input=None)

    def blocked(self, state, stage, issues, fields=None, exception=None):
        pending = {"kind": "input", "stage": stage, "issues": issues, "fields": fields or [],
                   "thread_id": state["thread_id"], "revision": state["revision"], "pending_token": uuid.uuid4().hex}
        for key in ("operation_status", "operation_id", "request_id"):
            value = getattr(exception, key, None)
            if value:
                pending[key] = value
        self.repo.update_job(state["job_id"], state["revision"], status="NEEDS_INPUT", stage=stage,
                             message="；".join(issues)[:2000], pending_input=pending)
        return {"route": "await_input", "gate_issues": issues, "pending_snapshot": pending}

    def node_screenwriter(self, state):
        job = self.stage(state, "script", "编剧正在整理文案与真实来源")
        try:
            script, research = self.screenwriter.run(job)
            current = self.repo.update_job(job.job_id, job.revision, script=script)
            self.service.write_json(current, "script.json", script.model_dump(), "script")
            return {"route": "script_gate", "research": research, "gate_issues": []}
        except (CapabilityMissing, ValueError) as exc:
            return self.blocked(state, "script", [str(exc)], getattr(exc, "fields", ["script"]), exc)

    def node_script_gate(self, state):
        issues = script_issues(self.job(state))
        return self.blocked(state, "script", issues, ["script", "source_urls", "assets"]) if issues else {"route": "voice", "gate_issues": []}

    def node_voice(self, state):
        job = self.stage(state, "voice", "配音正在核验真实音频与实测时间轴")
        try:
            audio, alignment, duration = self.voice.run(job, state.get("resume_command_id", state["run_id"]), state["action"] == "voice")
            self.service.write_json(job, "alignment.json", alignment.model_dump(), "alignment")
            self.service.write_json(job, "audio_report.json", {"audio_sha256": audio.sha256, "duration_seconds": duration,
                                    "origin": self.repo.asset_metadata(audio.asset_id).get("origin"), "alignment_origin": alignment.origin,
                                    "verified": alignment.verified}, "audio_report")
            return {"route": "audio_gate", "audio_asset_id": audio.asset_id, "alignment": alignment.model_dump(), "duration_seconds": duration, "gate_issues": []}
        except (CapabilityMissing, ValueError) as exc:
            return self.blocked(state, "voice", [str(exc)], getattr(exc, "fields", ["audio", "alignment"]), exc)

    def node_audio_gate(self, state):
        job = self.job(state)
        audio = next(item for item in job.assets if item.asset_id == state["audio_asset_id"])
        issues = validate_alignment(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"])
        if issues:
            return self.blocked(state, "voice", issues, ["alignment"])
        if state["action"] == "voice":
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="真实音频与时间轴已就绪", stage="voice")
            return {"route": "end"}
        return {"route": "director", "gate_issues": []}

    def node_director(self, state):
        job = self.stage(state, "director", "导演根据实测旁白安排镜头与关键画面")
        try:
            audio = next(item for item in job.assets if item.asset_id == state["audio_asset_id"])
            timeline = self.director.run(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"])
            current = self.repo.update_job(job.job_id, job.revision, timeline=timeline)
            self.service.write_json(current, "storyboard.json", timeline.model_dump(), "storyboard")
            self.service.write_json(current, "timeline.json", timeline.model_dump(), "timeline")
            return {"route": "timeline_gate", "gate_issues": []}
        except (CapabilityMissing, ValueError) as exc:
            return self.blocked(state, "director", [str(exc)], ["timeline"], exc)

    def node_timeline_gate(self, state):
        job = self.job(state)
        try:
            validate_timeline(job.timeline, job)
        except ValueError as exc:
            return self.blocked(state, "director", [str(exc)], ["timeline"])
        if state["action"] == "storyboard":
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="分镜和真实音频时间轴已就绪", stage="director")
            return {"route": "end"}
        return {"route": "reviewers" if state["action"] == "review" else "editing"}

    def node_editing(self, state):
        job = self.stage(state, "render", "剪辑正在冻结素材并调用 Remotion")
        mode = "preview" if state["action"] == "preview" else "final"
        try:
            self.editor.run(job, mode)
        except (CapabilityMissing, ValueError, TimeoutError) as exc:
            return self.blocked(state, "render", [str(exc)], getattr(exc, "fields", ["render"]), exc)
        if mode == "preview":
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="真实预览已渲染，可试听并调整分镜", stage="render", progress=1)
            return {"route": "end"}
        return {"route": "reviewers"}

    def node_reviewers(self, state):
        job = self.stage(state, "review", "审核正在检查最终视频、来源、时长与素材用途")
        try:
            review = self.reviewers.run(job)
        except (CapabilityMissing, ValueError) as exc:
            return self.blocked(state, "review", [str(exc)], getattr(exc, "fields", ["review"]), exc)
        self.repo.update_job(job.job_id, job.revision, review=review)
        self.service.write_json(job, "review.json", review.model_dump(), "review")
        return {"gate_issues": [], "route": "review_gate"}

    def node_review_gate(self, state):
        job = self.job(state)
        hard = [item.message for item in job.review.findings if item.blocking and item.severity == "error"]
        if hard:
            return self.blocked(state, "review", hard, ["review"])
        pending = {"kind": "human_review", "stage": "review", "thread_id": state["thread_id"], "revision": job.revision,
                   "media_sha256": job.review.media_sha256, "dependency_fingerprint": job.review.dependency_fingerprint,
                   "issues": [item.message for item in job.review.findings if item.blocking],
                   "confirmation_requirements": ["完整播放", "事实与截图", "音频与字幕", "排版可读性", "素材及字体用途"], "pending_token": uuid.uuid4().hex}
        self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", message="硬检查已通过，等待完整成片的人工复核", pending_input=pending)
        return {"route": "await_input", "pending_snapshot": pending}

    def node_await_input(self, state):
        job = self.job(state)
        # Node replay uses the original checkpoint's pending snapshot, not a
        # potentially newer SQL prompt written by an interrupted later round.
        pending = state.get("pending_snapshot") or job.pending_input
        if not pending:
            raise Conflict("中断输入记录不存在")
        # If final SQL commit succeeded but the LangGraph checkpoint did not,
        # replaying this node must settle the original resume command rather
        # than lose approval or manufacture another confirmation.
        if job.status == "READY_FOR_PUBLISH" and job.review and job.review.human_confirmed:
            final = next((item for item in job.artifacts if item.kind == "final" and item.revision == job.revision), None)
            from videoagents.tools.media import sha256
            if final and job.review.dependency_fingerprint == dependency_fingerprint(job) and sha256(self.repo.artifact_path(final.artifact_id)[0]) == job.review.media_sha256:
                return {"route": "end"}
            raise Conflict("发布完成记录与当前视频不匹配，需重新审核")
        if job.status == "DRAFT" and job.pending_input is None and job.message == "请修改对应产物并提交新版本":
            return {"route": "end"}
        decision = interrupt(pending)
        # Every resume, including subsequent answers after a short note,
        # dispatches all decisions through the same branch.
        while True:
            if decision.get("decision") == "cancel":
                self.repo.cancel(job.job_id)
                return {"route": "end"}
            if decision.get("decision") == "revise":
                self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="请修改对应产物并提交新版本", pending_input=None)
                return {"route": "end"}
            if decision.get("decision") != "confirm":
                raise Conflict("恢复决定无效")
            if pending["kind"] != "human_review" or len(decision.get("note", "").strip()) >= 10:
                break
            pending = dict(pending, pending_token=fingerprint({"previous": pending["pending_token"], "purpose": "full_review_note"})[:32])
            self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", message="请填写完整播放和内容/声音/画面/许可核验说明", pending_input=pending)
            decision = interrupt(pending)
        if pending["kind"] == "human_review":
            if job.revision != pending["revision"] or dependency_fingerprint(job) != pending["dependency_fingerprint"]:
                raise Conflict("人审输入版本已失效")
            note = decision.get("note", "").strip()
            review = self.reviewers.run(job, human_confirmed=True, model_review=False)
            previous_model_errors = [finding for finding in job.review.findings if finding.category == "model_content" and finding.blocking]
            review.findings.extend(previous_model_errors)
            if previous_model_errors or review.status != "PASS" or review.media_sha256 != pending["media_sha256"]:
                self.repo.update_job(job.job_id, job.revision, review=review)
                return self.blocked(state, "review", [finding.message for finding in review.findings if finding.blocking] or ["成片 hash 已改变，需要重新审核"], ["review"])
            # Keep the original pending receipt until the full package exists.
            self.repo.update_job(job.job_id, job.revision, review=review)
            report = self.service.write_json(job, "human_review.json", {"revision": job.revision, "media_sha256": review.media_sha256,
                "dependency_fingerprint": review.dependency_fingerprint, "note": note, "coverage": review.coverage}, "human_review")
            self.service.write_json(job, "review.json", review.model_dump(), "review")
            current = self.repo.get_job(job.job_id)
            self.service.write_json(current, "manifest.json", {"job_id": job.job_id, "revision": job.revision,
                "media_sha256": review.media_sha256, "dependency_fingerprint": review.dependency_fingerprint,
                "artifacts": [artifact.model_dump() for artifact in current.artifacts], "human_review_artifact_id": report.artifact_id}, "package")
            self.repo.update_job(job.job_id, job.revision, status="READY_FOR_PUBLISH", stage="complete", message="内部审核完成，发布包已就绪", pending_input=None, progress=1)
            return {"route": "end"}
        # Input confirmations always rerun the responsible stage and its gates.
        target = {"script": "screenwriter", "voice": "voice", "director": "director", "render": "editing", "review": "reviewers"}[pending["stage"]]
        return {"route": target}

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
                    self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN" if latest.get("kind") == "human_review" else "NEEDS_INPUT", pending_input=latest,
                                         message="工作流已推进到新的待办，请重新查看并回答")
                return snapshot.values
            if not current_interrupts:
                if snapshot.next:
                    return self.graph.invoke(None, config)
                return snapshot.values
            decision = {"decision": payload["decision"], "note": payload.get("note", "")}
            # Interrupt IDs also key the actual LangGraph resume map, so a
            # response can only be delivered to the selected recorded pause.
            result = self.graph.invoke(Command(update={"resume_command_id": command["command_id"]}, resume={target.id: decision}), config)
            self.sync_pending(config, job)
            return result
        thread_id = "job:" + job.job_id + ":run:" + command["command_id"]
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}
        previous = self.graph.get_state(config)
        # A crash reclaims the same command, not a new run; graph resumes saved node work.
        if previous.values:
            if previous.interrupts:
                return previous.values
            return self.graph.invoke(None, config)
        state = VideoState(job_id=job.job_id, revision=job.revision, action=payload["action"],
                           run_id=command["command_id"], thread_id=thread_id, gate_issues=[])
        result = self.graph.invoke(state, config)
        self.sync_pending(config, job)
        return result

    def sync_pending(self, config, job):
        snapshot = self.graph.get_state(config)
        if snapshot.interrupts:
            pending = snapshot.interrupts[0].value
            if isinstance(pending, dict):
                pending = dict(pending, interrupt_id=snapshot.interrupts[0].id)
                current = self.repo.get_job(job.job_id)
                if current.status != "CANCELLED":
                    self.repo.update_job(job.job_id, job.revision, pending_input=pending)
