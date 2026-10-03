import json
import math
import sqlite3
from pathlib import Path

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from videoagents.contracts import (
    Artifact,
    Asset,
    Brief,
    Finding,
    Review,
    Script,
    ScriptDiscussion,
    ScriptDiscussionRound,
    ScriptSegment,
    SettingsPatch,
    Shot,
    Timeline,
)
from videoagents.nodes.common import current_discussion, current_job, request_input, state_context
from videoagents.nodes.gates import ScriptGateNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState, job_context, merge_extras, validate_json
from videoagents.storage import Conflict, Repository
from videoagents.tools.media import sha256
from worker.process_manager import RenderCancelled


def _script(revision: int, narration: str = "观点：上下文传来的文案。") -> Script:
    return Script(title="上下文文案", origin="user", revision=revision,
                  segments=[ScriptSegment(segment_id="s1", narration=narration, screen_text=narration[:100])])


def _timeline(job_id: str, revision: int) -> Timeline:
    return Timeline(job_id=job_id, revision=revision, width=1080, height=1920, fps=30,
                    duration_in_frames=30,
                    shots=[Shot(shot_id="shot-1", start_frame=0, end_frame=30,
                                component_id="title", title="旧分镜", body="旧画面")])


def _artifact(repo: Repository, job_id: str, revision: int, kind: str) -> Artifact:
    path = repo.root / f"unit-{kind}.json"
    path.write_text(json.dumps({"kind": kind}, ensure_ascii=False), encoding="utf-8")
    artifact = Artifact(artifact_id=f"unit-{kind}", kind=kind, name=path.name,
                        mime_type="application/json", size_bytes=path.stat().st_size,
                        sha256=sha256(path), url=f"/api/artifacts/unit-{kind}", revision=revision)
    repo.put_artifact(job_id, artifact, path)
    return artifact


def _json_artifact(repo: Repository, job_id: str, revision: int, kind: str, value: dict) -> Artifact:
    path = repo.root / f"unit-{kind}-{len(value)}.json"
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    artifact = Artifact(artifact_id=f"unit-{kind}-{len(value)}", kind=kind, name=path.name,
                        mime_type="application/json", size_bytes=path.stat().st_size,
                        sha256=sha256(path), url=f"/api/artifacts/unit-{kind}-{len(value)}", revision=revision)
    repo.put_artifact(job_id, artifact, path)
    return artifact


def _registered_asset(repo: Repository, job, *, suffix: str = "asset", owner_job_id: str | None = None,
                      role: str = "evidence", mime_type: str = "image/png",
                      timeline_job_id: str | None = None, metadata: dict | None = None) -> Asset:
    extension = ".mp3" if mime_type.startswith("audio/") else ".png"
    path = repo.root / f"unit-context-{suffix}{extension}"
    path.write_bytes(f"UNIT TEST {suffix}".encode("utf-8"))
    artifact = Artifact(artifact_id=f"unit-context-artifact-{suffix}", kind="asset", name=path.name,
                        mime_type=mime_type, size_bytes=path.stat().st_size, sha256=sha256(path),
                        url=f"/api/artifacts/unit-context-artifact-{suffix}", revision=job.revision)
    repo.put_artifact(owner_job_id or job.job_id, artifact, path)
    asset = Asset(asset_id=f"unit-context-asset-{suffix}", name=path.name, role=role, mime_type=mime_type,
                  size_bytes=artifact.size_bytes, sha256=artifact.sha256, artifact_id=artifact.artifact_id,
                  url=artifact.url, timeline_src=f"videoagents/{timeline_job_id or job.job_id}/assets/{path.name}")
    if metadata is not None:
        repo.update_asset_metadata(asset.asset_id, metadata)
    return asset


def test_job_context_projects_all_persisted_business_fields(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="上下文测试", script_text="观点：所有节点读取同一个上下文。"))

    context = job_context(job)

    assert context["job_id"] == job.job_id
    assert context["revision"] == job.revision
    assert context["status"] == "DRAFT"
    assert context["stage"] == "idle"
    assert context["brief"] == job.brief.model_dump()
    assert context["script"] is None
    assert context["timeline"] is None
    assert context["assets"] == []
    assert context["artifacts"] == []
    assert context["review"] is None
    assert context["pending_input"] is None


def test_screenwriter_returns_latest_job_context_after_saving_script_and_artifacts(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    SettingsService(repo).patch(SettingsPatch(voice_provider="byte_ws", voice_api_key="UNIT-secret",
                                              voice_id="UNIT-voice", voice_resource_id="UNIT-resource"))
    job = repo.create_job(Brief(script_text="观点：上下文里应该带着文案。"))
    state = VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                       run_id="UNIT-context", thread_id="UNIT-context-thread")

    result = ScreenwriterNode(repo, service)(state)
    saved = repo.get_job(job.job_id)

    assert result["route"] == "script_gate"
    assert result["status"] == saved.status == "RUNNING"
    assert result["stage"] == saved.stage == "script"
    assert result["brief"] == saved.brief.model_dump()
    assert result["script"] == saved.script.model_dump()
    assert result["script_discussion"] is None
    assert result["artifacts"] == [item.model_dump() for item in saved.artifacts]
    assert result["settings"]["voice_configured"] is True
    assert result["settings"]["voice_api_key_configured"] is True
    assert "voice_api_key" not in result["settings"]
    script_artifact = next(item for item in saved.artifacts if item.kind == "script")
    assert json.loads(repo.artifact_path(script_artifact.artifact_id)[0].read_text(encoding="utf-8")) == result["script"]


def test_request_input_returns_pending_input_in_shared_context(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：暂停也要写回上下文。"))
    state = VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                       run_id="UNIT-context", thread_id="UNIT-context-thread")

    result = request_input(repo, state, "script", ["UNIT TEST: need human input"], ["script"])
    saved = repo.get_job(job.job_id)

    assert result["route"] == "await_input"
    assert result["status"] == saved.status == "NEEDS_INPUT"
    assert result["stage"] == saved.stage == "script"
    assert result["pending_input"] == saved.pending_input == result["pending_snapshot"]
    assert result["gate_issues"] == ["UNIT TEST: need human input"]


def test_partial_custom_langgraph_node_updates_context_for_next_real_node_and_checkpoint(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="旧主题", script_text="观点：旧文案。"))
    checkpoint_path = tmp_path / "checkpoints.sqlite"
    checkpoint = sqlite3.connect(checkpoint_path, check_same_thread=False)
    checkpoint.execute("PRAGMA journal_mode=WAL")
    saver = SqliteSaver(checkpoint)

    def build_graph(checkpointer):
        builder = StateGraph(VideoState)

        def custom_writer(state: VideoState):
            return {
                "brief": {**state["brief"], "topic": "上下文新主题", "script_text": "观点：上下文新文案。"},
                "script": _script(state["revision"], "观点：自定义节点只返回局部文案。").model_dump(),
                "extras": {"review_hint": None, "writer": "custom"},
            }

        builder.add_node("custom_writer", custom_writer)
        builder.add_node("script_gate", ScriptGateNode(repo))
        builder.add_edge(START, "custom_writer")
        builder.add_edge("custom_writer", "script_gate")
        builder.add_conditional_edges("script_gate", lambda state: state["route"], {"voice": END, "await_input": END})
        return builder.compile(checkpointer=checkpointer)

    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision,
                          action="produce", run_id="UNIT-custom", thread_id="UNIT-custom",
                          gate_issues=[], extras={"keep": "yes"}))
    config = {"configurable": {"thread_id": "UNIT-custom"}}

    result = build_graph(saver).invoke(state, config)
    checkpoint.close()
    reopened_connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    reopened_connection.execute("PRAGMA journal_mode=WAL")
    reopened = build_graph(SqliteSaver(reopened_connection)).get_state(config).values
    saved = repo.get_job(job.job_id)

    assert result["route"] == "voice"
    assert saved.brief.topic == "上下文新主题"
    assert saved.script.segments[0].narration == "观点：自定义节点只返回局部文案。"
    assert result["extras"] == {"keep": "yes", "review_hint": None, "writer": "custom"}
    assert reopened["script"] == saved.script.model_dump()
    assert reopened["extras"] == result["extras"]
    reopened_connection.close()


def test_legacy_minimal_state_is_completed_from_sql_context(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：旧 checkpoint 只有 job_id 和版本。"))
    job = repo.update_job(job.job_id, job.revision, script=_script(job.revision))

    result = ScriptGateNode(repo)(VideoState(job_id=job.job_id, revision=job.revision,
                                            action="produce", run_id="UNIT-legacy", thread_id="UNIT-legacy"))

    assert result["route"] == "voice"
    assert result["script"] == job.script.model_dump()
    assert result["brief"] == job.brief.model_dump()
    assert result["assets"] == []
    assert result["settings"]["voice_configured"] is False
    assert result["asset_metadata"] == {}
    assert result["metrics"] == {}


def test_sql_ahead_context_wins_over_stale_business_patch(tmp_path):
    repo = Repository(tmp_path / "runtime")
    created = repo.create_job(Brief(script_text="观点：初始。"))
    watermark = created.latest_event_id
    committed = repo.update_job(created.job_id, created.revision,
                                script=_script(created.revision, "观点：SQL 已经有更新后的文案。"))

    result = ScriptGateNode(repo)(VideoState(job_id=created.job_id, revision=created.revision,
                                            latest_event_id=watermark, action="produce",
                                            run_id="UNIT-sql-ahead", thread_id="UNIT-sql-ahead",
                                            script=_script(created.revision, "观点：旧 checkpoint 的文案。").model_dump()))

    assert result["route"] == "voice"
    assert result["script"] == committed.script.model_dump()
    assert repo.get_job(created.job_id).script == committed.script


def test_state_business_patch_rejects_invalid_revision_or_cancelled_job(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：版本保护。"))

    with pytest.raises(Conflict):
        current_job(repo, VideoState(job_id=job.job_id, revision=job.revision + 1,
                                    action="produce", run_id="UNIT-bad", thread_id="UNIT-bad"))

    repo.cancel(job.job_id)
    with pytest.raises(RenderCancelled):
        current_job(repo, VideoState(job_id=job.job_id, revision=job.revision,
                                    action="produce", run_id="UNIT-cancel", thread_id="UNIT-cancel"))


def test_explicit_none_clears_script_and_invalidates_downstream_outputs(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：清空文案。"))
    final = _artifact(repo, job.job_id, job.revision, "final")
    package = _artifact(repo, job.job_id, job.revision, "package")
    source = _artifact(repo, job.job_id, job.revision, "source")
    review = Review(status="PASS", findings=[Finding(finding_id="unit", severity="info", category="unit",
                    message="旧审核", owner="unit", blocking=False)], dependency_fingerprint="unit")
    job = repo.update_job(job.job_id, job.revision, script=_script(job.revision),
                          timeline=_timeline(job.job_id, job.revision), review=review,
                          artifacts=[source, final, package])

    current_job(repo, VideoState(job_id=job.job_id, revision=job.revision, latest_event_id=job.latest_event_id,
                                action="produce", run_id="UNIT-clear", thread_id="UNIT-clear", script=None))
    saved = repo.get_job(job.job_id)

    assert saved.script is None
    assert saved.timeline is None
    assert saved.review is None
    assert {item.kind for item in saved.artifacts} == {"source"}
    assert saved.status == "RUNNING"


def test_generic_business_patch_is_rejected_during_active_discussion(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：讨论冻结。"))
    discussion = ScriptDiscussion(run_id="UNIT-discussion", revision=job.revision, enabled=True,
                                  max_rounds=2, status="DISCUSSING",
                                  rounds=[ScriptDiscussionRound(round=1, script=_script(job.revision))])
    job = repo.update_job(job.job_id, job.revision, script=_script(job.revision),
                          script_discussion=discussion)

    with pytest.raises(Conflict, match="讨论中的文案"):
        current_job(repo, VideoState(job_id=job.job_id, revision=job.revision,
                                    latest_event_id=job.latest_event_id, action="produce",
                                    run_id="UNIT-discussion", thread_id="UNIT-discussion",
                                    script=_script(job.revision, "观点：绕过讨论的新文案。").model_dump()))


def test_extras_are_shallow_merged_and_json_only():
    assert merge_extras({"keep": "yes", "null_value": "old"}, {"null_value": None, "new": 1}) == {
        "keep": "yes", "null_value": None, "new": 1,
    }

    invalid_values = [b"bytes", Path("unit"), float("nan"), {1: "bad-key"}]
    cycle = []
    cycle.append(cycle)
    invalid_values.append(cycle)
    for value in invalid_values:
        with pytest.raises(ValueError):
            validate_json(value)
    with pytest.raises(ValueError):
        validate_json({"bad": math.inf})


def test_context_contains_public_receipts_without_runtime_secrets(tmp_path):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="UNIT-search-secret",
                                              voice_provider="byte_ws", voice_api_key="UNIT-voice-secret",
                                              voice_id="UNIT-voice", voice_resource_id="UNIT-resource",
                                              aligner_api_key="UNIT-aligner-secret"))
    job = repo.create_job(Brief(script_text="观点：公开上下文。"))
    repo.reserve_metric(job.job_id, job.revision, "llm_calls", 1, 10)
    with repo.connection() as db:
        db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?)",
                   ("unit-op", job.job_id, "unit-input", "codex_cli", "DONE",
                    json.dumps({"revision": job.revision, "command_id": "cmd",
                                "model": "unit-model", "secret": "UNIT-operation-secret"}, ensure_ascii=False)))

    context = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision,
                            action="produce", run_id="UNIT-public", thread_id="UNIT-public", extras={}))
    encoded = json.dumps(context, ensure_ascii=False)

    assert context["settings"]["search_configured"] is True
    assert context["settings"]["voice_api_key_configured"] is True
    assert context["metrics"] == {"llm_calls": 1}
    assert context["operations"] == [{"operation_id": "unit-op", "provider": "codex_cli", "status": "DONE",
                                      "revision": job.revision, "command_id": "cmd", "model": "unit-model"}]
    assert "UNIT-search-secret" not in encoded
    assert "UNIT-voice-secret" not in encoded
    assert "UNIT-aligner-secret" not in encoded
    assert "UNIT-operation-secret" not in encoded


@pytest.mark.parametrize("enabled,max_rounds,status", [(True, 5, "DISCUSSING"), (False, 3, "DISABLED")])
def test_new_run_freezes_fresh_discussion_policy_instead_of_reusing_previous_run(tmp_path, enabled, max_rounds, status):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=enabled,
                                              script_discussion_max_rounds=max_rounds))
    job = repo.create_job(Brief(script_text="观点：新 run 不能复用旧讨论。"))
    previous = ScriptDiscussion(run_id="OLD-run", revision=job.revision, enabled=True,
                                max_rounds=1, status="APPROVED",
                                rounds=[ScriptDiscussionRound(round=1, script=_script(job.revision))])
    job = repo.update_job(job.job_id, job.revision, script_discussion=previous)
    state = VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                       run_id="NEW-run", thread_id="NEW-thread")

    discussion = current_discussion(repo, state, job)
    saved = repo.get_job(job.job_id)

    assert discussion.run_id == "NEW-run"
    assert discussion.enabled is enabled
    assert discussion.max_rounds == max_rounds
    assert discussion.status == status
    assert discussion.rounds == []
    assert saved.script_discussion.run_id == "NEW-run"
    assert state["discussion_policy"] == {"run_id": "NEW-run", "revision": job.revision,
                                          "enabled": enabled, "max_rounds": max_rounds}


def test_request_input_commits_custom_state_patch_before_pending_event(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：请求输入前先保存上下文。"))
    script = _script(job.revision, "观点：暂停前来自自定义节点的新文案。")

    result = request_input(repo, VideoState(job_id=job.job_id, revision=job.revision,
                           latest_event_id=job.latest_event_id, action="produce",
                           run_id="UNIT-input-state", thread_id="UNIT-input-state",
                           script=script.model_dump()),
                           "script", ["UNIT TEST: pause after custom patch"], ["script"])
    saved = repo.get_job(job.job_id)

    assert saved.status == "NEEDS_INPUT"
    assert saved.script == script
    assert result["script"] == script.model_dump()
    assert result["pending_input"] == saved.pending_input
    assert saved.latest_event_id > job.latest_event_id + 1


def test_runtime_control_fields_and_future_watermark_cannot_override_sql(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：控制字段不由上下文覆盖。"))

    context = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision,
                            action="produce", run_id="UNIT-control", thread_id="UNIT-control",
                            status="READY_FOR_PUBLISH",
                            review={"status": "PASS", "dependency_fingerprint": "fake"}))

    assert context["status"] == "DRAFT"
    assert context["review"] is None
    with pytest.raises(Conflict, match="持久化版本无效"):
        current_job(repo, VideoState(job_id=job.job_id, revision=job.revision,
                                    latest_event_id=job.latest_event_id + 100,
                                    action="produce", run_id="UNIT-future", thread_id="UNIT-future"))


def test_state_context_loads_stage_receipts_audio_metadata_and_business_json(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：上下文带阶段记录。"))
    audio_path = repo.root / "unit-audio.mp3"
    audio_path.write_bytes(b"UNIT TEST fake audio bytes")
    audio_artifact = Artifact(artifact_id="unit-audio-artifact", kind="voice", name="unit-audio.mp3",
                              mime_type="audio/mpeg", size_bytes=audio_path.stat().st_size,
                              sha256=sha256(audio_path), url="/api/artifacts/unit-audio-artifact",
                              revision=job.revision)
    repo.put_artifact(job.job_id, audio_artifact, audio_path)
    audio = Asset(asset_id="unit-audio", name="unit-audio.mp3", role="audio", mime_type="audio/mpeg",
                  size_bytes=audio_artifact.size_bytes, sha256=audio_artifact.sha256,
                  artifact_id=audio_artifact.artifact_id, url=audio_artifact.url,
                  timeline_src=f"videoagents/{job.job_id}/assets/unit-audio.mp3")
    alignment = {"origin": "manual", "verified": True, "audio_sha256": audio.sha256,
                 "segments": [{"segment_id": "s1", "text": "观点", "start_ms": 0, "end_ms": 500}],
                 "note": "UNIT"}
    research = _json_artifact(repo, job.job_id, job.revision, "research", {"sources": [{"url": "https://example.test"}]})
    audio_report = _json_artifact(repo, job.job_id, job.revision, "audio_report", {"verified": True})
    voice_guidance = _json_artifact(repo, job.job_id, job.revision, "voice_guidance", {"delivery_notes": ["慢一点"]})
    editing_guidance = _json_artifact(repo, job.job_id, job.revision, "editing_guidance", {"layout_notes": ["标题加粗"]})
    stage_review = _json_artifact(repo, job.job_id, job.revision, "stage_review",
                                  {"decision": "confirm", "pending_token": "UNIT-token", "note": "已人工确认"})
    job = repo.update_job(job.job_id, job.revision, assets=[audio],
                          artifacts=[audio_artifact, research, audio_report, voice_guidance,
                                     editing_guidance, stage_review])
    repo.update_asset_metadata(audio.asset_id, {"origin": "upload", "duration_seconds": 0.5,
                                                "alignment": alignment})
    repo.select_audio(job.job_id, audio.asset_id)

    context = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision,
                            action="produce", run_id="UNIT-receipts", thread_id="UNIT-receipts",
                            extras={}))

    assert context["audio_asset_id"] == audio.asset_id
    assert context["audio"] == audio.model_dump()
    assert context["alignment"] == alignment
    assert context["duration_seconds"] == 0.5
    assert context["asset_metadata"][audio.asset_id]["origin"] == "upload"
    assert context["research"] == {"sources": [{"url": "https://example.test"}]}
    assert context["audio_report"] == {"verified": True}
    assert context["voice_guidance"] == {"delivery_notes": ["慢一点"]}
    assert context["editing_guidance"] == {"layout_notes": ["标题加粗"]}
    assert context["human_reviews"] == [{**{"decision": "confirm", "pending_token": "UNIT-token",
                                            "note": "已人工确认"}, "artifact_id": stage_review.artifact_id}]


def test_context_assets_accept_valid_current_job_asset(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：合法上下文素材。"))
    asset = _registered_asset(repo, job, suffix="valid")

    current_job(repo, VideoState(job_id=job.job_id, revision=job.revision,
                                latest_event_id=job.latest_event_id, action="produce",
                                run_id="UNIT-valid-asset", thread_id="UNIT-valid-asset",
                                assets=[asset.model_dump()]))
    saved = repo.get_job(job.job_id)

    assert saved.assets == [asset]
    assert saved.status == "RUNNING"


@pytest.mark.parametrize("case", [
    "foreign-job-artifact",
    "missing-artifact",
    "declared-sha",
    "declared-size",
    "declared-mime",
    "tampered-bytes",
    "cross-task-timeline-src",
    "audio-missing-metadata",
])
def test_context_assets_reject_invalid_file_bindings(tmp_path, case):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：拒绝伪造素材。"))
    other = repo.create_job(Brief(script_text="观点：另一个任务。")) if case == "foreign-job-artifact" else None
    if case == "missing-artifact":
        asset = Asset(asset_id="unit-context-missing", name="missing.png", role="evidence",
                      mime_type="image/png", size_bytes=10, sha256="0" * 64,
                      artifact_id="missing-artifact", url="/api/artifacts/missing-artifact",
                      timeline_src=f"videoagents/{job.job_id}/assets/missing.png")
    elif case == "foreign-job-artifact":
        asset = _registered_asset(repo, job, suffix=case, owner_job_id=other.job_id)
    elif case == "cross-task-timeline-src":
        asset = _registered_asset(repo, job, suffix=case, timeline_job_id=other.job_id if other else "other-job")
    elif case == "audio-missing-metadata":
        asset = _registered_asset(repo, job, suffix=case, role="audio", mime_type="audio/mpeg")
    else:
        asset = _registered_asset(repo, job, suffix=case)
        if case == "declared-sha":
            asset = asset.model_copy(update={"sha256": "1" * 64})
        elif case == "declared-size":
            asset = asset.model_copy(update={"size_bytes": asset.size_bytes + 1})
        elif case == "declared-mime":
            asset = asset.model_copy(update={"mime_type": "image/jpeg"})
        elif case == "tampered-bytes":
            repo.artifact_path(asset.artifact_id)[0].write_bytes(b"UNIT TEST tampered bytes")

    with pytest.raises((Conflict, ValueError)):
        current_job(repo, VideoState(job_id=job.job_id, revision=job.revision,
                                    latest_event_id=job.latest_event_id, action="produce",
                                    run_id=f"UNIT-{case}", thread_id=f"UNIT-{case}",
                                    assets=[asset.model_dump()]))

    assert repo.get_job(job.job_id).assets == []


def test_context_audio_asset_accepts_finite_duration_metadata(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：合法音频上下文素材。"))
    audio = _registered_asset(repo, job, suffix="valid-audio", role="audio", mime_type="audio/mpeg",
                              metadata={"origin": "upload", "duration_seconds": 1.25})

    current_job(repo, VideoState(job_id=job.job_id, revision=job.revision,
                                latest_event_id=job.latest_event_id, action="produce",
                                run_id="UNIT-valid-audio", thread_id="UNIT-valid-audio",
                                assets=[audio.model_dump()]))
    saved = repo.get_job(job.job_id)

    assert saved.assets == [audio]
