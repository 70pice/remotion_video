"""Bounded CLI output transport, exercised with real local child processes."""

import json
import sys

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, CliResult, run_cli
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


def fixture_cli(tmp_path, monkeypatch, code):
    path = tmp_path / "fixture.py"
    path.write_text("import json,sys\n" + code, encoding="utf-8")
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda provider: [sys.executable, "-u", str(path)])


@pytest.mark.parametrize("provider", ["claude_code_cli", "codex_cli"])
def test_research_discards_more_than_four_mib_of_legal_events(tmp_path, monkeypatch, provider):
    code = "body='private research text ' * 6554\n"
    if provider == "claude_code_cli":
        code += (
            "thinking={'type':'assistant','message':{'content':[{'type':'thinking','thinking':body}]}}\n"
            "tool={'type':'user','message':{'content':[{'type':'tool_result','content':body}]}}\n"
            "final={'type':'result','subtype':'success','structured_output':{'response_json':'{\"ok\":true}'}}\n"
        )
    else:
        code += (
            "thinking={'type':'item.completed','item':{'type':'reasoning','text':body}}\n"
            "tool={'type':'item.completed','item':{'type':'mcp_tool_call','status':'completed','result':body}}\n"
            "final={'type':'item.completed','item':{'type':'agent_message','text':"
            "json.dumps({'response_json':'{\"ok\":true}'})}}\n"
        )
    code += (
        "assert sum(len(json.dumps(e).encode())+1 for e in [thinking,tool])*20 > 4*1024*1024\n"
        "for _ in range(20):\n print(json.dumps(thinking))\n print(json.dumps(tool))\n"
        "print(json.dumps(final))\n"
    )
    if provider == "codex_cli":
        code += "print(json.dumps({'type':'turn.completed'}))\n"
    fixture_cli(tmp_path, monkeypatch, code)
    audit = tmp_path / "audit.jsonl"
    result = run_cli(
        provider, "fixture", 15, "fixture", {}, research_directory=tmp_path / "research",
        research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1},
        audit_path=audit,
    )
    assert result == CliResult({"ok": True})
    rows = [json.loads(line) for line in audit.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 21 and rows[-1]["type"] == "turn.completed"
    assert "private research text" not in audit.read_text(encoding="utf-8")
    assert not list(tmp_path.glob(".videoagents-cli-*"))


@pytest.mark.parametrize("provider", ["claude_code_cli", "codex_cli"])
def test_research_rejects_single_unterminated_event_over_four_mib(tmp_path, monkeypatch, provider):
    fixture_cli(tmp_path, monkeypatch, "sys.stdout.buffer.write(b'x'*(4*1024*1024+1))\nsys.stdout.flush()\n")
    with pytest.raises(CliFailure) as failure:
        run_cli(
            provider, "fixture", 5, "fixture", {}, research_directory=tmp_path / "research",
            research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1},
        )
    assert failure.value.reason == "cli_output_limit"
    assert failure.value.submitted and not failure.value.rejected


def test_research_infinite_legal_events_still_exhaust_bounded_stream(tmp_path, monkeypatch):
    fixture_cli(tmp_path, monkeypatch, (
        "line=json.dumps({'type':'assistant','message':{'content':[{'type':'thinking','thinking':'x'*65536}]}})\n"
        "while True:print(line)\n"
    ))
    processes = []
    original_popen = cli_runner.subprocess.Popen
    def capture_process(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        if args[0][0] == sys.executable:
            processes.append(process)
        return process
    monkeypatch.setattr(cli_runner.subprocess, "Popen", capture_process)
    with pytest.raises(CliFailure) as failure:
        run_cli(
            "claude_code_cli", "fixture", 15, "fixture", {}, research_directory=tmp_path / "research",
            research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1},
        )
    assert failure.value.reason == "cli_output_limit" and failure.value.submitted
    assert len(processes) == 1 and processes[0].poll() is not None
    assert not list(tmp_path.glob(".videoagents-cli-*"))


def test_research_final_business_json_cannot_borrow_the_stream_budget(tmp_path, monkeypatch):
    # Permit a larger transport event to isolate the business-response bound.
    monkeypatch.setattr(cli_runner, "MAX_EVENT_BYTES", 8 * 1024 * 1024)
    fixture_cli(tmp_path, monkeypatch, (
        "value={'response_json':json.dumps({'text':'x'*(4*1024*1024)})}\n"
        "print(json.dumps({'type':'result','subtype':'success','structured_output':value}))\n"
    ))
    with pytest.raises(CliFailure) as failure:
        run_cli(
            "claude_code_cli", "fixture", 5, "fixture", {}, research_directory=tmp_path / "research",
            research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1},
        )
    assert failure.value.reason == "cli_output_limit" and failure.value.submitted


@pytest.mark.parametrize("provider", ["claude_code_cli", "codex_cli", "trae_cli"])
def test_nonresearch_cumulative_output_remains_limited_to_four_mib(tmp_path, monkeypatch, provider):
    if provider == "claude_code_cli":
        code = (
            "value={'type':'result','subtype':'success','structured_output':"
            "{'response_json':json.dumps({'text':'x'*(4*1024*1024)})}}\n"
            "print(json.dumps(value,indent=2))\n"
        )
    else:
        code = (
            "line=json.dumps({'type':'item.completed','item':{'type':'reasoning','text':'x'*65536}})\n"
            "for _ in range(65):print(line)\n"
        )
    fixture_cli(tmp_path, monkeypatch, code)
    with pytest.raises(CliFailure) as failure:
        run_cli(provider, "fixture", 5, "fixture", {})
    assert failure.value.reason == "cli_output_limit" and failure.value.submitted


def test_research_output_limit_remains_unknown_and_cannot_be_replayed(tmp_path, monkeypatch):
    fixture_cli(tmp_path, monkeypatch, "sys.stdout.buffer.write(b'x'*(4*1024*1024+1))\n")
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(zhipu_api_key="fake-local-test-key", glm_reasoning_effort="xhigh"))
    model = JsonModel(repo)
    with pytest.raises(CapabilityMissing) as failure:
        model.call("fixture", 1, "screenwriter", "fixture", {}, research_directory=tmp_path / "research")
    assert failure.value.operation_status == "UNKNOWN"
    with repo.connection() as db:
        rows = db.execute("SELECT status,body FROM operations").fetchall()
    assert len(rows) == 1 and rows[0][0] == "UNKNOWN"
    assert json.loads(rows[0][1])["reason"] == "cli_output_limit"
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("must not replay"))
    with pytest.raises(CapabilityMissing) as second:
        model.call("fixture", 1, "screenwriter", "fixture", {}, research_directory=tmp_path / "research")
    assert second.value.operation_status == "UNKNOWN"
    assert second.value.operation_id == failure.value.operation_id


@pytest.mark.parametrize("ending,reason", [
    ("sys.exit(3)", "cli_nonzero_exit"),
    ("import time\ntime.sleep(30)", "cli_timeout"),
    ("", "cli_cancelled"),
])
def test_research_budget_does_not_hide_failure_or_cancellation(tmp_path, monkeypatch, ending, reason):
    fixture_cli(tmp_path, monkeypatch, "print(json.dumps({'type':'system'}))\n" + ending)
    polls = []
    def cancel_after_launch():
        polls.append(True)
        return reason == "cli_cancelled" and len(polls) > 2
    with pytest.raises(CliFailure) as failure:
        run_cli(
            "claude_code_cli", "fixture", 0.2 if reason == "cli_timeout" else 5, "fixture", {},
            cancelled=cancel_after_launch, research_directory=tmp_path / "research",
            research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1},
        )
    assert failure.value.reason == reason and failure.value.submitted
