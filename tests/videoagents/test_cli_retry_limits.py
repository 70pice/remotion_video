"""Paid retry limits are enforced in the actual child environment."""

import json
import os
import sys

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository

RETRY_ENV = {
    "CLAUDE_CODE_MAX_RETRIES": "0",
    "MAX_STRUCTURED_OUTPUT_RETRIES": "1",
    "CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES": "0",
}
AMBIENT_RETRY_ENV = {**dict.fromkeys(RETRY_ENV, "999"), "CLAUDE_CODE_RETRY_WATCHDOG": "1"}


@pytest.fixture
def retry_cli(tmp_path, monkeypatch):
    for name, value in AMBIENT_RETRY_ENV.items():
        monkeypatch.setenv(name, value)
    path = tmp_path / "fixture.py"
    prefix = [sys.executable, "-u", str(path)]
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: prefix)
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: prefix)

    def write(*, fail=False):
        code = "import json,os,sys\nsys.stdin.buffer.read()\n"
        code += f"limits={{name:os.getenv(name) for name in {list(AMBIENT_RETRY_ENV)!r}}}\n"
        if fail:
            code += "assert limits == " + repr({**RETRY_ENV, "CLAUDE_CODE_RETRY_WATCHDOG": None}) + "\n"
            code += "print(json.dumps({'type':'result','subtype':'error_during_execution','is_error':True}))\nsys.exit(1)\n"
        else:
            code += "wire={'response_json':json.dumps(limits)}\n"
            code += "print(json.dumps({'type':'result','subtype':'success','is_error':False,'structured_output':wire}))\n"
        path.write_text(code, encoding="utf-8")

    write()
    return write


@pytest.mark.parametrize("research", [False, True])
@pytest.mark.parametrize("route", ["glm", "ark"])
def test_claude_child_cannot_inherit_automatic_paid_retries(tmp_path, retry_cli, research, route):
    model = "glm-5.3[1m]" if route == "glm" else "doubao-seed-2-1-pro-260915"
    kwargs = {"zhipu_api_key": "fixture-secret"} if route == "glm" else {"ark_api_key": "fixture-secret"}
    if research:
        kwargs.update(research_directory=tmp_path / "research",
                      research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1})
    result = cli_runner.run_cli("claude_code_cli", model, 5, "fixture", {}, **kwargs)
    assert result.data == {**RETRY_ENV, "CLAUDE_CODE_RETRY_WATCHDOG": None}
    assert {name: os.environ[name] for name in AMBIENT_RETRY_ENV} == AMBIENT_RETRY_ENV


def test_retry_limits_are_auditable_and_completed_result_does_not_resubmit(tmp_path, monkeypatch, retry_cli):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(zhipu_api_key="fixture-secret"))
    model = JsonModel(repo)
    first = model.call("fixture", 1, "director", "fixture", {})
    with repo.connection() as db:
        row = db.execute("SELECT status,body FROM operations").fetchone()
    assert row[0] == "COMPLETED"
    assert json.loads(row[1])["cli_retry_limits"] == {
        "api_error_retries": 0, "structured_output_attempts": 1,
        "nonstreaming_timeout_retries": 0, "retry_watchdog": False,
    }
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("must reuse completed result"))
    assert model.call("fixture", 1, "director", "fixture", {}) == first


def test_bounded_error_stays_unknown_and_cannot_be_resubmitted(tmp_path, monkeypatch, retry_cli):
    retry_cli(fail=True)
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(zhipu_api_key="fixture-secret"))
    model = JsonModel(repo)
    with pytest.raises(CapabilityMissing) as first:
        model.call("fixture", 1, "director", "fixture", {}, "command-a")
    with repo.connection() as db:
        row = db.execute("SELECT status,body FROM operations").fetchone()
    assert row[0] == "UNKNOWN" and json.loads(row[1])["reason"].startswith("cli_nonzero_exit;")
    diagnostic = json.loads(json.loads(row[1])["reason"].partition("; ")[2])
    assert diagnostic["stdout_shape"] == "claude_error_result" and diagnostic["exit_code"] == 1
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("must not replay unknown"))
    with pytest.raises(CapabilityMissing) as second:
        model.call("fixture", 1, "director", "changed", {}, "command-b")
    assert second.value.operation_id == first.value.operation_id


@pytest.mark.parametrize("provider", ["codex_cli", "trae_cli"])
def test_other_providers_and_parent_environment_are_unchanged(tmp_path, monkeypatch, provider):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "source-codex"))
    monkeypatch.setenv("TRAE_HOME", str(tmp_path / "source-trae"))
    for name, value in AMBIENT_RETRY_ENV.items():
        monkeypatch.setenv(name, value)
    environment, _ = cli_runner._cli_environment(provider, False, tmp_path)
    assert {name: environment[name] for name in AMBIENT_RETRY_ENV} == AMBIENT_RETRY_ENV


def test_retry_limit_is_not_a_claim_that_prelaunch_failure_was_submitted(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: None)
    with pytest.raises(CliFailure) as failure:
        cli_runner.run_cli("claude_code_cli", "fixture", 5, "fixture", {})
    assert failure.value.submitted is False
