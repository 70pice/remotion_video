"""Canonical production component metadata shared by agents and validators."""

from __future__ import annotations

import hashlib
import json
import re
from functools import cache
from pathlib import Path
from typing import Any

from videoagents.default_config import PROJECT_ROOT

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "component-manifest.json"
COMPONENT_PATHS_PATH = PROJECT_ROOT / "docs" / "component-paths.json"
COMPONENT_USE_GUIDE_PATH = PROJECT_ROOT / "docs" / "component-use-guide.json"
VALID_USAGES = {"personal", "commercial", "unspecified"}


@cache
def component_manifest() -> tuple[dict[str, Any], ...]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if payload.get("schema_version") != "1" or not isinstance(entries, list):
        raise RuntimeError("组件清单格式无效")
    identifiers = [entry.get("component_id") for entry in entries]
    adapter_count = sum(1 for entry in entries if entry.get("kind") == "adapter")
    preset_count = sum(1 for entry in entries if entry.get("kind") == "preset")
    if len(entries) != len(set(identifiers)) or adapter_count != 9 or preset_count != 152:
        raise RuntimeError("组件清单必须包含 9 个参数适配器和 152 个预设组件")
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


def _json_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def manifest_fingerprint() -> str:
    return hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()


def _compact(value: str, limit: int) -> str:
    return re.sub(r"\s+", " ", value).strip()[:limit].rstrip()


def _balanced_block(text: str, start: int, limit: int) -> str:
    open_at = text.find("{", start)
    if open_at < 0:
        return _compact(text[start:start + limit], limit)
    depth = 0
    for index in range(open_at, min(len(text), open_at + limit * 4)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                if end < len(text) and text[end] == ";":
                    end += 1
                return _compact(text[start:end], limit)
    return _compact(text[start:start + limit], limit)


def _first_block(text: str, patterns: list[str], limit: int) -> str:
    positions = [match.start() for pattern in patterns if (match := re.search(pattern, text, re.S))]
    return _balanced_block(text, min(positions), limit) if positions else ""


def _source_summary(entry_text: str, source_text: str, component_id: str) -> dict[str, str]:
    """Project bounded static source evidence into the component study context."""

    merged = source_text + "\n" + entry_text
    comments = [match.group(0) for match in re.finditer(r"/\*[\s\S]{0,1200}?\*/|//[^\n]{1,240}", source_text)]
    summary = {
        "meta_hint": (
            _first_block(source_text, [r"export\s+const\s+meta\s*=", r"const\s+meta\s*="], 120)
            or _first_block(entry_text, [r"export\s+const\s+meta\s*=", r"const\s+meta\s*="], 120)
        ),
        "props_hint": _first_block(merged, [
            r"export\s+type\s+\w*Props\s*=", r"type\s+\w*Props\s*=",
            r"export\s+interface\s+\w*Props\s*", r"interface\s+\w*Props\s*",
        ], 110),
        "config_hint": _first_block(source_text, [r"const\s+CONFIG\s*=", r"const\s+\w*CONFIG\s*="], 110),
        "source_notes": _compact(" ".join(comments[:2]), 60),
    }
    return {key: value for key, value in summary.items() if value}


def component_source_guide() -> dict[str, Any]:
    """Return the source-derived vertical component guide used by the director."""

    paths = json.loads(COMPONENT_PATHS_PATH.read_text(encoding="utf-8")).get("components", [])
    path_by_id = {item["compositionId"]: item for item in paths}
    use_guide = {
        item["compositionId"]: item
        for item in json.loads(COMPONENT_USE_GUIDE_PATH.read_text(encoding="utf-8")).get("components", [])
    }
    components = []
    for entry in component_manifest():
        guide_item = use_guide.get(entry["component_id"], {})
        item: dict[str, Any] = {
            "component_id": entry["component_id"],
            "name": entry["name"],
            "library": entry["library"],
            "kind": entry["kind"],
            "description": guide_item.get("description") or entry["description"],
            "use_case": guide_item.get("useCase") or entry["use_case"],
            "allowed_usages": entry["allowed_usages"],
            "license_scope": "commercial_ok" if "commercial" in entry["allowed_usages"] else "noncommercial_only",
            "props_mode": entry.get("props_mode", "typed" if entry["kind"] == "adapter" else "empty"),
        }
        if entry["kind"] == "preset":
            path_info = path_by_id.get(entry["component_id"])
            if not path_info:
                raise RuntimeError(f"组件路径缺失：{entry['component_id']}")
            vertical_source = PROJECT_ROOT / path_info["verticalSourcePath"]
            vertical_entry = PROJECT_ROOT / path_info["verticalPath"]
            if not vertical_source.is_file() or not vertical_entry.is_file():
                raise RuntimeError(f"竖版组件源码缺失：{entry['component_id']}")
            entry_text = vertical_entry.read_text(encoding="utf-8")
            source_text = vertical_source.read_text(encoding="utf-8")
            item.update({
                "vertical_path": path_info["verticalPath"],
                "vertical_source_path": path_info["verticalSourcePath"],
                "vertical_path_sha256": hashlib.sha256(vertical_entry.read_bytes()).hexdigest(),
                "vertical_source_sha256": hashlib.sha256(vertical_source.read_bytes()).hexdigest(),
                "source_summary": _source_summary(entry_text, source_text, entry["component_id"]),
            })
        else:
            item["adapter_constraints"] = "真实素材必须来自当前任务 assets。"
            if entry["component_id"] in {"evidence", "image_focus"}:
                item["adapter_constraints"] += (
                    "focus_cues 在同镜头内按实测字幕移动相机并聚焦压暗："
                    "1-8项，第一项frame=0，随后严格递增；每项仅frame/region/label。"
                    "region为实测归一化矩形，省略代表总览；label最多24字。"
                    "固定18帧连续过渡，保持同一真实图片与原比例，不重启入场。"
                    "不与旧highlight/crop/focal_x/focal_y混用，未知位置不生成坐标。"
                )
            elif entry["component_id"] == "data":
                item["adapter_constraints"] += (
                    "默认cards的比较对象label和必要单位从开头可读，reveal_frame只控制数值value。"
                    "竖屏两项上下排列，避免整卡等待数值导致大面积空白。"
                    "可选visualization=bars/donuts复用已有真实数据图形底层，"
                    "items.numeric_value必须为来源明确的非负数字；图形、value与detail按reveal_frame用15帧揭示。"
                    "label从开头可见，说明空间保留，避免detail中的补集或倍数提前透露结果。"
                    "bars需unit、scale_max与本段source_ref，共用0起点和量程，可选reference_value。"
                    "donuts需unit=%、本段source_ref，每项独立100分母，numeric_value为0-100，最多2项。"
                    "倍数不做饼、不同群体比例不合并；保留来源、单位、时间、样本、最高/约等限定。"
                )
                source_paths = (
                    "src/video-production/adapters/data.tsx",
                    "src/video-production/adapters/dataCharts.tsx",
                    "src/components/component-horizontal/remotion-ui/scenes/animated-bar-chart/index.tsx",
                    "src/components/component-horizontal/rve/donut-chart.tsx",
                )
                item["implementation_sources"] = [
                    {"path": source_path,
                     "sha256": hashlib.sha256((PROJECT_ROOT / source_path).read_bytes()).hexdigest()}
                    for source_path in source_paths
                ]
        components.append(item)
    guide = {
        "schema_version": "1",
        "manifest_fingerprint": manifest_fingerprint(),
        "component_count": len(components),
        "adapter_count": len([item for item in components if item["kind"] == "adapter"]),
        "preset_count": len([item for item in components if item["kind"] == "preset"]),
        "adapter_sources": [
            {"path": path.relative_to(PROJECT_ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in sorted((PROJECT_ROOT / "src/video-production/adapters").glob("*"))
            if path.suffix in {".ts", ".tsx"}
        ],
        "components": components,
        "selection_rules": [
            "先用真实视频素材；只有视频不存在、时长不足或语义不匹配时才退回图片或解释组件。",
            "商业用途按 allowed_usages 过滤可选组件，但学习阶段仍要覆盖全部 152 个竖版预设。",
            "社区预设不能承载事实证据；事实、数字、原文与产品画面优先使用参数化适配器。",
            "所有竖版预设来源于 docs/component-paths.json 的 verticalPath/verticalSourcePath，并以 SHA256 防漂移。",
        ],
        "inspection_limits": [
            "组件资料来自使用指南、入口文件和竖版源码静态摘录；没有逐像素渲染观看全部动画。",
            "固定预设仅作为动效和布局模板，不能把内置 demo 文案或图片当成本期素材。",
        ],
    }
    return {**guide, "source_fingerprint": _json_hash(guide)}


def component_study_payload(usage: str) -> dict[str, Any]:
    if usage not in VALID_USAGES:
        raise ValueError(f"未知使用场景：{usage}")
    guide = component_source_guide()
    allowed = set(available_component_ids(usage))
    return {
        **guide,
        "usage": usage,
        "allowed_component_ids": [entry["component_id"] for entry in component_manifest()
                                  if entry["component_id"] in allowed],
        "allowed_preset_ids": [entry["component_id"] for entry in component_manifest()
                               if entry["kind"] == "preset" and entry["component_id"] in allowed],
        "all_preset_ids": list(COMMUNITY_COMPONENT_IDS),
    }


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
