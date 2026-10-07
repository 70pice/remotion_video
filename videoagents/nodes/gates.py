"""Deterministic stage checks, registered as nodes alongside production roles."""

import math
import uuid
from typing import Any

from videoagents.contracts import Alignment
from videoagents.nodes.common import current_job, request_input, state_context
from videoagents.nodes.screenwriter import script_issues
from videoagents.nodes.voice import validate_alignment
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline

READING_COMPONENT_IDS = frozenset({"evidence", "image_focus", "comparison", "data", "steps"})
CUED_ENTRANCE_FRAMES = 15


def _explicit_reveals(shot) -> list[tuple[str, int]]:
    """Return renderer-supported local cues that can expose new readable text."""

    if shot.component_id == "comparison" and "right_reveal_frame" in shot.props:
        return [("right_reveal_frame", shot.props["right_reveal_frame"])]
    if shot.component_id in {"data", "steps"}:
        return [
            (f"items[{index}].reveal_frame", item["reveal_frame"])
            for index, item in enumerate(shot.props.get("items", []))
            if "reveal_frame" in item
        ]
    return []


def timeline_readability_issues(timeline) -> list[str]:
    """Reject blink-length shots before a timeline can reach Remotion.

    Every shot needs enough time for the viewer to register the visual.  Shots
    that show evidence, an image crop, a comparison, data/steps, or a visible
    source label need the longer reading window promised by the director and
    editing prompts.  The thresholds scale with the actual timeline FPS.
    """

    normal_frames = math.ceil(1.5 * timeline.fps)
    reading_frames = math.ceil(2.5 * timeline.fps)
    issues = []
    for shot in timeline.shots:
        frames = shot.end_frame - shot.start_frame
        reading = shot.component_id in READING_COMPONENT_IDS or bool(shot.source_label.strip())
        required = reading_frames if reading else normal_frames
        if frames < required:
            kind = "阅读型" if reading else "普通"
            issues.append(
                f"镜头 {shot.shot_id} 只有 {frames} 帧；{kind}镜头至少需要 {required} 帧，"
                "请由导演合并、延长或重新编排，不能让组件或画面一闪而过"
            )
        # Explicitly cued cards spend 15 frames entering before they are fully
        # visible.  Keep the complete reading window after that entrance;
        # otherwise a long shot can still flash its last card at the cut.
        reveal_required = CUED_ENTRANCE_FRAMES + reading_frames
        for field, cue in _explicit_reveals(shot):
            remaining = frames - cue
            if remaining < reveal_required:
                readable = max(0, remaining - CUED_ENTRANCE_FRAMES)
                issues.append(
                    f"镜头 {shot.shot_id} 的 {field} 在局部第 {cue} 帧才开始展示，"
                    f"扣除 {CUED_ENTRANCE_FRAMES} 帧入场后只剩 {readable} 帧完整可读；"
                    f"至少需要 {reading_frames} 帧，请提前揭示、减少内容或延长镜头，"
                    "不能让最后一张卡片在切镜前闪现"
                )
    return issues


class ScriptGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        issues = script_issues(job)
        if issues:
            return request_input(self.repo, state, "script", issues, ["script", "source_urls", "assets"])
        return state_context(self.repo, state, route="voice", gate_issues=[])


class AudioGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        audio = next(item for item in job.assets if item.asset_id == state["audio_asset_id"])
        issues = validate_alignment(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"])
        if issues:
            return request_input(self.repo, state, "voice", issues, ["alignment"])
        if state["action"] == "voice":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="真实音频与时间轴已就绪", stage="voice")
            return state_context(self.repo, state, route="end")
        return state_context(self.repo, state, route="director", gate_issues=[])


class TimelineGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        try:
            metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
            validate_timeline(job.timeline, job, metadata)
        except ValueError as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["timeline"])
        issues = timeline_readability_issues(job.timeline)
        if issues:
            return request_input(self.repo, state, "director", issues, ["timeline"])
        if state["action"] == "storyboard":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="分镜和真实音频时间轴已就绪", stage="director")
            return state_context(self.repo, state, route="end")
        return state_context(self.repo, state, route="reviewers" if state["action"] == "review" else "editing")


class ReviewGateNode:
    def __init__(self, repository: Repository):
        self.repo = repository

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = current_job(self.repo, state)
        hard_errors = [item.message for item in job.review.findings if item.blocking and item.severity == "error"]
        if hard_errors:
            return request_input(self.repo, state, "review", hard_errors, ["review"])
        pending = {"kind": "human_review", "stage": "review", "thread_id": state["thread_id"], "revision": job.revision,
                   "media_sha256": job.review.media_sha256, "dependency_fingerprint": job.review.dependency_fingerprint,
                   "issues": [item.message for item in job.review.findings if item.blocking],
                   "confirmation_requirements": ["完整播放", "事实与截图", "音频与字幕", "排版可读性", "素材及字体用途"],
                   "pending_token": uuid.uuid4().hex}
        job = self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", message="硬检查已通过，等待完整成片的人工复核", pending_input=pending)
        return state_context(self.repo, state, route="await_input", pending_snapshot=pending)
