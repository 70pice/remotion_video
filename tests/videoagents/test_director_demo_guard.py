"""The final-render boundary fails closed, including legacy checkpoint entry."""

import json

import pytest

from videoagents.contracts import Alignment, AlignmentSegment, Brief, Script, ScriptSegment, Shot, Timeline
from videoagents.nodes.common import state_context
from videoagents.nodes.director import _performance_payload
from videoagents.nodes.director_review import director_demo_is_approved, director_review_fingerprint
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.process_manager import RenderCancelled


@pytest.fixture
def review_subject(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT: final-render boundary", width=240, height=426, fps=15))
    script = Script(title="UNIT", revision=job.revision, origin="user",
                    segments=[ScriptSegment(segment_id="s1", narration="UNIT narration.")])
    timeline = Timeline(job_id=job.job_id, revision=job.revision, width=240, height=426, fps=15,
                        duration_in_frames=900,
                        shots=[Shot(shot_id="shot1", start_frame=0, end_frame=900,
                                    component_id="title", title="UNIT: one continuous shot")])
    job = repo.update_job(job.job_id, script=script, timeline=timeline)
    alignment = Alignment(origin="manual", verified=True, audio_sha256="a" * 64,
                          segments=[AlignmentSegment(segment_id="s1", text="UNIT narration.",
                                                     start_ms=0, end_ms=60000)])
    plan = _performance_payload("existing_timeline", job, timeline, alignment)
    plan["demo"] = {"start_frame": 450, "end_frame": 900, "reason": "UNIT: second half."}
    plan_artifact = service.write_json(job, "unit-plan.json", plan, "director_plan")
    # Synthetic bytes deliberately test receipts, not playable media quality.
    preview = service.write_json(job, "unit-preview.json", {"synthetic": True}, "preview")
    repo.update_artifact_metadata(preview.artifact_id, {
        "dependency_fingerprint": dependency_fingerprint(job),
        "director_plan_sha256": plan_artifact.sha256, "frame_range": [450, 900],
    })
    return repo, service, repo.get_job(job.job_id), preview


def record_unit_approval(repo, service, job, decision="confirm"):
    service.write_json(job, "unit-review.json", {
        "node_name": "director_human_gate", "revision": job.revision, "decision": decision,
        "dependency_fingerprint": director_review_fingerprint(repo, job),
    }, "stage_review")
    return repo.get_job(job.job_id)


def editing_state(repo, job):
    return state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                                        thread_id="UNIT-boundary", run_id="UNIT-boundary", extras={}))


def test_legacy_editing_entry_without_demo_approval_cannot_render(review_subject, monkeypatch):
    repo, service, job, _ = review_subject
    monkeypatch.setattr(EditingNode, "render_video", lambda *a, **k: pytest.fail("unapproved final render"))
    assert EditingNode(repo, service)(editing_state(repo, job))["route"] == "director_demo"
    assert not any(item.kind == "final" for item in repo.get_job(job.job_id).artifacts)


@pytest.mark.parametrize("change", ["demo_bytes", "demo_range", "plan_bytes", "latest_revise", "timeline"])
def test_old_confirmation_does_not_approve_changed_subject(review_subject, change):
    repo, service, job, preview = review_subject
    job = record_unit_approval(repo, service, job)
    assert director_demo_is_approved(repo, job)
    if change == "demo_bytes":
        repo.artifact_path(preview.artifact_id)[0].write_bytes(b"changed unit demo")
    elif change == "demo_range":
        metadata = repo.artifact_metadata(preview.artifact_id)
        repo.update_artifact_metadata(preview.artifact_id, {**metadata, "frame_range": [0, 450]})
    elif change == "plan_bytes":
        plan = next(item for item in job.artifacts if item.kind == "director_plan")
        path = repo.artifact_path(plan.artifact_id)[0]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["demo"]["reason"] = "Changed after approval."
        path.write_text(json.dumps(payload), encoding="utf-8")
    elif change == "latest_revise":
        job = record_unit_approval(repo, service, job, "revise")
    else:
        changed = job.timeline.model_copy(deep=True)
        changed.shots[0].title = "Changed after approval."
        job = repo.update_job(job.job_id, timeline=changed)
    if change in {"demo_bytes", "plan_bytes"}:
        with pytest.raises(Conflict, match="产物已改变"):
            director_demo_is_approved(repo, job)
    else:
        assert not director_demo_is_approved(repo, job)


def test_confirmed_final_replay_reuses_committed_output(review_subject, monkeypatch):
    repo, service, job, _ = review_subject
    job = record_unit_approval(repo, service, job)
    calls = []

    def render_double(node, current, mode, state=None):
        calls.append(mode)
        artifact = service.write_json(current, "unit-final.json", {"synthetic": True}, "final")
        repo.update_artifact_metadata(artifact.artifact_id,
                                      {"dependency_fingerprint": dependency_fingerprint(current)})

    monkeypatch.setattr(EditingNode, "render_video", render_double)
    node = EditingNode(repo, service)
    state = editing_state(repo, job)
    assert node(state)["route"] == "end"
    assert node(state)["route"] == "end"
    assert calls == ["final"]
    assert repo.get_job(job.job_id).stage == "complete"


def test_cancellation_blocks_even_a_confirmed_final(review_subject, monkeypatch):
    repo, service, job, _ = review_subject
    job = record_unit_approval(repo, service, job)
    state = editing_state(repo, job)
    repo.cancel(job.job_id)
    monkeypatch.setattr(EditingNode, "render_video", lambda *a, **k: pytest.fail("cancelled final render"))
    with pytest.raises(RenderCancelled):
        EditingNode(repo, service)(state)
