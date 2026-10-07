"""Persisted pauses for missing inputs and recoverable production failures."""

from typing import Any

from langgraph.types import interrupt

from videoagents.nodes.common import current_job, state_context
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository


class AwaitInputNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        # Node replay uses the original checkpoint's pending snapshot, not a
        # potentially newer SQL prompt written by an interrupted later round.
        pending = state.get("pending_snapshot") or job.pending_input
        if not pending:
            raise Conflict("中断输入记录不存在")
        if pending.get("kind") != "input" or pending.get("stage") == "review":
            raise Conflict("成片审核流程已移除，请重新提交制作任务")
        if job.status == "DRAFT" and job.pending_input is None and job.message == "请修改对应产物并提交新版本":
            return state_context(self.repo, state, route="end")
        decision = interrupt(pending)
        if decision.get("decision") == "cancel":
            job = self.repo.cancel(job.job_id)
            return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
        if decision.get("decision") == "revise":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="请修改对应产物并提交新版本", pending_input=None)
            return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
        if decision.get("decision") != "confirm":
            raise Conflict("恢复决定无效")
        # Input confirmations always rerun the responsible stage and its gates.
        target = {"materials": "materials", "script": "screenwriter", "voice": "voice", "director": "director", "render": "editing"}[pending["stage"]]
        if target == "screenwriter" and not state.get("research") and not job.script and not job.brief.script_text.strip():
            # 兼容此前暂停在编剧的旧图：恢复时先补素材，编剧不自行联网采集。
            target = "materials"
        return state_context(self.repo, state, route=target, human_decision={**pending, **decision})

