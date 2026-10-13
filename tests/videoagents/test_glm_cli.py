"""GLM transport policy and tool-mode safety using real local subprocesses."""

import json
import os
import sys

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import GLM_MODEL, CliFailure, CliResult, build_arguments, run_cli
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


def fixture_cli(tmp_path, monkeypatch, code):
    path = tmp_path / "fixture.py"
    path.write_text("import os,json,sys\n" + code, encoding="utf-8")
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda provider: [sys.executable, "-u", str(path)])


def test_glm_credentials_and_max_1m_are_child_only(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ambient-other-key")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "ambient-oauth")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://unwanted.invalid")
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_1M_CONTEXT", "1")
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "low")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    code = "wanted=['ANTHROPIC_BASE_URL','CLAUDE_CODE_EFFORT_LEVEL','CLAUDE_CODE_AUTO_COMPACT_WINDOW','CLAUDE_CODE_MAX_CONTEXT_TOKENS']\n"
    code += "v={k:os.getenv(k) for k in wanted}\nv['authenticated']=os.getenv('ANTHROPIC_AUTH_TOKEN')=='fake-zhipu-secret'\n"
    code += "v['conflicts']=any(os.getenv(k) for k in ['ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN','CLAUDE_CODE_DISABLE_1M_CONTEXT','CLAUDE_CODE_USE_BEDROCK'])\n"
    code += "v['models']=[os.getenv('ANTHROPIC_DEFAULT_'+f+'_MODEL') for f in ['OPUS','SONNET','HAIKU','FABLE']]\n"
    code += "v['capabilities']=os.getenv('ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES')\n"
    code += "v['args']=sys.argv[1:]\nprint(json.dumps({'type':'result','subtype':'success','structured_output':{'response_json':json.dumps(v)}}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    data = run_cli("claude_code_cli", GLM_MODEL, 5, "fixture", {"type": "object"}, zhipu_api_key="fake-zhipu-secret").data
    assert data["authenticated"] and not data["conflicts"]
    assert data["ANTHROPIC_BASE_URL"] == "https://open.bigmodel.cn/api/anthropic"
    assert data["CLAUDE_CODE_EFFORT_LEVEL"] == "max"
    assert data["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] == data["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] == "1000000"
    assert data["models"] == [GLM_MODEL] * 4
    assert {"max_effort", "thinking", "adaptive_thinking"} <= set(data["capabilities"].split(","))
    assert data["args"][data["args"].index("--effort") + 1] == "max"
    assert "fake-zhipu-secret" not in repr(data)
    assert os.environ["CLAUDE_CODE_EFFORT_LEVEL"] == "low"
    assert os.environ["ANTHROPIC_API_KEY"] == "ambient-other-key"


def test_glm_missing_key_and_wrong_model_fail_before_reserving(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("not authorized to submit"))
    with pytest.raises(CapabilityMissing) as missing:
        JsonModel(repo).call("fixture", 1, "screenwriter", "test", {})
    assert missing.value.fields == ["zhipu_api_key"]
    SettingsService(repo).patch(SettingsPatch(zhipu_api_key="fake", role_models={"screenwriter": {"model": "glm-4.7"}}))
    with pytest.raises(CapabilityMissing, match="GLM-5.3"):
        JsonModel(repo).call("fixture", 1, "screenwriter", "test", {})
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


def test_all_roles_receive_glm_max_1m_and_materials_context(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    settings = SettingsService(repo)
    settings.patch(SettingsPatch(zhipu_api_key="fake-private-key"))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *a: ["fixture"])
    calls = []
    def invoke(provider, model, timeout, prompt, schema, **kwargs):
        calls.append((provider, model, prompt, kwargs))
        return CliResult({"ok": True})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", invoke)
    for role in settings.internal()["role_models"]:
        kwargs = {"research_directory": tmp_path / "research"} if role == "materials" else {}
        assert JsonModel(repo).call("fixture", 1, role, "test", {}, **kwargs) == {"ok": True}
    assert len(calls) == 7
    for provider, model, prompt, kwargs in calls:
        assert (provider, model) == ("claude_code_cli", GLM_MODEL)
        assert kwargs["zhipu_api_key"] == "fake-private-key"
        assert "fake-private-key" not in prompt
    assert calls[0][3]["research_context"] == {"runtime": str(repo.root), "job_id": "fixture", "revision": 1}
    with repo.connection() as db:
        rows = db.execute("SELECT body FROM operations").fetchall()
    for row in rows:
        assert "fake-private-key" not in row[0]
        ledger = json.loads(row[0])
        assert ledger["reasoning_effort"] == "max" and ledger["context_tokens"] == 1_000_000


def test_claude_research_stream_projects_tool_audit_and_final_result(tmp_path, monkeypatch):
    events = [
        {"type": "system", "subtype": "init", "secret": "must disappear"},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "mcp__videoagents_research__source", "input": {"secret": "must disappear"}}]}},
        {"type": "user", "message": {"content": [{"type": "tool_result", "content": "private raw text"}]}},
        {"type": "result", "subtype": "success", "structured_output": {"response_json": '{"ok":true}'}, "usage": {"output_tokens": 2}},
    ]
    fixture_cli(tmp_path, monkeypatch, "events=" + repr(events) + "\nfor e in events:print(json.dumps(e))\n")
    audit = tmp_path / "audit.jsonl"
    workspace = tmp_path / "research"
    result = run_cli("claude_code_cli", "fixture-model", 5, "fixture", {"type": "object"},
                     research_directory=workspace, audit_path=audit,
                     research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1})
    assert result == CliResult({"ok": True}, {"output_tokens": 2})
    rows = [json.loads(line) for line in audit.read_text().splitlines()]
    assert [row["type"] for row in rows] == ["item.started", "item.completed", "turn.completed"]
    assert "must disappear" not in audit.read_text() and "private raw text" not in audit.read_text()
    assert not list(tmp_path.glob(".videoagents-cli-*"))


@pytest.mark.parametrize("provider", ["codex_cli", "claude_code_cli"])
def test_research_prompt_matches_provider_tool_permissions(tmp_path, monkeypatch, provider):
    code = "prompt=sys.stdin.buffer.read().decode('utf-8')\nvalue={'response_json':json.dumps({'ok':True})}\n"
    if provider == "claude_code_cli":
        code += "assert 'videoagents_research MCP' in prompt\nassert 'web_search' not in prompt\nassert 'shell 命令' not in prompt\n"
        code += "print(json.dumps({'type':'result','subtype':'success','structured_output':value}))\n"
    else:
        code += "assert 'web_search' in prompt and 'shell 命令' in prompt\n"
        code += "print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(value)}}))\n"
        code += "print(json.dumps({'type':'turn.completed'}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    result = run_cli(provider, "fixture-model", 5, "fixture", {}, research_directory=tmp_path / "research",
                     research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1})
    assert result.data == {"ok": True}


@pytest.mark.parametrize("tool", ["Bash", "Read", "Write", "mcp__unapproved__fetch"])
def test_claude_research_rejects_unapproved_tool_events(tmp_path, monkeypatch, tool):
    fixture_cli(tmp_path, monkeypatch, "print(json.dumps({'type':'assistant','message':{'content':[{'type':'tool_use','name':" + repr(tool) + "}]}}))")
    with pytest.raises(CliFailure, match="unexpected_tool_event"):
        run_cli("claude_code_cli", "", 5, "fixture", {}, research_directory=tmp_path / "research",
                research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1})


def test_research_arguments_only_allow_bounded_bridge(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text('{}')
    with pytest.raises(CliFailure, match="missing_research_tool_config"):
        build_arguments("claude_code_cli", ["exe"], GLM_MODEL, tmp_path, schema, research=True)
    args = build_arguments("claude_code_cli", ["exe"], GLM_MODEL, tmp_path, schema, research=True, mcp_config=tmp_path / "mcp.json")
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in args and "--strict-mcp-config" in args
    assert not {"Bash", "Read", "Write", "--dangerously-skip-permissions"} & set(args)
