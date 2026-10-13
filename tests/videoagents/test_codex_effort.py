"""Per-role Codex effort routing and paid-request compatibility; no real models."""

import json
import sys

import pytest
from pydantic import ValidationError

from videoagents.contracts import RoleModelConfig, SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, CliResult, build_arguments, run_cli
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint


@pytest.mark.parametrize("research", [False, True])
@pytest.mark.parametrize("effort", [None, "xhigh", "max"])
def test_codex_arguments_select_effort_without_changing_tool_permissions(tmp_path, research, effort):
    args = build_arguments("codex_cli", ["fixture"], "gpt-6.1-sol", tmp_path, tmp_path / "schema.json",
                           research=research, codex_reasoning_effort=effort)
    configs = [args[index + 1] for index, value in enumerate(args) if value == "-c"]
    selected = [value for value in configs if value.startswith("model_reasoning_effort=")]
    assert selected == ([] if effort is None else [f'model_reasoning_effort="{effort}"'])
    assert args[args.index("--model") + 1] == "gpt-6.1-sol"
    assert args[args.index("--sandbox") + 1] == ("workspace-write" if research else "read-only")
    assert f'web_search="{"live" if research else "disabled"}"' in configs
    assert "--ignore-user-config" in args and "--ignore-rules" in args
    assert args[-1] == "-"


@pytest.mark.parametrize("research", [False, True])
def test_settings_to_real_fixture_process_receives_xhigh_and_records_ledger(tmp_path, monkeypatch, research):
    path = tmp_path / "fixture.py"
    path.write_text(
        "import sys,json\n"
        "args=sys.argv[1:]\n"
        "configs=[args[i+1] for i,v in enumerate(args) if v=='-c']\n"
        "result={'effort':[v for v in configs if v.startswith('model_reasoning_effort=')],"
        "'model':args[args.index('--model')+1],'prompt':sys.stdin.read()}\n"
        "wire={'response_json':json.dumps(result)}\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(wire)}}))\n"
        "print(json.dumps({'type':'turn.completed'}))\n", encoding="utf-8",
    )
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    prefix = [sys.executable, "-u", str(path)]
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: prefix)
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: prefix)
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {
        "provider": "codex_cli", "model": "gpt-6.1-sol", "codex_reasoning_effort": "xhigh",
    }}))
    kwargs = {"research_directory": tmp_path / "research"} if research else {}
    result = JsonModel(repo).call("fixture", 1, "materials", "中文任务", {}, **kwargs)
    assert result["effort"] == ['model_reasoning_effort="xhigh"']
    assert result["model"] == "gpt-6.1-sol" and "中文任务" in result["prompt"]
    with repo.connection() as db:
        status, body = db.execute("SELECT status,body FROM operations").fetchone()
    ledger = json.loads(body)
    assert status == "COMPLETED" and ledger["reasoning_effort"] == "xhigh"
    assert ledger["mode"] == ("research" if research else "structured")
    assert not list(tmp_path.glob(".videoagents-cli-*"))


def test_per_role_settings_roundtrip_preserves_unmodified_roles_and_old_serialization(tmp_path):
    assert "codex_reasoning_effort" not in RoleModelConfig().model_dump()
    assert "codex_reasoning_effort" not in RoleModelConfig(codex_reasoning_effort=None).model_dump()
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    original = settings.internal()["role_models"]
    patch = SettingsPatch.model_validate_json(json.dumps({"role_models": {"materials": {
        "provider": "codex_cli", "model": "gpt-6.1-sol", "codex_reasoning_effort": "xhigh",
    }}}))
    public = settings.patch(patch)["role_models"]
    restored = SettingsService(Repository(repo.root)).internal()["role_models"]
    assert restored == public
    assert restored["materials"]["codex_reasoning_effort"] == "xhigh"
    assert {key: value for key, value in restored.items() if key != "materials"} == {
        key: value for key, value in original.items() if key != "materials"
    }
    settings.patch(SettingsPatch(role_models={"materials": {"timeout_seconds": 600}}))
    assert settings.internal()["role_models"]["materials"]["codex_reasoning_effort"] == "xhigh"
    with pytest.raises(ValidationError):
        SettingsPatch(role_models={"materials": {"codex_reasoning_effort": "extra high"}})
    assert settings.internal()["role_models"]["materials"]["codex_reasoning_effort"] == "xhigh"


def test_invalid_effort_fails_before_process_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: ["must-not-launch"])
    monkeypatch.setattr(cli_runner.subprocess, "Popen", lambda *a, **k: pytest.fail("must not launch"))
    with pytest.raises(CliFailure, match="invalid_codex_reasoning_effort") as error:
        run_cli("codex_cli", "gpt-6.1-sol", 5, "fixture", {}, codex_reasoning_effort="extra high")
    assert error.value.submitted is False


@pytest.mark.parametrize("research", [False, True])
def test_effort_changes_hash_and_replays_only_matching_completed_result(tmp_path, monkeypatch, research):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(role_models={"materials": {
        "provider": "codex_cli", "model": "gpt-6.1-sol", "codex_reasoning_effort": "high",
    }}))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: ["fixture"])
    calls = []
    def invoke(*args, **kwargs):
        calls.append(kwargs["codex_reasoning_effort"])
        return CliResult({"effort": calls[-1]})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", invoke)
    model = JsonModel(repo)
    kwargs = {"research_directory": tmp_path / "research"} if research else {}
    assert model.call("fixture", 1, "materials", "test", {}, **kwargs) == {"effort": "high"}
    settings.patch(SettingsPatch(role_models={"materials": {"codex_reasoning_effort": "xhigh"}}))
    for _ in range(2):
        assert model.call("fixture", 1, "materials", "test", {}, **kwargs) == {"effort": "xhigh"}
    settings.patch(SettingsPatch(role_models={"materials": {"codex_reasoning_effort": "high"}}))
    assert model.call("fixture", 1, "materials", "test", {}, **kwargs) == {"effort": "high"}
    assert calls == ["high", "xhigh"]
    with repo.connection() as db:
        rows = db.execute("SELECT input_hash,body FROM operations").fetchall()
    assert len(rows) == len({row[0] for row in rows}) == 2
    assert {json.loads(row[1])["reasoning_effort"] for row in rows} == {"high", "xhigh"}


@pytest.mark.parametrize("research", [False, True])
def test_unset_effort_reuses_legacy_completed_hash(tmp_path, monkeypatch, research):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {
        "provider": "codex_cli", "model": "legacy-model",
    }}))
    payload = {"revision": 1, "provider": "codex_cli", "model": "legacy-model",
               "instruction": "test", "schema": {"type": "object"}, "context": {}}
    if research:
        payload["mode"] = "research"
    operation = repo.start_operation("fixture", fingerprint(payload), "llm:materials", {"revision": 1})
    repo.finish_operation(operation["operation_id"], "COMPLETED", {"result": {"old": True}})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("must replay"))
    kwargs = {"research_directory": tmp_path / "research"} if research else {}
    assert JsonModel(repo).call("fixture", 1, "materials", "test", {}, **kwargs) == {"old": True}


@pytest.mark.parametrize("provider", ["trae_cli", "claude_code_cli"])
def test_codex_effort_has_no_effect_on_other_providers(tmp_path, monkeypatch, provider):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(role_models={"screenwriter": {
        "provider": provider, "model": "fixture-model", "codex_reasoning_effort": "high",
    }}))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: ["fixture"])
    calls = []
    def invoke(*args, **kwargs):
        calls.append(kwargs)
        return CliResult({"ok": True})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", invoke)
    model = JsonModel(repo)
    assert model.call("fixture", 1, "screenwriter", "test", {}) == {"ok": True}
    settings.patch(SettingsPatch(role_models={"screenwriter": {"codex_reasoning_effort": "xhigh"}}))
    assert model.call("fixture", 1, "screenwriter", "test", {}) == {"ok": True}
    assert len(calls) == 1 and "codex_reasoning_effort" not in calls[0]
    with repo.connection() as db:
        rows = db.execute("SELECT body FROM operations").fetchall()
    assert len(rows) == 1 and "reasoning_effort" not in json.loads(rows[0][0])
    schema = tmp_path / "schema.json"
    schema.write_text('{}')
    args = build_arguments(provider, ["fixture"], "fixture-model", tmp_path, schema,
                           codex_reasoning_effort="xhigh")
    assert not any(value.startswith("model_reasoning_effort=") for value in args)


@pytest.mark.parametrize("status", ["SUBMITTING", "UNKNOWN"])
@pytest.mark.parametrize("old_provider", ["codex_cli", "claude_code_cli"])
def test_effort_and_provider_changes_cannot_bypass_unsettled_materials(tmp_path, monkeypatch, status, old_provider):
    repo = Repository(tmp_path / "runtime")
    ledger = {"revision": 1, "cli_provider": old_provider, "reasoning_effort": "high"}
    operation = repo.start_operation("fixture", "old-request", "llm:materials", ledger)
    if status == "UNKNOWN":
        repo.finish_operation(operation["operation_id"], status, ledger)
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {
        "provider": "codex_cli", "model": "gpt-6.1-sol", "codex_reasoning_effort": "xhigh",
    }}))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("must not resubmit"))
    with pytest.raises(CapabilityMissing) as error:
        JsonModel(repo).call("fixture", 1, "materials", "changed", {}, research_directory=tmp_path / "research")
    assert error.value.operation_status == "UNKNOWN"
    assert error.value.operation_id == operation["operation_id"]
    with repo.connection() as db:
        rows = db.execute("SELECT status,body FROM operations").fetchall()
    assert len(rows) == 1 and rows[0][0] == status
    assert json.loads(rows[0][1]) == ledger
