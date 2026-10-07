import io
import json
import math
import os
import struct
import wave

import pytest
from langgraph.graph import END, START, StateGraph

from videoagents.contracts import Alignment, Brief, DraftRequest, Script, ScriptSegment, SettingsPatch
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import mark_feedback_applied, request_input, stage_feedback, state_context
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.screenwriter import ScreenwriterNode, active_script_feedback
from videoagents.nodes.voice import VoiceNode
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.runner import Worker

NOTE = "UNIT TEST：已核对本阶段文案表达、事实来源及素材。"


def tone(seconds=1):
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(i / 10))) for i in range(int(seconds * 16000))))
    return output.getvalue()


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
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False))
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


def test_stage_reviews_are_registered_and_script_review_is_on_default_flow(tmp_path):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False))
    job = repo.create_job(Brief(script_text="观点：默认流程测试。"))
    with VideoProductionGraph(repo, tmp_path / "project") as graph:
        topology = graph.graph.get_graph()
        for node in ("human_review", "human_review_script", "human_review_timeline", "human_review_render"):
            assert node in topology.nodes
        assert not any(edge.target == "human_review" and edge.source != "human_review" for edge in topology.edges)
        assert any(edge.source == "script_gate" and edge.target == "human_review_script" for edge in topology.edges)
        assert any(edge.source == "timeline_gate" and edge.target == "human_review_timeline" for edge in topology.edges)
        assert any(edge.source == "clear_editing" and edge.target == "human_review_render" for edge in topology.edges)
    result = start(repo, tmp_path / "project", job)
    assert result.status == "NEEDS_HUMAN" and result.stage == "script"
    assert result.pending_input["kind"] == "stage_review"
    assert result.pending_input["node_name"] == "human_review_script"


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
        graph.invoke(Command(resume={second.id: {"decision": "revise", "note": "UNIT：试听后确认此阶段需要返工修改",
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


def test_screenwriter_feedback_bypasses_existing_script_cache(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧稿。"))
    script = Script(title="旧稿", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：旧稿。")])
    repo.update_job(job.job_id, script=script)
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {"enabled": True, "provider": "codex_cli"}}))
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, context, command_id))
        return {"response": "已按人工意见重写", "script": {"title": "新稿", "origin": "model",
            "revision": job.revision, "segments": [{"segment_id": "s1", "narration": "观点：新稿。"}]}}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
        run_id="UNIT-rewrite", thread_id="UNIT-rewrite", extras={"human_feedback": {"script": {
        "decision": "revise", "note": "UNIT：请重写旧稿", "pending_token": "UNIT-token"}}}))
    rewritten, _ = ScreenwriterNode(repo, service).write_script(repo.get_job(job.job_id), state)
    assert rewritten.segments[0].narration == "观点：新稿。"
    assert calls and calls[0][0] == "screenwriter" and calls[0][2].endswith(":script-revise")
    assert calls[0][1]["extras"]["human_feedback"]["script"]["note"] == "UNIT：请重写旧稿"




def test_screenwriter_feedback_replay_after_sql_before_applied_receipt_does_not_call_model_twice(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧稿。"))
    old = Script(title="旧稿", origin="user", revision=job.revision,
                 segments=[ScriptSegment(segment_id="s1", narration="观点：旧稿。")])
    repo.update_job(job.job_id, script=old)
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False,
        role_models={"screenwriter": {"enabled": True, "provider": "codex_cli"}}))
    feedback = {"script": {"decision": "revise", "note": "UNIT：请重写旧稿",
                            "pending_token": "UNIT-token", "script": old.model_dump()}}
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(context["script"]["segments"][0]["narration"])
        return {"response": "已改", "script": {"title": "新稿", "origin": "model",
            "revision": revision, "segments": [{"segment_id": "s1", "narration": "观点：新稿。"}]}}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    original_mark = __import__("videoagents.nodes.screenwriter", fromlist=["mark_feedback_applied"]).mark_feedback_applied
    crashed = []

    def crash_once(*args, **kwargs):
        if not crashed:
            crashed.append(True)
            raise SystemExit("UNIT crash after script SQL before applied receipt")
        return original_mark(*args, **kwargs)

    monkeypatch.setattr("videoagents.nodes.screenwriter.mark_feedback_applied", crash_once)
    state = state_context(repo, VideoState(job_id=job.job_id, revision=repo.get_job(job.job_id).revision,
        action="produce", run_id="UNIT-replay", thread_id="UNIT-replay", extras={"human_feedback": feedback}))
    with pytest.raises(SystemExit):
        ScreenwriterNode(repo, service)(state)
    assert calls == ["观点：旧稿。"]
    replay = state_context(repo, VideoState(job_id=job.job_id, revision=repo.get_job(job.job_id).revision,
        action="produce", run_id="UNIT-replay", thread_id="UNIT-replay", extras={"human_feedback": feedback}))
    result = ScreenwriterNode(repo, service)(replay)
    assert calls == ["观点：旧稿。"]
    assert result["route"] == "script_gate"
    current = repo.get_job(job.job_id)
    assert current.script.segments[0].narration == "观点：新稿。"
    assert any(item.kind == "human_feedback_applied" for item in current.artifacts)


def test_applied_feedback_receipt_must_match_pending_token(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧稿。"))
    old_state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
        run_id="UNIT-old", thread_id="UNIT-old", extras={"human_feedback": {"script": {
        "decision": "revise", "note": "UNIT：第一次返工", "pending_token": "UNIT-old-token"}}}))
    mark_feedback_applied(repo, service, repo.get_job(job.job_id), old_state, "script", "screenwriter")
    new_state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
        run_id="UNIT-new", thread_id="UNIT-new", extras={"human_feedback": {"script": {
        "decision": "revise", "note": "UNIT：第二次返工", "pending_token": "UNIT-new-token"}}}))
    feedback = new_state["extras"]["human_feedback"]["script"]
    assert feedback.get("applied") is not True
    assert stage_feedback(new_state, "script")["pending_token"] == "UNIT-new-token"


def test_screenwriter_feedback_rejects_noop_rewrite(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧稿。"))
    old = Script(title="旧稿", origin="user", revision=job.revision,
                 segments=[ScriptSegment(segment_id="s1", narration="观点：旧稿。")])
    repo.update_job(job.job_id, script=old)
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False,
        role_models={"screenwriter": {"enabled": True, "provider": "codex_cli"}}))

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        return {"response": "没有实际修改", "script": dict(old.model_dump(), origin="model", revision=revision)}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    feedback = {"script": {"decision": "revise", "note": "UNIT：请重写旧稿",
                            "pending_token": "UNIT-token", "script": old.model_dump()}}
    state = state_context(repo, VideoState(job_id=job.job_id, revision=repo.get_job(job.job_id).revision,
        action="produce", run_id="UNIT-noop", thread_id="UNIT-noop", extras={"human_feedback": feedback}))
    result = ScreenwriterNode(repo, service)(state)
    assert result["route"] == "await_input"
    assert "人工返工未产生文案修改" in result["gate_issues"][0]
    assert not any(item.kind == "human_feedback_applied" for item in repo.get_job(job.job_id).artifacts)


def test_screenwriter_ignores_visual_only_render_feedback():
    state = VideoState(job_id="UNIT-job", revision=1, action="final", extras={"human_feedback": {
        "render": {
            "decision": "revise",
            "note": "UNIT：请仅修复 DeepPlanning 的画面断行并保持旁白不变。",
            "pending_token": "UNIT-render-token",
            "target": "director",
            "applied": False,
        },
    }})

    stage, feedback = active_script_feedback(state)

    assert stage == "script"
    assert feedback is None


def test_screenwriter_consumes_render_feedback_that_requests_copy_rewrite():
    state = VideoState(job_id="UNIT-job", revision=1, action="final", extras={"human_feedback": {
        "render": {
            "decision": "revise",
            "note": "UNIT：防御性文案太多，请改旁白文案并把结论前置。",
            "pending_token": "UNIT-render-token",
            "target": "director",
            "applied": False,
        },
    }})

    stage, feedback = active_script_feedback(state)

    assert stage == "render"
    assert feedback and feedback["pending_token"] == "UNIT-render-token"


def test_director_feedback_allows_visual_mismatch_language_without_voice_block(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    node = DirectorNode(repo, service)
    assert not node._needs_voice_or_script("画面与旁白不对应，请重新匹配素材和镜头")
    assert node._needs_voice_or_script("语速太快，请调整语速后再做视频")
    assert node._needs_script_revision("防御性文案太多，请改旁白文案并把结论前置")
    assert not node._needs_voice_revision("防御性文案太多，请改旁白文案并把结论前置")

def test_director_feedback_does_not_reuse_cached_timeline_without_model(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧分镜。", width=240, height=426, fps=15, usage="personal"))
    script = Script(title="旧分镜", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：旧分镜。")])
    repo.update_job(job.job_id, script=script)
    alignment_data = {"origin": "manual", "verified": True,
                      "segments": [{"segment_id": "s1", "text": "观点：旧分镜。", "start_ms": 0, "end_ms": 1000}]}
    audio = service.upload(job.job_id, tone(), "unit.wav", "audio", license_note="UNIT", alignment=alignment_data)
    job = repo.get_job(job.job_id)
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])
    initial_state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="storyboard",
        run_id="UNIT-initial", thread_id="UNIT-initial", audio_asset_id=audio.asset_id,
        alignment=alignment.model_dump(), duration_seconds=1.0, extras={}))
    timeline = DirectorNode(repo, service).plan(repo.get_job(job.job_id), audio, alignment, 1.0, state=initial_state)
    repo.update_job(job.job_id, timeline=timeline)
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="storyboard",
        run_id="UNIT-revise", thread_id="UNIT-revise", audio_asset_id=audio.asset_id,
        alignment=alignment.model_dump(), duration_seconds=1.0, extras={"human_feedback": {"director": {
        "decision": "revise", "note": "UNIT：请重做画面", "pending_token": "UNIT-token"}}}))
    with pytest.raises(CapabilityMissing):
        DirectorNode(repo, service).plan(repo.get_job(job.job_id), audio, alignment, 1.0, state=state)



@pytest.mark.parametrize("crash_at", ["receipt", "storyboard", "timeline"])
def test_director_feedback_replay_after_sql_before_applied_receipt_does_not_call_model_twice(tmp_path, monkeypatch, crash_at):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧分镜。", width=240, height=426, fps=15, usage="personal"))
    script = Script(title="旧分镜", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：旧分镜。")])
    repo.update_job(job.job_id, script=script)
    alignment_data = {"origin": "manual", "verified": True,
                      "segments": [{"segment_id": "s1", "text": "观点：旧分镜。", "start_ms": 0, "end_ms": 1000}]}
    audio = service.upload(job.job_id, tone(), "unit.wav", "audio", license_note="UNIT", alignment=alignment_data)
    job = repo.get_job(job.job_id)
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])
    initial = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="storyboard",
        run_id="UNIT-director-initial", thread_id="UNIT-director-initial", audio_asset_id=audio.asset_id,
        alignment=alignment.model_dump(), duration_seconds=1.0, extras={}))
    old_timeline = DirectorNode(repo, service).plan(repo.get_job(job.job_id), audio, alignment, 1.0, state=initial)
    repo.update_job(job.job_id, timeline=old_timeline)
    job = repo.get_job(job.job_id)
    SettingsService(repo).patch(SettingsPatch(role_models={"director": {"enabled": True, "provider": "codex_cli"}}))
    monkeypatch.setattr(DirectorNode, "ensure_component_study", lambda *a, **k: type("Study", (), {"model_dump": lambda self: {"unit": True}})())
    calls = []

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(context["timeline"]["shots"][0]["body"])
        value = {"shots": context["timeline"]["shots"]}
        value["shots"] = [dict(item, body="观点：新分镜画面。") for item in value["shots"]]
        return value

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: True)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    original_mark = __import__("videoagents.nodes.director", fromlist=["mark_feedback_applied"]).mark_feedback_applied
    original_write = service.write_json
    crashed = []

    def crash_once(*args, **kwargs):
        if crash_at == "receipt" and not crashed:
            crashed.append(True)
            raise SystemExit("UNIT crash after timeline SQL before applied receipt")
        return original_mark(*args, **kwargs)

    def crash_before_artifact(current, name, value, kind):
        if crash_at == kind and not crashed:
            crashed.append(True)
            raise SystemExit("UNIT crash after timeline SQL before artifact " + kind)
        return original_write(current, name, value, kind)

    monkeypatch.setattr("videoagents.nodes.director.mark_feedback_applied", crash_once)
    monkeypatch.setattr(service, "write_json", crash_before_artifact)
    feedback = {"director": {"decision": "revise", "note": "UNIT：请重做画面",
                              "pending_token": "UNIT-token", "timeline": old_timeline.model_dump()}}
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="storyboard",
        run_id="UNIT-director-replay", thread_id="UNIT-director-replay", audio_asset_id=audio.asset_id,
        alignment=alignment.model_dump(), duration_seconds=1.0, extras={"human_feedback": feedback}))
    with pytest.raises(SystemExit):
        DirectorNode(repo, service)(state)
    assert calls == [old_timeline.shots[0].body]
    replay = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="storyboard",
        run_id="UNIT-director-replay", thread_id="UNIT-director-replay", audio_asset_id=audio.asset_id,
        alignment=alignment.model_dump(), duration_seconds=1.0, extras={"human_feedback": feedback}))
    result = DirectorNode(repo, service)(replay)
    assert calls == [old_timeline.shots[0].body]
    assert result["route"] == "timeline_gate"
    current = repo.get_job(job.job_id)
    assert current.timeline.shots[0].body == "观点：新分镜画面。"
    assert any(item.kind == "human_feedback_applied" for item in current.artifacts)
    for kind in ("storyboard", "timeline"):
        artifact = next(item for item in current.artifacts if item.kind == kind)
        saved = json.loads(repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8"))
        assert saved == current.timeline.model_dump()


def test_director_feedback_rejects_noop_timeline(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧分镜。", width=240, height=426, fps=15, usage="personal"))
    script = Script(title="旧分镜", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：旧分镜。")])
    repo.update_job(job.job_id, script=script)
    alignment_data = {"origin": "manual", "verified": True,
                      "segments": [{"segment_id": "s1", "text": "观点：旧分镜。", "start_ms": 0, "end_ms": 1000}]}
    audio = service.upload(job.job_id, tone(), "unit.wav", "audio", license_note="UNIT", alignment=alignment_data)
    job = repo.get_job(job.job_id)
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])
    initial = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="storyboard",
        run_id="UNIT-director-noop-initial", thread_id="UNIT-director-noop-initial", audio_asset_id=audio.asset_id,
        alignment=alignment.model_dump(), duration_seconds=1.0, extras={}))
    old_timeline = DirectorNode(repo, service).plan(repo.get_job(job.job_id), audio, alignment, 1.0, state=initial)
    repo.update_job(job.job_id, timeline=old_timeline)
    SettingsService(repo).patch(SettingsPatch(role_models={"director": {"enabled": True, "provider": "codex_cli"}}))
    monkeypatch.setattr(DirectorNode, "ensure_component_study", lambda *a, **k: type("Study", (), {"model_dump": lambda self: {"unit": True}})())

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: True)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    feedback = {"director": {"decision": "revise", "note": "UNIT：请重做画面",
                              "pending_token": "UNIT-token", "timeline": old_timeline.model_dump()}}
    state = state_context(repo, VideoState(job_id=job.job_id, revision=repo.get_job(job.job_id).revision,
        action="storyboard", run_id="UNIT-director-noop", thread_id="UNIT-director-noop",
        audio_asset_id=audio.asset_id, extras={"human_feedback": feedback}))
    result = DirectorNode(repo, service)(state)
    assert result["route"] == "await_input"
    assert "人工返工未产生分镜修改" in result["gate_issues"][0]
    assert not any(item.kind == "human_feedback_applied" for item in repo.get_job(job.job_id).artifacts)


def test_revise_route_returns_feedback_to_configured_model_node(tmp_path):
    from langgraph.types import Command

    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：返工路由测试。"))
    visited = []

    def director(state):
        visited.append(state.get("extras", {}).get("human_feedback", {}).get("render"))
        return {**state, "route": "end"}

    with VideoProductionGraph(repo, tmp_path / "project") as production:
        builder = StateGraph(VideoState)
        production.add_human_review(builder, "render_review", stage="render", title="成片确认",
                                    confirmation_requirements=("完整播放",), next_node=END,
                                    revise_node="director", min_note_length=0)
        builder.add_node("director", director)
        builder.add_edge(START, "render_review")
        builder.add_edge("director", END)
        graph = builder.compile(checkpointer=production.checkpointer)
        state = VideoState(job_id=job.job_id, revision=job.revision, run_id="UNIT-revise",
                           thread_id="UNIT-revise", action="produce")
        config = {"configurable": {"thread_id": state["thread_id"]}}
        graph.invoke(state, config)
        pending = repo.get_job(job.job_id).pending_input
        saved = graph.get_state(config).interrupts[0]
        graph.invoke(Command(resume={saved.id: {"decision": "revise", "note": "UNIT：画面节奏需要返工",
                    "pending_token": pending["pending_token"]}}), config)

    current = repo.get_job(job.job_id)
    assert current.status == "RUNNING" and current.pending_input is None
    assert visited and visited[0]["note"] == "UNIT：画面节奏需要返工"
    assert visited[0]["node_name"] == "render_review"
    report = next(item for item in current.artifacts if item.kind == "stage_review")
    receipt = json.loads(repo.artifact_path(report.artifact_id)[0].read_text(encoding="utf-8"))
    assert receipt["decision"] == "revise"
    assert receipt["feedback"]["note"] == "UNIT：画面节奏需要返工"
    assert receipt["feedback"]["target"] == "director"


def test_unapplied_review_feedback_survives_new_revision_until_consumed(tmp_path):
    from langgraph.types import Command

    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：需要返工的旧稿。"))
    script = Script(title="旧稿", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：需要返工的旧稿。")])
    repo.update_job(job.job_id, job.revision, script=script)

    with VideoProductionGraph(repo, service.project_root) as production:
        builder = StateGraph(VideoState)
        production.add_human_review(builder, "render_review", stage="render", title="成片确认",
                                    confirmation_requirements=("完整播放",), next_node=END,
                                    revise_node="director", min_note_length=0)
        builder.add_node("director", lambda state: {**state, "route": "end"})
        builder.add_edge(START, "render_review")
        builder.add_edge("director", END)
        graph = builder.compile(checkpointer=production.checkpointer)
        state = VideoState(job_id=job.job_id, revision=job.revision, run_id="UNIT-old-revision",
                           thread_id="UNIT-old-revision", action="produce")
        config = {"configurable": {"thread_id": state["thread_id"]}}
        graph.invoke(state, config)
        pending = repo.get_job(job.job_id).pending_input
        saved = graph.get_state(config).interrupts[0]
        graph.invoke(Command(resume={saved.id: {"decision": "revise",
            "note": "UNIT：删掉防御性文案并把结论前置。",
            "pending_token": pending["pending_token"]}}), config)

    previous = repo.get_job(job.job_id)
    revised = service.draft(job.job_id, DraftRequest(base_revision=previous.revision, script=previous.script))
    recovered = state_context(repo, VideoState(job_id=job.job_id, revision=revised.revision,
        run_id="UNIT-new-revision", thread_id="UNIT-new-revision", action="produce"))
    feedback = stage_feedback(recovered, "render")
    assert feedback["note"] == "UNIT：删掉防御性文案并把结论前置。"
    assert feedback["source_revision"] == previous.revision
    assert feedback["script"]["title"] == "旧稿"

    mark_feedback_applied(repo, service, revised, recovered, "render", "screenwriter")
    clean = state_context(repo, VideoState(job_id=job.job_id, revision=revised.revision,
        run_id="UNIT-after-applied", thread_id="UNIT-after-applied", action="produce"))
    assert stage_feedback(clean, "render") is None


@pytest.mark.parametrize("config", [{"node_name": "../unsafe"}, {"stage": "complete"},
    {"title": ""}, {"confirmation_requirements": ()}, {"min_note_length": -1}])
def test_invalid_review_configuration_is_rejected(tmp_path, config):
    with pytest.raises(ValueError):
        HumanReviewNode(Repository(tmp_path / "runtime"), **config)
