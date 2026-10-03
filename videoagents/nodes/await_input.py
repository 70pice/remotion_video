"""Persisted input pauses and final human confirmation for the current job."""

from typing import Any

from langgraph.types import interrupt

from videoagents.nodes.common import current_job, request_input, state_context
from videoagents.nodes.reviewers import ReviewersNode, dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint


class AwaitInputNode:
    def __init__(self, repository: Repository, service: JobService, reviewers: ReviewersNode):
        self.repo, self.service, self.reviewers = repository, service, reviewers

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
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
                return state_context(self.repo, state, route="end")
            raise Conflict("发布完成记录与当前视频不匹配，需重新审核")
        if job.status == "DRAFT" and job.pending_input is None and job.message == "请修改对应产物并提交新版本":
            return state_context(self.repo, state, route="end")
        decision = interrupt(pending)
        # Every resume, including subsequent answers after a short note,
        # dispatches all decisions through the same branch.
        while True:
            if decision.get("decision") == "cancel":
                job = self.repo.cancel(job.job_id)
                return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
            if decision.get("decision") == "revise":
                job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="请修改对应产物并提交新版本", pending_input=None)
                return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
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
            review = self.reviewers.review(job, human_confirmed=True, model_review=False)
            previous_model_errors = [finding for finding in job.review.findings if finding.category == "model_content" and finding.blocking]
            review.findings.extend(previous_model_errors)
            if previous_model_errors or review.status != "PASS" or review.media_sha256 != pending["media_sha256"]:
                self.repo.update_job(job.job_id, job.revision, review=review)
                return request_input(self.repo, state, "review", [finding.message for finding in review.findings if finding.blocking] or ["成片 hash 已改变，需要重新审核"], ["review"])
            # Keep the original pending receipt until the full package exists.
            self.repo.update_job(job.job_id, job.revision, review=review)
            report = self.service.write_json(job, "human_review.json", {"revision": job.revision, "media_sha256": review.media_sha256,
                "dependency_fingerprint": review.dependency_fingerprint, "note": note, "coverage": review.coverage}, "human_review")
            self.service.write_json(job, "review.json", review.model_dump(), "review")
            current = self.repo.get_job(job.job_id)
            self.service.write_json(current, "manifest.json", {"job_id": job.job_id, "revision": job.revision,
                "media_sha256": review.media_sha256, "dependency_fingerprint": review.dependency_fingerprint,
                "artifacts": [artifact.model_dump() for artifact in current.artifacts], "human_review_artifact_id": report.artifact_id}, "package")
            job = self.repo.update_job(job.job_id, job.revision, status="READY_FOR_PUBLISH", stage="complete", message="内部审核完成，发布包已就绪", pending_input=None, progress=1)
            return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
        # Input confirmations always rerun the responsible stage and its gates.
        target = {"materials": "materials", "script": "screenwriter", "voice": "voice", "director": "director", "render": "editing", "review": "reviewers"}[pending["stage"]]
        if target == "screenwriter" and not state.get("research") and not job.script and not job.brief.script_text.strip():
            # 兼容此前暂停在编剧的旧图：恢复时先补素材，编剧不自行联网采集。
            target = "materials"
        return state_context(self.repo, state, route=target, human_decision={**pending, **decision})

