"""Production kits: fixed native composition, current content, bounded director adjustments."""

import json
import math
from hashlib import sha256
from typing import Any

from videoagents.contracts import Asset, ComponentSetDesign, Job, Shot, Timeline
from videoagents.default_config import PROJECT_ROOT

CAPABILITIES_PATH = PROJECT_ROOT / "videoagents" / "component-set-capabilities.json"


def component_set_templates() -> dict[str, dict[str, Any]]:
    payload = json.loads(CAPABILITIES_PATH.read_text(encoding="utf-8"))
    return {item["set_id"]: item for item in payload["sets"]}


def component_set_fingerprint() -> str:
    return sha256(CAPABILITIES_PATH.read_bytes()).hexdigest()


def allowed_component_set_templates(usage: str) -> dict[str, dict[str, Any]]:
    from videoagents.tools.components import component_allowed

    return {
        set_id: template for set_id, template in component_set_templates().items()
        if component_allowed(template["main_component_id"], usage)
        and all(component_allowed(part["component_id"], usage) for part in template["parts"])
    }


def resolve_component_set_shots(shots: list[Shot], assets: list[Asset],
                                asset_metadata: dict[str, dict[str, Any]]) -> list[Shot]:
    """Expand only layout defaults; never synthesize facts, source refs or focus targets."""

    templates = component_set_templates()
    known = {asset.timeline_src: asset for asset in assets}
    resolved = []
    for shot in shots:
        if shot.set_design is None:
            resolved.append(shot)
            continue
        design = shot.set_design.model_dump(mode="json")
        template = templates[design["set_id"]]
        duration = shot.end_frame - shot.start_frame
        overrides = {part["part_id"]: part for part in design["parts"]}
        allowed = {part["part_id"] for part in template["parts"]}
        if set(overrides) - allowed:
            raise ValueError("组件套含未登记 part_id")
        design["parts"] = [overrides.get(part["part_id"], {
            "part_id": part["part_id"], "box": part["box"],
            "start_frame": math.floor(duration * part["start_ratio"]),
            "end_frame": math.ceil(duration * part["end_ratio"]),
        }) for part in template["parts"]]
        asset = known.get(shot.asset_src)
        metadata = asset_metadata.get(asset.asset_id, {}) if asset else {}
        if design.get("source_size") is None and type(metadata.get("width")) is int and type(metadata.get("height")) is int:
            design["source_size"] = {"width": metadata["width"], "height": metadata["height"]}
        resolved.append(Shot.model_validate({**shot.model_dump(mode="json"), "set_design": design}))
    return resolved


def component_set_part_text(shot: Shot, binding: str) -> str:
    if binding in {"title", "body"}:
        return getattr(shot, binding)
    if binding == "media":
        return ""
    value: Any = shot.set_design.content.model_dump(mode="json") if shot.set_design else {}
    for key in binding.split("."):
        if isinstance(value, dict):
            value = value.get(key, "")
        elif isinstance(value, list) and key.isdigit():
            value = value[int(key)] if int(key) < len(value) else ""
        else:
            return ""
    if isinstance(value, dict):
        return " ".join(str(text) for text in value.values() if text)
    if isinstance(value, list):
        return " ".join(str(text) for text in value)
    return str(value or "")


def validate_component_set_content(shot: Shot) -> None:
    from videoagents.tools.timeline import (
        B_RICH_RULES,
        MATERIAL_RICH_RULES,
        _validate_b_rich_content,
        _validate_material_rich_content,
    )

    design = shot.set_design
    if not design:
        return
    content = design.content.model_dump(mode="json", exclude_defaults=True)
    content.pop("source_refs", None)
    if content.get("metric", {}).get("detail") == "":
        content["metric"].pop("detail", None)
    if design.set_id in B_RICH_RULES:
        _validate_b_rich_content(design.set_id, shot, content, sample=False)
    elif design.set_id in MATERIAL_RICH_RULES:
        _validate_material_rich_content(design.set_id, shot,
                                        {**content, "title": shot.title, "body": shot.body}, sample=False)
    elif not shot.title.strip() or len(shot.title) > 32 or len(design.content.takeaway) > 32:
        raise ValueError("素材组件套标题与结论必须是可读短句")
    for text in [shot.title, *([shot.body] if shot.body else []), design.content.takeaway,
                 *design.content.items, *design.content.supporting_items, *design.content.numeric_items]:
        if not text.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in text):
            raise ValueError("组件套内容不能为空或含控制字符")


def validate_component_set_layout(shot: Shot, *, fps: int = 30) -> None:
    design = shot.set_design
    if not design:
        return
    template = component_set_templates()[design.set_id]
    if shot.component_id != template["main_component_id"]:
        raise ValueError("组件套主 component_id 与所选套不匹配")
    expected = {part["part_id"]: part for part in template["parts"]}
    parts = design.parts
    if {part.part_id for part in parts} != set(expected) or len(parts) != len(expected):
        raise ValueError("组件套必须展开全部登记 parts，不能添加或遗漏组件")
    duration = shot.end_frame - shot.start_frame
    for index, part in enumerate(parts):
        definition = expected[part.part_id]
        text = component_set_part_text(shot, definition["binding"])
        if definition["binding"] != "media" and not text.strip():
            raise ValueError(f"{design.set_id}.{part.part_id} 缺少本期真实内容")
        entrance = 0 if definition["binding"] == "media" else math.ceil(fps * 0.5)
        minimum = entrance + max(math.ceil(fps * 1.5), math.ceil(len(text.replace(" ", "")) / 12 * fps))
        if part.end_frame > duration or part.end_frame - part.start_frame < minimum:
            raise ValueError(f"{design.set_id}.{part.part_id} 显示区间不足阅读或超出镜头")
        # Normalized bounds are enforced by the shared contract. Reject boxes
        # too small to host native large-copy panels at the production resolution.
        if part.box.width < 0.18 or part.box.height < 0.045:
            raise ValueError(f"{design.set_id}.{part.part_id} 尺寸不足阅读")
        for other in parts[:index]:
            if min(part.end_frame, other.end_frame) <= max(part.start_frame, other.start_frame):
                continue
            a, b = part.box, other.box
            overlap_x = min(a.x + a.width, b.x + b.width) - max(a.x, b.x)
            overlap_y = min(a.y + a.height, b.y + b.height) - max(a.y, b.y)
            if overlap_x > 0.000001 and overlap_y > 0.000001:
                raise ValueError("同时显示的组件不能相互遮挡")
    validate_component_set_content(shot)


def validate_component_set_shot(job: Job, timeline: Timeline, shot: Shot,
                                asset_metadata: dict[str, dict[str, Any]] | None = None) -> None:
    from videoagents.tools.timeline import asset_renderable, safe_media_source

    design: ComponentSetDesign | None = shot.set_design
    if not design:
        return
    if timeline.presentation != "production" or (timeline.width, timeline.height, timeline.fps) != (1080, 1920, 30):
        raise ValueError("生产组件套只允许用于 1080×1920、30fps 的普通生产时间轴")
    templates = allowed_component_set_templates(job.brief.usage)
    if design.set_id not in templates:
        raise ValueError("组件套未开放当前任务用途")
    template = templates[design.set_id]
    if shot.layers:
        raise ValueError("组件套不能额外叠加 layers")
    unknown = set(shot.props) - {"start_seconds", "end_seconds", "fit", "asset_fit"}
    if unknown:
        raise ValueError("组件套只接受媒体截取/适配 props，内容和布局通过 set_design 传入")
    validate_component_set_layout(shot, fps=timeline.fps)
    refs = set(job.brief.source_urls)
    refs.update(asset.source_url for asset in job.assets if asset.source_url)
    if job.script:
        refs.update(ref for segment in job.script.segments for ref in segment.source_refs)
    if any(ref not in refs for ref in design.content.source_refs):
        raise ValueError("组件套 source_refs 必须来自当前任务已记录来源")
    if design.content.numeric_items and not design.content.source_refs:
        raise ValueError("数字组件套必须传入本期 source_refs，不能照搬演示数字")
    kind = template["material_kind"]
    asset = next((asset for asset in job.assets if asset.timeline_src == shot.asset_src), None)
    if kind == "none":
        if shot.asset_src or design.focus_steps or design.source_size or shot.props:
            raise ValueError("无素材组件套不能混入素材或媒体参数")
        return
    if not shot.asset_src:
        raise ValueError("有素材组件套必须传入当前任务素材")
    safe_media_source(shot.asset_src, job.job_id)
    if asset is None or not asset.mime_type.startswith(("image/", "video/")) or not asset_renderable(asset):
        raise ValueError("组件套素材必须来自当前任务可用的图片或视频")
    if not shot.source_label.strip():
        raise ValueError("有素材组件套必须标明当前素材出处")
    if shot.component_id == "evidence" and (asset.role != "evidence" or not asset.source_url):
        raise ValueError("证据组件套必须使用有真实来源的证据图片")
    is_video = asset.mime_type.startswith("video/")
    if (kind == "image" and is_video) or (kind == "video" and not is_video):
        raise ValueError("当前素材类型不适合所选组件套")
    if (is_video and not shot.asset_src.lower().endswith(".mp4")) or (
        not is_video and not shot.asset_src.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    ):
        raise ValueError("组件套只支持可渲染图片和 MP4")
    fit = shot.props.get("fit", shot.props.get("asset_fit", "contain"))
    if fit not in {"contain", "cover"} or (design.focus_steps and fit != "contain"):
        raise ValueError("媒体 fit 无效，圈选引导必须完整展示素材")
    metadata = (asset_metadata or {}).get(asset.asset_id, {})
    if is_video:
        start = shot.props.get("start_seconds", 0)
        end = shot.props.get("end_seconds", metadata.get("duration_seconds"))
        duration = metadata.get("duration_seconds")
        if any(not isinstance(value, (float, int)) or isinstance(value, bool) or not math.isfinite(value)
               for value in (start, end, duration)):
            raise ValueError("视频素材缺少有效实测时长或截取区间")
        if start < 0 or end > duration + 0.001 or end - start + 0.001 < (shot.end_frame - shot.start_frame) / timeline.fps:
            raise ValueError("视频素材截取区间必须覆盖镜头，不能循环凑时长")
    elif shot.props.keys() & {"start_seconds", "end_seconds"}:
        raise ValueError("图片素材不能设置视频截取区间")
    if design.source_size:
        if (design.source_size.width, design.source_size.height) != (metadata.get("width"), metadata.get("height")):
            raise ValueError("source_size 必须等于当前素材实测尺寸")
    if design.set_id == "A09" and not design.focus_steps:
        raise ValueError("操作跟随组件套必须传入与真实视频状态同步的 focus_steps")
    if design.focus_steps:
        if not template.get("focus_supported", False):
            raise ValueError("所选组件套尚不支持生产素材圈选")
        if not design.source_size:
            raise ValueError("素材圈选必须提供实测 source_size")
        previous = 0
        for step in design.focus_steps:
            if step.start_frame != previous or step.end_frame - step.start_frame < 30:
                raise ValueError("素材引导步骤必须连续且够读，不能留空或重叠")
            previous = step.end_frame
        if previous != shot.end_frame - shot.start_frame:
            raise ValueError("素材引导步骤必须覆盖镜头区间")
        if design.set_id == "A09" and [step.instruction for step in design.focus_steps] != design.content.items:
            raise ValueError("操作跟随口令必须与 items 逐项一致")
