"""Partial selection uses the real queued graph and leaves the same gate pending."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from videoagents.contracts import Asset, Brief, SettingsPatch, Shot, Timeline
from videoagents.main import main
from videoagents.nodes.common import state_context
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.script_review import script_before_materials_is_approved
from videoagents.services.jobs import JobService
from videoagents.services.material_selection import selection_receipts
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, Repository
from videoagents.tools.media import sha256
from videoagents.tools.timeline import validate_timeline

NOTE = "用户拒绝低画质视频，保留清晰图片；整包文案与素材仍待审，不开始配音。"


def cli(monkeypatch, capsys, repo, *args):
    monkeypatch.setattr(sys, "argv", ["videoagents", "--runtime-dir", str(repo.root), *args])
    code = main()
    return code, json.loads(capsys.readouterr().out)


def ledger(repo):
    with repo.connection() as db:
        return [dict(row) for row in db.execute("SELECT * FROM operations ORDER BY operation_id")]


def selection(job, **changes):
    return {"action": "resume", "base_revision": job.revision,
            "pending_token": job.pending_input["pending_token"], "idempotency_key": "UNIT-selection",
            "decision": "select_materials", "note": NOTE,
            "accepted_asset_ids": [job.assets[5].asset_id, job.assets[6].asset_id],
            "rejected_asset_ids": [item.asset_id for item in job.assets[:5]], **changes}


@pytest.fixture
def paused(tmp_path, monkeypatch, capsys, request):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False))
    job = repo.create_job(Brief(topic="UNIT paid AI chat", script_text="观点：付费聊天需要辨别真实用户。"))
    calls = []

    def collected(node, state):
        current = node.repo.get_job(state["job_id"])
        calls.append("materials")
        assets, artifacts = [], []
        for index in range(8):
            video = index < 5
            asset_id = f"unit-material-{index:02}"
            extension, mime = (".mp4", "video/mp4") if video else (".png", "image/png")
            path = repo.root / "jobs" / job.job_id / "assets" / (asset_id + extension)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"UNIT synthetic media bytes {index}".encode())
            artifact = JobService(repo).register_artifact(current, path, "asset", mime)
            assets.append(Asset(asset_id=asset_id, name=path.name, role="evidence", mime_type=mime,
                size_bytes=artifact.size_bytes, sha256=artifact.sha256, artifact_id=artifact.artifact_id,
                url=artifact.url, source_url="https://example.org/unit-paid-chat",
                license_note="UNIT personal use", timeline_src=f"videoagents/{job.job_id}/assets/{path.name}"))
            artifacts.append(artifact)
            repo.update_asset_metadata(asset_id, {"width": 480 if video else 1920,
                "height": 270 if video else 1080, "duration_seconds": 30 if video else 0})
        changes = {"brief": current.brief.model_copy(update={"source_urls": ["https://example.org/new-material-source"]})}
        repo.update_job(job.job_id, current.revision, assets=assets, artifacts=current.artifacts + artifacts,
                        **(changes if getattr(request, "param", False) else {}))
        return state_context(repo, state, route="human_review_script")

    monkeypatch.setattr(MaterialsNode, "__call__", collected)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *a, **kw: pytest.fail("No model calls"))
    monkeypatch.setattr("videoagents.nodes.voice.VoiceNode.__call__", lambda *a: pytest.fail("No TTS node"))
    assert cli(monkeypatch, capsys, repo, "run", job.job_id)[0] == 0
    current = repo.get_job(job.job_id)
    assert current.pending_input["node_name"] == "script_human_gate"
    assert cli(monkeypatch, capsys, repo, "resume", job.job_id, "--decision", "confirm",
               "--note", "UNIT：真实人工确认口播，允许素材采集。") [0] == 0
    current = repo.get_job(job.job_id)
    assert current.pending_input["node_name"] == "human_review_script"
    assert calls == ["materials"]
    assert script_before_materials_is_approved(repo, current) is not getattr(request, "param", False)
    monkeypatch.setattr(MaterialsNode, "__call__", lambda *a: pytest.fail("No new material collection"))
    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.__call__",
                        lambda *a: pytest.fail("No writer invocation"))
    return repo, current


BOOTSTRAP = """
import sys
from videoagents.main import main
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.voice import VoiceNode
from videoagents.providers.llm import JsonModel
def forbidden(*a, **kw):
    raise AssertionError('No production role or external model may run during selection')
for role in (MaterialsNode, ScreenwriterNode, VoiceNode):
    role.__call__ = forbidden
JsonModel.call = forbidden
{crash}
sys.argv = ['videoagents', *sys.argv[1:]]
raise SystemExit(main())
"""


def process_cli(repo, job, note_file, *, crash=False):
    injection = """
import os
original = HumanReviewNode._record
def crash_after_sql(self, job, receipt, *a, **kw):
    original(self, job, receipt, *a, **kw)
    if receipt.get('decision') == 'select_materials':
        os._exit(87)
HumanReviewNode._record = crash_after_sql
""" if crash else ""
    args = [sys.executable, "-c", BOOTSTRAP.format(crash=injection), "--runtime-dir", str(repo.root),
            "select-materials", job.job_id, "--note-file", str(note_file), "--idempotency-key", "UNIT-process-selection"]
    for asset in job.assets[:5]:
        args.extend(["--reject-asset", asset.asset_id])
    for asset in job.assets[5:7]:
        args.extend(["--accept-asset", asset.asset_id])
    root = Path(__file__).resolve().parents[2]
    return subprocess.run(args, cwd=root, env={**os.environ, "PYTHONPATH": str(root), "PYTHONUTF8": "1"},
                          capture_output=True, text=True, encoding="utf-8", timeout=35)


def assert_selected(repo, before):
    current = Repository(repo.root).get_job(before.job_id)
    assert current.status == "NEEDS_HUMAN" and current.stage == "script"
    assert current.pending_input["node_name"] == "human_review_script"
    assert current.pending_input["pending_token"] != before.pending_input["pending_token"]
    assert current.script == before.script and current.brief == before.brief
    assert script_before_materials_is_approved(repo, current)
    assert [item.asset_id for item in current.assets] == [item.asset_id for item in before.assets[5:]]
    receipts = selection_receipts(repo, current)
    assert len(receipts) == 1
    receipt = receipts[0]
    assert receipt["decision"] == "select_materials" and receipt["note"] == NOTE
    assert receipt["subject"]["script"] == before.script.model_dump()
    assert receipt["subject"]["assets"] == [item.model_dump() for item in before.assets]
    assert receipt["dependency_fingerprint"] == before.pending_input["dependency_fingerprint"]
    for item in before.artifacts:
        path, registered, owner = repo.artifact_path(item.artifact_id)
        assert path.is_file() and registered == item and owner == before.job_id
        assert sha256(path) == item.sha256
    assert all(repo.asset_metadata(item.asset_id) for item in before.assets)
    return current


def test_select_cli_reopens_graph_and_is_idempotent_across_processes(paused, tmp_path):
    repo, before = paused
    operations = ledger(repo)
    note_file = tmp_path / "note.txt"
    note_file.write_text(NOTE, encoding="utf-8")
    result = process_cli(repo, before, note_file)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "NEEDS_HUMAN"
    current = assert_selected(repo, before)
    event_id = current.latest_event_id
    result = process_cli(repo, before, note_file)
    assert result.returncode == 0, result.stderr
    assert_selected(repo, before)
    assert repo.get_job(before.job_id).latest_event_id == event_id
    assert ledger(repo) == operations
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands WHERE idempotency_key='UNIT-process-selection'").fetchone()[0] == 1


def test_selection_crash_after_sql_recovers_in_new_cli_process(paused, tmp_path):
    repo, before = paused
    note_file = tmp_path / "note.txt"
    note_file.write_text(NOTE, encoding="utf-8")
    operations = ledger(repo)
    result = process_cli(repo, before, note_file, crash=True)
    assert result.returncode == 87, result.stderr
    committed = repo.get_job(before.job_id)
    assert committed.pending_input is None and len(committed.assets) == 3
    assert len(selection_receipts(repo, committed)) == 1
    # Simulate the expired worker lease in this TEMP fixture; the OS process
    # really exited. No job state or LangGraph checkpoint is manually changed.
    with repo.connection() as db:
        db.execute("UPDATE commands SET lease_until=0 WHERE status='CLAIMED'")
    result = process_cli(repo, before, note_file)
    assert result.returncode == 0, result.stderr
    assert_selected(repo, before)
    assert ledger(repo) == operations


def test_default_key_replays_original_token_and_changed_explicit_key_fails(paused, monkeypatch, capsys):
    repo, before = paused
    args = ("select-materials", before.job_id, "--reject-asset", before.assets[0].asset_id, "--note", NOTE)
    assert cli(monkeypatch, capsys, repo, *args)[0] == 0
    current = repo.get_job(before.job_id)
    token, event_id = current.pending_input["pending_token"], current.latest_event_id
    assert cli(monkeypatch, capsys, repo, *args)[0] == 0
    assert repo.get_job(before.job_id).pending_input["pending_token"] == token
    assert repo.get_job(before.job_id).latest_event_id == event_id
    next_args = ("select-materials", before.job_id, "--accept-asset", before.assets[5].asset_id,
                 "--note", NOTE, "--idempotency-key", "UNIT-explicit-repeat")
    assert cli(monkeypatch, capsys, repo, *next_args)[0] == 0
    assert cli(monkeypatch, capsys, repo, *next_args)[0] == 0
    assert cli(monkeypatch, capsys, repo, *next_args, "--accept-asset", before.assets[6].asset_id)[0] == 2


@pytest.mark.parametrize("changes", [
    {"accepted_asset_ids": ["missing"]}, {"rejected_asset_ids": ["unit-material-00"] * 2},
    {"accepted_asset_ids": ["unit-material-00"], "rejected_asset_ids": ["unit-material-00"]},
    {"accepted_asset_ids": [], "rejected_asset_ids": []}, {"accepted_asset_ids": [1]},
    {"note": " "}, {"note": "x" * 3001}, {"pending_token": "stale-pending-token"},
    {"base_revision": 2}, {"stop_after": "voice"}, {"director_requirements": {}},
])
def test_invalid_selection_does_not_enqueue_or_change_job(paused, changes):
    repo, before = paused
    with pytest.raises((Conflict, ValidationError)):
        repo.enqueue(before.job_id, selection(before, **changes))
    assert repo.get_job(before.job_id) == before
    assert not selection_receipts(repo, before)


@pytest.mark.parametrize("node,stage,kind", [
    ("script_human_gate", "script", "stage_review"), ("director_human_gate", "director", "stage_review"),
    ("human_review", "script", "stage_review"), ("human_review_script", "materials", "input"),
])
def test_selection_cannot_apply_to_other_gates(paused, node, stage, kind):
    repo, before = paused
    pending = dict(before.pending_input, node_name=node, stage=stage, kind=kind)
    current = repo.update_job(before.job_id, stage=stage, pending_input=pending)
    with pytest.raises(Conflict, match="仅适用于"):
        repo.enqueue(current.job_id, selection(current))
    assert repo.get_job(before.job_id) == current


@pytest.mark.parametrize("status", ["SUBMITTING", "UNKNOWN"])
def test_current_unsettled_operation_blocks_selection(paused, status):
    repo, before = paused
    operation = repo.start_operation(before.job_id, "UNIT-unsettled", "llm:materials", {"revision": before.revision})
    if status == "UNKNOWN":
        repo.finish_operation(operation["operation_id"], status, {"revision": before.revision})
    with pytest.raises(Conflict, match="状态未知"):
        repo.enqueue(before.job_id, selection(before))
    assert repo.get_job(before.job_id) == before


def test_bound_script_is_not_silently_rewritten(paused):
    repo, before = paused
    script = before.script.model_copy(deep=True)
    script.segments[0].asset_ids = [before.assets[0].asset_id]
    current = repo.update_job(before.job_id, script=script)
    with pytest.raises(Conflict, match="静默改稿"):
        repo.enqueue(current.job_id, selection(current))
    assert repo.get_job(before.job_id).script == script


def test_rejected_media_cannot_become_timeline_media(paused, monkeypatch, capsys):
    repo, before = paused
    assert cli(monkeypatch, capsys, repo, "select-materials", before.job_id,
               "--reject-asset", before.assets[0].asset_id, "--note", NOTE)[0] == 0
    current = repo.get_job(before.job_id)
    timeline = Timeline(job_id=current.job_id, revision=current.revision, width=current.brief.width,
        height=current.brief.height, fps=current.brief.fps, duration_in_frames=30,
        shots=[Shot(shot_id="s1", title="UNIT rejected video", component_id="video", start_frame=0, end_frame=30,
                    asset_src=before.assets[0].timeline_src, source_label="UNIT source")])
    with pytest.raises(ValueError, match="必须来自此任务已导入"):
        validate_timeline(timeline, current, {item.asset_id: repo.asset_metadata(item.asset_id) for item in current.assets})


def test_accept_only_still_creates_a_new_pending_without_model_calls(paused, monkeypatch, capsys):
    repo, before = paused
    assert cli(monkeypatch, capsys, repo, "select-materials", before.job_id,
               "--accept-asset", before.assets[5].asset_id, "--note", NOTE)[0] == 0
    current = repo.get_job(before.job_id)
    assert current.assets == before.assets and current.script == before.script
    assert current.pending_input["pending_token"] != before.pending_input["pending_token"]
    assert script_before_materials_is_approved(repo, current)


@pytest.mark.parametrize("paused", [True], indirect=True)
def test_partial_selection_preserves_existing_false_approval_without_fabricating_confirm(paused, monkeypatch, capsys):
    repo, before = paused
    assert not script_before_materials_is_approved(repo, before)
    assert cli(monkeypatch, capsys, repo, "select-materials", before.job_id,
               "--reject-asset", before.assets[0].asset_id, "--note", NOTE)[0] == 0
    current = repo.get_job(before.job_id)
    assert current.status == "NEEDS_HUMAN" and current.pending_input["node_name"] == "human_review_script"
    assert current.script == before.script and current.brief == before.brief
    assert not script_before_materials_is_approved(repo, current)
    assert [item for item in current.artifacts if item.kind == "stage_review"][:-1] == [
        item for item in before.artifacts if item.kind == "stage_review"]


def test_changed_bytes_cannot_be_selected_at_old_pending(paused, monkeypatch, capsys):
    repo, before = paused
    repo.artifact_path(before.assets[0].artifact_id)[0].write_bytes(b"changed")
    code, summary = cli(monkeypatch, capsys, repo, "select-materials", before.job_id,
                        "--reject-asset", before.assets[0].asset_id, "--note", NOTE)
    assert code == 1 and summary["status"] == "FAILED"
    assert repo.get_job(before.job_id).assets == before.assets
    assert not selection_receipts(repo, repo.get_job(before.job_id))


def test_selection_fields_cannot_be_smuggled_into_confirm(paused):
    repo, before = paused
    with pytest.raises(Conflict, match="独立的部分决定"):
        repo.enqueue(before.job_id, selection(before, decision="confirm"))
    assert repo.get_job(before.job_id) == before


def test_immutable_selection_receipt_tamper_blocks_further_selection(paused, monkeypatch, capsys):
    repo, before = paused
    assert cli(monkeypatch, capsys, repo, "select-materials", before.job_id,
               "--accept-asset", before.assets[5].asset_id, "--note", NOTE)[0] == 0
    current = repo.get_job(before.job_id)
    artifact = [item for item in current.artifacts if item.kind == "stage_review"][-1]
    repo.artifact_path(artifact.artifact_id)[0].write_text('{}', encoding="utf-8")
    code, summary = cli(monkeypatch, capsys, repo, "select-materials", before.job_id,
                        "--reject-asset", before.assets[0].asset_id, "--note", NOTE)
    assert code == 1 and summary["status"] == "FAILED"
    assert repo.get_job(before.job_id).assets == before.assets
