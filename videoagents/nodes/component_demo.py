"""Reusable one-shot component-set demo planning node."""

from __future__ import annotations

import math
import re
import uuid
from dataclasses import dataclass
from typing import Any, Literal

from videoagents.contracts import (
    Asset,
    ComponentDemoContent,
    ComponentDemoRequest,
    Job,
    Shot,
    ShotLayer,
    Timeline,
)
from videoagents.nodes.common import start_stage, state_context
from videoagents.nodes.director import (
    _required_library_components,
    _validate_director_plan_payload,
    timeline_fingerprint,
)
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.tools.components import component_requirement_usage, validate_component_requirements
from videoagents.tools.timeline import safe_media_source, validate_timeline

SetId = Literal["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A11", "A12", "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18"]
RECIPE_VERSION = "component-demo-v2"
B_RECIPE_VERSION = "component-demo-v3"
B_RICH_RECIPE_VERSION = "component-demo-v4"
MATERIAL_RICH_RECIPE_VERSION = "component-demo-v5"
MATERIAL_RICH_SET_IDS = {f"A{index:02d}" for index in range(7, 13)}
VALID_SET_IDS = {f"A{index:02d}" for index in range(1, 13)} | {f"B{index:02d}" for index in range(1, 19)}
MATERIAL_RICH_COMPONENTS = {
    "A07": "Talkcraft-slow-push-in",
    "A08": "Snapcn-PhoneFrame",
    "A09": "Snapcn-PhoneFrame",
    "A10": "Talkcraft-scanline-annotate",
    "A11": "Talkcraft-tilt-3d-page",
    "A12": "Talkcraft-slow-pull-reveal",
}
B_SET_COMPONENTS = {
    "B01": "Rve-QuoteCard",
    "B02": "keyword",
    "B03": "Rve-SplitScreen",
    "B04": "Rve-StatCounter",
    "B05": "Rve-ProgressSteps",
    "B06": "conclusion",
    "B07": "Rve-ChartAnimation",
    "B08": "Rve-StatCounter",
    "B09": "Rve-ComparisonChart",
    "B10": "Rve-ChartAnimation",
    "B11": "Rve-ProgressSteps",
    "B12": "Rve-QuoteCard",
    "B13": "Rve-SplitScreen",
    "B14": "Snapcn-AnswerStream",
    "B15": "Rve-QuoteCard",
    "B16": "Rve-ProgressSteps",
    "B17": "Bits-ChatConversation",
    "B18": "Rve-ComparisonChart",
}

GUIDED_ACCENT = "#FB923C"


@dataclass(frozen=True)
class DemoRecipe:
    set_id: SetId
    main_component_id: str
    title: str
    body: str
    source_label: str
    props: dict[str, Any]
    layers: tuple[dict[str, Any], ...]
    visual_action: str
    component_reason: str
    requires_video: bool = False
    media_usage: str = "source_evidence"
    default_duration_seconds: float = 10.0
    actual_composition_components: tuple[str, ...] = ()


def _layer(component_id: str, role: str, start: int, end: int, title: str, body: str = "",
           props: dict[str, Any] | None = None, accent_color: str = "#38BDF8") -> dict[str, Any]:
    return {
        "component_id": component_id,
        "role": role,
        "start_frame": start,
        "end_frame": end,
        "title": title,
        "body": body,
        "accent_color": accent_color,
        "props": props or {},
    }


def _windows(total_frames: int) -> tuple[tuple[int, int], tuple[int, int]]:
    title_end = max(90, min(total_frames - 60, int(total_frames * 0.48)))
    emphasis_start = max(title_end + 6, int(total_frames * 0.58))
    if total_frames >= 360:
        emphasis_start = max(emphasis_start, 240)
    emphasis_start = min(emphasis_start, total_frames - 60)
    return (0, title_end), (emphasis_start, total_frames)


def _recipe(set_id: SetId, total_frames: int) -> DemoRecipe:
    title_window, emphasis_window = _windows(total_frames)
    title_start, title_end = title_window
    emph_start, emph_end = emphasis_window
    if set_id == "A01":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Bits-KenBurns",
            title="母女一起看手机",
            body="家里人学会先问清楚",
            source_label="AI生成样片：家庭手机学习照片",
            props={"asset_fit": "cover"},
            layers=(
                _layer("Talkcraft-corner-bracket-frame", "title", title_start, title_end, "家里人学AI", "先陪着试一次"),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "先确认再采用", props={"before": "先请家人", "highlight": "一起核对"}),
            ),
            visual_action="生成的母女在家看手机照片做轻微 Ken Burns，前半段出现家庭学习标题，后半段强调先让人核对。",
            component_reason="A01 用 Bits-KenBurns 保持照片主体清楚，标题层和高亮层分时出现，适合家庭手机学习样片。",
        )
    if set_id == "A02":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Snapcn-PhoneFrame",
            title="邻里小助手",
            body="模拟App首页，不代表真实产品",
            source_label="模拟App样片：邻里小助手首页",
            props={"content_mode": "media", "asset_fit": "contain"},
            layers=(
                _layer("Snapcn-TextReveal", "title", title_start, title_end, "邻里小助手", "待办提醒在首页"),
            ),
            visual_action="手机框展示模拟首页三张卡片，只叠加短标题层，保留更大的手机界面便于手机端看清。",
            component_reason="A02 用 PhoneFrame 放大模拟 App 首页，仅用 TextReveal 标题层说明入口，避免额外强调层压缩手机画面。",
        )
    if set_id == "A03":
        title_start, title_end = 30, min(total_frames - 90, 120)
        emph_start = min(max(240, int(total_frames * 0.66)), total_frames - 60)
        return DemoRecipe(
            set_id=set_id,
            main_component_id="video",
            title="添加提醒操作",
            body="保存后回到列表",
            source_label="模拟App录屏样片：添加提醒流程",
            props={"fit": "contain", "start_seconds": 0, "end_seconds": total_frames / 30},
            layers=(
                _layer("Snapcn-TextBuild", "title", title_start, title_end, "添加提醒", "下午给妈妈打电话", props={"items": ["输入事项", "点保存", "列表出现"]}),
                _layer("Talkcraft-keyword-pop-highlight", "emphasis", emph_start, total_frames, "结果出现", props={"highlight": "已添加提醒"}),
            ),
            visual_action="连续播放 12 秒 9:16 模拟操作录屏：添加“下午给妈妈打电话”、保存，并在结果出现后弹出已添加提醒强调。",
            component_reason="A03 用 video 主组件放大 9:16 操作录屏，标题在开始阶段出现，强调层等到结果后再短暂出现，优先保证操作字可读。",
            requires_video=True,
            default_duration_seconds=12.0,
        )
    if set_id == "A04":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Talkcraft-tilt-3d-page",
            title="普通人与AI日常",
            body="把复杂建议变成可核对的清单",
            source_label="AI生成样片：普通人与AI日常生活插画",
            props={"asset_fit": "contain"},
            layers=(
                _layer("Talkcraft-impact-open-title", "title", title_start, title_end, "普通生活里的", "AI", props={"highlight": "AI"}),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "人来确认结果", props={"before": "建议可以快，", "highlight": "确认要靠人"}),
            ),
            visual_action="横向插画以 3D 页面形式倾斜展示，开头打出普通人与 AI 标题，后半段强调人来确认结果。",
            component_reason="A04 用 Tilt 3D Page 让横向插画更有空间感，再用标题和高亮讲清普通生活里的 AI 分工。",
        )
    if set_id == "A05":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="evidence",
            title="模拟文件声明",
            body="AI生成回答，仍然需要人工核对。",
            source_label="模拟资料：不代表真实报告或事件",
            props={"highlight": {"x": 0.08, "y": 0.40, "width": 0.84, "height": 0.12}},
            layers=(
                _layer("Talkcraft-outline-box-title", "title", title_start, title_end, "模拟声明", "非真实证据"),
                _layer("Talkcraft-highlighter-sweep", "emphasis", emph_start, emph_end, "AI生成的回答", "先看原文，再判断", props={"highlight": "仍需人工核对"}),
            ),
            visual_action="模拟文档居中展示并精确高亮“AI生成的回答仍需人工核对”一行，文字层明确标注仅作样片。",
            component_reason="A05 使用 evidence 的归一化高亮能力验证文件重点标注，但 source_label 明确为模拟资料，避免误导成真实证据。",
        )
    return DemoRecipe(
        set_id=set_id,
        main_component_id="image_focus",
        title="人和AI分工",
        body="人提出问题，AI整理建议，人再核对结果。",
        source_label="关系示意样片：人-AI-核对-结果",
        props={"crop": {"x": 0.04, "y": 0.03, "width": 0.92, "height": 0.90}, "focal_x": 0.5, "focal_y": 0.5},
        layers=(
            _layer("Talkcraft-split-text-stagger", "title", title_start, title_end, "人和AI分工", "人确认后再采用"),
            _layer("Talkcraft-keyword-pop-highlight", "emphasis", emph_start, emph_end, "关键一步", props={"highlight": "人工核对"}),
        ),
        visual_action="关系图保持主体完整，开头出现分工标题，后半段强调人工核对这一环节。",
        component_reason="A06 用 image_focus 保持四卡关系图清楚，标题说明分工，关键词强调最后的人类核对动作。",
    )


def _b_recipe(set_id: SetId, total_frames: int, content: dict[str, Any]) -> DemoRecipe:
    _, emphasis_window = _windows(total_frames)
    title_start, title_end = 0, total_frames
    emph_start, emph_end = emphasis_window
    title = content["title"]
    body = content["body"]
    takeaway = content["takeaway"]
    base_props: dict[str, Any] = {"component_set": set_id}
    if set_id == "B01":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Rve-QuoteCard",
            title=title,
            body=body,
            source_label="",
            props=base_props,
            layers=(
                _layer("Snapcn-TextReveal", "title", title_start, title_end, title, body),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "记住这一点", props={"highlight": takeaway}),
            ),
            visual_action="暗底纯文字引用卡承接问题或悬念，顶部白字标题先进入，后半段在底部强调观众应记住的一句话。",
            component_reason="B01 用 Rve-QuoteCard 做无素材问题开场，配 Snapcn 标题和高亮层形成从问题到提示的节奏。",
            media_usage="no_external_material",
        )
    if set_id == "B02":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="keyword",
            title=title,
            body=body,
            source_label="",
            props={**base_props, "keyword": takeaway},
            layers=(
                _layer("Snapcn-TextRewrite", "title", title_start, title_end, title, body, props={"from_text": title, "to_text": takeaway}),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "换个说法", props={"highlight": takeaway}),
            ),
            visual_action="关键词主组件先解释概念，顶部 TextRewrite 把复杂词改写成观众能记住的短句，后半段底部再高亮这句话。",
            component_reason="B02 用 keyword 作为主语义组件，TextRewrite 和 TextHighlight 都取自 content，不编额外产品事实。",
            media_usage="no_external_material",
        )
    if set_id == "B03":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Rve-SplitScreen",
            title=title,
            body=body,
            source_label="",
            props={**base_props, "items": content["items"]},
            layers=(
                _layer("Snapcn-TextReveal", "title", title_start, title_end, title, body),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "对比结论", props={"highlight": takeaway}),
            ),
            visual_action="上下两区展示两种情况，顶部标题说明比较问题，后半段底部给出对比后的判断短句。",
            component_reason="B03 用 Rve-SplitScreen 承接 exact 2 items 的对比输入，强调层只使用 takeaway。",
            media_usage="no_external_material",
        )
    if set_id == "B04":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Rve-StatCounter",
            title=title,
            body=body,
            source_label="",
            props={**base_props, "metric": content["metric"]},
            layers=(
                _layer("Snapcn-TextReveal", "title", title_start, title_end, title, body),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "数字怎么理解", props={"highlight": takeaway}),
            ),
            visual_action="大数字计数器展示一个演示口径的非百分比数字，顶部标题说明数字含义，底部强调 takeaway。",
            component_reason="B04 用 Rve-StatCounter 验证无素材数字表达，metric.value 必须是 0..99999 的整数加 1 到 2 个汉字单位。",
            media_usage="no_external_material",
        )
    if set_id == "B05":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Rve-ProgressSteps",
            title=title,
            body=body,
            source_label="",
            props={**base_props, "items": content["items"]},
            layers=(
                _layer("Snapcn-TextBuild", "title", title_start, title_end, title, body),
                _layer("Snapcn-TextHighlight", "emphasis", emph_start, emph_end, "最后记住", props={"highlight": takeaway}),
            ),
            visual_action="三步进度组件逐步出现，顶部只放短标题，步骤内容留在主组件中，后半段底部用一句话收束。",
            component_reason="B05 用 Rve-ProgressSteps 承接 exact 3 steps，避免把所有步骤塞进顶部标题。",
            media_usage="no_external_material",
        )
    return DemoRecipe(
        set_id=set_id,
        main_component_id="conclusion",
        title=title,
        body=body,
        source_label="",
        props={**base_props, "call_to_action": takeaway},
        layers=(
            _layer("Snapcn-TextReveal", "title", title_start, title_end, title, body),
            _layer("Snapcn-TextBuild", "emphasis", emph_start, emph_end, "可以这样做", props={"items": content["items"]}),
        ),
        visual_action="结论主组件给出行动提示，顶部标题说明本段答案，后半段底部用 2 到 3 条行动项收束。",
        component_reason="B06 用 conclusion 承接 takeaway，底部 TextBuild 展示用户传入的行动 items。",
        media_usage="no_external_material",
    )


RICH_NESTED_COMPONENTS: dict[str, tuple[str, ...]] = {
    "B01": ("Rve-QuoteCard", "Rve-StatCounter", "Rve-ProgressSteps"),
    "B02": ("keyword", "Rve-StatCounter", "Snapcn-WordFlip"),
    "B03": ("Rve-SplitScreen", "Rve-ComparisonChart", "Snapcn-TextBuild"),
    "B04": ("Rve-StatCounter", "Rve-ChartAnimation", "Snapcn-TextBuild"),
    "B05": ("Rve-ProgressSteps", "Rve-StatCounter", "Rve-QuoteCard"),
    "B06": ("conclusion", "Bits-ChatConversation", "Rve-StatCounter", "Snapcn-TextBuild"),
    "B07": ("Rve-QuoteCard", "Rve-StatCounter", "Rve-ProgressSteps", "Snapcn-WordFlip"),
    "B08": ("Snapcn-TextBuild", "Rve-ChartAnimation", "Snapcn-WordFlip", "Talkcraft-ink-underline"),
    "B09": ("Rve-SplitScreen", "Rve-StatCounter", "Talkcraft-strike-and-replace"),
    "B10": ("Snapcn-TextBuild", "Rve-StatCounter", "Rve-LineChart", "Talkcraft-ink-underline"),
    "B11": ("Rve-SplitScreen", "Rve-StatCounter", "Snapcn-TextBuild", "Talkcraft-word-slot-cycle"),
    "B12": ("Talkcraft-source-converge", "Rve-StatCounter", "Rve-ProgressSteps", "Snapcn-WordFlip"),
    "B13": ("Snapcn-TextSwap", "Rve-StatCounter", "Talkcraft-error-retype", "Rve-QuoteCard", "Talkcraft-strike-and-replace"),
    "B14": ("Bits-ChatConversation", "Snapcn-TextBuild", "Rve-StatCounter"),
    "B15": ("Rve-ProgressSteps", "Rve-StatCounter", "Rve-ChartAnimation", "Snapcn-TextBuild"),
    "B16": ("Rve-StatCounter", "Snapcn-WordFlip", "Rve-QuoteCard", "Snapcn-TextHighlight"),
    "B17": ("Rve-ProgressSteps", "Rve-StatCounter", "Snapcn-TextBuild"),
    "B18": ("Rve-SplitScreen", "Snapcn-TextSwap", "Rve-ProgressSteps", "Talkcraft-strike-and-replace"),
}
RICH_LAYER_COMPONENTS: dict[str, tuple[str, str]] = {
    "B01": ("Snapcn-SearchTyping", "Snapcn-TextHighlight"),
    "B02": ("Snapcn-TextRewrite", "Snapcn-AnswerHighlight"),
    "B03": ("Snapcn-TextSwap", "Snapcn-TextHighlight"),
    "B04": ("Snapcn-TextRewrite", "Snapcn-TextHighlight"),
    "B05": ("Snapcn-TextBuild", "Snapcn-TextHighlight"),
    "B06": ("Snapcn-TextReveal", "Snapcn-AnswerHighlight"),
    "B07": ("Talkcraft-typewriter-reveal", "Snapcn-TextHighlight"),
    "B08": ("Snapcn-TextBuild", "Snapcn-TextHighlight"),
    "B09": ("Snapcn-TextSwap", "Snapcn-TextHighlight"),
    "B10": ("Snapcn-TextBuild", "Snapcn-TextHighlight"),
    "B11": ("Snapcn-TextBuild", "Snapcn-AnswerHighlight"),
    "B12": ("Snapcn-WordFlip", "Snapcn-TextHighlight"),
    "B13": ("Snapcn-TextRewrite", "Snapcn-TextHighlight"),
    "B14": ("Snapcn-SearchTyping", "Snapcn-AnswerHighlight"),
    "B15": ("Talkcraft-title-demote-to-label", "Snapcn-TextHighlight"),
    "B16": ("Talkcraft-title-demote-to-label", "Talkcraft-keyword-pop-highlight"),
    "B17": ("Talkcraft-line-by-line-slide", "Snapcn-AnswerHighlight"),
    "B18": ("Snapcn-TextSwap", "Snapcn-TextHighlight"),
}
RICH_CONTENT_KEYS: dict[str, tuple[str, ...]] = {
    "B01": ("items", "metric"),
    "B02": ("items", "metric"),
    "B03": ("items", "numeric_items"),
    "B04": ("metric", "numeric_items"),
    "B05": ("items", "metric", "supporting_items"),
    "B06": ("items", "metric", "supporting_items"),
    "B07": ("items", "metric", "numeric_items"),
    "B08": ("items", "metric", "numeric_items"),
    "B09": ("items", "metric", "numeric_items"),
    "B10": ("items", "metric", "numeric_items"),
    "B11": ("items", "metric", "supporting_items"),
    "B12": ("items", "metric", "supporting_items"),
    "B13": ("items", "metric", "supporting_items"),
    "B14": ("items", "metric", "supporting_items"),
    "B15": ("items", "metric", "numeric_items", "supporting_items"),
    "B16": ("items", "metric", "supporting_items"),
    "B17": ("items", "metric", "supporting_items"),
    "B18": ("items", "metric", "numeric_items", "supporting_items"),
}
MATERIAL_RICH_NESTED_COMPONENTS: dict[str, tuple[str, ...]] = {
    "A07": ("Rve-QuoteCard", "Rve-ProgressSteps", "Snapcn-WordFlip", "Talkcraft-source-converge"),
    "A08": ("Rve-ProgressSteps", "Rve-SplitScreen", "Snapcn-WordFlip", "Talkcraft-source-converge"),
    "A09": ("Rve-ProgressSteps", "Rve-StatCounter", "Snapcn-TextBuild", "Snapcn-TextSwap"),
    "A10": ("Rve-ChartAnimation", "Rve-StatCounter", "Snapcn-TextBuild", "Rve-LineChart"),
    "A11": ("Rve-QuoteCard", "Snapcn-WordFlip", "Talkcraft-source-converge", "Talkcraft-ink-underline"),
    "A12": ("Rve-SplitScreen", "Rve-ProgressSteps", "Talkcraft-source-converge", "Snapcn-WordFlip"),
}
MATERIAL_RICH_LAYER_COMPONENTS: dict[str, tuple[str, str]] = {
    "A07": ("Snapcn-TextReveal", "Snapcn-TextHighlight"),
    "A08": ("Snapcn-TextReveal", "Snapcn-TextHighlight"),
    "A09": ("Snapcn-TextReveal", "Snapcn-TextHighlight"),
    "A10": ("Snapcn-TextReveal", "Talkcraft-ink-underline"),
    "A11": ("Snapcn-TextReveal", "Snapcn-TextHighlight"),
    "A12": ("Snapcn-TextReveal", "Snapcn-TextHighlight"),
}


def _unique_components(component_ids: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for component_id in component_ids:
        if component_id not in seen:
            result.append(component_id)
            seen.add(component_id)
    return tuple(result)


def _rich_content(content: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    payload = {"takeaway": content["takeaway"]}
    for key in keys:
        payload[key] = content[key]
    return payload


def _rich_props(set_id: SetId, base_props: dict[str, Any], rich_content: dict[str, Any]) -> dict[str, Any]:
    return {**base_props, "composition": "rich", "rich_content": rich_content}


def _rich_actual_components(set_id: SetId, main_component_id: str) -> tuple[str, ...]:
    title_component, emphasis_component = RICH_LAYER_COMPONENTS[set_id]
    return _unique_components([main_component_id, title_component, emphasis_component, *RICH_NESTED_COMPONENTS[set_id]])


def _material_rich_actual_components(set_id: SetId, main_component_id: str) -> tuple[str, ...]:
    title_component, emphasis_component = MATERIAL_RICH_LAYER_COMPONENTS[set_id]
    return _unique_components([main_component_id, title_component, emphasis_component, *MATERIAL_RICH_NESTED_COMPONENTS[set_id]])


def _answer_highlight_body(content: dict[str, Any]) -> str:
    supporting = content.get("supporting_items")
    if isinstance(supporting, list) and supporting:
        return " / ".join(supporting)
    return content["body"]


def _rich_main_props(set_id: SetId, base_props: dict[str, Any], content: dict[str, Any]) -> dict[str, Any]:
    if set_id in {f"B{index:02d}" for index in range(7, 19)}:
        return base_props
    if set_id == "B02":
        return {**base_props, "keyword": content["takeaway"]}
    if set_id in {"B03", "B05"}:
        return {**base_props, "items": content["items"]}
    if set_id == "B04":
        return {**base_props, "metric": content["metric"]}
    if set_id == "B06":
        return {**base_props, "call_to_action": content["takeaway"]}
    return base_props


def _short_item_label(value: str) -> str:
    return re.split(r"[:：]", value, maxsplit=1)[0][:18]


def _rich_title_props(component_id: str, content: dict[str, Any]) -> dict[str, Any]:
    items = content.get("items") if isinstance(content.get("items"), list) else []
    if component_id in {"Snapcn-TextRewrite", "Snapcn-TextSwap"}:
        from_text = _short_item_label(items[0]) if items else content["title"]
        to_text = _short_item_label(items[1]) if len(items) > 1 else content["takeaway"]
        return {"from_text": from_text, "to_text": to_text}
    if component_id == "Snapcn-WordFlip" and items:
        return {"items": items[:4]}
    if component_id.startswith("Talkcraft-") and items:
        props: dict[str, Any] = {"items": items[:4], "highlight": content["takeaway"]}
        if len(items) >= 1:
            props["from_text"] = items[0]
        if len(items) >= 2:
            props["to_text"] = items[1]
        return props
    return {}


def _rich_emphasis_layer(component_id: str, start: int, end: int, content: dict[str, Any]) -> dict[str, Any]:
    takeaway = content["takeaway"]
    if component_id == "Snapcn-AnswerHighlight":
        return _layer(component_id, "emphasis", start, end, takeaway, _answer_highlight_body(content))
    if component_id == "Talkcraft-keyword-pop-highlight":
        return _layer(component_id, "emphasis", start, end, "先看这一项", props={"highlight": takeaway})
    return _layer(component_id, "emphasis", start, end, "最后记住", props={"highlight": takeaway})


def _b_rich_recipe(set_id: SetId, total_frames: int, content: dict[str, Any]) -> DemoRecipe:
    _, emphasis_window = _windows(total_frames)
    emph_start, emph_end = emphasis_window
    title = content["title"]
    body = content["body"]
    takeaway = content["takeaway"]
    base_props: dict[str, Any] = {"component_set": set_id}
    main_component_id = B_SET_COMPONENTS[set_id]
    title_component, emphasis_component = RICH_LAYER_COMPONENTS[set_id]
    common = {
        "set_id": set_id,
        "main_component_id": main_component_id,
        "title": title,
        "body": body,
        "source_label": "",
        "media_usage": "no_external_material",
        "actual_composition_components": _rich_actual_components(set_id, main_component_id),
    }
    if set_id == "B01":
        props = _rich_props(set_id, base_props, _rich_content(content, ("items", "metric")))
        return DemoRecipe(
            **common,
            props=props,
            layers=(
                _layer(title_component, "title", 0, total_frames, title, body),
                _layer(emphasis_component, "emphasis", emph_start, emph_end, "记住", props={"highlight": takeaway}),
            ),
            visual_action="rich B01 用引用卡建立问题，同时叠加演示数字和三步提示；顶部 SearchTyping 抛出短问题，后半段底部高亮 takeaway。",
            component_reason="B01 rich 由 QuoteCard、StatCounter、ProgressSteps 组成文字+数字+流程表达，适合无素材开场或关键风险提示。",
        )
    if set_id == "B02":
        props = _rich_props(set_id, {**base_props, "keyword": takeaway}, _rich_content(content, ("items", "metric")))
        return DemoRecipe(
            **common,
            props=props,
            layers=(
                _layer(title_component, "title", 0, total_frames, title, body, props={"from_text": title, "to_text": takeaway}),
                _layer(emphasis_component, "emphasis", emph_start, emph_end, takeaway, _answer_highlight_body(content)),
            ),
            visual_action="rich B02 先把复杂概念改写成短句，再用关键词、数字和词语翻转解释这句话为什么要记住。",
            component_reason="B02 rich 由 keyword、StatCounter、WordFlip 组成概念解释和数字辅助，适合把抽象机制讲成可记忆短句。",
        )
    if set_id == "B03":
        props = _rich_props(set_id, {**base_props, "items": content["items"]}, _rich_content(content, ("items", "numeric_items")))
        return DemoRecipe(
            **common,
            props=props,
            layers=(
                _layer(title_component, "title", 0, total_frames, title, body, props={"from_text": content["items"][0], "to_text": content["items"][1]}),
                _layer(emphasis_component, "emphasis", emph_start, emph_end, "对比结论", props={"highlight": takeaway}),
            ),
            visual_action="rich B03 用上下对比区承接两个对象，并用两项同单位数字画出差异，底部收束对比结论。",
            component_reason="B03 rich 由 SplitScreen、ComparisonChart、TextBuild 组成文字对比和数字对比，适合解释两种选择的差别。",
        )
    if set_id == "B04":
        props = _rich_props(set_id, {**base_props, "metric": content["metric"]}, _rich_content(content, ("metric", "numeric_items")))
        return DemoRecipe(
            **common,
            props=props,
            layers=(
                _layer(title_component, "title", 0, total_frames, title, body, props={"from_text": title, "to_text": content["metric"]["value"]}),
                _layer(emphasis_component, "emphasis", emph_start, emph_end, "数字口径", props={"highlight": takeaway}),
            ),
            visual_action="rich B04 用三项同单位数字累加到总数，配合柱/折线动画说明口径，底部提示不要只看单个大数。",
            component_reason="B04 rich 由 StatCounter、ChartAnimation、TextBuild 组成累加数字表达，并强校验 metric 等于 numeric_items 求和。",
        )
    if set_id == "B05":
        props = _rich_props(set_id, {**base_props, "items": content["items"]}, _rich_content(content, ("items", "metric", "supporting_items")))
        return DemoRecipe(
            **common,
            props=props,
            layers=(
                _layer(title_component, "title", 0, total_frames, title, body),
                _layer(emphasis_component, "emphasis", emph_start, emph_end, "最后记住", props={"highlight": takeaway}),
            ),
            visual_action="rich B05 先展示三步流程，再用数字和引用卡补一个判断依据，最后在底部高亮行动提示。",
            component_reason="B05 rich 由 ProgressSteps、StatCounter、QuoteCard 组成流程+数字+解释，适合方法论或避坑步骤。",
        )
    if set_id != "B06":
        main_props = _rich_main_props(set_id, base_props, content)
        props = _rich_props(set_id, main_props, _rich_content(content, RICH_CONTENT_KEYS[set_id]))
        return DemoRecipe(
            **common,
            props=props,
            layers=(
                _layer(title_component, "title", 0, total_frames, title, body, props=_rich_title_props(title_component, content)),
                _rich_emphasis_layer(emphasis_component, emph_start, emph_end, content),
            ),
            visual_action=f"rich {set_id} 使用 {', '.join(_rich_actual_components(set_id, main_component_id))} 组合成无素材文字、数字和提示表达，所有文案和数字来自 content。",
            component_reason=f"{set_id} rich 是登记后的无素材组件套，使用真实 native 组件组合，不绑定外部素材。",
        )
    props = _rich_props(set_id, {**base_props, "call_to_action": takeaway}, _rich_content(content, ("items", "metric", "supporting_items")))
    return DemoRecipe(
        **common,
        props=props,
        layers=(
            _layer(title_component, "title", 0, total_frames, title, body),
            _layer(emphasis_component, "emphasis", emph_start, emph_end, takeaway, _answer_highlight_body(content)),
        ),
        visual_action="rich B06 用结论组件给出行动项，再用模拟聊天和数字辅助解释，底部 AnswerHighlight 收束最终建议。",
        component_reason="B06 rich 由 conclusion、ChatConversation、StatCounter、TextBuild 组成结论+对话+数字+行动项，适合结尾或防骗提示。",
    )


def _material_rich_recipe(set_id: SetId, total_frames: int, content: dict[str, Any], focus_steps: list[dict[str, Any]] | None) -> DemoRecipe:
    _, emphasis_window = _windows(total_frames)
    emph_start, emph_end = emphasis_window
    main_component_id = MATERIAL_RICH_COMPONENTS[set_id]
    title_component, emphasis_component = MATERIAL_RICH_LAYER_COMPONENTS[set_id]
    props: dict[str, Any] = {
        "component_set": set_id,
        "composition": "rich",
        "rich_content": dict(content),
    }
    if focus_steps is not None:
        props["focus_steps"] = focus_steps
    actual = _material_rich_actual_components(set_id, main_component_id)
    return DemoRecipe(
        set_id=set_id,
        main_component_id=main_component_id,
        title=content["title"],
        body=content["body"],
        source_label="",
        props=props,
        layers=(
            _layer(title_component, "title", 0, total_frames, content["title"], content["body"]),
            _layer(emphasis_component, "emphasis", emph_start, emph_end, "最后记住", props={"highlight": content["takeaway"]}),
        ),
        visual_action=f"{set_id} 有素材 rich 样片使用当前任务素材做主画面，叠加 title/emphasis，并用 {', '.join(actual)} 组合展示文案、条目和结论。",
        component_reason=f"{set_id} rich 绑定当前任务素材，文案来自 content，组件组合固定为登记的 7 个 native 组件。",
        requires_video=set_id == "A09",
        actual_composition_components=actual,
    )


def _validate_target_rect(value: object) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
        raise ValueError("教学圈选 target 必须包含 x/y/width/height")
    rect: dict[str, float] = {}
    for key, item in value.items():
        if not isinstance(item, (int, float)) or isinstance(item, bool) or not math.isfinite(item):
            raise ValueError("教学圈选 target 必须是 0 到 1 的数字")
        rect[key] = float(item)
    if (
        rect["x"] < 0
        or rect["y"] < 0
        or rect["width"] <= 0
        or rect["height"] <= 0
        or rect["x"] + rect["width"] > 1
        or rect["y"] + rect["height"] > 1
    ):
        raise ValueError("教学圈选 target 必须完整落在素材画面内")
    return rect


def _validate_tutorial_steps(raw: object, total_frames: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 8:
        raise ValueError("A02 教学步骤需要 1 到 8 段")
    previous = 0
    steps: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"start_frame", "end_frame", "instruction", "target"}:
            raise ValueError("A02 教学步骤字段必须是 start_frame/end_frame/instruction/target")
        start = item["start_frame"]
        end = item["end_frame"]
        instruction = item["instruction"]
        if type(start) is not int or type(end) is not int or start != previous or end <= start or end - start < 30:
            raise ValueError("A02 教学步骤必须连续、半开、每段至少 30 帧")
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 24 or any(ord(char) < 32 and char not in "\t\r\n" for char in instruction):
            raise ValueError("A02 教学口令必须是 24 字以内非空文本")
        steps.append({
            "start_frame": start,
            "end_frame": end,
            "instruction": instruction,
            "target": _validate_target_rect(item["target"]),
        })
        previous = end
    if previous != total_frames:
        raise ValueError("A02 教学步骤必须覆盖整个样片帧段")
    return steps


def _validate_focus_steps(raw: object, total_frames: int) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not 1 <= len(raw) <= 8:
        raise ValueError("重点圈选步骤需要 1 到 8 段")
    previous = 0
    steps: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {"start_frame", "end_frame", "instruction", "target"}:
            raise ValueError("重点圈选步骤字段必须是 start_frame/end_frame/instruction/target")
        start = item["start_frame"]
        end = item["end_frame"]
        instruction = item["instruction"]
        if type(start) is not int or type(end) is not int or start != previous or end <= start or end - start < 30:
            raise ValueError("重点圈选步骤必须连续、半开、每段至少 30 帧")
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 24 or any(ord(char) < 32 and char not in "\t\r\n" for char in instruction):
            raise ValueError("重点圈选口令必须是 24 字以内非空文本")
        steps.append({
            "start_frame": start,
            "end_frame": end,
            "instruction": instruction,
            "target": _validate_target_rect(item["target"]),
        })
        previous = end
    if previous != total_frames:
        raise ValueError("重点圈选步骤必须覆盖整个样片帧段")
    return steps


def _metric_parts(value: object) -> tuple[int, str] | None:
    match = re.fullmatch(r"([0-9]{1,5})([\u4e00-\u9fff]{1,2})", value) if isinstance(value, str) else None
    if not match:
        return None
    number = int(match.group(1))
    if number > 99999:
        return None
    return number, match.group(2)


def _numeric_item_parts(value: object) -> tuple[int, str] | None:
    match = re.fullmatch(r"[^:\n]{1,12}:([0-9]{1,5})([\u4e00-\u9fff]{1,2})", value) if isinstance(value, str) else None
    if not match:
        return None
    number = int(match.group(1))
    if number > 99999:
        return None
    return number, match.group(2)


def _validate_metric(metric: object, *, context: str) -> tuple[int, str]:
    if not isinstance(metric, dict) or set(metric) - {"label", "value", "detail"} or not {"label", "value"} <= set(metric):
        raise ValueError(f"{context} 必须提供 metric")
    parts = _metric_parts(metric.get("value"))
    if parts is None:
        raise ValueError(f"{context} metric.value 必须是 0..99999 的 ASCII 整数加 1 到 2 个汉字单位，不能使用百分比、小数或混合文本")
    return parts


def _validate_numeric_items(items: object, *, count: int, context: str) -> tuple[list[tuple[int, str]], str]:
    if not isinstance(items, list) or len(items) != count:
        raise ValueError(f"{context} numeric_items 必须提供 exactly {count} 项")
    parsed = []
    unit = None
    for item in items:
        parts = _numeric_item_parts(item)
        if parts is None:
            raise ValueError(f"{context} numeric_items 每项必须是 标签:ASCII整数+1到2个汉字单位")
        if unit is None:
            unit = parts[1]
        elif unit != parts[1]:
            raise ValueError(f"{context} numeric_items 必须使用同一个单位")
        parsed.append(parts)
    return parsed, unit or ""


def _validate_basic_b_content(set_id: str, content: dict[str, Any]) -> None:
    items = content.get("items")
    metric = content.get("metric")
    if content.get("numeric_items") is not None or content.get("supporting_items") is not None:
        raise ValueError("basic B 无素材组件套不接受 numeric_items 或 supporting_items")
    if set_id in {"B01", "B02"}:
        if items is not None or metric is not None:
            raise ValueError(f"{set_id} 只接受 title/body/takeaway")
        return
    if set_id == "B03":
        if not isinstance(items, list) or len(items) != 2 or metric is not None:
            raise ValueError("B03 对比组件必须提供 exactly 2 个 items 且不能提供 metric")
        return
    if set_id == "B04":
        if items is not None:
            raise ValueError("B04 数字组件必须只提供 metric")
        _validate_metric(metric, context="B04")
        return
    if set_id == "B05":
        if not isinstance(items, list) or len(items) != 3 or metric is not None:
            raise ValueError("B05 步骤组件必须提供 exactly 3 个 items 且不能提供 metric")
        return
    if set_id == "B06" and (not isinstance(items, list) or not 2 <= len(items) <= 3 or metric is not None):
        raise ValueError("B06 结论组件必须提供 2 到 3 个 items 且不能提供 metric")


def _validate_rich_b_content(set_id: str, content: dict[str, Any], *, duration: float) -> None:
    if duration < 12:
        raise ValueError("rich B 无素材组件套 duration_seconds 至少 12 秒")
    if len(content.get("title", "")) > 18 or len(content.get("body", "")) > 60 or len(content.get("takeaway", "")) > 18:
        raise ValueError("rich content title/body/takeaway 分别不能超过 18/60/18 字")
    items = content.get("items")
    if items is not None and (any(len(item) > 24 for item in items) or sum(len(item) for item in items) > 64):
        raise ValueError("rich items 每项不能超过 24 字且合计不超过 64 字")
    metric = content.get("metric")
    numeric_items = content.get("numeric_items")
    supporting_items = content.get("supporting_items")
    if set_id in {"B01", "B02"}:
        if not isinstance(items, list) or len(items) != 3:
            raise ValueError(f"{set_id} rich 必须提供 exactly 3 个 items")
        metric_parts = _validate_metric(metric, context=f"{set_id} rich")
        if metric_parts[0] != len(items):
            raise ValueError(f"{set_id} rich metric.value 数字必须等于 items 条数")
        if numeric_items is not None or supporting_items is not None:
            raise ValueError(f"{set_id} rich 不接受 numeric_items 或 supporting_items")
        return
    if set_id == "B03":
        if not isinstance(items, list) or len(items) != 2 or metric is not None or supporting_items is not None:
            raise ValueError("B03 rich 必须提供 exactly 2 个 items、exactly 2 个 numeric_items，且不能提供 metric/supporting_items")
        _validate_numeric_items(numeric_items, count=2, context="B03 rich")
        return
    if set_id == "B04":
        if items is not None or supporting_items is not None:
            raise ValueError("B04 rich 不接受 items 或 supporting_items")
        metric_parts = _validate_metric(metric, context="B04 rich")
        numeric_parts, unit = _validate_numeric_items(numeric_items, count=3, context="B04 rich")
        if metric_parts[1] != unit or metric_parts[0] != sum(number for number, _ in numeric_parts):
            raise ValueError("B04 rich metric.value 必须等于 3 个 numeric_items 的同单位求和")
        return
    if set_id == "B05":
        if not isinstance(items, list) or len(items) != 3 or not isinstance(supporting_items, list) or len(supporting_items) != 3:
            raise ValueError("B05 rich 必须提供 exactly 3 个 items 和 exactly 3 个 supporting_items")
        metric_parts = _validate_metric(metric, context="B05 rich")
        if metric_parts[0] != len(items):
            raise ValueError("B05 rich metric.value 数字必须等于 items 条数")
        if numeric_items is not None:
            raise ValueError("B05 rich 不接受 numeric_items")
        return
    if not isinstance(items, list) or not 2 <= len(items) <= 3 or not isinstance(supporting_items, list) or len(supporting_items) != 2:
        raise ValueError("B06 rich 必须提供 2 到 3 个 items 和 exactly 2 个 supporting_items")
    metric_parts = _validate_metric(metric, context="B06 rich")
    if metric_parts[0] != len(items):
        raise ValueError("B06 rich metric.value 数字必须等于 items 条数")
    if numeric_items is not None:
        raise ValueError("B06 rich 不接受 numeric_items")


def _validate_b_content(set_id: str, content: dict[str, Any], *, composition: str, duration: float) -> None:
    if composition == "rich":
        _validate_rich_b_content(set_id, content, duration=duration)
    else:
        _validate_basic_b_content(set_id, content)


def _guided_recipe(total_frames: int, steps: list[dict[str, Any]]) -> DemoRecipe:
    first = steps[0]["instruction"]
    return DemoRecipe(
        set_id="A02",
        main_component_id="Snapcn-PhoneFrame",
        title=first,
        body="模拟 App 操作教学，不代表真实产品",
        source_label="",
        props={
            "content_mode": "media",
            "asset_fit": "contain",
            "start_seconds": 0,
            "end_seconds": total_frames / 30,
            "tutorial_steps": steps,
        },
        layers=(
            _layer("Snapcn-TextReveal", "title", 0, total_frames, first, "", accent_color=GUIDED_ACCENT),
        ),
        visual_action="手机框播放竖屏模拟 App 录屏，标题口令按步骤同步切换，并用橙色手绘圈逐段指向输入框、保存按钮和结果卡片。",
        component_reason="A02 guided 模式用 PhoneFrame 放大模拟 App 操作录屏，只保留一个全时长 TextReveal 标题层，由 tutorial_steps 驱动当前口令和圈选目标。",
        requires_video=True,
        default_duration_seconds=total_frames / 30,
    )


def _focus_recipe(set_id: SetId, total_frames: int, steps: list[dict[str, Any]]) -> DemoRecipe:
    first = steps[0]["instruction"]
    if set_id == "A03":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="video",
            title=first,
            body="",
            source_label="",
            props={"fit": "contain", "start_seconds": 0, "end_seconds": total_frames / 30, "focus_steps": steps},
            layers=(_layer("Snapcn-TextReveal", "title", 0, total_frames, first, "", accent_color=GUIDED_ACCENT),),
            visual_action="操作录屏按原画面 contain 展示，标题跟随当前步骤，用橙色无填充圈指向正在讲的按钮、输入框或结果区域。",
            component_reason="A03 focus 模式保留真实操作录屏完整画面，只用步骤圈注解决标题与画面动作脱节的问题。",
            requires_video=True,
            default_duration_seconds=total_frames / 30,
        )
    if set_id == "A04":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="Talkcraft-tilt-3d-page",
            title=first,
            body="",
            source_label="",
            props={"asset_fit": "contain", "focus_steps": steps},
            layers=(_layer("Snapcn-TextReveal", "title", 0, total_frames, first, "", accent_color=GUIDED_ACCENT),),
            visual_action="作品图以 Tilt 3D Page 展示，标题提示当前观察点，橙色圈注贴在页面上标明结果亮点。",
            component_reason="A04 focus 模式保留作品结果的展示感，同时把观众视线拉到当前讲述的画面细节。",
        )
    if set_id == "A05":
        return DemoRecipe(
            set_id=set_id,
            main_component_id="evidence",
            title=first,
            body="",
            source_label="",
            props={"focus_steps": steps},
            layers=(_layer("Snapcn-TextReveal", "title", 0, total_frames, first, "", accent_color=GUIDED_ACCENT),),
            visual_action="文档图完整 contain 展示，标题同步当前证据点，橙色圈注只标出正在讲的原文位置。",
            component_reason="A05 focus 模式不再使用旧静态 highlight，改为随步骤圈出原文重点，避免控件压住证据内容。",
        )
    return DemoRecipe(
        set_id=set_id,
        main_component_id="image_focus",
        title=first,
        body="",
        source_label="",
        props={"focus_steps": steps},
        layers=(_layer("Snapcn-TextReveal", "title", 0, total_frames, first, "", accent_color=GUIDED_ACCENT),),
        visual_action="关系图完整 contain 展示，标题同步当前关系点，橙色圈注按步骤指向每个节点或连线。",
        component_reason="A06 focus 模式保留关系图全貌，不裁剪不改焦点，只用步骤圈注解释当前关系。",
    )


class ComponentDemoNode:
    """Build a validated reusable component-set timeline and director plan for demo preview."""

    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service

    def __call__(self, state: VideoState) -> dict[str, Any]:
        start_stage(self.repo, state, "director", "组件套样片正在生成导演 Demo 方案")
        try:
            job = self.repo.get_job(state["job_id"])
            request = self._request(state)
            set_id = request["set_id"]
            duration_seconds = 12.0 if set_id == "A03" and not request["has_duration_seconds"] and not request["focus_steps"] else request["duration_seconds"]
            frames = int(math.ceil(duration_seconds * 30))
            if set_id.startswith("B"):
                recipe = _b_rich_recipe(set_id, frames, request["content"]) if request["composition"] == "rich" else _b_recipe(set_id, frames, request["content"])
            elif set_id in MATERIAL_RICH_SET_IDS:
                recipe = _material_rich_recipe(set_id, frames, request["content"], request["focus_steps"])
            elif request["tutorial_steps"]:
                recipe = _guided_recipe(frames, request["tutorial_steps"])
            elif request["focus_steps"]:
                recipe = _focus_recipe(set_id, frames, request["focus_steps"])
            else:
                recipe = _recipe(set_id, frames)
            asset = self._asset(job, request["asset_id"]) if request["asset_id"] is not None else None
            self._validate_asset(job, asset, recipe, duration_seconds, guided=bool(request["tutorial_steps"]), focused=bool(request["focus_steps"]))
            timeline = self._timeline(job, asset, recipe, frames, request)
            metadata = {item.asset_id: self.repo.asset_metadata(item.asset_id) for item in job.assets}
            validate_timeline(timeline, job, metadata)
            required = _required_library_components(job)
            if required:
                validate_component_requirements(timeline, job.brief.usage, required)
            plan = self._plan(job, timeline, recipe, request)
            _validate_director_plan_payload(plan, job, timeline)

            stale = {"preview", "final", "cover", "captions", "review", "package", "storyboard", "timeline", "editing_guidance", "human_review", "component_study", "director_plan"}
            current = self.repo.get_job(job.job_id)
            artifacts = [item for item in current.artifacts if item.kind not in stale]
            job = self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                                       timeline=timeline, review=None, progress=None, artifacts=artifacts,
                                       status="RUNNING", stage="director", message="组件套导演 Demo 方案已生成")
            self.service.write_json(job, f"component-demo-{set_id.lower()}-director-plan.json", plan, "director_plan")
            return state_context(self.repo, state, route="director_demo", gate_issues=[])
        except ValueError as exc:
            return self._request_input(state, str(exc))

    def _request(self, state: VideoState) -> dict[str, Any]:
        raw = (state.get("extras") or {}).get("component_demo")
        if not isinstance(raw, dict):
            raise ValueError("请提供 extras.component_demo，包含 set_id 及对应输入")
        if any(key in raw for key in ("timeline", "shots", "raw_timeline")):
            raise ValueError("组件样片入口不接受外部 timeline 或 shots")
        set_id = raw.get("set_id")
        if set_id not in VALID_SET_IDS:
            raise ValueError("组件样片 set_id 只能是 A01-A12 或 B01-B18")
        asset_id = raw.get("asset_id")
        duration = raw.get("duration_seconds", 10)
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration):
            raise ValueError("组件样片 duration_seconds 必须是 6 到 20 秒")
        if duration < 6 or duration > 20:
            raise ValueError("组件样片 duration_seconds 必须是 6 到 20 秒")
        frames = int(math.ceil(float(duration) * 30))
        tutorial_steps = raw.get("tutorial_steps")
        focus_steps = raw.get("focus_steps")
        composition = raw.get("composition", "basic")
        if composition not in {"basic", "rich"}:
            raise ValueError("组件样片 composition 只能是 basic 或 rich")
        content = raw.get("content")
        if set_id.startswith("B"):
            if asset_id is not None:
                raise ValueError("B 无素材组件套不接受 asset_id")
            if tutorial_steps is not None or focus_steps is not None:
                raise ValueError("B 无素材组件套不接受教学或重点圈选步骤")
            try:
                content_model = ComponentDemoContent.model_validate(content)
            except ValueError as exc:
                raise ValueError(f"B 无素材组件套 content 无效：{exc}") from exc
            try:
                ComponentDemoRequest(
                    base_revision=1,
                    idempotency_key="component-demo-node-validation",
                    set_id=set_id,
                    duration_seconds=float(duration),
                    composition=composition,
                    content=content_model,
                )
            except ValueError as exc:
                raise ValueError(f"B 无素材组件套 content 无效：{exc}") from exc
            content_payload = content_model.model_dump(exclude_none=True)
            return {
                "set_id": set_id,
                "asset_id": None,
                "duration_seconds": float(duration),
                "composition": composition,
                "has_duration_seconds": "duration_seconds" in raw,
                "tutorial_steps": None,
                "focus_steps": None,
                "content": content_payload,
            }
        if set_id in MATERIAL_RICH_SET_IDS:
            if not isinstance(asset_id, str) or not asset_id.strip():
                raise ValueError("组件样片需要指定当前任务已导入的 asset_id")
            if tutorial_steps is not None:
                raise ValueError("A07-A12 rich 素材组件套不接受 tutorial_steps")
            try:
                content_model = ComponentDemoContent.model_validate(content)
            except ValueError as exc:
                raise ValueError(f"{set_id} rich content 无效：{exc}") from exc
            focus_payload = _validate_focus_steps(focus_steps, frames) if focus_steps is not None else None
            try:
                ComponentDemoRequest(
                    base_revision=1,
                    idempotency_key="component-demo-node-validation",
                    set_id=set_id,
                    asset_id=asset_id,
                    duration_seconds=float(duration),
                    composition=composition,
                    content=content_model,
                    focus_steps=focus_payload,
                )
            except ValueError as exc:
                raise ValueError(f"{set_id} rich content 无效：{exc}") from exc
            return {
                "set_id": set_id,
                "asset_id": asset_id,
                "duration_seconds": float(duration),
                "composition": "rich",
                "has_duration_seconds": "duration_seconds" in raw,
                "tutorial_steps": None,
                "focus_steps": focus_payload,
                "content": content_model.model_dump(exclude_none=True),
            }
        if composition != "basic":
            raise ValueError("A01-A06 组件套只支持 basic composition")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError("组件样片需要指定当前任务已导入的 asset_id")
        if content is not None:
            raise ValueError("A 组件套不接受无素材 content")
        if tutorial_steps is not None and set_id != "A02":
            raise ValueError("教学步骤只允许用于 A02 App 对象组件套")
        if focus_steps is not None and set_id not in {"A03", "A04", "A05", "A06"}:
            raise ValueError("重点圈选步骤只允许用于 A03-A06 素材组件套")
        if tutorial_steps is not None and focus_steps is not None:
            raise ValueError("教学步骤和重点圈选步骤不能同时提供")
        return {
            "set_id": set_id,
            "asset_id": asset_id,
            "duration_seconds": float(duration),
            "has_duration_seconds": "duration_seconds" in raw,
            "composition": "basic",
            "tutorial_steps": _validate_tutorial_steps(tutorial_steps, frames) if tutorial_steps is not None else None,
            "focus_steps": _validate_focus_steps(focus_steps, frames) if focus_steps is not None else None,
            "content": None,
        }

    @staticmethod
    def _asset(job: Job, asset_id: str) -> Asset:
        asset = next((item for item in job.assets if item.asset_id == asset_id), None)
        if asset is None:
            raise ValueError("组件样片素材必须来自当前任务已导入的素材")
        return asset

    @staticmethod
    def _metadata_frame_count(metadata: dict[str, Any]) -> int | None:
        for key in ("frame_count", "framecount", "video_frame_count"):
            value = metadata.get(key)
            if type(value) is int and value > 0:
                return value
        return None

    @staticmethod
    def _metadata_frame_rate(metadata: dict[str, Any]) -> float | None:
        value = metadata.get("frame_rate")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            return float(value)
        return None

    @staticmethod
    def _source_label(asset: Asset) -> str:
        host = ""
        if asset.source_url:
            from urllib.parse import urlparse

            host = (urlparse(asset.source_url).hostname or "").removeprefix("www.")
        return f"当前任务素材：{asset.name}" + (f"｜{host}" if host else "")

    def _validate_asset(self, job: Job, asset: Asset | None, recipe: DemoRecipe, duration_seconds: float, *, guided: bool = False, focused: bool = False) -> None:
        if recipe.set_id.startswith("B"):
            if asset is not None:
                raise ValueError("B 无素材组件套不能绑定素材")
            if job.assets:
                raise ValueError("B 无素材组件套只能用于空素材草稿任务")
            return
        if asset is None:
            raise ValueError("组件样片需要指定当前任务已导入的 asset_id")
        if asset.role not in {"evidence", "illustration", "decoration"}:
            raise ValueError("组件样片素材必须是图片或视频素材，不能使用音频")
        safe_media_source(asset.timeline_src, job.job_id)
        if not asset.timeline_src.startswith(f"videoagents/{job.job_id}/assets/"):
            raise ValueError("组件样片素材必须来自当前任务 assets 目录")
        public_path = (self.service.project_root / "public" / asset.timeline_src).resolve()
        public_root = (self.service.project_root / "public" / "videoagents" / job.job_id / "assets").resolve()
        if not public_path.is_relative_to(public_root) or not public_path.is_file():
            raise ValueError("组件样片素材尚未冻结到当前任务 public assets 目录")
        if recipe.set_id in MATERIAL_RICH_SET_IDS:
            metadata = self.repo.asset_metadata(asset.asset_id)
            width = metadata.get("width")
            height = metadata.get("height")
            if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384:
                raise ValueError(f"{recipe.set_id} rich 素材必须带有效实测尺寸元数据")
            if recipe.set_id == "A09":
                actual = metadata.get("duration_seconds")
                frame_count = self._metadata_frame_count(metadata)
                frame_rate = self._metadata_frame_rate(metadata)
                requested_frames = int(math.ceil(duration_seconds * 30))
                if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
                    raise ValueError("A09 rich 必须选择当前任务导入的 MP4 操作录屏")
                if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(actual):
                    raise ValueError("A09 rich 操作录屏缺少有效实测时长")
                if frame_count is None and frame_rate is None:
                    raise ValueError("A09 rich 操作录屏缺少实测 frame_count 或 frame_rate 元数据")
                if frame_count is not None and frame_count < requested_frames:
                    raise ValueError("A09 rich duration_seconds 必须被实测 frame_count/时长覆盖")
                if actual + 0.001 < duration_seconds:
                    raise ValueError("A09 rich duration_seconds 必须被实测 frame_count/时长覆盖")
                return
            if not asset.mime_type.startswith("image/") or not asset.timeline_src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                raise ValueError(f"{recipe.set_id} rich 必须选择当前任务导入的图片素材")
            return
        if guided:
            if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
                raise ValueError("A02 教学演示需要当前任务上传的 MP4 竖屏录屏")
            metadata = self.repo.asset_metadata(asset.asset_id)
            actual = metadata.get("duration_seconds")
            width = metadata.get("width")
            height = metadata.get("height")
            if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(actual):
                raise ValueError("A02 教学录屏缺少有效实测时长")
            if actual + 0.001 < duration_seconds:
                raise ValueError("A02 教学录屏时长不足，无法覆盖组件样片")
            if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384 or height <= width:
                raise ValueError("A02 教学录屏必须带有效竖屏尺寸元数据")
            return
        if focused:
            metadata = self.repo.asset_metadata(asset.asset_id)
            width = metadata.get("width")
            height = metadata.get("height")
            if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384:
                raise ValueError("重点圈选素材必须带有效实测尺寸元数据")
            if recipe.requires_video:
                if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
                    raise ValueError("A03 重点演示需要当前任务上传的 MP4 操作录屏")
                actual = metadata.get("duration_seconds")
                if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(actual):
                    raise ValueError("A03 操作录屏缺少有效实测时长")
                if actual + 0.001 < duration_seconds:
                    raise ValueError("A03 操作录屏时长不足，无法覆盖组件样片")
                return
            if not asset.mime_type.startswith("image/") or not asset.timeline_src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                raise ValueError(f"{recipe.set_id} 重点演示需要当前任务上传的图片素材")
            if recipe.main_component_id == "evidence" and (asset.role != "evidence" or not asset.source_url):
                raise ValueError("A05 模拟文档需按 evidence 素材导入并保留模拟来源 URL")
            return
        if recipe.requires_video:
            if not asset.mime_type.startswith("video/") or not asset.timeline_src.lower().endswith(".mp4"):
                raise ValueError("A03 组件样片需要当前任务上传的 MP4 操作录屏")
            metadata = self.repo.asset_metadata(asset.asset_id)
            actual = metadata.get("duration_seconds")
            if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not math.isfinite(actual):
                raise ValueError("A03 操作录屏缺少有效实测时长")
            if actual + 0.001 < duration_seconds:
                raise ValueError("A03 操作录屏时长不足，无法覆盖组件样片")
            return
        if not asset.mime_type.startswith("image/") or not asset.timeline_src.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            raise ValueError(f"{recipe.set_id} 组件样片需要当前任务上传的图片素材")
        if recipe.main_component_id == "evidence" and (asset.role != "evidence" or not asset.source_url):
            raise ValueError("A05 模拟文档需按 evidence 素材导入并保留模拟来源 URL")

    def _timeline(self, job: Job, asset: Asset | None, recipe: DemoRecipe, frames: int, request: dict[str, Any]) -> Timeline:
        props = dict(recipe.props)
        if request["tutorial_steps"]:
            if asset is None:
                raise ValueError("教学组件样片需要素材")
            metadata = self.repo.asset_metadata(asset.asset_id)
            props["tutorial_source_size"] = {"width": metadata["width"], "height": metadata["height"]}
        if request["focus_steps"]:
            if asset is None:
                raise ValueError("重点圈选组件样片需要素材")
            metadata = self.repo.asset_metadata(asset.asset_id)
            props["focus_source_size"] = {"width": metadata["width"], "height": metadata["height"]}
        layers = [ShotLayer.model_validate(item) for item in recipe.layers]
        shot = Shot(
            shot_id=f"component-demo-{recipe.set_id.lower()}-shot-1",
            start_frame=0,
            end_frame=frames,
            component_id=recipe.main_component_id,
            title=recipe.title,
            body=recipe.body,
            asset_src=asset.timeline_src if asset is not None else None,
            source_label=self._source_label(asset) if recipe.set_id in MATERIAL_RICH_SET_IDS and asset is not None else recipe.source_label,
            accent_color=GUIDED_ACCENT if request["focus_steps"] else "#38BDF8",
            props=props,
            layers=layers,
        )
        return Timeline(
            job_id=job.job_id,
            revision=job.revision,
            width=1080,
            height=1920,
            fps=30,
            presentation="component_sample",
            duration_in_frames=frames,
            audio_src=None,
            shots=[shot],
            captions=[],
        )

    def _segment_performances(self, job: Job, timeline: Timeline, recipe: DemoRecipe) -> list[dict[str, Any]]:
        shot_ids = [shot.shot_id for shot in timeline.shots]
        if job.script and job.script.segments:
            return [
                {
                    "segment_id": segment.segment_id,
                    "shot_ids": shot_ids,
                    "component_reason": recipe.component_reason,
                    "visual_action": recipe.visual_action,
                }
                for segment in job.script.segments
            ]
        return [{
            "segment_id": "component_demo",
            "shot_ids": shot_ids,
            "component_reason": recipe.component_reason,
            "visual_action": recipe.visual_action,
        }]

    def _plan(self, job: Job, timeline: Timeline, recipe: DemoRecipe, request: dict[str, Any]) -> dict[str, Any]:
        duration_seconds = timeline.duration_in_frames / timeline.fps
        plan = {
            "job_id": job.job_id,
            "revision": job.revision,
            "origin": "component_demo",
            "timeline_fingerprint": timeline_fingerprint(timeline),
            "shots": [shot.model_dump(mode="json") for shot in timeline.shots],
            "segment_performances": self._segment_performances(job, timeline, recipe),
            "demo": {
                "start_frame": 0,
                "end_frame": timeline.duration_in_frames,
                "reason": f"组件套 {recipe.set_id} 静音视觉样片，连续 {duration_seconds:.1f} 秒，供导演 Demo 预览。",
            },
            "component_usage": component_requirement_usage(timeline, job.brief.usage, _required_library_components(job)),
            "component_demo_recipe": {
                "recipe_id": f"component-demo-{recipe.set_id}",
                "version": (MATERIAL_RICH_RECIPE_VERSION if recipe.set_id in MATERIAL_RICH_SET_IDS else B_RICH_RECIPE_VERSION if recipe.set_id.startswith("B") and request.get("composition") == "rich" else B_RECIPE_VERSION if recipe.set_id.startswith("B") else RECIPE_VERSION),
                "set_id": recipe.set_id,
                "asset_id": request["asset_id"],
                "duration_seconds": duration_seconds,
                "silent_visual_sample": True,
                "purpose": "生成/模拟素材的组件套视觉样片，用于人工审核组件搭配与空间，不代表真实证据、真实App或已发布成片。",
            },
        }
        if request["content"] is not None:
            plan["component_demo_recipe"]["content"] = request["content"]
            plan["component_demo_recipe"]["no_external_material"] = not recipe.set_id.startswith("A")
            if request.get("composition") == "rich":
                plan["component_demo_recipe"]["composition"] = "rich"
                plan["actual_composition_components"] = list(recipe.actual_composition_components)
                plan["component_demo_recipe"]["actual_composition_components"] = list(recipe.actual_composition_components)
        if request["tutorial_steps"]:
            plan["component_demo_recipe"]["guided_tutorial"] = True
            plan["component_demo_recipe"]["tutorial_steps"] = request["tutorial_steps"]
        if request["focus_steps"]:
            plan["component_demo_recipe"]["guided_focus"] = True
            plan["component_demo_recipe"]["focus_steps"] = request["focus_steps"]
        return plan

    def _request_input(self, state: VideoState, issue: str) -> dict[str, Any]:
        pending = {
            "kind": "input",
            "stage": "director",
            "issues": [issue],
            "fields": ["extras.component_demo"],
            "thread_id": state["thread_id"],
            "revision": state["revision"],
            "pending_token": uuid.uuid4().hex,
            "retry_node": "component_demo",
        }
        self.repo.update_job(state["job_id"], state["revision"], status="NEEDS_INPUT", stage="director",
                             message=issue[:2000], pending_input=pending)
        return state_context(self.repo, state, route="await_input", gate_issues=[issue], pending_snapshot=pending)
