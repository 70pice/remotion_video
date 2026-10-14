"""SQLite transactions own accepted commands, revisions and replayable events."""

import hashlib
import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from videoagents.contracts import (
    Artifact,
    Asset,
    Brief,
    Job,
    ReplenishMaterialsRequest,
    RestartUnknownRequest,
)


class Conflict(Exception):
    pass


class NotFound(Exception):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


class Repository:
    def __init__(self, runtime_dir: Path):
        self.root = runtime_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "application.sqlite"
        if os.name != "nt":
            # Same privacy bar as the settings writer: the DB holds job context.
            os.chmod(self.root, 0o700)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs(job_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL, created_at TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_job ON events(job_id,event_id);
                CREATE TABLE IF NOT EXISTS commands(command_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL, payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
                    status TEXT NOT NULL, pid INTEGER, lease_until REAL, created_at TEXT NOT NULL,
                    UNIQUE(job_id,idempotency_key));
                CREATE TABLE IF NOT EXISTS artifacts(artifact_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                    path TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS asset_metadata(asset_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS artifact_metadata(artifact_id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS job_inputs(job_id TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                    PRIMARY KEY(job_id,key));
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS heartbeats(name TEXT PRIMARY KEY, pid INTEGER, at REAL);
                CREATE TABLE IF NOT EXISTS operations(operation_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
                    input_hash TEXT NOT NULL, provider TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL,
                    UNIQUE(job_id,input_hash,provider));
                CREATE TABLE IF NOT EXISTS run_metrics(job_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    metric TEXT NOT NULL, value INTEGER NOT NULL, PRIMARY KEY(job_id,revision,metric));
            """)

    @contextmanager
    def connection(self, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.db, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            if immediate:
                db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def _get(self, db: sqlite3.Connection, job_id: str) -> Job:
        row = db.execute("SELECT body FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            raise NotFound("任务不存在")
        return Job.model_validate_json(row["body"])

    def get_job(self, job_id: str) -> Job:
        with self.connection() as db:
            return self._get(db, job_id)

    def list_jobs(self) -> list[Job]:
        with self.connection() as db:
            jobs = [Job.model_validate_json(row[0]) for row in db.execute("SELECT body FROM jobs")]
        return sorted(jobs, key=lambda item: item.updated_at, reverse=True)

    def _save(self, db: sqlite3.Connection, job: Job, event: str = "updated",
              event_details: dict[str, Any] | None = None) -> Job:
        job.updated_at = now()
        event_body = {"type": event, "job_id": job.job_id, "revision": job.revision,
                      "status": job.status, "stage": job.stage, "message": job.message,
                      "progress": job.progress, "updated_at": job.updated_at}
        event_body.update(event_details or {})
        result = db.execute("INSERT INTO events(job_id,created_at,body) VALUES(?,?,?)",
                            (job.job_id, now(), dumps(event_body)))
        job.latest_event_id = result.lastrowid or 0
        db.execute("INSERT INTO jobs(job_id,body) VALUES(?,?) ON CONFLICT(job_id) DO UPDATE SET body=excluded.body",
                   (job.job_id, job.model_dump_json()))
        return job

    def create_job(self, brief: Brief) -> Job:
        if not brief.topic.strip() and not brief.creative_direction.strip() and not brief.script_text.strip():
            raise ValueError("请提供主题或本期创作方向")
        job = Job(job_id=uuid.uuid4().hex, revision=1, status="DRAFT", stage="idle", message="草稿已保存",
                  created_at=now(), updated_at=now(), brief=brief)
        with self.connection(immediate=True) as db:
            return self._save(db, job, "created")

    def update_job(self, job_id: str, expected_revision: int | None = None,
                   expected_event_id: int | None = None, **changes: Any) -> Job:
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            if expected_revision is not None and job.revision != expected_revision:
                raise Conflict("任务版本已变化，请刷新后重试")
            if expected_event_id is not None and job.latest_event_id != expected_event_id:
                raise Conflict("上下文提交期间任务已变化，请恢复最新上下文")
            if job.status == "CANCELLED" and changes.get("status") not in {"CANCELLED", None}:
                raise Conflict("任务已取消")
            for key, value in changes.items():
                setattr(job, key, value)
            return self._save(db, Job.model_validate(job.model_dump()))

    def check_editable(self, db: sqlite3.Connection, job: Job, base_revision: int | None) -> None:
        if base_revision is not None and job.revision != base_revision:
            raise Conflict("任务版本已变化，请刷新后重试")
        active = db.execute("SELECT 1 FROM commands WHERE job_id=? AND status IN ('PENDING','CLAIMED')",
                            (job.job_id,)).fetchone()
        if active:
            raise Conflict("执行中的任务请先取消，待执行进程退出后再修改")

    def edit_job(self, job_id: str, base_revision: int | None, transform: Any) -> Job:
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            self.check_editable(db, job, base_revision)
            updated = transform(job)
            return self._save(db, Job.model_validate(updated.model_dump()), "revision")

    def restart_unknown(self, job_id: str, request: RestartUnknownRequest, transform: Any) -> Job:
        """Authorize one new revision atomically; never settle or replay the old call."""
        key = "authorized_model_restart:" + request.operation_id
        payload = request.model_dump(exclude={"base_revision"})
        # Default requests must still match authorizations saved before this flag existed.
        if not request.rebuild_script:
            payload.pop("rebuild_script")
        if not request.materials_only:
            payload.pop("materials_only")
            payload.pop("materials_note")
        if not request.director_only:
            payload.pop("director_only")
        digest = fingerprint(payload)
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            previous = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key=?", (job_id, key)).fetchone()
            if previous:
                receipt = json.loads(previous[0])
                if receipt["request_hash"] != digest:
                    raise Conflict("同一个未知操作不能用于不同的重启授权")
                if request.base_revision not in {receipt["source_revision"], receipt["target_revision"]}:
                    raise Conflict("重启授权的任务版本不匹配")
                return job
            self.check_editable(db, job, request.base_revision)
            pending = job.pending_input or {}
            providers = {"script": {"llm:screenwriter", "llm:编剧"}}
            if request.rebuild_script or request.materials_only:
                providers["materials"] = {"llm:materials"}
            if request.materials_only:
                providers.pop("script")
            if request.director_only:
                providers = {"director": {"llm:director"}}
            if (job.status != "NEEDS_INPUT" or job.stage not in providers or pending.get("kind") != "input"
                    or pending.get("operation_status") != "UNKNOWN"
                    or pending.get("operation_id") != request.operation_id
                    or pending.get("revision") != job.revision or pending.get("stage") != job.stage):
                raise Conflict("重启只支持当前编剧 UNKNOWN、明确范围的素材 UNKNOWN 或 director_only 摄影 UNKNOWN")
            operation = db.execute("SELECT job_id,provider,status,body FROM operations WHERE operation_id=?",
                                   (request.operation_id,)).fetchone()
            if (not operation or operation["job_id"] != job_id or operation["status"] != "UNKNOWN"
                    or operation["provider"] not in providers[job.stage]
                    or json.loads(operation["body"]).get("revision") != job.revision):
                raise Conflict("未知操作不属于当前任务版本与模型角色，或尚未停止提交")
            unsettled = db.execute("SELECT operation_id,body FROM operations WHERE job_id=? "
                                   "AND status IN ('SUBMITTING','UNKNOWN') AND operation_id<>?",
                                   (job_id, request.operation_id)).fetchall()
            if any(self._operation_revision(row["body"], job.revision) == job.revision for row in unsettled):
                raise Conflict("当前版本仍有其他未决提交，不能通过单次授权一起重启")
            receipt = {"operation_id": request.operation_id, "operation_status": "UNKNOWN",
                       "provider": operation["provider"], "source_revision": job.revision,
                       "target_revision": job.revision + 1, "acknowledge_possible_usage": True,
                       "rebuild_script": request.rebuild_script,
                       "note": request.note, "request_hash": digest, "authorized_at": now(),
                       "previous_pending_input": pending, "previous_brief": job.brief.model_dump(),
                       "previous_script": job.script.model_dump() if job.script else None,
                       "previous_artifacts": [{"artifact_id": row["artifact_id"], "path": row["path"]}
                                              for row in db.execute("SELECT artifact_id,path FROM artifacts WHERE job_id=?",
                                                                    (job_id,))]}
            if request.materials_only:
                from videoagents.nodes.script_review import preserve_approved_script

                receipt.update(materials_only=True, materials_note=request.materials_note,
                               previous_job=job.model_dump(),
                               preserved_script=preserve_approved_script(self, job))
            if request.director_only:
                from videoagents.services.director_recovery import preserve_director_inputs

                receipt.update(director_only=True, previous_job=job.model_dump(),
                               preserved_director=preserve_director_inputs(self, job, request.note))
            updated = Job.model_validate(transform(job).model_dump())
            if updated.revision != receipt["target_revision"] or updated.status != "DRAFT":
                raise Conflict("重启授权只能保存一个新版草稿")
            receipt["brief"] = updated.brief.model_dump()
            db.execute("INSERT INTO job_inputs VALUES(?,?,?)", (job_id, key, dumps(receipt)))
            event = {
                field: receipt[field] for field in (
                    "operation_id", "operation_status", "provider", "source_revision", "target_revision",
                    "acknowledge_possible_usage", "rebuild_script", "note", "previous_artifacts",
                )
            }
            if request.materials_only:
                event.update(materials_only=True, materials_note=request.materials_note,
                             preserved_script=receipt["preserved_script"])
            if request.director_only:
                event.update(director_only=True,
                             approval_artifact_id=receipt["preserved_director"]["approval_artifact_id"],
                             audio_asset_id=receipt["preserved_director"]["audio_asset_id"])
            return self._save(db, updated, "unknown_restart_authorized", event)

    def director_restart_receipt(self, job_id: str, revision: int) -> dict[str, Any] | None:
        with self.connection() as db:
            rows = db.execute("SELECT value FROM job_inputs WHERE job_id=? "
                              "AND key LIKE 'authorized_model_restart:%'", (job_id,)).fetchall()
        return next((receipt for row in rows if (receipt := json.loads(row[0])).get("director_only") is True
                     and receipt.get("target_revision") == revision), None)

    def materials_restart_receipt(self, job_id: str, revision: int) -> dict[str, Any] | None:
        """Read the explicit authorization; it is never a new human approval."""
        with self.connection() as db:
            rows = db.execute("SELECT value FROM job_inputs WHERE job_id=? "
                              "AND (key LIKE 'authorized_model_restart:%' "
                              "OR key LIKE 'authorized_materials_replenishment:%')", (job_id,)).fetchall()
        return next((receipt for row in rows if (receipt := json.loads(row[0])).get("materials_only") is True
                     and receipt.get("target_revision") == revision), None)

    def materials_replenishment_receipt(self, job_id: str, key: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key=?",
                             (job_id, "authorized_materials_replenishment:" + key)).fetchone()
        return json.loads(row[0]) if row else None

    def replenish_materials(self, job_id: str, request: ReplenishMaterialsRequest, transform: Any) -> Job:
        """Authorize an independent collection revision at the joint gate."""
        key = "authorized_materials_replenishment:" + request.idempotency_key
        digest = fingerprint(request.model_dump())
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            existing = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key=?", (job_id, key)).fetchone()
            if existing:
                receipt = json.loads(existing[0])
                if receipt["request_hash"] != digest or job.revision != receipt["target_revision"]:
                    raise Conflict("素材补采授权已改变或属于旧版本")
                return job
            self.check_editable(db, job, request.base_revision)
            pending = job.pending_input or {}
            if (job.status != "NEEDS_HUMAN" or job.stage != "script"
                    or pending.get("kind") != "stage_review" or pending.get("stage") != "script"
                    or pending.get("node_name") != "human_review_script" or pending.get("revision") != job.revision
                    or pending.get("pending_token") != request.pending_token):
                raise Conflict("补采素材仅适用于当前文案与素材人工审核待办")
            unsettled = db.execute("SELECT body FROM operations WHERE job_id=? AND status IN ('SUBMITTING','UNKNOWN')",
                                   (job_id,)).fetchall()
            if any(self._operation_revision(row["body"], job.revision) == job.revision for row in unsettled):
                raise Conflict("当前版本存在未决提交，不能授权补采")
            from videoagents.nodes.human_review import HumanReviewNode

            if HumanReviewNode(self, node_name="human_review_script")._inputs(job) != pending.get("dependency_fingerprint"):
                raise Conflict("待审文案与素材已改变，不能授权补采")
            original = job.model_dump()
            updated, imported, preserved, research = transform(job)
            updated = Job.model_validate(updated.model_dump())
            if updated.revision != request.base_revision + 1 or updated.status != "DRAFT":
                raise Conflict("素材补采授权只能建立一个新版草稿")
            receipt = {"purpose": "materials_replenishment", "authorized_new_collection": True,
                       "materials_only": True, "source_revision": request.base_revision,
                       "target_revision": updated.revision, "materials_note": request.materials_note,
                       "note": request.note, "request_hash": digest, "authorized_at": now(),
                       "previous_pending_input": pending, "previous_job": original,
                       "preserved_script": preserved, "imported_assets": imported,
                       "imported_research": research}
            db.execute("INSERT INTO job_inputs VALUES(?,?,?)", (job_id, key, dumps(receipt)))
            return self._save(db, updated, "materials_replenishment_authorized", {
                "source_revision": request.base_revision, "target_revision": updated.revision,
                "pending_token": request.pending_token, "note": request.note,
                "materials_note": request.materials_note, "retained_asset_ids": request.retained_asset_ids,
                "idempotency_key": request.idempotency_key,
            })

    def delete_job(self, job_id: str, base_revision: int, cleanup: Any) -> None:
        """Delete a cancelled, idle job while excluding concurrent queue/edit writes."""
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            self.check_editable(db, job, base_revision)
            if job.status != "CANCELLED":
                raise Conflict("请先取消任务，待执行进程退出后再删除")
            if job.stage == "complete":
                raise Conflict("已完成任务不属于在途创作，不能通过此入口删除")
            paths = [Path(row[0]) for row in db.execute("SELECT path FROM artifacts WHERE job_id=?", (job_id,))]
            # A failed filesystem cleanup keeps the cancelled job available for retry.
            cleanup(job, paths)
            asset_ids = {asset.asset_id for asset in job.assets}
            db.executemany("DELETE FROM asset_metadata WHERE asset_id=?", [(asset_id,) for asset_id in asset_ids])
            db.execute("DELETE FROM artifact_metadata WHERE artifact_id IN "
                       "(SELECT artifact_id FROM artifacts WHERE job_id=?)", (job_id,))
            for table in ("artifacts", "job_inputs", "operations", "run_metrics", "events", "commands", "jobs"):
                db.execute(f"DELETE FROM {table} WHERE job_id=?", (job_id,))


    @staticmethod
    def _command_thread_id(job_id: str, command_id: str, payload: dict[str, Any]) -> str:
        if isinstance(payload.get("continuation_thread_id"), str) and payload["continuation_thread_id"]:
            return payload["continuation_thread_id"]
        pending = payload.get("pending_input")
        if payload.get("action") == "resume" and isinstance(pending, dict) and isinstance(pending.get("thread_id"), str):
            return pending["thread_id"]
        return "job:" + job_id + ":run:" + command_id

    @staticmethod
    def _operation_revision(body: str, fallback: int) -> int:
        try:
            value = json.loads(body)
        except json.JSONDecodeError:
            return fallback
        revision = value.get("revision", fallback)
        return revision if type(revision) is int else fallback

    @staticmethod
    def _latest_current_revision_command(rows: list[sqlite3.Row], revision: int) -> str | None:
        for row in rows:
            try:
                previous = json.loads(row["payload"])
            except json.JSONDecodeError:
                continue
            if previous.get("base_revision") == revision:
                return row["command_id"]
        return None

    def enqueue(self, job_id: str, payload: dict[str, Any]) -> Job:
        if payload.get("decision") == "select_materials":
            from videoagents.contracts import MaterialSelectionRequest

            try:
                selection = MaterialSelectionRequest.model_validate(
                    {key: value for key, value in payload.items() if key != "action"})
            except ValueError as exc:
                raise Conflict("素材部分取舍请求无效：" + str(exc)) from exc
            if payload.get("action") != "resume":
                raise Conflict("素材部分取舍只能通过当前人工门恢复")
            payload = {"action": "resume", **selection.model_dump()}
        key = payload["idempotency_key"]
        digest = fingerprint(payload)
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            existing = db.execute("SELECT payload_hash FROM commands WHERE job_id=? AND idempotency_key=?",
                                  (job_id, key)).fetchone()
            if existing:
                if existing[0] != digest:
                    raise Conflict("同一个幂等键不能用于不同请求")
                return job
            if job.revision != payload["base_revision"]:
                raise Conflict("任务版本已变化，请刷新后重试")
            if db.execute("SELECT 1 FROM commands WHERE job_id=? AND status IN ('PENDING','CLAIMED')", (job_id,)).fetchone():
                raise Conflict("任务已有待执行或执行中的命令")
            if payload.get("action") == "retry":
                if job.status != "FAILED" or job.pending_input:
                    raise Conflict("仅失败且无待办的任务可从失败命令续跑")
                failed = db.execute("SELECT command_id,payload,status FROM commands WHERE job_id=? AND command_id=?",
                                    (job_id, payload.get("retry_command_id"))).fetchone()
                if not failed or failed["status"] != "FAILED":
                    raise Conflict("只能续跑同任务的失败命令")
                previous_payload = json.loads(failed["payload"])
                if previous_payload.get("base_revision") != job.revision:
                    raise Conflict("失败命令不属于当前任务版本")
                current_revision_commands = db.execute(
                    "SELECT command_id,payload FROM commands WHERE job_id=? ORDER BY created_at DESC,rowid DESC",
                    (job_id,),
                ).fetchall()
                if self._latest_current_revision_command(current_revision_commands, job.revision) != failed["command_id"]:
                    raise Conflict("只能续跑当前版本最新失败命令")
                unsettled = db.execute(
                    "SELECT provider,body FROM operations WHERE job_id=? AND status IN ('SUBMITTING','UNKNOWN')",
                    (job_id,),
                ).fetchall()
                if any(self._operation_revision(row["body"], job.revision) == job.revision for row in unsettled):
                    raise Conflict("存在状态未知的外部提交，请先对账后再续跑")
                payload = dict(payload, continuation_thread_id=self._command_thread_id(
                    job_id, failed["command_id"], previous_payload
                ))
            elif payload.get("continue_from") is not None or payload.get("rebuild_from") is not None:
                rebuilding = payload.get("rebuild_from") == "director"
                valid_stage = job.stage in {"director", "render", "complete"} if rebuilding else job.stage == "voice"
                if (payload.get("action") not in {"produce", "storyboard", "preview", "final"}
                        or (not rebuilding and payload.get("continue_from") != "voice")
                        or (rebuilding and payload.get("continue_from") is not None)
                        or job.status != "DRAFT" or not valid_stage or job.pending_input or not job.script
                        or (rebuilding and not job.timeline)):
                    raise Conflict("仅可从已完成分镜或视频的草稿重做画面" if rebuilding else "仅可从已完成配音的草稿继续制作")
                thread_id = None
                for row in db.execute("SELECT command_id,payload FROM commands WHERE job_id=? AND status='DONE' ORDER BY created_at DESC", (job_id,)):
                    previous = json.loads(row["payload"])
                    if previous.get("base_revision") != job.revision:
                        continue
                    if rebuilding:
                        if previous.get("action") == "resume":
                            thread_id = previous.get("pending_input", {}).get("thread_id")
                        elif previous.get("action") in {"produce", "storyboard", "preview", "final"}:
                            thread_id = previous.get("continuation_thread_id") or "job:" + job_id + ":run:" + row["command_id"]
                    elif previous.get("action") == "voice":
                        thread_id = "job:" + job_id + ":run:" + row["command_id"]
                    elif previous.get("action") == "resume" and previous.get("stop_after") == "voice":
                        thread_id = previous.get("pending_input", {}).get("thread_id")
                    if thread_id:
                        break
                if not thread_id:
                    raise Conflict("没有当前版本已完成画面制作的工作流记录" if rebuilding else "没有当前版本已完成配音的工作流记录")
                # Resolve under the queue transaction; a replay uses this same checkpoint.
                payload = dict(payload, continuation_thread_id=thread_id)
            if payload.get("action") == "retry":
                job.pending_input = None
            elif payload.get("action") == "resume":
                if job.status not in {"NEEDS_INPUT", "NEEDS_HUMAN"} or not job.pending_input:
                    raise Conflict("当前任务没有可恢复的中断")
                if not job.pending_input.get("thread_id") or payload.get("pending_token") != job.pending_input.get("pending_token"):
                    raise Conflict("恢复回复绑定的中断已变化，请刷新当前待办")
                selection_fields = {"accepted_asset_ids", "rejected_asset_ids"}
                if payload.get("decision") == "select_materials":
                    from videoagents.services.material_selection import validate_material_selection

                    validate_material_selection(job, job.pending_input, selection)
                    unsettled = db.execute(
                        "SELECT body FROM operations WHERE job_id=? AND status IN ('SUBMITTING','UNKNOWN')",
                        (job_id,),
                    ).fetchall()
                    if any(self._operation_revision(row["body"], job.revision) == job.revision for row in unsettled):
                        raise Conflict("存在状态未知的外部提交，不能改变当前素材")
                elif selection_fields & payload.keys():
                    raise Conflict("素材取舍字段仅可随独立的部分决定提交")
                if payload.get("reviewed_shot_ids") is not None:
                    pending = job.pending_input
                    if (pending.get("kind") != "stage_review" or pending.get("stage") != "director"
                            or pending.get("node_name") != "director_human_gate"
                            or payload.get("decision") != "confirm"):
                        raise Conflict("已阅镜头仅可用于当前摄影逐镜审核确认")
                if payload.get("stop_after") is not None:
                    pending = job.pending_input
                    script_review = (pending.get("kind") == "stage_review" and pending.get("stage") == "script"
                                     and pending.get("node_name") in {"human_review_script", "human_review"})
                    voice_input = pending.get("kind") == "input" and pending.get("stage") == "voice"
                    if payload["stop_after"] != "voice" or payload.get("decision") != "confirm" or not (script_review or voice_input):
                        raise Conflict("只跑配音仅适用于文案确认或配音失败续跑")
                payload = dict(payload, pending_input=job.pending_input)
            else:
                job.review, job.pending_input = None, None
            command_id = uuid.uuid4().hex
            db.execute("INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
                       "VALUES(?,?,?,?,?,'PENDING',?)", (command_id, job_id, key, dumps(payload), digest, now()))
            job.status, job.message, job.progress = "QUEUED", "命令已持久化，等待执行进程", None
            return self._save(db, job, "queued")

    def claim(self, pid: int, lease_seconds: float = 30) -> dict[str, Any] | None:
        with self.connection(immediate=True) as db:
            # A lease expiry alone is insufficient: the original process must be gone.
            stale = db.execute("SELECT command_id,pid FROM commands WHERE status='CLAIMED' AND lease_until<?", (time.time(),)).fetchall()
            for row in stale:
                if not process_exists(row["pid"] or 0):
                    db.execute("UPDATE commands SET status='PENDING',pid=NULL WHERE command_id=?", (row["command_id"],))
            # Single worker is a runtime invariant. It is checked even for distinct jobs.
            if db.execute("SELECT 1 FROM commands WHERE status='CLAIMED'").fetchone():
                return None
            row = db.execute("SELECT * FROM commands WHERE status='PENDING' ORDER BY created_at LIMIT 1").fetchone()
            if row is None:
                return None
            db.execute("UPDATE commands SET status='CLAIMED',pid=?,lease_until=? WHERE command_id=?",
                       (pid, time.time() + lease_seconds, row["command_id"]))
            return {**dict(row), "payload": json.loads(row["payload"])}

    def renew(self, command_id: str, pid: int) -> None:
        with self.connection() as db:
            db.execute("UPDATE commands SET lease_until=? WHERE command_id=? AND pid=? AND status='CLAIMED'",
                       (time.time() + 30, command_id, pid))
            db.execute("INSERT INTO heartbeats VALUES('worker',?,?) ON CONFLICT(name) DO UPDATE SET pid=excluded.pid,at=excluded.at",
                       (pid, time.time()))

    def finish(self, command_id: str, status: str = "DONE") -> None:
        with self.connection() as db:
            db.execute("UPDATE commands SET status=?,lease_until=NULL WHERE command_id=?", (status, command_id))

    def heartbeat(self) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO heartbeats VALUES('worker',?,?) ON CONFLICT(name) DO UPDATE SET pid=excluded.pid,at=excluded.at",
                       (os.getpid(), time.time()))

    def worker_alive(self) -> bool:
        with self.connection() as db:
            row = db.execute("SELECT pid,at FROM heartbeats WHERE name='worker'").fetchone()
        return bool(row and time.time() - row["at"] < 15 and process_exists(row["pid"]))

    def cancel(self, job_id: str) -> Job:
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            db.execute("UPDATE commands SET status='CANCELLED' WHERE job_id=? AND status='PENDING'", (job_id,))
            job.status, job.message, job.pending_input = "CANCELLED", "已请求取消，保留已生成产物", None
            return self._save(db, job, "cancelled")

    def events_after(self, job_id: str, event_id: int) -> list[dict[str, Any]]:
        with self.connection() as db:
            rows = db.execute("SELECT event_id,body FROM events WHERE job_id=? AND event_id>? ORDER BY event_id LIMIT 1000",
                              (job_id, event_id)).fetchall()
        return [{"event_id": row[0], "payload": json.loads(row[1])} for row in rows]

    def put_artifact(self, job_id: str, artifact: Artifact, path: Path) -> None:
        path = path.resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("产物必须保存在任务运行目录")
        with self.connection() as db:
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (artifact.artifact_id, job_id, str(path), artifact.model_dump_json()))

    def artifact_path(self, artifact_id: str) -> tuple[Path, Artifact, str]:
        with self.connection() as db:
            row = db.execute("SELECT path,body,job_id FROM artifacts WHERE artifact_id=?", (artifact_id,)).fetchone()
        if not row:
            raise NotFound("产物不存在")
        path = Path(row[0]).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise NotFound("产物文件缺失")
        return path, Artifact.model_validate_json(row[1]), row[2]

    def add_asset(self, job_id: str, asset: Asset, artifact: Artifact, metadata: dict[str, Any]) -> Job:
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            self.check_editable(db, job, None)
            db.execute("INSERT INTO asset_metadata VALUES(?,?)", (asset.asset_id, dumps(metadata)))
            if asset.role == "audio":
                db.execute("INSERT INTO job_inputs VALUES(?,'active_audio_asset_id',?) ON CONFLICT(job_id,key) DO UPDATE SET value=excluded.value",
                           (job_id, asset.asset_id))
            job.assets.append(asset)
            job.revision += 1
            job.script_discussion = None
            job.status, job.stage, job.message = "DRAFT", "idle", "素材已导入，旧成片审核已失效"
            job.review, job.pending_input, job.timeline = None, None, None
            job.artifacts = [a for a in job.artifacts if a.kind not in {
                "preview", "final", "cover", "timeline", "review", "package", "script_discussion",
                "director_shot_review", "shot_review_frame",
            }]
            job.artifacts.append(artifact)
            if job.script:
                job.script.revision = job.revision
            return self._save(db, job, "asset_uploaded")

    def attach_generated_audio(self, job_id: str, revision: int, asset: Asset, artifact: Artifact, metadata: dict[str, Any]) -> Job:
        """Graph attachment and timing provenance are one SQLite transaction."""
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            if job.revision != revision or job.status == "CANCELLED":
                raise Conflict("配音输入版本失效或任务已取消")
            db.execute("INSERT INTO asset_metadata VALUES(?,?)", (asset.asset_id, dumps(metadata)))
            db.execute("INSERT INTO job_inputs VALUES(?,'active_audio_asset_id',?) ON CONFLICT(job_id,key) DO UPDATE SET value=excluded.value", (job_id, asset.asset_id))
            job.assets.append(asset)
            job.timeline, job.review = None, None
            invalid = {"preview", "final", "cover", "timeline", "review", "package", "captions", "storyboard", "voice",
                       "director_shot_review", "shot_review_frame"}
            job.artifacts = [item for item in job.artifacts if item.kind not in invalid] + [artifact]
            return self._save(db, job, "voice_created")

    def asset_metadata(self, asset_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT body FROM asset_metadata WHERE asset_id=?", (asset_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def update_asset_metadata(self, asset_id: str, metadata: dict[str, Any]) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO asset_metadata VALUES(?,?) ON CONFLICT(asset_id) DO UPDATE SET body=excluded.body", (asset_id, dumps(metadata)))

    def update_artifact_metadata(self, artifact_id: str, metadata: dict[str, Any]) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO artifact_metadata VALUES(?,?) ON CONFLICT(artifact_id) DO UPDATE SET body=excluded.body", (artifact_id, dumps(metadata)))

    def artifact_metadata(self, artifact_id: str) -> dict[str, Any]:
        with self.connection() as db:
            row = db.execute("SELECT body FROM artifact_metadata WHERE artifact_id=?", (artifact_id,)).fetchone()
        return json.loads(row[0]) if row else {}

    def set_alignment(self, job_id: str, base_revision: int, asset_id: str, metadata: dict[str, Any], transform: Any) -> Job:
        with self.connection(immediate=True) as db:
            job = self._get(db, job_id)
            self.check_editable(db, job, base_revision)
            db.execute("INSERT INTO asset_metadata VALUES(?,?) ON CONFLICT(asset_id) DO UPDATE SET body=excluded.body", (asset_id, dumps(metadata)))
            db.execute("INSERT INTO job_inputs VALUES(?,'active_audio_asset_id',?) ON CONFLICT(job_id,key) DO UPDATE SET value=excluded.value",
                       (job_id, asset_id))
            return self._save(db, transform(job), "alignment_updated")

    def active_audio(self, job_id: str) -> str | None:
        with self.connection() as db:
            row = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key='active_audio_asset_id'", (job_id,)).fetchone()
        return row[0] if row else None

    def active_command_id(self, job_id: str) -> str:
        with self.connection() as db:
            row = db.execute("SELECT command_id FROM commands WHERE job_id=? AND status='CLAIMED' ORDER BY created_at DESC LIMIT 1", (job_id,)).fetchone()
        return row[0] if row else ""

    def select_audio(self, job_id: str, asset_id: str) -> None:
        with self.connection() as db:
            db.execute("INSERT INTO job_inputs VALUES(?,'active_audio_asset_id',?) ON CONFLICT(job_id,key) DO UPDATE SET value=excluded.value", (job_id, asset_id))

    def setting_values(self) -> dict[str, str]:
        with self.connection() as db:
            return {row[0]: row[1] for row in db.execute("SELECT key,value FROM settings")}

    def write_settings(self, values: dict[str, str]) -> None:
        with self.connection(immediate=True) as db:
            for key, value in values.items():
                db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def reserve_metric(self, job_id: str, revision: int, metric: str, amount: int, limit: int) -> int:
        with self.connection(immediate=True) as db:
            row = db.execute("SELECT value FROM run_metrics WHERE job_id=? AND revision=? AND metric=?", (job_id, revision, metric)).fetchone()
            total = (row[0] if row else 0) + amount
            if total > limit:
                raise Conflict(f"{metric} 已达到本任务配置限额")
            db.execute("INSERT INTO run_metrics VALUES(?,?,?,?) ON CONFLICT(job_id,revision,metric) DO UPDATE SET value=excluded.value",
                       (job_id, revision, metric, total))
            return total

    def operation(self, job_id: str, input_hash: str, provider: str) -> dict[str, Any] | None:
        with self.connection() as db:
            row = db.execute("SELECT operation_id,status,body FROM operations WHERE job_id=? AND input_hash=? AND provider=?",
                             (job_id, input_hash, provider)).fetchone()
        return {"operation_id": row[0], "status": row[1], **json.loads(row[2])} if row else None

    def latest_completed_operation(self, job_id: str, provider: str, revision: int) -> dict[str, Any] | None:
        """Return only this task/version's recorded result for node-owned repair."""
        with self.connection() as db:
            rows = db.execute("SELECT operation_id,body FROM operations WHERE job_id=? AND provider=? "
                              "AND status='COMPLETED' ORDER BY rowid DESC", (job_id, provider)).fetchall()
        for row in rows:
            body = json.loads(row["body"])
            if body.get("revision") == revision and isinstance(body.get("result"), dict):
                return {"operation_id": row["operation_id"], **body}
        return None

    def unsettled_operation(self, job_id: str, provider: str, revision: int,
                            search_scope: str | None = None) -> dict[str, Any] | None:
        """Unknown logical role submission is a barrier even if evidence refreshed."""
        with self.connection() as db:
            rows = db.execute("SELECT operation_id,status,body FROM operations WHERE job_id=? AND provider=? AND status IN ('SUBMITTING','UNKNOWN')",
                              (job_id, provider)).fetchall()
        for row in rows:
            body = json.loads(row[2])
            if body.get("revision", revision) == revision and (
                search_scope is None or body.get("search_scope", search_scope) == search_scope
            ):
                return {"operation_id": row[0], "status": row[1], **body}
        return None

    def start_operation(self, job_id: str, input_hash: str, provider: str, body: dict[str, Any]) -> dict[str, Any]:
        with self.connection(immediate=True) as db:
            existing = db.execute("SELECT operation_id,status,body FROM operations WHERE job_id=? AND input_hash=? AND provider=?",
                                  (job_id, input_hash, provider)).fetchone()
            if existing:
                return {"operation_id": existing[0], "status": existing[1], **json.loads(existing[2])}
            operation_id = uuid.uuid4().hex
            db.execute("INSERT INTO operations VALUES(?,?,?,?,'SUBMITTING',?)", (operation_id, job_id, input_hash, provider, dumps(body)))
            return {"operation_id": operation_id, "status": "SUBMITTING", **body, "new": True}

    def finish_operation(self, operation_id: str, status: str, body: dict[str, Any]) -> None:
        with self.connection() as db:
            db.execute("UPDATE operations SET status=?,body=? WHERE operation_id=?", (status, dumps(body), operation_id))

    def retry_rejected_operation(self, operation_id: str, command_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """Only a different explicit command can retry proven non-acceptance."""
        with self.connection(immediate=True) as db:
            row = db.execute("SELECT status,body FROM operations WHERE operation_id=?", (operation_id,)).fetchone()
            previous = json.loads(row[1]) if row else {}
            if not row or row[0] != "REJECTED" or previous.get("command_id") == command_id:
                raise Conflict("此提交不能自动重试；未知提交必须先对账")
            value = {**body, "command_id": command_id, "attempt": previous.get("attempt", 1) + 1,
                     "previous_rejection": {"http_status": previous.get("http_status"), "provider_code": previous.get("provider_code"), "request_id": previous.get("request_id")}}
            db.execute("UPDATE operations SET status='SUBMITTING',body=? WHERE operation_id=?", (dumps(value), operation_id))
            return {"operation_id": operation_id, "status": "SUBMITTING", **value, "new": True}
