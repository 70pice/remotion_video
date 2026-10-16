"""Old editor contracts are rechecked without bypassing director approval."""
import os

import pytest
from test_director_shot_review import shot_subject as shot_subject
from test_director_shot_review import write_review_package

from videoagents.contracts import Brief, Timeline
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.await_input import AwaitInputNode
from videoagents.nodes.common import state_context
from videoagents.nodes.editing import editing_instruction_fingerprint
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from worker.runner import Worker


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


def test_normal_resume_rechecks_changed_editor_contract_without_replanning(shot_subject, monkeypatch):
    import videoagents.nodes.editing as editing

    repo, service, _, _, _ = shot_subject
    job, _, _ = write_review_package(shot_subject)
    current_prompt = editing.PROMPT
    monkeypatch.setattr(editing, "PROMPT", "UNIT old preflight without current human visual decisions")
    monkeypatch.setattr("videoagents.nodes.human_review.HumanReviewNode._sync_feishu", lambda *a: None)
    for node in ("director.DirectorNode", "voice.VoiceNode"):
        monkeypatch.setattr(f"videoagents.nodes.{node}.__call__", lambda *a: pytest.fail("recheck called another role"))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda self, role: role == "editing")
    calls = []

    def preflight(model, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert role == "editing" and context["extras"]["visual_review"]["shot_review_confirmation"]
        calls.append(instruction)
        findings = [{"severity": "error", "owner": "director", "blocking": True,
                     "message": "UNIT old visual preference conflicts with the confirmed choice"}] if len(calls) == 1 else []
        return {"pacing_notes": [], "layout_notes": [], "findings": findings}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", preflight)

    def render(project, timeline, output, cover, mode, timeout, cancelled, progress, *, frame_range=None):
        assert mode == "final"
        output.write_bytes(b"UNIT synthetic final for graph routing")

    monkeypatch.setattr(editing, "render", render)
    repo.enqueue(job.job_id, {"action": "produce", "base_revision": job.revision,
                              "idempotency_key": "unit-editor-human-gate"})
    command = repo.claim(os.getpid())
    thread = f"job:{job.job_id}:run:{command['command_id']}"
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
        run_id=command["command_id"], thread_id=thread, route="director_demo", extras={}))
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.graph.update_state({"configurable": {"thread_id": thread}}, state, as_node="clear_director")
        graph.execute(command)
    repo.finish(command["command_id"])
    waiting = repo.get_job(job.job_id)
    repo.enqueue(job.job_id, {"action": "resume", "base_revision": job.revision, "decision": "confirm",
        "note": "UNIT: all actual shot frames confirmed, continue to final.", "reviewed_shot_ids": ["shot1", "shot2"],
        "pending_token": waiting.pending_input["pending_token"], "idempotency_key": "unit-editor-confirm-shots"})
    assert Worker(repo, service.project_root).once()
    blocked = repo.get_job(job.job_id)
    assert blocked.status == "NEEDS_INPUT" and blocked.stage == "director"
    assert blocked.pending_input["fields"] == ["timeline"]
    guidance = next(item for item in blocked.artifacts if item.kind == "editing_guidance")
    original_guidance = repo.artifact_path(guidance.artifact_id)[0].read_bytes()
    monkeypatch.setattr(editing, "PROMPT", current_prompt)
    repo.enqueue(job.job_id, {"action": "resume", "base_revision": job.revision, "decision": "confirm",
        "note": "UNIT: recheck with the updated editor contract, preserve the frozen plan.",
        "pending_token": blocked.pending_input["pending_token"], "idempotency_key": "unit-editor-recheck"})
    assert Worker(repo, service.project_root).once()
    final = repo.get_job(job.job_id)
    assert final.status == "DRAFT" and final.stage == "complete" and len(calls) == 2
    assert final.timeline == job.timeline and final.script == job.script and final.assets == job.assets
    assert repo.artifact_path(guidance.artifact_id)[0].read_bytes() == original_guidance
    assert any(item.kind == "final" for item in final.artifacts)
