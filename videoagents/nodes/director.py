"""Model-assisted shot choices, grounded in actual audio boundaries and real assets."""

import json
import math
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, model_validator

from videoagents.contracts import Alignment, Asset, Caption, Job, Shot, Timeline
from videoagents.nodes.common import (
    agent_state,
    mark_feedback_applied,
    needs_script_revision,
    request_input,
    stage_feedback,
    start_stage,
    state_context,
)
from videoagents.nodes.gates import timeline_readability_issues
from videoagents.prompts import render as render_prompt
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.tools.components import (
    available_component_ids,
    prompt_component_catalog,
    prompt_scene_playbook,
)
from videoagents.tools.timeline import (
    asset_renderable,
    media_coverage_report,
    validate_media_coverage,
    validate_timeline,
)

COMPONENT_PROPS_EXAMPLES = {
    "title": {"eyebrow": "给定主题"}, "keyword": {"keyword": "给定关键词"},
    "evidence": {"highlight": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
    # 裁剪仅演示参数形状；导演必须使用对应素材经像素核验的区域。
    "image_focus": {"focal_x": 0.5, "focal_y": 0.5,
                    "crop": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
    "video": {"start_seconds": 0, "end_seconds": 4.2, "fit": "contain",
              "crop": {"x": 0.2, "y": 0.0, "width": 0.6, "height": 1.0}},
    "comparison": {"left_title": "给定左标题", "left_body": "给定左正文",
                   "right_title": "给定右标题", "right_body": "给定右正文", "right_reveal_frame": 15},
    # 局部帧只是参数形状示例；真实揭示时机由导演根据当前镜头和实测字幕选择。
    "data": {"items": [
        {"label": "来源中的第一标签", "value": "来源中的第一值", "detail": "来源中的第一说明", "reveal_frame": 0},
        {"label": "来源中的第二标签", "value": "来源中的第二值", "detail": "来源中的第二说明", "reveal_frame": 15},
    ]},
    "steps": {"layout": "flow", "items": [
        {"title": "给定第一步骤", "body": "给定第一说明", "reveal_frame": 0},
        {"title": "给定第二步骤", "body": "给定第二说明", "reveal_frame": 15},
    ]},
    "conclusion": {"call_to_action": "文案中的行动建议"},
}


class DirectorPlan(BaseModel):
    """导演只交付镜头；实测音频、字幕和画幅由程序合入最终 Timeline。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    shots: list[Shot] = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def minimum_shot_length(self) -> "DirectorPlan":
        if any(shot.end_frame - shot.start_frame < 15 for shot in self.shots):
            raise ValueError("镜头至少需要 15 帧")
        return self


def production_portrait(job: Job) -> bool:
    return (job.brief.width, job.brief.height, job.brief.fps) == (1080, 1920, 30)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "素材来源")[:160]


def _video_covers(asset: Asset, metadata: dict[str, dict[str, Any]], shot_seconds: float) -> bool:
    duration = metadata.get(asset.asset_id, {}).get("duration_seconds")
    return isinstance(duration, (int, float)) and not isinstance(duration, bool) and math.isfinite(duration) and duration >= shot_seconds


def director_prompt(usage: str) -> str:
    """Build the complete component guide for this job's license context."""

    return render_prompt(
        "director",
        component_props=json.dumps(COMPONENT_PROPS_EXAMPLES, ensure_ascii=False, separators=(",", ":")),
        component_scene_playbook=prompt_scene_playbook(usage),
        component_catalog=prompt_component_catalog(usage),
    )


# Compatibility for tests and callers that import the default prompt. Jobs
# with an explicit commercial usage receive a license-filtered prompt at call
# time instead.
PROMPT = director_prompt("unspecified")


class DirectorNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "director", "导演根据实测旁白安排镜头与关键画面")
        try:
            feedback_stage = "render" if stage_feedback(state, "render") else "director"
            feedback = stage_feedback(state, feedback_stage)
            if feedback and feedback.get("note") and self._needs_script_revision(feedback["note"]):
                return state_context(self.repo, state, route="screenwriter", gate_issues=[])
            if feedback and feedback.get("note") and self._needs_voice_revision(feedback["note"]):
                return request_input(self.repo, state, "voice",
                    ["成片返工意见涉及语速、发音或音频，导演无法只靠镜头修复；请先调整配音后重新制作。"],
                    ["voice", "timeline"])
            audio = next(item for item in job.assets if item.asset_id == state["audio_asset_id"])
            feedback_stage = "render" if stage_feedback(state, "render") else "director"
            feedback = stage_feedback(state, feedback_stage)
            if (not state.get("extras", {}).get("timeline_rebuild") and feedback and job.timeline
                    and type(feedback.get("timeline")) is dict and job.timeline.model_dump() != feedback["timeline"]):
                # SQL may commit before either artifact write; restore both outputs before continuing.
                self.service.write_json(job, "storyboard.json", job.timeline.model_dump(), "storyboard")
                self.service.write_json(job, "timeline.json", job.timeline.model_dump(), "timeline")
                mark_feedback_applied(self.repo, self.service, job, state, feedback_stage, "director")
                return state_context(self.repo, state, route=self.next_route(state), gate_issues=[])
            timeline = self.plan(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"],
                                 state.get("research", {}), state=state)
            if feedback and type(feedback.get("timeline")) is dict and timeline.model_dump() == feedback["timeline"]:
                raise ValueError("人工返工未产生分镜修改，请补充更明确的修改意见")
            stale = {"preview", "final", "cover", "captions", "review", "package", "storyboard",
                     "timeline", "editing_guidance", "human_review", "component_study"}
            # Drop stale downstream artifacts from the snapshot read before planning.
            current = self.repo.get_job(job.job_id)
            artifacts = [item for item in current.artifacts if item.kind not in stale]
            job = self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                                       timeline=timeline, review=None, progress=None, artifacts=artifacts)
            self.service.write_json(job, "storyboard.json", timeline.model_dump(), "storyboard")
            self.service.write_json(job, "timeline.json", timeline.model_dump(), "timeline")
            if feedback:
                mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                      feedback_stage, "director")
            if state.get("extras", {}).get("timeline_rebuild"):
                state["extras"] = {**state["extras"], "timeline_rebuild": None}
            return state_context(self.repo, state, route=self.next_route(state), gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["timeline"], exc)

    @staticmethod
    def _needs_script_revision(note: str) -> bool:
        return needs_script_revision(note)

    @staticmethod
    def _needs_voice_revision(note: str) -> bool:
        patterns = ("改配音", "重配音", "调整配音", "改音频", "重做音频", "调整音频",
                    "改语速", "语速太", "语速过", "调整语速", "改发音", "读音错误")
        return any(pattern in note for pattern in patterns)

    @classmethod
    def _needs_voice_or_script(cls, note: str) -> bool:
        """Compatibility for callers that only need a combined classification."""
        return cls._needs_script_revision(note) or cls._needs_voice_revision(note)

    def next_route(self, state: VideoState) -> str:
        action = state.get("action")
        if action == "storyboard":
            job = self.repo.get_job(state["job_id"])
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message="分镜已生成，本次执行结束", progress=1, pending_input=None)
            return "end"
        if action == "review":
            job = self.repo.get_job(state["job_id"])
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message="已移除成片审核节点；请使用 produce/final 重新生成视频", progress=1,
                                 pending_input=None)
            return "end"
        return "editing"

    def plan(self, job: Job, audio: Asset, alignment: Alignment, duration: float,
             research: dict | None = None, state: VideoState | None = None) -> Timeline:
        asset_metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
        model_available = self.model.available("director")
        context = agent_state(self.repo, job, state)
        if state is None and research is not None:
            context = {**context, "research": research}
        feedback = stage_feedback(context, "director", "render")
        rebuilding = bool(context.get("extras", {}).get("timeline_rebuild"))
        pending = context.get("pending_snapshot") or {}
        repair_issues = list(context.get("gate_issues", [])) if pending.get("stage") == "director" else []
        if not rebuilding and feedback and job.timeline and type(feedback.get("timeline")) is dict and job.timeline.model_dump() != feedback["timeline"]:
            return job.timeline
        if rebuilding and not model_available:
            raise CapabilityMissing("重做画面需要启用导演模型重新选择素材和编排镜头，不能直接复用旧分镜", ["role_models", "timeline"])
        if feedback and not model_available:
            raise CapabilityMissing("人工返工需要导演模型读取审核意见并重新规划镜头；请启用导演模型或提供新的人工分镜", ["role_models", "timeline"])
        if job.timeline and not feedback and not rebuilding:
            validate_timeline(job.timeline, job, asset_metadata)
            expected = [(item.text, item.start_ms, item.end_ms) for item in alignment.segments]
            actual = [(item.text, item.start_ms, item.end_ms) for item in job.timeline.captions]
            if expected != actual or job.timeline.audio_src != audio.timeline_src:
                raise ValueError("人工分镜必须保留当前实测音频及字幕时间轴")
            repair_issues = timeline_readability_issues(job.timeline) if production_portrait(job) else repair_issues
            if not repair_issues:
                return job.timeline
            if not model_available:
                raise ValueError("；".join(repair_issues))
        starts = {}
        for segment in alignment.segments:
            starts.setdefault(segment.segment_id, math.floor(segment.start_ms * job.brief.fps / 1000))
        total = math.ceil(duration * job.brief.fps)
        if total < 15:
            raise ValueError("视频时长过短，镜头至少需要 15 帧")
        # 段落仅提供候选切点。短段落合入相邻基线镜头，实际字幕全部保留；
        # 导演可以基于这份提示自由拆镜、合镜或跨段落安排新的切点。
        cut_indices, cut_frames = [0], [0]
        for index, segment in enumerate(job.script.segments[1:], 1):
            boundary = starts[segment.segment_id]
            if boundary - cut_frames[-1] >= 15 and total - boundary >= 15:
                cut_indices.append(index)
                cut_frames.append(boundary)
        assets = {asset.asset_id: asset for asset in job.assets}
        shots = []
        for index, segment_index in enumerate(cut_indices):
            segment = job.script.segments[segment_index]
            start = cut_frames[index]
            end = cut_frames[index + 1] if index + 1 < len(cut_frames) else total
            next_segment_index = cut_indices[index + 1] if index + 1 < len(cut_indices) else len(job.script.segments)
            shot_seconds = (end - start) / job.brief.fps
            video = next((asset for asset in job.assets
                          if asset.mime_type.startswith("video/")
                          and (asset.asset_id in segment.asset_ids
                               or bool(asset.source_url and asset.source_url in segment.source_refs))
                          and asset_renderable(asset)
                          and _video_covers(asset, asset_metadata, shot_seconds)), None)
            image = next((assets[asset_id] for asset_id in segment.asset_ids
                          if asset_id in assets and assets[asset_id].mime_type.startswith("image/")
                          and asset_renderable(assets[asset_id])), None)
            if not image:
                # 编剧没有指定图片时，根据该段的出处匹配素材节点采集的真实画面。
                image = next((asset for asset in job.assets if asset.mime_type.startswith("image/")
                              and asset_renderable(asset) and asset.source_url in segment.source_refs), None)
            component = "video" if video else "evidence" if image and image.role == "evidence" and image.source_url else "image_focus" if image else "title" if index == 0 else "conclusion" if index == len(cut_indices) - 1 else "keyword"
            media = video or image
            shots.append(Shot(shot_id=f"shot-{index + 1}", start_frame=start, end_frame=end,
                              component_id=component, title=(segment.screen_text or job.script.title)[:100],
                              body="".join(item.narration for item in job.script.segments[segment_index:next_segment_index])[:240],
                              asset_src=media.timeline_src if media else None,
                              source_label=_host(media.source_url) if media and media.source_url else "",
                              props={"start_seconds": 0, "fit": "contain"} if video else {}))
        timeline = Timeline(job_id=job.job_id, revision=job.revision, width=job.brief.width, height=job.brief.height,
                            fps=job.brief.fps, duration_in_frames=total, audio_src=audio.timeline_src, shots=shots,
                            captions=[Caption(text=item.text, start_ms=item.start_ms, end_ms=item.end_ms) for item in alignment.segments])
        if model_available:
            schema = DirectorPlan.model_json_schema()
            schema["$defs"]["Shot"]["properties"]["component_id"]["enum"] = available_component_ids(
                job.brief.usage
            )
            # 仅当前任务已导入的图片/视频可作为渲染资产；研究链接不是资产路径。
            schema["$defs"]["Shot"]["properties"]["asset_src"]["enum"] = [
                asset.timeline_src for asset in job.assets
                if asset.mime_type.startswith(("image/", "video/"))
                and asset_renderable(asset)
            ] + [None]
            # 实测基线只作为本次导演输入；模型输出校验通过前不写入共享 state。
            reviewed_timeline = feedback.get("timeline") if feedback and type(feedback.get("timeline")) is dict else None
            if repair_issues and not rebuilding:
                reviewed_timeline = job.timeline.model_dump()
            planning_timeline = Timeline.model_validate(reviewed_timeline) if reviewed_timeline else timeline
            coverage = media_coverage_report(
                planning_timeline,
                job,
                asset_metadata,
                validate_relationships=False,
            )
            model_state = {**context, "timeline": planning_timeline.model_dump(),
                           # 音频对齐已在 timeline.captions 提供，避免在素材元信息中重复发送。
                           "asset_metadata": {asset.asset_id: {
                               **{key: value for key, value in {
                                   **context.get("asset_metadata", {}).get(asset.asset_id, {}),
                                   **asset_metadata[asset.asset_id],
                               }.items() if key != "alignment"},
                               **({"renderable": asset_renderable(asset)}
                                  if asset.mime_type.startswith(("image/", "video/")) else {}),
                           } for asset in job.assets},
                           "extras": {**context.get("extras", {}),
                                      "media_coverage": coverage, "timeline_repair_issues": repair_issues}}
            instruction = director_prompt(job.brief.usage)
            if coverage["required"]:
                instruction += ("\n\n本次提交的硬约束：图片/视频镜头至少覆盖 "
                                f"{coverage['target_frames']} 帧（全片 {total} 帧），"
                                f"asset_src=null 的纯解释镜头合计最多 {total - coverage['target_frames']} 帧。"
                                "先安排与本段旁白对应的真实素材，再保留必要解释镜头；"
                                "提交前按 end_frame-start_frame 求和核对。")
            value = self.model.invoke(model_state, "director", instruction,
                fields=("brief", "script", "timeline", "research", "assets", "asset_metadata", "extras"),
                command_id=(context.get("resume_command_id") or context.get("run_id", "")) + ":timeline",
                output_schema=schema)
            plan = DirectorPlan.model_validate(value)
            # 镜头切点属于画面编排，不是音频对齐：只替换 shots，真实音频、
            # 字幕、画幅和总帧数保持程序实测值，连续覆盖由 Timeline 校验。
            timeline = Timeline.model_validate({**timeline.model_dump(), "shots": [shot.model_dump() for shot in plan.shots]})
        validate_timeline(timeline, job, asset_metadata)
        issues = timeline_readability_issues(timeline) if production_portrait(job) else []
        if issues:
            raise ValueError("；".join(issues))
        if model_available:
            validate_media_coverage(timeline, job, asset_metadata)
        return timeline
