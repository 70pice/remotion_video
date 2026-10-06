"""Final role outputs survive handoff/recovery; tool traces stay in the audit store."""

import json
import sqlite3

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from videoagents.contracts import Brief, SettingsPatch
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.clear_tools import ClearToolsNode
from videoagents.nodes.common import current_job
from videoagents.nodes.materials import MaterialsNode
from videoagents.providers import llm
from videoagents.providers.cli_runner import CliResult
from videoagents.providers.llm import JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState, clean_handoff, merge_extras
from videoagents.storage import Repository


def raw_research():
    return {
        "status": "COMPLETED",
        "sources": [{"url": "https://example.test/muse", "text": "Muse 的来源正文。",
                     "title": "Muse", "sha256": "a" * 64, "asset_ids": ["image-1"],
                     "tool_calls": ["UNIT-private-source"]}],
        "visuals": [{"asset_id": "image-1", "source_url": "https://example.test/muse",
                     "knowledge_excerpt": "来源中的画面依据", "license_status": "needs_review",
                     "tool_result": "UNIT-private-image"}],
        "tools": [{"platform": "reddit", "status": "error", "request_id": "UNIT-private-request"}],
        "failures": [{"url": "https://example.test/missing", "stage": "read", "reason": "UNIT-private-error"}],
        "capture_notes": [{"url": "https://example.test/muse", "reason": "UNIT-private-capture"}],
        "search_results": [{"url": "https://example.test/lead", "snippet": "UNIT-private-search"}],
    }


def test_frozen_research_is_clean_on_recovery_but_audit_and_unknown_receipts_survive(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="Muse"))
    audit = raw_research()
    artifact = service.write_json(job, "research.json", audit, "research")
    operation = repo.start_operation(job.job_id, "unit-input", "llm:screenwriter", {"revision": job.revision})
    repo.finish_operation(operation["operation_id"], "UNKNOWN", {"revision": job.revision})
    state = VideoState(job_id=job.job_id, revision=job.revision, research=audit,
                       messages=[{"role": "tool", "content": "UNIT-private-message"}],
                       operations=[{"operation_id": operation["operation_id"]}])

    current_job(repo, state)
    encoded = json.dumps(state, ensure_ascii=False)
    assert "UNIT-private" not in encoded
    assert "operations" not in state and "messages" not in state
    assert state["research"]["sources"][0]["text"] == "Muse 的来源正文。"
    assert state["research"]["visuals"][0]["asset_id"] == "image-1"
    assert "plan" not in state["research"]
    assert "正文未取得" in " ".join(state["research"]["limitations"])
    path = repo.artifact_path(artifact.artifact_id)[0]
    assert json.loads(path.read_text(encoding="utf-8")) == audit
    assert repo.unsettled_operation(job.job_id, "llm:screenwriter", job.revision)["operation_id"] == operation["operation_id"]


def test_final_outputs_flow_through_two_roles_and_sqlite_checkpoint_without_tool_history(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="Muse"))
    model = JsonModel(repo)
    seen = []

    def call(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        seen.append((role, context))
        if role == "screenwriter":
            return {"title": "Muse", "origin": "model", "revision": job.revision,
                    "segments": [{"segment_id": "s1", "narration": "编剧最终口播稿。",
                                  "source_refs": ["https://example.test/muse"]}]}
        return {"decision": "APPROVE", "summary": "文案审查最终意见", "issues": []}

    monkeypatch.setattr(model, "call", call)

    def writer(state):
        output = model.invoke(state, "screenwriter", "固定编剧 Prompt", fields=("brief", "research"))
        return clean_handoff({**state, "script": output, "tool_calls": ["UNIT-private-writer"]})

    def reviewer(state):
        output = model.invoke(state, "script_reviewer", "固定审查 Prompt", fields=("research", "script"))
        return clean_handoff({**state, "script_discussion": {"rounds": [{"script": state["script"], "critique": output}]}})

    with sqlite3.connect(tmp_path / "checkpoint.sqlite", check_same_thread=False) as connection:
        graph = StateGraph(VideoState)
        graph.add_node("writer", writer)
        graph.add_node("reviewer", reviewer)
        graph.add_edge(START, "writer")
        graph.add_edge("writer", "reviewer")
        graph.add_edge("reviewer", END)
        compiled = graph.compile(checkpointer=SqliteSaver(connection))
        config = {"configurable": {"thread_id": "unit-handoff"}}
        result = compiled.invoke(clean_handoff(VideoState(job_id=job.job_id, revision=job.revision,
                                brief=job.brief.model_dump(), research=raw_research())), config)
        saved = compiled.get_state(config).values

    assert seen[1][1]["script"]["segments"][0]["narration"] == "编剧最终口播稿。"
    assert result["script_discussion"]["rounds"][0]["critique"]["summary"] == "文案审查最终意见"
    assert saved["research"] == result["research"]
    assert "UNIT-private" not in json.dumps(seen, ensure_ascii=False)
    assert "UNIT-private" not in json.dumps(saved, ensure_ascii=False)


def test_tool_traces_do_not_change_logical_cli_request_or_trigger_duplicate_submission(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="Muse"))
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {"enabled": True, "provider": "codex_cli"}}))
    calls = []
    monkeypatch.setattr(llm, "executable_prefix", lambda provider: ["unit-cli"])

    def run_cli(provider, model, timeout, prompt, schema, cancelled):
        calls.append(prompt)
        return CliResult({"final": "最终稿件"}, {"output_tokens": 1})

    monkeypatch.setattr(llm, "run_cli", run_cli)
    state = VideoState(job_id=job.job_id, revision=job.revision, research=raw_research(),
                       extras={"final_note": "来源已读取", "tool_calls": ["UNIT-private-extra"]})
    model = JsonModel(repo)
    first = model.invoke(state, "screenwriter", "固定 Prompt", fields=("research", "extras"))
    state["research"]["tools"][0]["request_id"] = "UNIT-another-private-request"
    state["research"]["search_results"].append({"url": "https://example.test/another-lead"})
    state["extras"]["tool_calls"] = ["UNIT-another-private-extra"]
    second = model.invoke(state, "screenwriter", "固定 Prompt", fields=("research", "extras"))
    assert first == second == {"final": "最终稿件"}
    assert len(calls) == 1 and "UNIT-private" not in calls[0]
    state["research"]["sources"][0]["text"] = "新的最终来源正文。"
    model.invoke(state, "screenwriter", "固定 Prompt", fields=("research", "extras"))
    assert len(calls) == 2


def test_model_input_filters_secrets_and_refuses_runtime_ledger_fields(tmp_path, monkeypatch):
    model = JsonModel(Repository(tmp_path / "runtime"))
    contexts = []
    monkeypatch.setattr(model, "call", lambda *args, **kwargs: contexts.append(args[4]) or {})
    state = VideoState(job_id="unit-job", revision=1,
                       settings={"voice_style": "热情演讲", "voice_speech_rate": 30,
                                 "voice_api_key": "UNIT-private-key", "research_tools": ["UNIT-private-tool"]})
    model.invoke(state, "voice", "固定 Prompt", fields=("settings",))
    assert contexts == [{"settings": {"voice_style": "热情演讲", "voice_speech_rate": 30}}]
    with pytest.raises(ValueError, match="最终业务产物"):
        model.invoke(state, "voice", "固定 Prompt", fields=("operations",))


@pytest.mark.parametrize("field", ["script", "script_discussion", "voice_guidance", "editing_guidance", "timeline", "review", "extras"])
def test_every_role_output_removes_nested_tool_history_and_preserves_final_data(field):
    final = {"summary": "角色最终产出", "nested": [{"note": "有效业务信息", "tool_results": ["UNIT-private-result"]}],
             "tool_calls": ["UNIT-private-call"], "messages": ["UNIT-private-message"]}
    cleaned = clean_handoff(VideoState(job_id="unit", revision=1, **{field: final}))
    assert cleaned[field] == {"summary": "角色最终产出", "nested": [{"note": "有效业务信息"}]}


def test_extras_reducer_cannot_restore_tool_history_in_real_checkpoint(tmp_path):
    def first(state):
        return {"extras": {"keep": "最终研究", "tool_calls": ["UNIT-private-first"],
                           "nested": {"final": "已读取正文", "messages": ["UNIT-private-nested"]}}}

    def second(state):
        assert "UNIT-private" not in json.dumps(state)
        return {"extras": {"next": "最终文案", "tool_results": ["UNIT-private-second"]}}

    with sqlite3.connect(tmp_path / "extras.sqlite", check_same_thread=False) as db:
        builder = StateGraph(VideoState)
        builder.add_node("first", first)
        builder.add_node("second", second)
        builder.add_edge(START, "first")
        builder.add_edge("first", "second")
        builder.add_edge("second", END)
        graph = builder.compile(checkpointer=SqliteSaver(db))
        config = {"configurable": {"thread_id": "unit-extras"}}
        result = graph.invoke(VideoState(job_id="unit", revision=1, extras={}), config)
        assert result["extras"] == {"keep": "最终研究", "nested": {"final": "已读取正文"}, "next": "最终文案"}
        assert all("UNIT-private" not in json.dumps(item.values) for item in graph.get_state_history(config))


def test_generic_tools_and_operations_in_final_business_data_survive_handoff():
    business = {"tools": ["剪辑软件清单"], "operations": ["先配音，再制作分镜"],
                "nested": {"tool_calls": ["UNIT-private-tool"], "tools": ["字幕编辑软件"]}}
    state = VideoState(job_id="unit", revision=1, extras=business, research=raw_research(),
                       tools=[{"request_id": "UNIT-private-runtime"}], operations=["UNIT-private-ledger"])
    result = ClearToolsNode()(state)
    assert result["extras"] == {"tools": ["剪辑软件清单"], "operations": ["先配音，再制作分镜"],
                                "nested": {"tools": ["字幕编辑软件"]}}
    assert "tools" not in result and "operations" not in result
    assert "tools" not in result["research"]
    assert "UNIT-private" not in json.dumps(result)
    assert merge_extras({}, business) == result["extras"]


@pytest.mark.parametrize("role", ["materials", "screenwriter", "script_reviewer", "voice", "director", "editing", "reviewers"])
def test_every_production_role_routes_through_its_clear_node(tmp_path, role):
    with VideoProductionGraph(Repository(tmp_path / "runtime"), tmp_path / "project") as production:
        topology = production.graph.get_graph()
        outgoing = [edge for edge in topology.edges if edge.source == role]
        assert len(outgoing) == 1
        assert outgoing[0].target == "clear_" + role
        assert not outgoing[0].conditional
        assert all(edge.conditional for edge in topology.edges if edge.source == "clear_" + role)


def test_clear_node_preserves_final_outputs_and_pause_binding_without_audit_references():
    state = VideoState(job_id="unit", revision=2, route="await_input", run_id="unit-run",
                       pending_snapshot={"pending_token": "unit-token", "stage": "materials"},
                       research=raw_research(), extras={"final_summary": "素材已核验"},
                       artifacts=[{"artifact_id": "audit", "kind": "material_tool_audit"},
                                  {"artifact_id": "manifest", "kind": "material_skill_manifest"},
                                  {"artifact_id": "final", "kind": "script"}],
                       artifact_metadata={"audit": {"source_url": "UNIT-private-audit"},
                                          "manifest": {"source_url": "UNIT-private-manifest"},
                                          "final": {"dependency_fingerprint": "unit-fingerprint"}})
    result = ClearToolsNode()(state)
    assert result["route"] == "await_input" and result["run_id"] == "unit-run"
    assert result["pending_snapshot"] == state["pending_snapshot"]
    assert result["extras"] == {"final_summary": "素材已核验"}
    assert result["artifacts"] == [{"artifact_id": "final", "kind": "script"}]
    assert result["artifact_metadata"] == {"final": {"dependency_fingerprint": "unit-fingerprint"}}
    assert result["research"]["sources"][0]["text"] == "Muse 的来源正文。"
    assert "UNIT-private" not in json.dumps(result)


def test_production_graph_clears_each_completed_role_before_real_input_pause(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False))
    job = repo.create_job(Brief(script_text="观点：我喜欢这个配色。"))
    service.write_json(job, "research.json", {"status": "COMPLETED", "sources": [], "visuals": [],
                       "limitations": ["UNIT TEST：观点稿无需事实来源，素材包显式为空。"]}, "research")
    visited = []
    original_clear = ClearToolsNode.__call__
    original_materials = MaterialsNode.__call__

    def materials(self, state):
        result = original_materials(self, state)
        result["extras"] = {"final_summary": "素材已核验", "tool_calls": ["UNIT-private-model"]}
        return result

    def clear(self, state):
        visited.append(state["stage"])
        return original_clear(self, state)

    monkeypatch.setattr(MaterialsNode, "__call__", materials)
    monkeypatch.setattr(ClearToolsNode, "__call__", clear)
    monkeypatch.setattr(JsonModel, "call", lambda *args, **kwargs: pytest.fail("Offline test reached a model"))
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "unit-clear"})
    with VideoProductionGraph(repo, service.project_root) as production:
        result = production.execute(repo.claim(12345))
        assert visited == ["materials", "script"]
        assert result["extras"] == {"final_summary": "素材已核验"}
        assert result["script"]["segments"][0]["narration"] == job.brief.script_text
        paused = repo.get_job(job.job_id)
        assert paused.status == "NEEDS_HUMAN" and paused.stage == "script"
        assert paused.pending_input["kind"] == "stage_review"
        assert paused.pending_input["node_name"] == "human_review_script"
        config = {"configurable": {"thread_id": paused.pending_input["thread_id"]}}
        saved = production.graph.get_state(config)
        assert saved.interrupts[0].value["pending_token"] == paused.pending_input["pending_token"]
        assert all("UNIT-private" not in json.dumps(item.values) for item in production.graph.get_state_history(config))
