"""Explicit materials recovery keeps real pre-collection approval, never a fake gate."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from videoagents.contracts import Brief, RestartUnknownRequest, Script, ScriptSegment, SettingsPatch
from videoagents.main import main
from videoagents.nodes.common import state_context
from videoagents.nodes.materials import MaterialsNode, collection_fingerprint
from videoagents.nodes.script_review import script_before_materials_is_approved
from videoagents.providers.cli_runner import CliResult
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, Repository
from videoagents.tools.media import sha256

NOTE = "用户明确要求保留已审口播，只找付费聊天、付费视频与 AI 欺诈素材；排除普通社交宣传图。"
SOURCE = "https://example.org/unit-report"


def cli(monkeypatch, capsys, repo, *args):
    monkeypatch.setattr(sys, "argv", ["videoagents", "--runtime-dir", str(repo.root), *args])
    result = main()
    return result, json.loads(capsys.readouterr().out)


def restart_request(operation_id, revision=1, **changes):
    return RestartUnknownRequest(base_revision=revision, operation_id=operation_id,
        acknowledge_possible_usage=True, note="用户明确授权新的素材尝试，接受旧提交可能有用量。",
        materials_only=True, materials_note=NOTE, **changes)


@pytest.fixture
def approved_unknown(tmp_path, monkeypatch, capsys):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT paid-chat deception", source_urls=[SOURCE]))
    service = JobService(repo)

    def writer(node, current, context):
        folder = repo.root / "jobs" / job.job_id / "revisions" / "1" / "skills-research"
        folder.mkdir(parents=True)
        for index in range(3):
            (folder / f"mcp-{index}.txt").write_text("UNIT read report: paid messages and video calls.", encoding="utf-8")
        # Neither failed candidate outputs nor staged CLI auth may be snapshotted.
        (folder / "research").mkdir()
        (folder / "research" / "unrelated-ui.txt").write_text("UNIT rejected candidate", encoding="utf-8")
        (folder / ".videoagents-cli-unit").mkdir()
        (folder / ".videoagents-cli-unit" / "auth.json").write_text('{"secret":"UNIT-secret"}', encoding="utf-8")
        service.write_json(current, "writer-audit.json", {"type": "item.completed", "item_type": "mcp_tool_call"},
                           "writer_tool_audit")
        return Script(title="UNIT reviewed script", origin="model", revision=current.revision,
            segments=[ScriptSegment(segment_id="s1", narration="UNIT paid chat and video deception.",
                                    source_refs=[SOURCE], visual_need="UNIT old generic UI preference")])

    def unknown(node, current, state):
        ledger = {"revision": current.revision, "reason": "UNIT unknown", "mode": "research"}
        operation = repo.start_operation(job.job_id, "UNIT-old-material-input", "llm:materials", ledger)
        repo.finish_operation(operation["operation_id"], "UNKNOWN", ledger)
        raise CapabilityMissing("UNIT materials submission unknown", ["llm_operation"],
                                operation_id=operation["operation_id"], operation_status="UNKNOWN")

    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.write", writer)
    monkeypatch.setattr(MaterialsNode, "collect", unknown)
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **kw: pytest.fail("No real provider calls"))
    monkeypatch.setattr("videoagents.nodes.voice.VoiceNode.__call__", lambda *a: pytest.fail("No voice before joint gate"))
    result, summary = cli(monkeypatch, capsys, repo, "run", job.job_id)
    assert result == 0 and summary["status"] == "NEEDS_HUMAN"
    paused = repo.get_job(job.job_id)
    assert paused.pending_input["node_name"] == "script_human_gate"
    result, summary = cli(monkeypatch, capsys, repo, "resume", job.job_id, "--decision", "confirm", "--note",
                          "UNIT：已逐段核对口播、读取记录与来源，同意采集素材。")
    assert result == 0 and summary["status"] == "NEEDS_INPUT"
    job = repo.get_job(job.job_id)
    assert script_before_materials_is_approved(repo, job)
    return repo, job, job.pending_input["operation_id"]


def test_materials_only_cli_survives_new_process_and_runs_only_collector(approved_unknown, tmp_path, monkeypatch, capsys):
    repo, original, operation_id = approved_unknown
    note_file = tmp_path / "materials-note.md"
    note_file.write_text(NOTE, encoding="utf-8")
    original_bytes = {item.artifact_id: repo.artifact_path(item.artifact_id)[0].read_bytes() for item in original.artifacts}
    old_operation = repo.operation(original.job_id, "UNIT-old-material-input", "llm:materials")
    # A real fresh CLI process accepts the command, saves a draft, and exits.
    result = subprocess.run([sys.executable, "-m", "videoagents.main", "--runtime-dir", str(repo.root),
        "restart-unknown", original.job_id, "--operation-id", operation_id, "--acknowledge-possible-usage",
        "--note", "用户新授权素材尝试，接受旧提交可能消耗额度", "--materials-only",
        "--materials-note-file", str(note_file)], capture_output=True, text=True, encoding="utf-8",
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
        cwd=Path(__file__).resolve().parents[2], timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "DRAFT"
    fresh = Repository(repo.root)
    current = fresh.get_job(original.job_id)
    assert current.revision == 2 and current.assets == [] and current.timeline is None and current.pending_input is None
    assert current.script.model_copy(update={"revision": 1}) == original.script
    assert current.brief == original.brief
    authorization = fresh.materials_restart_receipt(current.job_id, 2)
    assert authorization["materials_note"] == NOTE
    assert len(authorization["preserved_script"]["source_files"]) == 3
    assert all(Path(value["path"]).parent.name == "skills-research" and ".videoagents-cli" not in value["path"]
               for value in authorization["preserved_script"]["source_files"])
    assert script_before_materials_is_approved(fresh, current)
    with fresh.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands WHERE status IN ('PENDING','CLAIMED')").fetchone()[0] == 0
    assert not any(item.kind == "stage_review" and item.revision == 2 for item in current.artifacts)

    captured = []
    def fixture_model(node, job_id, revision, role, instruction, context, command_id="", **kwargs):
        assert role == "materials" and revision == 2
        assert context["extras"] == {"materials_note": NOTE}
        assert context["script"] == current.script.model_dump()
        assert "extras.materials_note" in instruction
        folder = kwargs["research_directory"]
        assert folder.parts[-3:] == ("revisions", "2", "skills-research")
        assert not (folder / "research" / "unrelated-ui.txt").exists()
        text = folder / "source.txt"
        text.write_text("UNIT new material report read", encoding="utf-8")
        captured.append(context)
        return {"sources": [{"url": "https://example.org/unit-paid-ui", "title": "UNIT", "platform": "UNIT",
                "text_file": "source.txt", "sha256": sha256(text)}], "visuals": [],
                "limitations": ["[画面缺口] UNIT fixture is intentionally without media"]}

    def collector(node, current_job, state):
        state["extras"] = {**state.get("extras", {}), "UNIT_carry": "preserve handoff"}
        output = REAL_COLLECT(node, current_job, state)
        assert state["extras"]["UNIT_carry"] == "preserve handoff"
        assert "materials_note" not in state["extras"]
        return output

    monkeypatch.setattr(MaterialsNode, "collect", collector)
    monkeypatch.setattr(JsonModel, "call", fixture_model)
    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.__call__",
                        lambda *a: pytest.fail("Materials-only recovery must not call writer"))
    code, summary = cli(monkeypatch, capsys, fresh, "run", current.job_id)
    assert code == 0 and summary["status"] == "NEEDS_HUMAN"
    collected = fresh.get_job(current.job_id)
    assert captured and collected.pending_input["node_name"] == "human_review_script"
    assert collected.brief == original.brief
    assert script_before_materials_is_approved(fresh, collected)
    assert not any(item.kind == "stage_review" and item.revision == 2 for item in collected.artifacts)
    assert fresh.operation(current.job_id, "UNIT-old-material-input", "llm:materials") == old_operation
    for artifact_id, content in original_bytes.items():
        assert fresh.artifact_path(artifact_id)[0].read_bytes() == content
    research = MaterialsNode(fresh, JobService(fresh)).saved_json(collected, "research")
    assert research["collection_fingerprint"] == collection_fingerprint(collected, NOTE)
    assert research["collection_fingerprint"] != collection_fingerprint(collected, NOTE + " corrected")
    restored = state_context(Repository(repo.root), {"job_id": current.job_id, "revision": 2})
    assert "materials_note" not in restored["extras"]
    assert Repository(repo.root).materials_restart_receipt(current.job_id, 2)["materials_note"] == NOTE
    # A later unknown material attempt can inherit the same original approval,
    # even after the first new collector registered an additional source.
    another = fresh.start_operation(current.job_id, "UNIT-second-unknown", "llm:materials", {"revision": 2})
    fresh.finish_operation(another["operation_id"], "UNKNOWN", {"revision": 2})
    fresh.update_job(current.job_id, status="NEEDS_INPUT", stage="materials", pending_input={
        "kind": "input", "stage": "materials", "revision": 2, "operation_status": "UNKNOWN",
        "operation_id": another["operation_id"]})
    third = JobService(Repository(repo.root)).restart_unknown(current.job_id, restart_request(another["operation_id"], 2))
    assert third.revision == 3 and third.brief == original.brief
    assert script_before_materials_is_approved(Repository(repo.root), third)


REAL_COLLECT = MaterialsNode.collect


@pytest.mark.parametrize("changes", [
    {"materials_only": False}, {"materials_only": "true"}, {"materials_only": 1},
    {"materials_note": " "}, {"rebuild_script": True}, {"brief": Brief(topic="UNIT changed")},
])
def test_scope_requires_strict_flag_note_and_unchanged_brief(changes):
    payload = restart_request("a" * 32).model_dump()
    with pytest.raises(ValidationError):
        RestartUnknownRequest.model_validate({**payload, **changes})


@pytest.mark.parametrize("invalid", ["missing_approval", "script_changed", "missing_script", "audit_changed",
    "missing_audit", "approval_changed", "wrong_role", "submitting", "another_unknown", "another_submitting"])
def test_preserving_script_rejects_invalid_state_without_revision(approved_unknown, invalid):
    repo, original, operation_id = approved_unknown
    kind = {"missing_approval": "stage_review", "missing_script": "script", "audit_changed": "writer_tool_audit",
            "missing_audit": "writer_tool_audit", "approval_changed": "stage_review"}.get(invalid)
    if kind:
        artifact = next(item for item in original.artifacts if item.kind == kind)
        if invalid.startswith("missing_"):
            repo.update_job(original.job_id, artifacts=[item for item in original.artifacts if item != artifact])
        else:
            repo.artifact_path(artifact.artifact_id)[0].write_text("UNIT changed", encoding="utf-8")
    elif invalid == "script_changed":
        changed = original.script.model_copy(deep=True)
        changed.segments[0].narration += "UNIT changed"
        repo.update_job(original.job_id, script=changed)
    elif invalid == "wrong_role":
        with repo.connection() as db:
            db.execute("UPDATE operations SET provider='llm:screenwriter' WHERE operation_id=?", (operation_id,))
    elif invalid == "submitting":
        repo.finish_operation(operation_id, "SUBMITTING", {"revision": 1})
    else:
        other = repo.start_operation(original.job_id, "UNIT-other", "llm:voice", {"revision": 1})
        if invalid == "another_unknown":
            repo.finish_operation(other["operation_id"], "UNKNOWN", {"revision": 1})
    before = repo.get_job(original.job_id)
    before_events = repo.events_after(original.job_id, 0)
    with pytest.raises((Conflict, ValueError)):
        JobService(repo).restart_unknown(original.job_id, restart_request(operation_id))
    assert repo.get_job(original.job_id) == before
    assert repo.events_after(original.job_id, 0) == before_events
    assert repo.materials_restart_receipt(original.job_id, 2) is None


def test_duplicate_authorization_is_atomic_and_material_note_is_part_of_identity(approved_unknown):
    repo, job, operation_id = approved_unknown
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: JobService(repo).restart_unknown(job.job_id, restart_request(operation_id)), range(2)))
    assert [item.revision for item in results] == [2, 2]
    assert JobService(Repository(repo.root)).restart_unknown(job.job_id, restart_request(operation_id, 2)).revision == 2
    changed = restart_request(operation_id).model_copy(update={"materials_note": NOTE + " different"})
    with pytest.raises(Conflict):
        JobService(repo).restart_unknown(job.job_id, changed)


def test_restart_source_snapshot_does_not_claim_historical_writer_completeness(approved_unknown):
    repo, job, operation_id = approved_unknown
    folder = repo.root / "jobs" / job.job_id / "revisions" / "1" / "skills-research"
    (folder / "mcp-1.txt").unlink()
    (folder / "mcp-material-candidate.txt").write_text("UNIT later source tool result", encoding="utf-8")
    updated = JobService(repo).restart_unknown(job.job_id, restart_request(operation_id))
    preserved = repo.materials_restart_receipt(job.job_id, 2)["preserved_script"]
    assert preserved["source_snapshot_scope"] == "restart_time_research_root_texts"
    assert len(preserved["source_files"]) == 3
    assert any(Path(item["path"]).name == "mcp-material-candidate.txt" for item in preserved["source_files"])
    assert script_before_materials_is_approved(repo, updated)
    # Old gates bound the immutable audit and script, not individual source-tool
    # file membership. This snapshot makes no unsupported historical claim.


def test_latest_real_script_revise_cannot_inherit_earlier_confirm(approved_unknown):
    from videoagents.nodes.human_review import HumanReviewNode

    repo, job, operation_id = approved_unknown
    artifact = next(item for item in job.artifacts if item.kind == "stage_review")
    receipt = json.loads(repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8"))
    receipt.update(decision="revise", note="UNIT: the reviewed narration must be changed before more collection.",
                   pending_token="UNIT-later-revise")
    HumanReviewNode(repo)._record(job, receipt, "NEEDS_INPUT", "UNIT fixture later revise")
    # A stale saved materials pause must not erase the later real decision.
    repo.update_job(job.job_id, stage="materials", pending_input=job.pending_input)
    assert not script_before_materials_is_approved(repo, repo.get_job(job.job_id))
    with pytest.raises(Conflict, match="人工确认"):
        JobService(repo).restart_unknown(job.job_id, restart_request(operation_id))


@pytest.mark.parametrize("changed", ["script", "audit", "approval", "source", "missing_source", "brief"])
def test_restart_checks_preserved_inputs_again_before_running(approved_unknown, monkeypatch, capsys, changed):
    repo, job, operation_id = approved_unknown
    updated = JobService(repo).restart_unknown(job.job_id, restart_request(operation_id))
    if changed in {"source", "missing_source"}:
        path = Path(repo.materials_restart_receipt(job.job_id, 2)["preserved_script"]["source_files"][0]["path"])
        if changed == "missing_source":
            path.unlink()
        else:
            path.write_text("UNIT mutated source", encoding="utf-8")
    elif changed in {"audit", "approval"}:
        kind = "writer_tool_audit" if changed == "audit" else "stage_review"
        artifact = next(item for item in updated.artifacts if item.kind == kind)
        repo.artifact_path(artifact.artifact_id)[0].write_text("UNIT changed", encoding="utf-8")
    elif changed == "brief":
        repo.update_job(job.job_id, brief=updated.brief.model_copy(update={"topic": "UNIT changed"}))
    else:
        script = updated.script.model_copy(deep=True)
        script.segments[0].narration += "UNIT changed"
        repo.update_job(job.job_id, script=script)
    monkeypatch.setattr(MaterialsNode, "__call__", lambda *a: pytest.fail("Invalid inherited inputs must stop"))
    code, summary = cli(monkeypatch, capsys, repo, "run", job.job_id)
    assert code == 1 and summary["status"] == "FAILED"
    assert repo.operation(job.job_id, "UNIT-old-material-input", "llm:materials")["status"] == "UNKNOWN"


def test_material_notes_change_actual_paid_call_fingerprint(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT notes fingerprint"))
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {"enabled": True, "provider": "codex_cli",
                                                                      "model": "UNIT-fixture"}}))
    captured = []
    def supplier(provider, model, timeout, prompt, schema, **kwargs):
        captured.append(prompt)
        return CliResult({"sources": [], "visuals": [], "limitations": []}, {})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", supplier)
    model = JsonModel(repo)
    for note in (NOTE, NOTE, NOTE + " changed"):
        model.invoke({"job_id": job.job_id, "revision": 1, "extras": {"materials_note": note}},
                     "materials", "UNIT instruction", fields=("extras",), research_directory=tmp_path)
    assert len(captured) == 2 and all(NOTE in prompt for prompt in captured)
    with repo.connection() as db:
        rows = db.execute("SELECT input_hash,status FROM operations").fetchall()
    assert len(rows) == 2 and rows[0][0] != rows[1][0] and all(row[1] == "COMPLETED" for row in rows)
