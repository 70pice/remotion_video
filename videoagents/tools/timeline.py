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
    "image_focus": {"focal_x", "focal_y"},
    "comparison": {"left_title", "left_body", "right_title", "right_body"},
    "data": {"items"}, "steps": {"items"}, "conclusion": {"call_to_action"},
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


def validate_timeline(timeline: Timeline, job: Job) -> None:
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
            if asset is None or not asset.mime_type.startswith("image/"):
                raise ValueError("镜头图片必须来自此任务已导入的图片")
            if not re.search(r"\.(png|jpe?g|webp)$", shot.asset_src, re.I):
                raise ValueError("镜头图片扩展名不支持")
        if shot.component_id in {"evidence", "image_focus"} and not shot.asset_src:
            raise ValueError("证据/图片组件需要真实图片")
        if shot.component_id == "evidence":
            asset = known[shot.asset_src]
            if asset.role != "evidence" or not asset.source_url or not shot.source_label.strip():
                raise ValueError("证据镜头必须选择有来源的证据图片并标注出处")
            highlight = shot.props.get("highlight")
            if highlight is not None:
                if not isinstance(highlight, dict) or set(highlight) != {"x", "y", "width", "height"}:
                    raise ValueError("高亮框必须提供 x/y/width/height")
                for key, value in highlight.items():
                    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                        raise ValueError("高亮框坐标必须在 0 到 1 之间")
                if highlight["width"] <= 0 or highlight["height"] <= 0 or highlight["x"] + highlight["width"] > 1 or highlight["y"] + highlight["height"] > 1:
                    raise ValueError("高亮框必须在图片内部且面积非零")
        if shot.component_id == "image_focus":
            for value in shot.props.values():
                if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not 0 <= value <= 1:
                    raise ValueError("图片焦点必须在 0 到 1 之间")
        if shot.component_id == "comparison":
            required = ALLOWED_PROPS["comparison"]
            if set(shot.props) != required or any(not prop_text(value, 48 if key.endswith("title") else 160) for key, value in shot.props.items()):
                raise ValueError("对比画面需要非空四项：标题不超过 48 字、正文不超过 160 字")
        if shot.component_id in {"data", "steps"}:
            items = shot.props.get("items")
            if not isinstance(items, list) or not 1 <= len(items) <= 4:
                raise ValueError("数据/步骤组件需要 1 到 4 项")
            required = {"label", "value"} if shot.component_id == "data" else {"title"}
            allowed = required | ({"detail"} if shot.component_id == "data" else {"body"})
            for item in items:
                limits = {"label": 48, "value": 40, "detail": 64} if shot.component_id == "data" else {"title": 48, "body": 96}
                if not isinstance(item, dict) or not required <= set(item) <= allowed or any(not prop_text(value, limits[key]) for key, value in item.items()):
                    raise ValueError("数据/步骤字段不完整或文字过长")
        for key in {"eyebrow", "keyword", "call_to_action"} & set(shot.props):
            if not prop_text(shot.props[key], {"eyebrow": 48, "keyword": 40, "call_to_action": 72}[key]):
                raise ValueError("组件补充文字为空、过长或含控制字符")
