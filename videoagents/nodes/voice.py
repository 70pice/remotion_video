"""Use real imported/Byte audio and verified timestamps, with strict text coverage."""

import array
import math
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from videoagents.contracts import (
    Alignment,
    AlignmentSegment,
    Asset,
    Job,
    VoiceAdvice,
    VoiceSegmentPerformance,
)
from videoagents.nodes.common import agent_state, request_input, start_stage, state_context
from videoagents.prompts import compose
from videoagents.providers.aligner import align
from videoagents.providers.byte_voice import synthesize
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService, supports_voice_style, voice_fingerprint
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.media import audio_duration
from worker.process_manager import RenderCancelled, terminate_tree
from worker.windows_job import WindowsJob

PROMPT = compose("shared-style", "voice")
VOICE_SAMPLE_RATE = 24000


def normalized(text: str) -> str:
    return "".join(char.lower() for char in text if char.isalnum())


def validate_alignment(job: Job, asset: Asset, alignment: Alignment, duration: float) -> list[str]:
    issues = []
    if not alignment.verified:
        issues.append("音频时间戳未标记为实测/已核验")
    if alignment.audio_sha256 != asset.sha256:
        issues.append("时间戳绑定的音频 hash 与当前音频不同")
    if alignment.segments[-1].end_ms > duration * 1000 + 80:
        issues.append("字幕时间戳超出实测音频时长")
    expected = {segment.segment_id: normalized(segment.narration) for segment in job.script.segments} if job.script else {}
    actual: dict[str, str] = {}
    ordered_ids: list[str] = []
    for segment in alignment.segments:
        actual[segment.segment_id] = actual.get(segment.segment_id, "") + normalized(segment.text)
        if not ordered_ids or ordered_ids[-1] != segment.segment_id:
            ordered_ids.append(segment.segment_id)
    if expected != actual or ordered_ids != list(expected):
        issues.append("实测字幕必须按顺序完整匹配文案的段落 ID 和旁白正文；修改文案后需要重新对齐")
    if alignment.segments[0].start_ms > 1500 or duration * 1000 - alignment.segments[-1].end_ms > 2000:
        issues.append("音频头尾存在超过容差的未覆盖区间，请核验音频或对齐")
    return issues


def from_byte_sentences(job: Job, audio_hash: str, sentences: list[dict]) -> Alignment | None:
    if not job.script:
        return None
    words = []
    for sentence in sentences:
        for word in sentence.get("words", []):
            if not word.get("word") or word.get("startTime") is None or word.get("endTime") is None:
                continue
            if any(type(word[key]) not in (int, float) or not math.isfinite(word[key]) for key in ("startTime", "endTime")):
                return None
            confidence = word.get("confidence")
            if confidence is not None and (type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
                return None
            words.append(word)
    words.sort(key=lambda word: float(word["startTime"]))
    expected = "".join(normalized(segment.narration) for segment in job.script.segments)
    if "".join(normalized(word["word"]) for word in words) != expected:
        return None
    ranges, offset = [], 0
    for segment in job.script.segments:
        offset += len(normalized(segment.narration))
        ranges.append((offset, segment.segment_id))
    result, consumed, index = [], 0, 0
    for word in words:
        size = len(normalized(word["word"]))
        while index < len(ranges) - 1 and consumed >= ranges[index][0]:
            index += 1
        if consumed + size > ranges[index][0] or len(word["word"]) > 72:
            return None
        result.append(AlignmentSegment(segment_id=ranges[index][1], text=word["word"],
                                       start_ms=float(word["startTime"]) * 1000, end_ms=float(word["endTime"]) * 1000))
        consumed += size
    if not result:
        return None
    quality = timestamp_quality(sentences)
    note = "字节返回原文时间戳；已校验正文/段落覆盖、排序与不重叠，AudioGate 继续校验音频 hash 与实测时长。不是独立识别或人工听审。"
    if quality["low_confidence_count"]:
        note += f" {quality['low_confidence_count']} 个词的时间戳置信度低于 0.8，最低 {quality['minimum_confidence']:.3f}；同步需人工听审。"
    return Alignment(origin="provider", verified=True, audio_sha256=audio_hash, segments=result, note=note)


def timestamp_quality(sentences: list[dict]) -> dict[str, Any]:
    """保留供应商置信度的质量信息；0.8 是提醒线，不是官方合格线。

    官方：https://docs.volcengine.com/docs/6561/1329505 的 TTS2.0 示例包含低置信度。
    不将返回文本覆盖等同于独立听审，也不估算或改动任何时间。
    """
    values = [{"text": word.get("word"), "start_seconds": word.get("startTime"),
               "end_seconds": word.get("endTime"), "confidence": word.get("confidence")}
              for sentence in sentences for word in sentence.get("words", []) if word.get("word")]
    confidences = [word["confidence"] for word in values
                   if type(word["confidence"]) in (int, float) and math.isfinite(word["confidence"]) and 0 <= word["confidence"] <= 1]
    low = [word for word in values if type(word["confidence"]) in (int, float)
           and math.isfinite(word["confidence"]) and 0 <= word["confidence"] < 0.8]
    return {"origin": "provider", "word_timestamps": values, "low_confidence_count": len(low),
            "minimum_confidence": min(confidences) if confidences else None,
            "independent_audio_recognition": False, "human_listening_confirmed": False}


@dataclass(frozen=True)
class SegmentAudio:
    segment_id: str
    path: Path
    duration_seconds: float
    words: list[dict[str, Any]]
    pause_after_ms: int
    operation: dict[str, Any] = field(default_factory=dict)
    acoustic_end_seconds: float | None = None


@dataclass(frozen=True)
class SegmentClip:
    segment_id: str
    path: Path
    trim_start_seconds: float
    trim_end_seconds: float
    acoustic_end_seconds: float
    provider_end_seconds: float
    adjusted_words: list[dict[str, Any]]
    requested_pause_after_seconds: float
    inserted_pause_after_seconds: float


def validate_segment_performances(job: Job, values: list[VoiceSegmentPerformance]) -> list[VoiceSegmentPerformance]:
    expected = [segment.segment_id for segment in job.script.segments] if job.script else []
    actual = [item.segment_id for item in values]
    if not expected or actual != expected:
        raise ValueError("逐段表演计划必须按顺序完整匹配文案段落 ID")
    if values[-1].pause_after_ms:
        raise ValueError("逐段表演计划最后一段的 pause_after_ms 必须为 0")
    return values


def _checked_segment_words(segment: SegmentAudio) -> list[dict[str, Any]]:
    if not math.isfinite(segment.duration_seconds) or not 0 < segment.duration_seconds <= 1800:
        raise ValueError("逐段配音时长无效")
    result: list[dict[str, Any]] = []
    previous_end = 0.0
    for word in segment.words:
        text = word.get("word")
        start, end = word.get("startTime"), word.get("endTime")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("逐段配音缺少供应商原文时间戳")
        if type(start) not in (int, float) or type(end) not in (int, float):
            raise ValueError("逐段配音时间戳格式无效")
        start, end = float(start), float(end)
        if not math.isfinite(start) or not math.isfinite(end) or start < previous_end or end <= start:
            raise ValueError("逐段配音时间戳必须有序且不重叠")
        if end > segment.duration_seconds + 0.08:
            raise ValueError("逐段配音时间戳超出实测音频时长")
        confidence = word.get("confidence")
        if confidence is not None and (
            type(confidence) not in (int, float)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            raise ValueError("逐段配音时间戳置信度无效")
        result.append({**word, "startTime": start, "endTime": end})
        previous_end = end
    if not result:
        raise ValueError("逐段配音没有可用的供应商原文时间戳")
    return result


def _probe_acoustic_end(segment: SegmentAudio, executable: str) -> float:
    """Find the real tail after the provider's last alignment boundary."""

    provider_end = _checked_segment_words(segment)[-1]["endTime"]
    analysis_start = max(0.0, provider_end - 0.05)
    analysis_duration = min(segment.duration_seconds - analysis_start, 3.05)
    command = [
        executable, "-v", "error", "-nostdin",
        "-ss", f"{analysis_start:.6f}", "-i", str(segment.path),
        "-t", f"{analysis_duration:.6f}", "-map", "0:a:0", "-vn",
        "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1",
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return min(segment.duration_seconds, provider_end + 0.65)
    if result.returncode or len(result.stdout) < 2:
        return min(segment.duration_seconds, provider_end + 0.65)
    samples = array.array("h")
    samples.frombytes(result.stdout[:len(result.stdout) // 2 * 2])
    if sys.byteorder == "big":
        samples.byteswap()
    window_size = 160
    threshold = 260  # Approximately -42 dBFS, matching the production waveform probe.
    last_active_sample = -1
    for offset in range(0, len(samples), window_size):
        window = samples[offset:offset + window_size]
        if window and sum(value * value for value in window) >= threshold * threshold * len(window):
            last_active_sample = offset + len(window)
    if last_active_sample < 0:
        return min(segment.duration_seconds, provider_end + 0.65)
    detected = analysis_start + last_active_sample / 16000
    return min(segment.duration_seconds, max(provider_end, detected))


def segment_clips(segments: list[SegmentAudio]) -> list[SegmentClip]:
    if not segments:
        raise ValueError("逐段配音不能为空")
    checked = [_checked_segment_words(segment) for segment in segments]
    starts = [words[0]["startTime"] for words in checked]
    ends = [words[-1]["endTime"] for words in checked]
    trim_starts, trim_ends = [], []
    for index, segment in enumerate(segments):
        if not 0 <= segment.pause_after_ms <= 1200:
            raise ValueError("逐段配音停顿必须在 0 到 1200 毫秒之间")
        acoustic_end = segment.acoustic_end_seconds
        if acoustic_end is None:
            acoustic_end = ends[index]
        if not math.isfinite(acoustic_end) or not ends[index] <= acoustic_end <= segment.duration_seconds:
            raise ValueError("逐段配音声学尾点无效")
        lead = min(0.1, starts[index])
        if index:
            previous_target = segments[index - 1].pause_after_ms / 1000
            lead = min(0.15, previous_target / 2, starts[index])
        tail = min(0.1, segment.duration_seconds - acoustic_end)
        if index < len(segments) - 1:
            target = segment.pause_after_ms / 1000
            # Keep at least 60 ms of release after measured speech. It counts
            # toward the requested pause instead of extending it twice.
            tail = min(0.15, max(0.06, target / 2), segment.duration_seconds - acoustic_end)
        trim_starts.append(starts[index] - lead)
        trim_ends.append(acoustic_end + tail)
    clips: list[SegmentClip] = []
    cursor = 0.0
    for index, (segment, words) in enumerate(zip(segments, checked, strict=True)):
        adjusted = [
            {
                **word,
                "startTime": cursor + word["startTime"] - trim_starts[index],
                "endTime": cursor + word["endTime"] - trim_starts[index],
            }
            for word in words
        ]
        requested = segment.pause_after_ms / 1000
        inserted = 0.0
        if index < len(segments) - 1:
            acoustic_end = segment.acoustic_end_seconds or ends[index]
            preserved_tail = trim_ends[index] - acoustic_end
            preserved_lead = starts[index + 1] - trim_starts[index + 1]
            remaining = requested - preserved_tail - preserved_lead
            # Adding and subtracting measured floating-point timestamps can
            # leave a tiny positive remainder even when the requested pause is
            # already fully represented by the retained tail and next lead.
            # Formatting that remainder to six decimals yields duration=0,
            # which FFmpeg treats as an unbounded anullsrc.  A pause shorter
            # than one output sample is not representable, so drop it.
            inserted = remaining if remaining >= 1 / VOICE_SAMPLE_RATE else 0.0
        clips.append(SegmentClip(
            segment_id=segment.segment_id,
            path=segment.path,
            trim_start_seconds=trim_starts[index],
            trim_end_seconds=trim_ends[index],
            acoustic_end_seconds=segment.acoustic_end_seconds or ends[index],
            provider_end_seconds=ends[index],
            adjusted_words=adjusted,
            requested_pause_after_seconds=requested,
            inserted_pause_after_seconds=inserted,
        ))
        cursor += trim_ends[index] - trim_starts[index] + inserted
    return clips


def _execute_ffmpeg(command: list[str], cancelled) -> None:
    job = WindowsJob()
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
    except BaseException:
        job.close()
        raise
    try:
        job.assign(process)
        deadline = time.monotonic() + 180
        while process.poll() is None:
            if cancelled():
                raise RenderCancelled("任务已取消")
            if time.monotonic() > deadline:
                raise ValueError("逐段配音拼接超过时间上限")
            time.sleep(0.05)
        if process.returncode:
            raise ValueError("逐段配音裁剪、响度归一化或拼接失败")
    finally:
        terminate_tree(process)
        job.close()


def _ffmpeg_supports_filter(executable: str, filter_name: str) -> bool:
    """Feature-detect optional filters instead of assuming a recent FFmpeg."""

    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-filters"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=15,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode:
        return False
    output = result.stdout + "\n" + result.stderr
    return any(
        len(parts := line.split()) >= 2 and parts[1] == filter_name
        for line in output.splitlines()
    )


def stitch_segment_audio(segments: list[SegmentAudio], output: Path, cancelled) -> list[SegmentClip]:
    if cancelled():
        raise RenderCancelled("任务已取消")
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("ffmpeg 未安装，无法拼接逐段配音")
    measured = []
    for segment in segments:
        if cancelled():
            raise RenderCancelled("任务已取消")
        measured.append(replace(
            segment,
            acoustic_end_seconds=_probe_acoustic_end(segment, executable),
        ))
    clips = segment_clips(measured)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.stem}-{uuid.uuid4().hex}.tmp.mp3")
    labels, filters = [], []
    for index, clip in enumerate(clips):
        filters.append(
            f"[{index}:a]atrim=start={clip.trim_start_seconds:.6f}:end={clip.trim_end_seconds:.6f},"
            f"asetpts=PTS-STARTPTS,aresample=24000,"
            f"aformat=sample_rates=24000:sample_fmts=fltp:channel_layouts=mono[s{index}]"
        )
        labels.append(f"[s{index}]")
        if clip.inserted_pause_after_seconds:
            filters.append(
                f"anullsrc=r=24000:cl=mono,atrim=duration={clip.inserted_pause_after_seconds:.6f},"
                f"asetpts=PTS-STARTPTS[p{index}]"
            )
            labels.append(f"[p{index}]")
    output_label = labels[0]
    if len(labels) > 1:
        output_label = "[joined]"
        filters.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1{output_label}")
    # loudnorm was added after some still-supported FFmpeg builds. The source
    # clips are already provider-level audio, so absence of this optional
    # normalization must not make the narration fail or invite manual trimming.
    if _ffmpeg_supports_filter(executable, "loudnorm"):
        filters.append(f"{output_label}loudnorm=I=-16:LRA=11:TP=-1.5[out]")
        output_label = "[out]"
    command = [executable, "-v", "error", "-nostdin", "-y"]
    for clip in clips:
        command.extend(["-i", str(clip.path)])
    command.extend([
        "-filter_complex", ";".join(filters),
        "-map", output_label, "-ar", "24000", "-ac", "1",
        "-codec:a", "libmp3lame", "-b:a", "128k", str(temporary),
    ])
    try:
        _execute_ffmpeg(command, cancelled)
        if not temporary.is_file() or not temporary.stat().st_size:
            raise ValueError("逐段配音拼接没有生成有效音频")
        temporary.replace(output)
        return clips
    finally:
        temporary.unlink(missing_ok=True)


class VoiceNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "voice", "配音正在核验真实音频与实测时间轴")
        try:
            audio, alignment, duration = self.prepare_audio(job, state.get("resume_command_id", state["run_id"]),
                                                            state["action"] == "voice", state=state)
            self.service.write_json(job, "alignment.json", alignment.model_dump(), "alignment")
            self.service.write_json(job, "audio_report.json", {"audio_sha256": audio.sha256, "duration_seconds": duration,
                                    "origin": self.repo.asset_metadata(audio.asset_id).get("origin"), "alignment_origin": alignment.origin,
                                    "verified": alignment.verified, "verification_note": alignment.note,
                                    "timestamp_quality": self.repo.asset_metadata(audio.asset_id).get("timestamp_quality")}, "audio_report")
            return state_context(self.repo, state, route="audio_gate",
                                 audio_asset_id=audio.asset_id, alignment=alignment.model_dump(),
                                 duration_seconds=duration, gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "voice", [str(exc)], getattr(exc, "fields", ["audio", "alignment"]), exc)

    def prepare_audio(self, job: Job, command_id: str = "", prefer_generation: bool = False,
                      state: VideoState | None = None) -> tuple[Asset, Alignment, float]:
        if not job.script:
            raise ValueError("请先完成旁白文案再生成配音")
        script_hash = fingerprint([{"segment_id": item.segment_id, "narration": item.narration} for item in job.script.segments])
        audio = None
        selected = self.repo.active_audio(job.job_id)
        candidates = [asset for asset in reversed(job.assets) if asset.role == "audio" and (not selected or asset.asset_id == selected)]
        delivery_style = ""
        performances: list[VoiceSegmentPerformance] = []
        if self.model.available("voice"):
            value = self.model.invoke(agent_state(self.repo, job, state), "voice", PROMPT,
                fields=("brief", "script", "settings"), command_id=command_id,
                output_schema=VoiceAdvice.model_json_schema())
            advice = VoiceAdvice.model_validate(value)
            self.service.write_json(job, "voice_guidance.json", advice.model_dump(), "voice_guidance")
            blocked = [item.message for item in advice.findings if item.blocking or item.severity == "error"]
            if blocked:
                raise ValueError("配音模型预检未通过：" + "；".join(blocked))
            delivery_style = "\n".join(advice.delivery_notes)[:2000]
            if advice.segment_performances:
                performances = validate_segment_performances(job, advice.segment_performances)
        # Guidance can take long enough for settings to change. Filter existing
        # audio with the configuration at selection, then attach generated audio
        # with the provider's actual request fingerprint.
        settings = SettingsService(self.repo).internal()
        voice_hash = voice_fingerprint(settings)
        if not (prefer_generation and SettingsService(self.repo).public()["voice_configured"]):
            for candidate in candidates:
                metadata = self.repo.asset_metadata(candidate.asset_id)
                if metadata.get("origin") in {"byte_http", "byte_ws"} and (metadata.get("script_fingerprint") != script_hash or metadata.get("voice_fingerprint") != voice_hash):
                    continue
                audio = candidate
                break
        if audio:
            path, _, _ = self.repo.artifact_path(audio.artifact_id)
            duration = audio_duration(path)
            metadata = self.repo.asset_metadata(audio.asset_id)
            if metadata.get("alignment"):
                alignment = Alignment.model_validate(metadata["alignment"])
            else:
                alignment = align(self.repo, path, audio.sha256, [segment.model_dump() for segment in job.script.segments])
                metadata["alignment"] = alignment.model_dump()
                self.repo.update_asset_metadata(audio.asset_id, metadata)
            return audio, alignment, duration
        def cancelled():
            return self.repo.get_job(job.job_id).status == "CANCELLED"

        if performances and supports_voice_style(settings):
            return self.prepare_segmented_audio(
                job, command_id, script_hash, voice_hash, performances, cancelled
            )
        text = "\n".join(segment.narration for segment in job.script.segments)
        options: dict[str, Any] = {"cancelled": cancelled}
        # 已有同配置音频照常复用；只有实际新合成才附加指导，用户风格由供应商配置快照优先合并。
        if delivery_style and supports_voice_style(settings):
            options["delivery_style"] = delivery_style
        value = synthesize(self.repo, job.job_id, job.revision, text, command_id, **options)
        path = Path(value["path"])
        duration = audio_duration(path)
        artifact = self.service.register_artifact(job, path, "voice", "audio/mpeg", "narration.mp3")
        asset_id = uuid.uuid4().hex
        audio = Asset(asset_id=asset_id, name="字节复刻配音.mp3", role="audio", mime_type="audio/mpeg",
                      size_bytes=artifact.size_bytes, sha256=artifact.sha256, source_url="",
                      license_note="用户配置的自有复刻音色；最终需核验内容完整性", artifact_id=artifact.artifact_id,
                      url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/{asset_id}.mp3")
        alignment = from_byte_sentences(job, audio.sha256, value.get("sentences", []))
        metadata = {"origin": value.get("origin", "byte_http"), "duration_seconds": duration,
                    "script_fingerprint": script_hash, "voice_fingerprint": value.get("voice_fingerprint", voice_hash),
                    "timestamp_quality": timestamp_quality(value.get("sentences", []))}
        metadata.update({key: value[key] for key in ("voice_model", "voice_style", "voice_speech_rate") if key in value})
        if alignment:
            metadata["alignment"] = alignment.model_dump()
        self.service.freeze_asset(audio)
        self.repo.attach_generated_audio(job.job_id, job.revision, audio, artifact, metadata)
        if not alignment:
            alignment = align(self.repo, path, audio.sha256, [segment.model_dump() for segment in job.script.segments])
            metadata["alignment"] = alignment.model_dump()
            self.repo.update_asset_metadata(asset_id, metadata)
        return audio, alignment, duration

    def prepare_segmented_audio(
        self,
        job: Job,
        command_id: str,
        script_hash: str,
        voice_hash: str,
        performances: list[VoiceSegmentPerformance],
        cancelled,
    ) -> tuple[Asset, Alignment, float]:
        segments: list[SegmentAudio] = []
        operations: list[dict[str, Any]] = []
        for script_segment, performance in zip(job.script.segments, performances, strict=True):
            value = synthesize(
                self.repo,
                job.job_id,
                job.revision,
                script_segment.narration,
                command_id + f":segment:{script_segment.segment_id}",
                cancelled=cancelled,
                delivery_style=performance.delivery_style,
                operation_key=f"script-segment:{script_segment.segment_id}",
            )
            path = Path(value["path"])
            duration = audio_duration(path)
            words = [
                word
                for sentence in value.get("sentences", [])
                for word in sentence.get("words", [])
            ]
            if "".join(normalized(word.get("word", "")) for word in words) != normalized(script_segment.narration):
                raise ValueError(f"逐段配音 {script_segment.segment_id} 的供应商时间戳未完整覆盖原文")
            operation = {"segment_id": script_segment.segment_id}
            for key in (
                "operation_id",
                "request_id",
                "input_hash",
                "origin",
                "voice_fingerprint",
                "voice_model",
                "voice_speech_rate",
            ):
                if key in value:
                    operation[key] = value[key]
            operation["delivery_style_fingerprint"] = fingerprint(performance.delivery_style)
            operations.append(operation)
            segments.append(SegmentAudio(
                segment_id=script_segment.segment_id,
                path=path,
                duration_seconds=duration,
                words=words,
                pause_after_ms=performance.pause_after_ms,
                operation=operation,
            ))
        folder = self.repo.root / "jobs" / job.job_id / "operations"
        output = folder / f"segmented-voice-{uuid.uuid4().hex}.mp3"
        clips = stitch_segment_audio(segments, output, cancelled)
        duration = audio_duration(output)
        artifact = self.service.register_artifact(job, output, "voice", "audio/mpeg", "narration.mp3")
        asset_id = uuid.uuid4().hex
        audio = Asset(
            asset_id=asset_id,
            name="字节复刻分段配音.mp3",
            role="audio",
            mime_type="audio/mpeg",
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
            source_url="",
            license_note="用户配置的自有复刻音色；逐段表演并拼接，最终需人工听审",
            artifact_id=artifact.artifact_id,
            url=artifact.url,
            timeline_src=f"videoagents/{job.job_id}/assets/{asset_id}.mp3",
        )
        adjusted_words = [word for clip in clips for word in clip.adjusted_words]
        sentences = [{"words": adjusted_words}]
        alignment = from_byte_sentences(job, audio.sha256, sentences)
        if not alignment:
            raise ValueError("逐段配音拼接后的供应商时间戳未完整覆盖文案")
        alignment.note += " 逐段供应商时间戳已按实测裁剪区间和插入静音作确定性偏移；未对音频变速。"
        used_fingerprint = next(
            (
                value
                for segment in segments
                if (value := segment.operation.get("voice_fingerprint"))
            ),
            voice_hash,
        )
        used_model = next(
            (value for segment in segments if (value := segment.operation.get("voice_model"))),
            None,
        )
        used_rate = next(
            (value for segment in segments if (value := segment.operation.get("voice_speech_rate")) is not None),
            None,
        )
        metadata = {
            "origin": "byte_ws",
            "duration_seconds": duration,
            "script_fingerprint": script_hash,
            "voice_fingerprint": used_fingerprint,
            "voice_model": used_model,
            "voice_speech_rate": used_rate,
            "timestamp_quality": timestamp_quality(sentences),
            "alignment": alignment.model_dump(),
            "segmented": True,
            "segment_operations": operations,
            "segment_stitch": [
                {
                    "segment_id": clip.segment_id,
                    "trim_start_ms": round(clip.trim_start_seconds * 1000, 3),
                    "trim_end_ms": round(clip.trim_end_seconds * 1000, 3),
                    "provider_end_ms": round(clip.provider_end_seconds * 1000, 3),
                    "acoustic_end_ms": round(clip.acoustic_end_seconds * 1000, 3),
                    "retained_acoustic_tail_ms": round(
                        (clip.acoustic_end_seconds - clip.provider_end_seconds) * 1000,
                        3,
                    ),
                    "requested_pause_after_ms": round(clip.requested_pause_after_seconds * 1000),
                    "inserted_pause_after_ms": round(clip.inserted_pause_after_seconds * 1000, 3),
                }
                for clip in clips
            ],
        }
        self.service.freeze_asset(audio)
        self.repo.attach_generated_audio(job.job_id, job.revision, audio, artifact, metadata)
        return audio, alignment, duration
