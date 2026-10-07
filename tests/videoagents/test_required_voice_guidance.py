import io
import json
import wave

import pytest

from videoagents.contracts import Brief, Script, ScriptSegment, SettingsPatch
from videoagents.nodes.voice import VoiceNode
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService, voice_fingerprint
from videoagents.storage import Repository


@pytest.fixture
def voice_job(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT voice guidance", script_text="测试旁白。"))
    job = repo.update_job(job.job_id, script=Script(
        title="UNIT voice guidance", origin="user", revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration=job.brief.script_text)],
    ))
    SettingsService(repo).patch(SettingsPatch(
        voice_provider="byte_ws", voice_api_key="UNIT-test-secret", voice_id="S_UNIT",
        voice_resource_id="seed-icl-2.0", voice_model="seed-tts-2.0-expressive",
        voice_style="用户固定风格。", voice_speech_rate=10,
    ))
    return repo, service, job


def test_voice_guidance_is_enabled_by_default_and_old_disabled_settings_are_normalized(tmp_path):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    assert settings.internal()["role_models"]["voice"]["enabled"] is True
    repo.write_settings({"role_models": json.dumps({
        "voice": {"enabled": False, "provider": "codex_cli", "model": "unit-voice", "timeout_seconds": 300},
        "director": {"enabled": False},
    })})
    roles = SettingsService(Repository(repo.root)).internal()["role_models"]
    assert roles["voice"] == {
        "enabled": True, "provider": "codex_cli", "model": "unit-voice", "timeout_seconds": 300,
    }
    assert roles["director"]["enabled"] is False


def test_settings_patch_cannot_disable_voice_guidance_or_replace_other_role_fields(tmp_path):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(role_models={
        "voice": {"enabled": True, "provider": "trae_cli", "model": "unit-voice", "timeout_seconds": 300},
        "director": {"enabled": True, "model": "unit-director"},
    }))
    settings.patch(SettingsPatch(role_models={"voice": {"enabled": False}, "director": {"enabled": False}}))
    roles = SettingsService(Repository(repo.root)).internal()["role_models"]
    assert roles["voice"] == {
        "enabled": True, "provider": "trae_cli", "model": "unit-voice", "timeout_seconds": 300,
    }
    assert roles["director"]["enabled"] is False and roles["director"]["model"] == "unit-director"
    assert json.loads(repo.setting_values()["role_models"])["voice"]["enabled"] is True


def call_voice(repo, service, job):
    return VoiceNode(repo, service)({
        "job_id": job.job_id, "revision": job.revision, "action": "voice",
        "run_id": "UNIT-voice-command", "thread_id": "UNIT-voice-thread",
    })


def test_missing_voice_agent_pauses_before_tts(voice_job, monkeypatch):
    repo, service, job = voice_job
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: False)
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *args, **kwargs: pytest.fail("unguided TTS"))
    result = call_voice(repo, service, job)
    assert result["route"] == "await_input"
    assert repo.get_job(job.job_id).status == "NEEDS_INPUT"
    assert "指导" in repo.get_job(job.job_id).message
    assert not any(asset.role == "audio" for asset in repo.get_job(job.job_id).assets)


def test_empty_advice_cannot_fall_back_to_fixed_style(voice_job, monkeypatch):
    repo, service, job = voice_job
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: True)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: {
        "delivery_notes": [], "segment_performances": [], "pronunciation_notes": [], "findings": [],
    })
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *args, **kwargs: pytest.fail("empty-guidance TTS"))
    result = call_voice(repo, service, job)
    assert result["route"] == "await_input"
    assert "指导" in repo.get_job(job.job_id).message


@pytest.mark.parametrize("patch", [
    {"voice_provider": "byte_http", "voice_style": "", "voice_speech_rate": 0},
    {"voice_model": "seed-tts-2.0-standard", "voice_style": ""},
])
def test_unsupported_tts_pauses_instead_of_dropping_guidance(voice_job, monkeypatch, patch):
    repo, service, job = voice_job
    SettingsService(repo).patch(SettingsPatch(**patch))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: {
        "delivery_notes": ["针对原文的表演指导。"], "findings": [],
    })
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *args, **kwargs: pytest.fail("unsupported TTS"))
    result = call_voice(repo, service, job)
    assert result["route"] == "await_input"
    assert "expressive" in repo.get_job(job.job_id).message


@pytest.mark.parametrize("status", ["SUBMITTING", "UNKNOWN"])
def test_unsettled_guidance_stays_paused_and_keeps_original_ledger(voice_job, monkeypatch, status):
    repo, service, job = voice_job
    body = {"revision": job.revision, "model": "unit-voice"}
    operation = repo.start_operation(job.job_id, "UNIT-pending-guidance", "llm:voice", body)
    repo.finish_operation(operation["operation_id"], status, body)
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *args, **kwargs: pytest.fail("unsettled-guidance TTS"))
    result = call_voice(repo, service, job)
    assert result["route"] == "await_input"
    assert "状态未知" in repo.get_job(job.job_id).message
    assert repo.operation(job.job_id, "UNIT-pending-guidance", "llm:voice")["status"] == status


def test_successful_new_tts_receives_completed_guidance_and_preserves_user_settings(voice_job, monkeypatch):
    repo, service, job = voice_job
    calls = []
    notes = "测试带好奇，旁白两字稍加重，句末收住。"

    def advice(*args, **kwargs):
        calls.append("guidance")
        return {"delivery_notes": [notes], "findings": []}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", advice)
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"\0\0" * 32000)
    path = repo.root / "UNIT-measured-test.wav"
    path.write_bytes(output.getvalue())

    def provider(repository, job_id, revision, text, command_id, **options):
        calls.append("tts")
        assert text == job.brief.script_text and options["delivery_style"] == notes
        settings = SettingsService(repository).internal()
        assert settings["voice_style"] == "用户固定风格。" and settings["voice_speech_rate"] == 10
        guidance = [item for item in repository.get_job(job_id).artifacts if item.kind == "voice_guidance"]
        assert len(guidance) == 1
        return {"path": str(path), "origin": "byte_ws", "voice_fingerprint": voice_fingerprint(settings),
                "sentences": [{"words": [{"word": text, "startTime": 0, "endTime": 1.8}]}]}

    monkeypatch.setattr("videoagents.nodes.voice.synthesize", provider)
    _, alignment, _ = VoiceNode(repo, service).prepare_audio(job, "UNIT-guided-command", prefer_generation=True)
    assert calls == ["guidance", "tts"]
    assert alignment.segments[0].text == job.brief.script_text
    assert repo.get_job(job.job_id).script == job.script


@pytest.mark.parametrize("provider", ["byte_ws", "byte_http"])
@pytest.mark.parametrize("status", ["SUBMITTING", "UNKNOWN"])
def test_unsettled_tts_pauses_before_another_guidance_call(voice_job, monkeypatch, provider, status):
    repo, service, job = voice_job
    body = {"revision": job.revision, "request_id": "UNIT-pending-tts"}
    operation = repo.start_operation(job.job_id, "UNIT-pending-tts", provider, body)
    repo.finish_operation(operation["operation_id"], status, body)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **kw: pytest.fail("unsettled TTS reached guidance"))
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *a, **kw: pytest.fail("unsettled TTS resubmitted"))
    result = call_voice(repo, service, job)
    assert result["route"] == "await_input"
    assert "未决配音" in repo.get_job(job.job_id).message
    assert repo.operation(job.job_id, "UNIT-pending-tts", provider)["status"] == status


def test_settings_change_after_advice_cannot_drop_guidance(voice_job, monkeypatch):
    repo, service, job = voice_job

    def advice(*args, **kwargs):
        SettingsService(repo).patch(SettingsPatch(voice_model="seed-tts-2.0-standard", voice_style=""))
        return {"delivery_notes": ["针对原文的表演指导。"], "findings": []}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", advice)
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *args, **kwargs: pytest.fail("dropped-guidance TTS"))
    with pytest.raises(CapabilityMissing, match="expressive"):
        VoiceNode(repo, service).prepare_audio(job, "UNIT-change-config", prefer_generation=True)
