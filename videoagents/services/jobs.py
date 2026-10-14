"""Versioned draft editing and manual, real media ingestion."""

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from langgraph.checkpoint.sqlite import SqliteSaver

from videoagents.contracts import (
    Alignment,
    Artifact,
    Asset,
    DraftRequest,
    Job,
    ReplenishMaterialsRequest,
    RestartUnknownRequest,
    RetryFailedRunRequest,
)
from videoagents.default_config import PROJECT_ROOT
from videoagents.storage import Conflict, Repository
from videoagents.tools.media import audio_duration, decode_check, detect_media, probe, sha256, video_metadata
from videoagents.tools.timeline import validate_timeline

INVALIDATED = {"preview", "final", "cover", "timeline", "review", "package", "captions",
               "storyboard", "director_plan", "script_discussion", "component_study",
               "director_shot_review", "shot_review_frame"}


class JobService:
    def __init__(self, repository: Repository, project_root: Path = PROJECT_ROOT):
        self.repo = repository
        self.project_root = project_root

    def delete(self, job_id: str, base_revision: int) -> None:
        """Remove only the cancelled job's owned files, checkpoints and records."""
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            raise ValueError("删除任务需要有效的任务 ID")

        def cleanup(job: Job, artifact_paths: list[Path]) -> None:
            roots = (self.repo.root / "jobs", self.project_root.resolve() / "public" / "videoagents")
            folders = tuple(root / job.job_id for root in roots)
            checkpoint = self.repo.root / "checkpoints.sqlite"
            # Validate every target before the first recursive removal. Never follow
            # a job directory, parent directory or artifact redirected elsewhere.
            for root, folder in zip(roots, folders, strict=True):
                if root.resolve() != root or folder.resolve() != folder:
                    raise ValueError("任务目录越界或指向链接，不能删除")
                if folder.exists() and not folder.is_dir():
                    raise ValueError("任务目录不是文件夹，不能删除")
            if any(not path.resolve().is_relative_to(folders[0]) for path in artifact_paths):
                raise ValueError("任务产物不在所属任务目录，不能删除")
            if checkpoint.resolve() != checkpoint:
                raise ValueError("检查点文件指向链接，不能删除")
            try:
                for folder in folders:
                    if folder.exists():
                        shutil.rmtree(folder)
                if checkpoint.exists():
                    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
                        prefix = f"job:{job.job_id}:"
                        with saver.cursor(transaction=False) as cursor:
                            threads = [row[0] for row in cursor.execute(
                                "SELECT thread_id FROM checkpoints WHERE substr(thread_id,1,?)=? "
                                "UNION SELECT thread_id FROM writes WHERE substr(thread_id,1,?)=?",
                                (len(prefix), prefix, len(prefix), prefix),
                            )]
                        for thread_id in threads:
                            saver.delete_thread(thread_id)
            except OSError as exc:
                raise ValueError("任务文件删除失败，任务记录已保留，请排除文件占用后重试") from exc

        self.repo.delete_job(job_id, base_revision, cleanup)


    def retry_failed_run(self, job_id: str, request: RetryFailedRunRequest) -> Job:
        payload = request.model_dump(exclude_none=True)
        payload["action"] = "retry"
        return self.repo.enqueue(job_id, payload)

    def draft(self, job_id: str, request: DraftRequest) -> Job:
        if request.brief is None and request.script is None and request.timeline is None:
            raise ValueError("草稿更新内容不能为空")
        return self.repo.edit_job(job_id, request.base_revision, lambda job: self._edit_draft(job, request))

    def restart_unknown(self, job_id: str, request: RestartUnknownRequest) -> Job:
        request = RestartUnknownRequest.model_validate(request.model_dump())

        def edit(job: Job) -> Job:
            if request.director_only:
                from videoagents.services.director_recovery import retained_director_inputs

                job.artifacts = retained_director_inputs(self.repo, job)
                job.revision += 1
                job.script = job.script.model_copy(update={"revision": job.revision})
                job.timeline = job.script_discussion = job.review = job.pending_input = job.progress = None
                job.status, job.stage = "DRAFT", "idle"
                job.message = "已授权仅重做摄影，保留联合批准与真实音频；旧提交仍 UNKNOWN，请通过 run 执行"
                return job
            if request.materials_only:
                # Keep immutable pre-collection evidence at its original revision.
                # The authorization chain validates it; no new confirm is forged.
                job.revision += 1
                job.script = job.script.model_copy(update={"revision": job.revision})
                job.assets = []
                job.artifacts = [item for item in job.artifacts
                                 if item.kind in {"script", "writer_tool_audit", "source", "stage_review"}]
                job.timeline = job.script_discussion = job.review = job.pending_input = job.progress = None
                job.status, job.stage = "DRAFT", "idle"
                job.message = "已授权仅重采素材，沿用原文案批准依据；旧提交仍 UNKNOWN，请通过 run 执行"
                return job
            # Rebuilding after materials must also discard the completed old script.
            job.script = None
            updated = self._edit_draft(job, DraftRequest(
                base_revision=request.base_revision, brief=request.brief or job.brief,
            ))
            invalidated = {"script"}
            if request.rebuild_script:
                invalidated |= {"research", "source", "material_skill_manifest"}
            updated.artifacts = [item for item in updated.artifacts if item.kind not in invalidated]
            updated.message = "已按明确授权保存新版草稿；旧提交仍为 UNKNOWN，请通过 run 执行"
            return updated

        return self.repo.restart_unknown(job_id, request, edit)

    def replenish_materials(self, job_id: str, request: ReplenishMaterialsRequest) -> Job:
        request = ReplenishMaterialsRequest.model_validate(request.model_dump())

        def edit(job: Job) -> tuple[Job, list[dict], dict, dict]:
            from videoagents.nodes.materials import MaterialsNode
            from videoagents.nodes.script_review import preserve_approved_script

            retained_ids = set(request.retained_asset_ids)
            assets = [item for item in job.assets if item.asset_id in retained_ids]
            if (len(assets) != len(retained_ids) or any(item.role == "audio"
                    or not item.mime_type.startswith(("image/", "video/")) for item in assets)):
                raise Conflict("保留素材必须是当前任务的图片或视频，不能恢复已拒素材")
            preserved = preserve_approved_script(self.repo, job, retained_asset_ids=retained_ids)
            research = MaterialsNode(self.repo, self).saved_json(job, "research")
            if not research:
                raise Conflict("保留素材缺少已冻结的来源与画面绑定")
            visuals = [item for item in research.get("visuals", []) if item.get("asset_id") in retained_ids]
            if {item["asset_id"] for item in visuals} != retained_ids:
                raise Conflict("保留素材缺少原研究画面绑定")
            sources = []
            for source in research.get("sources", []):
                bound = [key for key in source.get("asset_ids", []) if key in retained_ids]
                if bound:
                    sources.append({**source, "asset_ids": bound})
            by_url = {item["url"]: item for item in sources}
            imported = []
            for asset in assets:
                source = by_url.get(asset.source_url)
                visual = next(item for item in visuals if item["asset_id"] == asset.asset_id)
                if (not source or asset.asset_id not in source["asset_ids"]
                        or visual.get("source_url") != asset.source_url
                        or visual.get("artifact_id") != asset.artifact_id):
                    raise Conflict("保留素材与原研究来源不一致")
                path, artifact, owner = self.repo.artifact_path(asset.artifact_id)
                if (owner != job.job_id or sha256(path) != asset.sha256
                        or artifact.sha256 != asset.sha256 or artifact not in job.artifacts):
                    raise Conflict("保留素材的文件或登记信息已改变")
                source_path, source_artifact, source_owner = self.repo.artifact_path(source["artifact_id"])
                if (source_owner != job.job_id or source_artifact not in job.artifacts
                        or source_artifact.kind != "source" or source_artifact.sha256 != source["sha256"]
                        or sha256(source_path) != source["sha256"]):
                    raise Conflict("保留素材对应的冻结来源已改变")
                imported.append({"asset": asset.model_dump(), "artifact": artifact.model_dump(),
                                 "metadata": self.repo.asset_metadata(asset.asset_id)})
            job.revision += 1
            job.script = job.script.model_copy(update={"revision": job.revision})
            job.assets = assets
            artifact_ids = {item.artifact_id for item in assets}
            job.artifacts = [item for item in job.artifacts
                            if item.kind in {"script", "writer_tool_audit", "source", "stage_review"}
                            or item.artifact_id in artifact_ids]
            job.timeline = job.script_discussion = job.review = job.pending_input = job.progress = None
            job.status, job.stage = "DRAFT", "idle"
            job.message = "已授权补采素材并显式导入保留画面；原稿批准依据保留，请通过 run 执行"
            return job, imported, preserved, {"sources": sources, "visuals": visuals}

        return self.repo.replenish_materials(job_id, request, edit)

    def _edit_draft(self, job: Job, request: DraftRequest) -> Job:
        """Apply the existing revision/invalidation rules inside the caller's transaction."""
        new_revision = job.revision + 1
        if request.brief:
            brief_changed = (request.brief.creative_direction != job.brief.creative_direction
                             or request.brief.script_text != job.brief.script_text
                             or request.brief.topic != job.brief.topic)
            if not (request.brief.topic.strip() or request.brief.creative_direction.strip()
                    or request.brief.script_text.strip()):
                raise ValueError("主题和创作方向不能同时为空")
            if brief_changed:
                job.script = None
            job.brief = request.brief
        if request.script:
            for segment in request.script.segments:
                if not set(segment.asset_ids) <= {asset.asset_id for asset in job.assets}:
                    raise ValueError("文案包含不属于此任务的素材")
            job.script = request.script.model_copy(update={"revision": new_revision})
        if request.timeline:
            metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
            timeline = request.timeline
            if any(shot.set_design for shot in timeline.shots):
                from videoagents.tools.component_sets import resolve_component_set_shots

                timeline = timeline.model_copy(update={
                    "shots": resolve_component_set_shots(timeline.shots, job.assets, metadata),
                })
            validate_timeline(timeline, job, metadata)
            job.timeline = timeline.model_copy(update={"revision": new_revision})
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
        asset_id = uuid.uuid4().hex
        folder = self.repo.root / "jobs" / job_id / "assets"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / (asset_id + ".upload")
        path.write_bytes(data)
        metadata: dict[str, Any] = {"origin": "upload"}
        try:
            mime_type, extension = detect_media(data, path)
            final_path = folder / (asset_id + extension)
            path.replace(final_path)
            path = final_path
            if (role == "audio") != mime_type.startswith("audio/"):
                raise ValueError("素材类型与用途不一致")
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
            elif mime_type.startswith("image/"):
                info = probe(path)
                stream = next((item for item in info.get("streams", []) if item.get("codec_type") == "video"), None)
                if not stream or stream.get("width", 0) < 32 or stream.get("height", 0) < 32 or stream.get("width", 0) * stream.get("height", 0) > 40_000_000:
                    raise ValueError("图片无法解码、过小或分辨率超过限制")
                metadata.update(width=stream["width"], height=stream["height"])
            elif mime_type.startswith("video/"):
                metadata.update(video_metadata(path))
                decode_check(path)
            else:
                raise ValueError("素材类型与用途不一致")
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
