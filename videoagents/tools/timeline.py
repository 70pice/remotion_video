"""Semantic validation beyond the shared JSON schema."""

import math
import re
from pathlib import PurePosixPath

from videoagents.contracts import Job, Timeline
from videoagents.tools.components import (
    COMMUNITY_COMPONENT_ID_SET,
    component_allowed,
)

ALLOWED_PROPS = {
    "title": {"eyebrow"}, "keyword": {"keyword"}, "evidence": {"highlight"},
    "image_focus": {"focal_x", "focal_y", "crop"},
    "video": {"start_seconds", "end_seconds", "fit", "crop"},
    "comparison": {"left_title", "left_body", "right_title", "right_body", "right_reveal_frame"},
    "data": {"items"}, "steps": {"items", "layout"}, "conclusion": {"call_to_action"},
}
MEDIA_COMPONENT_IDS = frozenset({"video", "evidence", "image_focus"})
MEDIA_COVERAGE_TARGET = 0.7


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
) -> dict[str, object]:
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
            "required": False,
            "segments": [],
        }
    assets_by_src = {asset.timeline_src: asset for asset in job.assets}
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
        linked_ids = set(segment.asset_ids)
        linked_assets = [
            asset
            for asset in job.assets
            if asset.role in {"evidence", "illustration"}
            and asset.mime_type.startswith(("image/", "video/"))
            and (
                asset.asset_id in linked_ids
                or bool(asset.source_url and asset.source_url in segment.source_refs)
            )
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
    used_video_ranges: dict[str, list[tuple[float, float]]] = {}
    for shot in timeline.shots:
        if shot.component_id not in MEDIA_COMPONENT_IDS or not shot.asset_src:
            continue
        asset = assets_by_src.get(shot.asset_src)
        if shot.component_id == "video" and asset is not None:
            start_seconds = shot.props.get("start_seconds", 0)
            if isinstance(start_seconds, (int, float)) and not isinstance(start_seconds, bool):
                end_seconds = float(start_seconds) + (shot.end_frame - shot.start_frame) / timeline.fps
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
            overlap = max(0, min(shot.end_frame, end) - max(shot.start_frame, start))
            if not overlap:
                continue
            if shot.asset_src in eligible[segment_id]:
                linked_frames += overlap
            else:
                unrelated_frames += overlap
        if validate_relationships and not linked_frames:
            raise ValueError("媒体镜头必须与当前旁白段落的 asset_ids 或来源链接语义关联")
        if validate_relationships and unrelated_frames >= 15:
            raise ValueError("媒体镜头跨入了没有语义关联的旁白段落")
        actual_frames += linked_frames
    return {
        "target_ratio": MEDIA_COVERAGE_TARGET,
        "target_frames": target_frames,
        "eligible_capacity_frames": capacity_frames,
        "eligible_capacity_ratio": round(capacity_frames / timeline.duration_in_frames, 4),
        "actual_media_frames": actual_frames,
        "actual_media_ratio": round(actual_frames / timeline.duration_in_frames, 4),
        "required": capacity_frames >= target_frames,
        "segments": segment_reports,
    }


def validate_media_coverage(
    timeline: Timeline,
    job: Job,
    asset_metadata: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    report = media_coverage_report(timeline, job, asset_metadata)
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


def reveal_frame(value: object, duration: int) -> None:
    # 局部帧直接对齐本镜头内的真实口播，末尾保留 15 帧供内容出现。
    if type(value) is not int or not 0 <= value <= duration - 15:
        raise ValueError("展示帧必须是镜头内 0 到镜头时长减 15 的整数")


def validate_timeline(timeline: Timeline, job: Job, asset_metadata: dict[str, dict[str, object]] | None = None) -> None:
    if timeline.job_id != job.job_id:
        raise ValueError("分镜任务身份不匹配")
    if (timeline.width, timeline.height, timeline.fps) != (job.brief.width, job.brief.height, job.brief.fps):
        raise ValueError("分镜尺寸或帧率与任务设置不一致")
    known = {asset.timeline_src: asset for asset in job.assets}
    if timeline.audio_src:
        safe_media_source(timeline.audio_src, job.job_id)
        audio = known.get(timeline.audio_src)
        if audio is None or audio.role != "audio":
            raise ValueError("分镜音频必须来自此任务已导入的音频")
        if not re.search(r"\.(wav|mp3|m4a|aac|ogg)$", timeline.audio_src, re.I):
            raise ValueError("分镜音频扩展名不支持")
    for shot in timeline.shots:
        if not component_allowed(shot.component_id, job.brief.usage):
            raise ValueError(f"组件 {shot.component_id} 的许可不允许当前 {job.brief.usage} 使用场景")
        if shot.component_id in COMMUNITY_COMPONENT_ID_SET:
            if shot.props:
                raise ValueError(f"预设组件 {shot.component_id} 当前不接受自定义 props")
            if shot.asset_src:
                raise ValueError(f"预设组件 {shot.component_id} 使用已核验的内置素材，不接受 asset_src")
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
        if shot.component_id in {"evidence", "image_focus"} and not shot.asset_src:
            raise ValueError("证据/图片组件需要真实图片")
        if shot.component_id == "video":
            if not shot.asset_src:
                raise ValueError("视频组件需要真实视频素材")
            asset = known[shot.asset_src]
            if asset.role not in {"evidence", "illustration"} or not asset.source_url or not shot.source_label.strip():
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
        if shot.component_id == "evidence":
            asset = known[shot.asset_src]
            if asset.role != "evidence" or not asset.source_url or not shot.source_label.strip():
                raise ValueError("证据镜头必须选择有来源的证据图片并标注出处")
            highlight = shot.props.get("highlight")
            if highlight is not None:
                normalized_rect(highlight, "高亮框必须在图片内部且面积非零")
        if shot.component_id == "image_focus":
            for key in {"focal_x", "focal_y"} & set(shot.props):
                value = shot.props[key]
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("图片焦点必须在 0 到 1 之间")
            crop = shot.props.get("crop")
            if crop is not None:
                normalized_rect(crop, "图片裁切框必须在画面内部且面积非零")
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
