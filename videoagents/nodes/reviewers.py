"""Review binds exact inputs and bytes; human review cannot waive hard failures."""

from typing import Any

from videoagents.contracts import Alignment, ContentReviewAdvice, Finding, Job, Review
from videoagents.nodes.common import agent_state, request_input, start_stage, state_context
from videoagents.nodes.screenwriter import script_issues
from videoagents.nodes.voice import validate_alignment
from videoagents.prompts import compose
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.media import audio_duration, decode_check, probe, sha256
from videoagents.tools.timeline import validate_timeline

PROMPT = compose("shared-style", "review")


def dependency_fingerprint(job: Job) -> str:
    return fingerprint({"revision": job.revision, "brief": job.brief.model_dump(),
                        "script": job.script.model_dump() if job.script else None,
                        "timeline": job.timeline.model_dump() if job.timeline else None,
                        "assets": [item.model_dump() for item in job.assets]})


class ReviewersNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "review", "审核正在检查最终视频、来源、时长与素材用途")
        try:
            review = self.review(job, state=state)
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "review", [str(exc)], getattr(exc, "fields", ["review"]), exc)
        job = self.repo.update_job(job.job_id, job.revision, review=review)
        self.service.write_json(job, "review.json", review.model_dump(), "review")
        return state_context(self.repo, state, route="review_gate", gate_issues=[])

    def review(self, job: Job, *, human_confirmed: bool = False, model_review: bool = True,
               state: VideoState | None = None) -> Review:
        findings = []
        coverage = ["media_probe", "full_decode", "timeline_contract", "source_structure", "audio_alignment", "usage_and_license"]
        context = agent_state(self.repo, job, state)

        def add(category: str, message: str, owner: str, severity: str = "error", blocking: bool = True):
            findings.append(Finding(finding_id=f"{category}-{len(findings) + 1}", severity=severity,
                                    category=category, message=message, owner=owner, blocking=blocking))

        for issue in script_issues(job, context.get("research")):
            add("source", issue, "screenwriter")
        if job.brief.usage == "unspecified":
            add("usage", "请明确个人/商业用途后再申请发布审核", "user")
        if not job.brief.platform.strip() or job.brief.platform == "通用竖屏":
            add("platform", "请明确实际目标发布平台，通用竖屏设置只能用于预览", "user")
        if not job.timeline:
            add("timeline", "没有最终分镜", "director")
        else:
            try:
                metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
                validate_timeline(job.timeline, job, metadata)
            except ValueError as exc:
                add("timeline", str(exc), "director")
            used = {shot.asset_src for shot in job.timeline.shots if shot.asset_src}
            used.add(job.timeline.audio_src)
            for asset in job.assets:
                if asset.timeline_src in used:
                    try:
                        path, _, _ = self.repo.artifact_path(asset.artifact_id)
                        if sha256(path) != asset.sha256:
                            add("asset_hash", f"素材 {asset.name} 文件已改变", "editing")
                        frozen = self.service.project_root / "public" / asset.timeline_src
                        if not frozen.is_file() or sha256(frozen) != asset.sha256:
                            add("asset_hash", f"渲染素材 {asset.name} 与已审输入不一致", "editing")
                    except (ValueError, OSError):
                        add("asset", f"素材 {asset.name} 文件缺失", "editing")
                    if not asset.license_note.strip():
                        add("rights", f"素材 {asset.name} 未提供许可或自有说明", "user")
            audio = next((asset for asset in job.assets if asset.timeline_src == job.timeline.audio_src), None)
            if not audio:
                add("audio", "最终时间轴缺少真实旁白音频", "voice")
            else:
                try:
                    path, _, _ = self.repo.artifact_path(audio.artifact_id)
                    duration = audio_duration(path)
                    metadata = self.repo.asset_metadata(audio.asset_id)
                    alignment = Alignment.model_validate(metadata.get("alignment", {}))
                    quality = metadata.get("timestamp_quality", {})
                    if quality.get("low_confidence_count"):
                        add("timestamp_confidence", f"供应商返回的 {quality['low_confidence_count']} 个词时间戳置信度低于 0.8；"
                            "已校验全文覆盖与时间范围，但同步精度仍需完整播放人工听审", "user", "warning", False)
                    for issue in validate_alignment(job, audio, alignment, duration):
                        add("alignment", issue, "voice")
                    actual_captions = [(c.text, c.start_ms, c.end_ms) for c in job.timeline.captions]
                    expected_captions = [(c.text, c.start_ms, c.end_ms) for c in alignment.segments]
                    if actual_captions != expected_captions:
                        add("alignment", "分镜字幕不匹配当前实测对齐", "director")
                    timeline_duration = job.timeline.duration_in_frames / job.timeline.fps
                    if abs(timeline_duration - duration) > max(0.1, 1 / job.timeline.fps):
                        add("duration", "分镜时长与实测音频不符", "director")
                    if abs(duration - job.brief.target_seconds) > max(2, job.brief.target_seconds * 0.25):
                        add("duration", "实际旁白时长偏离目标超过 25%；请修改目标时长或重配音", "voice")
                except Exception as exc:
                    add("audio", "音频/对齐检查失败：" + str(exc)[:400], "voice")
        final = next((item for item in reversed(job.artifacts) if item.kind == "final" and item.revision == job.revision), None)
        media_hash = None
        if not final:
            add("final", "缺少当前版本的最终 MP4，预览不能作为发布成片", "editing")
        else:
            try:
                binding = self.repo.artifact_metadata(final.artifact_id)
                if binding.get("dependency_fingerprint") != dependency_fingerprint(job):
                    add("render_binding", "最终成片的输入绑定与当前文案/音频/分镜/用途不同，必须重新渲染", "editing")
                path, _, _ = self.repo.artifact_path(final.artifact_id)
                media_hash = sha256(path)
                if media_hash != final.sha256:
                    add("media_hash", "最终视频文件已改变，旧产物记录无效", "editing")
                info = probe(path)
                video = next((item for item in info.get("streams", []) if item.get("codec_type") == "video"), None)
                audio_stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "audio"), None)
                if not video or not audio_stream:
                    add("media", "最终视频必须同时含画面与音轨", "editing")
                if video and job.timeline:
                    ratio = video.get("avg_frame_rate", "0/1").split("/")
                    fps = float(ratio[0]) / (float(ratio[1]) or 1)
                    if (video.get("width"), video.get("height")) != (job.brief.width, job.brief.height) or abs(fps - job.brief.fps) > 0.01:
                        add("media", "最终视频宽高或帧率不符合任务设置", "editing")
                    if abs(float(info.get("format", {}).get("duration", 0)) - job.timeline.duration_in_frames / job.timeline.fps) > 0.15:
                        add("media", "最终视频时长与分镜不符", "editing")
                decode_check(path)
            except Exception as exc:
                add("media", "最终视频探测/完整解码失败：" + str(exc)[:400], "editing")
        if model_review and self.model.available("review") and job.script:
            value = self.model.invoke(context, "review", PROMPT,
                fields=("brief", "script", "timeline", "assets", "research", "alignment"),
                command_id=context.get("resume_command_id", context.get("run_id", "")),
                output_schema=ContentReviewAdvice.model_json_schema())
            advice = ContentReviewAdvice.model_validate(value)
            for item in advice.findings:
                add("model_content", item.message, item.owner, item.severity, item.blocking or item.severity == "error")
            coverage.append("model_content_only")
        if not human_confirmed:
            add("human_full_review", "需完整播放成片并核验事实与截图匹配、旁白漏字/错读、字幕、可读性、素材及字体用途；确认说明必须覆盖这些检查", "user", "warning")
        else:
            coverage.extend(["human_full_playback", "human_facts_and_rights", "human_audio_and_layout"])
        hard_errors = any(item.blocking and item.severity == "error" for item in findings)
        return Review(status="REVISE" if hard_errors else "PASS" if human_confirmed else "NEEDS_HUMAN",
                      findings=findings, media_sha256=media_hash, dependency_fingerprint=dependency_fingerprint(job),
                      coverage=coverage, human_confirmed=human_confirmed and not hard_errors)
