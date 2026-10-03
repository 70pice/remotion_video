"""FastAPI owns persistence and HTTP only; long work stays in the worker."""

import argparse
import asyncio
import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
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
    DraftRequest,
    Job,
    ModelCatalog,
    ResumeRequest,
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
                       allow_methods=["GET", "POST", "PATCH", "HEAD", "OPTIONS"],
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
        return repository.create_job(brief)

    @app.get("/api/jobs/{job_id}", response_model=Job, dependencies=protected)
    def get_job(job_id: str):
        return repository.get_job(job_id)

    @app.patch("/api/jobs/{job_id}/draft", response_model=Job, dependencies=protected)
    def patch_draft(job_id: str, draft: DraftRequest):
        return service.draft(job_id, draft)

    @app.post("/api/jobs/{job_id}/runs", response_model=Job, status_code=202, dependencies=protected)
    def run(job_id: str, command: RunRequest):
        return repository.enqueue(job_id, command.model_dump())

    @app.post("/api/jobs/{job_id}/cancel", response_model=Job, dependencies=protected)
    def cancel(job_id: str):
        return repository.cancel(job_id)

    @app.post("/api/jobs/{job_id}/resume", response_model=Job, status_code=202, dependencies=protected)
    def resume(job_id: str, command: ResumeRequest):
        payload = command.model_dump()
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
