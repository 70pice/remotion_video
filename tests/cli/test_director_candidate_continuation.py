"""Use real recovery, graph, model fingerprint and media; all providers are fixtures."""

import copy
import json

import pytest
from test_director_only_restart import (
    REAL_DIRECTOR_PLAN,
    cli,
    operations,
    png,
    request,
)
from test_director_only_restart import photography_unknown as photography_unknown

from videoagents.contracts import SettingsPatch, Timeline
from videoagents.nodes.director import DirectorNode
from videoagents.providers.cli_runner import CliFailure, CliResult
from videoagents.providers.llm import CapabilityMissing, JsonModel, request_fingerprint, semantic
from videoagents.services.director_recovery import (
    _model_identity,
    validate_director_restart,
    verify_director_candidate_continuation,
)
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint


def result_for(shots):
    return {"shots": shots,
            "segment_performances": [{"segment_id": "s1", "shot_ids": [s["shot_id"] for s in shots],
                                      "component_reason": "UNIT preserve useful design", "visual_action": "UNIT read"}],
            "shot_reviews": [{"shot_id": s["shot_id"], "review_frame": s["start_frame"] + 30,
                              "component_reason": "UNIT representative view", "visual_action": "UNIT read"}
                             for s in shots]}


@pytest.fixture
def completed_then_unknown(photography_unknown, monkeypatch, capsys):
    repo, service, job, joint = photography_unknown
    draft = service.restart_unknown(job.job_id, request(job))
    calls = []

    def provider(provider, model, timeout, prompt, schema, **kwargs):
        context = json.loads(prompt.split("上下文：\n", 1)[1])
        calls.append(copy.deepcopy(context))
        if len(calls) == 1:
            baseline = context["timeline"]["shots"][0]
            assert context["timeline"]["duration_in_frames"] == 1440
            shots = [{**copy.deepcopy(baseline), "shot_id": f"candidate-{i + 1}",
                      "start_frame": i * 90, "end_frame": (i + 1) * 90,
                      "title": f"UNIT saved candidate {i + 1}", "body": ""} for i in range(16)]
            shots[0]["end_frame"] = shots[1]["start_frame"] = 60
            return CliResult(result_for(shots), {})
        raise CliFailure("cli_nonzero_exit", submitted=True)

    monkeypatch.setattr(DirectorNode, "plan", REAL_DIRECTOR_PLAN)
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda provider: ["UNIT-fixture"])
    monkeypatch.setattr("videoagents.providers.llm.run_cli", provider)
    assert cli(monkeypatch, capsys, repo, "run", job.job_id)[0] == 0
    rejected = repo.get_job(job.job_id)
    assert rejected.timeline is None and rejected.status == "NEEDS_INPUT"
    assert "阅读" in "；".join(rejected.pending_input["issues"])
    completed = repo.latest_completed_operation(job.job_id, "llm:director", draft.revision)
    assert len(completed["result"]["shots"]) == 16
    assert cli(monkeypatch, capsys, repo, "resume", job.job_id, "--decision", "confirm", "--note",
               "UNIT continue repairing saved candidate, preserve audio")[0] == 0
    paused = repo.get_job(job.job_id)
    assert paused.pending_input["operation_status"] == "UNKNOWN" and len(calls) == 2
    assert calls[1]["extras"]["timeline_repair_candidate"]["operation_id"] == completed["operation_id"]
    assert calls[1]["extras"]["timeline_repair_note"] == "UNIT continue repairing saved candidate, preserve audio"
    assert "human_decision" not in calls[1]
    return repo, service, paused, completed, calls


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
def test_normal_restart_run_continues_completed_candidate_without_rebuilding_upstream(
    completed_then_unknown, monkeypatch, capsys,
):
    repo, service, paused, completed, calls = completed_then_unknown
    before = operations(repo, paused.job_id)
    old_assets = copy.deepcopy(paused.assets)
    draft = service.restart_unknown(paused.job_id, request(paused))
    assert draft.revision == paused.revision + 1 and draft.timeline is None

    def repair(provider, model, timeout, prompt, schema, **kwargs):
        context = json.loads(prompt.split("上下文：\n", 1)[1])
        candidate = context["extras"].get("timeline_repair_candidate")
        assert candidate and candidate["operation_id"] == completed["operation_id"]
        assert candidate["result"] == completed["result"]
        assert len(context["timeline"]["shots"]) == 16
        assert context["timeline"]["shots"][0]["title"] == "UNIT saved candidate 1"
        assert "保留无问题镜头" in prompt
        assert "阅读" in "；".join(context["extras"]["timeline_repair_issues"])
        shots = copy.deepcopy(candidate["result"]["shots"])
        shots[0]["end_frame"] = shots[1]["start_frame"] = 90
        return CliResult(result_for(shots), {})

    def frames(project, timeline_path, request_path, output, *args):
        images = []
        for item in json.loads(request_path.read_text(encoding="utf-8")):
            path = output.parent / (item["shot_id"] + ".png")
            path.write_bytes(png(1080, 1920))
            images.append({**item, "width": 1080, "height": 1920, "path": str(path)})
        output.write_text(json.dumps(images), encoding="utf-8")
        return {"images": images}

    monkeypatch.setattr("videoagents.providers.llm.run_cli", repair)
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frames)
    for node in ("screenwriter.ScreenwriterNode", "materials.MaterialsNode", "voice.VoiceNode", "editing.EditingNode"):
        monkeypatch.setattr(f"videoagents.nodes.{node}.__call__", lambda *a: pytest.fail("Must skip upstream/final"))
    assert cli(monkeypatch, capsys, repo, "run", paused.job_id)[0] == 0
    after = repo.get_job(paused.job_id)
    assert after.status == "NEEDS_HUMAN" and after.pending_input["node_name"] == "director_human_gate"
    assert after.assets == old_assets and len(after.timeline.shots) == 16
    assert after.timeline.shots[0].title == "UNIT saved candidate 1"
    assert [s.model_dump() for s in after.timeline.shots[2:]] == completed["result"]["shots"][2:]
    assert not any(a.kind == "final" for a in after.artifacts)
    assert [r for r in operations(repo, paused.job_id) if r[0] in {r[0] for r in before}] == before


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
def test_candidate_discovery_is_read_only_and_does_not_release_unknown_barrier(
    completed_then_unknown, monkeypatch,
):
    repo, service, paused, completed, calls = completed_then_unknown
    before = operations(repo, paused.job_id)
    events = repo.events_after(paused.job_id, 0)
    proof = verify_director_candidate_continuation(repo, paused)
    assert proof["available"] and proof["operation_id"] == completed["operation_id"]
    assert proof["source_revision"] == paused.revision and proof["shot_count"] == 16
    assert "result" not in proof and "source_pending" not in proof
    assert "阅读" in "；".join(proof["repair_issues"])
    assert repo.get_job(paused.job_id) == paused and repo.events_after(paused.job_id, 0) == events
    assert operations(repo, paused.job_id) == before
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("UNKNOWN replay"))
    with pytest.raises(CapabilityMissing, match="状态未知"):
        JsonModel(repo).call(paused.job_id, paused.revision, "director", "UNIT new input", {})
    assert operations(repo, paused.job_id) == before


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
def test_unknown_partial_output_never_replaces_complete_candidate(completed_then_unknown):
    repo, service, paused, completed, calls = completed_then_unknown
    with repo.connection(immediate=True) as db:
        identifier = paused.pending_input["operation_id"]
        body = json.loads(db.execute("SELECT body FROM operations WHERE operation_id=?", (identifier,)).fetchone()[0])
        body["result"] = {"shots": [{"shot_id": "UNIT unknown partial"}]}
        db.execute("UPDATE operations SET body=? WHERE operation_id=?", (json.dumps(body), identifier))
    before = operations(repo, paused.job_id)
    proof = verify_director_candidate_continuation(repo, paused)
    assert proof["operation_id"] == completed["operation_id"] and proof["shot_count"] == 16
    draft = service.restart_unknown(paused.job_id, request(paused))
    assert validate_director_restart(repo, draft)["candidate_continuation"]["operation_id"] == completed["operation_id"]
    assert operations(repo, paused.job_id) == before


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
def test_accepted_previous_timeline_keeps_existing_rebuild_semantics(completed_then_unknown):
    repo, service, paused, completed, calls = completed_then_unknown
    shots = copy.deepcopy(completed["result"]["shots"])
    shots[0]["end_frame"] = shots[1]["start_frame"] = 90
    audio = paused.assets[-1]
    metadata = repo.asset_metadata(audio.asset_id)
    timeline = Timeline(job_id=paused.job_id, revision=paused.revision, width=1080, height=1920, fps=30,
        duration_in_frames=1440, audio_src=audio.timeline_src, shots=shots,
        captions=[{k: c[k] for k in ("text", "start_ms", "end_ms")} for c in metadata["alignment"]["segments"]])
    current = repo.update_job(paused.job_id, timeline=timeline)
    assert verify_director_candidate_continuation(repo, current)["available"] is False
    draft = service.restart_unknown(current.job_id, request(current))
    assert "candidate_continuation" not in validate_director_restart(repo, draft)


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
def test_repeated_recovery_inherits_proven_candidate_ignoring_unproven_newer_completion(
    completed_then_unknown,
):
    repo, service, paused, completed, calls = completed_then_unknown
    draft = service.restart_unknown(paused.job_id, request(paused))
    saved = validate_director_restart(repo, draft)["candidate_continuation"]
    newer = repo.start_operation(paused.job_id, "UNIT-unproven-repaired-response", "llm:director",
                                {"revision": draft.revision})
    repo.finish_operation(newer["operation_id"], "COMPLETED",
                          {"revision": draft.revision, "result": {"shots": [{"shot_id": "UNIT not proven"}]}})
    unknown = repo.start_operation(paused.job_id, "UNIT-new-unknown", "llm:director", {"revision": draft.revision})
    repo.finish_operation(unknown["operation_id"], "UNKNOWN", {"revision": draft.revision})
    pending = {**paused.pending_input, "revision": draft.revision, "operation_id": unknown["operation_id"]}
    again = repo.update_job(paused.job_id, status="NEEDS_INPUT", stage="director", pending_input=pending)
    old_operations = operations(repo, paused.job_id)
    second = service.restart_unknown(paused.job_id, request(again))
    assert validate_director_restart(repo, second)["candidate_continuation"] == saved
    assert verify_director_candidate_continuation(repo, second)["operation_id"] == completed["operation_id"]
    assert operations(repo, paused.job_id) == old_operations


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
@pytest.mark.parametrize("change", ["input_hash", "empty_shots", "wrong_role", "wrong_job", "wrong_revision", "model"])
def test_unproven_completed_candidate_is_rejected_before_new_revision(
    completed_then_unknown, change,
):
    repo, service, paused, completed, calls = completed_then_unknown
    with repo.connection(immediate=True) as db:
        row = db.execute("SELECT body FROM operations WHERE operation_id=?", (completed["operation_id"],)).fetchone()
        body = json.loads(row[0])
        if change == "input_hash":
            db.execute("UPDATE operations SET input_hash='UNIT wrong input' WHERE operation_id=?", (completed["operation_id"],))
        elif change == "empty_shots":
            body["result"]["shots"] = []
        elif change == "wrong_role":
            db.execute("UPDATE operations SET provider='llm:voice' WHERE operation_id=?", (completed["operation_id"],))
        elif change == "wrong_job":
            db.execute("UPDATE operations SET job_id='UNIT other job' WHERE operation_id=?", (completed["operation_id"],))
        elif change == "wrong_revision":
            body["revision"] -= 1
        db.execute("UPDATE operations SET body=? WHERE operation_id=?", (json.dumps(body), completed["operation_id"]))
    if change == "model":
        SettingsService(repo).patch(SettingsPatch(role_models={
            "director": {"enabled": True, "provider": "codex_cli", "model": "UNIT different model"}}))
    if change in {"wrong_role", "wrong_job"}:
        # Correct discovery excludes another task/role/version entirely.
        assert verify_director_candidate_continuation(repo, paused)["available"] is False
    else:
        with pytest.raises(Conflict):
            service.restart_unknown(paused.job_id, request(paused))
    assert repo.get_job(paused.job_id) == paused


@pytest.mark.parametrize("photography_unknown", ["sixteen_shots"], indirect=True)
@pytest.mark.parametrize("change", ["operation", "unknown", "script", "metadata", "model"])
def test_saved_candidate_rechecks_original_evidence_before_model(
    completed_then_unknown, change, monkeypatch,
):
    repo, service, paused, completed, calls = completed_then_unknown
    draft = service.restart_unknown(paused.job_id, request(paused))
    if change in {"operation", "unknown"}:
        identifier = completed["operation_id"] if change == "operation" else paused.pending_input["operation_id"]
        with repo.connection(immediate=True) as db:
            body = json.loads(db.execute("SELECT body FROM operations WHERE operation_id=?", (identifier,)).fetchone()[0])
            body["UNIT changed"] = True
            db.execute("UPDATE operations SET body=? WHERE operation_id=?", (json.dumps(body), identifier))
    elif change == "script":
        draft = draft.model_copy(deep=True)
        draft.script.segments[0].narration += " altered"
    elif change == "metadata":
        metadata = repo.asset_metadata(draft.assets[0].asset_id)
        repo.update_asset_metadata(draft.assets[0].asset_id, {**metadata, "width": 99})
    else:
        SettingsService(repo).patch(SettingsPatch(role_models={
            "director": {"enabled": True, "provider": "codex_cli", "model": "UNIT changed model"}}))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("Changed proof submitted"))
    with pytest.raises(Conflict):
        validate_director_restart(repo, draft)


@pytest.mark.parametrize("provider,effort,research", [
    ("codex_cli", None, False), ("codex_cli", "xhigh", False), ("codex_cli", "xhigh", True),
    ("claude_code_cli", "xhigh", False), ("claude_code_cli", "max", True),
])
def test_pure_request_fingerprint_preserves_original_algorithm(provider, effort, research):
    from videoagents.providers.cli_runner import GLM_CONTEXT_TOKENS

    config = {"provider": provider, "model": "glm-5.3[1m]" if provider == "claude_code_cli" else "UNIT model"}
    if provider == "codex_cli":
        config["codex_reasoning_effort"] = effort
    context = {"assets": [{"asset_id": "unit", "url": "ignored", "sha256": "stable"}],
               "research": {"retrieved_at": "ignored", "text": "stable"}}
    old = {"revision": 3, "provider": provider, "model": config["model"], "instruction": "UNIT",
           "schema": {"type": "object"}, "context": semantic(context)}
    if research:
        old["mode"] = "research"
    if provider == "claude_code_cli":
        old.update(reasoning_effort=effort, context_tokens=GLM_CONTEXT_TOKENS)
    elif effort is not None:
        old["reasoning_effort"] = effort
    assert request_fingerprint(3, config, "UNIT", {"type": "object"}, context,
                               research_mode=research, glm_reasoning_effort=effort) == fingerprint(old)


@pytest.mark.parametrize("model", ["glm-5.4[1m]", "glm-4", "glm-5.3[1m]"])
def test_readonly_model_identity_never_decrypts_credentials_or_normalizes_unsupported_glm(
    tmp_path, monkeypatch, model,
):
    from videoagents.default_config import DEFAULT_SETTINGS

    repo = Repository(tmp_path / "runtime")
    roles = copy.deepcopy(DEFAULT_SETTINGS["role_models"])
    roles["director"].update(enabled=True, provider="claude_code_cli", model=model)
    repo.write_settings({"role_models": json.dumps(roles), "glm_reasoning_effort": '"xhigh"',
                         "zhipu_api_key": "UNIT must not be selected or decrypted"})
    monkeypatch.setattr(SettingsService, "internal", lambda self: pytest.fail("Readonly identity decrypted settings"))
    if model != "glm-5.3[1m]":
        with pytest.raises(Conflict, match="GLM-5.3"):
            _model_identity(repo)
    else:
        assert _model_identity(repo)["ledger"] == {"cli_provider": "claude_code_cli", "model": "glm-5.3[1m]",
                                                   "reasoning_effort": "xhigh", "context_tokens": 1000000}
