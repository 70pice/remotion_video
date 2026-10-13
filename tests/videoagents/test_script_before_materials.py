"""Real graph pauses and receipts, with collection and models doubled."""

import json

import pytest
from langgraph.graph import START, StateGraph

from videoagents.contracts import Brief, DraftRequest, Script, ScriptSegment
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import state_context
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.script_review import (
    SCRIPT_REVIEW_NODE,
    script_before_materials_is_approved,
)
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.runner import Worker


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    project = tmp_path / "project"
    job = repo.create_job(Brief(script_text="UNIT：明确给出的测试文案。"))
    calls = []

    def materials(node, state):
        calls.append(state["revision"])
        return state_context(repo, state, route="human_review_script")

    monkeypatch.setattr(MaterialsNode, "__call__", materials)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call",
                        lambda *a, **kw: pytest.fail("Unexpected paid model call"))
    return repo, project, job, calls


def start(pipeline):
    repo, project, job, _ = pipeline
    repo.enqueue(job.job_id, {"action": "produce", "base_revision": job.revision, "idempotency_key": "UNIT-start"})
    assert Worker(repo, project).once()
    return repo.get_job(job.job_id)


def confirm(repo, project, job, key="UNIT-confirm"):
    repo.enqueue(job.job_id, {"action": "resume", "base_revision": job.revision,
        "pending_token": job.pending_input["pending_token"], "decision": "confirm",
        "note": "UNIT：已核对当前文案与来源，允许素材采集。", "idempotency_key": key})
    assert Worker(repo, project).once()
    return repo.get_job(job.job_id)


def test_default_run_stops_before_any_material_call_and_confirm_only_releases_collection(pipeline):
    repo, project, _, calls = pipeline
    paused = start(pipeline)
    assert paused.status == "NEEDS_HUMAN" and paused.pending_input["node_name"] == SCRIPT_REVIEW_NODE
    assert paused.pending_input["stage"] == "script" and paused.assets == [] and calls == []
    assert not script_before_materials_is_approved(repo, paused)
    collected = confirm(repo, project, paused)
    assert calls == [paused.revision]
    assert collected.pending_input["node_name"] == "human_review_script"
    assert script_before_materials_is_approved(repo, collected)
    assert not any(item.kind in {"voice", "final"} for item in collected.artifacts)


def test_new_revision_does_not_inherit_pre_collection_approval(pipeline):
    repo, project, _, calls = pipeline
    approved = confirm(repo, project, start(pipeline))
    revised = JobService(repo, project).draft(approved.job_id, DraftRequest(
        base_revision=approved.revision, script=Script(title="UNIT new revision", revision=approved.revision, segments=[
            ScriptSegment(segment_id="s1", narration="UNIT：下一版文案。")]),
    ))
    repo.enqueue(revised.job_id, {"action": "produce", "base_revision": revised.revision, "idempotency_key": "UNIT-r2"})
    assert Worker(repo, project).once()
    paused = repo.get_job(revised.job_id)
    assert paused.pending_input["node_name"] == SCRIPT_REVIEW_NODE
    assert calls == [approved.revision]
    assert not script_before_materials_is_approved(repo, paused)


@pytest.mark.parametrize("decision", ["cancel", "revise"])
def test_pre_collection_cancel_or_revise_never_calls_materials(pipeline, monkeypatch, decision):
    repo, project, _, calls = pipeline
    paused = start(pipeline)
    if decision == "revise":
        monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **kw: {
            "response": "UNIT revised", "script": {"title": "UNIT revised", "revision": paused.revision, "segments": [
                {"segment_id": "s1", "narration": "UNIT：改过的新文案。"}]}})
    repo.enqueue(paused.job_id, {"action": "resume", "base_revision": paused.revision,
        "pending_token": paused.pending_input["pending_token"], "decision": decision,
        "note": "UNIT：取消或要求重写文案，不能先取素材。", "idempotency_key": "UNIT-revise"})
    assert Worker(repo, project).once()
    current = repo.get_job(paused.job_id)
    assert calls == []
    if decision == "revise":
        assert current.pending_input["node_name"] == SCRIPT_REVIEW_NODE
        assert current.pending_input["pending_token"] != paused.pending_input["pending_token"]
    else:
        assert current.status == "CANCELLED"


def test_materials_checkpoint_without_new_gate_receipt_routes_to_pre_review(pipeline):
    repo, project, job, calls = pipeline
    paused = start(pipeline)
    state = VideoState(job_id=job.job_id, revision=paused.revision, run_id="UNIT-old",
                       thread_id="UNIT-old", action="produce", route="materials")
    with VideoProductionGraph(repo, project) as graph:
        # The callable attached to the retained node name guards direct old schedules.
        result = graph.materials_after_script_review(state)
    assert result["route"] == SCRIPT_REVIEW_NODE and calls == []


def test_real_old_checkpoint_scheduled_at_materials_is_redirected_without_collection(pipeline):
    repo, project, job, calls = pipeline
    paused = start(pipeline)
    config = {"configurable": {"thread_id": "UNIT-legacy-materials"}}
    state = state_context(repo, VideoState(job_id=job.job_id, revision=paused.revision,
                                          run_id="UNIT-old", thread_id="UNIT-legacy-materials", action="produce"))
    with VideoProductionGraph(repo, project) as graph:
        old = StateGraph(VideoState)
        old.add_node("old_writer", lambda value: state_context(repo, value, route="materials"))
        def failed_materials(value):
            raise RuntimeError("UNIT saved before material call")
        old.add_node("materials", failed_materials)
        old.add_edge(START, "old_writer")
        old.add_edge("old_writer", "materials")
        previous = old.compile(checkpointer=graph.checkpointer)
        with pytest.raises(RuntimeError):
            previous.invoke(state, config)
        assert previous.get_state(config).next == ("materials",)
        graph.graph.invoke(None, config)
        checkpoint = graph.graph.get_state(config)
    assert calls == []
    assert checkpoint.interrupts[0].value["node_name"] == SCRIPT_REVIEW_NODE
    assert repo.get_job(job.job_id).pending_input["node_name"] == SCRIPT_REVIEW_NODE


@pytest.mark.parametrize("status", ["SUBMITTING", "UNKNOWN"])
def test_old_unknown_materials_barrier_is_preserved_ahead_of_new_gate(pipeline, status):
    repo, project, job, calls = pipeline
    paused = start(pipeline)
    operation = repo.start_operation(job.job_id, "UNIT-unsettled", "llm:materials", {"revision": paused.revision})
    if status == "UNKNOWN":
        repo.finish_operation(operation["operation_id"], status, {"revision": paused.revision, "reason": "UNIT"})
    state = VideoState(job_id=job.job_id, revision=paused.revision, run_id="UNIT-old",
                       thread_id="UNIT-old", action="produce", route="materials")
    with VideoProductionGraph(repo, project) as graph:
        result = graph.materials_after_script_review(state)
    current = repo.get_job(job.job_id)
    assert result["route"] == "await_input" and current.status == "NEEDS_INPUT" and calls == []
    assert current.pending_input["operation_id"] == operation["operation_id"]
    assert current.pending_input["operation_status"] == status
    assert repo.unsettled_operation(job.job_id, "llm:materials", paused.revision)["status"] == status
    assert not script_before_materials_is_approved(repo, current)


def test_confirm_receipt_cannot_survive_script_change_or_tampering(pipeline):
    repo, project, _, _ = pipeline
    current = confirm(repo, project, start(pipeline))
    assert script_before_materials_is_approved(repo, current)
    changed = current.script.model_copy(deep=True)
    changed.segments[0].narration += "UNIT changed"
    repo.update_job(current.job_id, current.revision, script=changed)
    assert not script_before_materials_is_approved(repo, repo.get_job(current.job_id))
    receipt = next(item for item in current.artifacts if item.kind == "stage_review")
    path, _, _ = repo.artifact_path(receipt.artifact_id)
    path.write_text(json.dumps({"decision": "confirm"}), encoding="utf-8")
    with pytest.raises(Conflict, match="回执已改变"):
        script_before_materials_is_approved(repo, repo.get_job(current.job_id))


def test_voice_only_option_cannot_bypass_materials_review_at_pre_gate(pipeline):
    repo, _, _, _ = pipeline
    paused = start(pipeline)
    with pytest.raises(Conflict, match="只跑配音"):
        repo.enqueue(paused.job_id, {"action": "resume", "base_revision": paused.revision,
            "pending_token": paused.pending_input["pending_token"], "decision": "confirm", "stop_after": "voice",
            "note": "UNIT：文案确认不能跳过素材审核。", "idempotency_key": "UNIT-voice"})


def test_material_outputs_do_not_invalidate_the_pre_collection_receipt(pipeline):
    repo, project, _, _ = pipeline
    current = confirm(repo, project, start(pipeline))
    JobService(repo, project).write_json(current, "research.json", {
        "status": "COMPLETED", "sources": [], "visuals": [], "limitations": ["UNIT frozen research"]}, "research")
    assert script_before_materials_is_approved(repo, repo.get_job(current.job_id))
