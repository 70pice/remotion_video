import io
import math
import struct
import wave

import pytest
from pydantic import ValidationError

from videoagents.contracts import (
    Brief,
    Script,
    ScriptSegment,
    SettingsPatch,
    VoiceAdvice,
    VoiceSegmentPerformance,
)
from videoagents.nodes.voice import (
    SegmentAudio,
    VoiceNode,
    segment_clips,
    stitch_segment_audio,
    validate_segment_performances,
)
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService, voice_fingerprint
from videoagents.storage import Repository
from worker.process_manager import RenderCancelled


def tone(seconds: float = 2) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"".join(
            struct.pack("<h", int(500 * math.sin(index / 10)))
            for index in range(int(seconds * 16000))
        ))
    return output.getvalue()


def tone_window(seconds: float, active_start: float, active_end: float) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"".join(
            struct.pack(
                "<h",
                int(6000 * math.sin(index / 10))
                if active_start <= index / 16000 < active_end else 0,
            )
            for index in range(int(seconds * 16000))
        ))
    return output.getvalue()


def two_segment_job(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="TEST segmented voice", script_text="第一段。第二段。"))
    script = Script(
        title="TEST segmented voice",
        revision=job.revision,
        origin="user",
        segments=[
            ScriptSegment(segment_id="s1", narration="第一段。"),
            ScriptSegment(segment_id="s2", narration="第二段。"),
        ],
    )
    return repo, service, repo.update_job(job.job_id, script=script)


def performances() -> list[VoiceSegmentPerformance]:
    return [
        VoiceSegmentPerformance(segment_id="s1", delivery_style="第一段带着疑问起句，段末留出承接。", pause_after_ms=200),
        VoiceSegmentPerformance(segment_id="s2", delivery_style="第二段明确回答，结尾坚定收住。", pause_after_ms=0),
    ]


def test_voice_advice_rejects_duplicate_segment_ids():
    with pytest.raises(ValidationError, match="段落 ID 必须唯一"):
        VoiceAdvice.model_validate({
            "segment_performances": [
                {"segment_id": "s1", "delivery_style": "第一种读法。", "pause_after_ms": 200},
                {"segment_id": "s1", "delivery_style": "第二种读法。", "pause_after_ms": 0},
            ],
        })


@pytest.mark.parametrize("values", [
    [
        VoiceSegmentPerformance(segment_id="s2", delivery_style="第二段。", pause_after_ms=200),
        VoiceSegmentPerformance(segment_id="s1", delivery_style="第一段。", pause_after_ms=0),
    ],
    [VoiceSegmentPerformance(segment_id="s1", delivery_style="只有一段。", pause_after_ms=0)],
])
def test_segment_performance_plan_must_match_script_order(tmp_path, values):
    _, _, job = two_segment_job(tmp_path)
    with pytest.raises(ValueError, match="完整匹配"):
        validate_segment_performances(job, values)


def test_segment_timeline_uses_requested_total_pause_without_double_counting(tmp_path):
    path = tmp_path / "tone.wav"
    path.write_bytes(tone())
    clips = segment_clips([
        SegmentAudio("s1", path, 2, [{"word": "第一段", "startTime": 0.2, "endTime": 1.0}], 500),
        SegmentAudio("s2", path, 2, [{"word": "第二段", "startTime": 0.2, "endTime": 1.0}], 0),
    ])
    first_end = clips[0].adjusted_words[-1]["endTime"]
    second_start = clips[1].adjusted_words[0]["startTime"]
    assert second_start - first_end == pytest.approx(0.5)
    assert clips[0].inserted_pause_after_seconds == pytest.approx(0.2)


def test_stitch_retains_acoustic_tail_beyond_provider_last_word_end(tmp_path):
    source = tmp_path / "tail.wav"
    source.write_bytes(tone_window(1.8, 0.2, 1.45))
    output = tmp_path / "tail.mp3"

    clips = stitch_segment_audio([
        SegmentAudio("s1", source, 1.8, [
            {"word": "完整尾音", "startTime": 0.2, "endTime": 1.0},
        ], 0),
    ], output, lambda: False)

    assert clips[0].trim_end_seconds >= 1.45


def test_expressive_plan_synthesizes_each_segment_and_offsets_real_timestamps(tmp_path, monkeypatch):
    repo, service, job = two_segment_job(tmp_path)
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(
        voice_provider="byte_ws",
        voice_api_key="UNIT-secret",
        voice_id="UNIT-own-voice",
        voice_resource_id="seed-icl-2.0",
        voice_model="seed-tts-2.0-expressive",
        voice_style="像朋友一样自然讲解。",
        voice_speech_rate=0,
    ))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: True)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: {
        "delivery_notes": ["先提出疑问，再明确回答。"],
        "segment_performances": [item.model_dump() for item in performances()],
        "pronunciation_notes": [],
        "findings": [],
    })
    source = repo.root / "segment-source.wav"
    source.write_bytes(tone_window(2, 0.2, 1.0))
    calls = []

    def provider(repository, job_id, revision, text, command_id, **options):
        calls.append((text, command_id, options))
        index = len(calls)
        return {
            "path": str(source),
            "origin": "byte_ws",
            "operation_id": f"operation-{index}",
            "request_id": f"request-{index}",
            "input_hash": f"input-{index}",
            "voice_fingerprint": voice_fingerprint(settings.internal()),
            "voice_model": "seed-tts-2.0-expressive",
            "voice_speech_rate": 0,
            "sentences": [{"words": [{
                "word": text,
                "startTime": 0.2,
                "endTime": 1.0,
                "confidence": 0.99,
            }]}],
        }

    monkeypatch.setattr("videoagents.nodes.voice.synthesize", provider)
    audio, alignment, duration = VoiceNode(repo, service).prepare_audio(
        job, "UNIT-segmented-command", prefer_generation=True
    )
    assert [item[0] for item in calls] == ["第一段。", "第二段。"]
    assert [item[2]["delivery_style"] for item in calls] == [
        "第一段带着疑问起句，段末留出承接。",
        "第二段明确回答，结尾坚定收住。",
    ]
    assert [item[2]["operation_key"] for item in calls] == ["script-segment:s1", "script-segment:s2"]
    assert [item[1] for item in calls] == [
        "UNIT-segmented-command:segment:s1",
        "UNIT-segmented-command:segment:s2",
    ]
    assert [item.segment_id for item in alignment.segments] == ["s1", "s2"]
    assert alignment.segments[1].start_ms - alignment.segments[0].end_ms == pytest.approx(200)
    assert 1.9 < duration < 2.4
    metadata = repo.asset_metadata(audio.asset_id)
    assert metadata["segmented"] is True
    assert [item["segment_id"] for item in metadata["segment_operations"]] == ["s1", "s2"]
    assert metadata["segment_stitch"][0]["requested_pause_after_ms"] == 200
    assert metadata["segment_stitch"][0]["provider_end_ms"] == 1000
    assert metadata["segment_stitch"][0]["acoustic_end_ms"] == 1000
    assert metadata["segment_stitch"][0]["retained_acoustic_tail_ms"] == 0


def test_standard_model_with_segment_plan_falls_back_to_whole_script(tmp_path, monkeypatch):
    repo, service, job = two_segment_job(tmp_path)
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(
        voice_provider="byte_ws",
        voice_api_key="UNIT-secret",
        voice_id="UNIT-own-voice",
        voice_resource_id="seed-icl-2.0",
        voice_model="seed-tts-2.0-standard",
        voice_style="",
        voice_speech_rate=0,
    ))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda *args: True)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: {
        "delivery_notes": ["整稿自然朗读。"],
        "segment_performances": [item.model_dump() for item in performances()],
        "pronunciation_notes": [],
        "findings": [],
    })
    source = repo.root / "whole-source.wav"
    source.write_bytes(tone())
    calls = []

    def provider(repository, job_id, revision, text, command_id, **options):
        calls.append((text, options))
        return {
            "path": str(source),
            "origin": "byte_ws",
            "voice_fingerprint": voice_fingerprint(settings.internal()),
            "sentences": [{"words": [
                {"word": "第一段。", "startTime": 0.1, "endTime": 0.8},
                {"word": "第二段。", "startTime": 1.0, "endTime": 1.8},
            ]}],
        }

    monkeypatch.setattr("videoagents.nodes.voice.synthesize", provider)
    VoiceNode(repo, service).prepare_audio(job, "UNIT-whole-command", prefer_generation=True)
    assert len(calls) == 1 and calls[0][0] == "第一段。\n第二段。"
    assert "delivery_style" not in calls[0][1] and "operation_key" not in calls[0][1]


@pytest.mark.parametrize("cancelled", [False, True])
def test_stitch_failure_or_cancel_does_not_leave_partial_output(tmp_path, monkeypatch, cancelled):
    source = tmp_path / "source.wav"
    source.write_bytes(tone())
    output = tmp_path / "result.mp3"
    segments = [
        SegmentAudio("s1", source, 2, [{"word": "第一段", "startTime": 0.2, "endTime": 1.0}], 0),
    ]
    if not cancelled:
        monkeypatch.setattr(
            "videoagents.nodes.voice._execute_ffmpeg",
            lambda *args: (_ for _ in ()).throw(ValueError("UNIT concat failure")),
        )
    expected = RenderCancelled if cancelled else ValueError
    with pytest.raises(expected):
        stitch_segment_audio(segments, output, lambda: cancelled)
    assert not output.exists()
