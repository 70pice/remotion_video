"""The Feishu review surface: idempotent sync, keyed review rows, decision polling."""

import json

import pytest

from videoagents.contracts import Brief
from videoagents.providers import feishu
from videoagents.providers.cli_runner import executable_prefix
from videoagents.providers.feishu import FeishuReviewBase, FeishuUnavailable, _plain
from videoagents.storage import Repository


class FakeLark:
    def __init__(self):
        self.calls: list[list[str]] = []
        self.tables: dict[str, list[dict]] = {}
        self.review_rows: dict[str, dict] = {}
        self.next_record = 100
        self.fields: dict[str, list[dict]] = {}
        self.review_stage_field = {"name": "阶段", "type": "select", "multiple": False,
                                   "description": "保留的阶段说明", "default_value": ["逐镜"],
                                   "options": [{"name": feishu.REVIEW_STAGE_SCRIPT, "hue": "Blue"},
                                               {"name": feishu.REVIEW_STAGE_SHOTS}]}

    def __call__(self, arguments, *, timeout=60):
        self.calls.append(arguments)  # noqa: F841 — 调用轨迹供断言使用
        joined = " ".join(arguments)
        if "+base-create" in joined:
            self.tables = {"审核记录": []}
            self.review_stage_field = next(item for item in json.loads(arguments[arguments.index("--fields") + 1])
                                           if item["name"] == "阶段")
            return {"data": {"app": {"app_token": "basetoken123"}}}

        if "+field-get" in joined:
            return {"data": {"field": self.review_stage_field}}
        if "+field-list" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            return {"data": {"fields": self.fields.get(table, [])}}
        if "+field-create" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            field = json.loads(arguments[arguments.index("--json") + 1])
            self.fields.setdefault(table, []).append(field)
            return {"data": {"field": field}}

        if "+table-create" in joined:
            name = arguments[arguments.index("--name") + 1]
            self.tables[name] = []
            self.fields[name] = json.loads(arguments[arguments.index("--fields") + 1])
            return {"data": {"table_id": f"tbl_{name}"}}
        if "+table-list" in joined:
            return {"data": {"tables": [{"name": name, "id": f"tbl_{name}"} for name in self.tables]}}
        if "+base-get" in joined:
            return {"data": {"app": {"tables": [{"name": name, "table_id": f"tbl_{name}"}
                                                for name in self.tables]}}}
        if "+record-list" in joined:
            table = arguments[arguments.index("--table-id") + 1]
            rows = self.tables.get(table.removeprefix("tbl_"), [])
            fields = [a for i, a in enumerate(arguments) if i > 0 and arguments[i - 1] == "--field-id"]
            return {"data": {"items": [{"record_id": r["record_id"],
                                        "fields": {f: r["fields"].get(f) for f in fields}}
                                       for r in rows]}}
        if "+record-delete" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            rid = arguments[arguments.index("--record-id") + 1]
            self.tables[table] = [r for r in self.tables[table] if r["record_id"] != rid]
            return {"data": {}}
        if "+record-batch-create" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            body = json.loads(arguments[arguments.index("--json") + 1])
            for fields in body["create_records"]:
                self.next_record += 1
                self.tables[table].append({"record_id": f"rec{self.next_record}", "fields": fields})
            return {"data": {}}
        if "+record-batch-update" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            body = json.loads(arguments[arguments.index("--json") + 1])
            for rid, fields in body["update_records"].items():
                for row in self.tables[table]:
                    if row["record_id"] == rid:
                        row["fields"].update(fields)
            return {"data": {}}
        if "+record-get" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            rid = arguments[arguments.index("--record-id") + 1]
            row = next(r for r in self.tables[table] if r["record_id"] == rid)
            return {"data": {"items": [row]}}
        if "+record-upload-attachment" in joined:
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            rid = arguments[arguments.index("--record-id") + 1]
            path = arguments[arguments.index("--file") + 1]
            field = arguments[arguments.index("--field-id") + 1]
            row = next(r for r in self.tables[table] if r["record_id"] == rid)
            row["fields"].setdefault(field, []).append(path)
            return {"data": {}}
        raise AssertionError(f"unexpected lark-cli call: {joined}")


@pytest.fixture
def lark(monkeypatch):
    fake = FakeLark()
    monkeypatch.setattr(feishu, "_run", fake)
    return fake


@pytest.fixture
def job(tmp_path):
    repo = Repository(tmp_path / "runtime")
    return repo.create_job(Brief(topic="飞书审核测试", script_text="观点：第一段。\n观点：第二段。"))


def test_ensure_base_creates_once_and_caches_token(lark, tmp_path, job):
    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    token = base.ensure_base(job)
    assert token == "basetoken123"
    created = [c for c in lark.calls if "+base-create" in " ".join(c)]
    assert len(created) == 1
    # Second call reuses the cached token without any lark traffic.
    lark.calls.clear()
    assert base.ensure_base(job) == "basetoken123"
    assert lark.calls == []


def test_missing_folder_token_is_unavailable(tmp_path, job):
    base = FeishuReviewBase(Repository(tmp_path / "runtime"), "")
    with pytest.raises(FeishuUnavailable, match="feishu_folder_token"):
        base.ensure_base(job)


def test_old_base_missing_script_stage_is_read_only_and_keeps_old_options_and_reviews(lark, tmp_path, job):
    repo = Repository(tmp_path / "runtime")
    lark.tables["审核记录"] = [{"record_id": "old", "fields": {"结论": [feishu.DECISION_CONFIRM]}}]
    with repo.connection() as db:
        db.execute("INSERT INTO job_inputs VALUES(?, 'feishu_base_token', 'oldbase')", (job.job_id,))
    old = dict(lark.review_stage_field)
    base = FeishuReviewBase(repo, "fld123")
    with pytest.raises(FeishuUnavailable, match="缺少“文案”"):
        base.ensure_base(job)
    assert lark.review_stage_field == old
    assert lark.tables["审核记录"] == [{"record_id": "old", "fields": {"结论": [feishu.DECISION_CONFIRM]}}]
    assert not any("+record-delete" in call or "+field-update" in call for call in lark.calls)
    # Once the existing schema actually has the option, check and cache it.
    lark.review_stage_field["options"].append({"name": feishu.REVIEW_STAGE_SCRIPT_ONLY})
    assert base.ensure_base(job) == "oldbase"
    lark.calls.clear()
    assert base.ensure_base(job) == "oldbase" and lark.calls == []


def test_sync_script_and_assets_is_idempotent(lark, tmp_path, job):
    repo = Repository(tmp_path / "runtime")
    from videoagents.contracts import Script, ScriptSegment
    script = Script(title="飞书审核测试", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：第一段。",
                                            source_refs=["https://example.com/a"],
                                            visual_need="按本段内容寻找真实画面"),
                              ScriptSegment(segment_id="s2", narration="观点：第二段。",
                                            source_refs=["https://example.com/b"], visual_need="")])
    job = repo.update_job(job.job_id, job.revision, script=script)
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    lark.calls.clear()
    base.sync_script_and_assets(job)
    rows = lark.tables["文案"]
    assert [r["fields"]["段落ID"] for r in rows] == ["s1", "s2"]
    assert rows[0]["fields"]["画面需求"] == "按本段内容寻找真实画面"
    record_ids = [row["record_id"] for row in rows]
    rows[0]["fields"].update({"修改意见": "第一段数字要解释口径", "用户自建字段": "保留"})
    rows[0]["native_comments"] = ["逐段评论跟随记录"]
    script.segments[0].narration = "更新后的第一段。"
    job = repo.update_job(job.job_id, job.revision, script=script)
    base.sync_script_and_assets(job)
    assert len(lark.tables["文案"]) == 2
    assert [row["record_id"] for row in lark.tables["文案"]] == record_ids
    assert rows[0]["fields"]["口播"] == "更新后的第一段。"
    assert rows[0]["fields"]["修改意见"] == "第一段数字要解释口径"
    assert rows[0]["native_comments"] == ["逐段评论跟随记录"]


def test_partial_material_selection_keeps_records_attachments_and_human_opinions(lark, tmp_path, job):
    from videoagents.contracts import Asset, MaterialSelectionRequest, Script, ScriptSegment
    from videoagents.nodes.common import state_context
    from videoagents.nodes.human_review import HumanReviewNode
    from videoagents.services.jobs import JobService

    repo = Repository(tmp_path / "runtime")
    script = Script(title="UNIT", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：UNIT素材选择。")])
    assets, artifacts = [], []
    for index in range(3):
        path = repo.root / "jobs" / job.job_id / f"unit-image-{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"UNIT-{index}".encode())
        artifact = JobService(repo).register_artifact(job, path, "asset", "image/png")
        assets.append(Asset(asset_id=f"{index:08x}-unit-asset", name=path.name, role="evidence",
            mime_type="image/png", size_bytes=artifact.size_bytes, sha256=artifact.sha256,
            artifact_id=artifact.artifact_id, url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/{path.name}"))
        artifacts.append(artifact)
    job = repo.update_job(job.job_id, job.revision, script=script, assets=assets, artifacts=artifacts,
                          status="NEEDS_HUMAN", stage="script")
    state = state_context(repo, {"job_id": job.job_id, "revision": job.revision,
                                "thread_id": "UNIT-partial", "resume_command_id": "UNIT-partial-command"})
    node = HumanReviewNode(repo, node_name="human_review_script", stage="script")
    pending = node._pending(state, job)
    job = repo.update_job(job.job_id, job.revision, pending_input=pending)
    base = FeishuReviewBase(repo, "fld123")
    base.sync_script_and_assets(job)
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, pending["pending_token"], "原审核要求")
    rows = lark.tables["素材清单"]
    record_ids = [row["record_id"] for row in rows]
    for row in rows:
        # Existing real attachments must never be appended/replaced by a
        # selection-only sync, including its rejected historical row.
        row["fields"]["文件"] = [{"file_token": "UNIT-existing-" + row["record_id"]}]
        row["fields"]["用户自建字段"] = "保留"
        row["native_comments"] = ["原人工评论"]
    old_review = lark.tables["审核记录"][0]
    old_review["fields"]["意见"] = "用户填写的取舍意见保留"
    old_review["native_comments"] = ["原审核行评论"]
    # An older Base has no selection schema; migrate only these text fields.
    lark.fields["素材清单"] = [field for field in lark.fields["素材清单"]
                              if field["name"] not in {"采纳状态", "采纳意见"}]
    lark.calls.clear()
    # Resuming the joint gate syncs the old question before the partial
    # decision exists. This sync must also preserve all existing files.
    base.sync_script_and_assets(job)
    assert not any("+record-upload-attachment" in call for call in lark.calls)
    request = MaterialSelectionRequest(base_revision=job.revision, pending_token=pending["pending_token"],
        idempotency_key="UNIT-selection", note="清晰图片保留，低画质不采用；整包仍待审。",
        accepted_asset_ids=[assets[0].asset_id], rejected_asset_ids=[assets[1].asset_id])
    result = node._select_materials(state, job, pending, request.model_dump())
    current = repo.get_job(job.job_id)
    next_pending = node._pending(result, current)
    lark.calls.clear()
    base.sync_script_and_assets(current)
    base.submit_review(current, feishu.REVIEW_STAGE_SCRIPT, next_pending["pending_token"], "新待办仍需整包审核")
    base.sync_script_and_assets(current)
    assert [row["record_id"] for row in rows] == record_ids
    assert [row["fields"]["采纳状态"] for row in rows] == ["保留", "不采用", "待审"]
    assert [row["fields"]["采纳意见"] for row in rows] == [request.note, request.note, ""]
    assert all(row["fields"]["用户自建字段"] == "保留" and row["native_comments"] == ["原人工评论"] for row in rows)
    assert all(row["fields"]["文件"] == [{"file_token": "UNIT-existing-" + row["record_id"]}] for row in rows)
    assert not any("+record-upload-attachment" in call or "+record-delete" in call for call in lark.calls)
    creates = [call for call in lark.calls if "+field-create" in call]
    assert len(creates) == 2
    assert old_review["fields"]["意见"] == "用户填写的取舍意见保留"
    assert old_review["fields"]["结论"] == [feishu.DECISION_PENDING]
    assert "整包未确认" in old_review["fields"]["审核要求"]
    assert old_review["fields"]["审核要求"].startswith("原审核要求\n")
    assert old_review["fields"]["审核要求"].count(request.note) == 1
    assert old_review["native_comments"] == ["原审核行评论"]
    new_review = lark.tables["审核记录"][1]
    assert new_review["fields"]["结论"] == [feishu.DECISION_PENDING]
    assert base.poll_decision(current, next_pending["pending_token"]) is None
    assert rows[0]["fields"]["用户自建字段"] == "保留"
    assert not any("+record-delete" in call for call in lark.calls)


@pytest.mark.parametrize("missing", ["absent", "empty"])
def test_normal_material_sync_preserves_files_and_only_fills_missing_attachments(lark, tmp_path, job, missing):
    from videoagents.contracts import Asset
    from videoagents.services.jobs import JobService

    repo = Repository(tmp_path / "runtime")
    assets = []
    for index in range(2):
        path = repo.root / "jobs" / job.job_id / f"unit-image-{index}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"UNIT-{index}".encode())
        artifact = JobService(repo).register_artifact(job, path, "asset", "image/png")
        assets.append(Asset(asset_id=f"{index:08x}-unit-asset", name=path.name, role="evidence",
            mime_type="image/png", size_bytes=artifact.size_bytes, sha256=artifact.sha256,
            artifact_id=artifact.artifact_id, url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/{path.name}"))
    job = repo.update_job(job.job_id, assets=assets)
    base = FeishuReviewBase(repo, "fld123")
    base.sync_script_and_assets(job)
    rows = lark.tables["素材清单"]
    record_ids = [row["record_id"] for row in rows]
    original_files = [list(row["fields"]["文件"]) for row in rows]
    assert all(len(files) == 1 for files in original_files)
    lark.calls.clear()
    base.sync_script_and_assets(job)
    base.sync_script_and_assets(job)
    assert not any("+record-upload-attachment" in call for call in lark.calls)
    assert [row["fields"]["文件"] for row in rows] == original_files
    if missing == "absent":
        rows[1]["fields"].pop("文件")
    else:
        rows[1]["fields"]["文件"] = []
    lark.calls.clear()
    base.sync_script_and_assets(job)
    uploads = [call for call in lark.calls if "+record-upload-attachment" in call]
    assert len(uploads) == 1
    assert uploads[0][uploads[0].index("--record-id") + 1] == record_ids[1]
    assert [row["fields"]["文件"] for row in rows] == original_files
    assert [row["record_id"] for row in rows] == record_ids
    lark.calls.clear()
    base.sync_script_and_assets(job)
    assert not any("+record-upload-attachment" in call or "+record-delete" in call for call in lark.calls)


def test_script_sync_keeps_removed_and_manual_rows_and_adds_feedback_field_once(lark, tmp_path, job):
    from videoagents.contracts import Script, ScriptSegment

    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    lark.fields["文案"] = [field for field in lark.fields["文案"] if field["name"] != "修改意见"]
    old = {"record_id": "old", "fields": {"段落ID": "old-segment", "修改意见": "保留旧意见"}}
    manual = {"record_id": "manual", "fields": {"段落ID": "", "口播": "用户记录"}}
    lark.tables["文案"] = [old, manual]
    script = Script(title="t", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id=f"s{i}", narration=f"第{i}段。") for i in range(7)])
    job = repo.update_job(job.job_id, job.revision, script=script)
    base.sync_script(job)
    base.sync_script(job)
    assert len(lark.tables["文案"]) == 9
    assert lark.tables["文案"][:2] == [old, manual]
    creates = [call for call in lark.calls if "+field-create" in call]
    assert len(creates) == 1
    assert json.loads(creates[0][creates[0].index("--json") + 1]) == {"name": "修改意见", "type": "text"}


def test_duplicate_segment_ids_refuse_writes(lark, tmp_path, job):
    from videoagents.contracts import Script, ScriptSegment

    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    script = Script(title="t", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="一。")])
    job = repo.update_job(job.job_id, job.revision, script=script)
    lark.tables["文案"] = [{"record_id": rid, "fields": {"段落ID": "s1"}} for rid in ("a", "b")]
    lark.calls.clear()
    with pytest.raises(FeishuUnavailable, match="重复"):
        base.sync_script(job)
    assert not any("+record-batch-create" in call or "+record-batch-update" in call for call in lark.calls)


def test_explicit_root_creation_only(lark, tmp_path, job):
    base = FeishuReviewBase(Repository(tmp_path / "runtime"), "", allow_root_creation=True)
    assert base.ensure_base(job) == "basetoken123"
    created = next(call for call in lark.calls if "+base-create" in call)
    assert "--folder-token" not in created


def test_current_cli_matrix_is_decoded_and_invalid_shape_is_rejected():
    payload = {"ok": True, "data": {"fields": ["段落ID", "修改意见"], "field_id_list": ["fld1", "fld2"],
        "field_type_list": ["text", "text"], "record_id_list": ["rec1", "rec2"],
        "data": [["s1", "第一段说清数字。"], ["s2", None]], "has_more": False, "timezone": "Asia/Shanghai"}}
    assert feishu._records(payload) == [
        {"record_id": "rec1", "fields": {"段落ID": "s1", "修改意见": "第一段说清数字。"}},
        {"record_id": "rec2", "fields": {"段落ID": "s2", "修改意见": None}}]
    payload["data"]["data"] = [["s1"]]
    with pytest.raises(FeishuUnavailable):
        feishu._records(payload)


def test_record_pagination_reads_all_keys_before_upsert(tmp_path, job, monkeypatch):
    base = FeishuReviewBase(Repository(tmp_path / "runtime"), "fld123")
    calls = []

    def paged(arguments, *, timeout=60):
        calls.append(arguments)
        offset = int(arguments[arguments.index("--offset") + 1])
        assert arguments[arguments.index("--limit") + 1] == "200"
        return {"data": {"fields": ["段落ID"], "record_id_list": [f"rec{offset}"],
                         "data": [[f"s{offset}"]], "has_more": offset == 0, "rev": 2}}

    monkeypatch.setattr(feishu, "_run", paged)
    records = base._list_records("token", "tbl1", ["段落ID"])
    assert [row["record_id"] for row in records] == ["rec0", "rec1"]
    assert len(calls) == 2


def test_ignored_key_field_never_becomes_empty_lookup():
    with pytest.raises(FeishuUnavailable, match="字段"):
        feishu._records({"data": {"fields": [], "record_id_list": ["rec1"], "data": [[]],
                                  "ignored_fields": [{"name": "段落ID"}]}})


def test_unconfigured_new_job_gate_does_not_call_lark(tmp_path, job, monkeypatch):
    from videoagents.nodes.human_review import HumanReviewNode

    repo = Repository(tmp_path / "runtime")
    monkeypatch.setattr(feishu, "_run", lambda *a, **k: pytest.fail("missing folder must not call lark"))
    HumanReviewNode(repo)._sync_feishu(job, {})


def test_submit_review_is_keyed_by_pending_token(lark, tmp_path, job):
    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, "tok1", "逐项核对")
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, "tok1", "逐项核对")
    rows = lark.tables["审核记录"]
    assert len(rows) == 1 and rows[0]["fields"]["结论"] == [feishu.DECISION_PENDING]


def test_poll_decision_requires_note_for_revise(lark, tmp_path, job):
    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, "tok1", "要求")
    assert base.poll_decision(job, "tok1") is None  # 待审 -> keep waiting
    row = lark.tables["审核记录"][0]
    row["fields"]["结论"] = [feishu.DECISION_REVISE]
    row["fields"]["意见"] = ""
    assert base.poll_decision(job, "tok1") is None  # revise without note keeps waiting
    row["fields"]["意见"] = "第二段来源不对,请换官方通报"
    assert base.poll_decision(job, "tok1") == {"decision": "revise", "note": "第二段来源不对,请换官方通报"}
    row["fields"]["结论"] = [feishu.DECISION_CONFIRM]
    row["fields"]["意见"] = ""
    assert base.poll_decision(job, "tok1") == {"decision": "confirm", "note": "飞书多维表格人工审核通过（结论：通过）"}


def test_plain_handles_lark_text_segments():
    assert _plain([{"text": "a"}, {"text": "b"}]) == "a\nb"
    assert _plain({"text": " x "}) == "x"
    assert _plain(None) == ""


@pytest.mark.parametrize("clear_folder", [False, True])
def test_script_gate_syncs_to_feishu_and_still_pauses(lark, tmp_path, monkeypatch, clear_folder):
    """The gate mirrors content before waiting; failure degrades to CLI-only review."""
    from videoagents.contracts import SettingsPatch
    from videoagents.services.jobs import JobService
    from videoagents.services.settings import SettingsService
    from videoagents.storage import Repository
    from worker.runner import Worker

    repo = Repository(tmp_path / "runtime")
    project = tmp_path / "project"
    SettingsService(repo).patch(SettingsPatch(feishu_folder_token="fld123"))
    job = repo.create_job(Brief(script_text="观点：飞书门测试。"))
    from videoagents.nodes.materials import collection_fingerprint
    from videoagents.nodes.screenwriter import ScreenwriterNode
    from videoagents.state import VideoState
    ScreenwriterNode(repo, JobService(repo, project))(VideoState(job_id=job.job_id, revision=job.revision,
                                                                 action="produce", run_id="UNIT-seed", thread_id="UNIT-seed"))
    job = repo.get_job(job.job_id)
    JobService(repo, project).write_json(job, "research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["UNIT：显式空素材夹具"],
        "collection_fingerprint": collection_fingerprint(job)}, "research")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    if clear_folder:
        SettingsService(repo).patch(SettingsPatch(feishu_folder_token=""))
    lark.calls.clear()
    repo.enqueue(job.job_id, {"action": "produce", "base_revision": job.revision, "idempotency_key": "unit-feishu-gate"})
    Worker(repo, project).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN" and paused.pending_input["node_name"] == "script_human_gate"
    assert lark.tables["文案"] and lark.tables["审核记录"]
    assert lark.tables["审核记录"][0]["fields"]["待办令牌"] == paused.pending_input["pending_token"]
    assert lark.tables["审核记录"][0]["fields"]["阶段"] == [feishu.REVIEW_STAGE_SCRIPT_ONLY]
    assert not any("+record-upload-attachment" in call for call in lark.calls)
    # Poll reads this distinct token and confirms only the script gate.
    lark.tables["审核记录"][0]["fields"]["结论"] = [feishu.DECISION_CONFIRM]
    decision = base.poll_decision(paused, paused.pending_input["pending_token"])
    repo.enqueue(job.job_id, {"action": "resume", "base_revision": paused.revision,
        "pending_token": paused.pending_input["pending_token"], **decision, "idempotency_key": "unit-feishu-script-confirm"})
    assert Worker(repo, project).once()
    collected = repo.get_job(job.job_id)
    assert collected.pending_input["node_name"] == "human_review_script"
    assert collected.pending_input["pending_token"] != paused.pending_input["pending_token"]
    assert lark.tables["审核记录"][-1]["fields"]["阶段"] == [feishu.REVIEW_STAGE_SCRIPT]

    # When lark-cli breaks entirely the gate still pauses; the message surfaces the gap.
    def broken(arguments, *, timeout=60):
        raise FeishuUnavailable("lark-cli 无法执行：boom")

    monkeypatch.setattr(feishu, "_run", broken)
    repo2, project2 = Repository(tmp_path / "r2"), tmp_path / "p2"
    SettingsService(repo2).patch(SettingsPatch(feishu_folder_token="fld123"))
    job2 = repo2.create_job(Brief(script_text="观点：降级测试。"))
    ScreenwriterNode(repo2, JobService(repo2, project2))(VideoState(job_id=job2.job_id, revision=job2.revision,
                                                                    action="produce", run_id="UNIT-seed", thread_id="UNIT-seed"))
    job2 = repo2.get_job(job2.job_id)
    JobService(repo2, project2).write_json(job2, "research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["UNIT：显式空素材夹具"],
        "collection_fingerprint": collection_fingerprint(job2)}, "research")
    repo2.enqueue(job2.job_id, {"action": "produce", "base_revision": job2.revision, "idempotency_key": "unit-feishu-down"})
    Worker(repo2, project2).once()
    paused2 = repo2.get_job(job2.job_id)
    assert paused2.status == "NEEDS_HUMAN"
    assert "飞书同步失败" in paused2.message


def test_sync_shots_uploads_real_artifact_images(lark, tmp_path, job):
    """The manifest stores Artifact dumps; PNG paths must resolve via the repo."""
    from videoagents.services.jobs import JobService

    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    frames = repo.root / "jobs" / job.job_id / "revisions" / "1"
    frames.mkdir(parents=True, exist_ok=True)
    png = frames / "frame.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nUNIT")
    artifact = service.register_artifact(job, png, "shot_review_frame", "image/png")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    lark.calls.clear()
    manifest = {"mode": "per_shot_stills", "items": [
        {"shot_id": "shot1", "start_frame": 0, "end_frame": 90,
         "component_id": "title", "component_reason": "r", "visual_action": "a",
         "image": artifact.model_dump()}]}
    base.sync_shots(job, manifest)
    uploads = [" ".join(c) for c in lark.calls if "+record-upload-attachment" in " ".join(c)]
    assert uploads, "代表帧 PNG 必须实际上传"
    assert str(png) in uploads[0] and "--field-id 代表帧" in uploads[0]
    assert lark.tables["镜头编排"][0]["fields"]["镜头ID"] == "shot1"


def test_resubmit_preserves_human_decision_fields(lark, tmp_path, job):
    """A replayed sync must not clobber the human's 结论/意见."""
    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    base.submit_review(job, feishu.REVIEW_STAGE_SHOTS, "tok9", "要求")
    row = lark.tables["审核记录"][0]
    row["fields"]["结论"] = [feishu.DECISION_REVISE]
    row["fields"]["意见"] = "第二镜换真实截图"
    base.submit_review(job, feishu.REVIEW_STAGE_SHOTS, "tok9", "要求")
    assert row["fields"]["结论"] == [feishu.DECISION_REVISE]
    assert row["fields"]["意见"] == "第二镜换真实截图"


def test_poll_short_revise_note_keeps_waiting(lark, tmp_path, job):
    """A revise note shorter than the gate's minimum cannot bounce at the gate."""
    repo = Repository(tmp_path / "runtime")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, "tok1", "要求")
    row = lark.tables["审核记录"][0]
    row["fields"]["结论"] = [feishu.DECISION_REVISE]
    row["fields"]["意见"] = "太短"  # 2 chars < 10
    assert base.poll_decision(job, "tok1") is None
    row["fields"]["意见"] = "第二段来源不对，请换成官方通报后再提交"
    decision = base.poll_decision(job, "tok1")
    assert decision["decision"] == "revise" and len(decision["note"]) >= 10
    # Default confirm note satisfies the default gate minimum too.
    row["fields"]["结论"] = [feishu.DECISION_CONFIRM]
    row["fields"]["意见"] = ""
    confirm = base.poll_decision(job, "tok1")
    assert confirm["decision"] == "confirm" and len(confirm["note"]) >= 10


@pytest.mark.skipif(executable_prefix("lark_cli") is None, reason="needs local lark-cli help output")
def test_feishu_commands_match_real_lark_cli_parsing(tmp_path, job, monkeypatch):
    """No bare --json on commands where the real CLI defines it as a VALUE input.

    Spy at the subprocess layer so the assertion sees the exact final argv
    (including _run's trailing output-format flags), then validate the flag
    usage against the real lark-cli help specifications.
    """
    import json as json_module
    import re as re_module
    import subprocess as sp

    # Classify flag usage from the REAL lark-cli help before the subprocess
    # module gets monkeypatched below (patching subprocess.run is global).
    commands = ["+base-create", "+table-create", "+table-list", "+field-list", "+field-create", "+record-list",
                "+record-batch-create", "+record-batch-update", "+record-get", "+record-upload-attachment"]
    value_json_commands, boolean_json_commands = set(), set()
    prefix = executable_prefix("lark_cli")
    for command in commands:
        help_text = sp.run([*prefix, "base", command, "--help"], capture_output=True, text=True,
                           encoding="utf-8", check=False, shell=False).stdout
        if re_module.search(r"--json\s+string", help_text):
            value_json_commands.add(command)
        elif "--json" in help_text:
            boolean_json_commands.add(command)

    repo = Repository(tmp_path / "runtime")
    captured: list[list[str]] = []
    state = {"records": {}, "tables": {"审核记录": []}, "fields": {}}

    def matrix(fields, records):
        return {"ok": True, "data": {
            "fields": fields, "field_id_list": [f"fld{i}" for i in range(len(fields))],
            "field_type_list": ["text"] * len(fields), "record_id_list": list(records),
            "data": [[row.get(field) for field in fields] for row in records.values()],
            "has_more": False, "timezone": "Asia/Shanghai"}}

    def fake_execute(argv, **kwargs):
        captured.append(list(argv))
        joined = " ".join(argv)
        if "+base-create" in joined:
            return {"data": {"base": {"base_token": "t1"}}}
        if "+table-create" in joined:
            name = argv[argv.index("--name") + 1]
            state["tables"][name] = []
            state["fields"][name] = json_module.loads(argv[argv.index("--fields") + 1])
            return {"data": {}}
        if "+table-list" in joined:
            return {"data": {"tables": [{"name": n, "id": f"tbl_{n}"} for n in state["tables"]]}}
        if "+field-list" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            return {"data": {"fields": state["fields"][table]}}
        if "+field-create" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            field = json_module.loads(argv[argv.index("--json") + 1])
            state["fields"][table].append(field)
            return {"data": {"field": field}}
        if "+record-list" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            fields = [a for i, a in enumerate(argv) if i and argv[i - 1] == "--field-id"]
            return matrix(fields, state["records"].get(table, {}))
        if "+record-delete" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            rid = argv[argv.index("--record-id") + 1]
            state["records"].setdefault(table, {}).pop(rid, None)
            return {"data": {}}
        if "+record-batch-create" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            body = json_module.loads(argv[argv.index("--json") + 1])
            for fields in body["create_records"]:
                rid = f"rec{len(state['records'].setdefault(table, {})) + 1}"
                state["records"][table][rid] = fields
            return {"data": {}}
        if "+record-batch-update" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            body = json_module.loads(argv[argv.index("--json") + 1])
            for rid, fields in body["update_records"].items():
                state["records"][table].setdefault(rid, {}).update(fields)
            return {"data": {}}
        if "+record-get" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            rid = argv[argv.index("--record-id") + 1]
            row = state["records"][table][rid]
            return matrix(list(row), {rid: row})
        if "+record-upload-attachment" in joined:
            return {"data": {}}
        raise AssertionError(f"unexpected call: {joined}")

    def fake_run(argv, **kwargs):
        class Result:
            returncode = 0
            stdout = json_module.dumps(fake_execute(argv), ensure_ascii=False)
            stderr = ""
        return Result()

    monkeypatch.setattr(feishu.subprocess, "run", fake_run)

    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    from videoagents.contracts import Script, ScriptSegment
    script = Script(title="t", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：一。",
                                            source_refs=["https://example.com/a"], visual_need="v")])
    job = repo.update_job(job.job_id, job.revision, script=script)
    base.sync_script_and_assets(job)
    row = state["records"]["文案"]["rec1"]
    row["修改意见"] = "请在第一段解释用户数量"
    base.sync_script_and_assets(job)
    assert state["records"]["文案"] == {"rec1": row}
    assert row["修改意见"] == "请在第一段解释用户数量"
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, "tokp", "要求")
    assert base.poll_decision(job, "tokp") is None

    for argv in captured:
        assert argv[:len(prefix)] == prefix
        command = argv[len(prefix) + 1]
        # The output format is always selected explicitly.
        index = argv.index("--format")
        assert index is not None and argv[index + 1] == "json", argv
        assert argv[argv.index("--as") + 1] == "user"
        for position, item in enumerate(argv):
            if item == "--json":
                # On value-taking commands --json must always carry a payload.
                assert command in boolean_json_commands or (
                    position + 1 < len(argv) and not argv[position + 1].startswith("--")), argv
    assert value_json_commands, "本机 lark-cli 应识别出值参 --json 命令"
    assert any("+record-batch-create" in " ".join(a) for a in captured)
