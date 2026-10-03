"""Read Codex's local model cache without starting a session or reading auth.

The cache can be written by another Codex version and does not prove account
access. Model names remain unrestricted in role settings and CLI argv.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from videoagents.contracts import ModelCatalog, ModelChoice
from videoagents.contracts.models import ModelProvider
from videoagents.providers.cli_runner import executable_prefix

MAX_CACHE_BYTES = 4 * 1024 * 1024


def read_codex_models(cache_path: Path) -> tuple[list[ModelChoice], str]:
    with cache_path.open("rb") as stream:
        data = stream.read(MAX_CACHE_BYTES + 1)
    if len(data) > MAX_CACHE_BYTES:
        raise ValueError("model_cache_too_large")
    value = json.loads(data)
    if not isinstance(value, dict) or not isinstance(value.get("models"), list):
        raise ValueError("invalid_model_cache")
    fetched_at = value.get("fetched_at")
    if not isinstance(fetched_at, str) or len(fetched_at) > 100:
        raise ValueError("invalid_model_cache_time")
    if datetime.fromisoformat(fetched_at.replace("Z", "+00:00")).utcoffset() != timedelta(0):
        raise ValueError("invalid_model_cache_time")
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
    return choices, fetched_at


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
            return ModelCatalog(provider=provider, status="unavailable", message="未检测到 Codex CLI；仍可填写自定义模型名称。", fetched_at="")
        directory = Path(os.getenv("CODEX_HOME") or str(Path.home() / ".codex")).expanduser()
        key = (str(directory.resolve()), tuple(prefix))
        with self._lock:
            now = time.monotonic()
            cached = self._cached.get(key)
            if not refresh and cached and now - cached[0] < self.cache_seconds:
                return cached[1].model_copy(deep=True)
            try:
                choices, fetched_at = read_codex_models(directory / "models_cache.json")
                result = ModelCatalog(
                    provider=provider, status="ready", models=choices, fetched_at=fetched_at,
                    message="已读取本机 Codex 模型缓存，包含隐藏模型。列表可能由不同 Codex 版本写入；访问权限和实际支持以 CLI 调用为准。",
                )
            except FileNotFoundError:
                result = ModelCatalog(provider=provider, status="unavailable", fetched_at="",
                                      message="本机暂无 Codex 模型缓存；可直接填写 CLI 支持的模型名称。使用 Codex 后可重新读取列表。")
            except (OSError, ValueError, UnicodeError, RecursionError):
                # Never return cache contents, exception text, paths or auth data.
                result = ModelCatalog(provider=provider, status="error", fetched_at="",
                                      message="本机 Codex 模型缓存暂时无法读取；可继续使用自定义模型名称，稍后重新读取列表。")
            self._cached = {key: (time.monotonic(), result)}
            return result.model_copy(deep=True)
