import io
import math
import os
import struct
import wave

import pytest

from videoagents.contracts import Brief, Finding, Review, Script, ScriptSegment, SettingsPatch
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import request_input
from videoagents.nodes.gates import TimelineGateNode
from videoagents.nodes.reviewers import ReviewersNode, dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from worker.runner import Worker


def _tone(seconds=2):
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(i / 10))) for i in range(int(seconds * 16000))))
    return output.getvalue()


def _seed_completed_research(repo: Repository, service: JobService, job) -> None:
    current = repo.get_job(job.job_id)
    if any(item.kind == "research" and item.revision == current.revision for item in current.artifacts):
        return
    service.write_json(current, "research.json", {
        "schema_version": "3",
        "status": "COMPLETED",
        "sources": [],
        "visuals": [],
        "limitations": ["UNIT TEST：下游流程测试夹具，素材节点研究结果已显式冻结为空。"],
    }, "research")


@pytest.fixture
def manual_job(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="明确标注的测试流程", script_text="观点：测试流程。", target_seconds=2,
                                width=240, height=426, fps=15, usage="personal", platform="测试平台"))
    alignment = {"origin": "manual", "verified": True, "segments": [{"segment_id": "s1", "text": "观点：测试流程。", "start_ms": 0, "end_ms": 1800}]}
    asset = service.upload(job.job_id, _tone(), "test-tone.wav", "audio", license_note="自有测试音，仅用于自动化测试", alignment=alignment)
    _seed_completed_research(repo, service, repo.get_job(job.job_id))
    return repo, service, repo.get_job(job.job_id), asset


def enqueue(repo, job, action="produce", key="first-command"):
    _seed_completed_research(repo, JobService(repo), job)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": action, "idempotency_key": key})
    return repo.get_job(job.job_id)


def test_missing_voice_is_persisted_interrupt_not_fake_audio(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：测试流程。"))
    enqueue(repo, job)
    worker = Worker(repo, tmp_path / "project")
    assert worker.once()
    paused = confirm_stage_reviews(repo, job.job_id, worker, "missing-voice")
    assert paused.status == "NEEDS_INPUT" and paused.stage == "voice"
    assert not any(item.role == "audio" for item in paused.assets)
    assert paused.pending_input["thread_id"]
    assert paused.pending_input["pending_token"]
    with VideoProductionGraph(repo, tmp_path / "project") as graph:
        saved = graph.graph.get_state({"configurable": {"thread_id": paused.pending_input["thread_id"]}})
        assert saved.interrupts
        assert saved.interrupts[0].value["pending_token"] == paused.pending_input["pending_token"]


def test_fact_source_gate_does_not_trigger_tts(monkeypatch, tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="测试数字是十。"))
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *a, **k: pytest.fail("unverified script reached paid TTS"))
    enqueue(repo, job)
    Worker(repo, tmp_path / "project").once()
    result = repo.get_job(job.job_id)
    assert result.status == "NEEDS_INPUT" and result.stage == "script"


def test_real_imported_audio_measured_timing_generates_storyboard(manual_job):
    repo, service, job, asset = manual_job
    enqueue(repo, job, "storyboard")
    worker = Worker(repo, service.project_root)
    worker.once()
    result = confirm_stage_reviews(repo, job.job_id, worker, "storyboard")
    assert result.status == "DRAFT" and result.stage == "director"
    assert result.timeline.audio_src == asset.timeline_src
    assert result.timeline.duration_in_frames == 30
    assert result.timeline.captions[0].end_ms == 1800
    assert result.timeline.shots[0].start_frame == 0 and result.timeline.shots[-1].end_frame == 30


def test_selected_older_audio_is_used_for_storyboard(manual_job):
    repo, service, job, first = manual_job
    second = service.upload(job.job_id, _tone(3), "second-test-tone.wav", "audio", license_note="自有测试音")
    current = repo.get_job(job.job_id)
    assert repo.active_audio(job.job_id) == second.asset_id
    service.set_alignment(job.job_id, current.revision, first.asset_id, {"origin": "manual", "verified": True,
        "segments": [{"segment_id": "s1", "text": "观点：测试流程。", "start_ms": 0, "end_ms": 1800}]})
    current = repo.get_job(job.job_id)
    enqueue(repo, current, "storyboard")
    worker = Worker(repo, service.project_root)
    worker.once()
    result = confirm_stage_reviews(repo, job.job_id, worker, "selected-audio")
    assert result.timeline.audio_src == first.timeline_src
    assert result.timeline.duration_in_frames == 30


def test_voice_role_advice_preserves_narration_and_actual_alignment(manual_job, monkeypatch):
    repo, service, job, audio = manual_job
    SettingsService(repo).patch(SettingsPatch(role_models={"voice": {"enabled": True, "model": "unit-voice"}}))
    calls = []
    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, context, output_schema))
        return {"delivery_notes": ["UNIT TEST：按原文自然朗读"], "pronunciation_notes": [], "findings": []}
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    enqueue(repo, job, "storyboard")
    worker = Worker(repo, service.project_root)
    worker.once()
    current = confirm_stage_reviews(repo, job.job_id, worker, "voice-advice")
    assert current.status == "DRAFT", current.message
    assert [call[0] for call in calls] == ["voice"]
    assert calls[0][2]["title"] == "VoiceAdvice"
    assert current.script.segments[0].narration == calls[0][1]["script"]["segments"][0]["narration"] == "观点：测试流程。"
    assert current.timeline.audio_src == audio.timeline_src
    assert current.timeline.captions[0].end_ms == 1800
    guidance = next(item for item in current.artifacts if item.kind == "voice_guidance")
    assert "UNIT TEST" in repo.artifact_path(guidance.artifact_id)[0].read_text(encoding="utf-8")


@pytest.mark.parametrize("voice_model", ["seed-tts-2.0-standard", "seed-tts-2.0-expressive"])
def test_new_voice_synthesis_applies_guidance_only_to_supported_model(manual_job, monkeypatch, voice_model):
    from videoagents.nodes.voice import VoiceNode
    from videoagents.services.settings import voice_fingerprint

    repo, service, job, _ = manual_job
    narration = job.brief.script_text
    job = repo.update_job(job.job_id, script=Script(title="TEST voice guidance", origin="user", revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration=narration)]))
    SettingsService(repo).patch(SettingsPatch(voice_provider="byte_ws", voice_api_key="UNIT-secret", voice_id="S_UNIT",
        voice_resource_id="seed-icl-2.0", voice_model=voice_model))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *a: True)
    notes = ["问题带好奇，重点加重。", "句间自然停顿。"]
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: {
        "delivery_notes": notes, "pronunciation_notes": [], "findings": []})
    path = repo.root / "UNIT-guidance-test-tone.wav"
    path.write_bytes(_tone())
    calls = []

    def provider(repository, job_id, revision, text, command_id, **options):
        calls.append((text, options))
        return {"path": str(path), "origin": "byte_ws", "voice_fingerprint": voice_fingerprint(SettingsService(repo).internal()),
            "voice_model": voice_model, "voice_style": options.get("delivery_style", ""), "voice_speech_rate": 0,
            "sentences": [{"words": [{"word": text, "startTime": 0, "endTime": 1.8}]}]}

    monkeypatch.setattr("videoagents.nodes.voice.synthesize", provider)
    audio, alignment, _ = VoiceNode(repo, service).prepare_audio(job, "UNIT-guidance-command", prefer_generation=True)
    assert len(calls) == 1 and calls[0][0] == narration
    assert ("delivery_style" in calls[0][1]) == voice_model.endswith("expressive")
    if voice_model.endswith("expressive"):
        assert calls[0][1]["delivery_style"] == "\n".join(notes)
    assert alignment.segments[0].text == narration and repo.get_job(job.job_id).script.segments[0].narration == narration
    assert repo.asset_metadata(audio.asset_id)["voice_model"] == voice_model


def test_matching_expressive_audio_is_reused_when_advice_changes(manual_job, monkeypatch):
    from videoagents.nodes.voice import VoiceNode
    from videoagents.services.settings import voice_fingerprint
    from videoagents.storage.repository import fingerprint

    repo, service, job, audio = manual_job
    job = repo.update_job(job.job_id, script=Script(title="TEST reuse", origin="user", revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration=job.brief.script_text)]))
    SettingsService(repo).patch(SettingsPatch(voice_provider="byte_ws", voice_api_key="UNIT-secret", voice_id="S_UNIT",
        voice_resource_id="seed-icl-2.0", voice_model="seed-tts-2.0-expressive", voice_style="面对观众自然讲解。"))
    repo.update_asset_metadata(audio.asset_id, {**repo.asset_metadata(audio.asset_id), "origin": "byte_ws",
        "voice_fingerprint": voice_fingerprint(SettingsService(repo).internal()),
        "script_fingerprint": fingerprint([{"segment_id": s.segment_id, "narration": s.narration} for s in job.script.segments])})
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *a: True)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: {
        "delivery_notes": ["UNIT：新增朗读建议不应让恢复流程重复合成。"], "pronunciation_notes": [], "findings": []})
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *a, **k: pytest.fail("matching audio was synthesized again"))
    selected, alignment, duration = VoiceNode(repo, service).prepare_audio(job, "UNIT-reuse-command")
    assert selected.asset_id == audio.asset_id and alignment.verified and duration == pytest.approx(2)


def test_imported_audio_can_be_used_after_disabling_expressive_service(manual_job, monkeypatch):
    from videoagents.nodes.voice import VoiceNode

    repo, service, job, audio = manual_job
    job = repo.update_job(job.job_id, script=Script(title="TEST imported audio", origin="user", revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration=job.brief.script_text)]))
    # 关闭服务保留风格设置，不能因此拒绝用户导入的真实音频和对齐记录。
    SettingsService(repo).patch(SettingsPatch(voice_provider="none", voice_model="seed-tts-2.0-expressive", voice_style="自然演讲。"))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *a: False)
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *a, **k: pytest.fail("imported audio unexpectedly reached synthesis"))
    selected, alignment, _ = VoiceNode(repo, service).prepare_audio(job)
    assert selected.asset_id == audio.asset_id and alignment.verified


@pytest.mark.parametrize("invalid", [False, True])
def test_voice_model_blocking_or_rewritten_output_cannot_reach_audio_execution(manual_job, monkeypatch, invalid):
    repo, service, job, _ = manual_job
    SettingsService(repo).patch(SettingsPatch(role_models={"voice": {"enabled": True}}))
    value = {"delivery_notes": [], "pronunciation_notes": [], "findings": [{
        "severity": "warning", "message": "UNIT TEST：请核对读音", "owner": "voice", "blocking": True}]}
    if invalid:
        value = {"narration": "forbidden model rewrite", "delivery_notes": [], "pronunciation_notes": [], "findings": []}
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **k: value)
    monkeypatch.setattr("videoagents.nodes.voice.audio_duration", lambda *a: pytest.fail("blocked preflight reached audio execution"))
    enqueue(repo, job, "storyboard")
    worker = Worker(repo, service.project_root)
    worker.once()
    current = confirm_stage_reviews(repo, job.job_id, worker, f"voice-blocked-{invalid}")
    assert current.status == "NEEDS_INPUT" and current.stage == "voice"
    assert current.pending_input["thread_id"] and current.pending_input["pending_token"]
    assert current.script.segments[0].narration == "观点：测试流程。"
    assert any(item.kind == "voice_guidance" for item in current.artifacts) is (not invalid)


@pytest.mark.parametrize("blocking", [False, True])
def test_editing_role_preflight_keeps_remotion_execution_and_blocks_findings(manual_job, monkeypatch, blocking):
    repo, service, job, _ = manual_job
    enqueue(repo, job, "storyboard")
    worker = Worker(repo, service.project_root)
    worker.once()
    current = confirm_stage_reviews(repo, job.job_id, worker, f"editing-setup-{blocking}")
    original_timeline = current.timeline.model_dump()
    SettingsService(repo).patch(SettingsPatch(role_models={"editing": {"enabled": True}}))
    calls, renders = [], []
    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, output_schema["title"]))
        return {"pacing_notes": ["UNIT TEST：保持实测边界"], "layout_notes": ["UNIT TEST：核对标题可读性"],
            "findings": [{"severity": "warning", "message": "UNIT TEST：需调整标题", "owner": "editing", "blocking": True}] if blocking else []}
    def render_double(project, timeline_path, output, cover, mode, timeout, cancelled, progress):
        # Synthetic bytes test invocation only, never claim a production MP4.
        renders.append(mode)
        output.write_bytes(b"synthetic-render-unit-test-not-a-production-video")
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    monkeypatch.setattr("videoagents.nodes.editing.render", render_double)
    enqueue(repo, current, "preview", "editing-preflight-command")
    worker.once()
    result = confirm_stage_reviews(repo, job.job_id, worker, f"editing-preview-{blocking}")
    assert calls == [("editing", "EditingAdvice")]
    assert result.timeline.model_dump() == original_timeline
    assert any(item.kind == "editing_guidance" for item in result.artifacts)
    if blocking:
        assert result.status == "NEEDS_INPUT" and result.stage == "render"
        assert renders == []
    else:
        assert result.status == "DRAFT" and result.stage == "render"
        assert renders == ["preview"]


def test_editing_model_unknown_is_a_real_persisted_interrupt(manual_job, monkeypatch):
    from videoagents.providers.llm import CapabilityMissing
    repo, service, job, _ = manual_job
    enqueue(repo, job, "storyboard")
    worker = Worker(repo, service.project_root)
    worker.once()
    current = confirm_stage_reviews(repo, job.job_id, worker, "unknown-editing-setup")
    SettingsService(repo).patch(SettingsPatch(role_models={"editing": {"enabled": True}}))
    def unknown(*args, **kwargs):
        raise CapabilityMissing("UNIT TEST unknown CLI submission", ["llm_operation"], operation_status="UNKNOWN", operation_id="unit-editing-operation")
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", unknown)
    monkeypatch.setattr("videoagents.nodes.editing.render", lambda *a: pytest.fail("UNKNOWN preflight reached Remotion"))
    enqueue(repo, current, "preview", "unknown-editing-command")
    worker.once()
    result = confirm_stage_reviews(repo, job.job_id, worker, "unknown-editing-preview")
    assert result.status == "NEEDS_INPUT" and result.stage == "render"
    assert result.pending_input["operation_status"] == "UNKNOWN"
    assert result.pending_input["operation_id"] == "unit-editing-operation"
    assert result.pending_input["thread_id"] and result.pending_input["pending_token"]


def install_isolated_review_doubles(monkeypatch):
    """No real media claim: these doubles test state transitions/fault windows only."""
    def edit(self, job, mode, state=None):
        path = self.repo.root / (job.job_id + "-synthetic-render-unit-test.mp4")
        path.write_bytes(b"synthetic-render-unit-test-not-a-production-video")
        artifact = self.service.register_artifact(job, path, "final", "video/mp4")
        self.repo.update_artifact_metadata(artifact.artifact_id, {"dependency_fingerprint": dependency_fingerprint(job)})
        self.service.append_artifact(job.job_id, artifact, job.revision)
    def review(self, job, human_confirmed=False, model_review=True, state=None):
        final = next(item for item in job.artifacts if item.kind == "final")
        return Review(status="PASS" if human_confirmed else "NEEDS_HUMAN", findings=[] if human_confirmed else [Finding(
            finding_id="unit-human", severity="warning", category="human_full_review", owner="user", blocking=True, message="UNIT TEST DOUBLE: verify simulated transition")],
            media_sha256=final.sha256, dependency_fingerprint=dependency_fingerprint(job),
            coverage=["unit_test_double"], human_confirmed=human_confirmed)
    monkeypatch.setattr("videoagents.nodes.editing.EditingNode.render_video", edit)
    monkeypatch.setattr("videoagents.nodes.reviewers.ReviewersNode.review", review)


def resume(repo, job, decision, note="", key="resume-command"):
    payload = {"base_revision": job.revision, "action": "resume", "decision": decision, "note": note,
               "idempotency_key": key, "pending_token": job.pending_input["pending_token"]}
    repo.enqueue(job.job_id, payload)
    return payload


def confirm_stage_reviews(repo, job_id, worker, key_prefix="stage-review"):
    note = "UNIT TEST：确认本阶段产物可进入后续自动化节点。"
    for index in range(10):
        current = repo.get_job(job_id)
        if current.status != "NEEDS_HUMAN" or current.pending_input.get("kind") != "stage_review":
            return current
        resume(repo, current, "confirm", note, f"{key_prefix}-{index}-{current.pending_input['pending_token'][:8]}")
        assert worker.once()
    raise AssertionError("stage review confirmation loop did not settle")


@pytest.mark.parametrize("decision", ["cancel", "revise"])
def test_short_human_note_then_cancel_or_revise_never_publishes(manual_job, monkeypatch, decision):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    worker = Worker(repo, service.project_root)
    enqueue(repo, job)
    worker.once()
    paused = confirm_stage_reviews(repo, job.job_id, worker, f"final-review-{decision}")
    first_token = paused.pending_input["pending_token"]
    resume(repo, paused, "confirm", "short", "first-resume")
    worker.once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN"
    assert paused.pending_input["pending_token"] != first_token
    resume(repo, paused, decision, "完整播放并核验内容、音画和许可的测试说明", "second-resume")
    worker.once()
    result = repo.get_job(job.job_id)
    assert result.status == ("CANCELLED" if decision == "cancel" else "DRAFT"), result.message
    assert not result.review.human_confirmed


def test_resume_reclaim_does_not_answer_a_new_interrupt(manual_job, monkeypatch):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    # Force an initial configuration gate before actual rendering.
    original = TimelineGateNode.__call__
    first = [True]
    def initially_blocked(self, state):
        if first[0]:
            first[0] = False
            return request_input(self.repo, state, "render", ["UNIT TEST: configure render"], ["render"])
        return original(self, state)
    monkeypatch.setattr(TimelineGateNode, "__call__", initially_blocked)
    worker = Worker(repo, service.project_root)
    enqueue(repo, job)
    worker.once()
    paused = confirm_stage_reviews(repo, job.job_id, worker, "reclaim-before-input")
    assert paused.status == "NEEDS_INPUT"
    resume(repo, paused, "confirm", "仅确认配置修复，并未观看任何成片", "configuration-resume")
    command = repo.claim(os.getpid())
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
    human = repo.get_job(job.job_id)
    assert human.status == "NEEDS_HUMAN"
    assert human.pending_input["pending_token"] != paused.pending_input["pending_token"]
    # Simulate crash after graph checkpoint, before command DONE, then execute
    # the same claimed command again: old confirmation must not reach review.
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN"
    assert current.pending_input["pending_token"] == human.pending_input["pending_token"]
    assert current.review is None or current.review.human_confirmed is False
    repo.finish(command["command_id"])


def test_finalization_recovers_after_sql_ready_before_graph_checkpoint(manual_job, monkeypatch):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    worker = Worker(repo, service.project_root)
    worker.once()
    paused = confirm_stage_reviews(repo, job.job_id, worker, "finalization")
    resume(repo, paused, "confirm", "UNIT TEST 完整播放并核验事实、音画、字幕和素材许可。")
    command = repo.claim(os.getpid())
    original = repo.update_job
    hit = [False]
    def injected(job_id, expected_revision=None, **changes):
        result = original(job_id, expected_revision, **changes)
        if changes.get("status") == "READY_FOR_PUBLISH" and not hit[0]:
            hit[0] = True
            raise SystemExit("UNIT TEST simulated process loss after terminal SQL commit")
        return result
    monkeypatch.setattr(repo, "update_job", injected)
    with VideoProductionGraph(repo, service.project_root) as graph, pytest.raises(SystemExit):
        graph.execute(command)
    assert repo.get_job(job.job_id).status == "READY_FOR_PUBLISH"
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
    repo.finish(command["command_id"])
    current = repo.get_job(job.job_id)
    assert current.status == "READY_FOR_PUBLISH"
    assert len([item for item in current.artifacts if item.kind == "package"]) == 1


@pytest.mark.parametrize("unknown", [False, True])
def test_reviewer_provider_failure_has_real_resumable_interrupt(manual_job, monkeypatch, unknown):
    install_isolated_review_doubles(monkeypatch)
    from videoagents.providers.llm import CapabilityMissing
    failure = CapabilityMissing("UNIT TEST missing model", ["llm"], operation_status="UNKNOWN" if unknown else None,
        operation_id="unit-unknown-operation" if unknown else None)
    monkeypatch.setattr("videoagents.nodes.reviewers.ReviewersNode.review", lambda *args, **kwargs: (_ for _ in ()).throw(failure))
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    worker = Worker(repo, service.project_root)
    worker.once()
    paused = confirm_stage_reviews(repo, job.job_id, worker, "finalization")
    assert paused.status == "NEEDS_INPUT"
    assert paused.pending_input["thread_id"] and paused.pending_input["pending_token"]
    if unknown:
        assert paused.pending_input["operation_status"] == "UNKNOWN"
        assert paused.pending_input["operation_id"] == "unit-unknown-operation"


def test_201_measured_byte_words_fit_alignment_contract():
    from videoagents.contracts import Job
    from videoagents.nodes.voice import from_byte_sentences
    text = "字" * 201
    script = Script(title="测试", origin="user", revision=1, segments=[ScriptSegment(segment_id="s1", narration=text)])
    job = Job(job_id="test", revision=1, status="DRAFT", stage="idle", created_at="test", updated_at="test", message="",
              brief=Brief(topic="test"), script=script)
    words = [{"word": "字", "startTime": i * 0.1, "endTime": (i + 1) * 0.1, "confidence": 1} for i in range(201)]
    result = from_byte_sentences(job, "a" * 64, [{"words": words}])
    assert result is not None and len(result.segments) == 201


@pytest.mark.parametrize("existing_generated", [False, True])
def test_voice_preflight_settings_change_records_actual_provider_fingerprint(manual_job, monkeypatch, existing_generated):
    from videoagents.nodes.voice import VoiceNode
    from videoagents.providers.llm import CapabilityMissing
    from videoagents.services.settings import voice_fingerprint
    from videoagents.storage.repository import fingerprint

    repo, service, job, old_audio = manual_job
    job = repo.update_job(job.job_id, script=Script(title="TEST preflight", origin="user", revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration=job.brief.script_text)]))
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(voice_provider="byte_ws", voice_api_key="UNIT-secret", voice_id="UNIT-own-voice", voice_resource_id="seed-icl-2.0"))
    old_hash = voice_fingerprint(settings.internal())
    if existing_generated:
        repo.update_asset_metadata(old_audio.asset_id, {**repo.asset_metadata(old_audio.asset_id), "origin": "byte_ws",
            "voice_fingerprint": old_hash, "script_fingerprint": fingerprint([
                {"segment_id": item.segment_id, "narration": item.narration} for item in job.script.segments])})
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: True)
    def advice(*args, **kwargs):
        settings.patch(SettingsPatch(voice_model="seed-tts-2.0-expressive"))
        return {"delivery_notes": [], "pronunciation_notes": [], "findings": []}
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", advice)
    path = repo.root / "UNIT-preflight-test-tone.wav"
    path.write_bytes(_tone())
    def provider(*args, **kwargs):
        # A measured TEST tone stands in for audio; this is metadata/coverage
        # regression evidence, not a claim of actual speech or clone quality.
        return {"path": str(path), "origin": "byte_ws", "voice_fingerprint": voice_fingerprint(settings.internal()),
            "sentences": [{"words": [{"word": job.script.segments[0].narration, "startTime": 0, "endTime": 1.8}]}]}
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", provider)
    audio, _, _ = VoiceNode(repo, service).prepare_audio(job, "UNIT-preflight-command", prefer_generation=not existing_generated)
    assert audio.asset_id != old_audio.asset_id
    actual_hash = repo.asset_metadata(audio.asset_id)["voice_fingerprint"]
    assert actual_hash == voice_fingerprint(settings.internal()) and actual_hash != old_hash
    settings.patch(SettingsPatch(voice_model="seed-tts-2.0-standard"))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: False)
    calls = []
    def new_provider(*args, **kwargs):
        calls.append(args[3])
        raise CapabilityMissing("UNIT old configuration requires fresh synthesis")
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", new_provider)
    with pytest.raises(CapabilityMissing):
        VoiceNode(repo, service).prepare_audio(repo.get_job(job.job_id), "UNIT-return-to-old-config")
    assert calls == [job.script.segments[0].narration]


def test_human_confirmation_reruns_hard_checks_and_cannot_waive_failure(manual_job, monkeypatch):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    worker = Worker(repo, service.project_root)
    worker.once()
    paused = confirm_stage_reviews(repo, job.job_id, worker, "hard-check-rerun")
    assert paused.status == "NEEDS_HUMAN"
    def fail_review(self, job, **kwargs):
        return Review(status="REVISE", findings=[Finding(finding_id="changed-media", severity="error", category="media_hash",
            owner="editing", blocking=True, message="UNIT TEST: final media changed after first review")],
            media_sha256="new-hash", dependency_fingerprint=dependency_fingerprint(job), human_confirmed=False)
    monkeypatch.setattr(ReviewersNode, "review", fail_review)
    resume(repo, paused, "confirm", "UNIT TEST完整播放并核验事实、声音、画面与素材许可。")
    worker.once()
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT"
    assert current.review.status == "REVISE" and not current.review.human_confirmed
    assert current.pending_input["pending_token"] != paused.pending_input["pending_token"]


def test_generated_attachment_rolls_back_metadata_with_job_on_crash(manual_job, monkeypatch):
    from videoagents.contracts import Asset
    repo, service, job, _ = manual_job
    path = repo.root / "unit-generated.wav"
    path.write_bytes(_tone())
    artifact = service.register_artifact(job, path, "voice", "audio/wav")
    generated = Asset(asset_id="unit-generated", name="unit.wav", role="audio", mime_type="audio/wav", size_bytes=artifact.size_bytes,
        sha256=artifact.sha256, artifact_id=artifact.artifact_id, url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/unit-generated.wav")
    before = repo.active_audio(job.job_id)
    def crash(*args, **kwargs):
        raise SystemExit("UNIT TEST injected transaction crash")
    monkeypatch.setattr(repo, "_save", crash)
    with pytest.raises(SystemExit):
        repo.attach_generated_audio(job.job_id, job.revision, generated, artifact, {"origin": "byte_http", "alignment": {"test": "fixture"}})
    assert all(asset.asset_id != generated.asset_id for asset in repo.get_job(job.job_id).assets)
    assert repo.asset_metadata(generated.asset_id) == {}
    assert repo.active_audio(job.job_id) == before


def test_stale_pending_token_same_revision_is_rejected(manual_job, monkeypatch):
    from videoagents.storage import Conflict
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    worker = Worker(repo, service.project_root)
    worker.once()
    paused = repo.get_job(job.job_id)
    resume(repo, paused, "confirm", "short", "old-short-answer")
    worker.once()
    current = repo.get_job(job.job_id)
    assert current.revision == paused.revision
    with pytest.raises(Conflict):
        repo.enqueue(job.job_id, {"action": "resume", "base_revision": current.revision, "decision": "confirm",
            "note": "UNIT TEST old answer", "pending_token": paused.pending_input["pending_token"], "idempotency_key": "stale-old-answer"})
