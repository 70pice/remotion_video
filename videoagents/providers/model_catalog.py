"""Query the active Codex CLI's catalog without starting a generation session.

Fall back to the shared cache when the catalog command is unavailable. Another
client can overwrite that cache. Model names remain unrestricted in settings.
"""

import json
import os
import subprocess
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from videoagents.contracts import ModelCatalog, ModelChoice
from videoagents.contracts.models import ModelProvider
from videoagents.providers.cli_runner import executable_prefix

MAX_CACHE_BYTES = 4 * 1024 * 1024


def _model_choices(value: object) -> list[ModelChoice]:
    if not isinstance(value, dict) or not isinstance(value.get("models"), list):
        raise ValueError("invalid_model_cache")
    if len(value["models"]) > 2000:
        raise ValueError("model_cache_too_many_entries")
    choices, seen = [], set()
    for entry in value["models"]:
        if not isinstance(entry, dict):
            raise ValueError("invalid_model_cache_entry")
        # ModelInfo's executable identifier is slug, not a display name or alias.
        choice = ModelChoice(
            id=entry.get("slug"), display_name=entry.get("display_name"),
            description="" if entry.get("description") is None else entry["description"],
            hidden=entry.get("visibility") != "list",
            is_default=entry.get("is_default", False),
        )
        if not choice.id.strip():
            raise ValueError("invalid_model_cache_entry")
        if choice.id not in seen:
            choices.append(choice)
            seen.add(choice.id)
    return choices


def read_codex_models(cache_path: Path) -> tuple[list[ModelChoice], str]:
    with cache_path.open("rb") as stream:
        data = stream.read(MAX_CACHE_BYTES + 1)
    if len(data) > MAX_CACHE_BYTES:
        raise ValueError("model_cache_too_large")
    value = json.loads(data)
    choices = _model_choices(value)
    fetched_at = value.get("fetched_at")
    if not isinstance(fetched_at, str) or len(fetched_at) > 100:
        raise ValueError("invalid_model_cache_time")
    if datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).utcoffset() != timedelta(0):
        raise ValueError("invalid_model_cache_time")
    return choices, fetched_at


def read_cli_models(prefix: list[str]) -> tuple[list[ModelChoice], str]:
    # 与角色调用使用同一个可执行入口，避免 App/旧 CLI 覆盖共享缓存后丢失新模型。
    # debug models 只查询目录，不执行 exec、不创建对话、不发起模型生成。
    result = subprocess.run(
        [*prefix, "debug", "models"], capture_output=True, check=True, timeout=12,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if len(result.stdout) > MAX_CACHE_BYTES:
        raise ValueError("model_catalog_too_large")
    choices = _model_choices(json.loads(result.stdout))
    return choices, datetime.now(UTC).isoformat().replace("+00:00", "Z")


def read_trae_models(prefix: list[str]) -> tuple[list[ModelChoice], str]:
    result = subprocess.run(
        [*prefix, "models", "--json", "-c", "hooks.state={}"],
        capture_output=True, check=True, timeout=12,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if len(result.stdout) > MAX_CACHE_BYTES:
        raise ValueError("model_catalog_too_large")
    value = json.loads(result.stdout)
    if not isinstance(value, list) or len(value) > 2000:
        raise ValueError("invalid_trae_model_catalog")
    choices, seen = [], set()
    for entry in value:
        if not isinstance(entry, dict):
            raise ValueError("invalid_trae_model_entry")
        identifier = entry.get("name")
        display_name = entry.get("real_name") or identifier
        description = "" if entry.get("description") is None else entry.get("description")
        if not isinstance(identifier, str) or not isinstance(display_name, str) or not isinstance(description, str):
            raise ValueError("invalid_trae_model_entry")
        choice = ModelChoice(
            id=identifier, display_name=display_name, description=description,
            hidden=False, is_default=False,
        )
        if choice.id not in seen:
            choices.append(choice)
            seen.add(choice.id)
    return choices, datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ModelCatalogService:
    def __init__(self, *, cache_seconds: float = 60):
        self.cache_seconds = cache_seconds
        self._cached: dict[tuple, tuple[float, ModelCatalog]] = {}
        self._lock = threading.Lock()

    def get(self, provider: ModelProvider, refresh: bool = False) -> ModelCatalog:
        if provider == "claude_code_cli":
            return ModelCatalog(provider=provider, status="unavailable", message="Claude Code CLI 请直接填写模型名称。", fetched_at="")
        prefix = executable_prefix(provider)
        if not prefix:
            label = "TRAE CLI" if provider == "trae_cli" else "Codex CLI"
            return ModelCatalog(provider=provider, status="unavailable", message=f"未检测到 {label}；仍可填写自定义模型名称。", fetched_at="")
        if provider == "trae_cli":
            key = (provider, tuple(prefix))
            with self._lock:
                now = time.monotonic()
                cached = self._cached.get(key)
                if not refresh and cached and now - cached[0] < self.cache_seconds:
                    return cached[1].model_copy(deep=True)
                try:
                    choices, fetched_at = read_trae_models(prefix)
                    result = ModelCatalog(
                        provider=provider, status="ready", models=choices, fetched_at=fetched_at,
                        message="已通过项目实际使用的 TRAE CLI 查询模型列表。列表不代表当前账号一定可调用，实际支持以模型调用为准。",
                    )
                except (OSError, ValueError, UnicodeError, RecursionError, subprocess.SubprocessError):
                    result = ModelCatalog(
                        provider=provider, status="unavailable", fetched_at="",
                        message="TRAE CLI 模型目录暂时无法读取；可直接填写 CLI 支持的模型名称，稍后刷新列表。",
                    )
                self._cached[key] = (time.monotonic(), result)
                return result.model_copy(deep=True)
        directory = Path(os.getenv("CODEX_HOME") or str(Path.home() / ".codex")).expanduser()
        key = (provider, str(directory.resolve()), tuple(prefix))
        with self._lock:
            now = time.monotonic()
            cached = self._cached.get(key)
            if not refresh and cached and now - cached[0] < self.cache_seconds:
                return cached[1].model_copy(deep=True)
            try:
                choices, fetched_at = read_cli_models(prefix)
                result = ModelCatalog(
                    provider=provider, status="ready", models=choices, fetched_at=fetched_at,
                    message="已通过项目实际使用的 Codex CLI 查询模型列表，包含 CLI 隐藏模型。列表不代表调用一定成功，实际支持以模型调用为准。",
                )
            except (OSError, ValueError, UnicodeError, RecursionError, subprocess.SubprocessError):
                try:
                    choices, fetched_at = read_codex_models(directory / "models_cache.json")
                    result = ModelCatalog(
                        provider=provider, status="ready", models=choices, fetched_at=fetched_at,
                        message="CLI 模型查询暂时不可用，已回退到本机缓存。缓存可能由其他版本写入；权限和实际支持以 CLI 调用为准，也可填写自定义模型。",
                    )
                except FileNotFoundError:
                    result = ModelCatalog(provider=provider, status="unavailable", fetched_at="",
                                          message="CLI 暂时无法查询模型，且本机暂无模型缓存；可直接填写 CLI 支持的模型名称。")
                except (OSError, ValueError, UnicodeError, RecursionError):
                    # Never return exception text, process output, paths or auth data.
                    result = ModelCatalog(provider=provider, status="error", fetched_at="",
                                          message="CLI 模型列表和本机缓存暂时无法读取；可继续使用自定义模型名称，稍后刷新列表。")
            self._cached[key] = (time.monotonic(), result)
            return result.model_copy(deep=True)
