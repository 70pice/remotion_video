"""Canonical production component metadata shared by agents and validators."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "component-manifest.json"
VALID_USAGES = {"personal", "commercial", "unspecified"}


@cache
def component_manifest() -> tuple[dict[str, Any], ...]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if payload.get("schema_version") != "1" or not isinstance(entries, list):
        raise RuntimeError("组件清单格式无效")
    identifiers = [entry.get("component_id") for entry in entries]
    if len(entries) != 160 or len(set(identifiers)) != 160:
        raise RuntimeError("组件清单必须包含 8 个参数适配器和 152 个预设组件")
    for entry in entries:
        usages = set(entry.get("allowed_usages", []))
        if entry.get("kind") not in {"adapter", "preset"} or not usages or not usages <= VALID_USAGES:
            raise RuntimeError(f"组件清单条目无效：{entry.get('component_id', '<unknown>')}")
    return tuple(entries)


COMPONENT_BY_ID = {entry["component_id"]: entry for entry in component_manifest()}
PRODUCTION_COMPONENT_IDS = tuple(COMPONENT_BY_ID)
PRODUCTION_COMPONENT_ID_SET = frozenset(PRODUCTION_COMPONENT_IDS)
SEMANTIC_COMPONENT_IDS = tuple(
    entry["component_id"] for entry in component_manifest() if entry["kind"] == "adapter"
)
SEMANTIC_COMPONENT_ID_SET = frozenset(SEMANTIC_COMPONENT_IDS)
COMMUNITY_COMPONENT_IDS = tuple(
    entry["component_id"] for entry in component_manifest() if entry["kind"] == "preset"
)
COMMUNITY_COMPONENT_ID_SET = frozenset(COMMUNITY_COMPONENT_IDS)


def available_component_ids(usage: str) -> list[str]:
    if usage not in VALID_USAGES:
        raise ValueError(f"未知使用场景：{usage}")
    return [
        entry["component_id"]
        for entry in component_manifest()
        if usage in entry["allowed_usages"]
    ]


def component_allowed(component_id: str, usage: str) -> bool:
    entry = COMPONENT_BY_ID.get(component_id)
    return bool(entry and usage in entry["allowed_usages"])


def prompt_component_catalog(usage: str) -> str:
    """Return the compact, complete selection guide injected into the director prompt."""

    lines = []
    for entry in component_manifest():
        if usage not in entry["allowed_usages"]:
            continue
        mode = "参数化" if entry["kind"] == "adapter" else "固定预设"
        lines.append(
            f"{entry['component_id']} | {entry['library']} | {mode} | "
            f"{entry['description']} | {entry['use_case']}"
        )
    return "\n".join(lines)
