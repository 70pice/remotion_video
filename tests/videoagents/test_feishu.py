"""The Feishu review surface: idempotent sync, keyed review rows, decision polling."""

import json

import pytest

from videoagents.contracts import Brief
from videoagents.providers import feishu
from videoagents.providers.feishu import FeishuReviewBase, FeishuUnavailable, _plain
from videoagents.storage import Repository


class FakeLark:
    def __init__(self):
        self.calls: list[list[str]] = []
        self.tables: dict[str, list[dict]] = {}
        self.review_rows: dict[str, dict] = {}
        self.next_record = 100

    def __call__(self, arguments, *, timeout=60):
        self.calls.append(arguments)  # noqa: F841 — 调用轨迹供断言使用
        joined = " ".join(arguments)
        if "+base-create" in joined:
            self.tables = {"审核记录": []}
            return {"data": {"app": {"app_token": "basetoken123"}}}

        if "+table-create" in joined:
            name = arguments[arguments.index("--name") + 1]
            self.tables[name] = []
            return {"data": {"table_id": f"tbl_{name}"}}
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
            arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
            rid = arguments[arguments.index("--record-id") + 1]
            path = arguments[arguments.index("--file") + 1]
            row = next(r for r in self.tables[table] if r["record_id"] == rid)
            row["fields"].setdefault("附件", []).append(path)
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
    # Resync rewrites instead of duplicating.
    base.sync_script_and_assets(job)
    assert len(lark.tables["文案"]) == 2


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
    assert base.poll_decision(job, "tok1") == {"decision": "confirm", "note": "飞书审核通过"}


def test_plain_handles_lark_text_segments():
    assert _plain([{"text": "a"}, {"text": "b"}]) == "a\nb"
    assert _plain({"text": " x "}) == "x"
    assert _plain(None) == ""


def test_script_gate_syncs_to_feishu_and_still_pauses(lark, tmp_path, monkeypatch):
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
    JobService(repo, project).write_json(job, "research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["UNIT：显式空素材夹具"]}, "research")
    base = FeishuReviewBase(repo, "fld123")
    base.ensure_base(job)
    lark.calls.clear()
    repo.enqueue(job.job_id, {"action": "produce", "base_revision": job.revision, "idempotency_key": "unit-feishu-gate"})
    Worker(repo, project).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN" and paused.pending_input["node_name"] == "human_review_script"
    assert lark.tables["文案"] and lark.tables["审核记录"]
    assert lark.tables["审核记录"][0]["fields"]["待办令牌"] == paused.pending_input["pending_token"]

    # When lark-cli breaks entirely the gate still pauses; the message surfaces the gap.
    def broken(arguments, *, timeout=60):
        raise FeishuUnavailable("lark-cli 无法执行：boom")

    monkeypatch.setattr(feishu, "_run", broken)
    repo2, project2 = Repository(tmp_path / "r2"), tmp_path / "p2"
    SettingsService(repo2).patch(SettingsPatch(feishu_folder_token="fld123"))
    job2 = repo2.create_job(Brief(script_text="观点：降级测试。"))
    JobService(repo2, project2).write_json(job2, "research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["UNIT：显式空素材夹具"]}, "research")
    repo2.enqueue(job2.job_id, {"action": "produce", "base_revision": job2.revision, "idempotency_key": "unit-feishu-down"})
    Worker(repo2, project2).once()
    paused2 = repo2.get_job(job2.job_id)
    assert paused2.status == "NEEDS_HUMAN"
    assert "飞书同步失败" in paused2.message
