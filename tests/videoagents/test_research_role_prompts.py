"""Read the real child stdin and MCP config, without launching a model."""

import sys

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, run_cli
from videoagents.providers.llm import JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


@pytest.mark.parametrize("provider", ["codex_cli", "claude_code_cli"])
@pytest.mark.parametrize("role", ["screenwriter", "materials"])
def test_research_child_prompt_matches_role_and_keeps_writer_mcp_read_only(tmp_path, monkeypatch, provider, role):
    path = tmp_path / "fixture.py"
    path.write_text(
        "import sys,json\n"
        "prompt=sys.stdin.buffer.read().decode('utf-8')\n"
        "tools=None\n"
        "if '--mcp-config' in sys.argv:\n"
        " config=json.load(open(sys.argv[sys.argv.index('--mcp-config')+1],encoding='utf-8'))\n"
        " args=config['mcpServers']['videoagents_research']['args']\n"
        " if '--tools' in args:tools=args[args.index('--tools')+1].split(',')\n"
        "wire={'response_json':json.dumps({'prompt':prompt,'tools':tools})}\n"
        "if '--print' in sys.argv:\n"
        " print(json.dumps({'type':'result','subtype':'success','structured_output':wire}))\n"
        "else:\n"
        " print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps(wire)}}))\n"
        " print(json.dumps({'type':'turn.completed'}))\n", encoding="utf-8",
    )
    prefix = [sys.executable, "-u", str(path)]
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: prefix)
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: prefix)
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={role: {"provider": provider, "model": "fixture"}}))
    tools = ("skill", "search", "source") if role == "screenwriter" else None
    result = JsonModel(repo).call("fixture", 1, role, "本角色业务任务", {},
                                 research_directory=tmp_path / "research", research_tools=tools)
    prompt = result["prompt"]
    assert "本角色业务 JSON" in prompt
    if role == "screenwriter":
        assert "这是编剧节点" in prompt
        assert "这是素材节点" not in prompt
        assert "素材研究 JSON" not in prompt and "采集来源与画面" not in prompt
        assert "不采集画面" in prompt
        if provider == "claude_code_cli":
            assert result["tools"] == ["skill", "search", "source"]
    else:
        assert "这是素材节点" in prompt
        assert "画面" in prompt and result["tools"] is None
    if provider == "claude_code_cli":
        assert "不使用 shell" in prompt
    else:
        assert "web_search" in prompt


def test_invalid_research_role_is_rejected_before_child_start(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: pytest.fail("must not resolve or launch CLI"))
    with pytest.raises(CliFailure, match="unsupported_research_role") as error:
        run_cli("codex_cli", "fixture", 5, "fixture", {}, research_directory=tmp_path / "research",
                research_role="voice")
    assert error.value.submitted is False
    assert not (tmp_path / "research").exists()
