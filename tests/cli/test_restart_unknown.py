import json
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from videoagents.contracts import Brief, Script, ScriptSegment, models
from videoagents.main import build_parser, main
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.jobs import JobService
from videoagents.storage import Conflict, Repository
from videoagents.storage.repository import fingerprint


def paused_job(tmp_path, *, operation_status="UNKNOWN", provider="llm:screenwriter", revision=1):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT authorized model restart"))
    ledger = {"revision": revision, "command_id": "unit-old-command", "reason": "cli_output_limit"}
    operation = repo.start_operation(job.job_id, "unit-model-input", provider, ledger)
    repo.finish_operation(operation["operation_id"], operation_status, ledger)
    pending = {"kind": "input", "stage": "script", "revision": 1,
               "fields": ["llm_operation"], "pending_token": "unit-pending",
               "thread_id": f"job:{job.job_id}:run:unit-old-command",
               "operation_status": "UNKNOWN", "operation_id": operation["operation_id"]}
    job = repo.update_job(job.job_id, status="NEEDS_INPUT", stage="script", pending_input=pending)
    return repo, job, operation


def request(operation, **changes):
    return models.RestartUnknownRequest.model_validate({
        "base_revision": 1, "operation_id": operation["operation_id"],
        "acknowledge_possible_usage": True, "note": "用户明确允许再次提交，接受可能已经计费",
        **changes,
    })


@pytest.mark.parametrize("changes", [
    {"acknowledge_possible_usage": False}, {"acknowledge_possible_usage": 1},
    {"acknowledge_possible_usage": "true"}, {"note": ""}, {"note": " \n\t"},
    {"operation_id": "not-an-operation"},
])
def test_restart_requires_explicit_acknowledgement_and_nonblank_note(changes):
    with pytest.raises(ValidationError):
        request({"operation_id": "a" * 32}, **changes)


def test_rebuild_script_is_an_explicit_boolean_with_a_backward_compatible_default():
    operation = {"operation_id": "a" * 32}
    assert request(operation).rebuild_script is False
    for invalid in (1, "true"):
        with pytest.raises(ValidationError):
            request(operation, rebuild_script=invalid)


def test_restart_without_acknowledgement_is_not_a_valid_request():
    with pytest.raises(ValidationError):
        models.RestartUnknownRequest.model_validate({
            "base_revision": 1, "operation_id": "a" * 32, "note": "allow",
        })


def test_restart_preserves_unknown_and_snapshots_and_does_not_enqueue(tmp_path):
    repo, job, operation = paused_job(tmp_path)
    audit = JobService(repo).write_json(job, "tool-audit.json", {"tool": "UNIT source"}, "writer_tool_audit")
    job = repo.get_job(job.job_id)
    audit_path, _, _ = repo.artifact_path(audit.artifact_id)
    old_events = repo.events_after(job.job_id, 0)
    new_brief = job.brief.model_copy(update={"creative_direction": "GLM-5.3 xhigh"})
    updated = JobService(repo).restart_unknown(job.job_id, request(operation, brief=new_brief))
    assert (updated.job_id, updated.revision, updated.status, updated.stage) == (job.job_id, 2, "DRAFT", "idle")
    assert updated.pending_input is None and updated.review is None
    assert updated.brief == new_brief
    assert repo.operation(job.job_id, "unit-model-input", "llm:screenwriter") == {
        "operation_id": operation["operation_id"], "status": "UNKNOWN", "revision": 1,
        "command_id": "unit-old-command", "reason": "cli_output_limit",
    }
    events = repo.events_after(job.job_id, 0)
    assert events[:len(old_events)] == old_events
    event = events[-1]["payload"]
    assert event["type"] == "unknown_restart_authorized"
    assert event["operation_id"] == operation["operation_id"]
    assert event["acknowledge_possible_usage"] is True
    assert event["source_revision"] == 1 and event["revision"] == 2
    assert event["note"] == request(operation).note
    assert {"artifact_id": audit.artifact_id, "path": str(audit_path)} in event["previous_artifacts"]
    assert repo.artifact_path(audit.artifact_id)[0] == audit_path
    assert audit in updated.artifacts
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0
        receipt = json.loads(db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key=?", (
            job.job_id, "authorized_model_restart:" + operation["operation_id"],
        )).fetchone()[0])
    assert receipt["previous_pending_input"] == job.pending_input
    assert receipt["previous_brief"] == job.brief.model_dump()
    assert receipt["brief"] == new_brief.model_dump()
    # Existing authorizations were fingerprinted before rebuild_script existed.
    legacy_payload = request(operation, brief=new_brief).model_dump(exclude={"base_revision", "rebuild_script"})
    assert receipt["request_hash"] == fingerprint(legacy_payload)


def test_restart_without_brief_runs_a_fresh_writer_and_keeps_old_script_file(tmp_path, monkeypatch, capsys):
    repo, job, operation = paused_job(tmp_path)
    script = Script(title="UNIT partial", origin="model", revision=1,
                    segments=[ScriptSegment(segment_id="s1", narration="UNIT incomplete")])
    repo.update_job(job.job_id, script=script)
    artifact = JobService(repo).write_json(repo.get_job(job.job_id), "partial-script.json", script.model_dump(), "script")
    updated = JobService(repo).restart_unknown(job.job_id, request(operation))
    assert updated.script is None
    assert not any(item.kind == "script" for item in updated.artifacts)
    assert repo.artifact_path(artifact.artifact_id)[0].is_file()
    with repo.connection() as db:
        receipt = json.loads(db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key=?", (
            job.job_id, "authorized_model_restart:" + operation["operation_id"],
        )).fetchone()[0])
    assert receipt["previous_script"] == script.model_dump()
    calls = []
    def write(self, current, context):
        calls.append(current.revision)
        assert current.script is None and context["script"] is None
        raise CapabilityMissing("UNIT fresh writer stopped without supplier call")
    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.write", write)
    monkeypatch.setattr("sys.argv", ["videoagents", "--runtime-dir", str(repo.root), "run", job.job_id])
    assert main() == 0
    assert calls == [2]
    assert json.loads(capsys.readouterr().out)["status"] == "NEEDS_INPUT"
    assert repo.artifact_path(artifact.artifact_id)[0].is_file()


@pytest.mark.parametrize("invalid", [
    "base_revision", "pending_revision", "pending_operation", "pending_status", "pending_kind",
    "pending_stage", "human_gate", "running", "cancelled", "missing_pending", "operation_revision",
    "operation_missing_revision", "operation_role", "operation_owner", "operation_missing",
    "submitting", "completed", "pending_command", "claimed_command", "another_submitting", "another_unknown",
    "stage_materials", "stage_voice", "stage_director", "stage_render",
])
def test_restart_rejects_unbound_or_active_state_without_mutation(tmp_path, invalid):
    repo, job, operation = paused_job(tmp_path)
    changes = {}
    pending = dict(job.pending_input)
    ledger = {"revision": 1, "command_id": "unit-old-command"}
    if invalid == "base_revision":
        changes["base_revision"] = 2
    elif invalid.startswith("pending_") and invalid not in {"pending_command"}:
        key, value = {"pending_revision": ("revision", 2), "pending_operation": ("operation_id", "b" * 32),
                      "pending_status": ("operation_status", "REJECTED"), "pending_kind": ("kind", "stage_review"),
                      "pending_stage": ("stage", "voice")}[invalid]
        pending[key] = value
        repo.update_job(job.job_id, pending_input=pending)
    elif invalid in {"human_gate", "running", "cancelled"}:
        repo.update_job(job.job_id, status={"human_gate": "NEEDS_HUMAN", "running": "RUNNING",
                                           "cancelled": "CANCELLED"}[invalid])
    elif invalid == "missing_pending":
        repo.update_job(job.job_id, pending_input=None)
    elif invalid in {"operation_revision", "operation_missing_revision", "submitting", "completed"}:
        if invalid == "operation_revision":
            ledger["revision"] = 2
        elif invalid == "operation_missing_revision":
            ledger.pop("revision")
        repo.finish_operation(operation["operation_id"], {
            "submitting": "SUBMITTING", "completed": "COMPLETED",
        }.get(invalid, "UNKNOWN"), ledger)
    elif invalid in {"operation_role", "operation_owner", "operation_missing"}:
        other = repo.create_job(Brief(topic="UNIT other job")) if invalid == "operation_owner" else job
        if invalid == "operation_missing":
            changes["operation_id"] = "b" * 32
        else:
            second = repo.start_operation(other.job_id, "unit-other-input", "llm:voice", ledger)
            repo.finish_operation(second["operation_id"], "UNKNOWN", ledger)
            changes["operation_id"] = second["operation_id"]
            pending["operation_id"] = second["operation_id"]
            repo.update_job(job.job_id, pending_input=pending)
    elif invalid in {"pending_command", "claimed_command"}:
        repo.enqueue(job.job_id, {"action": "resume", "base_revision": 1,
                                  "pending_token": pending["pending_token"], "decision": "confirm",
                                  "note": "UNIT", "idempotency_key": "unit-active-command"})
        if invalid == "claimed_command":
            repo.claim(2147483647)
        repo.update_job(job.job_id, status="NEEDS_INPUT", pending_input=pending)
    elif invalid in {"another_submitting", "another_unknown"}:
        second = repo.start_operation(job.job_id, "unit-other-input", "llm:voice", ledger)
        if invalid == "another_unknown":
            repo.finish_operation(second["operation_id"], "UNKNOWN", ledger)
    elif invalid.startswith("stage_"):
        stage = invalid.removeprefix("stage_")
        pending["stage"] = stage
        repo.update_job(job.job_id, stage=stage, pending_input=pending)
        with repo.connection() as db:
            db.execute("UPDATE operations SET provider=? WHERE operation_id=?", (
                "llm:" + {"render": "editing"}.get(stage, stage), operation["operation_id"],
            ))
    before = repo.get_job(job.job_id).model_dump()
    events_before = repo.events_after(job.job_id, 0)
    with pytest.raises(Conflict):
        JobService(repo).restart_unknown(job.job_id, request(operation, **changes))
    assert repo.get_job(job.job_id).model_dump() == before
    assert repo.events_after(job.job_id, 0) == events_before
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM job_inputs WHERE key LIKE 'authorized_model_restart:%'").fetchone()[0] == 0


def test_restart_replay_and_concurrent_duplicate_create_one_revision(tmp_path):
    repo, job, operation = paused_job(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: JobService(repo).restart_unknown(job.job_id, request(operation)), range(2)))
    assert [result.revision for result in results] == [2, 2]
    count = len(repo.events_after(job.job_id, 0))
    assert JobService(repo).restart_unknown(job.job_id, request(operation, base_revision=2)).revision == 2
    assert len(repo.events_after(job.job_id, 0)) == count
    for changes in ({"note": "different authorization"}, {"brief": Brief(topic="different brief")}):
        with pytest.raises(Conflict):
            JobService(repo).restart_unknown(job.job_id, request(operation, **changes))
    assert repo.get_job(job.job_id).revision == 2


def test_restart_rolls_back_authorization_when_edit_fails(tmp_path, monkeypatch):
    repo, job, operation = paused_job(tmp_path)
    service = JobService(repo)
    def fail(*args):
        raise ValueError("UNIT draft validation failure")
    monkeypatch.setattr(service, "_edit_draft", fail)
    with pytest.raises(ValueError, match="UNIT"):
        service.restart_unknown(job.job_id, request(operation))
    assert repo.get_job(job.job_id).revision == 1
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM job_inputs").fetchone()[0] == 0


def test_cli_restart_requires_ack_and_never_starts_worker(tmp_path, monkeypatch, capsys):
    repo, job, operation = paused_job(tmp_path)
    argv = ["--runtime-dir", str(repo.root), "restart-unknown", job.job_id,
            "--operation-id", operation["operation_id"], "--note", "明确允许再提交，接受可能消耗额度"]
    with pytest.raises(SystemExit) as missing:
        build_parser().parse_args(argv)
    assert missing.value.code == 2
    capsys.readouterr()
    new_brief = job.brief.model_copy(update={"creative_direction": "xhigh"})
    brief_file = tmp_path / "brief.json"
    brief_file.write_text(new_brief.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("videoagents.main._worker", lambda *args: pytest.fail("restart must not start production"))
    monkeypatch.setattr("sys.argv", ["videoagents", *argv, "--acknowledge-possible-usage", "--brief", str(brief_file)])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["revision"] == 2 and result["status"] == "DRAFT"
    assert repo.get_job(job.job_id).brief == new_brief
    assert main() == 0
    assert repo.get_job(job.job_id).revision == 2


def test_cli_restart_reports_invalid_note_without_changing_job(tmp_path, monkeypatch, capsys):
    repo, job, operation = paused_job(tmp_path)
    monkeypatch.setattr("sys.argv", ["videoagents", "--runtime-dir", str(repo.root),
        "restart-unknown", job.job_id, "--operation-id", operation["operation_id"],
        "--acknowledge-possible-usage", "--note", "   "])
    assert main() == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert repo.get_job(job.job_id).revision == 1


def test_cli_restart_reports_empty_brief_and_rolls_back(tmp_path, monkeypatch, capsys):
    repo, job, operation = paused_job(tmp_path)
    brief_file = tmp_path / "brief.json"
    brief_file.write_text(Brief(topic="").model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["videoagents", "--runtime-dir", str(repo.root),
        "restart-unknown", job.job_id, "--operation-id", operation["operation_id"],
        "--acknowledge-possible-usage", "--note", "明确授权", "--brief", str(brief_file)])
    assert main() == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert repo.get_job(job.job_id).revision == 1
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM job_inputs").fetchone()[0] == 0


def paused_materials_job(tmp_path):
    repo, job, operation = paused_job(tmp_path, provider="llm:materials")
    script = Script(title="UNIT completed old script", origin="model", revision=1,
                    segments=[ScriptSegment(segment_id="s1", narration="UNIT old completed narration")])
    job = repo.update_job(job.job_id, stage="materials", script=script,
                          pending_input={**job.pending_input, "stage": "materials"})
    service = JobService(repo)
    script_artifact = service.write_json(job, "old-script.json", script.model_dump(), "script")
    audit = service.write_json(job, "material-audit.json", {"tool": "UNIT source"}, "material_tool_audit")
    research = service.write_json(job, "old-research.json", {"status": "COMPLETED"}, "research")
    ledger = {"revision": 1, "command_id": "unit-old-command", "reason": "unexpected_cli_event"}
    repo.finish_operation(operation["operation_id"], "UNKNOWN", ledger)
    completed_writer = repo.start_operation(job.job_id, "unit-completed-writer", "llm:screenwriter", {"revision": 1})
    repo.finish_operation(completed_writer["operation_id"], "COMPLETED", {"revision": 1, "result": script.model_dump()})
    return repo, repo.get_job(job.job_id), operation, (script_artifact, audit, research)


def test_materials_unknown_without_rebuild_script_keeps_the_completed_script_and_pending(tmp_path):
    repo, job, operation, _ = paused_materials_job(tmp_path)
    before_events = repo.events_after(job.job_id, 0)
    with pytest.raises(Conflict):
        JobService(repo).restart_unknown(job.job_id, request(operation))
    assert repo.get_job(job.job_id) == job
    assert repo.events_after(job.job_id, 0) == before_events


def test_materials_rebuild_at_revision_two_keeps_prior_revision_unknown(tmp_path):
    repo, job, operation, _ = paused_materials_job(tmp_path)
    repo.update_job(job.job_id, revision=2, script=job.script.model_copy(update={"revision": 2}),
                    pending_input={**job.pending_input, "revision": 2})
    repo.finish_operation(operation["operation_id"], "UNKNOWN", {"revision": 2, "reason": "unexpected_cli_event"})
    earlier = repo.start_operation(job.job_id, "unit-prior-unknown", "llm:screenwriter", {"revision": 1})
    repo.finish_operation(earlier["operation_id"], "UNKNOWN", {"revision": 1, "reason": "cli_output_limit"})
    updated = JobService(repo).restart_unknown(job.job_id, request(operation, base_revision=2, rebuild_script=True))
    assert updated.revision == 3 and updated.script is None
    assert repo.operation(job.job_id, "unit-prior-unknown", "llm:screenwriter")["status"] == "UNKNOWN"
    assert repo.operation(job.job_id, "unit-model-input", "llm:materials")["status"] == "UNKNOWN"


def test_materials_rebuild_script_preserves_old_results_audit_and_unknown_and_rewrites_normally(tmp_path, monkeypatch, capsys):
    repo, job, operation, artifacts = paused_materials_job(tmp_path)
    old_operation = repo.operation(job.job_id, "unit-model-input", "llm:materials")
    old_writer = repo.operation(job.job_id, "unit-completed-writer", "llm:screenwriter")
    old_paths = {artifact.artifact_id: repo.artifact_path(artifact.artifact_id)[0] for artifact in artifacts}
    service = JobService(repo)
    updated = service.restart_unknown(job.job_id, request(operation, rebuild_script=True))
    assert (updated.revision, updated.status, updated.stage) == (2, "DRAFT", "idle")
    assert updated.script is None and updated.pending_input is None and updated.review is None
    assert not any(artifact.kind in {"script", "research", "source"} for artifact in updated.artifacts)
    assert repo.operation(job.job_id, "unit-model-input", "llm:materials") == old_operation
    assert repo.operation(job.job_id, "unit-completed-writer", "llm:screenwriter") == old_writer
    event = repo.events_after(job.job_id, 0)[-1]["payload"]
    assert event["rebuild_script"] is True
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0
        receipt = json.loads(db.execute("SELECT value FROM job_inputs WHERE job_id=? AND key=?", (
            job.job_id, "authorized_model_restart:" + operation["operation_id"],
        )).fetchone()[0])
    assert receipt["rebuild_script"] is True and receipt["previous_script"] == job.script.model_dump()
    for artifact_id, path in old_paths.items():
        assert repo.artifact_path(artifact_id)[0] == path and path.is_file()
        assert {"artifact_id": artifact_id, "path": str(path)} in receipt["previous_artifacts"]
    assert service.restart_unknown(job.job_id, request(operation, rebuild_script=True, base_revision=2)).revision == 2
    with pytest.raises(Conflict):
        service.restart_unknown(job.job_id, request(operation, rebuild_script=False))
    calls = []
    def write(self, current, context):
        calls.append("script")
        assert current.script is None
        return Script(title="UNIT fresh writer", origin="model", revision=current.revision,
                      segments=[ScriptSegment(segment_id="s1", narration="UNIT revised narration")])
    def collect(self, current, state):
        calls.append("materials")
        assert current.revision == 2 and current.script.title == "UNIT fresh writer"
        assert self.saved_json(current, "research") is None
        raise CapabilityMissing("UNIT fresh materials stopped without supplier call")
    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.write", write)
    monkeypatch.setattr("videoagents.nodes.materials.MaterialsNode.collect", collect)
    monkeypatch.setattr("sys.argv", ["videoagents", "--runtime-dir", str(repo.root), "run", job.job_id])
    assert main() == 0
    assert calls == ["script", "materials"]
    assert json.loads(capsys.readouterr().out)["status"] == "NEEDS_INPUT"


@pytest.mark.parametrize("invalid", ["human_gate", "wrong_role", "submitting", "active_command", "voice", "director", "render"])
def test_rebuild_script_flag_does_not_bypass_existing_guards(tmp_path, invalid):
    repo, job, operation, _ = paused_materials_job(tmp_path)
    if invalid == "human_gate":
        repo.update_job(job.job_id, status="NEEDS_HUMAN",
                        pending_input={**job.pending_input, "kind": "stage_review"})
    elif invalid == "submitting":
        repo.finish_operation(operation["operation_id"], "SUBMITTING", {"revision": 1})
    elif invalid == "active_command":
        repo.enqueue(job.job_id, {"action": "resume", "base_revision": 1,
            "pending_token": job.pending_input["pending_token"], "decision": "confirm",
            "note": "UNIT", "idempotency_key": "unit-active-materials"})
        repo.update_job(job.job_id, status="NEEDS_INPUT", stage="materials", pending_input=job.pending_input)
    else:
        stage = "materials" if invalid == "wrong_role" else invalid
        repo.update_job(job.job_id, stage=stage, pending_input={**job.pending_input, "stage": stage})
        with repo.connection() as db:
            provider = "llm:screenwriter" if invalid == "wrong_role" else "llm:" + {"render": "editing"}.get(stage, stage)
            db.execute("UPDATE operations SET provider=? WHERE operation_id=?", (provider, operation["operation_id"]))
    before = repo.get_job(job.job_id)
    with pytest.raises(Conflict):
        JobService(repo).restart_unknown(job.job_id, request(operation, rebuild_script=True))
    assert repo.get_job(job.job_id) == before


def test_cli_materials_rebuild_requires_flag_and_does_not_start_paid_work(tmp_path, monkeypatch, capsys):
    repo, job, operation, _ = paused_materials_job(tmp_path)
    argv = ["videoagents", "--runtime-dir", str(repo.root), "restart-unknown", job.job_id,
            "--operation-id", operation["operation_id"], "--acknowledge-possible-usage", "--note",
            "用户新授权接受可能消耗额度并重做文案和素材"]
    monkeypatch.setattr("sys.argv", argv)
    assert main() == 2
    assert "error" in json.loads(capsys.readouterr().out)
    assert repo.get_job(job.job_id).revision == 1
    monkeypatch.setattr("videoagents.main._worker", lambda *args: pytest.fail("authorization must not start production"))
    monkeypatch.setattr("sys.argv", [*argv, "--rebuild-script"])
    assert main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "DRAFT" and result["revision"] == 2
    assert repo.get_job(job.job_id).script is None
