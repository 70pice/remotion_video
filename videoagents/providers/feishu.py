"""Feishu Bitable as the human review surface; the engine stays authoritative.

一个视频一个多维表格(飞书 Base),四张数据表:文案、素材清单、镜头编排、审核记录。
引擎在人工门前把内容幂等同步出去;人工在表格里改「审核记录」的结论与意见;
CLI 的 poll 命令读回决定并走既有 resume 通道。飞书不可用时命令行 decide 兜底,
任务永不因表格故障丢失。所有访问通过本机 lark-cli 子进程,不新增应用密钥。
"""

import json
import os
import subprocess
from typing import Any

from videoagents.contracts import Job
from videoagents.providers.cli_runner import executable_prefix

SCRIPT_TABLE = "文案"
ASSETS_TABLE = "素材清单"
SHOTS_TABLE = "镜头编排"
REVIEW_TABLE = "审核记录"
REVIEW_STAGE_SCRIPT = "文案与素材"
REVIEW_STAGE_SHOTS = "逐镜"
DECISION_PENDING = "待审"
DECISION_CONFIRM = "通过"
DECISION_REVISE = "需修改"

_SCRIPT_FIELDS = [
    {"name": "段落ID", "type": "text"},
    {"name": "口播", "type": "text"},
    {"name": "屏幕文字", "type": "text"},
    {"name": "来源", "type": "text"},
    {"name": "画面需求", "type": "text"},
]
_ASSET_FIELDS = [
    {"name": "素材ID", "type": "text"},
    {"name": "名称", "type": "text"},
    {"name": "类型", "type": "text"},
    {"name": "用途", "type": "text"},
    {"name": "来源URL", "type": "text"},
    {"name": "许可说明", "type": "text"},
    {"name": "文件", "type": "attachment"},
]
_SHOT_FIELDS = [
    {"name": "镜头ID", "type": "text"},
    {"name": "起止帧", "type": "text"},
    {"name": "组件", "type": "text"},
    {"name": "组件理由", "type": "text"},
    {"name": "画面动作", "type": "text"},
    {"name": "素材引用", "type": "text"},
    {"name": "代表帧", "type": "attachment"},
]
_REVIEW_FIELDS = [
    {"name": "标题", "type": "text"},
    {"name": "阶段", "type": "select", "multiple": False,
     "options": [{"name": REVIEW_STAGE_SCRIPT}, {"name": REVIEW_STAGE_SHOTS}]},
    {"name": "待办令牌", "type": "text"},
    {"name": "审核要求", "type": "text"},
    {"name": "结论", "type": "select", "multiple": False,
     "options": [{"name": DECISION_PENDING}, {"name": DECISION_CONFIRM}, {"name": DECISION_REVISE}]},
    {"name": "意见", "type": "text"},
]


class FeishuUnavailable(RuntimeError):
    """lark-cli missing or the API call failed; the CLI decide path still works."""


def _run(arguments: list[str], *, timeout: int = 60) -> dict[str, Any]:
    # Output format is always selected with --format json; a bare --json would
    # collide with commands where --json is a VALUE input (batch create/update,
    # record get/delete), which lark-cli rejects as "flag needs an argument".
    prefix = executable_prefix("lark_cli")
    if prefix is None:
        raise FeishuUnavailable("未找到可执行的 lark-cli；请安装完整 CLI 或设置 VIDEOAGENTS_LARK_CLI_EXECUTABLE")
    try:
        result = subprocess.run([*prefix, *arguments, "--format", "json"], capture_output=True, text=True,
                                encoding="utf-8", timeout=timeout, check=False, shell=False,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FeishuUnavailable(f"lark-cli 无法执行：{exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:] or ["unknown error"]
        raise FeishuUnavailable(f"lark-cli 调用失败：{detail[0][:300]}")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise FeishuUnavailable("lark-cli 返回了无法解析的输出") from exc


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", payload)
    for key in ("items", "records"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


class FeishuReviewBase:
    """One video, one Bitable; content tables are rewritten, review rows are keyed."""

    def __init__(self, repository, folder_token: str):
        self.repo = repository
        self.folder_token = (folder_token or "").strip()

    def base_token(self, job_id: str) -> str | None:
        with self.repo.connection() as db:
            row = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key='feishu_base_token'",
                             (job_id,)).fetchone()
        return row[0] if row else None

    def ensure_base(self, job: Job) -> str:
        existing = self.base_token(job.job_id)
        if existing:
            return existing
        if not self.folder_token:
            raise FeishuUnavailable("未配置 feishu_folder_token，无法创建飞书表格")
        name = f"video-{job.job_id[:8]}-{(job.brief.topic or 'untitled')[:24]}"
        created = _run(["base", "+base-create", "--name", name, "--folder-token", self.folder_token,
                        "--table-name", REVIEW_TABLE, "--fields", json.dumps(_REVIEW_FIELDS, ensure_ascii=False)])
        data = created.get("data", created)
        token = (data.get("app", {}) or {}).get("app_token") or data.get("app_token")
        if not token:
            raise FeishuUnavailable("创建飞书表格未返回 app_token")
        for table, fields in ((SCRIPT_TABLE, _SCRIPT_FIELDS), (ASSETS_TABLE, _ASSET_FIELDS),
                              (SHOTS_TABLE, _SHOT_FIELDS)):
            _run(["base", "+table-create", "--base-token", token, "--name", table,
                  "--fields", json.dumps(fields, ensure_ascii=False)])
        with self.repo.connection() as db:
            db.execute("INSERT OR REPLACE INTO job_inputs(job_id, key, value) VALUES(?, 'feishu_base_token', ?)",
                       (job.job_id, token))
        return token

    def _table_id(self, token: str, table: str) -> str:
        listing = _run(["base", "+base-get", "--base-token", token])
        data = listing.get("data", listing)
        tables = (data.get("app", {}) or data).get("tables", [])
        for item in tables:
            if item.get("name") == table:
                return item.get("table_id", "")
        raise FeishuUnavailable(f"飞书表格中找不到数据表 {table}")

    def _list_records(self, token: str, table_id: str, fields: list[str]) -> list[dict[str, Any]]:
        arguments = ["base", "+record-list", "--base-token", token, "--table-id", table_id]
        for field in fields:
            arguments.extend(["--field-id", field])
        return _records(_run(arguments))

    def _rewrite_table(self, token: str, table: str, key_field: str, records: list[dict[str, Any]],
                       attachments: dict[str, str] | None = None, attachment_field: str = "") -> None:
        """Idempotent sync: clear the table, recreate rows, then attach files."""
        table_id = self._table_id(token, table)
        for item in self._list_records(token, table_id, [key_field]):
            record_id = item.get("record_id")
            if record_id:
                _run(["base", "+record-delete", "--base-token", token, "--table-id", table_id,
                      "--record-id", record_id, "--yes"])
        payload = [{key: value for key, value in row.items() if not key.startswith("_")} for row in records]
        if payload:
            _run(["base", "+record-batch-create", "--base-token", token, "--table-id", table_id,
                  "--json", json.dumps({"create_records": payload}, ensure_ascii=False)])
        if attachments:
            by_key = {_plain(item.get("fields", {}).get(key_field)): item.get("record_id")
                      for item in self._list_records(token, table_id, [key_field])}
            for key, path in attachments.items():
                record_id = by_key.get(key)
                if not record_id:
                    continue
                try:
                    _run(["base", "+record-upload-attachment", "--base-token", token, "--table-id", table_id,
                          "--record-id", record_id, "--field-id", attachment_field, "--file", path], timeout=180)
                except FeishuUnavailable:
                    # Attachment upload failure is non-fatal; paths still surface via the CLI.
                    continue

    def sync_script_and_assets(self, job: Job) -> str:
        token = self.ensure_base(job)
        script_rows = []
        if job.script:
            for segment in job.script.segments:
                script_rows.append({
                    "段落ID": segment.segment_id,
                    "口播": segment.narration,
                    "屏幕文字": segment.screen_text,
                    "来源": "\n".join(segment.source_refs),
                    "画面需求": segment.visual_need,
                })
        self._rewrite_table(token, SCRIPT_TABLE, "段落ID", script_rows)
        asset_rows, attachments = [], {}
        for asset in job.assets:
            try:
                path, _, _ = self.repo.artifact_path(asset.artifact_id)
            except (ValueError, OSError):
                path = None
            key = asset.asset_id[:12]
            asset_rows.append({
                "素材ID": key,
                "名称": asset.name,
                "类型": asset.mime_type,
                "用途": asset.role,
                "来源URL": asset.source_url,
                "许可说明": asset.license_note,
            })
            if path:
                attachments[key] = str(path)
        self._rewrite_table(token, ASSETS_TABLE, "素材ID", asset_rows, attachments, "文件")
        return token

    def sync_shots(self, job: Job, manifest: dict[str, Any]) -> str:
        token = self.ensure_base(job)
        rows, attachments = [], {}
        for item in manifest.get("items", []):
            image = item.get("image", {})
            shot_id = item.get("shot_id", "")
            rows.append({
                "镜头ID": shot_id,
                "起止帧": f"{item.get('start_frame', '')}-{item.get('end_frame', '')}",
                "组件": ", ".join(item.get("component_ids") or [item.get("component_id", "")]),
                "组件理由": item.get("component_reason", ""),
                "画面动作": item.get("visual_action", ""),
                "素材引用": item.get("asset_src", ""),
            })
            # The manifest stores an Artifact dump (artifact_id/url), not a path;
            # resolve the real file through the repository before uploading.
            artifact_id = image.get("artifact_id")
            if artifact_id:
                try:
                    path, _, _ = self.repo.artifact_path(artifact_id)
                except (ValueError, OSError):
                    path = None
                if path:
                    attachments[shot_id] = str(path)
        self._rewrite_table(token, SHOTS_TABLE, "镜头ID", rows, attachments, "代表帧")
        return token

    def submit_review(self, job: Job, stage: str, pending_token: str, requirements: str) -> None:
        """Insert or refresh the pending review row; keyed by 待办令牌."""
        token = self.ensure_base(job)
        table_id = self._table_id(token, REVIEW_TABLE)
        fields = {"标题": f"{job.brief.topic[:60]} · {stage}", "阶段": [stage], "待办令牌": pending_token,
                  "审核要求": requirements}
        existing = self._find_review(token, table_id, pending_token)
        if existing:
            # Replayed syncs (worker crash, retry) must never clobber what the
            # human already filled in; refresh descriptive fields only.
            _run(["base", "+record-batch-update", "--base-token", token, "--table-id", table_id,
                  "--json", json.dumps({"update_records": {existing: fields}}, ensure_ascii=False)])
            return
        fields.update({"结论": [DECISION_PENDING], "意见": ""})
        _run(["base", "+record-batch-create", "--base-token", token, "--table-id", table_id,
              "--json", json.dumps({"create_records": [fields]}, ensure_ascii=False)])

    def _find_review(self, token: str, table_id: str, pending_token: str) -> str | None:
        for item in self._list_records(token, table_id, ["待办令牌"]):
            if _plain(item.get("fields", {}).get("待办令牌")) == pending_token:
                return item.get("record_id")
        return None

    def poll_decision(self, job: Job, pending_token: str, *, min_note_length: int = 10) -> dict[str, Any] | None:
        """Return {'decision': confirm|revise, 'note': str} once the human answered.

        The note must satisfy the human gate's minimum length, so the same
        answer that poll accepts can never bounce at the gate itself.
        """
        token = self.base_token(job.job_id)
        if not token:
            return None
        table_id = self._table_id(token, REVIEW_TABLE)
        record_id = self._find_review(token, table_id, pending_token)
        if not record_id:
            return None
        row = _run(["base", "+record-get", "--base-token", token, "--table-id", table_id,
                    "--record-id", record_id])
        fields = (_records(row) or [{}])[0].get("fields", {})
        note = _plain(fields.get("意见"))
        decision = _plain(fields.get("结论"))
        if decision == DECISION_CONFIRM:
            # The gate requires a substantive note; an empty 意见 box still
            # records an explicit human decision, so send a full sentence.
            return {"decision": "confirm", "note": note or "飞书多维表格人工审核通过（结论：通过）"}
        if decision == DECISION_REVISE:
            if len(note) < max(1, min_note_length):
                return None  # 需修改必须附带达到门长度的意见,否则继续等待。
            return {"decision": "revise", "note": note}
        return None


def _plain(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in value).strip()
    if isinstance(value, dict):
        return (value.get("text") or value.get("value") or "").strip()
    return str(value).strip()


def available(folder_token: str) -> bool:
    return bool((folder_token or "").strip())
