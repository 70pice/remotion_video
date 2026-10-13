"""Operator CLI for the VideoAgents pipeline.

The supervising director session drives production through these commands; the
durable semantics (command idempotency, checkpoints, operation ledgers) are the
same ones the graph has always used. All output is JSON so agents can parse it.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from videoagents.contracts import Brief, RetryFailedRunRequest, SettingsPatch
from videoagents.default_config import PROJECT_ROOT, RUNTIME_ROOT
from videoagents.nodes.director_review import current_shot_review_artifact
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, NotFound, Repository
from worker.runner import Worker


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _repository(args: argparse.Namespace) -> Repository:
    return Repository(Path(args.runtime_dir) if args.runtime_dir else RUNTIME_ROOT)


def _worker(repo: Repository) -> Worker:
    return Worker(repo, PROJECT_ROOT)


def _drain(worker: Worker) -> list[str]:
    """Run every claimable command; the graph pauses itself at human gates."""
    executed: list[str] = []
    while worker.once():
        pass
    return executed


def _finish(repo: Repository, job_id: str) -> int:
    """Emit the final state and exit non-zero when the run actually failed."""
    job = repo.get_job(job_id)
    emit(_job_summary(job))
    return 1 if job.status == "FAILED" else 0


def _job_summary(job: Any) -> dict[str, Any]:
    return {"job_id": job.job_id, "revision": job.revision, "status": job.status, "stage": job.stage,
            "message": job.message, "topic": job.brief.topic,
            "pending": bool(job.pending_input)}


def cmd_create(args: argparse.Namespace) -> int:
    repo = _repository(args)
    if args.brief:
        payload = json.loads(Path(args.brief).read_text(encoding="utf-8"))
    else:
        payload = {"topic": args.topic or "", "creative_direction": args.direction or "",
                   "script_text": args.script or "", "source_urls": args.source_url or []}
        if args.target_seconds:
            payload["target_seconds"] = args.target_seconds
        if args.usage:
            payload["usage"] = args.usage
    job = repo.create_job(Brief.model_validate(payload))
    emit(_job_summary(job))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    repo = _repository(args)
    job = repo.get_job(args.job_id)
    repo.enqueue(job.job_id, {"action": args.action, "base_revision": job.revision,
                              "idempotency_key": args.idempotency_key or f"cli-{args.action}-{job.job_id}-{job.revision}"})
    _drain(_worker(repo))
    return _finish(repo, job.job_id)


def cmd_retry(args: argparse.Namespace) -> int:
    repo = _repository(args)
    job = repo.get_job(args.job_id)
    with repo.connection() as db:
        row = db.execute(
            "SELECT command_id FROM commands WHERE job_id=? AND status='FAILED' "
            "ORDER BY created_at DESC, rowid DESC LIMIT 1", (job.job_id,)).fetchone()
    if not row:
        emit({"error": "没有可续跑的失败命令", "status": job.status})
        return 1
    JobService(repo, PROJECT_ROOT).retry_failed_run(args.job_id, RetryFailedRunRequest(
        base_revision=job.revision, retry_command_id=row[0],
        idempotency_key=f"cli-retry-{row[0][:12]}-{int(time.time())}"))
    _drain(_worker(repo))
    return _finish(repo, args.job_id)


def cmd_resume(args: argparse.Namespace) -> int:
    repo = _repository(args)
    job = repo.get_job(args.job_id)
    pending = job.pending_input
    if not pending:
        emit({"error": "任务没有待回复的审核", "status": job.status})
        return 1
    payload: dict[str, Any] = {"action": "resume", "base_revision": job.revision,
                               "pending_token": pending["pending_token"],
                               "decision": args.decision, "note": args.note,
                               "idempotency_key": args.idempotency_key or f"cli-resume-{job.job_id}-{job.revision}-{pending['pending_token'][:8]}"}
    if args.shot_ids:
        payload["reviewed_shot_ids"] = [item.strip() for item in args.shot_ids.split(",") if item.strip()]
    repo.enqueue(job.job_id, payload)
    _drain(_worker(repo))
    return _finish(repo, args.job_id)


def cmd_status(args: argparse.Namespace) -> int:
    repo = _repository(args)
    if not args.job_id:
        emit([_job_summary(job) for job in repo.list_jobs()])
        return 0
    job = repo.get_job(args.job_id)
    result = _job_summary(job)
    if job.pending_input:
        result["pending_input"] = job.pending_input
    result["artifacts"] = [
        {"kind": item.kind, "revision": item.revision,
         "path": str(repo.artifact_path(item.artifact_id)[0]) if _artifact_exists(repo, item) else None,
         "url": item.url}
        for item in job.artifacts]
    emit(result)
    return 0


def _artifact_exists(repo: Repository, item: Any) -> bool:
    try:
        repo.artifact_path(item.artifact_id)
        return True
    except (ValueError, OSError):
        return False


def cmd_shots(args: argparse.Namespace) -> int:
    repo = _repository(args)
    job = repo.get_job(args.job_id)
    try:
        artifact, manifest = current_shot_review_artifact(repo, job, validate_components=False)
    except ValueError as exc:
        emit({"error": str(exc), "stage": job.stage})
        return 1
    emit({"job_id": job.job_id, "revision": job.revision, "manifest_path": str(repo.artifact_path(artifact.artifact_id)[0]),
          "mode": manifest.get("mode"), "required_shot_ids": job.pending_input.get("required_shot_ids") if job.pending_input else None,
          "shots": [{"shot_id": item["shot_id"], "review_frame": item["review_frame"],
                     "image": str(repo.artifact_path(item["image"]["artifact_id"])[0]),
                     "design": {key: value for key, value in item.items()
                                if key not in {"shot_id", "review_frame", "image"}}}
                    for item in manifest["items"]]})
    return 0


def cmd_poll(args: argparse.Namespace) -> int:
    """Read the human decision from the job's Feishu review table and resume."""
    from videoagents.providers.feishu import FeishuReviewBase, FeishuUnavailable

    repo = _repository(args)
    job = repo.get_job(args.job_id)
    if job.status != "NEEDS_HUMAN" or not job.pending_input:
        emit(_job_summary(job))
        return 0
    settings = SettingsService(repo).internal()
    base = FeishuReviewBase(repo, settings.get("feishu_folder_token", ""))
    try:
        decision = base.poll_decision(job, job.pending_input["pending_token"])
    except FeishuUnavailable as exc:
        emit({"error": str(exc), "status": job.status, "hint": "飞书不可用时可改用 videoagents resume"})
        return 2
    if not decision:
        emit({"job_id": job.job_id, "status": job.status, "stage": job.stage, "waiting": True,
              "pending_token": job.pending_input["pending_token"],
              "hint": "在飞书「审核记录」中把结论改为 通过/需修改(需修改须填意见)后再次运行 poll"})
        return 0
    payload: dict[str, Any] = {"action": "resume", "base_revision": job.revision,
                               "pending_token": job.pending_input["pending_token"],
                               "decision": decision["decision"], "note": decision["note"],
                               "idempotency_key": f"feishu-{job.pending_input['pending_token']}"}
    if decision["decision"] == "confirm" and job.pending_input.get("review_mode") == "per_shot_stills":
        # Feishu 通过 is the whole-package confirmation for every listed shot;
        # a revise answer must NOT carry the reviewed-shot list (rejected upstream).
        payload["reviewed_shot_ids"] = list(job.pending_input["required_shot_ids"])
    repo.enqueue(job.job_id, payload)
    _drain(_worker(repo))
    return _finish(repo, args.job_id)


def cmd_cancel(args: argparse.Namespace) -> int:
    repo = _repository(args)
    job = repo.cancel(args.job_id)
    emit(_job_summary(job))
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    repo = _repository(args)
    job = repo.get_job(args.job_id)
    JobService(repo, PROJECT_ROOT).delete(args.job_id, job.revision)
    emit({"job_id": args.job_id, "deleted": True})
    return 0


def cmd_upload(args: argparse.Namespace) -> int:
    repo = _repository(args)
    alignment = json.loads(Path(args.alignment).read_text(encoding="utf-8")) if args.alignment else None
    asset = JobService(repo, PROJECT_ROOT).upload(
        args.job_id, Path(args.file).read_bytes(), Path(args.file).name, args.role,
        source_url=args.source_url, license_note=args.license_note, alignment=alignment)
    emit(asset.model_dump())
    return 0


def cmd_settings(args: argparse.Namespace) -> int:
    repo = _repository(args)
    if args.settings_command == "get":
        emit(SettingsService(repo).public())
        return 0
    key = args.key
    value: Any = args.value
    try:
        value = json.loads(args.value)
    except ValueError:
        pass
    emit(SettingsService(repo).patch(SettingsPatch.model_validate({key: value})))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="videoagents", description=__doc__)
    parser.add_argument("--runtime-dir", default="", help="覆盖运行目录(默认 .runtime/videoagents)")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建任务(brief)")
    create.add_argument("--brief", default="", help="Brief JSON 文件路径(推荐)")
    create.add_argument("--topic", default="")
    create.add_argument("--direction", default="")
    create.add_argument("--script", default="")
    create.add_argument("--source-url", action="append", default=[])
    create.add_argument("--target-seconds", type=float, default=0)
    create.add_argument("--usage", default="", choices=["", "personal", "commercial", "unspecified"])
    create.set_defaults(handler=cmd_create)

    run = sub.add_parser("run", help="执行任务到下一个人工门或完成")
    run.add_argument("job_id")
    run.add_argument("--action", default="produce", choices=["produce", "voice"])
    run.add_argument("--idempotency-key", default="")
    run.set_defaults(handler=cmd_run)

    retry = sub.add_parser("retry", help="失败续跑")
    retry.add_argument("job_id")
    retry.set_defaults(handler=cmd_retry)

    resume = sub.add_parser("resume", help="回复人工审核(飞书不可用时的兜底入口)")
    resume.add_argument("job_id")
    resume.add_argument("--decision", required=True, choices=["confirm", "revise", "cancel"])
    resume.add_argument("--note", required=True, help="确认说明或修改意见")
    resume.add_argument("--shot-ids", default="", help="逐镜审核整包确认时的镜头ID列表(逗号分隔)")
    resume.add_argument("--idempotency-key", default="")
    resume.set_defaults(handler=cmd_resume)

    poll = sub.add_parser("poll", help="读取飞书审核记录中的人工决定并续跑")
    poll.add_argument("job_id")
    poll.set_defaults(handler=cmd_poll)

    status = sub.add_parser("status", help="任务状态;不带 job_id 列出全部")
    status.add_argument("job_id", nargs="?", default="")
    status.set_defaults(handler=cmd_status)

    shots = sub.add_parser("shots", help="列出逐镜审核包(PNG 路径与设计)")
    shots.add_argument("job_id")
    shots.set_defaults(handler=cmd_shots)

    cancel = sub.add_parser("cancel", help="取消任务")
    cancel.add_argument("job_id")
    cancel.set_defaults(handler=cmd_cancel)

    delete = sub.add_parser("delete", help="删除已取消且未完成的任务")
    delete.add_argument("job_id")
    delete.set_defaults(handler=cmd_delete)

    upload = sub.add_parser("upload", help="导入真实素材(音频/图片/视频)")
    upload.add_argument("job_id")
    upload.add_argument("file")
    upload.add_argument("--role", required=True, choices=["audio", "evidence", "illustration", "decoration"])
    upload.add_argument("--source-url", default="")
    upload.add_argument("--license-note", default="")
    upload.add_argument("--alignment", default="", help="音频对齐 JSON 文件")
    upload.set_defaults(handler=cmd_upload)

    settings = sub.add_parser("settings", help="查看/修改设置(密钥走系统凭据库)")
    settings.add_argument("settings_command", choices=["get", "set"])
    settings.add_argument("key", nargs="?", default="")
    settings.add_argument("value", nargs="?", default="")
    settings.set_defaults(handler=cmd_settings)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (Conflict, NotFound) as exc:
        emit({"error": str(exc)})
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
