"""Versioned draft editing and manual, real media ingestion."""

import json
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from videoagents.contracts import Alignment, Artifact, Asset, DraftRequest, Job
from videoagents.default_config import PROJECT_ROOT
from videoagents.storage import Repository
from videoagents.tools.media import audio_duration, detect_media, probe, sha256
from videoagents.tools.timeline import validate_timeline

INVALIDATED = {"preview", "final", "cover", "timeline", "review", "package", "captions", "storyboard", "script_discussion"}


class JobService:
    def __init__(self, repository: Repository, project_root: Path = PROJECT_ROOT):
        self.repo = repository
        self.project_root = project_root

    def draft(self, job_id: str, request: DraftRequest) -> Job:
        if request.brief is None and request.script is None and request.timeline is None:
            raise ValueError("草稿更新内容不能为空")
        def edit(job: Job) -> Job:
            new_revision = job.revision + 1
            if request.brief:
                brief_changed = request.brief.script_text != job.brief.script_text or request.brief.topic != job.brief.topic
                if not request.brief.topic.strip() and not request.brief.script_text.strip():
                    raise ValueError("主题和文案不能同时为空")
                if brief_changed:
                    job.script = None
                job.brief = request.brief
            if request.script:
                for segment in request.script.segments:
                    if not set(segment.asset_ids) <= {asset.asset_id for asset in job.assets}:
                        raise ValueError("文案包含不属于此任务的素材")
                job.script = request.script.model_copy(update={"revision": new_revision})
            if request.timeline:
                validate_timeline(request.timeline, job)
                job.timeline = request.timeline.model_copy(update={"revision": new_revision})
            else:
                job.timeline = None
            if job.script:
                job.script.revision = new_revision
            job.revision = new_revision
            job.script_discussion = None
            job.review, job.pending_input, job.progress = None, None, None
            invalidated = INVALIDATED | ({"research", "source"} if request.brief and brief_changed else set())
            job.artifacts = [item for item in job.artifacts if item.kind not in invalidated]
            job.status, job.stage, job.message = "DRAFT", "idle", "新版草稿已保存，下游渲染与审核已失效"
            return job
        return self.repo.edit_job(job_id, request.base_revision, edit)

    def register_artifact(self, job: Job, path: Path, kind: str, mime_type: str, name: str | None = None) -> Artifact:
        artifact_id = uuid.uuid4().hex
        artifact = Artifact(artifact_id=artifact_id, kind=kind, name=name or path.name, mime_type=mime_type,
                            size_bytes=path.stat().st_size, sha256=sha256(path), url=f"/api/artifacts/{artifact_id}", revision=job.revision)
        self.repo.put_artifact(job.job_id, artifact, path)
        return artifact

    def append_artifact(self, job_id: str, artifact: Artifact, expected_revision: int) -> Job:
        job = self.repo.get_job(job_id)
        artifacts = [item for item in job.artifacts if item.kind != artifact.kind] + [artifact]
        return self.repo.update_job(job_id, expected_revision, artifacts=artifacts)

    def upload(self, job_id: str, data: bytes, name: str, role: str, source_url: str = "", license_note: str = "", alignment: dict | None = None) -> Asset:
        job = self.repo.get_job(job_id)
        if role not in {"evidence", "illustration", "decoration", "audio"}:
            raise ValueError("素材用途无效")
        if len(data) > 100 * 1024 * 1024 or not data:
            raise ValueError("素材为空或超过 100 MiB")
        if len(license_note) > 3000 or len(source_url) > 3000:
            raise ValueError("素材来源或许可说明过长")
        if source_url:
            parsed = urlparse(source_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("素材来源必须是无凭据的 HTTP/HTTPS URL")
        mime_type, extension = detect_media(data)
        if (role == "audio") != mime_type.startswith("audio/"):
            raise ValueError("素材类型与用途不一致")
        asset_id = uuid.uuid4().hex
        folder = self.repo.root / "jobs" / job_id / "assets"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (asset_id + extension)
        path.write_bytes(data)
        metadata: dict[str, Any] = {"origin": "upload"}
        try:
            if role == "audio":
                metadata["duration_seconds"] = audio_duration(path)
                if alignment:
                    if alignment.get("audio_sha256") and alignment["audio_sha256"] != sha256(path):
                        raise ValueError("提交的 alignment 音频 hash 与上传文件不匹配")
                    alignment = dict(alignment, audio_sha256=sha256(path))
                    checked = Alignment.model_validate(alignment)
                    if checked.segments[-1].end_ms > metadata["duration_seconds"] * 1000 + 80:
                        raise ValueError("对齐时间超出音频实测时长")
                    metadata["alignment"] = checked.model_dump()
            else:
                info = probe(path)
                stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "video"), None)
                if not stream or stream.get("width", 0) < 32 or stream.get("height", 0) < 32 or stream.get("width", 0) * stream.get("height", 0) > 40_000_000:
                    raise ValueError("图片无法解码、过小或分辨率超过限制")
                metadata.update(width=stream["width"], height=stream["height"])
            artifact = self.register_artifact(job.model_copy(update={"revision": job.revision + 1}), path, "audio_import" if role == "audio" else "asset", mime_type, Path(name).name[:200])
            timeline_src = f"videoagents/{job_id}/assets/{asset_id}{extension}"
            asset = Asset(asset_id=asset_id, name=Path(name).name[:200], role=role, mime_type=mime_type,
                          size_bytes=artifact.size_bytes, sha256=artifact.sha256, source_url=source_url,
                          license_note=license_note, artifact_id=artifact.artifact_id, url=artifact.url, timeline_src=timeline_src)
            self.freeze_asset(asset)
            self.repo.add_asset(job_id, asset, artifact, metadata)
            return asset
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def freeze_asset(self, asset: Asset) -> Path:
        original, artifact, _ = self.repo.artifact_path(asset.artifact_id)
        if sha256(original) != asset.sha256:
            raise ValueError("素材文件 hash 改变，不能继续使用旧审核")
        target = (self.project_root / "public" / asset.timeline_src).resolve()
        public = (self.project_root / "public" / "videoagents").resolve()
        if not target.is_relative_to(public):
            raise ValueError("素材路径越界")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        if sha256(target) != artifact.sha256:
            raise ValueError("冻结素材校验失败")
        return target

    def set_alignment(self, job_id: str, base_revision: int, asset_id: str, alignment: dict[str, Any]) -> Job:
        job = self.repo.get_job(job_id)
        asset = next((item for item in job.assets if item.asset_id == asset_id and item.role == "audio"), None)
        if not asset:
            raise ValueError("请指定此任务的音频素材")
        if alignment.get("audio_sha256") and alignment["audio_sha256"] != asset.sha256:
            raise ValueError("提交的 alignment 音频 hash 与当前素材不匹配")
        checked = Alignment.model_validate(dict(alignment, audio_sha256=asset.sha256))
        metadata = self.repo.asset_metadata(asset_id)
        if checked.segments[-1].end_ms > metadata.get("duration_seconds", 0) * 1000 + 80:
            raise ValueError("对齐超出实测音频时长")
        def edit(current: Job) -> Job:
            current.revision += 1
            current.script_discussion = None
            if current.script:
                current.script.revision = current.revision
            current.timeline, current.review, current.pending_input = None, None, None
            current.artifacts = [item for item in current.artifacts if item.kind not in INVALIDATED]
            current.status, current.stage, current.message = "DRAFT", "voice", "已保存实测音频对齐，旧分镜和审核已失效"
            return current
        metadata["alignment"] = checked.model_dump()
        return self.repo.set_alignment(job_id, base_revision, asset_id, metadata, edit)

    def write_json(self, job: Job, filename: str, value: Any, kind: str) -> Artifact:
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / filename
        # Different versions of a render/review in the same revision must stay immutable.
        if path.exists():
            path = folder / f"{Path(filename).stem}-{uuid.uuid4().hex[:8]}{Path(filename).suffix}"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        artifact = self.register_artifact(job, path, kind, "application/json")
        self.append_artifact(job.job_id, artifact, job.revision)
        return artifact
