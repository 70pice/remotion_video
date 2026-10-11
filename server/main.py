"""FastAPI owns persistence and HTTP only; long work stays in the worker."""

import argparse
import asyncio
import json
import math
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from server.security.session import LocalSession
from videoagents import __version__
from videoagents.contracts import (
    Asset,
    Brief,
    ComponentDemoRequest,
    DraftRequest,
    Job,
    ModelCatalog,
    ResumeRequest,
    RetryFailedRunRequest,
    RunRequest,
    SettingsPatch,
)
from videoagents.contracts.models import ModelProvider
from videoagents.default_config import PROJECT_ROOT, RUNTIME_ROOT
from videoagents.providers.model_catalog import ModelCatalogService
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.tools.catalog import component_catalog


class AlignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_revision: int = Field(ge=1)
    asset_id: str
    alignment: dict[str, Any]


def require_portrait_production(brief: Brief) -> None:
    """生产入口统一抖音竖屏；旧版本仍能读取，修改需求后才转换。"""
    if (brief.width, brief.height, brief.fps) != (1080, 1920, 30):
        raise ValueError("制作格式固定为抖音竖屏 1080 × 1920、30 fps；请保存新版本制作要求")
    if "横屏" in brief.platform:
        raise ValueError("发布格式固定为竖屏，请使用抖音等竖屏平台")


def _same_idempotency_command_exists(repository: Repository, job_id: str, idempotency_key: str) -> bool:
    with repository.connection() as db:
        return db.execute(
            "SELECT 1 FROM commands WHERE job_id=? AND idempotency_key=?",
            (job_id, idempotency_key),
        ).fetchone() is not None


def _validate_component_demo_history(repository: Repository, job: Job, idempotency_key: str) -> None:
    if _same_idempotency_command_exists(repository, job.job_id, idempotency_key):
        return
    with repository.connection() as db:
        rows = db.execute(
            "SELECT command_id,payload FROM commands WHERE job_id=? ORDER BY created_at,rowid",
            (job.job_id,),
        ).fetchall()

    commands: dict[str, dict[str, Any]] = {}
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError as exc:
            raise Conflict("任务已有无法识别的历史命令，不能改作组件套样片") from exc
        if not isinstance(payload, dict):
            raise Conflict("任务已有无法识别的历史命令，不能改作组件套样片")
        commands[row["command_id"]] = payload

    def is_prior_revision(payload: dict[str, Any]) -> bool:
        base_revision = payload.get("base_revision")
        if type(base_revision) is not int:
            raise Conflict("任务已有无法识别的历史命令，不能改作组件套样片")
        if base_revision >= job.revision:
            raise Conflict("当前版本已有组件套样片命令，请刷新或保存新版本后重试")
        return True

    def referenced_command(thread_id: Any) -> dict[str, Any] | None:
        prefix = f"job:{job.job_id}:run:"
        if not isinstance(thread_id, str) or not thread_id.startswith(prefix):
            return None
        return commands.get(thread_id.removeprefix(prefix))

    def is_component_demo_recovery(payload: dict[str, Any]) -> bool:
        action = payload.get("action")
        if action == "resume":
            pending = payload.get("pending_input")
            if not isinstance(pending, dict) or pending.get("retry_node") != "director_demo":
                return False
            previous = referenced_command(pending.get("thread_id"))
        elif action == "retry":
            retry_command_id = payload.get("retry_command_id")
            previous = commands.get(retry_command_id) if isinstance(retry_command_id, str) else None
        else:
            return False
        return (
            isinstance(previous, dict)
            and previous.get("action") == "component_demo"
            and payload.get("base_revision") == previous.get("base_revision")
        )

    for payload in commands.values():
        if payload.get("action") == "component_demo":
            is_prior_revision(payload)
            continue
        if is_component_demo_recovery(payload) and is_prior_revision(payload):
            continue
        if payload.get("action") != "component_demo":
            raise Conflict("任务已有生产或恢复命令历史，不能改作组件套样片")


def validate_component_demo_request(repository: Repository, job: Job, request: ComponentDemoRequest) -> None:
    """Allow component samples only on fresh material-only draft revisions."""
    if _same_idempotency_command_exists(repository, job.job_id, request.idempotency_key):
        return
    _validate_component_demo_history(repository, job, request.idempotency_key)
    if job.status != "DRAFT" or job.pending_input:
        raise Conflict("组件套样片只能从无待办的草稿任务发起")
    if job.script or job.timeline:
        raise Conflict("已有文案或时间轴的任务不能改作组件套样片")
    if any(asset.role == "audio" for asset in job.assets):
        raise Conflict("已有配音素材的任务不能改作组件套样片")
    if any(artifact.kind == "stage_review" for artifact in job.artifacts):
        raise Conflict("已有人工审核记录的任务不能改作组件套样片")
    if any(artifact.kind != "asset" for artifact in job.artifacts):
        raise Conflict("已有生产产物的任务不能改作组件套样片")
    if request.set_id.startswith("B"):
        if job.assets or any(artifact.kind == "asset" for artifact in job.artifacts):
            raise Conflict("B 无素材组件套只能从空素材草稿任务发起")
        return
    asset = next((item for item in job.assets if item.asset_id == request.asset_id), None)
    if asset is None:
        raise Conflict("组件套样片指定的素材不存在")
    if asset.role == "audio" or not (asset.mime_type.startswith("image/") or asset.mime_type.startswith("video/")):
        raise Conflict("组件套样片必须选择已导入的图片或视频素材")
    if request.set_id in {f"A{index:02d}" for index in range(7, 13)}:
        metadata = repository.asset_metadata(asset.asset_id)
        width = metadata.get("width")
        height = metadata.get("height")
        if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384:
            raise Conflict(f"{request.set_id} rich 素材必须带有效实测尺寸元数据")
        if request.set_id == "A09":
            duration = metadata.get("duration_seconds")
            frame_count = next(
                (
                    metadata.get(key)
                    for key in ("frame_count", "framecount", "video_frame_count")
                    if type(metadata.get(key)) is int and metadata.get(key) > 0
                ),
                None,
            )
            frame_rate = metadata.get("frame_rate")
            expected_frames = math.ceil(request.duration_seconds * 30)
            if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
                raise Conflict("A09 rich 必须选择当前任务导入的 MP4 操作录屏")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration):
                raise Conflict("A09 rich 操作录屏缺少有效实测时长")
            if frame_count is None and (
                not isinstance(frame_rate, (int, float)) or isinstance(frame_rate, bool) or frame_rate <= 0
            ):
                raise Conflict("A09 rich 操作录屏缺少实测 frame_count 或 frame_rate 元数据")
            if frame_count is not None and frame_count < expected_frames:
                raise Conflict("A09 rich duration_seconds 必须被实测 frame_count/时长覆盖")
            if duration + 0.001 < request.duration_seconds:
                raise Conflict("A09 rich duration_seconds 必须被实测 frame_count/时长覆盖")
        else:
            if not asset.mime_type.startswith("image/") or not asset.timeline_src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                raise Conflict(f"{request.set_id} rich 必须选择当前任务导入的图片素材")
        return
    if request.tutorial_steps is not None:
        if request.set_id != "A02":
            raise Conflict("教学步骤只允许用于 A02 App 对象组件套")
        if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
            raise Conflict("A02 教学演示必须选择当前任务导入的 MP4 录屏素材")
        metadata = repository.asset_metadata(asset.asset_id)
        duration = metadata.get("duration_seconds")
        width = metadata.get("width")
        height = metadata.get("height")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration + 0.001 < request.duration_seconds:
            raise Conflict("A02 教学录屏缺少有效实测时长或时长不足")
        if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384 or height <= width:
            raise Conflict("A02 教学录屏必须带有效竖屏尺寸元数据")
    if request.focus_steps is not None:
        if request.set_id not in {"A03", "A04", "A05", "A06"}:
            raise Conflict("重点圈选步骤只允许用于 A03-A06 素材组件套")
        metadata = repository.asset_metadata(asset.asset_id)
        width = metadata.get("width")
        height = metadata.get("height")
        if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384:
            raise Conflict("重点圈选素材必须带有效实测尺寸元数据")
        if request.set_id == "A03":
            duration = metadata.get("duration_seconds")
            if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
                raise Conflict("A03 重点演示必须选择当前任务导入的 MP4 操作录屏素材")
            if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration + 0.001 < request.duration_seconds:
                raise Conflict("A03 操作录屏缺少有效实测时长或时长不足")
        else:
            if not asset.mime_type.startswith("image/") or not asset.timeline_src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                raise Conflict(f"{request.set_id} 重点演示必须选择当前任务导入的图片素材")
            if request.set_id == "A05" and (asset.role != "evidence" or not asset.source_url):
                raise Conflict("A05 模拟文档需按 evidence 素材导入并保留模拟来源 URL")


def create_app(runtime_dir: Path | None = None, project_root: Path | None = None) -> FastAPI:
    repository = Repository(runtime_dir or RUNTIME_ROOT)
    root = project_root or PROJECT_ROOT
    service = JobService(repository, root)
    settings = SettingsService(repository)
    sessions = LocalSession()
    app = FastAPI(title="VideoAgents", version=__version__)
    app.state.repository = repository
    app.state.service = service
    app.state.sessions = sessions
    app.state.model_catalog = ModelCatalogService()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver"])
    app.add_middleware(CORSMiddleware, allow_origins=list(sessions.origins), allow_credentials=True,
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                       allow_headers=["Content-Type", "X-CSRF-Token", "Last-Event-ID", "Range"],
                       expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"])

    @app.middleware("http")
    async def protect_before_body_parse(request: Request, call_next):
        if request.url.path.startswith("/api/") and request.url.path not in {"/api/session", "/api/health"} and request.method != "OPTIONS":
            try:
                sessions.require(request)
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        if request.url.path.endswith("/assets"):
            length = request.headers.get("content-length")
            if length:
                try:
                    too_large = int(length) > 100 * 1024 * 1024 + 65536
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Content-Length 无效"})
                if too_large:
                    return JSONResponse(status_code=413, content={"detail": "上传请求超过 100 MiB"})
        return await call_next(request)

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)[:2000]})

    @app.exception_handler(RequestValidationError)
    async def request_invalid(request: Request, exc: RequestValidationError):
        # Never echo submitted credential values through validation error input.
        detail = "；".join(".".join(str(part) for part in item["loc"]) + ": " + item["msg"] for item in exc.errors())
        return JSONResponse(status_code=422, content={"detail": detail[:2000]})

    @app.get("/api/health")
    def health():
        return {"status": "ok", "worker_alive": repository.worker_alive(), "version": __version__}

    @app.get("/api/session")
    def session(request: Request):
        sessions.validate_origin(request)
        session_id = secrets.token_urlsafe(32)
        response = JSONResponse({"csrf_token": sessions.token("csrf:" + session_id)})
        response.set_cookie("videoagents_session", sessions.cookie(session_id), httponly=True,
                            samesite="strict", secure=request.url.scheme == "https", max_age=86400, path="/")
        response.headers["Cache-Control"] = "no-store"
        return response

    protected = [Depends(sessions.require)]

    @app.get("/api/jobs", response_model=list[Job], dependencies=protected)
    def list_jobs():
        return repository.list_jobs()

    @app.post("/api/jobs", response_model=Job, status_code=201, dependencies=protected)
    def create_job(brief: Brief):
        require_portrait_production(brief)
        return repository.create_job(brief)

    @app.get("/api/jobs/{job_id}", response_model=Job, dependencies=protected)
    def get_job(job_id: str):
        return repository.get_job(job_id)

    @app.patch("/api/jobs/{job_id}/draft", response_model=Job, dependencies=protected)
    def patch_draft(job_id: str, draft: DraftRequest):
        require_portrait_production(draft.brief or repository.get_job(job_id).brief)
        return service.draft(job_id, draft)

    @app.post("/api/jobs/{job_id}/runs", response_model=Job, status_code=202, dependencies=protected)
    def run(job_id: str, command: RunRequest):
        require_portrait_production(repository.get_job(job_id).brief)
        if command.action == "review":
            raise HTTPException(422, "成片审核流程已移除，请使用制作或渲染动作")
        return repository.enqueue(job_id, command.model_dump(exclude_none=True))


    @app.post("/api/jobs/{job_id}/retry-failed-run", response_model=Job, status_code=202, dependencies=protected)
    def retry_failed_run(job_id: str, command: RetryFailedRunRequest):
        require_portrait_production(repository.get_job(job_id).brief)
        return service.retry_failed_run(job_id, command)


    @app.post("/api/jobs/{job_id}/component-demo", response_model=Job, status_code=202, dependencies=protected)
    def component_demo(job_id: str, command: ComponentDemoRequest):
        job = repository.get_job(job_id)
        require_portrait_production(job.brief)
        validate_component_demo_request(repository, job, command)
        component_demo = {
            "set_id": command.set_id,
            "duration_seconds": command.duration_seconds,
        }
        if command.composition != "basic":
            component_demo["composition"] = command.composition
        if command.asset_id is not None:
            component_demo["asset_id"] = command.asset_id
        if command.content is not None:
            component_demo["content"] = command.content.model_dump(exclude_none=True)
        if command.tutorial_steps is not None:
            component_demo["tutorial_steps"] = [item.model_dump() for item in command.tutorial_steps]
        if command.focus_steps is not None:
            component_demo["focus_steps"] = [item.model_dump() for item in command.focus_steps]
        return repository.enqueue(job_id, {
            "base_revision": command.base_revision,
            "idempotency_key": command.idempotency_key,
            "action": "component_demo",
            "component_demo": component_demo,
        })


    @app.post("/api/jobs/{job_id}/cancel", response_model=Job, dependencies=protected)
    def cancel(job_id: str):
        return repository.cancel(job_id)

    @app.delete("/api/jobs/{job_id}", status_code=204, dependencies=protected)
    def delete_job(job_id: str, base_revision: int = Query(ge=1)):
        service.delete(job_id, base_revision)
        return Response(status_code=204)

    @app.post("/api/jobs/{job_id}/resume", response_model=Job, status_code=202, dependencies=protected)
    def resume(job_id: str, command: ResumeRequest):
        require_portrait_production(repository.get_job(job_id).brief)
        payload = command.model_dump(exclude_none=True)
        payload["action"] = "resume"
        return repository.enqueue(job_id, payload)

    @app.post("/api/jobs/{job_id}/assets", response_model=Asset, status_code=201, dependencies=protected)
    async def upload(job_id: str, file: UploadFile = File(...), role: str = Form(...), source_url: str = Form(""),
                     license_note: str = Form(""), alignment: str | None = Form(None)):
        data = bytearray()
        while chunk := await file.read(1024 * 1024):
            data.extend(chunk)
            if len(data) > 100 * 1024 * 1024:
                raise HTTPException(413, "文件超过 100 MiB")
        try:
            alignment_value = json.loads(alignment) if alignment else None
        except json.JSONDecodeError:
            raise HTTPException(422, "alignment 必须是 JSON 对象")
        # ffprobe/file IO are bounded, executed off the event loop.
        return await asyncio.to_thread(service.upload, job_id, bytes(data), file.filename or "upload", role, source_url, license_note, alignment_value)

    @app.post("/api/jobs/{job_id}/alignment", response_model=Job, dependencies=protected)
    def alignment(job_id: str, request: AlignmentRequest):
        return service.set_alignment(job_id, request.base_revision, request.asset_id, request.alignment)

    @app.get("/api/jobs/{job_id}/alignment", dependencies=protected)
    def get_alignment(job_id: str, asset_id: str | None = None):
        job = repository.get_job(job_id)
        selected = asset_id or repository.active_audio(job_id)
        audio = next((item for item in reversed(job.assets) if item.role == "audio" and (not selected or item.asset_id == selected)), None)
        if asset_id and not audio:
            raise HTTPException(404, "此任务没有指定的音频素材")
        if not audio:
            return {"asset_id": None, "alignment": None, "duration_seconds": None}
        metadata = repository.asset_metadata(audio.asset_id)
        return {"asset_id": audio.asset_id, "alignment": metadata.get("alignment"), "duration_seconds": metadata.get("duration_seconds")}

    @app.get("/api/jobs/{job_id}/events", dependencies=protected)
    async def events(job_id: str, request: Request, after: int = 0):
        repository.get_job(job_id)
        header = request.headers.get("last-event-id", "")
        if header:
            try:
                after = max(after, int(header))
            except ValueError:
                raise HTTPException(422, "Last-Event-ID 必须是整数")
        async def stream():
            cursor, idle = after, 0
            while not await request.is_disconnected():
                for event in repository.events_after(job_id, cursor):
                    cursor, idle = event["event_id"], 0
                    yield f"id: {cursor}\nevent: progress\ndata: {json.dumps(event['payload'], ensure_ascii=False)}\n\n"
                idle += 1
                if idle >= 15:
                    idle = 0
                    yield ": keep-alive\n\n"
                await asyncio.sleep(1)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.head("/api/artifacts/{artifact_id}", dependencies=protected, include_in_schema=False)
    @app.get("/api/artifacts/{artifact_id}", dependencies=protected)
    def artifact(artifact_id: str, request: Request):
        path, info, _ = repository.artifact_path(artifact_id)
        # Starlette FileResponse performs RFC Range/suffix-range handling.
        # Named artifacts are the only filesystem entry point.
        return FileResponse(path, media_type=info.mime_type, filename=info.name,
                            content_disposition_type="inline", headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/catalog", dependencies=protected)
    def catalog():
        return component_catalog(root)

    @app.get("/api/settings", dependencies=protected)
    def get_settings():
        return settings.public()

    @app.patch("/api/settings", dependencies=protected)
    def patch_settings(patch: SettingsPatch):
        return settings.patch(patch)

    @app.get("/api/models/{provider}", response_model=ModelCatalog, dependencies=protected)
    def models(provider: ModelProvider, refresh: bool = False):
        return app.state.model_catalog.get(provider, refresh=refresh)

    dist = root / "web" / "dist"
    if (dist / "index.html").is_file():
        # API routes are registered first; the built React app is the fallback.
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app


app = create_app()


def main():
    parser = argparse.ArgumentParser(description="VideoAgents 本机 HTTP API")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost", "::1"])
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
