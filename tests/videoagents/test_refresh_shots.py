"""Refresh unchanged all-shot frames through a new durable graph command."""

import copy
import os

import pytest
from test_director_shot_review import frame_render_double, write_review_package
from test_director_shot_review import shot_subject as shot_subject

from videoagents.contracts import RefreshShotsRequest, RetryFailedRunRequest
from videoagents.graph import VideoProductionGraph
from videoagents.main import build_parser
from videoagents.nodes.common import state_context
from videoagents.nodes.director_demo import DirectorDemoNode
from videoagents.nodes.director_review import current_shot_review_artifact, director_demo_is_approved
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict
from worker.runner import Worker


@pytest.fixture
def waiting_shots(shot_subject, monkeypatch):
    repo, service, job, _, _ = shot_subject
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call",
                        lambda *a, **k: pytest.fail("refresh must not call a production model"))
    monkeypatch.setattr("videoagents.nodes.voice.VoiceNode.__call__",
                        lambda *a, **k: pytest.fail("refresh must not synthesize voice"))
    monkeypatch.setattr("videoagents.nodes.editing.EditingNode.render_video",
                        lambda *a, **k: pytest.fail("refresh must not render a video"))
    monkeypatch.setattr("videoagents.nodes.human_review.HumanReviewNode._sync_feishu", lambda *a: None)
    job, _, _ = write_review_package(shot_subject)
    repo.enqueue(job.job_id, {"action": "produce", "base_revision": job.revision,
                              "idempotency_key": "unit-refresh-original"})
    command = repo.claim(os.getpid())
    thread_id = f"job:{job.job_id}:run:{command['command_id']}"
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision,
        action="produce", run_id=command["command_id"], thread_id=thread_id, route="director_demo", extras={}))
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.graph.update_state({"configurable": {"thread_id": thread_id}}, state, as_node="clear_director")
        graph.execute(command)
    repo.finish(command["command_id"])
    return repo, service, repo.get_job(job.job_id), shot_subject[3]


def refresh_request(subject, key="unit-refresh-frames"):
    _, _, job, plan = subject
    return {"action": "refresh_shots", **RefreshShotsRequest(base_revision=job.revision,
        pending_token=job.pending_input["pending_token"], director_plan_artifact_id=plan.artifact_id,
        director_plan_sha256=plan.sha256, idempotency_key=key).model_dump()}


def test_cli_refresh_is_idempotent_changes_gate_and_preserves_inputs(waiting_shots, monkeypatch, capsys):
    repo, service, before, _ = waiting_shots
    old_review, _ = current_shot_review_artifact(repo, before)
    old_files = {item.artifact_id: repo.artifact_path(item.artifact_id)[0].read_bytes()
                 for item in before.artifacts}
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls))
    monkeypatch.setattr("videoagents.main._worker", lambda repository: Worker(repository, service.project_root))
    args = build_parser().parse_args(["--runtime-dir", str(repo.root), "refresh-shots", before.job_id,
                                     "--idempotency-key", "unit-cli-refresh-frames"])
    assert args.handler(args) == 0
    after = repo.get_job(before.job_id)
    new_review, _ = current_shot_review_artifact(repo, after)
    assert len(calls) == 1 and new_review.artifact_id != old_review.artifact_id
    assert after.status == "NEEDS_HUMAN" and after.stage == "director"
    assert after.pending_input["pending_token"] != before.pending_input["pending_token"]
    assert after.pending_input["thread_id"] != before.pending_input["thread_id"]
    assert after.pending_input["required_shot_ids"] == ["shot1", "shot2"]
    for name in ("revision", "brief", "script", "assets", "timeline", "director_requirements"):
        assert getattr(after, name) == getattr(before, name)
    assert all(repo.artifact_path(key)[0].read_bytes() == value for key, value in old_files.items())
    assert not director_demo_is_approved(repo, after)
    assert not any(item.kind == "stage_review" for item in after.artifacts)
    assert args.handler(args) == 0
    assert len(calls) == 1 and repo.get_job(before.job_id).pending_input == after.pending_input
    with repo.connection() as db:
        assert db.execute("SELECT count(*) FROM commands WHERE job_id=?", (after.job_id,)).fetchone()[0] == 2
    with pytest.raises(Conflict, match="中断已变化"):
        repo.enqueue(after.job_id, {"action": "resume", "base_revision": after.revision,
            "pending_token": before.pending_input["pending_token"], "decision": "confirm", "note": "UNIT old token",
            "idempotency_key": "unit-old-shot-token"})
    capsys.readouterr()


@pytest.mark.parametrize("changed", ["revision", "token", "plan_id", "plan_hash", "status", "mode", "node", "inputs"])
def test_refresh_queue_rejects_stale_or_wrong_subject(waiting_shots, changed):
    repo, _, job, _ = waiting_shots
    payload = refresh_request(waiting_shots)
    if changed == "revision":
        payload["base_revision"] += 1
    elif changed == "token":
        payload["pending_token"] = "f" * 32
    elif changed == "plan_id":
        payload["director_plan_artifact_id"] = "f" * 32
    elif changed == "plan_hash":
        payload["director_plan_sha256"] = "f" * 64
    elif changed == "status":
        repo.update_job(job.job_id, status="DRAFT")
    elif changed == "inputs":
        timeline = job.timeline.model_copy(deep=True)
        timeline.shots[0].title = "Changed frozen shot"
        repo.update_job(job.job_id, timeline=timeline)
    else:
        pending = copy.deepcopy(job.pending_input)
        pending["review_mode" if changed == "mode" else "node_name"] = "legacy"
        repo.update_job(job.job_id, pending_input=pending)
    with pytest.raises(Conflict):
        repo.enqueue(job.job_id, payload)
    with repo.connection() as db:
        assert db.execute("SELECT count(*) FROM commands WHERE job_id=?", (job.job_id,)).fetchone()[0] == 1


@pytest.mark.parametrize("status", ["PENDING", "CLAIMED"])
def test_refresh_blocks_active_command(waiting_shots, status):
    repo, _, job, _ = waiting_shots
    repo.enqueue(job.job_id, refresh_request(waiting_shots))
    if status == "CLAIMED":
        assert repo.claim(os.getpid())
    with pytest.raises(Conflict, match="待执行或执行中"):
        repo.enqueue(job.job_id, refresh_request(waiting_shots, "unit-second-refresh"))


@pytest.mark.parametrize("status", ["SUBMITTING", "UNKNOWN"])
def test_refresh_blocks_unsettled_current_operation(waiting_shots, status):
    repo, _, job, _ = waiting_shots
    operation = repo.start_operation(job.job_id, "unit-unsettled", "llm:director", {"revision": job.revision})
    if status == "UNKNOWN":
        repo.finish_operation(operation["operation_id"], status, {"revision": job.revision})
    with pytest.raises(Conflict, match="状态未知"):
        repo.enqueue(job.job_id, refresh_request(waiting_shots))


def test_refresh_key_cannot_change_binding(waiting_shots):
    repo, _, job, _ = waiting_shots
    payload = refresh_request(waiting_shots)
    repo.enqueue(job.job_id, payload)
    repo.enqueue(job.job_id, payload)
    with pytest.raises(Conflict, match="幂等键"):
        repo.enqueue(job.job_id, {**payload, "director_plan_sha256": "f" * 64})


def test_refresh_reclaim_at_new_gate_does_not_render_again(waiting_shots, monkeypatch):
    repo, service, job, _ = waiting_shots
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls))
    repo.enqueue(job.job_id, refresh_request(waiting_shots))
    command = repo.claim(os.getpid())
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
        pending = repo.get_job(job.job_id).pending_input
        graph.execute(command)
    assert len(calls) == 1
    assert repo.get_job(job.job_id).pending_input == pending


def test_failed_refresh_after_publish_retries_saved_node_without_second_render(waiting_shots, monkeypatch):
    repo, service, job, _ = waiting_shots
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls))
    original = DirectorDemoNode.render_shots

    def crash_after_publish(node, current, **kwargs):
        original(node, current, **kwargs)
        raise RuntimeError("UNIT worker stopped after complete package publication")

    monkeypatch.setattr(DirectorDemoNode, "render_shots", crash_after_publish)
    repo.enqueue(job.job_id, refresh_request(waiting_shots))
    assert Worker(repo, service.project_root).once()
    assert repo.get_job(job.job_id).status == "FAILED" and len(calls) == 1
    with repo.connection() as db:
        failed = db.execute("SELECT command_id FROM commands WHERE job_id=? AND status='FAILED'",
                            (job.job_id,)).fetchone()[0]
    JobService(repo, service.project_root).retry_failed_run(job.job_id, RetryFailedRunRequest(
        base_revision=job.revision, retry_command_id=failed, idempotency_key="unit-refresh-crash-retry"))
    assert Worker(repo, service.project_root).once()
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN" and len(calls) == 1
    assert current.pending_input["pending_token"] != job.pending_input["pending_token"]
    assert current.timeline == job.timeline and not director_demo_is_approved(repo, current)


@pytest.mark.parametrize("failure", [TimeoutError("UNIT timeout"), ValueError(
    "Remotion 渲染失败：WordFlip production slot 200x110 cannot fit its words at 42px with at most two lines. "
    "Increase this slot or split the words.")])
def test_refresh_render_failure_resumes_same_plan_without_model(waiting_shots, monkeypatch, failure):
    repo, service, job, _ = waiting_shots
    calls, attempts = [], []
    render = frame_render_double(calls)

    def fail_once(*args, **kwargs):
        attempts.append(True)
        if len(attempts) == 1:
            raise failure
        return render(*args, **kwargs)

    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", fail_once)
    repo.enqueue(job.job_id, refresh_request(waiting_shots))
    assert Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.pending_input["retry_node"] == "director_demo"
    assert paused.pending_input["fields"] == ["render"]
    repo.enqueue(job.job_id, {"action": "resume", "base_revision": job.revision,
        "pending_token": paused.pending_input["pending_token"], "decision": "confirm", "note": "UNIT render retry",
        "idempotency_key": "unit-refresh-render-retry"})
    assert Worker(repo, service.project_root).once()
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN" and len(attempts) == 2 and len(calls) == 1
    assert current.pending_input["review_mode"] == "per_shot_stills"
    assert current.timeline == job.timeline and not director_demo_is_approved(repo, current)
