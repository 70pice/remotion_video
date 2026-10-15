"""Noninteractive, isolated CLI transports. No shell strings or model SDKs."""

import json
import logging
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from videoagents.default_config import DEFAULT_GLM_REASONING_EFFORT
from videoagents.default_config import DEFAULT_SCRIPT_MODEL as GLM_MODEL
from worker.process_manager import terminate_tree
from worker.windows_job import WindowsJob

MAX_OUTPUT_BYTES = 4 * 1024 * 1024
# Research emits fetched tool content and thinking before its business result.
# Bound each NDJSON event separately and discard it after projection; the
# larger cumulative budget does not enlarge the final structured response.
MAX_EVENT_BYTES = 4 * 1024 * 1024
MAX_RESEARCH_STREAM_BYTES = 64 * 1024 * 1024
MAX_AUTH_BYTES = 1024 * 1024
MAX_STDERR_TAIL_BYTES = 8 * 1024
# A logical engine operation must not silently multiply retries inside Claude.
# Normal tool turns can still make several requests; this is not a token cap.
CLAUDE_RETRY_ENV = {
    "CLAUDE_CODE_MAX_RETRIES": "0",
    "MAX_STRUCTURED_OUTPUT_RETRIES": "1",
    "CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES": "0",
}
_LOGGER = logging.getLogger(__name__)
GLM_CONTEXT_TOKENS = 1_000_000
GLM_CAPABILITIES = "effort,xhigh_effort,max_effort,thinking,adaptive_thinking"
CLAUDE_RESEARCH_TOOLS = {
    "mcp__videoagents_research__skill", "mcp__videoagents_research__search",
    "mcp__videoagents_research__source", "mcp__videoagents_research__visual",
    "mcp__videoagents_research__screenshot",
}
CLAUDE_RESEARCH_METADATA = {"tool_progress", "tool_use_summary", "auth_status"}
# Fixed result subtypes from the Claude SDK, plus the legacy model error.
# Never persist errors/result prose; diagnostic codes use fixed allowlists.
CLAUDE_FAILURE_HINTS = {
    "error_during_execution": "CLI执行失败，具体供应商原因尚未确定",
    "error_max_turns": "CLI达到本次会话轮次上限，未取得可用结果",
    "error_max_budget_usd": "CLI达到本次调用预算上限，未取得可用结果",
    "error_max_structured_output_retries": "CLI未生成有效结构化输出（重试次数已耗尽）",
    "unrecognized_model": "CLI错误回执报告模型标识无法识别",
}
API_ERROR_TYPES = {
    "invalid_request_error", "authentication_error", "billing_error", "permission_error",
    "not_found_error", "rate_limit_error", "api_error", "overloaded_error", "request_too_large",
    "conflict_error", "timeout_error",
}
HTTP_FAILURE_HINTS = {
    400: "CLI报告接口拒绝请求（HTTP 400），具体参数原因尚未确定",
    401: "CLI报告接口认证失败（HTTP 401）",
    402: "CLI报告接口账单错误（HTTP 402）",
    403: "CLI报告接口权限不足（HTTP 403）",
    404: "CLI报告接口资源不存在（HTTP 404）",
    408: "CLI报告接口请求超时（HTTP 408）",
    409: "CLI报告接口请求冲突（HTTP 409）",
    413: "CLI报告接口请求过大（HTTP 413）",
    422: "CLI报告接口无法处理请求（HTTP 422），具体参数原因尚未确定",
    429: "CLI报告接口限制请求（HTTP 429），尚不能区分限流与额度原因",
    500: "CLI报告接口内部错误（HTTP 500）",
    502: "CLI报告接口网关错误（HTTP 502）",
    503: "CLI报告接口暂不可用（HTTP 503）",
    504: "CLI报告接口网关超时（HTTP 504）",
    529: "CLI报告接口过载（HTTP 529）",
}
TRANSPORT_FAILURE_MESSAGES = {
    "Connection error.": "connection_error",
    "Request timed out.": "request_timeout",
    "Stream closed": "stream_closed",
    "Connection lost mid-response": "stream_closed",
    "The response stream was malformed": "malformed_stream",
    "Unexpected end of JSON input": "unexpected_json_end",
}
TRANSPORT_FAILURE_HINTS = {
    "connection_error": "CLI报告连接错误，尚不能区分本机网络与供应商中断",
    "request_timeout": "CLI报告请求超时，尚不能确定发生在哪一端",
    "stream_closed": "CLI报告响应流提前关闭，未取得完整结果",
    "malformed_stream": "CLI报告响应流格式错误，未取得完整结果",
    "unexpected_json_end": "CLI报告JSON读取到意外结尾，具体截断原因尚未确定",
}
CLAUDE_TERMINAL_HINTS = {
    "completed": "CLI报告本轮会话结束，但未取得可用结果，失败原因尚未确定",
    "max_turns": "CLI报告达到会话轮次上限",
    "tool_deferred": "CLI报告工具执行被延期",
    "aborted_streaming": "CLI报告响应流被中止",
    "aborted_tools": "CLI报告工具执行被中止",
    "hook_stopped": "CLI报告被停止钩子终止",
    "stop_hook_prevented": "CLI报告停止钩子阻止结束",
    "background_requested": "CLI报告请求转为后台执行",
    "blocking_limit": "CLI报告达到阻断限制，具体限制尚未确定",
    "rapid_refill_breaker": "CLI报告快速重填保护触发，具体原因尚未确定",
    "prompt_too_long": "CLI报告输入过长",
    "image_error": "CLI报告图片处理错误",
    "model_error": "CLI报告模型错误，供应商具体原因尚未确定",
    "api_error": "CLI报告API错误，未提供可识别的HTTP状态",
    "malformed_tool_use_exhausted": "CLI报告无效工具调用的重试次数已耗尽",
    "budget_exhausted": "CLI报告本次调用预算耗尽",
    "structured_output_retry_exhausted": "CLI报告结构化输出重试次数已耗尽",
    "tool_deferred_unavailable": "CLI报告延期工具不可用",
    "turn_setup_failed": "CLI报告会话轮次初始化失败",
}
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
CODEX_RESEARCH_DISABLED = (
    "multi_agent", "apps", "remote_plugin", "plugins", "hooks",
    "browser_use", "browser_use_external", "browser_use_full_cdp_access", "computer_use",
    "in_app_browser", "in_app_chat", "in_app_local_automation", "in_app_dictation",
    "image_generation", "tool_suggest", "skill_mcp_dependency_install",
)
TRAE_DISABLED = (
    "shell_tool", "unified_exec", "apply_patch_freeform", "multi_agent", "multi_agent_v2",
    "apps", "plugins", "hooks", "plugin_hooks", "browser_use",
    "browser_use_external", "computer_use", "in_app_browser", "image_generation", "tool_suggest",
    "skill_mcp_dependency_install", "tool_search", "workspace_dependencies", "shell_snapshot",
    "goals", "memories", "task_v2", "workspace_undo", "codex_git_commit",
)
# 当前 CLI 的研究会话也会报告协作工具生命周期。只在素材模式接收，
# 与其他工具一样只保留脱敏审计摘要，不把过程消息当作业务结果。
CODEX_RESEARCH_TOOLS = {"command_execution", "web_search", "mcp_tool_call", "file_change", "collab_tool_call"}
CODEX_MANAGED_CONTEXT_ENV = {
    "CODEX_PERMISSION_PROFILE",
    "CODEX_INTERNAL_ORIGINATOR_OVERRIDE",
    "CODEX_SESSION_ID",
    "CODEX_THREAD_ID",
    "CODEX_TASK_WORKSPACE_VERIFYING_IDENTITY",
    "CODEX_APP_TOOLS_PIPE_PATH",
    "CODEX_WINDOWS_SANDBOX_PACKAGE_FAMILY",
}
TRAE_MANAGED_CONTEXT_ENV = {
    "TRAE_COMPUTER_USE_MTC_TARGET",
    "TRAE_RUNTIME",
    "TRAE_SANDBOX_CLI_PATH",
    "TRAE_SANDBOX_DUMP_DIR",
    "TRAE_SANDBOX_LOG_DIR",
    "TRAE_SANDBOX_NEW_PERMISSION",
    "TRAE_SANDBOX_SBOX_ID",
    "TRAE_SANDBOX_STORAGE_PATH",
    "TRAE_SANDBOX_TRACE_FILE",
}


class CliFailure(Exception):
    def __init__(self, reason: str, *, submitted: bool = True, rejected: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.submitted = submitted
        self.rejected = rejected

    @property
    def hint(self) -> str:
        reason_code, separator, details = self.reason.partition("; ")
        if reason_code not in {"cli_nonzero_exit", "cli_reported_error"} or not separator or len(details) > 1024:
            return ""
        try:
            diagnostic = json.loads(details)
        except (ValueError, RecursionError):
            return ""
        if not isinstance(diagnostic, dict):
            return ""
        status, kind = diagnostic.get("reported_http_status"), diagnostic.get("reported_error_kind")
        if type(status) is int and status in HTTP_FAILURE_HINTS:
            return HTTP_FAILURE_HINTS[status]
        if isinstance(kind, str) and kind in TRANSPORT_FAILURE_HINTS:
            return TRANSPORT_FAILURE_HINTS[kind]
        terminal = diagnostic.get("reported_terminal_reason")
        if isinstance(terminal, str) and terminal != "completed" and terminal in CLAUDE_TERMINAL_HINTS:
            return CLAUDE_TERMINAL_HINTS[terminal]
        subtype = diagnostic.get("subtype")
        subtype_hint = CLAUDE_FAILURE_HINTS.get(subtype, "") if isinstance(subtype, str) else ""
        return subtype_hint or (CLAUDE_TERMINAL_HINTS["completed"] if terminal == "completed" else "")


@dataclass(frozen=True)
class CliResult:
    data: dict[str, Any]
    usage: dict[str, Any] | None = None


def executable_prefix(provider: str) -> list[str] | None:
    """Resolve npm Windows shims to a native binary or Node without a shell."""
    names = {"codex_cli": ("codex", "@openai/codex/bin/codex.js"),
             "claude_code_cli": ("claude", "@anthropic-ai/claude-code/cli.js"),
             "trae_cli": ("traecli", ""),
             "lark_cli": ("lark-cli", "@larksuite/cli/bin/lark-cli.exe")}
    if provider not in names:
        return None
    name, entry = names[provider]
    configured = os.getenv("VIDEOAGENTS_" + name.upper().replace("-", "_") + "_EXECUTABLE")
    found = configured or shutil.which(name)
    if not found and os.name == "nt" and name in {"claude", "traecli"}:
        candidate = Path.home() / ".local" / "bin" / (name + ".exe")
        found = str(candidate) if candidate.is_file() else None
    if not found and os.name == "nt" and name == "claude":
        packages = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
        found = next((str(path) for path in packages.glob("Anthropic.ClaudeCode_*/claude.exe")
                      if path.is_file()), None)
    if not found:
        return None
    path = Path(found).resolve()
    if not path.is_file():
        return None
    if os.name != "nt" or path.suffix.lower() == ".exe":
        return [str(path)]
    script = path if path.suffix.lower() in {".js", ".mjs"} else path.parent / "node_modules" / entry
    if entry and script.is_file():
        if script.suffix.lower() == ".exe":
            return [str(script)]
        node = shutil.which("node")
        if node:
            return [node, str(script)]
    return None


def cli_availability() -> dict[str, dict[str, bool]]:
    return {provider: {"available": executable_prefix(provider) is not None}
            for provider in ("codex_cli", "trae_cli", "claude_code_cli")}


def build_arguments(provider: str, prefix: list[str], model: str, directory: Path, schema: Path, *,
                    research: bool = False, mcp_config: Path | None = None,
                    glm_reasoning_effort: str = DEFAULT_GLM_REASONING_EFFORT,
                    codex_reasoning_effort: str | None = None) -> list[str]:
    if provider == "codex_cli":
        args = [*prefix, "-a", "never", "exec"]
        if research:
            # 忽略用户配置也会忽略 Windows 沙盒级别；未显式开启时，
            # Codex 会将 workspace-write 降为 read-only，研究文件无法落盘。
            args.extend(["--sandbox", "workspace-write",
                "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules", "--json",
                "--color", "never", "--cd", str(directory), "--output-schema", str(schema),
                "-c", 'windows.sandbox="unelevated"',
                "-c", "sandbox_workspace_write.network_access=true",
                "-c", 'web_search="live"',
            ])
        else:
            args.extend(["--sandbox", "read-only", "--ephemeral",
                "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules", "--json",
                "--color", "never", "--cd", str(directory), "--output-schema", str(schema),
                "-c", 'web_search="disabled"'])
        for feature in CODEX_RESEARCH_DISABLED if research else CODEX_DISABLED:
            args.extend(["--disable", feature])
        if model:
            args.extend(["--model", model])
        if codex_reasoning_effort is not None:
            if codex_reasoning_effort not in {"none", "minimal", "low", "medium", "high", "xhigh", "max"}:
                raise CliFailure("invalid_codex_reasoning_effort", submitted=False)
            args.extend(["-c", "model_reasoning_effort=" + json.dumps(codex_reasoning_effort)])
        return [*args, "-"]
    if provider == "trae_cli":
        state = directory / ".trae-state"
        logs = directory / ".trae-logs"
        args = [*prefix, "-a", "never", "exec", "--sandbox", "read-only", "--ephemeral",
                "--skip-git-repo-check", "--ignore-user-config", "--ignore-rules", "--json",
                "--color", "never", "--cd", str(directory), "--output-schema", str(schema),
                "--disallowed-tool", "*",
                "-c", "sqlite_home=" + json.dumps(str(state)),
                "-c", "log_dir=" + json.dumps(str(logs)),
                "-c", "check_for_update_on_startup=false",
                "-c", "analytics.enabled=false",
                "-c", "trae_telemetry.enabled=false",
                "-c", "hooks.state={}",
        ]
        for feature in TRAE_DISABLED:
            args.extend(["--disable", feature])
        if model:
            args.extend(["--model", model])
        return [*args, "-"]
    if provider == "claude_code_cli":
        if research and mcp_config is None:
            raise CliFailure("missing_research_tool_config", submitted=False)
        args = [*prefix, "--print", "--output-format", "stream-json" if research else "json", "--json-schema",
                schema.read_text(encoding="utf-8"), "--tools", "",
                "--strict-mcp-config", "--mcp-config", str(mcp_config) if research else '{"mcpServers":{}}',
                "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
                "--disable-slash-commands", "--no-session-persistence", "--permission-mode", "dontAsk"]
        if research:
            args.extend(["--verbose", "--allowedTools", *sorted(CLAUDE_RESEARCH_TOOLS)])
        else:
            args.extend(["--disallowedTools", "mcp__*"])
        if model:
            args.extend(["--model", model])
        if model.lower().removesuffix("[1m]") == "glm-5.3":
            if glm_reasoning_effort not in {"xhigh", "max"}:
                raise CliFailure("invalid_glm_reasoning_effort", submitted=False)
            args.extend(["--effort", glm_reasoning_effort])
        return args
    raise CliFailure("unsupported_cli", submitted=False)


def _research_environment(research: bool) -> dict[str, str]:
    # 每个角色是独立 CLI 会话，不能继承桌面父会话的身份、管道与权限档案。
    # 登录、代理等普通 CLI 环境保持不变；研究模式再补充工具所需的 PATH。
    env = os.environ.copy()
    for name in CODEX_MANAGED_CONTEXT_ENV | TRAE_MANAGED_CONTEXT_ENV:
        env.pop(name, None)
    if not research:
        return env
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    local_bin = Path.home() / ".local" / "bin"
    if not local_bin.is_dir():
        return env
    current = env.get("PATH", "")
    entries = [item for item in current.split(os.pathsep) if item]
    if str(local_bin) not in entries:
        env["PATH"] = str(local_bin) + (os.pathsep + current if current else "")
    return env


def _cli_environment(provider: str, research: bool, control: Path,
                     ark_api_key: str | None = None, zhipu_api_key: str | None = None,
                     model: str = "", glm_reasoning_effort: str = DEFAULT_GLM_REASONING_EFFORT,
                     ) -> tuple[dict[str, str], Path | None]:
    env = _research_environment(research)
    if provider == "claude_code_cli":
        env.update(CLAUDE_RETRY_ENV)
        env.pop("CLAUDE_CODE_RETRY_WATCHDOG", None)
    if provider == "claude_code_cli" and (ark_api_key or zhipu_api_key):
        # Pass the credential only to this child process, never in arguments or graph state.
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("CLAUDE_CODE_OAUTH_TOKEN", None)
        for name in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
            env.pop(name, None)
        if zhipu_api_key:
            if model.lower().removesuffix("[1m]") != "glm-5.3" or ark_api_key:
                raise CliFailure("invalid_zhipu_model_route", submitted=False)
            env["ANTHROPIC_AUTH_TOKEN"] = zhipu_api_key
            env["ANTHROPIC_BASE_URL"] = os.getenv("VIDEOAGENTS_ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/anthropic")
            env.pop("CLAUDE_CODE_DISABLE_1M_CONTEXT", None)
            env["ANTHROPIC_MODEL"] = GLM_MODEL
            env["CLAUDE_CODE_SUBAGENT_MODEL"] = GLM_MODEL
            env["CLAUDE_CODE_EFFORT_LEVEL"] = glm_reasoning_effort
            env["CLAUDE_CODE_MAX_CONTEXT_TOKENS"] = str(GLM_CONTEXT_TOKENS)
            env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(GLM_CONTEXT_TOKENS)
            env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
            for family in ("OPUS", "SONNET", "HAIKU", "FABLE"):
                name = f"ANTHROPIC_DEFAULT_{family}_MODEL"
                env[name] = GLM_MODEL
                env[name + "_SUPPORTED_CAPABILITIES"] = GLM_CAPABILITIES
            env["ANTHROPIC_CUSTOM_MODEL_OPTION"] = GLM_MODEL
            env["ANTHROPIC_CUSTOM_MODEL_OPTION_SUPPORTED_CAPABILITIES"] = GLM_CAPABILITIES
        else:
            env["ANTHROPIC_AUTH_TOKEN"] = ark_api_key
            env["ANTHROPIC_BASE_URL"] = "https://ark.cn-beijing.volces.com/api/compatible"
    if provider not in {"codex_cli", "trae_cli"}:
        return env, None
    if provider == "codex_cli":
        source_home = Path(env.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
        source_auth = source_home / "auth.json"
        isolated_home = control / "codex-home"
        auth_directory = isolated_home
    else:
        source_home = Path(env.get("TRAE_HOME") or Path.home() / ".trae").expanduser()
        source_auth = source_home / "cli" / "auth.json"
        isolated_home = control / "trae-home"
        auth_directory = isolated_home / "cli"
    auth_directory.mkdir(parents=True)
    if os.name != "nt":
        os.chmod(isolated_home, 0o700)
        os.chmod(auth_directory, 0o700)
    staged_auth = None
    if source_auth.is_file():
        size = source_auth.stat().st_size
        if not 0 < size <= MAX_AUTH_BYTES:
            raise CliFailure("cli_auth_file_invalid", submitted=False)
        staged_auth = auth_directory / "auth.json"
        shutil.copyfile(source_auth, staged_auth)
        if os.name != "nt":
            os.chmod(staged_auth, 0o600)
    if provider == "codex_cli":
        sqlite_home = isolated_home / "sqlite"
        sqlite_home.mkdir()
        if os.name != "nt":
            os.chmod(sqlite_home, 0o700)
        env["CODEX_HOME"] = str(isolated_home)
        env["CODEX_SQLITE_HOME"] = str(sqlite_home)
    else:
        env["TRAE_HOME"] = str(isolated_home)
    return env, staged_auth


def _audit_summary(event: dict[str, Any]) -> dict[str, Any] | None:
    kind = event.get("type")
    item = event.get("item") if isinstance(event.get("item"), dict) else {}
    item_type = item.get("type")
    if kind in {"item.started", "item.updated", "item.completed"} and item_type in CODEX_RESEARCH_TOOLS:
        result: dict[str, Any] = {"type": kind, "item_type": item_type}
        for key in ("status", "exit_code", "tool_name"):
            if key in item and isinstance(item[key], str | int | float | bool | None):
                result[key] = item[key]
        return result
    if kind in {"turn.completed", "turn.failed"}:
        return {"type": kind, "status": event.get("status")}
    return None


def _write_audit_record(handle, summary: dict[str, Any] | None) -> None:
    if handle is not None and summary is not None:
        handle.write(json.dumps(summary, ensure_ascii=False) + "\n")


def _write_audit(handle, event: dict[str, Any]) -> None:
    _write_audit_record(handle, _audit_summary(event))


def _codex_event(line: str, *, research: bool = False, audit_handle=None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    event = json.loads(line)
    if not isinstance(event, dict):
        raise CliFailure("invalid_cli_event")
    _write_audit(audit_handle, event)
    kind = event.get("type")
    if kind in {"item.started", "item.updated", "item.completed"}:
        item = event.get("item", {})
        # Error items carry CLI configuration/deprecation/reroute notices;
        # todo lists are local planning metadata. Neither executes a tool.
        allowed = {
            "reasoning", "agent_message", "error", "todo_list", "model_reroute",
        } | (CODEX_RESEARCH_TOOLS if research else set())
        if not isinstance(item, dict) or item.get("type") not in allowed:
            raise CliFailure("unexpected_tool_event")
        if kind == "item.completed" and item.get("type") == "agent_message":
            return {"__raw_agent_message__": item.get("text", "")}, None
    elif kind == "turn.completed":
        return None, event.get("usage")
    elif kind == "turn.failed":
        raise CliFailure("cli_reported_error")
    # Top-level errors can be recoverable server notifications. Discard their
    # text; run_cli still requires structured output, turn completion and exit 0.
    elif kind not in {"thread.started", "turn.started", "error"}:
        raise CliFailure("unexpected_cli_event")
    return None, None


def _business_object(envelope: Any) -> dict[str, Any]:
    # TRAE can apply WIRE_SCHEMA after the model already emitted the requested
    # envelope, producing one additional response_json layer. Unwrap at most
    # two transport layers and keep rejecting arbitrary or recursively nested
    # output before it reaches the business contract validator.
    for _ in range(2):
        if not isinstance(envelope, dict) or set(envelope) != {"response_json"} or not isinstance(envelope["response_json"], str):
            raise CliFailure("missing_structured_output")
        if len(envelope["response_json"].encode("utf-8")) > MAX_OUTPUT_BYTES:
            raise CliFailure("cli_output_limit")
        result = json.loads(envelope["response_json"])
        if not isinstance(result, dict):
            raise CliFailure("non_object_output")
        if set(result) != {"response_json"} or not isinstance(result["response_json"], str):
            return result
        envelope = result
    raise CliFailure("nested_structured_output_limit")


def normalize_business_result(result: Any) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise CliFailure("non_object_output")
    if set(result) == {"response_json"} and isinstance(result["response_json"], str):
        return _business_object(result)
    return result


def _claude_result(output: str) -> CliResult:
    value = json.loads(output)
    if not isinstance(value, dict) or value.get("type") != "result":
        raise CliFailure("invalid_cli_result")
    if value.get("is_error") or value.get("subtype") != "success":
        # CLI errors can happen after billing. They never prove nonacceptance.
        raise CliFailure("cli_reported_error")
    return CliResult(_business_object(value.get("structured_output")), value.get("usage"))


def _reported_failure_details(messages: Any, source: str) -> dict[str, Any]:
    """Recognize bounded error headers; retain codes only, never error prose."""
    if not isinstance(messages, list):
        return {}
    for message in reversed(messages[-16:]):
        if not isinstance(message, str) or len(message) > MAX_STDERR_TAIL_BYTES:
            continue
        message = message.strip()
        match = re.fullmatch(r"API Error: ([45][0-9]{2})(?:\s+(.*))?", message, re.DOTALL)
        if match and int(match[1]) in HTTP_FAILURE_HINTS:
            details = {"reported_http_status": int(match[1]), "reported_error_kind": "http_error",
                       "error_detail_source": source}
            try:
                body = json.loads(match[2] or "")
            except (ValueError, RecursionError):
                pass
            else:
                error = body.get("error") if isinstance(body, dict) and body.get("type") == "error" else None
                kind = error.get("type") if isinstance(error, dict) else None
                if isinstance(kind, str) and kind in API_ERROR_TYPES:
                    details["reported_error_kind"] = kind
            return details
        kind = TRANSPORT_FAILURE_MESSAGES.get(message.removeprefix("API Error: ").removeprefix("Error: "))
        if kind:
            return {"reported_error_kind": kind, "error_detail_source": source}
    return {}


def _failure_diagnostic(reason_code: str, provider: str, output: list[str], stdout_bytes: int,
                        exit_code: int | None, stderr_tail_bytes: int,
                        stderr_tail: list[bytes] | None = None) -> str:
    """Project a failed process into fixed diagnostics, never its response text."""
    shape, subtype, response_shape = "empty", "unknown", "absent"
    reported_details, terminal_details = {}, {}
    if provider == "claude_code_cli" and output:
        try:
            value = json.loads("\n".join(output))
        except (TypeError, ValueError, RecursionError):
            shape = "invalid_json"
        else:
            if isinstance(value, dict) and value.get("type") == "result":
                shape = ("claude_success_result" if value.get("subtype") == "success"
                         and value.get("is_error") is False else "claude_error_result")
                candidate = value.get("subtype")
                if isinstance(candidate, str) and candidate in CLAUDE_FAILURE_HINTS:
                    subtype = candidate
                if value.get("is_error") is True:
                    terminal = value.get("terminal_reason")
                    if isinstance(terminal, str) and terminal in CLAUDE_TERMINAL_HINTS:
                        terminal_details = {"reported_terminal_reason": terminal}
                    errors = value.get("errors")
                    reported_details = _reported_failure_details(
                        [errors] if isinstance(errors, str) else errors, "claude_result_errors")
                    if not reported_details:
                        reported_details = _reported_failure_details([value.get("result")], "claude_result_error_text")
                    status = value.get("api_error_status")
                    if type(status) is int and status in HTTP_FAILURE_HINTS:
                        kind = (reported_details.get("reported_error_kind", "http_error")
                                if reported_details.get("reported_http_status") == status else "http_error")
                        reported_details = {"reported_http_status": status, "reported_error_kind": kind,
                                            "error_detail_source": "claude_result_api_error_status"}
                structured = value.get("structured_output")
                if isinstance(structured, dict):
                    inner = structured.get("response_json")
                    if isinstance(inner, str):
                        try:
                            response_shape = "json_object" if isinstance(json.loads(inner), dict) else "json_other"
                        except (ValueError, RecursionError):
                            response_shape = "invalid_json"
            else:
                shape = "other_json"
    elif stdout_bytes:
        shape = "event_stream"
    if not reported_details and provider == "claude_code_cli" and stderr_tail:
        stderr_lines = b"".join(stderr_tail)[-MAX_STDERR_TAIL_BYTES:].decode("utf-8", errors="replace").splitlines()
        reported_details = _reported_failure_details(stderr_lines, "stderr")
    return reason_code + "; " + json.dumps({
        "exit_code": exit_code, "stdout_bytes": stdout_bytes,
        "stdout_shape": shape, "subtype": subtype,
        "response_json_shape": response_shape, "stderr_tail_bytes": stderr_tail_bytes,
        **reported_details, **terminal_details,
    }, sort_keys=True)


def _cli_identifier(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value) is not None


def _claude_metadata_summary(event: dict[str, Any]) -> dict[str, Any]:
    """Validate known SDK metadata; never persist auth output or free text."""
    kind = event["type"]
    event_id = event.get("uuid")
    try:
        valid_uuid = isinstance(event_id, str) and str(UUID(event_id)) == event_id.lower()
    except ValueError:
        valid_uuid = False
    if not valid_uuid or not _cli_identifier(event.get("session_id")):
        raise CliFailure("invalid_cli_event")
    summary = {"type": kind, "event_id": event_id}
    if kind == "tool_progress":
        name, elapsed = event.get("tool_name"), event.get("elapsed_time_seconds")
        if not isinstance(name, str):
            raise CliFailure("invalid_cli_event")
        if name not in CLAUDE_RESEARCH_TOOLS | {"StructuredOutput"}:
            raise CliFailure("unexpected_tool_event")
        if (not _cli_identifier(event.get("tool_use_id"))
                or "parent_tool_use_id" not in event
                or (event["parent_tool_use_id"] is not None and not _cli_identifier(event["parent_tool_use_id"]))
                or type(elapsed) not in {int, float} or elapsed < 0
                or (isinstance(elapsed, float) and not math.isfinite(elapsed))
                or ("task_id" in event and not _cli_identifier(event["task_id"]))
                or ("heartbeat" in event and not isinstance(event["heartbeat"], bool))
                or ("subagent_type" in event and not isinstance(event["subagent_type"], str))):
            raise CliFailure("invalid_cli_event")
        if "subagent_retry" in event:
            retry = event["subagent_retry"]
            if (not isinstance(retry, dict) or not _cli_identifier(retry.get("agent_id"))
                    or any(type(retry.get(key)) is not int or retry[key] < 0
                           for key in ("attempt", "max_retries", "retry_delay_ms"))
                    or "error_status" not in retry
                    or (retry["error_status"] is not None and type(retry["error_status"]) is not int)
                    or not isinstance(retry.get("error_category"), str)):
                raise CliFailure("invalid_cli_event")
        return {**summary, "status": "in_progress", "tool_name": name, "tool_use_id": event["tool_use_id"]}
    if kind == "tool_use_summary":
        ids = event.get("preceding_tool_use_ids")
        if (not isinstance(event.get("summary"), str) or not isinstance(ids, list)
                or not all(_cli_identifier(value) for value in ids)
                or ("timestamp" in event and not isinstance(event["timestamp"], str))):
            raise CliFailure("invalid_cli_event")
        return {**summary, "status": "reported"}
    if (not isinstance(event.get("isAuthenticating"), bool) or not isinstance(event.get("output"), list)
            or not all(isinstance(value, str) for value in event["output"])
            or ("error" in event and not isinstance(event["error"], str))):
        raise CliFailure("invalid_cli_event")
    status = "failed" if event.get("error") else "authenticating" if event["isAuthenticating"] else "idle"
    return {**summary, "status": status}


def _claude_event_rejected(audit_handle, kind: Any) -> None:
    # Preserve a bounded discriminator for future diagnosis, never the event
    # body, auth text, summary, source content, or arbitrary error message.
    event_type = kind if isinstance(kind, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", kind) else "invalid"
    _write_audit_record(audit_handle, {"type": "cli.event.rejected", "event_type": event_type, "status": "rejected"})


def _claude_research_event(line: str, audit_handle=None) -> CliResult | None:
    event = json.loads(line)
    if not isinstance(event, dict):
        raise CliFailure("invalid_cli_event")
    kind = event.get("type")
    if not isinstance(kind, str):
        _claude_event_rejected(audit_handle, kind)
        raise CliFailure("invalid_cli_event")
    if kind == "result":
        result = _claude_result(line)
        _write_audit(audit_handle, {"type": "turn.completed", "status": "completed"})
        return result
    if kind in CLAUDE_RESEARCH_METADATA:
        try:
            summary = _claude_metadata_summary(event)
        except CliFailure:
            _claude_event_rejected(audit_handle, kind)
            raise
        _write_audit_record(audit_handle, summary)
        return None
    if kind == "assistant":
        message = event.get("message", {})
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            raise CliFailure("invalid_cli_event")
        for block in message["content"]:
            if not isinstance(block, dict):
                raise CliFailure("invalid_cli_event")
            if block.get("type") == "tool_use":
                name = block.get("name")
                if name not in CLAUDE_RESEARCH_TOOLS | {"StructuredOutput"}:
                    raise CliFailure("unexpected_tool_event")
                if name != "StructuredOutput":
                    _write_audit(audit_handle, {"type": "item.started", "item": {
                        "type": "mcp_tool_call", "status": "in_progress", "tool_name": name,
                    }})
    elif kind == "user":
        message = event.get("message", {})
        if not isinstance(message, dict) or not isinstance(message.get("content"), list):
            raise CliFailure("invalid_cli_event")
        for block in message["content"]:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                _write_audit(audit_handle, {"type": "item.completed", "item": {
                    "type": "mcp_tool_call", "status": "failed" if block.get("is_error") else "completed",
                }})
    elif kind not in {"system", "rate_limit_event"}:
        _claude_event_rejected(audit_handle, kind)
        raise CliFailure("unexpected_cli_event")
    return None


def _cleanup_cli_resource(cleanup: Callable[[], Any], phase: str, *, attempts: int = 1) -> None:
    """A cleanup lock must not overwrite the submitted call's result or failure."""
    for attempt in range(attempts):
        try:
            cleanup()
            return
        except PermissionError:
            if attempt + 1 < attempts:
                time.sleep(0.05)
                continue
        except (OSError, subprocess.TimeoutExpired):
            pass
        break
    # Known phase labels only: no exception text, credential or temporary path.
    _LOGGER.warning("CLI cleanup incomplete (%s)", phase)


@contextmanager
def _cli_control_directory(parent: Path | None) -> Iterator[str]:
    directory = tempfile.TemporaryDirectory(prefix=".videoagents-cli-", dir=parent)
    try:
        yield directory.name
    finally:
        control = Path(directory.name)
        # Remove credentials separately even if a Windows SQLite/descendant lock
        # prevents deleting the rest of the isolated home.
        for auth in (control / "codex-home" / "auth.json", control / "trae-home" / "cli" / "auth.json"):
            _cleanup_cli_resource(lambda: auth.unlink(missing_ok=True), "staged_auth", attempts=3)
        _cleanup_cli_resource(directory.cleanup, "control_directory", attempts=3)


def run_cli(provider: str, model: str, timeout: int, prompt: str, output_schema: dict[str, Any],
            cancelled=lambda: False, *, research_directory: Path | None = None,
            audit_path: Path | None = None, ark_api_key: str | None = None,
            zhipu_api_key: str | None = None, research_context: dict[str, Any] | None = None,
            glm_reasoning_effort: str = DEFAULT_GLM_REASONING_EFFORT,
            codex_reasoning_effort: str | None = None, research_role: str = "materials") -> CliResult:
    if cancelled():
        raise CliFailure("cli_cancelled", submitted=False)
    research = research_directory is not None
    if research and provider not in {"codex_cli", "claude_code_cli"}:
        raise CliFailure("unsupported_research_cli", submitted=False)
    if research and research_role not in {"materials", "screenwriter"}:
        raise CliFailure("unsupported_research_role", submitted=False)
    if research and provider == "claude_code_cli" and not research_context:
        raise CliFailure("missing_research_tool_config", submitted=False)
    prefix = executable_prefix(provider)
    if prefix is None:
        raise CliFailure("cli_not_installed", submitted=False)
    if research:
        research_directory.mkdir(parents=True, exist_ok=True)
    # Codex refuses to create its Linux sandbox helper aliases when CODEX_HOME
    # lives below the system temporary directory. Research mode needs those
    # helpers for command_execution, so keep the isolated control directory
    # next to the durable job revision instead of under /tmp. The randomized
    # directory is still outside the model-writable research workspace. Cleanup
    # runs after the call without changing its accepted result or failure reason.
    control_parent = research_directory.parent if research_directory is not None else None
    with _cli_control_directory(control_parent) as temporary:
        control = Path(temporary)
        directory = research_directory if research else control
        schema = control / "output-schema.json"
        schema.write_text(json.dumps(WIRE_SCHEMA, ensure_ascii=False), encoding="utf-8")
        source = control / "input.txt"
        prefix_text = ""
        research_task = ("这是编剧节点的证据研究任务。" if research_role == "screenwriter" else
                         "这是素材节点的工具研究任务。")
        research_goal = ("按用户配置的平台与预算读取并核验来源正文，为本角色写作提供证据；不采集画面。"
                         if research_role == "screenwriter" else
                         "按用户配置的平台与预算收集可核验来源、图片或截图线索并采集画面。")
        if research and provider == "codex_cli":
            prefix_text = (
                research_task + "你可以使用已安装的研究 skill、web_search、shell 命令和工作区文件，"
                "但只在当前工作目录写入研究过程文件；不要读取密钥，不要把工具日志放进最终 JSON。"
                "优先使用 agent-reach 等检索 skill。" + research_goal + "\n"
            )
        elif research:
            prefix_text = (
                research_task + "只使用本次启用的 videoagents_research MCP 工具。"
                + research_goal + "不要把工具日志放进最终 JSON。\n"
            )
        transport_prompt = (prefix_text + prompt + "\n业务 JSON schema：\n" + json.dumps(output_schema, ensure_ascii=False)
                            + '\n最终传输格式必须为 {"response_json":"业务 JSON 对象序列化后的字符串"}。'
                            + "response_json 内的对象遵循上面的业务 schema，外层仅有 response_json 一个字段。")
        source.write_text(transport_prompt, encoding="utf-8")
        mcp_config = None
        if research and provider == "claude_code_cli":
            mcp_config = control / "research-mcp.json"
            server_args = [
                "-m", "videoagents.tools.claude_research", "--workspace", str(directory),
                "--runtime", str(research_context["runtime"]), "--job-id", research_context["job_id"],
                "--revision", str(research_context["revision"]),
            ]
            if research_context.get("tools"):
                server_args.extend(["--tools", ",".join(research_context["tools"])])
            research_server = {"command": sys.executable, "args": server_args,
                "env": {"PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                       "ANTHROPIC_AUTH_TOKEN": "", "ANTHROPIC_API_KEY": "", "CLAUDE_CODE_OAUTH_TOKEN": ""}}
            mcp_config.write_text(json.dumps({"mcpServers": {"videoagents_research": research_server}}), encoding="utf-8")
            transport_prompt += ("\n本次只使用启用的 videoagents_research MCP 工具。" + research_goal +
                                 "工具会保存文件并返回真实路径及 SHA256；不使用 shell 或读取本机任意路径。")
            source.write_text(transport_prompt, encoding="utf-8")
        args = build_arguments(provider, prefix, model, directory, schema, research=research, mcp_config=mcp_config,
                               glm_reasoning_effort=glm_reasoning_effort,
                               codex_reasoning_effort=codex_reasoning_effort)
        environment, staged_auth = _cli_environment(provider, research, control, ark_api_key, zhipu_api_key, model,
                                                    glm_reasoning_effort)
        job = WindowsJob()
        audit_handle = None
        try:
            if audit_path is not None:
                audit_path.parent.mkdir(parents=True, exist_ok=True)
                audit_handle = audit_path.open("w", encoding="utf-8")
            with source.open("rb") as stream:
                try:
                    if cancelled():
                        raise CliFailure("cli_cancelled", submitted=False)
                    process = subprocess.Popen(args, cwd=directory, stdin=stream, stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, shell=False,
                                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                               start_new_session=os.name != "nt",
                                               env=environment)
                except OSError as exc:
                    raise CliFailure("cli_launch_failed", submitted=False) from exc
        except BaseException:
            if audit_handle is not None:
                _cleanup_cli_resource(audit_handle.close, "audit")
            _cleanup_cli_resource(job.close, "job")
            raise
        # At most four raw events await projection, rather than retaining an
        # entire research transcript or up to 64 maximum-sized events.
        lines: queue.Queue = queue.Queue(maxsize=4)
        stopped = threading.Event()
        stderr_tail: list[bytes] = []
        def enqueue(line):
            while not stopped.is_set():
                try:
                    lines.put(line, timeout=0.1)
                    return
                except queue.Full:
                    continue
        def read():
            try:
                while not stopped.is_set() and (line := process.stdout.readline(MAX_EVENT_BYTES + 1)):
                    enqueue(line)
            finally:
                enqueue(None)
        def read_stderr():
            # Keep only the last few KB: enough to diagnose a crash or rate
            # limit, never enough to echo back fetched page content.
            try:
                while not stopped.is_set() and (chunk := process.stderr.readline(MAX_OUTPUT_BYTES + 1)):
                    stderr_tail.append(chunk)
                    if sum(len(item) for item in stderr_tail) > MAX_STDERR_TAIL_BYTES:
                        del stderr_tail[:len(stderr_tail) // 2]
            except (OSError, ValueError):
                pass
        def stderr_note() -> str:
            tail_bytes = sum(len(chunk) for chunk in stderr_tail)
            return f"; stderr_tail_bytes={tail_bytes}" if tail_bytes else ""
        reader = threading.Thread(target=read, daemon=True)
        stderr_reader = threading.Thread(target=read_stderr, daemon=True)
        data, usage, output, size, completed, last_agent_message, exit_code = None, None, [], 0, False, None, None
        stream_limit = MAX_RESEARCH_STREAM_BYTES if research else MAX_OUTPUT_BYTES
        try:
            job.assign(process)
            reader.start()
            stderr_reader.start()
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
                if len(line) > MAX_EVENT_BYTES or size > stream_limit:
                    raise CliFailure("cli_output_limit")
                decoded = line.decode("utf-8", errors="strict").strip()
                if not decoded:
                    continue
                if provider in {"codex_cli", "trae_cli"}:
                    event_kind = json.loads(decoded).get("type")
                    if provider == "codex_cli" and event_kind == "thread.started" and staged_auth is not None:
                        staged_auth.unlink(missing_ok=True)
                    item, counts = _codex_event(decoded, research=research, audit_handle=audit_handle)
                    if isinstance(item, dict) and "__raw_agent_message__" in item:
                        last_agent_message = item["__raw_agent_message__"]
                    else:
                        data = item if item is not None else data
                    usage = counts if counts is not None else usage
                    completed |= event_kind == "turn.completed"
                elif research:
                    result = _claude_research_event(decoded, audit_handle)
                    if result is not None:
                        if completed:
                            raise CliFailure("duplicate_cli_result")
                        data, usage, completed = result.data, result.usage, True
                else:
                    output.append(decoded)
            remaining = max(0.01, deadline - time.monotonic())
            try:
                exit_code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired as exc:
                # EOF right at the deadline is still a timeout, not bad output.
                raise CliFailure("cli_timeout") from exc
            if exit_code != 0:
                stderr_reader.join(timeout=1)
                raise CliFailure(_failure_diagnostic(
                    "cli_nonzero_exit", provider, output, size, exit_code,
                    sum(len(chunk) for chunk in stderr_tail), stderr_tail))
            if provider == "claude_code_cli" and not research:
                return _claude_result("\n".join(output))
            if last_agent_message is not None:
                data = _business_object(json.loads(last_agent_message))
            if not completed or data is None:
                raise CliFailure("incomplete_cli_result" + stderr_note())
            return CliResult(data, usage)
        except CliFailure as exc:
            if exc.reason == "cli_reported_error" and provider == "claude_code_cli" and not research:
                stderr_reader.join(timeout=1)
                exc.reason = _failure_diagnostic(
                    exc.reason, provider, output, size, exit_code,
                    sum(len(chunk) for chunk in stderr_tail), stderr_tail)
                exc.args = (exc.reason,)
            if not exc.rejected and exc.submitted:
                # Attach the captured tail for the operation ledger; the reason
                # code alone cannot distinguish a crash from a rate limit.
                note = stderr_note()
                if note and "stderr" not in str(exc):
                    exc.args = (str(exc) + note,)
            raise
        except Exception:
            if exit_code is not None:
                stderr_reader.join(timeout=1)
            raise CliFailure(_failure_diagnostic(
                "invalid_cli_output", provider, output, size, exit_code,
                sum(len(chunk) for chunk in stderr_tail), stderr_tail)) from None
        finally:
            stopped.set()
            _cleanup_cli_resource(lambda: terminate_tree(process), "process_tree")
            _cleanup_cli_resource(job.close, "job")
            _cleanup_cli_resource(lambda: process.wait(timeout=1), "process_wait")
            if reader.ident:
                _cleanup_cli_resource(lambda: reader.join(timeout=1), "stdout_reader")
            if stderr_reader.ident:
                _cleanup_cli_resource(lambda: stderr_reader.join(timeout=1), "stderr_reader")
            _cleanup_cli_resource(process.stdout.close, "stdout")
            _cleanup_cli_resource(process.stderr.close, "stderr")
            if audit_handle is not None:
                _cleanup_cli_resource(audit_handle.close, "audit")
