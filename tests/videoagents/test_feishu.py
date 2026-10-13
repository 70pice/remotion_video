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
            table = arguments[arguments.index("--table-id") + 1].removeprefix("tbl_")
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
    assert base.poll_decision(job, "tok1") == {"decision": "confirm", "note": "飞书多维表格人工审核通过（结论：通过）"}


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
    commands = ["+base-create", "+table-create", "+base-get", "+record-list", "+record-delete",
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
    state = {"records": {}, "tables": {"审核记录": []}}

    def fake_execute(argv, **kwargs):
        captured.append(list(argv))
        joined = " ".join(argv)
        if "+base-create" in joined:
            return {"data": {"app": {"app_token": "t1"}}}
        if "+table-create" in joined:
            name = argv[argv.index("--name") + 1]
            state["tables"][name] = []
            return {"data": {}}
        if "+base-get" in joined:
            return {"data": {"app": {"tables": [{"name": n, "table_id": f"tbl_{n}"} for n in state["tables"]]}}}
        if "+record-list" in joined:
            table = argv[argv.index("--table-id") + 1].removeprefix("tbl_")
            fields = [a for i, a in enumerate(argv) if i and argv[i - 1] == "--field-id"]
            return {"data": {"items": [{"record_id": rid,
                                        "fields": {f: row.get(f) for f in fields}}
                                       for rid, row in state["records"].get(table, {}).items()]}}
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
            return {"data": {"items": [{"record_id": rid, "fields": state["records"][table][rid]}]}}
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
    base.submit_review(job, feishu.REVIEW_STAGE_SCRIPT, "tokp", "要求")
    base.poll_decision(job, "tokp")

    for argv in captured:
        assert argv[:len(prefix)] == prefix
        command = argv[len(prefix) + 1]
        # The output format is always selected explicitly.
        index = argv.index("--format")
        assert index is not None and argv[index + 1] == "json", argv
        for position, item in enumerate(argv):
            if item == "--json":
                # On value-taking commands --json must always carry a payload.
                assert command in boolean_json_commands or (
                    position + 1 < len(argv) and not argv[position + 1].startswith("--")), argv
    assert value_json_commands, "本机 lark-cli 应识别出值参 --json 命令"
    assert any("+record-batch-create" in " ".join(a) for a in captured)
