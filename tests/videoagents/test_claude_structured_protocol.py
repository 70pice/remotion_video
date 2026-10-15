"""Installed Claude CLI against synthetic loopback responses; no provider usage.

The child gets only OS launcher variables, a disposable config directory and a
synthetic token. Production CLI arguments, retry policy and result parsing stay
in the call path; only the base environment and HTTP service are fixtures.
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure

LAUNCHER_ENV = {
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC", "SYSTEMDRIVE",
    "LOCALAPPDATA", "APPDATA", "USERPROFILE", "PROGRAMFILES", "PROGRAMFILES(X86)",
    "PROCESSOR_ARCHITECTURE",
}
WIRE = {"response_json": '{"ok":true}'}


@pytest.fixture
def local_claude(tmp_path, monkeypatch):
    prefix = cli_runner.executable_prefix("claude_code_cli")
    if prefix is None:
        pytest.skip("Claude CLI is not installed; offline protocol integration requires it")
    requests = []
    handler_errors = []
    state = {"mode": "tool-first"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, payload, content_type="application/json", status=200):
            encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("content-type", content_type)
            self.send_header("content-length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            try:
                self.respond()
            except Exception as exc:
                handler_errors.append(repr(exc))
                self.reply({"type": "error", "error": {
                    "type": "invalid_request_error", "message": "offline fixture rejected request",
                }}, status=400)

        def respond(self):
            data = json.loads(self.rfile.read(int(self.headers.get("content-length", "0"))) or b"{}")
            assert self.path in {"/v1/messages", "/v1/messages?beta=true", "/v1/messages/count_tokens",
                                 "/v1/messages/count_tokens?beta=true"}
            if "count_tokens" in self.path:
                self.reply({"input_tokens": 10})
                return
            # Respond with the tool actually declared by this CLI version.
            tools = data.get("tools", [])
            structured = [tool for tool in tools if
                          tool.get("input_schema", {}).get("properties", {}).get("response_json") ==
                          {"type": "string"}]
            assert len(structured) == 1
            tool_name = structured[0]["name"]
            assert [tool["name"] for tool in tools] == [tool_name], "external tools must stay disabled"
            requests.append({"path": self.path, "tool_name": tool_name,
                             "messages": len(data.get("messages", []))})
            assert len(requests) <= 4, "unexpected retry loop in offline fixture"
            mode = state["mode"]
            use_tool = mode != "text-first" or len(requests) > 1
            invalid = mode == "always-invalid" or (mode == "invalid-first" and len(requests) == 1)
            wire = {"response_json": 123} if invalid else WIRE
            if mode == "invalid-inner-json":
                wire = {"response_json": "{invalid fixture JSON"}
            tool_id = f"toolu_offline_{len(requests)}"
            content = ({"type": "tool_use", "id": tool_id, "name": tool_name, "input": wire}
                       if use_tool else {"type": "text", "text": json.dumps(wire)})
            stop_reason = "tool_use" if use_tool else "end_turn"
            response = {
                "id": f"msg_offline_{len(requests)}", "type": "message", "role": "assistant",
                "model": data.get("model", "fixture"), "content": [content],
                "stop_reason": stop_reason, "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 10},
            }
            if not data.get("stream"):
                self.reply(response)
                return
            start = ({"type": "tool_use", "id": tool_id, "name": tool_name, "input": {}}
                     if use_tool else {"type": "text", "text": ""})
            delta = ({"type": "input_json_delta", "partial_json": json.dumps(wire)}
                     if use_tool else {"type": "text_delta", "text": json.dumps(wire)})
            events = [
                ("message_start", {"type": "message_start", "message": {
                    **response, "content": [], "stop_reason": None,
                }}),
                ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": start}),
                ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": delta}),
                ("content_block_stop", {"type": "content_block_stop", "index": 0}),
                ("message_delta", {"type": "message_delta", "delta": {
                    "stop_reason": stop_reason, "stop_sequence": None,
                }, "usage": {"output_tokens": 10}}),
                ("message_stop", {"type": "message_stop"}),
            ]
            payload = "".join(f"event: {kind}\ndata: {json.dumps(value)}\n\n" for kind, value in events)
            self.reply(payload.encode(), "text/event-stream")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
    thread.start()
    config = tmp_path / "claude-config"
    config.mkdir()
    environment = {name: value for name, value in os.environ.items() if name.upper() in LAUNCHER_ENV}
    environment.update({
        "CLAUDE_CONFIG_DIR": str(config),
        "ANTHROPIC_BASE_URL": f"http://127.0.0.1:{server.server_port}",
        "ANTHROPIC_AUTH_TOKEN": "offline-fixture-token",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "DISABLE_TELEMETRY": "1", "DISABLE_ERROR_REPORTING": "1",
        "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",
    })
    monkeypatch.setattr(cli_runner, "_research_environment", lambda _: environment.copy())
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda provider: prefix if provider ==
                        "claude_code_cli" else None)

    def call(mode, *, limit=None):
        assert not requests, "one isolated CLI invocation per fixture"
        state["mode"] = mode
        if limit is not None:
            monkeypatch.setitem(cli_runner.CLAUDE_RETRY_ENV, "MAX_STRUCTURED_OUTPUT_RETRIES", str(limit))
        return cli_runner.run_cli(
            "claude_code_cli", "glm-5.3[1m]", 12,
            "Synthetic offline test. Submit the supplied fixture result using StructuredOutput.",
            {"type": "object", "properties": {"ok": {"type": "boolean"}},
             "required": ["ok"], "additionalProperties": False},
        )

    try:
        yield call, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)
        assert not handler_errors, handler_errors


@pytest.mark.parametrize("mode,request_count", [("tool-first", 1), ("text-first", 2)])
def test_valid_structured_output_succeeds_at_cap_one(local_claude, mode, request_count):
    call, requests = local_claude
    assert call(mode, limit=1).data == {"ok": True}
    assert len(requests) == request_count


def test_first_invalid_structured_output_exhausts_cap_one(local_claude):
    call, requests = local_claude
    with pytest.raises(CliFailure) as failure:
        call("invalid-first", limit=1)
    diagnostic = json.loads(failure.value.reason.partition("; ")[2])
    assert diagnostic["subtype"] == "error_max_structured_output_retries"
    assert diagnostic["reported_terminal_reason"] == "structured_output_retry_exhausted"
    assert len(requests) == 1


def test_first_invalid_structured_output_can_correct_once_at_cap_two(local_claude):
    call, requests = local_claude
    assert call("invalid-first", limit=2).data == {"ok": True}
    assert len(requests) == 2


def test_cap_two_stops_after_two_invalid_structured_attempts(local_claude):
    call, requests = local_claude
    with pytest.raises(CliFailure) as failure:
        call("always-invalid", limit=2)
    diagnostic = json.loads(failure.value.reason.partition("; ")[2])
    assert diagnostic["subtype"] == "error_max_structured_output_retries"
    assert len(requests) == 2


def test_valid_wire_cannot_bypass_inner_json_validation(local_claude):
    call, requests = local_claude
    with pytest.raises(CliFailure) as failure:
        call("invalid-inner-json", limit=2)
    assert failure.value.reason.startswith("invalid_cli_output;")
    assert failure.value.submitted
    assert len(requests) == 1


def test_production_policy_allows_one_structured_correction(local_claude):
    call, requests = local_claude
    assert call("invalid-first").data == {"ok": True}
    assert len(requests) == 2
