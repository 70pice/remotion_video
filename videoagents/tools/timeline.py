"""Semantic validation beyond the shared JSON schema."""

import math
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

from videoagents.contracts import Job, Timeline
from videoagents.tools.components import (
    COMMUNITY_COMPONENT_ID_SET,
    component_allowed,
    native_component_capabilities,
)

ALLOWED_PROPS = {
    "title": {"eyebrow"}, "keyword": {"keyword", "component_set", "composition", "rich_content"}, "evidence": {"highlight", "focus_steps", "focus_source_size"},
    "image_focus": {"focal_x", "focal_y", "crop", "focus_steps", "focus_source_size"},
    "video": {"start_seconds", "end_seconds", "fit", "crop", "focus_steps", "focus_source_size"},
    "comparison": {"left_title", "left_body", "right_title", "right_body", "right_reveal_frame"},
    "data": {"items"}, "steps": {"items", "layout"}, "conclusion": {"call_to_action", "component_set", "composition", "rich_content"},
}
COMMUNITY_PRESET_PROPS = {
    "content_mode", "asset_fit", "asset_crop", "start_seconds", "end_seconds", "items", "metric", "tutorial_steps", "tutorial_source_size",
    "focus_steps", "focus_source_size", "component_set", "composition", "rich_content",
}

LAYER_PROP_KEYS = {"items", "before", "highlight", "after", "from_text", "to_text"}
MEDIA_COMPONENT_IDS = frozenset({"video", "evidence", "image_focus"})
FOCUS_COMPONENT_IDS = frozenset({"video", "evidence", "image_focus", "Talkcraft-tilt-3d-page"})
MATERIAL_RICH_SET_IDS = {f"A{index:02d}" for index in range(7, 13)}
MATERIAL_RICH_COMPONENTS = {
    "A07": "Talkcraft-slow-push-in",
    "A08": "Snapcn-PhoneFrame",
    "A09": "Snapcn-PhoneFrame",
    "A10": "Talkcraft-scanline-annotate",
    "A11": "Talkcraft-tilt-3d-page",
    "A12": "Talkcraft-slow-pull-reveal",
}
B_COMPONENT_SET_COMPONENTS = {
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
COMPONENT_SAMPLE_COMPONENTS = {**MATERIAL_RICH_COMPONENTS, **B_COMPONENT_SET_COMPONENTS}
MATERIAL_RICH_EXPECTED_KEYS = {
    "A07": {"title", "body", "takeaway", "items", "supporting_items"},
    "A08": {"title", "body", "takeaway", "items", "supporting_items"},
    "A09": {"title", "body", "takeaway", "items", "supporting_items", "metric"},
    "A10": {"title", "body", "takeaway", "items", "metric", "numeric_items"},
    "A11": {"title", "body", "takeaway", "items", "supporting_items"},
    "A12": {"title", "body", "takeaway", "items", "supporting_items"},
}
MATERIAL_RICH_RULES = {
    "A07": {"items": 3, "supporting": 3},
    "A08": {"items": 3, "supporting": 3},
    "A09": {"items": 3, "supporting": 3, "metric": "items_count"},
    "A10": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "A11": {"items": 3, "supporting": 3},
    "A12": {"items": 3, "supporting": 3},
}
B_RICH_ONLY_SET_IDS = {f"B{index:02d}" for index in range(7, 19)}
B_RICH_EXPECTED_KEYS = {
    "B01": {"takeaway", "items", "metric"},
    "B02": {"takeaway", "items", "metric"},
    "B03": {"takeaway", "items", "numeric_items"},
    "B04": {"takeaway", "metric", "numeric_items"},
    "B05": {"takeaway", "items", "metric", "supporting_items"},
    "B06": {"takeaway", "items", "metric", "supporting_items"},
    "B07": {"takeaway", "items", "metric", "numeric_items"},
    "B08": {"takeaway", "items", "metric", "numeric_items"},
    "B09": {"takeaway", "items", "metric", "numeric_items"},
    "B10": {"takeaway", "items", "metric", "numeric_items"},
    "B11": {"takeaway", "items", "metric", "supporting_items"},
    "B12": {"takeaway", "items", "metric", "supporting_items"},
    "B13": {"takeaway", "items", "metric", "supporting_items"},
    "B14": {"takeaway", "items", "metric", "supporting_items"},
    "B15": {"takeaway", "items", "metric", "numeric_items", "supporting_items"},
    "B16": {"takeaway", "items", "metric", "supporting_items"},
    "B17": {"takeaway", "items", "metric", "supporting_items"},
    "B18": {"takeaway", "items", "metric", "numeric_items", "supporting_items"},
}
B_RICH_RULES = {
    "B01": {"items": 3, "metric": "items_count"},
    "B02": {"items": 3, "metric": "items_count"},
    "B03": {"items": 2, "numeric": 2},
    "B04": {"numeric": 3, "metric": "numeric_sum"},
    "B05": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B06": {"items_range": (2, 3), "supporting": 2, "metric": "items_count"},
    "B07": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "B08": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "B09": {"items": 2, "numeric": 2, "metric": "numeric_diff"},
    "B10": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "B11": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B12": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B13": {"items": 2, "supporting": 3, "metric": "supporting_count"},
    "B14": {"items": 3, "supporting": 2, "metric": "items_count"},
    "B15": {"items": 3, "supporting": 3, "numeric": 3, "metric": "numeric_sum"},
    "B16": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B17": {"items": 3, "supporting": 2, "metric": "items_count"},
    "B18": {"items": 2, "supporting": 3, "numeric": 2, "metric": "supporting_count_and_numeric_max"},
}

MEDIA_COVERAGE_TARGET = 0.7
NON_RENDERABLE_LICENSE_MARKERS = (
    "仅作核验依据",
    "不直接发布",
    "禁止使用",
    "禁止再利用",
)


def _asset_matches_segment(asset, segment) -> bool:
    return asset.asset_id in segment.asset_ids or bool(asset.source_url and asset.source_url in segment.source_refs)


def _context_example_sources(job: Job) -> set[str]:
    """Only media already grounded in this video's script can establish a scene."""
    if not job.script:
        return set()
    return {
        asset.timeline_src for asset in job.assets
        if asset.role in {"evidence", "illustration"}
        and asset.mime_type.startswith(("image/", "video/"))
        and asset_renderable(asset)
        and any(_asset_matches_segment(asset, segment) for segment in job.script.segments)
    }


def _validate_context_example(
    shot, job: Job, known, context_sources: set[str], approved_context_sources: set[str] | None = None,
) -> None:
    if shot.media_usage != "context_example":
        return
    if shot.component_id not in {"image_focus", "video"} | COMMUNITY_COMPONENT_ID_SET:
        raise ValueError("另案示例只能使用图片、视频或原生素材槽组件，不能作为 evidence 证据镜头")
    additionally_approved = bool(shot.asset_src and shot.asset_src in (approved_context_sources or set()))
    if not shot.asset_src or (shot.asset_src not in context_sources and not additionally_approved):
        raise ValueError("另案示例必须来自当前任务文案已关联的真实图片或视频")
    asset = known.get(shot.asset_src)
    if (additionally_approved and shot.asset_src not in context_sources
            and (asset is None or asset.role not in {"evidence", "illustration"}
                 or not asset.mime_type.startswith(("image/", "video/")) or not asset_renderable(asset))):
        raise ValueError("另案示例必须来自当前任务已批准且可渲染的真实图片或视频")
    host = (urlparse(asset.source_url).hostname or "").removeprefix("www.") if asset else ""
    if not host or "另案示例" not in shot.source_label or host not in shot.source_label.lower():
        raise ValueError("另案示例必须在画面 source_label 标明“另案示例”及真实来源域名")
    if (shot.asset_src not in context_sources
            and ("同类" not in shot.source_label
                 or not any(marker in shot.source_label for marker in ("示意", "示例"))
                 or not any(marker in shot.source_label for marker in ("非涉案", "非报告涉案")))):
        raise ValueError("已批准但文案未关联的另案示例必须可见标明同类示意/示例及非涉案")


def asset_renderable(asset) -> bool:
    """Allow pending publication review in drafts; honor explicit use restrictions.

    Rendering a draft does not approve publication or change the original
    license receipt. Only explicit verification-only or prohibited-use assets
    are excluded from Timeline execution and media capacity calculations.
    """

    note = asset.license_note.casefold()
    return not any(marker.casefold() in note for marker in NON_RENDERABLE_LICENSE_MARKERS)


def _normalized(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _script_segment_ranges(timeline: Timeline, job: Job) -> list[tuple[str, int, int]]:
    if not job.script or not timeline.captions:
        return []
    expected = [_normalized(segment.narration) for segment in job.script.segments]
    actual = [_normalized(caption.text) for caption in timeline.captions]
    if not all(expected) or "".join(expected) != "".join(actual):
        return []
    caption_index = 0
    starts: list[int] = []
    for segment_index, text in enumerate(expected):
        if caption_index >= len(timeline.captions):
            return []
        starts.append(
            0
            if segment_index == 0
            else math.floor(timeline.captions[caption_index].start_ms * timeline.fps / 1000)
        )
        consumed = 0
        while consumed < len(text):
            if caption_index >= len(actual) or consumed + len(actual[caption_index]) > len(text):
                return []
            consumed += len(actual[caption_index])
            caption_index += 1
        if consumed != len(text):
            return []
    if caption_index != len(actual):
        return []
    return [
        (
            segment.segment_id,
            starts[index],
            starts[index + 1] if index + 1 < len(starts) else timeline.duration_in_frames,
        )
        for index, segment in enumerate(job.script.segments)
    ]


def media_coverage_report(
    timeline: Timeline,
    job: Job,
    asset_metadata: dict[str, dict[str, object]] | None = None,
    *,
    validate_relationships: bool = True,
    approved_context_sources: set[str] | None = None,
) -> dict[str, object]:
    assets_by_src = {asset.timeline_src: asset for asset in job.assets}
    context_sources = _context_example_sources(job)
    for shot in timeline.shots:
        _validate_context_example(shot, job, assets_by_src, context_sources, approved_context_sources)
    ranges = _script_segment_ranges(timeline, job)
    # The production requirement is strictly greater than 70%, not merely an
    # exact 70% boundary. Frame counts are integers, so advance one frame past
    # floor(70%) for every timeline length.
    target_frames = math.floor(timeline.duration_in_frames * MEDIA_COVERAGE_TARGET) + 1
    if not ranges or not job.script:
        return {
            "target_ratio": MEDIA_COVERAGE_TARGET,
            "target_frames": target_frames,
            "eligible_capacity_frames": 0,
            "eligible_capacity_ratio": 0.0,
            "actual_media_frames": 0,
            "actual_media_ratio": 0.0,
            "source_evidence_frames": 0,
            "context_example_frames": 0,
            "required": False,
            "segments": [],
        }
    remaining_video_frames = {}
    for asset in job.assets:
        duration = (asset_metadata or {}).get(asset.asset_id, {}).get("duration_seconds")
        if (
            asset.mime_type.startswith("video/")
            and isinstance(duration, (int, float))
            and not isinstance(duration, bool)
            and math.isfinite(duration)
            and duration > 0
        ):
            remaining_video_frames[asset.asset_id] = math.floor(duration * timeline.fps)
    eligible: dict[str, set[str]] = {}
    segment_reports = []
    capacity_frames = 0
    for segment, (_, start, end) in zip(job.script.segments, ranges, strict=True):
        linked_assets = [
            asset
            for asset in job.assets
            if asset.role in {"evidence", "illustration"}
            and asset.mime_type.startswith(("image/", "video/"))
            and asset_renderable(asset)
            and _asset_matches_segment(asset, segment)
        ]
        eligible[segment.segment_id] = {asset.timeline_src for asset in linked_assets}
        span = end - start
        if any(asset.mime_type.startswith("image/") for asset in linked_assets):
            capacity = span
        else:
            available_video_frames = 0
            for asset in linked_assets:
                remaining = remaining_video_frames.get(asset.asset_id, 0)
                used = min(max(0, span - available_video_frames), remaining)
                available_video_frames += used
                remaining_video_frames[asset.asset_id] = remaining - used
            capacity = min(span, available_video_frames)
        capacity_frames += capacity
        segment_reports.append({
            "segment_id": segment.segment_id,
            "start_frame": start,
            "end_frame": end,
            "eligible_asset_ids": [
                asset.asset_id for asset in linked_assets
            ],
            "eligible_capacity_frames": capacity,
        })
    actual_frames = 0
    source_evidence_frames = 0
    context_example_frames = 0
    used_video_ranges: dict[str, list[tuple[float, float]]] = {}
    for shot in timeline.shots:
        if not shot.asset_src or (
            shot.component_id not in MEDIA_COMPONENT_IDS
            and shot.component_id not in COMMUNITY_COMPONENT_ID_SET
        ):
            continue
        media_start, media_end = shot.start_frame, shot.end_frame
        if getattr(shot, "set_design", None):
            main = next((part for part in shot.set_design.parts if part.part_id == "main"), None)
            if main is None:
                raise ValueError("组件套媒体覆盖统计缺少已展开的 main 部件")
            media_start = shot.start_frame + main.start_frame
            media_end = shot.start_frame + main.end_frame
        asset = assets_by_src.get(shot.asset_src)
        if asset is not None and asset.mime_type.startswith("video/"):
            start_seconds = shot.props.get("start_seconds", 0)
            if isinstance(start_seconds, (int, float)) and not isinstance(start_seconds, bool):
                start_seconds = float(start_seconds) + (media_start - shot.start_frame) / timeline.fps
                end_seconds = float(start_seconds) + (media_end - media_start) / timeline.fps
                intervals = used_video_ranges.setdefault(asset.asset_id, [])
                if validate_relationships and any(
                    min(end_seconds, previous_end) - max(float(start_seconds), previous_start) > 0.001
                    for previous_start, previous_end in intervals
                ):
                    raise ValueError("同一视频素材不能重复使用相同截取区间凑媒体覆盖率")
                intervals.append((float(start_seconds), end_seconds))
        linked_frames = 0
        unrelated_frames = 0
        for segment_id, start, end in ranges:
            overlap = max(0, min(media_end, end) - max(media_start, start))
            if not overlap:
                continue
            if shot.asset_src in eligible[segment_id] or shot.media_usage == "context_example":
                linked_frames += overlap
            else:
                unrelated_frames += overlap
        if validate_relationships and not linked_frames:
            raise ValueError("媒体镜头必须与当前旁白段落的 asset_ids 或来源链接语义关联")
        if validate_relationships and unrelated_frames >= 15:
            raise ValueError("媒体镜头跨入了没有语义关联的旁白段落")
        actual_frames += linked_frames
        if shot.media_usage == "context_example":
            context_example_frames += linked_frames
        else:
            source_evidence_frames += linked_frames
    return {
        "target_ratio": MEDIA_COVERAGE_TARGET,
        "target_frames": target_frames,
        "eligible_capacity_frames": capacity_frames,
        "eligible_capacity_ratio": round(capacity_frames / timeline.duration_in_frames, 4),
        "actual_media_frames": actual_frames,
        "actual_media_ratio": round(actual_frames / timeline.duration_in_frames, 4),
        "source_evidence_frames": source_evidence_frames,
        "context_example_frames": context_example_frames,
        "required": capacity_frames >= target_frames,
        "segments": segment_reports,
    }


def validate_media_coverage(
    timeline: Timeline,
    job: Job,
    asset_metadata: dict[str, dict[str, object]] | None = None,
    *,
    approved_context_sources: set[str] | None = None,
) -> dict[str, object]:
    report = media_coverage_report(timeline, job, asset_metadata,
                                   approved_context_sources=approved_context_sources)
    if report["required"] and report["actual_media_frames"] < report["target_frames"]:
        actual = float(report["actual_media_ratio"]) * 100
        raise ValueError(
            f"语义关联素材足以覆盖全片超过 70%，实际图片/视频镜头仅覆盖 {actual:.1f}%"
        )
    return report


def safe_media_source(source: str, job_id: str) -> None:
    path = PurePosixPath(source)
    if "\\" in source or "%" in source or ":" in source or path.is_absolute() or ".." in path.parts:
        raise ValueError("媒体路径必须是任务控制的相对路径")
    if not source.startswith(f"videoagents/{job_id}/"):
        raise ValueError("媒体路径不属于此视频任务")
    if len(source) > 512 or any(not re.fullmatch(r"[a-zA-Z0-9_-][a-zA-Z0-9_.-]*", piece) for piece in source.split("/")):
        raise ValueError("媒体路径含非法字符")


def prop_text(value, maximum):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum and not any(ord(char) < 32 and char not in "\t\r\n" for char in value)


def normalized_rect(value: object, message: str) -> None:
    if not isinstance(value, dict) or set(value) != {"x", "y", "width", "height"}:
        raise ValueError(message)
    for item in value.values():
        if not isinstance(item, (int, float)) or isinstance(item, bool) or not math.isfinite(item) or not 0 <= item <= 1:
            raise ValueError(message)
    if value["width"] <= 0 or value["height"] <= 0 or value["x"] + value["width"] > 1 or value["y"] + value["height"] > 1:
        raise ValueError(message)


def _tutorial_source_size(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"width", "height"}:
        raise ValueError("教学录屏尺寸必须包含 width/height")
    width = value["width"]
    height = value["height"]
    if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384 or height <= width:
        raise ValueError("教学录屏必须是有效竖屏尺寸")


def _tutorial_steps(value: object, duration: int) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError("教学步骤需要 1 到 8 段")
    previous = 0
    for item in value:
        if not isinstance(item, dict) or set(item) != {"start_frame", "end_frame", "instruction", "target"}:
            raise ValueError("教学步骤字段必须是 start_frame/end_frame/instruction/target")
        start = item["start_frame"]
        end = item["end_frame"]
        if type(start) is not int or type(end) is not int or start != previous or end <= start or end - start < 30:
            raise ValueError("教学步骤必须连续、半开、每段至少 30 帧")
        if not prop_text(item["instruction"], 24):
            raise ValueError("教学口令必须是 24 字以内非空文本")
        normalized_rect(item["target"], "教学圈选 target 必须完整落在素材画面内")
        previous = end
    if previous != duration:
        raise ValueError("教学步骤必须覆盖整个镜头")


def _focus_source_size(value: object) -> None:
    if not isinstance(value, dict) or set(value) != {"width", "height"}:
        raise ValueError("重点圈选素材尺寸必须包含 width/height")
    width = value["width"]
    height = value["height"]
    if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384:
        raise ValueError("重点圈选素材尺寸必须来自有效元数据")


def _focus_steps(value: object, duration: int) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError("重点圈选步骤需要 1 到 8 段")
    previous = 0
    for item in value:
        if not isinstance(item, dict) or set(item) != {"start_frame", "end_frame", "instruction", "target"}:
            raise ValueError("重点圈选步骤字段必须是 start_frame/end_frame/instruction/target")
        start = item["start_frame"]
        end = item["end_frame"]
        if type(start) is not int or type(end) is not int or start != previous or end <= start or end - start < 30:
            raise ValueError("重点圈选步骤必须连续、半开、每段至少 30 帧")
        if not prop_text(item["instruction"], 24):
            raise ValueError("重点圈选口令必须是 24 字以内非空文本")
        normalized_rect(item["target"], "重点圈选 target 必须完整落在素材画面内")
        previous = end
    if previous != duration:
        raise ValueError("重点圈选步骤必须覆盖整个镜头")


def _validate_tutorial_title_layer(shot, steps: list[dict[str, object]]) -> None:
    layers = getattr(shot, "layers", []) or []
    duration = shot.end_frame - shot.start_frame
    if len(layers) != 1:
        raise ValueError("教学 PhoneFrame 必须只有一个全时长标题层")
    layer = layers[0]
    if (
        _layer_value(layer, "component_id") != "Snapcn-TextReveal"
        or _layer_value(layer, "role") != "title"
        or _layer_value(layer, "start_frame") != 0
        or _layer_value(layer, "end_frame") != duration
    ):
        raise ValueError("教学 PhoneFrame 标题层必须是全时长 Snapcn-TextReveal")
    if _layer_value(layer, "title") != steps[0]["instruction"]:
        raise ValueError("教学 PhoneFrame 初始标题必须等于第一步口令")


def _validate_focus_title_layer(shot, steps: list[dict[str, object]]) -> None:
    layers = getattr(shot, "layers", []) or []
    duration = shot.end_frame - shot.start_frame
    if len(layers) != 1:
        raise ValueError("重点圈选样片必须只有一个全时长标题层")
    layer = layers[0]
    if (
        _layer_value(layer, "component_id") != "Snapcn-TextReveal"
        or _layer_value(layer, "role") != "title"
        or _layer_value(layer, "start_frame") != 0
        or _layer_value(layer, "end_frame") != duration
    ):
        raise ValueError("重点圈选标题层必须是全时长 Snapcn-TextReveal")
    if _layer_value(layer, "title") != steps[0]["instruction"]:
        raise ValueError("重点圈选初始标题必须等于第一步口令")


def _validate_focus_props(shot, *, timeline: Timeline | None = None) -> bool:
    focus_steps = shot.props.get("focus_steps")
    focus_source_size = shot.props.get("focus_source_size")
    if focus_steps is None and focus_source_size is None:
        return False
    is_material_rich_focus = shot.props.get("component_set") == "A09" and shot.component_id == "Snapcn-PhoneFrame"
    if shot.component_id not in FOCUS_COMPONENT_IDS and not is_material_rich_focus:
        raise ValueError("重点圈选步骤只允许用于 A03-A06 素材组件套")
    if focus_steps is None or focus_source_size is None:
        raise ValueError("重点圈选步骤必须同时提供素材尺寸")
    if timeline is not None and timeline.presentation != "component_sample":
        raise ValueError("重点圈选步骤只允许用于组件样片时间轴")
    if timeline is not None and timeline.height <= timeline.width:
        raise ValueError("重点圈选样片必须使用竖屏时间轴")
    if not shot.asset_src:
        raise ValueError("重点圈选样片必须使用当前任务素材")
    if "asset_crop" in shot.props or "crop" in shot.props:
        raise ValueError("重点圈选样片必须完整展示素材，不能裁剪")
    if "highlight" in shot.props or "focal_x" in shot.props or "focal_y" in shot.props:
        raise ValueError("重点圈选样片不能同时传入旧 highlight 或焦点参数")
    if shot.props.get("asset_fit", "contain") != "contain" or shot.props.get("fit", "contain") != "contain":
        raise ValueError("重点圈选样片必须使用 contain 展示素材")
    _focus_source_size(focus_source_size)
    _focus_steps(focus_steps, shot.end_frame - shot.start_frame)
    if not is_material_rich_focus:
        _validate_focus_title_layer(shot, focus_steps)
    return True


def _b_metric_parts(value: object) -> tuple[int, str] | None:
    value_match = re.fullmatch(r"([0-9]{1,5})([\u4e00-\u9fff]{1,2})", value) if isinstance(value, str) else None
    if not value_match:
        return None
    number = int(value_match.group(1))
    if number > 99999:
        return None
    return number, value_match.group(2)


def _b_numeric_item_parts(value: object) -> tuple[int, str] | None:
    value_match = re.fullmatch(r"[^:\n]{1,12}:([0-9]{1,5})([\u4e00-\u9fff]{1,2})", value) if isinstance(value, str) else None
    if not value_match:
        return None
    number = int(value_match.group(1))
    if number > 99999:
        return None
    return number, value_match.group(2)


def _validate_b_metric(metric: object, marker: str) -> tuple[int, str]:
    if not isinstance(metric, dict) or set(metric) - {"label", "value", "detail"} or not {"label", "value"} <= set(metric):
        raise ValueError(f"{marker} metric 字段不符合组件套契约")
    parts = _b_metric_parts(metric.get("value"))
    if not prop_text(metric.get("label"), 24) or parts is None:
        raise ValueError(f"{marker} metric.value 必须是 0..99999 的 ASCII 整数加 1 到 2 个汉字单位")
    if "detail" in metric and not prop_text(metric.get("detail"), 32):
        raise ValueError(f"{marker} metric.detail 必须是短文本")
    return parts


def _validate_b_numeric_items(items: object, marker: str, count: int) -> tuple[list[tuple[int, str]], str]:
    if not isinstance(items, list) or len(items) != count or any(not prop_text(item, 24) for item in items) or sum(len(item) for item in items) > 64:
        raise ValueError(f"{marker} numeric_items 数量或文字长度不符合组件套契约")
    parsed = []
    unit = None
    for item in items:
        parts = _b_numeric_item_parts(item)
        if parts is None:
            raise ValueError(f"{marker} numeric_items 每项必须是 标签:ASCII整数+1到2个汉字单位")
        if unit is None:
            unit = parts[1]
        elif unit != parts[1]:
            raise ValueError(f"{marker} numeric_items 必须使用同一个单位")
        parsed.append(parts)
    return parsed, unit or ""


def _b_expected_count(value: object, expected: int, marker: str, field: str) -> list[str]:
    if not isinstance(value, list) or len(value) != expected or any(not prop_text(item, 24) for item in value) or sum(len(item) for item in value) > 64:
        raise ValueError(f"{marker} rich {field} 必须是 exactly {expected} 条短文本")
    return value


def _b_expected_range(value: object, lower: int, upper: int, marker: str, field: str) -> list[str]:
    if not isinstance(value, list) or not lower <= len(value) <= upper or any(not prop_text(item, 24) for item in value) or sum(len(item) for item in value) > 64:
        raise ValueError(f"{marker} rich {field} 必须是 {lower} 到 {upper} 条短文本")
    return value


def _validate_b_metric_rule(
    marker: str,
    metric_parts: tuple[int, str],
    *,
    rule: object,
    items: list[str] | None,
    supporting: list[str] | None,
    numeric_parts: list[tuple[int, str]] | None,
    numeric_unit: str | None,
) -> None:
    metric_number, metric_unit = metric_parts
    if rule == "items_count":
        if items is None or metric_number != len(items):
            raise ValueError(f"{marker} rich metric.value 数字必须等于 items 条数")
    elif rule == "supporting_count":
        if supporting is None or metric_number != len(supporting):
            raise ValueError(f"{marker} rich metric.value 数字必须等于 supporting_items 条数")
    elif rule == "numeric_sum":
        if numeric_parts is None or numeric_unit is None or metric_unit != numeric_unit or metric_number != sum(number for number, _ in numeric_parts):
            raise ValueError(f"{marker} rich metric.value 必须等于 numeric_items 的同单位求和")
    elif rule == "numeric_diff":
        if numeric_parts is None or numeric_unit is None or len(numeric_parts) != 2 or metric_unit != numeric_unit or metric_number != abs(numeric_parts[1][0] - numeric_parts[0][0]):
            raise ValueError(f"{marker} rich metric.value 必须等于两个 numeric_items 的同单位差值")
    elif rule == "supporting_count_and_numeric_max":
        if supporting is None or metric_number != len(supporting):
            raise ValueError(f"{marker} rich metric.value 数字必须等于 supporting_items 条数")
        if numeric_parts is None or numeric_unit is None or metric_unit != numeric_unit or metric_number != max(number for number, _ in numeric_parts):
            raise ValueError(f"{marker} rich metric.value 必须等于 numeric_items 最大值")
    else:
        raise ValueError(f"{marker} rich metric 规则未登记")


def _validate_b_rich_content(marker: str, shot, rich_content: object, *, sample: bool = True) -> None:
    if not isinstance(rich_content, dict):
        raise ValueError("B rich_content 必须是对象")
    duration_frames = shot.end_frame - shot.start_frame
    if sample and (duration_frames < 360 or duration_frames > 600):
        raise ValueError("B rich 组件套样片时长必须是 12 到 20 秒")
    if not prop_text(shot.title, 18) or not prop_text(shot.body, 60):
        raise ValueError("B rich shot title/body 超出 rich 契约")
    takeaway = rich_content.get("takeaway")
    if not prop_text(takeaway, 18):
        raise ValueError("B rich_content.takeaway 必须是 18 字以内非空文本")
    expected_keys = B_RICH_EXPECTED_KEYS[marker]
    if set(rich_content) != expected_keys:
        raise ValueError(f"{marker} rich_content 字段不符合组件套契约")
    rule = B_RICH_RULES[marker]
    items = None
    if "items" in rule:
        items = _b_expected_count(rich_content.get("items"), int(rule["items"]), marker, "items")
    elif "items_range" in rule:
        lower, upper = rule["items_range"]
        items = _b_expected_range(rich_content.get("items"), int(lower), int(upper), marker, "items")
    elif rich_content.get("items") is not None:
        raise ValueError(f"{marker} rich 不接受 items")
    supporting = None
    if "supporting" in rule:
        supporting = _b_expected_count(rich_content.get("supporting_items"), int(rule["supporting"]), marker, "supporting_items")
    elif rich_content.get("supporting_items") is not None:
        raise ValueError(f"{marker} rich 不接受 supporting_items")
    numeric_parts = None
    numeric_unit = None
    if "numeric" in rule:
        numeric_parts, numeric_unit = _validate_b_numeric_items(rich_content.get("numeric_items"), marker, int(rule["numeric"]))
    elif rich_content.get("numeric_items") is not None:
        raise ValueError(f"{marker} rich 不接受 numeric_items")
    metric_rule = rule.get("metric")
    if metric_rule is None:
        if rich_content.get("metric") is not None:
            raise ValueError(f"{marker} rich 不接受 metric")
    else:
        metric_parts = _validate_b_metric(rich_content.get("metric"), marker)
        _validate_b_metric_rule(marker, metric_parts, rule=metric_rule, items=items, supporting=supporting, numeric_parts=numeric_parts, numeric_unit=numeric_unit)
    if sample and marker == "B02" and shot.props.get("keyword") != takeaway:
        raise ValueError("B02 rich keyword 必须等于 rich_content.takeaway")
    if sample and marker in {"B03", "B05"} and shot.props.get("items") != items:
        raise ValueError(f"{marker} rich props.items 必须等于 rich_content.items")
    if sample and marker == "B04" and shot.props.get("metric") != rich_content.get("metric"):
        raise ValueError(f"{marker} rich props.metric 必须等于 rich_content.metric")
    if sample and marker == "B06" and shot.props.get("call_to_action") != takeaway:
        raise ValueError("B06 rich call_to_action 必须等于 rich_content.takeaway")


def _validate_material_rich_content(marker: str, shot, rich_content: object, *, sample: bool = True) -> None:
    if not isinstance(rich_content, dict):
        raise ValueError("A rich_content 必须是对象")
    duration_frames = shot.end_frame - shot.start_frame
    if sample and (duration_frames < 360 or duration_frames > 600):
        raise ValueError("A rich 组件套样片时长必须是 12 到 20 秒")
    if set(rich_content) != MATERIAL_RICH_EXPECTED_KEYS[marker]:
        raise ValueError(f"{marker} rich_content 字段不符合组件套契约")
    if rich_content.get("title") != shot.title or rich_content.get("body") != shot.body:
        raise ValueError(f"{marker} rich shot title/body 必须等于 rich_content")
    if not prop_text(rich_content.get("title"), 18) or not prop_text(rich_content.get("body"), 60) or not prop_text(rich_content.get("takeaway"), 18):
        raise ValueError("A rich_content title/body/takeaway 必须是 18/60/18 字以内非空文本")
    rule = MATERIAL_RICH_RULES[marker]
    items = _b_expected_count(rich_content.get("items"), int(rule["items"]), marker, "items")
    supporting = None
    if "supporting" in rule:
        supporting = _b_expected_count(rich_content.get("supporting_items"), int(rule["supporting"]), marker, "supporting_items")
    elif rich_content.get("supporting_items") is not None:
        raise ValueError(f"{marker} rich 不接受 supporting_items")
    numeric_parts = None
    numeric_unit = None
    if "numeric" in rule:
        numeric_parts, numeric_unit = _validate_b_numeric_items(rich_content.get("numeric_items"), marker, int(rule["numeric"]))
    elif rich_content.get("numeric_items") is not None:
        raise ValueError(f"{marker} rich 不接受 numeric_items")
    metric_rule = rule.get("metric")
    if metric_rule is None:
        if rich_content.get("metric") is not None:
            raise ValueError(f"{marker} rich 不接受 metric")
    else:
        metric_parts = _validate_b_metric(rich_content.get("metric"), marker)
        _validate_b_metric_rule(marker, metric_parts, rule=metric_rule, items=items, supporting=supporting, numeric_parts=numeric_parts, numeric_unit=numeric_unit)
    if sample and marker == "A09":
        focus_steps = shot.props.get("focus_steps")
        if not isinstance(focus_steps, list) or [item.get("instruction") for item in focus_steps] != items:
            raise ValueError("A09 focus_steps.instruction 必须逐项等于 rich_content.items")


def _metadata_frame_count(metadata: dict[str, object]) -> int | None:
    for key in ("frame_count", "framecount", "video_frame_count"):
        value = metadata.get(key)
        if type(value) is int and value > 0:
            return value
    return None


def _metadata_frame_rate(metadata: dict[str, object]) -> float | None:
    value = metadata.get("frame_rate")
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    return None


def _validate_material_rich_asset(marker: str, shot, asset, metadata: dict[str, object]) -> None:
    width = metadata.get("width")
    height = metadata.get("height")
    if type(width) is not int or type(height) is not int or not 1 <= width <= 16384 or not 1 <= height <= 16384:
        raise ValueError(f"{marker} rich 素材尺寸必须来自当前素材元数据")
    if marker == "A09":
        duration = metadata.get("duration_seconds")
        frame_count = _metadata_frame_count(metadata)
        frame_rate = _metadata_frame_rate(metadata)
        expected_frames = shot.end_frame - shot.start_frame
        if not asset.mime_type.startswith("video/") or not re.search(r"\.mp4$", shot.asset_src or "", re.I):
            raise ValueError("A09 rich 必须使用当前任务 MP4 视频素材")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("A09 rich 视频素材缺少有效实测时长")
        if frame_count is None and frame_rate is None:
            raise ValueError("A09 rich 视频素材缺少实测 frame_count 或 frame_rate 元数据")
        if frame_count is not None and frame_count < expected_frames:
            raise ValueError("A09 rich 视频素材 frame_count 必须覆盖样片帧数")
        if shot.props.get("focus_source_size") != {"width": width, "height": height}:
            raise ValueError("A09 rich focus_source_size 必须等于素材实测尺寸元数据")
        shot_seconds = expected_frames / 30
        if duration + 0.001 < shot_seconds:
            raise ValueError("A09 rich 视频素材实测时长必须覆盖样片区间")
        return
    if not asset.mime_type.startswith("image/") or not re.search(r"\.(png|jpe?g|webp)$", shot.asset_src or "", re.I):
        raise ValueError(f"{marker} rich 必须使用当前任务图片素材")


def _validate_component_sample_marker(shot, *, timeline: Timeline) -> str | None:
    marker = shot.props.get("component_set")
    if marker is None:
        if "composition" in shot.props or "rich_content" in shot.props:
            raise ValueError("composition/rich_content 只允许和 component_set 一起用于组件样片")
        return None
    if marker not in COMPONENT_SAMPLE_COMPONENTS:
        raise ValueError("component_set 只允许已登记组件套标记")
    if timeline.presentation != "component_sample":
        raise ValueError("component_set 标记只允许用于组件样片时间轴")
    if timeline.height <= timeline.width:
        raise ValueError("B 无素材组件套样片必须使用竖屏时间轴")
    if COMPONENT_SAMPLE_COMPONENTS[marker] != shot.component_id:
        raise ValueError("component_set 标记与主组件不匹配")
    props = shot.props
    if marker in MATERIAL_RICH_SET_IDS:
        if not shot.asset_src or not shot.source_label.strip():
            raise ValueError("A rich 有素材组件套必须带 asset_src 和 source_label")
        if props.get("tutorial_steps") is not None:
            raise ValueError("A rich 有素材组件套不能包含 tutorial_steps")
        if marker == "A09":
            expected_keys = {"component_set", "composition", "rich_content", "focus_steps", "focus_source_size"}
        else:
            if props.get("focus_steps") is not None or props.get("focus_source_size") is not None:
                raise ValueError(f"{marker} rich 不接受 focus_steps")
            expected_keys = {"component_set", "composition", "rich_content"}
        if set(props) != expected_keys:
            raise ValueError("A rich 有素材组件套主组件参数不匹配")
        if props.get("composition") != "rich":
            raise ValueError(f"{marker} 只支持 rich composition")
        _validate_material_rich_content(marker, shot, props.get("rich_content"))
        return marker
    if shot.asset_src:
        raise ValueError("B 无素材组件套不能带 asset_src")
    if shot.props.get("tutorial_steps") is not None or shot.props.get("focus_steps") is not None:
        raise ValueError("B 无素材组件套不能包含教学或重点圈选参数")
    basic_expected_keys = {
        "B01": {"component_set"},
        "B02": {"component_set", "keyword"},
        "B03": {"component_set", "items"},
        "B04": {"component_set", "metric"},
        "B05": {"component_set", "items"},
        "B06": {"component_set", "call_to_action"},
        "B07": {"component_set"},
        "B08": {"component_set"},
        "B09": {"component_set"},
        "B10": {"component_set"},
        "B11": {"component_set"},
        "B12": {"component_set"},
        "B13": {"component_set"},
        "B14": {"component_set"},
        "B15": {"component_set"},
        "B16": {"component_set"},
        "B17": {"component_set"},
        "B18": {"component_set"},
    }[marker]
    composition = props.get("composition", "basic")
    if marker in B_RICH_ONLY_SET_IDS and composition != "rich":
        raise ValueError(f"{marker} 只支持 rich composition")
    if composition not in {"basic", "rich"}:
        raise ValueError("B composition 只能是 basic 或 rich")
    expected_keys = basic_expected_keys | ({"composition", "rich_content"} if composition == "rich" else set())
    if set(props) != expected_keys:
        raise ValueError("B 无素材组件套主组件参数不匹配")
    if marker == "B02" and not prop_text(props.get("keyword"), 40):
        raise ValueError("B02 keyword 必须是非空短文本")
    if marker in {"B03", "B05"}:
        expected_count = 2 if marker == "B03" else 3
        items = props.get("items")
        if not isinstance(items, list) or len(items) != expected_count or any(not prop_text(item, 32) for item in items):
            raise ValueError(f"{marker} items 数量或文字长度不符合组件套契约")
    if marker == "B04":
        _validate_b_metric(props.get("metric"), marker)
    if marker == "B06" and not prop_text(props.get("call_to_action"), 72):
        raise ValueError("B06 call_to_action 必须是非空短文本")
    if composition == "rich":
        _validate_b_rich_content(marker, shot, props.get("rich_content"))
    return marker


def reveal_frame(value: object, duration: int) -> None:
    # 局部帧直接对齐本镜头内的真实口播，末尾保留 15 帧供内容出现。
    if type(value) is not int or not 0 <= value <= duration - 15:
        raise ValueError("展示帧必须是镜头内 0 到镜头时长减 15 的整数")


def validate_community_preset_slots(shot) -> None:
    unknown = set(shot.props) - COMMUNITY_PRESET_PROPS
    if unknown:
        raise ValueError(f"预设组件 {shot.component_id} 不接受参数 {', '.join(sorted(unknown))}")
    if shot.props.get("component_set") is None and ("composition" in shot.props or "rich_content" in shot.props):
        raise ValueError("composition/rich_content 只允许用于 B 无素材组件套样片")
    mode = shot.props.get("content_mode")
    if mode is not None and mode not in {"auto", "media", "list", "metric"}:
        raise ValueError("预设组件内容模式只能是 auto、media、list 或 metric")
    fit = shot.props.get("asset_fit", "contain")
    if fit not in {"contain", "cover"}:
        raise ValueError("预设组件素材 fit 只能是 contain 或 cover")
    crop = shot.props.get("asset_crop")
    if crop is not None:
        normalized_rect(crop, "预设组件素材裁剪框必须在画面内部且面积非零")
    tutorial_steps = shot.props.get("tutorial_steps")
    tutorial_source_size = shot.props.get("tutorial_source_size")
    _validate_focus_props(shot)
    if tutorial_steps is not None or tutorial_source_size is not None:
        if shot.component_id != "Snapcn-PhoneFrame":
            raise ValueError("教学步骤只允许用于 PhoneFrame 预设组件")
        if tutorial_steps is None or tutorial_source_size is None:
            raise ValueError("教学步骤必须同时提供录屏尺寸")
        if mode != "media" or fit != "contain" or crop is not None:
            raise ValueError("教学 PhoneFrame 必须使用 media/contain 且不能裁剪素材")
        _tutorial_source_size(tutorial_source_size)
        _tutorial_steps(tutorial_steps, shot.end_frame - shot.start_frame)
        _validate_tutorial_title_layer(shot, tutorial_steps)
    start_seconds = shot.props.get("start_seconds", 0)
    end_seconds = shot.props.get("end_seconds")
    if not isinstance(start_seconds, (int, float)) or isinstance(start_seconds, bool) or not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError("预设组件视频起始时间必须是非负秒数")
    if end_seconds is not None and (
        not isinstance(end_seconds, (int, float))
        or isinstance(end_seconds, bool)
        or not math.isfinite(end_seconds)
        or end_seconds <= start_seconds
    ):
        raise ValueError("预设组件视频结束时间必须晚于起始时间")
    items = shot.props.get("items")
    if items is not None:
        if not isinstance(items, list) or not 1 <= len(items) <= 4 or any(not prop_text(item, 64) for item in items):
            raise ValueError("预设组件内容项需要 1 到 4 条非空短文本")
    metric = shot.props.get("metric")
    if metric is not None:
        required = {"label", "value"}
        allowed = required | {"detail"}
        limits = {"label": 48, "value": 40, "detail": 64}
        if (
            not isinstance(metric, dict)
            or not required <= set(metric) <= allowed
            or any(not prop_text(value, limits[key]) for key, value in metric.items())
        ):
            raise ValueError("预设组件指标需要 label/value 和可选 detail")



def _validate_layer_props(props: object) -> None:
    if props is None:
        return
    if not isinstance(props, dict):
        raise ValueError("层 props 必须是对象")
    unknown = set(props) - LAYER_PROP_KEYS
    if unknown:
        raise ValueError(f"层 props 不接受参数 {', '.join(sorted(unknown))}")
    combined = [props[key] for key in ("before", "highlight", "after") if key in props]
    if any(not prop_text(item, 32) for item in combined) or sum(len(item) for item in combined) > 32:
        raise ValueError("层 before/highlight/after 合计不能超过 32 字")
    for key in {"from_text", "to_text"} & set(props):
        if not prop_text(props[key], 32):
            raise ValueError("层 from_text/to_text 不能超过 32 字")
    items = props.get("items")
    if items is not None:
        if not isinstance(items, list) or not 1 <= len(items) <= 4 or any(not prop_text(item, 64) for item in items) or sum(len(item) for item in items) > 64:
            raise ValueError("层内容项需要 1 到 4 条非空短文本且合计不超过 64 字")

def _layer_value(layer: object, key: str, default: object = None) -> object:
    if isinstance(layer, dict):
        return layer.get(key, default)
    return getattr(layer, key, default)


def _validate_layers(shot) -> None:
    layers = getattr(shot, "layers", []) or []
    if not isinstance(layers, list) or len(layers) > 2:
        raise ValueError("每个镜头最多只能有 2 个文字/强调层")
    duration = shot.end_frame - shot.start_frame
    seen_components: set[str] = set()
    previous_by_role: dict[str, tuple[int, int]] = {}
    for layer in layers:
        role = _layer_value(layer, "role")
        component_id = _layer_value(layer, "component_id")
        if role not in {"title", "emphasis"}:
            raise ValueError("层 role 只能是 title 或 emphasis")
        layer_roles = native_component_capabilities()["layer_roles"]
        if not isinstance(component_id, str) or role not in layer_roles.get(component_id, frozenset()):
            raise ValueError("层组件必须是支持该 role 的原生文字/强调组件")
        if component_id == shot.component_id:
            raise ValueError("组件层不能重复所属镜头组件")
        if component_id in seen_components:
            raise ValueError("同一镜头内层组件不能重复")
        seen_components.add(component_id)
        start = _layer_value(layer, "start_frame")
        end = _layer_value(layer, "end_frame")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= duration:
            raise ValueError("层时间必须是镜头内半开区间")
        if end - start < 30:
            raise ValueError("层最短显示时间为 30 帧")
        previous = previous_by_role.get(role)
        if previous and min(end, previous[1]) > max(start, previous[0]):
            raise ValueError("同一 role 的层时间不能重叠")
        previous_by_role[role] = (start, end)
        title = _layer_value(layer, "title")
        body = _layer_value(layer, "body", "")
        if not prop_text(title, 32) or (body not in {None, ""} and not prop_text(body, 64)):
            raise ValueError("层标题不能超过 32 字，正文不能超过 64 字，且不能含控制字符")
        color = _layer_value(layer, "accent_color", "#38BDF8")
        if not isinstance(color, str) or not re.fullmatch(r"#[a-fA-F0-9]{6}", color):
            raise ValueError("层强调色必须是六位十六进制颜色")
        _validate_layer_props(_layer_value(layer, "props", {}))

def validate_timeline(
    timeline: Timeline, job: Job, asset_metadata: dict[str, dict[str, object]] | None = None,
    *, approved_context_sources: set[str] | None = None,
) -> None:
    if timeline.job_id != job.job_id:
        raise ValueError("分镜任务身份不匹配")
    if (timeline.width, timeline.height, timeline.fps) != (job.brief.width, job.brief.height, job.brief.fps):
        raise ValueError("分镜尺寸或帧率与任务设置不一致")
    known = {asset.timeline_src: asset for asset in job.assets}
    context_sources = _context_example_sources(job)
    if timeline.audio_src:
        safe_media_source(timeline.audio_src, job.job_id)
        audio = known.get(timeline.audio_src)
        if audio is None or audio.role != "audio":
            raise ValueError("分镜音频必须来自此任务已导入的音频")
        if not re.search(r"\.(wav|mp3|m4a|aac|ogg)$", timeline.audio_src, re.I):
            raise ValueError("分镜音频扩展名不支持")
    for shot in timeline.shots:
        _validate_layers(shot)
        _validate_context_example(shot, job, known, context_sources, approved_context_sources)
        if not component_allowed(shot.component_id, job.brief.usage):
            raise ValueError(f"组件 {shot.component_id} 的许可不允许当前 {job.brief.usage} 使用场景")
        _validate_component_sample_marker(shot, timeline=timeline)
        if getattr(shot, "set_design", None) is not None:
            from videoagents.tools.component_sets import validate_component_set_shot

            validate_component_set_shot(job, timeline, shot, asset_metadata)
            continue
        focus_mode = _validate_focus_props(shot, timeline=timeline)
        if shot.component_id in COMMUNITY_COMPONENT_ID_SET:
            guided_tutorial = shot.props.get("tutorial_steps") is not None
            if guided_tutorial and timeline.height <= timeline.width:
                raise ValueError("教学 PhoneFrame 样片必须使用竖屏时间轴")
            validate_community_preset_slots(shot)
            if guided_tutorial and not shot.asset_src:
                raise ValueError("教学 PhoneFrame 必须使用当前任务 MP4 录屏素材")
            if shot.asset_src:
                safe_media_source(shot.asset_src, job.job_id)
                asset = known.get(shot.asset_src)
                if asset is None or not asset.mime_type.startswith(("image/", "video/")):
                    raise ValueError("预设组件素材必须来自此任务已导入的图片或视频")
                if shot.props.get("tutorial_steps") is not None and not asset.mime_type.startswith("video/"):
                    raise ValueError("教学 PhoneFrame 必须使用 MP4 录屏素材")
                if focus_mode and shot.props.get("component_set") != "A09" and not asset.mime_type.startswith("image/"):
                    raise ValueError("重点圈选社区预设必须使用图片素材")
                marker = shot.props.get("component_set")
                if marker in MATERIAL_RICH_SET_IDS:
                    _validate_material_rich_asset(marker, shot, asset, (asset_metadata or {}).get(asset.asset_id, {}))
                if asset.mime_type.startswith("video/"):
                    if shot.props.get("tutorial_steps") is not None:
                        source_size = shot.props["tutorial_source_size"]
                        metadata = (asset_metadata or {}).get(asset.asset_id, {})
                        width = metadata.get("width")
                        height = metadata.get("height")
                        if not (type(width) is int and type(height) is int and width == source_size["width"] and height == source_size["height"] and height > width):
                            raise ValueError("教学录屏尺寸必须来自当前视频素材元数据")
                    if not re.search(r"\.mp4$", shot.asset_src, re.I):
                        raise ValueError("预设组件素材必须是图片或 MP4 视频")
                    start_seconds = shot.props.get("start_seconds", 0)
                    end_seconds = shot.props.get("end_seconds")
                    metadata = (asset_metadata or {}).get(asset.asset_id, {})
                    duration = metadata.get("duration_seconds")
                    if guided_tutorial and duration is None:
                        raise ValueError("教学 PhoneFrame 录屏素材缺少有效实测时长")
                    if duration is not None:
                        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration <= 0:
                            raise ValueError("预设组件视频素材缺少有效实测时长")
                        selected_end = duration if end_seconds is None else end_seconds
                        shot_seconds = (shot.end_frame - shot.start_frame) / timeline.fps
                        if selected_end > duration + 0.001 or selected_end - start_seconds + 0.001 < shot_seconds:
                            raise ValueError("预设组件视频素材截取区间必须在实测时长内并覆盖镜头时长")
                elif not re.search(r"\.(png|jpe?g|webp)$", shot.asset_src, re.I):
                    raise ValueError("预设组件素材必须是图片或 MP4 视频")
                if focus_mode:
                    source_size = shot.props["focus_source_size"]
                    metadata = (asset_metadata or {}).get(asset.asset_id, {})
                    width = metadata.get("width")
                    height = metadata.get("height")
                    if not (type(width) is int and type(height) is int and width == source_size["width"] and height == source_size["height"]):
                        raise ValueError("重点圈选素材尺寸必须来自当前素材元数据")
                if not asset_renderable(asset):
                    raise ValueError("镜头素材的许可回执明确仅供核验或禁止使用，不能进入制作画面")
            continue
        unknown = set(shot.props) - ALLOWED_PROPS[shot.component_id]
        if unknown:
            raise ValueError(f"组件 {shot.component_id} 不接受参数 {', '.join(sorted(unknown))}")
        if shot.asset_src:
            safe_media_source(shot.asset_src, job.job_id)
            asset = known.get(shot.asset_src)
            if shot.component_id == "video":
                if asset is None or not asset.mime_type.startswith("video/"):
                    raise ValueError("镜头视频必须来自此任务已导入的视频")
                if not re.search(r"\.mp4$", shot.asset_src, re.I):
                    raise ValueError("镜头视频扩展名不支持")
            else:
                if asset is None or not asset.mime_type.startswith("image/"):
                    raise ValueError("镜头图片必须来自此任务已导入的图片")
                if not re.search(r"\.(png|jpe?g|webp)$", shot.asset_src, re.I):
                    raise ValueError("镜头图片扩展名不支持")
            if asset is not None and not asset_renderable(asset):
                raise ValueError("镜头素材的许可回执明确仅供核验或禁止使用，不能进入制作画面")
        if shot.component_id in {"evidence", "image_focus"} and not shot.asset_src:
            raise ValueError("证据/图片组件需要真实图片")
        if shot.component_id == "video":
            if not shot.asset_src:
                raise ValueError("视频组件需要真实视频素材")
            asset = known[shot.asset_src]
            if asset.role not in {"evidence", "illustration"} or (not focus_mode and (not asset.source_url or not shot.source_label.strip())):
                raise ValueError("视频镜头必须选择有来源的视频素材并标注出处")
            fit = shot.props.get("fit", "contain")
            if fit not in {"contain", "cover"}:
                raise ValueError("视频 fit 只能是 contain 或 cover")
            start_seconds = shot.props.get("start_seconds", 0)
            end_seconds = shot.props.get("end_seconds")
            if not isinstance(start_seconds, (int, float)) or isinstance(start_seconds, bool) or not math.isfinite(start_seconds) or start_seconds < 0:
                raise ValueError("视频起始时间必须是非负秒数")
            if end_seconds is not None and (not isinstance(end_seconds, (int, float)) or isinstance(end_seconds, bool) or not math.isfinite(end_seconds) or end_seconds <= start_seconds):
                raise ValueError("视频结束时间必须晚于起始时间")
            metadata = (asset_metadata or {}).get(asset.asset_id, {})
            duration = metadata.get("duration_seconds")
            if asset_metadata is not None and duration is None:
                raise ValueError("视频素材缺少有效实测时长")
            if duration is not None:
                if not isinstance(duration, (int, float)) or isinstance(duration, bool) or not math.isfinite(duration) or duration <= 0:
                    raise ValueError("视频素材缺少有效实测时长")
                selected_end = duration if end_seconds is None else end_seconds
                shot_seconds = (shot.end_frame - shot.start_frame) / timeline.fps
                if selected_end > duration + 0.001 or selected_end - start_seconds + 0.001 < shot_seconds:
                    raise ValueError("视频素材截取区间必须在实测时长内并覆盖镜头时长")
            crop = shot.props.get("crop")
            if crop is not None:
                normalized_rect(crop, "视频裁剪框必须在画面内部且面积非零")
            if focus_mode:
                source_size = shot.props["focus_source_size"]
                metadata = (asset_metadata or {}).get(asset.asset_id, {})
                width = metadata.get("width")
                height = metadata.get("height")
                if not (type(width) is int and type(height) is int and width == source_size["width"] and height == source_size["height"]):
                    raise ValueError("重点圈选素材尺寸必须来自当前素材元数据")
        if shot.component_id == "evidence":
            asset = known[shot.asset_src]
            if asset.role != "evidence" or not asset.source_url or (not focus_mode and not shot.source_label.strip()):
                raise ValueError("证据镜头必须选择有来源的证据图片并标注出处")
            highlight = shot.props.get("highlight")
            if highlight is not None:
                normalized_rect(highlight, "高亮框必须在图片内部且面积非零")
            if focus_mode:
                source_size = shot.props["focus_source_size"]
                metadata = (asset_metadata or {}).get(asset.asset_id, {})
                width = metadata.get("width")
                height = metadata.get("height")
                if not (type(width) is int and type(height) is int and width == source_size["width"] and height == source_size["height"]):
                    raise ValueError("重点圈选素材尺寸必须来自当前素材元数据")
        if shot.component_id == "image_focus":
            for key in {"focal_x", "focal_y"} & set(shot.props):
                value = shot.props[key]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("图片焦点必须在 0 到 1 之间")
            crop = shot.props.get("crop")
            if crop is not None:
                normalized_rect(crop, "图片裁切框必须在画面内部且面积非零")
            if focus_mode:
                source_size = shot.props["focus_source_size"]
                metadata = (asset_metadata or {}).get(asset.asset_id, {})
                width = metadata.get("width")
                height = metadata.get("height")
                if not (type(width) is int and type(height) is int and width == source_size["width"] and height == source_size["height"]):
                    raise ValueError("重点圈选素材尺寸必须来自当前素材元数据")
        if shot.component_id == "comparison":
            required = {"left_title", "left_body", "right_title", "right_body"}
            if not required <= set(shot.props) or any(not prop_text(shot.props[key], 48 if key.endswith("title") else 160) for key in required):
                raise ValueError("对比画面需要非空四项：标题不超过 48 字、正文不超过 160 字")
            if "right_reveal_frame" in shot.props:
                reveal_frame(shot.props["right_reveal_frame"], shot.end_frame - shot.start_frame)
        if shot.component_id in {"data", "steps"}:
            items = shot.props.get("items")
            if not isinstance(items, list) or not 1 <= len(items) <= 4:
                raise ValueError("数据/步骤组件需要 1 到 4 项")
            required = {"label", "value"} if shot.component_id == "data" else {"title"}
            allowed = required | ({"detail"} if shot.component_id == "data" else {"body"}) | {"reveal_frame"}
            if shot.component_id == "steps":
                layout = shot.props.get("layout", "cards")
                if not isinstance(layout, str) or layout not in {"cards", "flow"}:
                    raise ValueError("步骤布局只能是 cards 或 flow")
            previous_cue = 0
            for item in items:
                limits = {"label": 48, "value": 40, "detail": 64} if shot.component_id == "data" else {"title": 48, "body": 96}
                if not isinstance(item, dict) or not required <= set(item) <= allowed or any(not prop_text(value, limits[key]) for key, value in item.items() if key != "reveal_frame"):
                    raise ValueError("数据/步骤字段不完整或文字过长")
                cue = item.get("reveal_frame", 0)
                if "reveal_frame" in item:
                    reveal_frame(cue, shot.end_frame - shot.start_frame)
                if cue < previous_cue:
                    raise ValueError("内容项的展示帧必须按顺序非递减；未设置时按 0 计算")
                previous_cue = cue
        for key in {"eyebrow", "keyword", "call_to_action"} & set(shot.props):
            if not prop_text(shot.props[key], {"eyebrow": 48, "keyword": 40, "call_to_action": 72}[key]):
                raise ValueError("组件补充文字为空、过长或含控制字符")
