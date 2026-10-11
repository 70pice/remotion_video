"""Old editor contracts are rechecked without bypassing director approval."""
import pytest

from videoagents.contracts import Brief, Timeline
from videoagents.nodes.await_input import AwaitInputNode
from videoagents.nodes.editing import editing_instruction_fingerprint
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository


@pytest.mark.parametrize("case, expected_route", [
    ("legacy", "editing"), ("updated", "editing"), ("current", "director"),
    ("unapproved", "director"), ("different-issue", "director"),
    ("different-fields", "director"), ("changed-input", "director"),
])
def test_old_editing_advice_rechecks_only_matching_approved_inputs(tmp_path, monkeypatch, case, expected_route):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT"))
    job = repo.update_job(job.job_id, timeline=Timeline(job_id=job.job_id, revision=job.revision,
        width=1080, height=1920, fps=30, duration_in_frames=90, shots=[
            {"shot_id": "shot", "start_frame": 0, "end_frame": 90, "component_id": "title",
             "title": "持续信息", "layers": [{"component_id": "Snapcn-TextReveal", "role": "title",
                 "title": "强调", "start_frame": 0, "end_frame": 90}]}]))
    advice = {"pacing_notes": [], "layout_notes": [], "findings": [
        {"severity": "error", "owner": "director", "blocking": True, "message": "UNIT：旧契约"}]}
    artifact = service.write_json(job, "editing_guidance.json", advice, "editing_guidance")
    if case != "legacy":
        repo.update_artifact_metadata(artifact.artifact_id, {
            "instruction_fingerprint": editing_instruction_fingerprint(job) if case == "current" else "old-instruction",
            "dependency_fingerprint": "other-input" if case == "changed-input" else dependency_fingerprint(job)})
    pending = {"kind": "input", "stage": "director", "revision": job.revision,
               "issues": ["剪辑发现分镜问题：UNIT：旧契约"], "fields": ["timeline"],
               "thread_id": "UNIT", "pending_token": "UNIT-token"}
    if case == "different-issue":
        pending["issues"] = ["实际素材缺失"]
    if case == "different-fields":
        pending["fields"] = ["assets"]
    job = repo.update_job(job.job_id, status="NEEDS_INPUT", stage="director", pending_input=pending)
    monkeypatch.setattr("videoagents.nodes.await_input.interrupt", lambda payload: {"decision": "confirm"})
    monkeypatch.setattr("videoagents.nodes.director_review.director_demo_is_approved",
                        lambda repository, current: case != "unapproved")
    state = VideoState(job_id=job.job_id, revision=job.revision, action="produce", pending_snapshot=pending)
    result = AwaitInputNode(repo, service)(state)
    assert result["route"] == expected_route
    assert repo.get_job(job.job_id).timeline == job.timeline
    assert not any(a.kind == "stage_review" for a in repo.get_job(job.job_id).artifacts)
