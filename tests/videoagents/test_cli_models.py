"""Real subprocess protocol fixtures; never invoke a model or use credentials."""

import os
import sys

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, CliResult, build_arguments, run_cli
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


def fixture_cli(tmp_path, monkeypatch, code):
    path = tmp_path / "protocol_fixture.py"
    path.write_text("import sys,json,time\n" + code, encoding="utf-8")
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda provider: [sys.executable, "-u", str(path)])


@pytest.mark.parametrize("provider", ["codex_cli", "claude_code_cli"])
def test_structured_subprocess_and_utf8_stdin(tmp_path, monkeypatch, provider):
    code = "value={'response_json':json.dumps({'text':sys.stdin.buffer.read().decode('utf-8')})}\n"
    if provider == "codex_cli":
        code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\nprint(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n"
    else:
        code += "print(json.dumps({'type':'result','subtype':'success','is_error':False,'structured_output':value,'usage':{'output_tokens':2}}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    result = run_cli(provider, "model ;$(touch secret)", 5, "中文输入", {"type": "object"})
    assert "中文输入" in result.data["text"] and "业务 JSON schema" in result.data["text"]
    assert result.usage == {"output_tokens": 2}


@pytest.mark.parametrize("code,reason", [
    ("print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}))\ntime.sleep(30)", "unexpected_tool_event"),
    ("print('not JSON')", "invalid_cli_output"),
    ("print(json.dumps({'type':'turn.failed','error':{'message':'secret must not propagate'}}))", "cli_reported_error"),
    ("sys.exit(3)", "cli_nonzero_exit"),
    ("print(json.dumps({'type':'thread.started'}))", "incomplete_cli_result"),
])
def test_codex_failures_are_unknown_and_sanitized(tmp_path, monkeypatch, code, reason):
    fixture_cli(tmp_path, monkeypatch, code)
    with pytest.raises(CliFailure) as failure:
        run_cli("codex_cli", "", 5, "fixture", {"type": "object"})
    assert failure.value.reason == reason and failure.value.submitted
    assert "secret" not in str(failure.value)


def test_timeout_and_cancellation_terminate_subprocess(tmp_path, monkeypatch):
    fixture_cli(tmp_path, monkeypatch, "time.sleep(30)")
    with pytest.raises(CliFailure, match="cli_timeout"):
        run_cli("codex_cli", "", 0.1, "fixture", {"type": "object"})
    polls = []
    def cancel_after_launch():
        polls.append(True)
        return len(polls) > 2
    with pytest.raises(CliFailure, match="cli_cancelled") as failure:
        run_cli("claude_code_cli", "", 5, "fixture", {"type": "object"}, cancelled=cancel_after_launch)
    assert failure.value.submitted


def test_prelaunch_cancellation_does_not_start_a_cli(tmp_path, monkeypatch):
    launches = []
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: ["never-invoke-this"])
    monkeypatch.setattr(cli_runner.subprocess, "Popen", lambda *a, **k: launches.append(a))
    for stop_at in (1, 2):
        polls = []
        def cancel():
            polls.append(True)
            return len(polls) >= stop_at
        with pytest.raises(CliFailure, match="cli_cancelled") as failure:
            run_cli("codex_cli", "", 5, "fixture", {"type": "object"}, cancelled=cancel)
        assert not failure.value.submitted
    assert not launches


def test_output_limit_and_invalid_inner_json_fail_closed(tmp_path, monkeypatch):
    fixture_cli(tmp_path, monkeypatch, "print('x'*2000)")
    monkeypatch.setattr(cli_runner, "MAX_OUTPUT_BYTES", 1024)
    with pytest.raises(CliFailure, match="cli_output_limit"):
        run_cli("codex_cli", "", 5, "fixture", {"type": "object"})
    fixture_cli(tmp_path, monkeypatch, "print(json.dumps({'type':'result','subtype':'success','structured_output':{'response_json':'[]'}}))")
    with pytest.raises(CliFailure, match="non_object_output"):
        run_cli("claude_code_cli", "", 5, "fixture", {"type": "object"})


def test_argument_isolation_and_windows_shim_resolution(tmp_path, monkeypatch):
    schema = tmp_path / "schema.json"
    schema.write_text('{"type":"object"}')
    codex = build_arguments("codex_cli", ["exe"], "opaque model", tmp_path, schema)
    assert codex[:4] == ["exe", "-a", "never", "exec"]
    assert "--ignore-user-config" in codex and "--ignore-rules" in codex
    assert codex[codex.index("--model") + 1] == "opaque model"
    assert "shell_tool" in codex and "multi_agent" in codex
    claude = build_arguments("claude_code_cli", ["exe"], "", tmp_path, schema)
    assert claude[claude.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in claude and "--no-session-persistence" in claude
    assert "--bare" not in claude and "--model" not in claude
    if os.name == "nt":
        shim = tmp_path / "codex.cmd"
        shim.write_text("this shell content must never execute")
        entry = tmp_path / "node_modules/@openai/codex/bin/codex.js"
        entry.parent.mkdir(parents=True)
        entry.write_text("// fixture")
        monkeypatch.setenv("VIDEOAGENTS_CODEX_EXECUTABLE", str(shim))
        monkeypatch.setattr(cli_runner.shutil, "which", lambda name: "node.exe")
        assert cli_runner.executable_prefix("codex_cli") == ["node.exe", str(entry)]
        entry.unlink()
        assert cli_runner.executable_prefix("codex_cli") is None


def test_role_routes_and_unknown_survives_provider_change(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    configs = {role: {"enabled": True, "model": role + "-model", "provider": "claude_code_cli" if role == "review" else "codex_cli"}
               for role in ("screenwriter", "voice", "director", "editing", "review")}
    settings.patch(SettingsPatch(role_models=configs))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *args: ["fixture-cli"])
    calls = []
    def transport(provider, model, timeout, prompt, schema, **kwargs):
        calls.append((provider, model, timeout))
        if model == "screenwriter-model":
            raise CliFailure("cli_timeout")
        return CliResult({"model": model})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", transport)
    model = JsonModel(repo)
    for role in ("voice", "director", "editing", "review"):
        assert model.call("fixture-job", 1, role, "test", {}, "command") == {"model": role + "-model"}
    assert calls[-1] == ("claude_code_cli", "review-model", 300)
    with pytest.raises(CapabilityMissing) as first:
        model.call("fixture-job", 1, "screenwriter", "test", {}, "command")
    assert first.value.operation_status == "UNKNOWN"
    settings.patch(SettingsPatch(role_models={"screenwriter": {"provider": "claude_code_cli", "model": "different"}}))
    with pytest.raises(CapabilityMissing) as repeat:
        model.call("fixture-job", 1, "screenwriter", "changed", {}, "new-command")
    assert repeat.value.operation_id == first.value.operation_id and len(calls) == 5


def test_missing_cli_does_not_reserve_paid_submission(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"voice": {"enabled": True}}))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *args: None)
    with pytest.raises(CapabilityMissing, match="未找到"):
        JsonModel(repo).call("fixture-job", 1, "voice", "test", {})
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM run_metrics").fetchone()[0] == 0


@pytest.mark.parametrize("submitted", [False, True])
def test_cancelled_role_preserves_job_cancellation_and_submission_receipt(tmp_path, monkeypatch, submitted):
    from videoagents.contracts import Brief, Script, ScriptSegment
    from videoagents.graph import VideoProductionGraph
    from worker.process_manager import RenderCancelled

    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="这是我的主观看法。"))
    repo.update_job(job.job_id, script=Script(title="fixture", origin="user", revision=1,
        segments=[ScriptSegment(segment_id="s1", narration="这是我的主观看法。")]))
    SettingsService(repo).patch(SettingsPatch(role_models={"voice": {"enabled": True}}))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *args: ["fixture-cli"])
    def cancel(*args, **kwargs):
        repo.cancel(job.job_id)
        raise CliFailure("cli_cancelled", submitted=submitted)
    monkeypatch.setattr("videoagents.providers.llm.run_cli", cancel)
    with VideoProductionGraph(repo, tmp_path / "project") as graph:
        with pytest.raises(RenderCancelled):
            graph.node_voice({"job_id": job.job_id, "revision": 1, "run_id": "fixture-command", "action": "produce"})
    assert repo.get_job(job.job_id).status == "CANCELLED"
    with repo.connection() as db:
        row = db.execute("SELECT status,body FROM operations").fetchone()
    assert row[0] == ("UNKNOWN" if submitted else "REJECTED")
