"""Persisted pauses for missing inputs and recoverable production failures."""

import json
from typing import Any

from langgraph.types import interrupt

from videoagents.contracts import Job
from videoagents.nodes.common import (
    DIRECTOR_VOICE_REVISION_ISSUE,
    REVISE_SETTLED_MESSAGE,
    current_job,
    needs_script_revision,
    needs_voice_revision,
    render_text_fit_issues,
    stage_feedback,
    state_context,
)
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository


def _stale_editing_preflight(repository: Repository, job: Job, pending: dict[str, Any]) -> bool:
    """Recheck old model advice after a contract update, preserving the real gate.

    This only schedules EditingNode again. Current advice still routes actual
    visual problems to director; no finding or approval is overwritten here.
    """
    if (pending.get("stage") != "director" or pending.get("retry_node")
            or set(pending.get("fields") or []) != {"timeline"}):
        return False
    from videoagents.nodes.director_review import checked_artifact, director_demo_is_approved
    from videoagents.nodes.editing import editing_instruction_fingerprint
    from videoagents.nodes.reviewers import dependency_fingerprint

    artifact = next((item for item in reversed(job.artifacts)
                     if item.kind == "editing_guidance" and item.revision == job.revision), None)
    if not artifact or not director_demo_is_approved(repository, job):
        return False
    advice = json.loads(checked_artifact(repository, job, artifact).read_text(encoding="utf-8"))
    blocked = [item["message"] for item in advice.get("findings", [])
               if item.get("blocking") or item.get("severity") == "error"]
    if not blocked or pending.get("issues") != ["剪辑发现分镜问题：" + "；".join(blocked)]:
        return False
    metadata = repository.artifact_metadata(artifact.artifact_id)
    recorded = metadata.get("instruction_fingerprint")
    if recorded is None:
        # Legacy preflight omitted the newly supported in-shot contracts.
        return bool(job.timeline and any(shot.set_design or shot.layers for shot in job.timeline.shots))
    return (recorded != editing_instruction_fingerprint(job)
            and metadata.get("dependency_fingerprint") == dependency_fingerprint(job))


def _legacy_director_voice_false_positive(pending: dict[str, Any], state: VideoState) -> bool:
    """Route old director visual-only feedback back to director instead of voice.

    Older DirectorNode builds treated any mention of "重配音/音频" as an audio
    change request, including explicit preservation notes.  Only that exact
    generated pause is corrected here; real voice pauses keep their original
    route.
    """
    if pending.get("stage") != "voice":
        return False
    if pending.get("retry_node"):
        return False
    if pending.get("issues") != [DIRECTOR_VOICE_REVISION_ISSUE]:
        return False
    if set(pending.get("fields") or []) != {"voice", "timeline"}:
        return False
    feedback = stage_feedback(state, "render", "director")
    note = feedback.get("note") if feedback else None
    if not isinstance(note, str) or not note.strip():
        return False
    return not needs_script_revision(note) and not needs_voice_revision(note)


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
        if job.status == "DRAFT" and job.pending_input is None and job.message == REVISE_SETTLED_MESSAGE:
            return state_context(self.repo, state, route="end")
        decision = interrupt(pending)
        if decision.get("decision") == "cancel":
            job = self.repo.cancel(job.job_id)
            return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
        if decision.get("decision") == "revise":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message=REVISE_SETTLED_MESSAGE, pending_input=None)
            return state_context(self.repo, state, route="end", human_decision={**pending, **decision})
        if decision.get("decision") != "confirm":
            raise Conflict("恢复决定无效")
        # Input confirmations always rerun the responsible stage and its gates.
        target = {"materials": "materials", "script": "screenwriter", "voice": "voice", "director": "director", "render": "editing"}[pending["stage"]]
        layout_repair = False
        if pending.get("retry_node") == "director_demo":
            # Older checkpoints tagged copy-fit failures as render-only retries.
            # Confirm still repairs the frozen plan through the photography node;
            # it does not approve the shots or replay a provider submission.
            layout_repair = (state.get("action") != "refresh_shots"
                and pending.get("stage") == "director"
                and set(pending.get("fields") or []) == {"render"}
                and not pending.get("operation_status")
                and render_text_fit_issues(pending.get("issues") or []))
            target = "director" if layout_repair else "director_demo"
        if target == "voice" and _legacy_director_voice_false_positive(pending, state):
            target = "director"
        if target == "director" and _stale_editing_preflight(self.repo, job, pending):
            target = "editing"
        return state_context(self.repo, state, route=target, human_decision={**pending, **decision},
                             **({"gate_issues": pending["issues"]} if layout_repair else {}))
