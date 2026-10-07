"""Assert evidence reaches the actual CLI boundary, not merely node mocks."""

import json

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.nodes import screenwriter, script_reviewer
from videoagents.providers.cli_runner import CliResult
from videoagents.providers.llm import JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


@pytest.mark.parametrize("role,instruction,fields", [
    ("screenwriter", screenwriter.PROMPT, ("brief", "research", "assets")),
    ("screenwriter", screenwriter.REWRITE_PROMPT,
     ("brief", "script", "script_discussion", "research", "assets", "extras")),
    ("script_reviewer", script_reviewer.PROMPT,
     ("brief", "script", "script_discussion", "research", "assets", "extras")),
], ids=["draft", "rewrite", "review"])
def test_script_roles_send_source_body_assets_and_feedback_to_cli(tmp_path, monkeypatch, role, instruction, fields):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={role: {
        "enabled": True, "provider": "codex_cli", "model": "unit-model",
    }}))
    source = "https://example.test/report"
    state = {
        "job_id": "unit-job", "revision": 1,
        "brief": {"creative_direction": "完整解读报告，给普通观众讲清口径", "target_seconds": 240},
        "research": {
            "sources": [{"url": source, "title": "报告", "text": "正文：网站按访问量排序，手机按月活排序。"}],
            "visuals": [{"asset_id": "real-chart", "source_url": source, "description": "八月榜单原图"}],
            "limitations": ["流量不能证明能力"],
            "tool_calls": [{"secret": "UNIT-TOOL-TRACE"}],
        },
        "assets": [{"asset_id": "real-chart", "name": "真实榜单图", "role": "evidence", "source_url": source}],
        "script": {"segments": [{"segment_id": "s1", "narration": "网站和手机榜统计的不是一件事。"}]},
        "script_discussion": {"rounds": [{"critique": {"decision": "REVISE", "summary": "解释清楚两个口径"}}]},
        "extras": {"human_feedback": {"script": {"note": "不要只列产品名，要完整讲解报告", "applied": True}}},
        "settings": {"ark_api_key": "UNIT-SECRET"},
    }
    captured = []

    def transport(provider, model, timeout, prompt, schema, **kwargs):
        captured.append(prompt)
        return CliResult({"ok": True})

    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: ["unit-cli"])
    monkeypatch.setattr("videoagents.providers.llm.run_cli", transport)
    JsonModel(repo).invoke(state, role, instruction, fields=fields)

    prompt = captured[0]
    payload = json.loads(prompt.split("\n上下文：\n", 1)[1])
    assert instruction in prompt
    assert set(payload) == set(fields)
    assert payload["brief"]["creative_direction"] == state["brief"]["creative_direction"]
    assert payload["research"]["sources"][0]["text"] == state["research"]["sources"][0]["text"]
    assert payload["research"]["visuals"][0]["asset_id"] == payload["assets"][0]["asset_id"]
    assert payload["research"]["limitations"] == ["流量不能证明能力"]
    if "extras" in fields:
        assert payload["extras"]["human_feedback"] == state["extras"]["human_feedback"]
    assert "UNIT-SECRET" not in prompt and "UNIT-TOOL-TRACE" not in prompt
