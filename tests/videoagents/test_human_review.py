import json
import os

import pytest
from langgraph.graph import END, START, StateGraph

from videoagents.contracts import Brief, DraftRequest
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import request_input
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.voice import VoiceNode
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.runner import Worker

NOTE = "UNIT TEST：已核对本阶段文案表达、事实来源及素材。"


def seed_completed_research(repo: Repository, project, job) -> None:
    current = repo.get_job(job.job_id)
    if any(item.kind == "research" and item.revision == current.revision for item in current.artifacts):
        return
    JobService(repo, project).write_json(current, "research.json", {
        "schema_version": "3",
        "status": "COMPLETED",
        "sources": [],
        "visuals": [],
        "limitations": ["UNIT TEST：人工审核测试夹具，素材节点研究结果已显式冻结为空。"],
    }, "research")


@pytest.fixture
def wired_job(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    project = tmp_path / "project"
    job = repo.create_job(Brief(script_text="观点：人工审核测试。"))
    add_edges = StateGraph.add_conditional_edges

    def wire_script_review(builder, source, path, path_map=None, **kwargs):
        if source == "script_gate":
            path_map = dict(path_map, voice="human_review")
        return add_edges(builder, source, path, path_map, **kwargs)

    monkeypatch.setattr(StateGraph, "add_conditional_edges", wire_script_review)
    calls = []

    def downstream(self, state):
        calls.append(state["job_id"])
        return request_input(self.repo, state, "voice", ["UNIT TEST：继续到配音配置检查"], ["voice"])

    monkeypatch.setattr(VoiceNode, "__call__", downstream)
    return repo, project, job, calls


def start(repo, project, job, key="UNIT-start"):
    seed_completed_research(repo, project, job)
    repo.enqueue(job.job_id, {"action": "produce", "base_revision": job.revision, "idempotency_key": key})
    assert Worker(repo, project).once()
    return repo.get_job(job.job_id)


def answer(repo, job, decision="confirm", note=NOTE, key="UNIT-resume"):
    repo.enqueue(job.job_id, {"action": "resume", "base_revision": job.revision,
        "pending_token": job.pending_input["pending_token"], "decision": decision, "note": note,
        "idempotency_key": key})


def test_optional_node_is_registered_without_changing_default_flow(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：默认流程测试。"))
    with VideoProductionGraph(repo, tmp_path / "project") as graph:
        topology = graph.graph.get_graph()
        assert "human_review" in topology.nodes
        assert not any(edge.target == "human_review" and edge.source != "human_review" for edge in topology.edges)
    result = start(repo, tmp_path / "project", job)
    assert result.status == "NEEDS_INPUT" and result.stage == "voice"
    assert result.pending_input["kind"] == "input"


def test_wired_review_pauses_before_downstream_and_recovers_after_reopen(wired_job):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    assert paused.status == "NEEDS_HUMAN" and paused.stage == "script"
    assert paused.pending_input["kind"] == "stage_review"
    assert paused.pending_input["title"] == "文案人工审核"
    assert paused.pending_input["revision"] == paused.revision
    assert paused.review is None and not calls
    with VideoProductionGraph(repo, project) as graph:
        snapshot = graph.graph.get_state({"configurable": {"thread_id": paused.pending_input["thread_id"]}})
        assert snapshot.interrupts[0].value["pending_token"] == paused.pending_input["pending_token"]
    # Worker creates a new graph and SQLite connection for the resume.
    answer(repo, paused)
    assert Worker(repo, project).once()
    current = repo.get_job(job.job_id)
    assert calls == [job.job_id]
    assert current.status == "NEEDS_INPUT" and current.stage == "voice"
    assert current.review is None  # Stage approval does not approve publication.
    report = next(item for item in current.artifacts if item.kind == "stage_review")
    receipt = json.loads(repo.artifact_path(report.artifact_id)[0].read_text(encoding="utf-8"))
    assert receipt["note"] == NOTE and receipt["decision"] == "confirm"
    assert receipt["dependency_fingerprint"] == paused.pending_input["dependency_fingerprint"]


@pytest.mark.parametrize("decision,status", [("revise", "DRAFT"), ("cancel", "CANCELLED")])
def test_revise_and_cancel_stop_without_running_downstream(wired_job, decision, status):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    answer(repo, paused, decision, "UNIT：此阶段需要修改")
    Worker(repo, project).once()
    current = repo.get_job(job.job_id)
    assert current.status == status and current.pending_input is None and not calls
    report = next(item for item in current.artifacts if item.kind == "stage_review")
    assert json.loads(repo.artifact_path(report.artifact_id)[0].read_text(encoding="utf-8"))["decision"] == decision
    if decision == "revise":
        updated = JobService(repo, project).draft(job.job_id, DraftRequest(base_revision=current.revision,
            brief=current.brief.model_copy(update={"script_text": "观点：修订后的测试文案。"})))
        new_pause = start(repo, project, updated, "UNIT-new-revision")
        assert new_pause.revision == current.revision + 1 and new_pause.status == "NEEDS_HUMAN"
        assert new_pause.pending_input["pending_token"] != paused.pending_input["pending_token"]


def test_short_note_creates_new_pending_and_old_reply_cannot_release_it(wired_job):
    repo, project, job, calls = wired_job
    old = start(repo, project, job)
    answer(repo, old, note="short")
    Worker(repo, project).once()
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN" and not calls
    assert current.pending_input["pending_token"] != old.pending_input["pending_token"]
    assert "10" in current.pending_input["issues"][0]
    with pytest.raises(Conflict):
        answer(repo, old, key="UNIT-stale-answer")
    answer(repo, current, key="UNIT-valid-answer")
    Worker(repo, project).once()
    assert calls == [job.job_id]


def test_reclaimed_answer_does_not_answer_downstream_interrupt(wired_job):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    answer(repo, paused)
    command = repo.claim(os.getpid())
    with VideoProductionGraph(repo, project) as graph:
        graph.execute(command)
    downstream = repo.get_job(job.job_id)
    with VideoProductionGraph(repo, project) as graph:
        graph.execute(command)
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT" and calls == [job.job_id]
    assert current.pending_input["pending_token"] == downstream.pending_input["pending_token"]
    assert len([item for item in current.artifacts if item.kind == "stage_review"]) == 1
    repo.finish(command["command_id"])


def test_confirmation_receipt_replays_after_sql_save_before_checkpoint(wired_job, monkeypatch):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    answer(repo, paused)
    command = repo.claim(os.getpid())
    update = repo.update_job
    crashed = []

    def crash(job_id, expected_revision=None, **changes):
        result = update(job_id, expected_revision, **changes)
        if changes.get("status") == "RUNNING" and "已确认" in changes.get("message", "") and not crashed:
            crashed.append(True)
            raise SystemExit("UNIT loss after stage approval SQL commit")
        return result

    monkeypatch.setattr(repo, "update_job", crash)
    with VideoProductionGraph(repo, project) as graph, pytest.raises(SystemExit):
        graph.execute(command)
    assert not calls
    with VideoProductionGraph(repo, project) as graph:
        graph.execute(command)
    current = repo.get_job(job.job_id)
    assert calls == [job.job_id] and current.status == "NEEDS_INPUT"
    assert len([item for item in current.artifacts if item.kind == "stage_review"]) == 1
    assert len(list((repo.root / "jobs" / job.job_id).rglob("stage-review-*.json"))) == 1
    repo.finish(command["command_id"])


def test_short_note_recovers_after_new_pending_sql_before_checkpoint(wired_job, monkeypatch):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    answer(repo, paused, note="short")
    command = repo.claim(os.getpid())
    update = repo.update_job
    crashed = []

    def crash(job_id, expected_revision=None, **changes):
        result = update(job_id, expected_revision, **changes)
        if changes.get("message", "").startswith("审核说明至少") and not crashed:
            crashed.append(True)
            raise SystemExit("UNIT loss after new prompt SQL save")
        return result

    monkeypatch.setattr(repo, "update_job", crash)
    with VideoProductionGraph(repo, project) as graph, pytest.raises(SystemExit):
        graph.execute(command)
    token = repo.get_job(job.job_id).pending_input["pending_token"]
    with VideoProductionGraph(repo, project) as graph:
        graph.execute(command)
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN" and not calls
    assert current.pending_input["pending_token"] == token != paused.pending_input["pending_token"]
    repo.finish(command["command_id"])
    answer(repo, current, key="UNIT-valid-after-crash")
    Worker(repo, project).once()
    assert calls == [job.job_id]


@pytest.mark.parametrize("change", ["revision", "script", "requirements"])
def test_changed_version_content_or_policy_cannot_be_approved(wired_job, monkeypatch, change):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    answer(repo, paused)
    if change == "revision":
        repo.update_job(job.job_id, revision=paused.revision + 1)
    elif change == "script":
        script = paused.script.model_copy(deep=True)
        script.segments[0].narration = "观点：此内容不属于原审核。"
        repo.update_job(job.job_id, script=script)
    else:
        original = HumanReviewNode.__init__

        def changed(self, *args, **kwargs):
            kwargs["confirmation_requirements"] = ("UNIT changed policy",)
            original(self, *args, **kwargs)

        monkeypatch.setattr(HumanReviewNode, "__init__", changed)
    Worker(repo, project).once()
    current = repo.get_job(job.job_id)
    assert current.status == "FAILED" and not calls
    assert not any(item.kind == "stage_review" for item in current.artifacts)


@pytest.mark.parametrize("change", ["bytes", "metadata"])
def test_changed_media_or_alignment_metadata_is_not_approved(wired_job, change):
    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    artifact = next(item for item in paused.artifacts if item.kind == "script")
    if change == "bytes":
        answer(repo, paused)
        repo.artifact_path(artifact.artifact_id)[0].write_text("UNIT tampered media bytes", encoding="utf-8")
    else:
        # Fingerprint also covers timing metadata on assets, not only files.
        from videoagents.contracts import Asset
        from videoagents.tools.media import sha256
        path = repo.artifact_path(artifact.artifact_id)[0]
        asset = Asset(asset_id="unit-metadata-asset", name="UNIT", role="audio", mime_type="audio/wav",
                      size_bytes=path.stat().st_size, sha256=sha256(path), artifact_id=artifact.artifact_id,
                      url=artifact.url, timeline_src="videoagents/UNIT/audio.wav")
        repo.update_job(job.job_id, assets=[asset])
        # Restart the run to bind this metadata fixture to its own new pause.
        paused = start(repo, project, repo.get_job(job.job_id), "UNIT-metadata-start")
        answer(repo, paused)
        repo.update_asset_metadata(asset.asset_id, {"alignment": {"origin": "UNIT changed"}})
    Worker(repo, project).once()
    assert repo.get_job(job.job_id).status == "FAILED" and not calls


def test_two_distinct_stage_nodes_have_independent_pending_and_routes(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：两个阶段测试。"))
    with VideoProductionGraph(repo, tmp_path / "project") as production:
        builder = StateGraph(VideoState)
        production.add_human_review(builder, "script_review", stage="script", title="文案确认",
                                    confirmation_requirements=("文案",), next_node="audio_review")
        production.add_human_review(builder, "audio_review", stage="voice", title="配音试听",
                                    confirmation_requirements=("试听声音",), next_node=END)
        builder.add_edge(START, "script_review")
        graph = builder.compile(checkpointer=production.checkpointer)
        state = VideoState(job_id=job.job_id, revision=job.revision, run_id="UNIT-two", thread_id="UNIT-two", action="produce")
        config = {"configurable": {"thread_id": state["thread_id"]}}
        graph.invoke(state, config)
        pending = repo.get_job(job.job_id).pending_input
        first = graph.get_state(config).interrupts[0]
        from langgraph.types import Command
        graph.invoke(Command(resume={first.id: {"decision": "confirm", "note": NOTE,
                    "pending_token": pending["pending_token"]}}), config)
        current = repo.get_job(job.job_id)
        assert current.pending_input["node_name"] == "audio_review"
        assert current.pending_input["pending_token"] != pending["pending_token"]
        second = graph.get_state(config).interrupts[0]
        graph.invoke(Command(resume={second.id: {"decision": "revise", "note": "UNIT试听需修改",
                    "pending_token": current.pending_input["pending_token"]}}), config)
        assert repo.get_job(job.job_id).status == "DRAFT"
        assert len([item for item in repo.get_job(job.job_id).artifacts if item.kind == "stage_review"]) == 2


def test_confirm_to_end_finishes_as_draft_without_publish_approval(tmp_path):
    from langgraph.types import Command

    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：单独阶段确认测试。"))
    with VideoProductionGraph(repo, tmp_path / "project") as production:
        builder = StateGraph(VideoState)
        production.add_human_review(builder, "terminal_review", stage="voice", title="阶段确认",
                                    confirmation_requirements=("本阶段",), next_node=END, min_note_length=0)
        builder.add_edge(START, "terminal_review")
        graph = builder.compile(checkpointer=production.checkpointer)
        state = VideoState(job_id=job.job_id, revision=job.revision, run_id="UNIT-end", thread_id="UNIT-end", action="voice")
        config = {"configurable": {"thread_id": state["thread_id"]}}
        graph.invoke(state, config)
        pending = repo.get_job(job.job_id).pending_input
        saved = graph.get_state(config).interrupts[0]
        graph.invoke(Command(resume={saved.id: {"decision": "confirm", "note": "",
                    "pending_token": pending["pending_token"]}}), config)
        current = repo.get_job(job.job_id)
        assert current.status == "DRAFT" and current.review is None and current.pending_input is None
        assert not graph.get_state(config).next


def test_existing_authenticated_resume_api_accepts_stage_review_and_rejects_stale_token(wired_job):
    from fastapi.testclient import TestClient

    from server.main import create_app

    repo, project, job, calls = wired_job
    paused = start(repo, project, job)
    app = create_app(repo.root, project)
    with TestClient(app) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        payload = {"base_revision": paused.revision, "pending_token": "UNIT-stale-token-0000",
                   "decision": "confirm", "note": NOTE, "idempotency_key": "UNIT-api-answer"}
        assert client.post(f"/api/jobs/{job.job_id}/resume", json=payload).status_code == 409
        payload["pending_token"] = paused.pending_input["pending_token"]
        assert client.post(f"/api/jobs/{job.job_id}/resume", json=payload).status_code == 202
        Worker(repo, project).once()
        current = client.get(f"/api/jobs/{job.job_id}").json()
        assert current["status"] == "NEEDS_INPUT" and current["stage"] == "voice"
        report = next(item for item in current["artifacts"] if item["kind"] == "stage_review")
        assert client.get(report["url"]).json()["decision"] == "confirm"
        assert calls == [job.job_id]


@pytest.mark.parametrize("config", [{"node_name": "../unsafe"}, {"stage": "complete"},
    {"title": ""}, {"confirmation_requirements": ()}, {"min_note_length": -1}])
def test_invalid_review_configuration_is_rejected(tmp_path, config):
    with pytest.raises(ValueError):
        HumanReviewNode(Repository(tmp_path / "runtime"), **config)
