"""Claude CLI progress metadata, using local protocol fixtures only."""

import json
import sys

import pytest

from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, CliResult, run_cli

EVENT_ID = "11111111-1111-4111-8111-111111111111"
TOOL = "mcp__videoagents_research__source"
METADATA = [
    {"type": "tool_progress", "tool_use_id": "toolu_fixture", "tool_name": TOOL,
     "parent_tool_use_id": None, "elapsed_time_seconds": 30, "heartbeat": True,
     "uuid": EVENT_ID, "session_id": "fixture-session"},
    {"type": "tool_use_summary", "summary": "private tool summary",
     "preceding_tool_use_ids": ["toolu_fixture"], "uuid": EVENT_ID, "session_id": "fixture-session"},
    {"type": "auth_status", "isAuthenticating": True, "output": ["private auth token"],
     "uuid": EVENT_ID, "session_id": "fixture-session"},
]
SUCCESS = {"type": "result", "subtype": "success", "structured_output": {"response_json": '{"ok":true}'}}


def fixture_cli(tmp_path, monkeypatch, events, ending=""):
    path = tmp_path / "fixture.py"
    path.write_text(
        "import json,sys,time\n" + f"events={events!r}\n"
        + "for event in events:print(json.dumps(event),flush=True)\n" + ending,
        encoding="utf-8",
    )
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda provider: [sys.executable, "-u", str(path)])


def research_call(tmp_path, **kwargs):
    return run_cli(
        "claude_code_cli", "fixture", kwargs.pop("timeout", 5), "fixture", {},
        research_directory=tmp_path / "research", audit_path=tmp_path / "audit.jsonl",
        research_context={"runtime": str(tmp_path), "job_id": "fixture", "revision": 1}, **kwargs,
    )


@pytest.mark.parametrize("metadata", METADATA, ids=lambda value: value["type"])
def test_supported_metadata_does_not_interrupt_research(tmp_path, monkeypatch, metadata):
    start = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": TOOL,
              "id": "toolu_fixture", "input": {"private": "must disappear"}}]}}
    completed = {"type": "user", "message": {"content": [{"type": "tool_result",
                  "tool_use_id": "toolu_fixture", "content": "private source body"}]}}
    fixture_cli(tmp_path, monkeypatch, [start, metadata, completed, SUCCESS])
    assert research_call(tmp_path) == CliResult({"ok": True})
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    rows = [json.loads(line) for line in audit_text.splitlines()]
    assert [row["type"] for row in rows] == ["item.started", metadata["type"], "item.completed", "turn.completed"]
    assert rows[1]["event_id"] == EVENT_ID
    assert "private" not in audit_text and "must disappear" not in audit_text
    assert not list(tmp_path.glob(".videoagents-cli-*"))


@pytest.mark.parametrize("index,changed", [
    (0, {"tool_use_id": "private id\nnot a token"}),
    (0, {"tool_use_id": None}),
    (0, {"parent_tool_use_id": []}),
    (0, {"elapsed_time_seconds": True}),
    (0, {"elapsed_time_seconds": -1}),
    (0, {"elapsed_time_seconds": "30"}),
    (0, {"elapsed_time_seconds": float("inf")}),
    (0, {"elapsed_time_seconds": float("nan")}),
    (0, {"task_id": []}),
    (0, {"heartbeat": "true"}),
    (0, {"subagent_type": {"private": "payload"}}),
    (0, {"subagent_retry": {"private": "payload"}}),
    (0, {"tool_name": []}),
    (1, {"summary": {"private": "payload"}}),
    (1, {"preceding_tool_use_ids": "toolu_fixture"}),
    (1, {"preceding_tool_use_ids": ["toolu_fixture", None]}),
    (1, {"timestamp": 1}),
    (2, {"isAuthenticating": 1}),
    (2, {"output": "private auth text"}),
    (2, {"output": ["private auth text", {}]}),
    (2, {"error": {"private": "payload"}}),
    (0, {"uuid": "private event text"}),
    (1, {"uuid": None}),
    (2, {"session_id": "private session\nnot a token"}),
])
def test_malformed_metadata_fails_closed_without_recording_body(tmp_path, monkeypatch, index, changed):
    event = {**METADATA[index], **changed}
    # repr of nonfinite numbers isn't executable Python; serialize the fixture.
    if index == 0 and isinstance(changed.get("elapsed_time_seconds"), float):
        path = tmp_path / "fixture.py"
        path.write_text("import sys\nsys.stdout.write(" + repr(json.dumps(event) + "\n") + ")\n", encoding="utf-8")
        monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: [sys.executable, "-u", str(path)])
    else:
        fixture_cli(tmp_path, monkeypatch, [event, SUCCESS])
    with pytest.raises(CliFailure) as failure:
        research_call(tmp_path)
    assert failure.value.reason == "invalid_cli_event" and failure.value.submitted
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert json.loads(audit_text) == {"type": "cli.event.rejected", "event_type": event["type"], "status": "rejected"}
    assert "private" not in audit_text


@pytest.mark.parametrize("tool", ["Bash", "PowerShell", "Read", "Write", "Agent", "mcp__unapproved__fetch"])
def test_progress_metadata_does_not_authorize_other_tools(tmp_path, monkeypatch, tool):
    fixture_cli(tmp_path, monkeypatch, [{**METADATA[0], "tool_name": tool}, SUCCESS])
    with pytest.raises(CliFailure) as failure:
        research_call(tmp_path)
    assert failure.value.reason == "unexpected_tool_event" and failure.value.submitted
    assert tool not in (tmp_path / "audit.jsonl").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind,recorded", [
    ("future_metadata", "future_metadata"),
    ("private arbitrary event text", "invalid"),
    ("x" * 65, "invalid"),
])
def test_unknown_metadata_stays_blocked_with_only_bounded_type_audit(tmp_path, monkeypatch, kind, recorded):
    fixture_cli(tmp_path, monkeypatch, [{"type": kind, "private": "must disappear"}, SUCCESS])
    with pytest.raises(CliFailure) as failure:
        research_call(tmp_path)
    assert failure.value.reason == "unexpected_cli_event" and failure.value.submitted
    assert json.loads((tmp_path / "audit.jsonl").read_text(encoding="utf-8")) == {
        "type": "cli.event.rejected", "event_type": recorded, "status": "rejected",
    }


def test_auth_status_never_records_output_error_or_extra_fields(tmp_path, monkeypatch):
    event = {**METADATA[2], "isAuthenticating": False, "error": "private auth failure",
             "extra": {"private": "must disappear"}}
    fixture_cli(tmp_path, monkeypatch, [event, SUCCESS])
    assert research_call(tmp_path).data == {"ok": True}
    rows = [json.loads(line) for line in (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0] == {"type": "auth_status", "event_id": EVENT_ID, "status": "failed"}
    assert all(isinstance(value, str) for row in rows for value in row.values())


@pytest.mark.parametrize("last,ending,reason", [
    ([], "", "incomplete_cli_result"),
    ([{**SUCCESS, "is_error": True}], "", "cli_reported_error"),
    ([{**SUCCESS, "subtype": "error_max_turns"}], "", "cli_reported_error"),
    ([SUCCESS], "sys.exit(3)\n", "cli_nonzero_exit"),
    ([SUCCESS, SUCCESS], "", "duplicate_cli_result"),
    ([], "time.sleep(30)\n", "cli_timeout"),
])
def test_metadata_cannot_replace_or_override_successful_terminal_result(tmp_path, monkeypatch, last, ending, reason):
    fixture_cli(tmp_path, monkeypatch, [*METADATA, *last], ending)
    with pytest.raises(CliFailure) as failure:
        research_call(tmp_path, timeout=0.2 if reason == "cli_timeout" else 5)
    assert failure.value.reason == reason and failure.value.submitted
