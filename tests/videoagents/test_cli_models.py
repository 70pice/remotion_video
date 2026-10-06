"""Real subprocess protocol fixtures; never invoke a model or use credentials."""

import json
import os
import sys

import pytest

from videoagents.contracts import MaterialResearch, SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, CliResult, build_arguments, run_cli
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint


def fixture_cli(tmp_path, monkeypatch, code):
    path = tmp_path / "protocol_fixture.py"
    path.write_text("import sys,json,time\n" + code, encoding="utf-8")
    source_home = tmp_path / "codex-source-home"
    source_home.mkdir(exist_ok=True)
    trae_source_home = tmp_path / "trae-source-home"
    (trae_source_home / "cli").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    monkeypatch.setenv("TRAE_HOME", str(trae_source_home))
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda provider: [sys.executable, "-u", str(path)])


@pytest.mark.parametrize("provider", ["codex_cli", "trae_cli", "claude_code_cli"])
def test_structured_subprocess_and_utf8_stdin(tmp_path, monkeypatch, provider):
    code = "value={'response_json':json.dumps({'text':sys.stdin.buffer.read().decode('utf-8')})}\n"
    if provider in {"codex_cli", "trae_cli"}:
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


@pytest.mark.parametrize("notification", [
    {"type": "error", "message": "secret reconnect notification"},
    {"type": "item.completed", "item": {"type": "error", "message": "secret config warning"}},
    {"type": "item.completed", "item": {"type": "todo_list", "items": [{"text": "secret plan", "completed": True}]}},
    {"type": "item.completed", "item": {"type": "model_reroute", "from_model": "display-name",
                                       "to_model": "backend-name", "message": "secret route notice"}},
])
def test_codex_notifications_allow_a_completed_structured_result(tmp_path, monkeypatch, notification):
    code = f"print(json.dumps({notification!r}))\n"
    code += "value={'response_json':json.dumps({'text':'ready'})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    result = run_cli("codex_cli", "", 5, "fixture", {"type": "object"})
    assert result == CliResult({"text": "ready"}, {"output_tokens": 2})
    assert "secret" not in repr(result)


@pytest.mark.parametrize("provider", ["codex_cli", "trae_cli"])
def test_cli_uses_last_agent_message_as_structured_result(tmp_path, monkeypatch, provider):
    code = "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'progress only'}}))\n"
    code += "value={'response_json':json.dumps({'text':'ready'})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    result = run_cli(provider, "", 5, "fixture", {"type": "object"})
    assert result == CliResult({"text": "ready"}, {"output_tokens": 2})


def test_trae_double_wrapped_structured_result_is_unwrapped(tmp_path, monkeypatch):
    business = {"script": {"title": "fixture"}, "response": "revised"}
    code = f"business={business!r}\n"
    code += "value={'response_json':json.dumps({'response_json':json.dumps(business)})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n"
    fixture_cli(tmp_path, monkeypatch, code)

    result = run_cli("trae_cli", "", 5, "fixture", {"type": "object"})

    assert result == CliResult(business, {"output_tokens": 2})


@pytest.mark.parametrize("ending,reason", [
    ("", "incomplete_cli_result"),
    ("sys.exit(3)", "cli_nonzero_exit"),
    ("time.sleep(30)", "cli_timeout"),
    ("print(json.dumps({'type':'turn.failed','error':{'message':'secret final failure'}}))", "cli_reported_error"),
    ("print(json.dumps({'type':'turn.completed'}))", "incomplete_cli_result"),
    ("print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'{}'}}))\n"
     "print(json.dumps({'type':'turn.completed'}))", "missing_structured_output"),
])
def test_codex_notification_does_not_hide_terminal_failure(tmp_path, monkeypatch, ending, reason):
    fixture_cli(tmp_path, monkeypatch, "print(json.dumps({'type':'error','message':'secret notification'}))\n" + ending)
    with pytest.raises(CliFailure) as failure:
        run_cli("codex_cli", "", 0.2 if reason == "cli_timeout" else 5, "fixture", {"type": "object"})
    assert failure.value.reason == reason and failure.value.submitted
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize("kind", ["item.started", "item.updated", "item.completed"])
@pytest.mark.parametrize("tool", ["command_execution", "file_change", "mcp_tool_call", "web_search", "collab_tool_call"])
def test_codex_notifications_keep_external_tool_events_blocked(tmp_path, monkeypatch, kind, tool):
    code = "print(json.dumps({'type':'error','message':'secret notification'}))\n"
    event = {"type": kind, "item": {"type": tool}}
    code += f"print(json.dumps({event!r}))\ntime.sleep(30)"
    fixture_cli(tmp_path, monkeypatch, code)
    with pytest.raises(CliFailure) as failure:
        run_cli("codex_cli", "", 5, "fixture", {"type": "object"})
    assert failure.value.reason == "unexpected_tool_event" and failure.value.submitted
    assert "secret" not in str(failure.value)


@pytest.mark.parametrize("completed,exit_code,reason", [
    (False, 0, "incomplete_cli_result"),
    (True, 3, "cli_nonzero_exit"),
])
def test_codex_valid_output_still_requires_completed_turn_and_zero_exit(tmp_path, monkeypatch, completed, exit_code, reason):
    code = "print(json.dumps({'type':'error','message':'secret notification'}))\n"
    code += "value={'response_json':json.dumps({'text':'ready'})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    if completed:
        code += "print(json.dumps({'type':'turn.completed'}))\n"
    code += f"sys.exit({exit_code})"
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
    trae = build_arguments("trae_cli", ["traecli"], "Doubao-Seed-2.1-Pro", tmp_path, schema)
    assert trae[:4] == ["traecli", "-a", "never", "exec"]
    assert trae[trae.index("--sandbox") + 1] == "read-only"
    assert "--ephemeral" in trae and "--ignore-user-config" in trae and "--ignore-rules" in trae
    assert trae[trae.index("--model") + 1] == "Doubao-Seed-2.1-Pro"
    assert trae[trae.index("--disallowed-tool") + 1] == "*"
    assert all(feature in trae for feature in (
        "shell_snapshot", "tool_search", "multi_agent_v2", "apply_patch_freeform",
    ))
    assert "browser_use_full_cdp_access" not in trae and "in_app_chat" not in trae
    assert any(item.startswith("sqlite_home=") for item in trae)
    assert "check_for_update_on_startup=false" in trae
    research = build_arguments("codex_cli", ["exe"], "", tmp_path, schema, research=True)
    assert research[:4] == ["exe", "-a", "never", "exec"]
    assert research[research.index("--sandbox") + 1] == "workspace-write"
    assert "--ephemeral" not in research
    assert "--ignore-user-config" in research
    assert 'windows.sandbox="unelevated"' in research
    assert "sandbox_workspace_write.network_access=true" in research
    assert 'web_search="live"' in research
    assert "shell_tool" not in research and "skill_search" not in research
    assert "multi_agent" in research and "plugins" in research
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


def test_trae_executable_uses_dedicated_override_and_is_reported(tmp_path, monkeypatch):
    executable = tmp_path / ("traecli.exe" if os.name == "nt" else "traecli")
    executable.write_text("fixture")
    monkeypatch.setenv("VIDEOAGENTS_TRAECLI_EXECUTABLE", str(executable))
    assert cli_runner.executable_prefix("trae_cli") == [str(executable.resolve())]
    assert cli_runner.cli_availability()["trae_cli"] == {"available": True}


def test_codex_research_mode_allows_tool_events_and_writes_sanitized_audit(tmp_path, monkeypatch):
    code = "from pathlib import Path\nPath('research-note.txt').write_text('kept workspace file', encoding='utf-8')\n"
    code += "print(json.dumps({'type':'item.started','item':{'type':'command_execution','status':'running','command':'secret command text'}}))\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'progress only'}}))\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'web_search','status':'completed','query':'secret query'}}))\n"
    code += "value={'response_json':json.dumps({'text':'final research'})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    workspace = tmp_path / "research-workspace"
    audit = tmp_path / "audit" / "events.jsonl"
    result = run_cli("codex_cli", "", 5, "fixture", {"type": "object"},
                     research_directory=workspace, audit_path=audit)
    assert result == CliResult({"text": "final research"}, {"output_tokens": 2})
    assert (workspace / "research-note.txt").read_text(encoding="utf-8") == "kept workspace file"
    audit_text = audit.read_text(encoding="utf-8")
    assert "command_execution" in audit_text and "web_search" in audit_text
    assert "secret" not in audit_text and "output_tokens" not in audit_text


def test_codex_uses_ephemeral_home_and_removes_staged_auth_after_thread_start(tmp_path, monkeypatch):
    source_home = tmp_path / "authenticated-codex-home"
    source_home.mkdir()
    source_auth = source_home / "auth.json"
    source_auth.write_text('{"test_only_token":"must-not-persist"}', encoding="utf-8")
    monkeypatch.setenv("VIDEOAGENTS_TEST_SOURCE_HOME", str(source_home))
    code = (
        "import os\nfrom pathlib import Path\n"
        "home=Path(os.environ['CODEX_HOME'])\n"
        "source=Path(os.environ['VIDEOAGENTS_TEST_SOURCE_HOME'])\n"
        "auth=home/'auth.json'\n"
        "loaded=auth.read_text(encoding='utf-8')\n"
        "print(json.dumps({'type':'thread.started'}), flush=True)\n"
        "for _ in range(100):\n"
        "    if not auth.exists(): break\n"
        "    time.sleep(0.01)\n"
        "value={'response_json':json.dumps({'isolated':home != source,"
        "'sqlite_isolated':Path(os.environ['CODEX_SQLITE_HOME']).is_relative_to(home),"
        "'auth_loaded':'must-not-persist' in loaded,'auth_removed':not auth.exists(),"
        "'home':str(home)})}\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
        "print(json.dumps({'type':'turn.completed'}))\n"
    )
    fixture_cli(tmp_path, monkeypatch, code)
    monkeypatch.setenv("CODEX_HOME", str(source_home))

    result = run_cli("codex_cli", "", 5, "fixture", {"type": "object"})

    assert result.data | {"home": ""} == {
        "isolated": True,
        "sqlite_isolated": True,
        "auth_loaded": True,
        "auth_removed": True,
        "home": "",
    }
    assert source_auth.is_file()
    assert not cli_runner.Path(result.data["home"]).exists()


def test_trae_uses_ephemeral_home_and_cleans_staged_auth_after_exit(tmp_path, monkeypatch):
    source_home = tmp_path / "authenticated-trae-home"
    source_auth = source_home / "cli" / "auth.json"
    source_auth.parent.mkdir(parents=True)
    source_auth.write_text('{"test_only_token":"must-not-persist"}', encoding="utf-8")
    monkeypatch.setenv("VIDEOAGENTS_TEST_SOURCE_HOME", str(source_home))
    code = (
        "import os\nfrom pathlib import Path\n"
        "home=Path(os.environ['TRAE_HOME'])\n"
        "source=Path(os.environ['VIDEOAGENTS_TEST_SOURCE_HOME'])\n"
        "auth=home/'cli'/'auth.json'\n"
        "loaded=auth.read_text(encoding='utf-8')\n"
        "print(json.dumps({'type':'thread.started'}), flush=True)\n"
        "value={'response_json':json.dumps({'isolated':home != source,"
        "'auth_loaded':'must-not-persist' in loaded,'auth_retained':auth.exists(),"
        "'home':str(home)})}\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
        "print(json.dumps({'type':'turn.completed'}))\n"
    )
    fixture_cli(tmp_path, monkeypatch, code)
    monkeypatch.setenv("TRAE_HOME", str(source_home))

    result = run_cli("trae_cli", "", 5, "fixture", {"type": "object"})

    assert result.data | {"home": ""} == {
        "isolated": True,
        "auth_loaded": True,
        "auth_retained": True,
        "home": "",
    }
    assert source_auth.is_file()
    assert not cli_runner.Path(result.data["home"]).exists()


def test_codex_research_accepts_collaboration_events_without_handing_off_tool_details(tmp_path, monkeypatch):
    event = {"type": "item.completed", "item": {"type": "collab_tool_call", "status": "completed",
             "tool": "wait", "prompt": "private tool prompt", "receiver_thread_ids": ["private-thread"]}}
    code = f"print(json.dumps({event!r}))\n"
    code += "value={'response_json':json.dumps({'sources':[], 'limitations':['known gap']})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))"
    fixture_cli(tmp_path, monkeypatch, code)
    audit = tmp_path / "audit.jsonl"
    result = run_cli("codex_cli", "", 5, "fixture", {"type": "object"},
                     research_directory=tmp_path / "research", audit_path=audit)
    assert result.data == {"sources": [], "limitations": ["known gap"]}
    record = json.loads(audit.read_text(encoding="utf-8").splitlines()[0])
    assert record == {"type": "item.completed", "item_type": "collab_tool_call", "status": "completed"}
    assert "private" not in audit.read_text(encoding="utf-8")


@pytest.mark.parametrize("research", [False, True])
def test_codex_requires_last_agent_message_to_be_structured(tmp_path, monkeypatch, research):
    code = "value={'response_json':json.dumps({'text':'not final'})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':'progress after final'}}))\n"
    code += "print(json.dumps({'type':'turn.completed'}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    kwargs = {"research_directory": tmp_path / "research"} if research else {}
    with pytest.raises(CliFailure, match="invalid_cli_output"):
        run_cli("codex_cli", "", 5, "fixture", {"type": "object"}, **kwargs)


@pytest.mark.parametrize("research", [False, True])
def test_cli_roles_do_not_inherit_desktop_session_or_permission_context(tmp_path, monkeypatch, research):
    for name in cli_runner.CODEX_MANAGED_CONTEXT_ENV:
        monkeypatch.setenv(name, "parent-desktop-context")
    monkeypatch.setenv("VIDEOAGENTS_ENV_FIXTURE", "preserved")
    code = "import os\n"
    code += f"managed={sorted(cli_runner.CODEX_MANAGED_CONTEXT_ENV)!r}\n"
    code += "value={'response_json':json.dumps({'inherited':[key for key in managed if key in os.environ], 'other':os.environ.get('VIDEOAGENTS_ENV_FIXTURE')})}\n"
    code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
    code += "print(json.dumps({'type':'turn.completed'}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    kwargs = {"research_directory": tmp_path / "research"} if research else {}
    result = run_cli("codex_cli", "", 5, "fixture", {"type": "object"}, **kwargs)
    assert result.data == {"inherited": [], "other": "preserved"}


def test_research_mode_prepends_user_local_bin_without_changing_plain_mode(tmp_path, monkeypatch):
    local_bin = tmp_path / "home" / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setattr(cli_runner.Path, "home", lambda: tmp_path / "home")
    monkeypatch.setenv("CODEX_PERMISSION_PROFILE", ":danger-full-access")
    fixture_cli(tmp_path, monkeypatch,
                "import os\n"
                "value={'response_json':json.dumps({'path':os.environ.get('PATH',''),"
                "'pythonutf8':os.environ.get('PYTHONUTF8',''),"
                "'pythonioencoding':os.environ.get('PYTHONIOENCODING',''),"
                "'permission_profile':os.environ.get('CODEX_PERMISSION_PROFILE','')})}\n"
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
                "print(json.dumps({'type':'turn.completed'}))\n")
    plain = run_cli("codex_cli", "", 5, "fixture", {"type": "object"}).data
    research = run_cli("codex_cli", "", 5, "fixture", {"type": "object"},
                       research_directory=tmp_path / "research").data
    assert not plain["path"].startswith(str(local_bin) + os.pathsep)
    assert research["path"].startswith(str(local_bin) + os.pathsep)
    assert research["pythonutf8"] == "1"
    assert research["pythonioencoding"] == "utf-8"
    assert plain["permission_profile"] == ""
    assert research["permission_profile"] == ""


def test_role_routes_and_unknown_survives_provider_change(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    configs = {role: {"enabled": True, "model": role + "-model", "provider": "claude_code_cli" if role == "review" else "codex_cli"}
               for role in ("screenwriter", "script_reviewer", "voice", "director", "editing", "review")}
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
    for role in ("script_reviewer", "voice", "director", "editing", "review"):
        assert model.call("fixture-job", 1, role, "test", {}, "command") == {"model": role + "-model"}
    assert calls[-1] == ("claude_code_cli", "review-model", 300)
    with pytest.raises(CapabilityMissing) as first:
        model.call("fixture-job", 1, "screenwriter", "test", {}, "command")
    assert first.value.operation_status == "UNKNOWN"
    settings.patch(SettingsPatch(role_models={"screenwriter": {"provider": "claude_code_cli", "model": "different"}}))
    with pytest.raises(CapabilityMissing) as repeat:
        model.call("fixture-job", 1, "screenwriter", "changed", {}, "new-command")
    assert repeat.value.operation_id == first.value.operation_id and len(calls) == 6


def test_plain_mode_reuses_legacy_completed_operation_hash_without_mode(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {
        "enabled": True, "provider": "codex_cli", "model": "legacy-model",
    }}))
    legacy_hash = fingerprint({"revision": 1, "provider": "codex_cli", "model": "legacy-model",
                               "instruction": "JSON only", "schema": {"type": "object"}, "context": {}})
    operation = repo.start_operation("fixture-job", legacy_hash, "llm:screenwriter", {"revision": 1})
    repo.finish_operation(operation["operation_id"], "COMPLETED", {"result": {"text": "legacy result"}})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *args, **kwargs: pytest.fail("legacy result should replay"))
    assert JsonModel(repo).call("fixture-job", 1, "screenwriter", "JSON only", {}, "command-a") == {"text": "legacy result"}


def test_completed_trae_operation_replays_double_wrapped_business_result(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {
        "enabled": True, "provider": "trae_cli", "model": "unit-model",
    }}))
    schema = {"type": "object"}
    input_hash = fingerprint({"revision": 1, "provider": "trae_cli", "model": "unit-model",
                              "instruction": "JSON only", "schema": schema, "context": {}})
    operation = repo.start_operation("fixture-job", input_hash, "llm:screenwriter", {"revision": 1})
    business = {"script": {"title": "fixture"}, "response": "revised"}
    wrapped = {"response_json": json.dumps(business)}
    repo.finish_operation(operation["operation_id"], "COMPLETED", {"result": wrapped})
    monkeypatch.setattr("videoagents.providers.llm.run_cli",
                        lambda *args, **kwargs: pytest.fail("completed result should replay"))

    result = JsonModel(repo).call(
        "fixture-job", 1, "screenwriter", "JSON only", {}, "command-a", output_schema=schema,
    )

    assert result == business


def test_materials_research_uses_codex_tools_without_persisting_workspace_in_operation(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(
        search_provider="opencli_google",
        research_platforms=["web", "reddit"],
        role_models={"materials": {"enabled": True, "provider": "codex_cli", "model": "unit-research"}},
    ))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *args: ["fixture-cli"])
    calls = []

    def transport(provider, model, timeout, prompt, schema, **kwargs):
        calls.append((provider, model, prompt, kwargs))
        assert schema["title"] == "MaterialResearch" and "plan" not in schema["properties"]
        return CliResult({"sources": [], "visuals": [], "limitations": ["unit gap"]})

    monkeypatch.setattr("videoagents.providers.llm.run_cli", transport)
    state = {
        "job_id": "fixture-job",
        "revision": 1,
        "settings": {
            "research_skills": [{"name": "agent-reach", "path": "C:/unit/agent-reach", "installed": True}],
            "search_provider": "opencli_google",
            "research_platforms": ["web", "reddit"],
            "research_max_searches": 8,
            "research_max_sources": 12,
            "research_download_images": True,
            "search_api_key": "UNIT-secret",
            "voice_api_key": "UNIT-voice-secret",
            "voice_style": "不要给素材看",
        },
    }
    workspace = tmp_path / "workspace-a"
    audit = tmp_path / "audit-a.jsonl"
    result = JsonModel(repo).invoke(state, "materials", "固定素材 Prompt", fields=("settings",),
                                   output_schema=MaterialResearch.model_json_schema(),
                                   command_id="command-a", research_directory=workspace,
                                   audit_path=audit)
    assert result == {"sources": [], "visuals": [], "limitations": ["unit gap"]}
    provider, model, prompt, kwargs = calls[0]
    assert (provider, model) == ("codex_cli", "unit-research")
    assert kwargs["research_directory"] == workspace and kwargs["audit_path"] == audit
    assert "opencli_google" in prompt and "reddit" in prompt and "agent-reach" in prompt
    assert "UNIT-secret" not in prompt and "不要给素材看" not in prompt
    with repo.connection() as db:
        status, body = db.execute("SELECT status,body FROM operations").fetchone()
    assert status == "COMPLETED"
    ledger = json.loads(body)
    assert ledger["mode"] == "research" and ledger["result"]["limitations"] == ["unit gap"]
    assert str(workspace) not in body and str(audit) not in body


def test_research_mode_is_limited_to_materials_codex(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={
        "materials": {"enabled": True, "provider": "claude_code_cli"},
        "screenwriter": {"enabled": True, "provider": "codex_cli"},
    }))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *args, **kwargs: pytest.fail("transport should not launch"))
    model = JsonModel(repo)
    with pytest.raises(CapabilityMissing, match="工具研究模式仅支持素材角色使用 Codex CLI"):
        model.call("fixture-job", 1, "materials", "test", {}, "command", research_directory=tmp_path / "r1")
    with pytest.raises(CapabilityMissing, match="工具研究模式仅支持素材角色使用 Codex CLI"):
        model.call("fixture-job", 1, "screenwriter", "test", {}, "command", research_directory=tmp_path / "r2")
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


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
    from videoagents.nodes.voice import VoiceNode
    from videoagents.services.jobs import JobService
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
    voice = VoiceNode(repo, JobService(repo, tmp_path / "project"))
    with pytest.raises(RenderCancelled):
        voice({"job_id": job.job_id, "revision": 1, "run_id": "fixture-command", "action": "produce"})
    assert repo.get_job(job.job_id).status == "CANCELLED"
    with repo.connection() as db:
        row = db.execute("SELECT status,body FROM operations").fetchone()
    assert row[0] == ("UNKNOWN" if submitted else "REJECTED")
