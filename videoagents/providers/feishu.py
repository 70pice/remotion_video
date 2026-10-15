"""Feishu Bitable as the human review surface; the engine stays authoritative.

一个视频一个多维表格(飞书 Base),四张数据表:文案、素材清单、镜头编排、审核记录。
引擎在人工门前把内容幂等同步出去;人工在表格里改「审核记录」的结论与意见;
CLI 的 poll 命令读回决定并走既有 resume 通道。飞书不可用时命令行 decide 兜底,
任务永不因表格故障丢失。所有访问通过本机 lark-cli 子进程,不新增应用密钥。
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from videoagents.contracts import Asset, Job
from videoagents.providers.cli_runner import executable_prefix
from videoagents.services.material_selection import selection_receipts

SCRIPT_TABLE = "文案"
ASSETS_TABLE = "素材清单"
SHOTS_TABLE = "镜头编排"
REVIEW_TABLE = "审核记录"
REVIEW_STAGE_SCRIPT = "文案与素材"
REVIEW_STAGE_SCRIPT_ONLY = "文案"
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
    {"name": "修改意见", "type": "text"},
]
_ASSET_FIELDS = [
    {"name": "素材ID", "type": "text"},
    {"name": "名称", "type": "text"},
    {"name": "类型", "type": "text"},
    {"name": "用途", "type": "text"},
    {"name": "来源URL", "type": "text"},
    {"name": "许可说明", "type": "text"},
    {"name": "采纳状态", "type": "text"},
    {"name": "采纳意见", "type": "text"},
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
     "options": [{"name": REVIEW_STAGE_SCRIPT_ONLY}, {"name": REVIEW_STAGE_SCRIPT}, {"name": REVIEW_STAGE_SHOTS}]},
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
        # The CLI accepts files under cwd, account temp or ~/files. A runtime
        # may belong to another worktree: stage exact bytes in its documented
        # temp root rather than changing the CLI's file-access policy.
        upload = "+record-upload-attachment" in arguments and "--file" in arguments
        staging = tempfile.TemporaryDirectory(prefix="videoagents-lark-") if upload else nullcontext(None)
        with staging as directory:
            argv = list(arguments)
            if directory:
                for index, flag in enumerate(arguments[:-1]):
                    if flag == "--file":
                        source = Path(arguments[index + 1])
                        target = Path(directory) / str(index) / source.name
                        target.parent.mkdir()
                        shutil.copyfile(source, target)
                        argv[index + 1] = str(target)
            result = subprocess.run([*prefix, *argv, "--format", "json", "--as", "user"], capture_output=True, text=True,
                                    encoding="utf-8", timeout=timeout, check=False, shell=False,
                                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except (OSError, subprocess.SubprocessError) as exc:
        raise FeishuUnavailable("lark-cli 无法执行；请检查本机 CLI 和上传文件") from exc
    if result.returncode != 0:
        hint = "请检查用户授权与权限"
        try:
            payload = json.loads(result.stderr or result.stdout)
        except ValueError:
            payload = None
        error = payload.get("error") if isinstance(payload, dict) and payload.get("ok") is False else None
        if isinstance(error, dict) and error.get("type") == "authorization" and error.get("subtype") == "missing_scope":
            scopes = error.get("missing_scopes")
            if (isinstance(scopes, list) and 1 <= len(scopes) <= 50
                    and all(isinstance(scope, str) and len(scope) <= 128
                            and re.fullmatch(r"[a-z][a-z0-9_]{0,31}(?::[a-z][a-z0-9_.]{0,63}){1,3}", scope)
                            for scope in scopes)):
                hint = "缺少用户授权权限（missing_scope）：" + ", ".join(dict.fromkeys(scopes)) + "；请补充这些权限后再同步"
        raise FeishuUnavailable(f"lark-cli 用户身份调用失败（退出码 {result.returncode}）；{hint}")
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise FeishuUnavailable("lark-cli 返回了无法解析的输出") from exc


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    # Current CLI JSON is the Base v3 parallel-array matrix, not nested rows.
    data = payload if "record_id_list" in payload else payload.get("data", payload)
    if not isinstance(data, dict):
        raise FeishuUnavailable("飞书记录返回格式不完整，停止同步以免重复创建")
    if data.get("ignored_fields"):
        raise FeishuUnavailable("飞书未返回请求的字段，停止同步以免重复创建")
    if "record_id_list" in data:
        fields, ids, rows = data.get("fields"), data["record_id_list"], data.get("data")
        if (not isinstance(fields, list) or not all(isinstance(field, str) for field in fields)
                or len(fields) != len(set(fields))
                or not isinstance(ids, list) or not all(isinstance(rid, str) and rid for rid in ids)
                or not isinstance(rows, list) or len(ids) != len(rows)
                or any(not isinstance(row, list) or len(row) != len(fields) for row in rows)):
            raise FeishuUnavailable("飞书记录矩阵不完整，停止同步以免重复创建")
        return [{"record_id": rid, "fields": dict(zip(fields, row, strict=True))}
                for rid, row in zip(ids, rows, strict=True)]
    for key in ("items", "records"):
        if isinstance(data.get(key), list):
            return data[key]
    raise FeishuUnavailable("飞书记录返回格式不完整，停止同步以免重复创建")


class FeishuReviewBase:
    """One video, one Base; keyed updates preserve record IDs and human fields."""

    def __init__(self, repository, folder_token: str, *, allow_root_creation: bool = False):
        self.repo = repository
        self.folder_token = (folder_token or "").strip()
        self.allow_root_creation = allow_root_creation

    def base_token(self, job_id: str) -> str | None:
        with self.repo.connection() as db:
            row = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key='feishu_base_token'",
                             (job_id,)).fetchone()
        return row[0] if row else None

    def ensure_base(self, job: Job) -> str:
        existing = self.base_token(job.job_id)
        if existing:
            self._ensure_script_stage(job.job_id, existing)
            return existing
        if not self.folder_token and not self.allow_root_creation:
            raise FeishuUnavailable("未配置 feishu_folder_token，无法创建飞书表格")
        name = f"video-{job.job_id[:8]}-{(job.brief.topic or 'untitled')[:24]}"
        arguments = ["base", "+base-create", "--name", name, "--table-name", REVIEW_TABLE,
                     "--fields", json.dumps(_REVIEW_FIELDS, ensure_ascii=False)]
        if self.folder_token:
            arguments.extend(["--folder-token", self.folder_token])
        created = _run(arguments)
        data = created.get("data", created)
        base = data.get("base") or data.get("app") or data
        token = base.get("base_token") or base.get("app_token")
        if not token:
            raise FeishuUnavailable("创建飞书表格未返回 app_token")
        for table, fields in ((SCRIPT_TABLE, _SCRIPT_FIELDS), (ASSETS_TABLE, _ASSET_FIELDS),
                              (SHOTS_TABLE, _SHOT_FIELDS)):
            _run(["base", "+table-create", "--base-token", token, "--name", table,
                  "--fields", json.dumps(fields, ensure_ascii=False)])
        with self.repo.connection() as db:
            db.execute("INSERT OR REPLACE INTO job_inputs(job_id, key, value) VALUES(?, 'feishu_base_token', ?)",
                       (job.job_id, token))
            db.execute("INSERT OR REPLACE INTO job_inputs(job_id, key, value) VALUES(?, 'feishu_script_stage_ready', ?)",
                       (job.job_id, token))
        return token

    def _ensure_script_stage(self, job_id: str, token: str) -> None:
        """Check an old Base read-only; never replace its select identities."""
        with self.repo.connection() as db:
            ready = db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key='feishu_script_stage_ready'",
                               (job_id,)).fetchone()
        if ready and ready[0] == token:
            return
        table_id = self._table_id(token, REVIEW_TABLE)
        payload = _run(["base", "+field-get", "--base-token", token, "--table-id", table_id,
                        "--field-id", "阶段"])
        data = payload.get("data", payload)
        field = data.get("field", data)
        if field.get("type") != "select" or not isinstance(field.get("options"), list):
            raise FeishuUnavailable("审核记录的阶段字段不是可扩展的单选配置")
        if not any(item.get("name") == REVIEW_STAGE_SCRIPT_ONLY for item in field["options"]):
            raise FeishuUnavailable("旧飞书表格缺少“文案”审核阶段；任务已保留人工待办，可用 CLI resume 兜底")
        with self.repo.connection() as db:
            db.execute("INSERT OR REPLACE INTO job_inputs(job_id, key, value) VALUES(?, 'feishu_script_stage_ready', ?)",
                       (job_id, token))

    def _table_id(self, token: str, table: str) -> str:
        listing = _run(["base", "+table-list", "--base-token", token])
        data = listing.get("data", listing)
        tables = data.get("tables", data.get("items", []))
        for item in tables:
            if item.get("name") == table:
                table_id = item.get("table_id") or item.get("id")
                if table_id:
                    return table_id
        raise FeishuUnavailable(f"飞书表格中找不到数据表 {table}")

    def _ensure_script_feedback_field(self, token: str, table_id: str) -> None:
        payload = _run(["base", "+field-list", "--base-token", token, "--table-id", table_id])
        data = payload.get("data", payload)
        fields = data.get("fields", data.get("items"))
        if not isinstance(fields, list):
            raise FeishuUnavailable("无法读取文案字段，停止修改表结构")
        matching = [field for field in fields if field.get("name") == "修改意见"]
        if matching:
            if len(matching) != 1 or matching[0].get("type") != "text":
                raise FeishuUnavailable("文案“修改意见”字段须为唯一文本字段，保留现有数据")
            return
        _run(["base", "+field-create", "--base-token", token, "--table-id", table_id,
              "--json", json.dumps({"name": "修改意见", "type": "text"}, ensure_ascii=False)])

    def _list_records(self, token: str, table_id: str, fields: list[str]) -> list[dict[str, Any]]:
        arguments = ["base", "+record-list", "--base-token", token, "--table-id", table_id, "--limit", "200"]
        for field in fields:
            arguments.extend(["--field-id", field])
        records, offset, revision = [], 0, None
        for _ in range(100):
            payload = _run([*arguments, "--offset", str(offset)])
            page = _records(payload)
            data = payload if "record_id_list" in payload else payload.get("data", payload)
            if revision is not None and data.get("rev") != revision:
                raise FeishuUnavailable("飞书记录在分页期间发生变化，请重新同步")
            revision = data.get("rev")
            records.extend(page)
            if not data.get("has_more", False):
                return records
            next_offset = data.get("next_offset", offset + len(page))
            if not isinstance(next_offset, int) or next_offset <= offset:
                raise FeishuUnavailable("飞书记录分页不完整，停止同步")
            offset = next_offset
        raise FeishuUnavailable("飞书记录分页超过同步上限，停止同步")

    def _ensure_material_selection_fields(self, token: str, table_id: str) -> None:
        payload = _run(["base", "+field-list", "--base-token", token, "--table-id", table_id])
        data = payload.get("data", payload)
        fields = data.get("fields", data.get("items"))
        if not isinstance(fields, list):
            raise FeishuUnavailable("无法读取素材字段，停止修改表结构")
        for name in ("采纳状态", "采纳意见"):
            matches = [field for field in fields if field.get("name") == name]
            if matches:
                if len(matches) != 1 or matches[0].get("type") != "text":
                    raise FeishuUnavailable(f"素材“{name}”字段须为唯一文本字段，保留现有数据")
            else:
                _run(["base", "+field-create", "--base-token", token, "--table-id", table_id,
                      "--json", json.dumps({"name": name, "type": "text"}, ensure_ascii=False)])

    def _rewrite_table(self, token: str, table: str, key_field: str, records: list[dict[str, Any]],
                       attachments: dict[str, str] | None = None, attachment_field: str = "",
                       *, preserve_attachments: bool = False, require_attachments: bool = False) -> None:
        """Update managed fields by key; keep human fields, comments and old rows."""
        table_id = self._table_id(token, table)
        if table == SCRIPT_TABLE:
            self._ensure_script_feedback_field(token, table_id)
        by_key = {}
        for item in self._list_records(token, table_id, [key_field]):
            key = _plain(item.get("fields", {}).get(key_field))
            if key:
                if key in by_key or not item.get("record_id"):
                    raise FeishuUnavailable(f"飞书 {table} 的 {key_field} 重复或记录ID缺失，停止同步")
                by_key[key] = item["record_id"]
        payload = [{key: value for key, value in row.items() if not key.startswith("_")} for row in records]
        keys = [_plain(row.get(key_field)) for row in payload]
        if any(not key for key in keys) or len(keys) != len(set(keys)):
            raise FeishuUnavailable(f"待同步 {table} 的 {key_field} 为空或重复")
        updates = {by_key[key]: row for key, row in zip(keys, payload, strict=True) if key in by_key}
        creates = [row for key, row in zip(keys, payload, strict=True) if key not in by_key]
        if updates:
            _run(["base", "+record-batch-update", "--base-token", token, "--table-id", table_id,
                  "--json", json.dumps({"update_records": updates}, ensure_ascii=False)])
        if creates:
            _run(["base", "+record-batch-create", "--base-token", token, "--table-id", table_id,
                  "--json", json.dumps({"create_records": creates}, ensure_ascii=False)])
        if attachments:
            fields = [key_field, attachment_field] if preserve_attachments else [key_field]
            rows = self._list_records(token, table_id, fields)
            by_key = {_plain(item.get("fields", {}).get(key_field)): item.get("record_id") for item in rows}
            attached = {_plain(item.get("fields", {}).get(key_field)) for item in rows
                        if preserve_attachments and item.get("fields", {}).get(attachment_field)}
            for key, path in attachments.items():
                if key in attached:
                    continue
                record_id = by_key.get(key)
                if not record_id:
                    if require_attachments:
                        raise FeishuUnavailable(f"飞书 {table} 的 {key} 记录缺失，无法上传附件")
                    continue
                try:
                    _run(["base", "+record-upload-attachment", "--base-token", token, "--table-id", table_id,
                          "--record-id", record_id, "--field-id", attachment_field, "--file", path], timeout=180)
                except FeishuUnavailable as exc:
                    if require_attachments:
                        raise FeishuUnavailable(f"飞书 {table} 的 {key} 附件上传失败：{exc}") from exc
                    # Material paths still surface via the CLI.
                    continue

    def sync_script(self, job: Job) -> str:
        """Present narration and sources before any collection is required."""
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
        return token

    def sync_script_and_assets(self, job: Job) -> str:
        token = self.sync_script(job)
        asset_rows, attachments = [], {}
        selections = selection_receipts(self.repo, job)
        decisions, historic_assets = {}, {}
        for receipt in selections:
            for asset in receipt["subject"]["assets"]:
                historic_assets[asset["asset_id"]] = Asset.model_validate(asset)
            for key in receipt["accepted_asset_ids"]:
                decisions[key] = ("保留", receipt["note"])
            for key in receipt["rejected_asset_ids"]:
                decisions[key] = ("不采用", receipt["note"])
        assets = {key: historic_assets[key] for key in decisions}
        assets.update({asset.asset_id: asset for asset in job.assets})
        if selections:
            self._ensure_material_selection_fields(token, self._table_id(token, ASSETS_TABLE))
        for asset in assets.values():
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
                **({"采纳状态": decisions.get(asset.asset_id, ("待审", ""))[0],
                    "采纳意见": decisions.get(asset.asset_id, ("待审", ""))[1]} if selections else {}),
            })
            if path:
                attachments[key] = str(path)
        self._rewrite_table(token, ASSETS_TABLE, "素材ID", asset_rows, attachments, "文件",
                            preserve_attachments=True)
        if selections:
            table_id = self._table_id(token, REVIEW_TABLE)
            review_rows = {_plain(row.get("fields", {}).get("待办令牌")): row
                           for row in self._list_records(token, table_id, ["待办令牌", "审核要求"])}
            for receipt in selections:
                row = review_rows.get(receipt["pending_token"])
                if row and row.get("record_id"):
                    # This settles only a partial selection, never the full
                    # gate. Human opinions/comments and select values survive.
                    explanation = "本待办已记录素材部分取舍；请审核新的待办，整包未确认。\n" + receipt["note"]
                    requirements = (_plain(row.get("fields", {}).get("审核要求"))
                                    or "\n".join(receipt["confirmation_requirements"]))
                    if explanation not in requirements:
                        requirements += "\n" + explanation
                    fields = {"标题": f"{job.brief.topic[:60]} · 文案与素材 · 部分取舍已记录（整包未通过）",
                              "审核要求": requirements}
                    _run(["base", "+record-batch-update", "--base-token", token, "--table-id", table_id,
                          "--json", json.dumps({"update_records": {row["record_id"]: fields}}, ensure_ascii=False)])
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
            if not artifact_id:
                raise FeishuUnavailable(f"逐镜 {shot_id} 缺少代表帧产物")
            try:
                path, _, _ = self.repo.artifact_path(artifact_id)
            except (ValueError, OSError) as exc:
                raise FeishuUnavailable(f"逐镜 {shot_id} 代表帧文件缺失") from exc
            attachments[shot_id] = str(path)
        self._rewrite_table(token, SHOTS_TABLE, "镜头ID", rows, attachments, "代表帧", require_attachments=True)
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
