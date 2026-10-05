"""Deterministic stage checks, registered as nodes alongside production roles."""

import uuid
from typing import Any

from videoagents.contracts import Alignment
from videoagents.nodes.common import current_job, request_input, state_context
from videoagents.nodes.screenwriter import script_issues
from videoagents.nodes.voice import validate_alignment
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline


class ScriptGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        issues = script_issues(job)
        if issues:
            return request_input(self.repo, state, "script", issues, ["script", "source_urls", "assets"])
        return state_context(self.repo, state, route="voice", gate_issues=[])


class AudioGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        audio = next(item for item in job.assets if item.asset_id == state["audio_asset_id"])
        issues = validate_alignment(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"])
        if issues:
            return request_input(self.repo, state, "voice", issues, ["alignment"])
        if state["action"] == "voice":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="真实音频与时间轴已就绪", stage="voice")
            return state_context(self.repo, state, route="end")
        return state_context(self.repo, state, route="director", gate_issues=[])


class TimelineGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        try:
            metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
            validate_timeline(job.timeline, job, metadata)
        except ValueError as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["timeline"])
        if state["action"] == "storyboard":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="分镜和真实音频时间轴已就绪", stage="director")
            return state_context(self.repo, state, route="end")
        return state_context(self.repo, state, route="reviewers" if state["action"] == "review" else "editing")


class ReviewGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        hard_errors = [item.message for item in job.review.findings if item.blocking and item.severity == "error"]
        if hard_errors:
            return request_input(self.repo, state, "review", hard_errors, ["review"])
        pending = {"kind": "human_review", "stage": "review", "thread_id": state["thread_id"], "revision": job.revision,
                   "media_sha256": job.review.media_sha256, "dependency_fingerprint": job.review.dependency_fingerprint,
                   "issues": [item.message for item in job.review.findings if item.blocking],
                   "confirmation_requirements": ["完整播放", "事实与截图", "音频与字幕", "排版可读性", "素材及字体用途"],
                   "pending_token": uuid.uuid4().hex}
        job = self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", message="硬检查已通过，等待完整成片的人工复核", pending_input=pending)
        return state_context(self.repo, state, route="await_input", pending_snapshot=pending)
