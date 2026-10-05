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
    for key, item in value.items():
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
