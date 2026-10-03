"""Use real imported/Byte audio and verified timestamps, with strict text coverage."""

import uuid

from videoagents.contracts import Alignment, AlignmentSegment, Asset, Job, VoiceAdvice
from videoagents.providers.aligner import align
from videoagents.providers.byte_voice import synthesize
from videoagents.providers.llm import JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService, voice_fingerprint
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.media import audio_duration


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
            if word.get("confidence") is not None and float(word["confidence"]) < 0.8:
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
    return Alignment(origin="provider", verified=True, audio_sha256=audio_hash, segments=result, note="字节接口实测单词时间戳")


class VoiceNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def run(self, job: Job, command_id: str = "", prefer_generation: bool = False) -> tuple[Asset, Alignment, float]:
        script_hash = fingerprint([{"segment_id": item.segment_id, "narration": item.narration} for item in job.script.segments])
        settings = SettingsService(self.repo).internal()
        audio = None
        selected = self.repo.active_audio(job.job_id)
        candidates = [asset for asset in reversed(job.assets) if asset.role == "audio" and (not selected or asset.asset_id == selected)]
        if self.model.available("voice"):
            value = self.model.call(job.job_id, job.revision, "voice",
                "作为配音指导，在实际配音/对齐前检查原文朗读风险、专名和多音字、停顿重音、情绪与受众匹配；给出delivery_notes和pronunciation_notes及findings。"
                "保持旁白原文；建议仅供人工核验，不能改写文案、伪造或修改实测时间戳、声称已听到音频、生成音频、执行代码或请求额外工具。"
                "发现不能继续配音的文案/音色用途问题须blocking=true。",
                {"brief": job.brief.model_dump(), "script": job.script.model_dump(),
                 "voice": {key: settings.get(key) for key in ("voice_provider", "voice_id", "voice_resource_id")}},
                command_id, output_schema=VoiceAdvice.model_json_schema())
            advice = VoiceAdvice.model_validate(value)
            self.service.write_json(job, "voice_guidance.json", advice.model_dump(), "voice_guidance")
            blocked = [item.message for item in advice.findings if item.blocking or item.severity == "error"]
            if blocked:
                raise ValueError("配音模型预检未通过：" + "；".join(blocked))
        # Guidance can take long enough for settings to change. Filter existing
        # audio with the configuration at selection, then attach generated audio
        # with the provider's actual request fingerprint.
        voice_hash = voice_fingerprint(SettingsService(self.repo).internal())
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
        text = "\n".join(segment.narration for segment in job.script.segments)
        value = synthesize(self.repo, job.job_id, job.revision, text, command_id,
                           cancelled=lambda: self.repo.get_job(job.job_id).status == "CANCELLED")
        from pathlib import Path
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
                    "script_fingerprint": script_hash, "voice_fingerprint": value.get("voice_fingerprint", voice_hash)}
        if alignment:
            metadata["alignment"] = alignment.model_dump()
        self.service.freeze_asset(audio)
        self.repo.attach_generated_audio(job.job_id, job.revision, audio, artifact, metadata)
        if not alignment:
            alignment = align(self.repo, path, audio.sha256, [segment.model_dump() for segment in job.script.segments])
            metadata["alignment"] = alignment.model_dump()
            self.repo.update_asset_metadata(asset_id, metadata)
        return audio, alignment, duration
