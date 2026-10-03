"""Model-assisted shot choices, grounded in actual audio boundaries and real assets."""

import math
from urllib.parse import urlparse

from videoagents.contracts import Alignment, Asset, Caption, Job, Shot, Timeline
from videoagents.providers.llm import JsonModel
from videoagents.tools.timeline import ALLOWED_PROPS, validate_timeline


class Director:
    def __init__(self, repository):
        self.model = JsonModel(repository)

    def run(self, job: Job, audio: Asset, alignment: Alignment, duration: float) -> Timeline:
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
            component = "evidence" if image and image.role == "evidence" and image.source_url else "image_focus" if image else "title" if index == 0 else "conclusion" if index == len(job.script.segments) - 1 else "keyword"
            shots.append(Shot(shot_id=f"shot-{index + 1}", start_frame=start, end_frame=end,
                              component_id=component, title=(segment.screen_text or job.script.title)[:100],
                              body=segment.narration[:240], asset_src=image.timeline_src if image else None,
                              source_label=urlparse(image.source_url).hostname[:160] if image and image.source_url else ""))
        timeline = Timeline(job_id=job.job_id, revision=job.revision, width=job.brief.width, height=job.brief.height,
                            fps=job.brief.fps, duration_in_frames=total, audio_src=audio.timeline_src, shots=shots,
                            captions=[Caption(text=item.text, start_ms=item.start_ms, end_ms=item.end_ms) for item in alignment.segments])
        if self.model.available("director"):
            value = self.model.call(job.job_id, job.revision, "director", "优化镜头构图、选型、主次和文字冲击力。保留给定时间轴帧区间、caption、audio_src、job_id和revision；只用白名单组件与已提供的素材。不得产生新数据或改变旁白。返回完整 Timeline。组件props=" + str(ALLOWED_PROPS),
                                    {"script": job.script.model_dump(), "timeline": timeline.model_dump(), "assets": [asset.model_dump() for asset in job.assets]}, output_schema=Timeline.model_json_schema())
            candidate = Timeline.model_validate(value)
            immutable = (candidate.audio_src, candidate.captions, [(s.start_frame, s.end_frame) for s in candidate.shots])
            baseline = (timeline.audio_src, timeline.captions, [(s.start_frame, s.end_frame) for s in timeline.shots])
            if immutable != baseline:
                raise ValueError("导演模型修改了实测音频时间轴，未接受分镜")
            timeline = candidate
        validate_timeline(timeline, job)
        return timeline
