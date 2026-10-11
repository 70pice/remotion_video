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
NATIVE_COMPONENT_CAPABILITIES_PATH = PROJECT_ROOT / "videoagents" / "native-component-capabilities.json"
VALID_USAGES = {"personal", "commercial", "unspecified"}
VALID_MATERIAL_CAPABILITIES = {"native_slots", "overlay"}
VALID_NATIVE_CONSTRAINT_KEYS = {
    "items_min", "numeric_first_item", "body_required",
    "media_required", "image_only", "metric_required",
    "replacement_required", "items_distinct", "keyword_required", "asset_forbidden",
    "min_visible_frames", "selection_matches_item",
}
EXPECTED_ADAPTER_COUNT = 9
EXPECTED_PRESET_COUNT = 187
SCENE_PLAYBOOKS: tuple[dict[str, Any], ...] = (
    {
        "scene_id": "opening_hook",
        "scene": "开头钩子 / 问题立住",
        "intent": "前 3-5 秒看见具体对象、结果或冲突。",
        "composition": "一镜抛问题，一镜给证据锚点。",
        "shot_flow": [
            {
                "slot": "hook",
                "purpose": "抛出问题、对象或反差。",
                "components": ["Talkcraft-impact-open-title", "Snapcn-SearchTyping", "title"],
            },
            {
                "slot": "anchor",
                "purpose": "接真实界面、截图或结果。",
                "components": ["video", "evidence", "image_focus", "Snapcn-LaptopFrame", "Snapcn-PhoneFrame"],
            },
        ],
        "avoid": "不要连续纯标题；没有证据就用明确问题关系。",
    },
    {
        "scene_id": "ai_coding_workflow",
        "scene": "AI Coding / Agent 工作流",
        "intent": "讲提示词、工具执行、测试和结果。",
        "composition": "输入意图 -> 执行过程 -> 结果或日志。",
        "shot_flow": [
            {
                "slot": "input",
                "purpose": "展示提示词或任务启动。",
                "components": ["Snapcn-PromptSend", "Snapcn-SearchTyping", "title"],
            },
            {
                "slot": "execution",
                "purpose": "展示 Agent 执行或终端过程。",
                "components": ["Snapcn-AgentSteps", "Snapcn-TerminalSimulator", "steps", "Talkcraft-terminal-typing-log"],
            },
            {
                "slot": "result",
                "purpose": "展示产出、diff 或最终回答。",
                "components": ["Snapcn-AnswerStream", "Snapcn-AnswerHighlight", "evidence", "image_focus"],
            },
        ],
        "avoid": "不要把终端/代码预设当通用 AI 氛围。",
    },
    {
        "scene_id": "product_demo",
        "scene": "产品 / 工具界面演示",
        "intent": "讲网页、App、后台、录屏和操作结果。",
        "composition": "设备容器承载界面 -> 局部放大关键操作 -> 结果或限制说明。",
        "shot_flow": [
            {
                "slot": "container",
                "purpose": "用设备/窗口承载界面素材。",
                "components": ["Snapcn-LaptopFrame", "Snapcn-PhoneFrame", "Snapcn-ScreenRecording", "video"],
            },
            {
                "slot": "focus",
                "purpose": "放大按钮、输入、结果或关键区。",
                "components": ["image_focus", "evidence", "Snapcn-CursorTrack"],
            },
            {
                "slot": "takeaway",
                "purpose": "收束能力、限制或结论。",
                "components": ["comparison", "data", "conclusion"],
            },
        ],
        "avoid": "不要完整截图、长标题和大段 body 同屏堆。",
    },
    {
        "scene_id": "source_evidence",
        "scene": "来源证据 / 官方说法",
        "intent": "展示论文、公告、截图或网页原文。",
        "composition": "先给出处，再聚焦引用区域。",
        "shot_flow": [
            {
                "slot": "source",
                "purpose": "展示真实来源和上下文。",
                "components": ["evidence", "Rve-QuoteCard", "Snapcn-LaptopFrame"],
            },
            {
                "slot": "detail",
                "purpose": "放大正在引用的证据。",
                "components": ["image_focus", "Snapcn-AnswerHighlight", "keyword"],
            },
        ],
        "avoid": "不要把链接或内置 demo 文案当证据。",
    },
    {
        "scene_id": "data_claim",
        "scene": "数据 / 指标判断",
        "intent": "讲价格、速度、比例、排名或评测分数。",
        "composition": "先抛核心数字，再给口径或对比。",
        "shot_flow": [
            {
                "slot": "metric",
                "purpose": "展示主数字或核验指标。",
                "components": ["data", "Rve-StatCounter", "Rve-ProgressBars"],
            },
            {
                "slot": "trend_or_compare",
                "purpose": "展示变化、差距或同口径对比。",
                "components": ["Rve-ChartAnimation", "Rve-LineChart", "Rve-ComparisonChart", "RenderComp-PixelCandlestickOhlc"],
            },
        ],
        "avoid": "不要凭空生成百分比、趋势、排名或赢家。",
    },
    {
        "scene_id": "before_after",
        "scene": "前后对比 / 反转解释",
        "intent": "讲旧新方案、误解答案、A/B 差异。",
        "composition": "先建立 A，再在转折句揭示 B。",
        "shot_flow": [
            {
                "slot": "setup",
                "purpose": "立住旧认知或左侧对象。",
                "components": ["comparison", "Rve-SplitScreen", "Snapcn-TextRewrite"],
            },
            {
                "slot": "reveal",
                "purpose": "揭示新结论或右侧对象。",
                "components": ["Rve-ComparisonChart", "Rve-ImageComparisonSlider", "Snapcn-TextSwap", "conclusion"],
            },
        ],
        "avoid": "不要把无共同口径的素材硬并列。",
    },
    {
        "scene_id": "process_steps",
        "scene": "流程 / 方法论 / 阶段推进",
        "intent": "讲 2-4 步流程、Agent 分工或项目阶段。",
        "composition": "同一结构逐项揭示，每步有动作或结论。",
        "shot_flow": [
            {
                "slot": "map",
                "purpose": "给流程骨架或当前阶段。",
                "components": ["steps", "Rve-ProgressSteps", "Snapcn-AgentSteps"],
            },
            {
                "slot": "state_change",
                "purpose": "展示任务推进或状态变化。",
                "components": ["RemotionUI-KanbanMove", "Rve-ProgressBars", "Talkcraft-chapter-progress-list"],
            },
        ],
        "avoid": "不要超过 4 个屏幕条目，并列名词别装流程。",
    },
    {
        "scene_id": "gallery_context",
        "scene": "多素材集合 / 案例墙",
        "intent": "讲多个案例、候选方案或作品集合。",
        "composition": "先用图库建立集合感，再切一张主图或结论解释。",
        "shot_flow": [
            {
                "slot": "collection",
                "purpose": "展示集合、案例墙或多图对照。",
                "components": ["Snapcn-MoodboardReveal", "Rve-GalleryGrid", "Rve-MasonryGallery", "Talkcraft-gallery-wall-dolly"],
            },
            {
                "slot": "select",
                "purpose": "选出当前对象或结论。",
                "components": ["image_focus", "evidence", "keyword", "conclusion"],
            },
        ],
        "avoid": "不要把一张图硬做成多图案例。",
    },
)


@cache
def component_manifest() -> tuple[dict[str, Any], ...]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("entries")
    if payload.get("schema_version") != "1" or not isinstance(entries, list):
        raise RuntimeError("组件清单格式无效")
    identifiers = [entry.get("component_id") for entry in entries]
    adapter_count = sum(1 for entry in entries if entry.get("kind") == "adapter")
    preset_count = sum(1 for entry in entries if entry.get("kind") == "preset")
    if (
        len(entries) != len(set(identifiers))
        or adapter_count != EXPECTED_ADAPTER_COUNT
        or preset_count != EXPECTED_PRESET_COUNT
    ):
        raise RuntimeError(
            f"组件清单必须包含 {EXPECTED_ADAPTER_COUNT} 个参数适配器和"
            f" {EXPECTED_PRESET_COUNT} 个预设组件"
        )
    for entry in entries:
        usages = set(entry.get("allowed_usages", []))
        capability = entry.get("material_capability")
        if (
            entry.get("kind") not in {"adapter", "preset"}
            or not usages
            or not usages <= VALID_USAGES
            or capability not in VALID_MATERIAL_CAPABILITIES
        ):
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


@cache
def native_component_capabilities() -> dict[str, Any]:
    path = NATIVE_COMPONENT_CAPABILITIES_PATH
    if not path.is_file():
        return {
            "entries": [], "main_component_ids": frozenset(), "layer_roles": {},
            "content_constraints": {}, "fingerprint": None,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    main_ids: set[str] = set()
    role_map: dict[str, frozenset[str]] = {}
    constraints_by_id: dict[str, dict[str, Any]] = {}
    for item in payload.get("entries", []):
        if type(item) is not dict:
            continue
        component_id = item.get("component_id")
        roles = item.get("roles")
        if component_id not in COMMUNITY_COMPONENT_ID_SET or not isinstance(roles, list):
            continue
        accepted_roles = {role for role in roles if role in {"main", "title", "emphasis"}}
        if not accepted_roles:
            continue
        constraints = item.get("content_constraints")
        normalized_constraints: dict[str, Any] = {}
        if type(constraints) is dict:
            normalized_constraints = {
                key: value for key, value in constraints.items()
                if key in VALID_NATIVE_CONSTRAINT_KEYS
            }
        normalized = {
            "component_id": component_id,
            "roles": sorted(accepted_roles),
            "source": item.get("source", ""),
            "renderer": item.get("renderer", ""),
            "use_case": item.get("use_case", ""),
            "content_constraints": normalized_constraints,
        }
        entries.append(normalized)
        if "main" in accepted_roles:
            main_ids.add(component_id)
        layer_roles = accepted_roles & {"title", "emphasis"}
        if layer_roles:
            role_map[component_id] = frozenset(layer_roles)
        if normalized_constraints:
            constraints_by_id[component_id] = normalized_constraints
    return {
        "entries": entries,
        "main_component_ids": frozenset(main_ids),
        "layer_roles": role_map,
        "content_constraints": constraints_by_id,
        "fingerprint": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def native_library_component_ids(usage: str) -> frozenset[str]:
    if usage not in VALID_USAGES:
        raise ValueError(f"未知使用场景：{usage}")
    allowed = set(available_component_ids(usage))
    capabilities = native_component_capabilities()
    ids = set(capabilities["main_component_ids"]) | set(capabilities["layer_roles"])
    return frozenset(component_id for component_id in ids if component_id in allowed)


def prompt_native_component_requirements(usage: str) -> str:
    if usage not in VALID_USAGES:
        raise ValueError(f"未知使用场景：{usage}")
    allowed = set(available_component_ids(usage))
    entries = [entry for entry in native_component_capabilities()["entries"] if entry["component_id"] in allowed]
    if not entries:
        return "原生能力清单未提供可计数组件；有最低数量要求时必须暂停，不能用 adapter 或 fallback ID 凑数。"
    lines = [
        "计数口径：只统计下列 native-component-capabilities entries；adapter 和基础语义组件不计数；同一 component_id 重复只计一次。",
        "main 镜头只有 roles 含 main 才能作为主组件计数；layers 只有 role 为 title/emphasis 且该组件 roles 支持该 role 才能计数。",
        "layers 字段形状：{component_id, role:title|emphasis, start_frame, end_frame, title, body, props, accent_color}；时间是所属镜头本地帧，持续至少 30 帧；每镜头最多 2 层。",
        "layers 的意义是补充真实标题或重点强调，文字必须来自本期旁白/证据，不能为了凑数量填空泛文案。",
        "需要 60 个不同组件时不要硬拆 60 个主镜头；建议约 36-50 个有内容主镜头加 title/emphasis 层补足，层时间要对应原 caption 语义。",
    ]
    for entry in entries:
        lines.append(
            f"- {entry['component_id']} | roles={','.join(entry['roles'])} | "
            f"constraints={json.dumps(entry['content_constraints'], ensure_ascii=False, separators=(',', ':'))} | "
            f"renderer={entry['renderer']} | source={entry['source']} | {entry['use_case']}"
        )
    return "\n".join(lines)


def _native_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _native_props(value: Any) -> dict[str, Any]:
    props = getattr(value, "props", {})
    return props if isinstance(props, dict) else {}


def _native_items(value: Any) -> list[str]:
    items = _native_props(value).get("items")
    if not isinstance(items, list):
        return []
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def _has_numeric_text(value: str) -> bool:
    return bool(re.search(r"[0-9０-９一二三四五六七八九十百千万亿两]+", value))


def _native_metric_present(value: Any) -> bool:
    metric = _native_props(value).get("metric")
    if not isinstance(metric, dict):
        return False
    label = _native_text(metric.get("label"))
    metric_value = _native_text(metric.get("value"))
    return bool(label and metric_value)


def _native_asset_src(value: Any) -> str:
    asset_src = getattr(value, "asset_src", None)
    return asset_src.strip() if isinstance(asset_src, str) else ""


def _native_content_issues(
    component_id: str, value: Any, constraints: dict[str, Any], *, kind: str, visible_frames: int | None = None
) -> list[str]:
    issues: list[str] = []
    min_visible_frames = constraints.get("min_visible_frames")
    if isinstance(min_visible_frames, int) and min_visible_frames > 0:
        actual = visible_frames if isinstance(visible_frames, int) else 0
        if actual < min_visible_frames:
            issues.append(f"{kind} {component_id} 可见 {actual} 帧，要求至少 {min_visible_frames} 帧")
    if constraints.get("body_required") and not _native_text(getattr(value, "body", "")):
        issues.append(f"{kind} {component_id} 需要非空 body")
    items_min = constraints.get("items_min")
    if isinstance(items_min, int) and len(_native_items(value)) < items_min:
        issues.append(f"{kind} {component_id} 需要 props.items 至少 {items_min} 项")
    if constraints.get("numeric_first_item"):
        items = _native_items(value)
        if not items or not _has_numeric_text(items[0]):
            issues.append(f"{kind} {component_id} 需要 props.items[0] 含真实数字")
    if constraints.get("items_distinct"):
        items = _native_items(value)
        if len(items) != len(set(items)):
            issues.append(f"{kind} {component_id} 需要 props.items 不重复")
    if constraints.get("selection_matches_item"):
        props = _native_props(value)
        target = (_native_text(props.get("keyword")) or _native_text(props.get("highlight"))
                  or _native_text(props.get("title")) or _native_text(getattr(value, "title", "")))
        normalized = re.sub(r"[\W_]+", "", target).lower()
        matches = [item for item in _native_items(value)[:5]
                   if re.sub(r"[\W_]+", "", item).lower() == normalized]
        if not normalized or len(matches) != 1:
            issues.append(f"{kind} {component_id} 的 title 或 props.highlight 必须精确匹配唯一选项")
    if constraints.get("replacement_required"):
        props = _native_props(value)
        from_text = _native_text(props.get("from_text"))
        to_text = _native_text(props.get("to_text"))
        if not from_text or not to_text or from_text == to_text:
            issues.append(f"{kind} {component_id} 需要不同的 props.from_text/to_text")
    if constraints.get("metric_required") and not _native_metric_present(value):
        issues.append(f"{kind} {component_id} 需要 props.metric.label/value")
    if constraints.get("keyword_required"):
        props = _native_props(value)
        items = _native_items(value)
        if not (_native_text(props.get("highlight")) or items):
            issues.append(f"{kind} {component_id} 需要 props.highlight 或 props.items[0] 作为关键词")
    asset_src = _native_asset_src(value)
    if constraints.get("asset_forbidden") and asset_src:
        issues.append(f"{kind} {component_id} 不允许 asset_src，不能挂素材路径冒充真实画面")
    if constraints.get("media_required") and not asset_src:
        issues.append(f"{kind} {component_id} 需要真实 asset_src 素材")
    if constraints.get("image_only"):
        if not asset_src or not re.search(r"\.(png|jpe?g|webp|gif|avif)$", asset_src, re.I):
            issues.append(f"{kind} {component_id} 只允许真实图片 asset_src")
    return issues


def _component_requirement_analysis(timeline: Any, usage: str, required: int) -> tuple[dict[str, Any], list[str]]:
    native_ids = native_library_component_ids(usage)
    capabilities = native_component_capabilities()
    roles = capabilities["layer_roles"]
    main_allowed = capabilities["main_component_ids"]
    constraints = capabilities["content_constraints"]
    main_ids: set[str] = set()
    layer_ids: set[str] = set()
    issues: list[str] = []
    set_fingerprint = None
    for shot in timeline.shots:
        if getattr(shot, "set_design", None) is not None:
            from videoagents.tools.component_sets import (
                allowed_component_set_templates,
                component_set_fingerprint,
                validate_component_set_layout,
            )

            try:
                validate_component_set_layout(shot, fps=timeline.fps)
                template = allowed_component_set_templates(usage)[shot.set_design.set_id]
            except (KeyError, ValueError) as exc:
                issues.append(f"组件套使用统计校验失败：{exc}")
                continue
            set_fingerprint = component_set_fingerprint()
            # Count only fixed parts actually mounted by the production renderer.
            # Semantic adapters remain outside native component counts.
            for part in template["parts"]:
                component_id = part["component_id"]
                if component_id in native_ids:
                    (main_ids if part["role"] == "main" else layer_ids).add(component_id)
            continue
        if shot.component_id in native_ids and shot.component_id in main_allowed:
            shot_duration = shot.end_frame - shot.start_frame
            shot_issues = []
            if shot_duration < 30:
                shot_issues.append(f"main {shot.component_id} 至少需要可见 30 帧")
            if required:
                shot_issues.extend(_native_content_issues(
                    shot.component_id, shot, constraints.get(shot.component_id, {}),
                    kind="main", visible_frames=shot_duration,
                ))
            if shot_issues:
                issues.extend(shot_issues)
            else:
                main_ids.add(shot.component_id)
        for layer in getattr(shot, "layers", []):
            if layer.component_id not in native_ids or layer.role not in roles.get(layer.component_id, frozenset()):
                continue
            layer_issues = []
            layer_duration = layer.end_frame - layer.start_frame
            if layer_duration < 30:
                layer_issues.append(f"layer {layer.component_id} 至少需要可见 30 帧")
            layer_issues.extend(_native_content_issues(
                layer.component_id, layer, constraints.get(layer.component_id, {}),
                kind="layer", visible_frames=layer_duration,
            ))
            if layer_issues:
                issues.extend(layer_issues)
            else:
                layer_ids.add(layer.component_id)
    library_ids = sorted(main_ids | layer_ids)
    usage_payload = {
        "required": required,
        "library_count": len(library_ids),
        "library_ids": library_ids,
        "main_count": len(main_ids),
        "layer_count": len(layer_ids),
        "native_manifest_fingerprint": native_component_capabilities()["fingerprint"],
    }
    if set_fingerprint:
        usage_payload["component_set_fingerprint"] = set_fingerprint
    return usage_payload, issues


def component_requirement_usage(timeline: Any, usage: str, required: int = 0) -> dict[str, Any]:
    return _component_requirement_analysis(timeline, usage, required)[0]


def validate_component_requirements(timeline: Any, usage: str, required: int) -> dict[str, Any]:
    usage_payload, issues = _component_requirement_analysis(timeline, usage, required)
    if required and usage_payload["native_manifest_fingerprint"] is None:
        raise ValueError("缺少原生组件能力清单，不能证明库组件真实可生产使用")
    if issues:
        raise ValueError("；".join(issues))
    if required and usage_payload["library_count"] < required:
        raise ValueError(
            f"导演分镜只使用了 {usage_payload['library_count']} 个不同原生库组件，"
            f"本片要求至少 {required} 个；基础语义组件和非原生组件不计数"
        )
    return usage_payload


def _component_list_for_usage(component_ids: list[str], allowed: set[str]) -> list[str]:
    return [component_id for component_id in component_ids if component_id in allowed]


def component_scene_playbook(usage: str) -> list[dict[str, Any]]:
    """Return scenario-first component combinations filtered by license usage."""

    if usage not in VALID_USAGES:
        raise ValueError(f"未知使用场景：{usage}")
    allowed = set(available_component_ids(usage))
    playbooks: list[dict[str, Any]] = []
    for playbook in SCENE_PLAYBOOKS:
        shot_flow = []
        for step in playbook["shot_flow"]:
            components = _component_list_for_usage(step["components"], allowed)
            if components:
                shot_flow.append({**step, "components": components})
        if len(shot_flow) >= 2:
            playbooks.append({**playbook, "shot_flow": shot_flow})
    return playbooks


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
        "source_notes": _compact(" ".join(comments[:2]), 36),
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
            "material_capability": entry["material_capability"],
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
                "source_summary": _source_summary(entry_text, source_text, entry["component_id"]),
            })
        else:
            item["adapter_constraints"] = "真实素材必须来自当前任务 assets。"
        components.append(item)
    guide = {
        "schema_version": "1",
        "manifest_fingerprint": manifest_fingerprint(),
        "component_count": len(components),
        "adapter_count": len([item for item in components if item["kind"] == "adapter"]),
        "preset_count": len([item for item in components if item["kind"] == "preset"]),
        "components": components,
        "selection_rules": [
            "先定场景，再选组件；同一连续段落按 scene_playbooks 的组合职责选择镜头，不逐镜随机换预设。",
            "先用真实视频素材；只有视频不存在、时长不足或语义不匹配时才退回图片或解释组件。",
            f"商业用途按 allowed_usages 过滤可选组件，但学习阶段仍要覆盖全部 {EXPECTED_PRESET_COUNT} 个竖版预设。",
            "社区预设可承载当前任务的图片/视频、标题、正文、短列表、指标和强调色；需要精确证据框、复杂数据或步骤同步时使用参数化适配器。",
            "material_capability=native_slots 表示素材和文案进入组件本体或语义匹配的原生展示面；当前包括 9 个参数化适配器和 187 个社区预设。",
            "所有竖版预设来源于 docs/component-paths.json 的 verticalPath/verticalSourcePath，并由 source_fingerprint 防漂移。",
        ],
        "inspection_limits": [
            "组件资料来自使用指南、入口文件和竖版源码静态摘录；没有逐像素渲染观看全部动画。",
            "预设内部 demo 文案或图片不能当成本期素材；生产时只使用任务导入素材和导演填写的安全内容槽位。",
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
        "scene_playbooks": component_scene_playbook(usage),
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
            f"{entry['material_capability']} | "
            f"{entry['description']} | {entry['use_case']}"
        )
    return "\n".join(lines)


def prompt_scene_playbook(usage: str) -> str:
    """Return compact scenario-first component combinations for prompt injection."""

    lines = ["先定场景，再选组件；同一 10-20 秒段落优先按一个 playbook 连续组合，避免逐镜随机换组件。"]
    for playbook in component_scene_playbook(usage):
        lines.append(
            f"- {playbook['scene']}（{playbook['scene_id']}）：{playbook['intent']}"
        )
        lines.append(f"  组合节奏：{playbook['composition']}")
        flow = []
        for step in playbook["shot_flow"]:
            flow.append(
                f"{step['slot']}={','.join(step['components'])}（{step['purpose']}）"
            )
        lines.append(f"  推荐镜头：{'; '.join(flow)}")
        lines.append(f"  避免：{playbook['avoid']}")
    return "\n".join(lines)
