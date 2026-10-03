"""Noninteractive, isolated CLI transports. No shell strings or model SDKs."""

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from worker.process_manager import terminate_tree
from worker.windows_job import WindowsJob

MAX_OUTPUT_BYTES = 4 * 1024 * 1024
# The CLI transport needs OpenAI's strict schema subset. Business contracts
# contain defaults/free-form props, so carry their locally validated JSON as a
# string instead of silently narrowing the actual production contract.
WIRE_SCHEMA = {
    "type": "object", "properties": {"response_json": {"type": "string"}},
    "required": ["response_json"], "additionalProperties": False,
}
CODEX_DISABLED = (
    "shell_tool", "unified_exec", "multi_agent", "apps", "remote_plugin", "plugins", "hooks",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use",
    "in_app_browser", "in_app_chat", "in_app_local_automation", "in_app_dictation",
    "image_generation", "tool_suggest", "skill_mcp_dependency_install", "skill_search",
    "view_image", "workspace_dependencies",
)


class CliFailure(Exception):
    def __init__(self, reason: str, *, submitted: bool = True, rejected: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.submitted = submitted
        self.rejected = rejected


@dataclass(frozen=True)
class CliResult:
    data: dict[str, Any]
    usage: dict[str, Any] | None = None


def executable_prefix(provider: str) -> list[str] | None:
    """Resolve npm Windows shims to Node, never execute .cmd through a shell."""
    names = {"codex_cli": ("codex", "@openai/codex/bin/codex.js"),
             "claude_code_cli": ("claude", "@anthropic-ai/claude-code/cli.js")}
    if provider not in names:
        return None
    name, entry = names[provider]
    configured = os.getenv("VIDEOAGENTS_" + name.upper() + "_EXECUTABLE")
    found = configured or shutil.which(name)
    if not found and os.name == "nt" and name == "claude":
        candidate = Path.home() / ".local" / "bin" / "claude.exe"
        found = str(candidate) if candidate.is_file() else None
    if not found:
        return None
    path = Path(found).resolve()
    if not path.is_file():
        return None
    if os.name != "nt" or path.suffix.lower() == ".exe":
        return [str(path)]
    node = shutil.which("node")
    script = path if path.suffix.lower() in {".js", ".mjs"} else path.parent / "node_modules" / entry
    if node and script.is_file():
        return [node, str(script)]
    return None


def cli_availability() -> dict[str, dict[str, bool]]:
    return {provider: {"available": executable_prefix(provider) is not None}
            for provider in ("codex_cli", "claude_code_cli")}


def build_arguments(provider: str, prefix: list[str], model: str, directory: Path, schema: Path) -> list[str]:
    if provider == "codex_cli":
        args = [*prefix, "-a", "never", "exec", "--sandbox", "read-only", "--ephemeral",
                "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules", "--json",
                "--color", "never", "--cd", str(directory), "--output-schema", str(schema),
                "-c", 'web_search="disabled"']
        for feature in CODEX_DISABLED:
            args.extend(["--disable", feature])
        if model:
            args.extend(["--model", model])
        return [*args, "-"]
    if provider == "claude_code_cli":
        args = [*prefix, "--print", "--output-format", "json", "--json-schema",
                schema.read_text(encoding="utf-8"), "--tools", "", "--disallowedTools", "mcp__*",
                "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
                "--disable-slash-commands", "--no-session-persistence", "--permission-mode", "dontAsk"]
        if model:
            args.extend(["--model", model])
        return args
    raise CliFailure("unsupported_cli", submitted=False)


def _codex_event(line: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    event = json.loads(line)
    if not isinstance(event, dict):
        raise CliFailure("invalid_cli_event")
    kind = event.get("type")
    if kind in {"item.started", "item.updated", "item.completed"}:
        item = event.get("item", {})
        if not isinstance(item, dict) or item.get("type") not in {"reasoning", "agent_message"}:
            raise CliFailure("unexpected_tool_event")
        if kind == "item.completed" and item.get("type") == "agent_message":
            return _business_object(json.loads(item.get("text", ""))), None
    elif kind == "turn.completed":
        return None, event.get("usage")
    elif kind in {"error", "turn.failed"}:
        raise CliFailure("cli_reported_error")
    elif kind not in {"thread.started", "turn.started"}:
        raise CliFailure("unexpected_cli_event")
    return None, None


def _business_object(envelope: Any) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != {"response_json"} or not isinstance(envelope["response_json"], str):
        raise CliFailure("missing_structured_output")
    result = json.loads(envelope["response_json"])
    if not isinstance(result, dict):
        raise CliFailure("non_object_output")
    return result


def _claude_result(output: str) -> CliResult:
    value = json.loads(output)
    if not isinstance(value, dict) or value.get("type") != "result":
        raise CliFailure("invalid_cli_result")
    if value.get("is_error") or value.get("subtype") != "success":
        # CLI errors can happen after billing. They never prove nonacceptance.
        raise CliFailure("cli_reported_error")
    return CliResult(_business_object(value.get("structured_output")), value.get("usage"))


def run_cli(provider: str, model: str, timeout: int, prompt: str, output_schema: dict[str, Any],
            cancelled=lambda: False) -> CliResult:
    if cancelled():
        raise CliFailure("cli_cancelled", submitted=False)
    prefix = executable_prefix(provider)
    if prefix is None:
        raise CliFailure("cli_not_installed", submitted=False)
    with tempfile.TemporaryDirectory(prefix="videoagents-cli-") as temporary:
        directory = Path(temporary)
        schema = directory / "output-schema.json"
        schema.write_text(json.dumps(WIRE_SCHEMA, ensure_ascii=False), encoding="utf-8")
        source = directory / "input.txt"
        transport_prompt = (prompt + "\n业务 JSON schema：\n" + json.dumps(output_schema, ensure_ascii=False)
                            + '\n最终传输格式必须为 {"response_json":"业务 JSON 对象序列化后的字符串"}。'
                            + "response_json 内的对象遵循上面的业务 schema，外层仅有 response_json 一个字段。")
        source.write_text(transport_prompt, encoding="utf-8")
        args = build_arguments(provider, prefix, model, directory, schema)
        job = WindowsJob()
        try:
            with source.open("rb") as stream:
                try:
                    if cancelled():
                        raise CliFailure("cli_cancelled", submitted=False)
                    process = subprocess.Popen(args, cwd=directory, stdin=stream, stdout=subprocess.PIPE,
                                               stderr=subprocess.DEVNULL, shell=False,
                                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                               start_new_session=os.name != "nt")
                except OSError as exc:
                    raise CliFailure("cli_launch_failed", submitted=False) from exc
        except BaseException:
            job.close()
            raise
        lines: queue.Queue = queue.Queue(maxsize=64)
        stopped = threading.Event()
        def enqueue(line):
            while not stopped.is_set():
                try:
                    lines.put(line, timeout=0.1)
                    return
                except queue.Full:
                    continue
        def read():
            try:
                while not stopped.is_set() and (line := process.stdout.readline(MAX_OUTPUT_BYTES + 1)):
                    enqueue(line)
            finally:
                enqueue(None)
        reader = threading.Thread(target=read, daemon=True)
        data, usage, output, size, completed = None, None, [], 0, False
        try:
            job.assign(process)
            reader.start()
            deadline = time.monotonic() + timeout
            while True:
                if cancelled():
                    raise CliFailure("cli_cancelled")
                if time.monotonic() > deadline:
                    raise CliFailure("cli_timeout")
                try:
                    line = lines.get(timeout=0.1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                size += len(line)
                if size > MAX_OUTPUT_BYTES:
                    raise CliFailure("cli_output_limit")
                decoded = line.decode("utf-8", errors="strict").strip()
                if not decoded:
                    continue
                if provider == "codex_cli":
                    item, counts = _codex_event(decoded)
                    data = item if item is not None else data
                    usage = counts if counts is not None else usage
                    completed |= json.loads(decoded).get("type") == "turn.completed"
                else:
                    output.append(decoded)
            remaining = max(0.01, deadline - time.monotonic())
            if process.wait(timeout=remaining) != 0:
                raise CliFailure("cli_nonzero_exit")
            if provider == "claude_code_cli":
                return _claude_result("\n".join(output))
            if not completed or data is None:
                raise CliFailure("incomplete_cli_result")
            return CliResult(data, usage)
        except CliFailure:
            raise
        except Exception as exc:
            raise CliFailure("invalid_cli_output") from exc
        finally:
            stopped.set()
            terminate_tree(process)
            job.close()
            if reader.ident:
                reader.join(timeout=1)
            process.stdout.close()
