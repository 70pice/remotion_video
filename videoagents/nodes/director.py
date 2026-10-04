"""Model-assisted shot choices, grounded in actual audio boundaries and real assets."""

import json
import math
from typing import Any
from urllib.parse import urlparse

from videoagents.contracts import Alignment, Asset, Caption, Job, Shot, Timeline
from videoagents.nodes.common import agent_state, request_input, start_stage, state_context
from videoagents.prompts import load_prompt
from videoagents.prompts import render as render_prompt
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline

COMPONENT_PROPS_EXAMPLES = {
    "title": {"eyebrow": "给定主题"}, "keyword": {"keyword": "给定关键词"},
    "evidence": {"highlight": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
    "image_focus": {"focal_x": 0.5, "focal_y": 0.5},
    "comparison": {"left_title": "给定左标题", "left_body": "给定左正文",
                   "right_title": "给定右标题", "right_body": "给定右正文"},
    "data": {"items": [{"label": "来源中的标签", "value": "来源中的值", "detail": "来源中的说明"}]},
    "steps": {"items": [{"title": "给定步骤标题", "body": "给定步骤说明"}]},
    "conclusion": {"call_to_action": "文案中的行动建议"},
}
# 导演 Prompt 独立维护；props 结构示例在加载时注入，示例只展示字段结构，
# 不提供本视频事实。统一风格圣经在前，导演规则在后。
PROMPT = load_prompt("shared-style") + "\n\n" + render_prompt(
    "director",
    component_props=json.dumps(COMPONENT_PROPS_EXAMPLES, ensure_ascii=False, separators=(",", ":")),
)


class DirectorNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "director", "导演根据实测旁白安排镜头与关键画面")
        try:
            audio = next(item for item in job.assets if item.asset_id == state["audio_asset_id"])
            timeline = self.plan(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"],
                                 state.get("research", {}), state=state)
            job = self.repo.update_job(job.job_id, job.revision, timeline=timeline)
            self.service.write_json(job, "storyboard.json", timeline.model_dump(), "storyboard")
            self.service.write_json(job, "timeline.json", timeline.model_dump(), "timeline")
            return state_context(self.repo, state,
                                 route="timeline_gate", gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["timeline"], exc)

    def plan(self, job: Job, audio: Asset, alignment: Alignment, duration: float,
             research: dict | None = None, state: VideoState | None = None) -> Timeline:
        if job.timeline:
            validate_timeline(job.timeline, job)
            expected = [(item.text, item.start_ms, item.end_ms) for item in alignment.segments]
            actual = [(item.text, item.start_ms, item.end_ms) for item in job.timeline.captions]
            if expected != actual or job.timeline.audio_src != audio.timeline_src:
                raise ValueError("人工分镜必须保留当前实测音频及字幕时间轴")
            return job.timeline
        starts = {}
        for segment in alignment.segments:
            starts.setdefault(segment.segment_id, math.floor(segment.start_ms * job.brief.fps / 1000))
        total = math.ceil(duration * job.brief.fps)
        assets = {asset.asset_id: asset for asset in job.assets}
        shots = []
        for index, segment in enumerate(job.script.segments):
            start = 0 if index == 0 else starts[segment.segment_id]
            end = total if index == len(job.script.segments) - 1 else starts[job.script.segments[index + 1].segment_id]
            if end - start < 15:
                raise ValueError("实测旁白段落过短，镜头至少需要 15 帧；请调整段落/语速")
            image = next((assets[asset_id] for asset_id in segment.asset_ids if asset_id in assets and assets[asset_id].mime_type.startswith("image/")), None)
            if not image:
                # 编剧没有指定图片时，根据该段的出处匹配素材节点采集的真实画面。
                image = next((asset for asset in job.assets if asset.mime_type.startswith("image/")
                              and asset.source_url in segment.source_refs), None)
            component = "evidence" if image and image.role == "evidence" and image.source_url else "image_focus" if image else "title" if index == 0 else "conclusion" if index == len(job.script.segments) - 1 else "keyword"
            shots.append(Shot(shot_id=f"shot-{index + 1}", start_frame=start, end_frame=end,
                              component_id=component, title=(segment.screen_text or job.script.title)[:100],
                              body=segment.narration[:240], asset_src=image.timeline_src if image else None,
                              source_label=urlparse(image.source_url).hostname[:160] if image and image.source_url else ""))
        timeline = Timeline(job_id=job.job_id, revision=job.revision, width=job.brief.width, height=job.brief.height,
                            fps=job.brief.fps, duration_in_frames=total, audio_src=audio.timeline_src, shots=shots,
                            captions=[Caption(text=item.text, start_ms=item.start_ms, end_ms=item.end_ms) for item in alignment.segments])
        if self.model.available("director"):
            schema = Timeline.model_json_schema()
            # 仅当前调用提供的已导入图片可作为渲染资产；研究链接不是资产路径。
            schema["$defs"]["Shot"]["properties"]["asset_src"]["enum"] = [
                asset.timeline_src for asset in job.assets if asset.mime_type.startswith("image/")
            ] + [None]
            context = agent_state(self.repo, job, state)
            if state is None and research is not None:
                context = {**context, "research": research}
            # 实测基线只作为本次导演输入；模型输出校验通过前不写入共享 state。
            model_state = {**context, "timeline": timeline.model_dump()}
            value = self.model.invoke(model_state, "director", PROMPT,
                fields=("brief", "script", "timeline", "research", "assets", "asset_metadata"),
                command_id=context.get("resume_command_id", context.get("run_id", "")), output_schema=schema)
            candidate = Timeline.model_validate(value)
            immutable = (candidate.audio_src, candidate.captions, [(s.start_frame, s.end_frame) for s in candidate.shots])
            baseline = (timeline.audio_src, timeline.captions, [(s.start_frame, s.end_frame) for s in timeline.shots])
            if immutable != baseline:
                raise ValueError("导演模型修改了实测音频时间轴，未接受分镜")
            timeline = candidate
        validate_timeline(timeline, job)
        return timeline
