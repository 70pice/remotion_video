"""Photography recovery: real local media and gates, no external API calls."""

import json
import os
import struct
import subprocess
import sys
import wave
import zlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from videoagents.contracts import (
    Alignment,
    Asset,
    Brief,
    Job,
    RestartUnknownRequest,
    Script,
    ScriptSegment,
    SettingsPatch,
    Timeline,
)
from videoagents.main import main
from videoagents.nodes.common import state_context
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.voice import VoiceNode
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.director_recovery import validate_director_restart, verify_director_recovery_inputs
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService, voice_fingerprint
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint

SOURCE = "https://example.org/unit-photography-source"
CONTEXT_SOURCE = "https://context.example/unit-similar-product"
NOTE = "用户接受上次摄影提交可能已有用量，授权新尝试；保留文案与音频，组件套补真实画面缺口并标示示意。"
REAL_DIRECTOR_PLAN = DirectorNode.plan
REAL_VOICE_PREPARE = VoiceNode.prepare_audio


def cli(monkeypatch, capsys, repo, *args):
    monkeypatch.setattr(sys, "argv", ["videoagents", "--runtime-dir", str(repo.root), *args])
    code = main()
    return code, json.loads(capsys.readouterr().out)


def png(width=64, height=64):
    def chunk(kind, value):
        return struct.pack(">I", len(value)) + kind + value + struct.pack(">I", zlib.crc32(kind + value))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x40\x70\xa0" * width) * height)) + chunk(b"IEND", b""))


def request(job, **changes):
    return RestartUnknownRequest.model_validate({
        "base_revision": job.revision, "operation_id": job.pending_input["operation_id"],
        "director_only": True, "acknowledge_possible_usage": True, "note": NOTE, **changes,
    })


def operations(repo, job_id):
    with repo.connection() as db:
        return [tuple(row) for row in db.execute("SELECT * FROM operations WHERE job_id=? ORDER BY operation_id", (job_id,))]


def wav(path):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24000)
        stream.writeframes(b"\x01\x00" * 24000 * 6)


@pytest.fixture
def photography_unknown(tmp_path, monkeypatch, capsys, request):
    variant = getattr(request, "param", "generated")
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT photography", source_urls=[SOURCE], target_seconds=6))
    if variant.startswith("manual"):
        path = tmp_path / "manual-audio.wav"
        wav(path)
        alignment = {
            "origin": "manual", "verified": True, "note": "UNIT human checked imported timing",
            "segments": [{"segment_id": "s1", "text": "UNIT narration about real people and AI.",
                          "start_ms": 100, "end_ms": 5800}]}
        service.upload(job.job_id, path.read_bytes(), path.name, "audio", alignment=alignment)
        if variant == "manual_history":
            service.upload(job.job_id, path.read_bytes(), "second-manual-audio.wav", "audio", alignment=alignment)
        job = repo.get_job(job.job_id)
    SettingsService(repo).patch(SettingsPatch(role_models={
        "director": {"enabled": True, "provider": "codex_cli", "model": "UNIT-fixture"}}))
    monkeypatch.setattr("videoagents.main.PROJECT_ROOT", service.project_root)
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("No external LLM"))
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *a, **k: pytest.fail("No external TTS"))

    def writer(node, current, context):
        folder = repo.root / "jobs" / current.job_id / "revisions" / str(current.revision) / "skills-research"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "writer-read.txt").write_text("UNIT source read before human script confirmation", encoding="utf-8")
        service.write_json(current, "writer-audit.json", {"tools": ["UNIT read-only source"]}, "writer_tool_audit")
        return Script(title="UNIT reviewed", origin="model", revision=current.revision, segments=[
            ScriptSegment(segment_id="s1", narration="UNIT narration about real people and AI.",
                          source_refs=[SOURCE], visual_need="UNIT: real supporting image")])

    def materials(node, state):
        current = repo.get_job(state["job_id"])
        if variant == "carried_script" and current.revision == 1:
            operation = repo.start_operation(current.job_id, "UNIT-old-materials", "llm:materials", {"revision": 1})
            repo.finish_operation(operation["operation_id"], "UNKNOWN", {"revision": 1})
            from videoagents.nodes.common import request_input

            exc = CapabilityMissing("UNIT materials unknown", ["llm_operation"],
                                    operation_id=operation["operation_id"], operation_status="UNKNOWN")
            return request_input(repo, state, "materials", [str(exc)], exc.fields, exc)
        folder = repo.root / "jobs" / current.job_id / "revisions" / str(current.revision)
        folder.mkdir(parents=True, exist_ok=True)
        source = folder / "source.txt"
        source.write_text("UNIT first-party source fixture", encoding="utf-8")
        source_artifact = service.register_artifact(current, source, "source", "text/plain")
        repo.update_job(current.job_id, artifacts=current.artifacts + [source_artifact])
        visuals = []
        for index in range(3):
            current = repo.get_job(current.job_id)
            path = folder / f"visual-{index}.png"
            path.write_bytes(png())
            artifact = service.register_artifact(current, path, "asset", "image/png")
            visual_source = CONTEXT_SOURCE if variant.startswith("context") and index != 1 else SOURCE
            asset = Asset(asset_id=f"UNIT-visual-{index}", name=path.name, role="evidence", mime_type="image/png",
                          size_bytes=artifact.size_bytes, sha256=artifact.sha256, source_url=visual_source,
                          artifact_id=artifact.artifact_id, url=artifact.url,
                          timeline_src=f"videoagents/{current.job_id}/assets/{index}.png")
            repo.update_asset_metadata(asset.asset_id, {"origin": "capture", "width": 64, "height": 64})
            repo.update_job(current.job_id, assets=current.assets + [asset], artifacts=current.artifacts + [artifact])
            visuals.append({"asset_id": asset.asset_id, "kind": "screenshot", "source_url": visual_source,
                            "artifact_id": artifact.artifact_id, "description": "UNIT actual captured image"})
        current = repo.get_job(current.job_id)
        sources = [{"url": SOURCE, "text": source.read_text(), "sha256": source_artifact.sha256,
                    "artifact_id": source_artifact.artifact_id,
                    "asset_ids": [item["asset_id"] for item in visuals if item["source_url"] == SOURCE]}]
        if variant.startswith("context"):
            context_source = folder / "context-source.txt"
            context_source.write_text("UNIT unrelated product used only as illustration", encoding="utf-8")
            context_artifact = service.register_artifact(current, context_source, "source", "text/plain")
            repo.update_job(current.job_id, artifacts=current.artifacts + [context_artifact])
            current = repo.get_job(current.job_id)
            sources.append({"url": CONTEXT_SOURCE, "text": context_source.read_text(),
                            "sha256": context_artifact.sha256, "artifact_id": context_artifact.artifact_id,
                            "asset_ids": [item["asset_id"] for item in visuals if item["source_url"] == CONTEXT_SOURCE]})
        service.write_json(current, "material-audit.json", {"tools": ["UNIT tool process must not reach model"]},
                           "material_tool_audit")
        if variant == "context_missing_visual":
            visuals = [item for item in visuals if item["asset_id"] != "UNIT-visual-0"]
        if variant == "context_missing_source_link":
            sources[-1]["asset_ids"].remove("UNIT-visual-0")
        if variant == "context_string_asset_ids":
            sources[-1]["asset_ids"] = ",".join(sources[-1]["asset_ids"])
        service.write_json(current, "research.json", {"sources": sources, "visuals": visuals,
            "limitations": ["UNIT one real-world view is unavailable"]}, "research")
        return state_context(repo, state, route="human_review_script")

    def audio(node, current, command_id="", prefer_generation=False, state=None):
        folder = repo.root / "jobs" / current.job_id / "revisions" / str(current.revision)
        path = folder / "narration.wav"
        wav(path)
        artifact = service.register_artifact(current, path, "voice", "audio/wav")
        asset = Asset(asset_id="UNIT-real-audio", name=path.name, role="audio", mime_type="audio/wav",
                      size_bytes=artifact.size_bytes, sha256=artifact.sha256, artifact_id=artifact.artifact_id,
                      url=artifact.url, timeline_src=f"videoagents/{current.job_id}/assets/narration.wav")
        alignment = Alignment(origin="provider", verified=True, audio_sha256=asset.sha256,
            note="UNIT recorded timing", segments=[{"segment_id": "s1", "text": current.script.segments[0].narration,
                                                   "start_ms": 100, "end_ms": 5800}])
        service.write_json(current, "voice_guidance.json", {"delivery_notes": ["UNIT preserve natural pauses"]},
                           "voice_guidance")
        repo.attach_generated_audio(current.job_id, current.revision, asset, artifact, {
            "origin": "byte_ws", "duration_seconds": 6.0, "alignment": alignment.model_dump(),
            "script_fingerprint": fingerprint([{"segment_id": "s1", "narration": current.script.segments[0].narration}]),
            "voice_fingerprint": voice_fingerprint(SettingsService(repo).internal()),
        })
        return asset, alignment, 6.0

    def unknown(node, current, *args, **kwargs):
        ledger = {"revision": current.revision, "reason": "cli_timeout", "command_id": "UNIT-old-command"}
        operation = repo.start_operation(current.job_id, "UNIT-old-director-input", "llm:director", ledger)
        repo.finish_operation(operation["operation_id"], "UNKNOWN", ledger)
        raise CapabilityMissing("UNIT photography unknown", ["llm_operation"],
                                operation_id=operation["operation_id"], operation_status="UNKNOWN")

    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.write", writer)
    monkeypatch.setattr(MaterialsNode, "__call__", materials)
    monkeypatch.setattr(VoiceNode, "prepare_audio", REAL_VOICE_PREPARE if variant.startswith("manual") else audio)
    monkeypatch.setattr(DirectorNode, "plan", unknown)
    assert cli(monkeypatch, capsys, repo, "run", job.job_id)[0] == 0
    assert repo.get_job(job.job_id).pending_input["node_name"] == "script_human_gate"
    assert cli(monkeypatch, capsys, repo, "resume", job.job_id, "--decision", "confirm", "--note",
               "UNIT reviewed script and read source; collect now")[0] == 0
    if variant == "carried_script":
        paused_materials = repo.get_job(job.job_id)
        assert paused_materials.stage == "materials"
        service.restart_unknown(job.job_id, RestartUnknownRequest(
            base_revision=1, operation_id=paused_materials.pending_input["operation_id"],
            acknowledge_possible_usage=True, materials_only=True,
            note="UNIT authorized new materials attempt, possible usage acknowledged", materials_note="UNIT collect real images"))
        assert cli(monkeypatch, capsys, repo, "run", job.job_id)[0] == 0
    assert cli(monkeypatch, capsys, repo, "select-materials", job.job_id,
               "--accept-asset", "UNIT-visual-0", "--accept-asset", "UNIT-visual-1",
               "--reject-asset", "UNIT-visual-2", "--note", "UNIT reject unrelated image, keep two")[0] == 0
    joint = repo.get_job(job.job_id)
    assert cli(monkeypatch, capsys, repo, "resume", job.job_id, "--decision", "confirm", "--note",
               "UNIT joint script and two real images fully reviewed")[0] == 0
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.stage == "director"
    # Feishu identity is independently persisted and must survive this recovery.
    with repo.connection(immediate=True) as db:
        db.execute("INSERT INTO job_inputs VALUES(?,?,?)", (job.job_id, "feishu_review_base", '{"base_token":"UNIT-base"}'))
    return repo, service, paused, joint


def fresh_restart(repo, job, note=NOTE):
    return subprocess.run([sys.executable, "-m", "videoagents.main", "--runtime-dir", str(repo.root),
        "restart-unknown", job.job_id, "--operation-id", job.pending_input["operation_id"],
        "--acknowledge-possible-usage", "--director-only", "--note", note],
        capture_output=True, text=True, encoding="utf-8", cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "PYTHONUTF8": "1", "PYTHONPATH": str(Path(__file__).resolve().parents[2])}, timeout=30)


def test_preflight_reads_only_and_reconstructs_partial_selection_joint_projection(photography_unknown):
    repo, service, job, joint = photography_unknown
    before_events, before_operations = repo.events_after(job.job_id, 0), operations(repo, job.job_id)
    proof = verify_director_recovery_inputs(repo, job)
    assert proof["audio_asset_id"] == "UNIT-real-audio"
    projected = job.model_validate(proof["approval_projection"])
    gate = HumanReviewNode(repo, node_name="human_review_script")
    assert gate._inputs(projected) == joint.pending_input["dependency_fingerprint"]
    assert projected.assets == joint.assets and len(projected.assets) == 2
    assert {item.artifact_id for item in projected.artifacts if item.kind != "stage_review"} == {
        item.artifact_id for item in joint.artifacts if item.kind != "stage_review"}
    approval = next(item for item in job.artifacts if item.artifact_id == proof["approval_artifact_id"])
    assert "subject" not in json.loads(repo.artifact_path(approval.artifact_id)[0].read_text(encoding="utf-8"))
    assert repo.get_job(job.job_id) == job and repo.events_after(job.job_id, 0) == before_events
    assert operations(repo, job.job_id) == before_operations


def test_fresh_cli_saves_one_draft_then_normal_graph_only_photography_and_shot_gate(
        photography_unknown, monkeypatch, capsys):
    repo, service, job, joint = photography_unknown
    before_operations = operations(repo, job.job_id)
    originals = {item.artifact_id: repo.artifact_path(item.artifact_id)[0].read_bytes() for item in job.artifacts}
    result = fresh_restart(repo, job)
    assert result.returncode == 0, result.stderr
    fresh = Repository(repo.root)
    draft = fresh.get_job(job.job_id)
    assert (draft.revision, draft.status, draft.stage) == (2, "DRAFT", "idle")
    assert draft.brief == job.brief and draft.assets == job.assets
    assert draft.script.model_copy(update={"revision": 1}) == job.script
    assert draft.timeline is None and draft.pending_input is None and draft.review is None
    assert operations(fresh, job.job_id) == before_operations
    assert validate_director_restart(fresh, draft)["audio_asset_id"] == "UNIT-real-audio"
    assert fresh_restart(fresh, job).returncode == 0 and fresh.get_job(job.job_id) == draft
    with fresh.connection() as db:
        assert db.execute("SELECT value FROM job_inputs WHERE key='feishu_review_base'").fetchone()[0] == '{"base_token":"UNIT-base"}'
        assert db.execute("SELECT COUNT(*) FROM commands WHERE payload LIKE '%\"base_revision\":2%'").fetchone()[0] == 0
    calls = []

    def model_call(model, job_id, revision, role, instruction, context, *args, **kwargs):
        assert revision == 2 and role == "director"
        assert context["extras"]["director_note"] == NOTE
        assert "明确标为“示意”" in instruction
        assert context["research"]["sources"][0]["text"] == "UNIT first-party source fixture"
        assert not {"human_reviews", "human_decision", "pending_input", "operations", "preserved_director"} & context.keys()
        assert not {"previous_job", "request_hash", "authorized_model_restart", "human_feedback"} & context["extras"].keys()
        calls.append(context)
        return {"shots": context["timeline"]["shots"],
                "segment_performances": [{"segment_id": "s1", "shot_ids": ["shot-1"],
                    "component_reason": "UNIT image supports narration", "visual_action": "UNIT read source image"}],
                "shot_reviews": [{"shot_id": "shot-1", "review_frame": 60,
                    "component_reason": "UNIT real image readability", "visual_action": "UNIT image remains readable"}]}

    def frames(project, timeline_path, request_path, output, *args):
        images = []
        for item in json.loads(request_path.read_text(encoding="utf-8")):
            path = output.parent / (item["shot_id"] + ".png")
            path.write_bytes(png(1080, 1920))
            images.append({**item, "width": 1080, "height": 1920, "path": str(path)})
        output.write_text(json.dumps(images), encoding="utf-8")
        return {"images": images}

    monkeypatch.setattr(DirectorNode, "plan", REAL_DIRECTOR_PLAN)
    monkeypatch.setattr(JsonModel, "call", model_call)
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frames)
    for node in ("screenwriter.ScreenwriterNode", "materials.MaterialsNode", "voice.VoiceNode", "editing.EditingNode"):
        monkeypatch.setattr(f"videoagents.nodes.{node}.__call__", lambda *a: pytest.fail("Must skip writer/materials/voice/editing"))
    assert cli(monkeypatch, capsys, fresh, "run", job.job_id)[0] == 0
    after = fresh.get_job(job.job_id)
    assert after.status == "NEEDS_HUMAN" and after.pending_input["node_name"] == "director_human_gate"
    assert after.pending_input["review_mode"] == "per_shot_stills" and len(calls) == 1
    assert after.pending_input["required_shot_ids"] == ["shot-1"]
    assert {item["asset_id"] for item in calls[0]["research"]["visuals"]} == {"UNIT-visual-0", "UNIT-visual-1"}
    assert after.assets == job.assets and after.timeline.audio_src == job.assets[-1].timeline_src
    assert not any(item.kind == "final" or (item.kind == "stage_review" and item.revision == 2) for item in after.artifacts)
    assert operations(fresh, job.job_id) == before_operations
    assert cli(monkeypatch, capsys, fresh, "run", job.job_id)[0] == 0 and len(calls) == 1
    assert fresh_restart(fresh, job).returncode == 0 and fresh.get_job(job.job_id) == after
    for artifact_id, data in originals.items():
        assert fresh.artifact_path(artifact_id)[0].read_bytes() == data


@pytest.mark.parametrize("changes", [
    {"director_only": "true"}, {"director_only": 1}, {"acknowledge_possible_usage": False},
    {"acknowledge_possible_usage": 1}, {"brief": Brief(topic="UNIT changed")},
    {"materials_only": True, "materials_note": "UNIT collect"}, {"rebuild_script": True},
    {"materials_note": "UNIT collect"}, {"note": " "},
])
def test_director_scope_contract_requires_explicit_unchanged_inputs(changes):
    with pytest.raises(ValidationError):
        RestartUnknownRequest.model_validate({"base_revision": 1, "operation_id": "a" * 32,
            "director_only": True, "acknowledge_possible_usage": True, "note": NOTE, **changes})


@pytest.mark.parametrize("invalid", ["approval_missing", "visual_metadata", "brief", "script", "visual_file",
    "source_file", "audio_file", "audio_missing", "alignment", "script_fingerprint", "voice_fingerprint",
    "audio_report", "guidance_missing", "wrong_provider", "wrong_operation_revision", "wrong_pending",
    "cancelled", "active_command", "other_unknown", "revise_note", "voice_note", "later_revise"])
def test_director_recovery_rejects_unverified_or_unsafe_inputs_without_saving(photography_unknown, invalid):
    repo, service, job, _ = photography_unknown
    req = request(job)
    if invalid == "approval_missing":
        proof = verify_director_recovery_inputs(repo, job)
        repo.update_job(job.job_id, artifacts=[item for item in job.artifacts
                                              if item.artifact_id != proof["approval_artifact_id"]])
    elif invalid in {"visual_metadata", "alignment", "script_fingerprint", "voice_fingerprint"}:
        asset = job.assets[0] if invalid == "visual_metadata" else job.assets[-1]
        metadata = repo.asset_metadata(asset.asset_id)
        if invalid == "visual_metadata":
            metadata["width"] = 999
        elif invalid == "alignment":
            metadata["alignment"]["segments"][0]["text"] = "UNIT wrong narration"
        else:
            metadata[invalid] = "UNIT wrong hash"
        repo.update_asset_metadata(asset.asset_id, metadata)
    elif invalid in {"brief", "script"}:
        value = getattr(job, invalid).model_copy(deep=True)
        if invalid == "brief":
            value.topic = "UNIT modified topic"
        else:
            value.segments[0].narration += " changed"
        repo.update_job(job.job_id, **{invalid: value})
    elif invalid in {"visual_file", "source_file", "audio_file", "audio_missing", "audio_report"}:
        kind = {"visual_file": "asset", "source_file": "source", "audio_file": "voice",
                "audio_missing": "voice", "audio_report": "audio_report"}[invalid]
        path = repo.artifact_path(next(item.artifact_id for item in job.artifacts if item.kind == kind))[0]
        if invalid == "audio_missing":
            path.unlink()
        else:
            path.write_bytes(b"UNIT changed bytes")
    elif invalid == "guidance_missing":
        repo.update_job(job.job_id, artifacts=[item for item in job.artifacts if item.kind != "voice_guidance"])
    elif invalid in {"wrong_provider", "wrong_operation_revision"}:
        with repo.connection(immediate=True) as db:
            if invalid == "wrong_provider":
                db.execute("UPDATE operations SET provider='llm:editing' WHERE operation_id=?", (req.operation_id,))
            else:
                db.execute("UPDATE operations SET body=? WHERE operation_id=?", ('{"revision":99}', req.operation_id))
    elif invalid == "wrong_pending":
        repo.update_job(job.job_id, pending_input={**job.pending_input, "revision": 99})
    elif invalid == "cancelled":
        repo.cancel(job.job_id)
    elif invalid == "active_command":
        with repo.connection(immediate=True) as db:
            db.execute("UPDATE commands SET status='CLAIMED' WHERE job_id=? AND command_id=("
                       "SELECT command_id FROM commands WHERE job_id=? ORDER BY created_at DESC LIMIT 1)",
                       (job.job_id, job.job_id))
    elif invalid == "other_unknown":
        operation = repo.start_operation(job.job_id, "UNIT-other-input", "llm:editing", {"revision": 1})
        repo.finish_operation(operation["operation_id"], "UNKNOWN", {"revision": 1})
    elif invalid == "later_revise":
        artifact = next(item for item in reversed(job.artifacts) if item.kind == "stage_review")
        receipt = json.loads(repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8"))
        receipt.update(decision="revise", note="UNIT requires narration revision", pending_token="UNIT-later-revise")
        HumanReviewNode(repo, node_name="human_review_script")._record(job, receipt, "NEEDS_INPUT", "UNIT later decision")
        repo.update_job(job.job_id, stage="director", pending_input=job.pending_input)
    else:
        req = req.model_copy(update={"note": "重写文案" if invalid == "revise_note" else "调整语速"})
    before, events, ledger = repo.get_job(job.job_id), repo.events_after(job.job_id, 0), operations(repo, job.job_id)
    with pytest.raises((Conflict, ValueError)):
        JobService(repo).restart_unknown(job.job_id, req)
    assert repo.get_job(job.job_id) == before and repo.events_after(job.job_id, 0) == events
    assert operations(repo, job.job_id) == ledger and repo.director_restart_receipt(job.job_id, 2) is None


@pytest.mark.parametrize("changed", ["source", "approval", "audio", "metadata", "brief", "script"])
def test_run_rechecks_preserved_evidence_before_any_model(photography_unknown, monkeypatch, capsys, changed):
    repo, _, job, _ = photography_unknown
    draft = JobService(repo).restart_unknown(job.job_id, request(job))
    if changed in {"source", "approval", "audio"}:
        proof = repo.director_restart_receipt(job.job_id, 2)["preserved_director"]
        artifact_id = (proof["approval_artifact_id"] if changed == "approval" else
                       next(item.artifact_id for item in draft.artifacts if item.kind == {"source": "source", "audio": "voice"}[changed]))
        repo.artifact_path(artifact_id)[0].write_bytes(b"UNIT changed after authorization")
    elif changed == "metadata":
        repo.update_asset_metadata(draft.assets[-1].asset_id, {"origin": "upload", "duration_seconds": 6})
    elif changed == "brief":
        repo.update_job(job.job_id, brief=draft.brief.model_copy(update={"topic": "UNIT changed"}))
    else:
        script = draft.script.model_copy(deep=True)
        script.segments[0].narration += "UNIT changed"
        repo.update_job(job.job_id, script=script)
    monkeypatch.setattr(JsonModel, "call", lambda *a, **k: pytest.fail("Must reject before model"))
    monkeypatch.setattr(DirectorNode, "__call__", lambda *a: pytest.fail("Must reject before photography"))
    code, summary = cli(monkeypatch, capsys, repo, "run", job.job_id)
    assert code == 1 and summary["status"] == "FAILED"
    assert repo.operation(job.job_id, "UNIT-old-director-input", "llm:director")["status"] == "UNKNOWN"


def test_concurrent_same_authorization_is_atomic_and_note_changes_conflict(photography_unknown):
    repo, _, job, _ = photography_unknown
    req = request(job)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: JobService(Repository(repo.root)).restart_unknown(job.job_id, req), range(2)))
    assert [item.revision for item in results] == [2, 2]
    with pytest.raises(Conflict):
        JobService(repo).restart_unknown(job.job_id, req.model_copy(update={"note": NOTE + " new direction"}))
    events = [item for item in repo.events_after(job.job_id, 0) if item["payload"].get("type") == "unknown_restart_authorized"]
    assert len(events) == 1


@pytest.mark.parametrize("photography_unknown", ["manual", "manual_history", "carried_script"], indirect=True)
def test_projection_accepts_preapproved_imported_audio_and_real_script_carry_chain(photography_unknown):
    repo, service, job, joint = photography_unknown
    proof = verify_director_recovery_inputs(repo, job)
    projection = Job.model_validate(proof["approval_projection"])
    assert HumanReviewNode(repo, node_name="human_review_script")._inputs(projection) == joint.pending_input["dependency_fingerprint"]
    assert projection.assets == joint.assets
    draft = service.restart_unknown(job.job_id, RestartUnknownRequest(
        base_revision=job.revision, operation_id=job.pending_input["operation_id"],
        acknowledge_possible_usage=True, director_only=True, note=NOTE))
    assert draft.revision == job.revision + 1 and draft.assets == job.assets
    assert validate_director_restart(repo, draft)["approval_artifact_id"] == proof["approval_artifact_id"]
    assert repo.asset_metadata(proof["audio_asset_id"])["alignment"] == proof["asset_metadata"][proof["audio_asset_id"]]["alignment"]


def test_second_explicit_director_unknown_recovery_keeps_same_real_joint_evidence(photography_unknown):
    repo, service, job, _ = photography_unknown
    draft = service.restart_unknown(job.job_id, request(job))
    proof = validate_director_restart(repo, draft)
    operation = repo.start_operation(job.job_id, "UNIT-second-director", "llm:director", {"revision": 2})
    repo.finish_operation(operation["operation_id"], "UNKNOWN", {"revision": 2})
    pending = {**job.pending_input, "revision": 2, "operation_id": operation["operation_id"]}
    paused = repo.update_job(job.job_id, status="NEEDS_INPUT", stage="director", pending_input=pending)
    next_draft = service.restart_unknown(job.job_id, request(paused))
    assert next_draft.revision == 3 and next_draft.assets == job.assets
    assert validate_director_restart(repo, next_draft)["approval_artifact_id"] == proof["approval_artifact_id"]
    assert repo.operation(job.job_id, "UNIT-old-director-input", "llm:director")["status"] == "UNKNOWN"
    assert repo.operation(job.job_id, "UNIT-second-director", "llm:director")["status"] == "UNKNOWN"


def test_photography_note_changes_the_existing_model_call_fingerprint(tmp_path, monkeypatch):
    from videoagents.providers.cli_runner import CliResult

    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT note fingerprint"))
    SettingsService(repo).patch(SettingsPatch(role_models={
        "director": {"enabled": True, "provider": "codex_cli", "model": "UNIT-fixture"}}))
    prompts = []

    def supplier(provider, model, timeout, prompt, schema, **kwargs):
        prompts.append(prompt)
        return CliResult({"unit": True}, {})

    monkeypatch.setattr("videoagents.providers.llm.run_cli", supplier)
    for note in (NOTE, NOTE, NOTE + " additional readable real image"):
        JsonModel(repo).invoke({"job_id": job.job_id, "revision": 1, "extras": {"director_note": note}},
                              "director", "UNIT instruction", fields=("extras",))
    assert len(prompts) == 2 and all(NOTE in prompt for prompt in prompts)
    ledger = operations(repo, job.job_id)
    assert len(ledger) == 2 and all(row[4] == "COMPLETED" for row in ledger)


def test_recovery_voice_only_action_stops_without_photography_or_resynthesis(photography_unknown, monkeypatch, capsys):
    repo, service, job, _ = photography_unknown
    draft = service.restart_unknown(job.job_id, request(job))
    ledger = operations(repo, job.job_id)
    for node in ("voice.VoiceNode", "director.DirectorNode", "materials.MaterialsNode", "screenwriter.ScreenwriterNode"):
        monkeypatch.setattr(f"videoagents.nodes.{node}.__call__", lambda *a: pytest.fail("voice-only uses frozen audio gate"))
    code, summary = cli(monkeypatch, capsys, repo, "run", job.job_id, "--action", "voice")
    assert code == 0 and (summary["status"], summary["stage"]) == ("DRAFT", "voice")
    after = repo.get_job(job.job_id)
    assert after.assets == draft.assets and after.timeline is None and after.pending_input is None
    assert operations(repo, job.job_id) == ledger


def test_recovery_clears_old_photography_and_editing_references_without_deleting_files(photography_unknown):
    repo, service, job, _ = photography_unknown
    audio = job.assets[-1]
    timeline = Timeline(job_id=job.job_id, revision=job.revision, width=1080, height=1920, fps=30,
        duration_in_frames=180, audio_src=audio.timeline_src, shots=[{
            "shot_id": "old-shot", "start_frame": 0, "end_frame": 180,
            "component_id": "evidence", "title": "UNIT old design", "asset_src": job.assets[0].timeline_src}])
    repo.update_job(job.job_id, timeline=timeline)
    for kind in ("timeline", "storyboard", "director_plan", "component_study", "director_shot_review",
                 "shot_review_frame", "preview", "final", "editing_guidance", "human_feedback_applied"):
        service.write_json(repo.get_job(job.job_id), f"old-{kind}.json", {"UNIT": "old derived output"}, kind)
    before = repo.get_job(job.job_id)
    files = {item.artifact_id: repo.artifact_path(item.artifact_id)[0].read_bytes() for item in before.artifacts}
    draft = service.restart_unknown(job.job_id, request(before))
    assert draft.timeline is None and draft.review is None and draft.script_discussion is None
    assert {item.kind for item in draft.artifacts} <= {"script", "writer_tool_audit", "source", "asset", "research",
        "material_tool_audit", "stage_review", "voice", "voice_guidance", "alignment", "audio_report"}
    assert validate_director_restart(repo, draft)["audio_asset_id"] == audio.asset_id
    for artifact_id, data in files.items():
        assert repo.artifact_path(artifact_id)[0].read_bytes() == data
