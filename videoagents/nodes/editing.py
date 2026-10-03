"""Freeze verified media, render a real MP4 and register inspectable outputs."""

import uuid

from videoagents.agents.reviewers import dependency_fingerprint
from videoagents.contracts import EditingAdvice, Job
from videoagents.providers.llm import JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline
from worker.process_manager import render


class EditingNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def run(self, job: Job, mode: str) -> None:
        if not job.timeline:
            raise ValueError("没有可执行分镜")
        validate_timeline(job.timeline, job)
        if self.model.available("editing"):
            value = self.model.call(job.job_id, job.revision, "editing",
                "作为剪辑指导，在Remotion执行前检查实测镜头节奏、字幕和标题密度、画面主次、图片与旁白的对应；返回pacing_notes、layout_notes和findings。"
                "只给可审阅建议，不能改写旁白、改动帧区间或字幕时间、添加未经核实的素材、执行代码或请求额外工具；不得声称已观看未渲染的视频。"
                "发现会阻止按当前分镜出片的问题须blocking=true。",
                {"brief": job.brief.model_dump(), "script": job.script.model_dump() if job.script else None,
                 "timeline": job.timeline.model_dump(), "assets": [asset.model_dump() for asset in job.assets], "render_mode": mode},
                output_schema=EditingAdvice.model_json_schema())
            advice = EditingAdvice.model_validate(value)
            self.service.write_json(job, "editing_guidance.json", advice.model_dump(), "editing_guidance")
            blocked = [item.message for item in advice.findings if item.blocking or item.severity == "error"]
            if blocked:
                raise ValueError("剪辑模型预检未通过：" + "；".join(blocked))
        for asset in job.assets:
            self.service.freeze_asset(asset)
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "renders" / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        timeline_path, output, cover = folder / "timeline.json", folder / f"{mode}.mp4", folder / "cover.png"
        timeline_path.write_text(job.timeline.model_dump_json(indent=2), encoding="utf-8")
        config = SettingsService(self.repo).internal()
        def update(value):
            self.repo.update_job(job.job_id, job.revision, progress=max(0, min(1, value)), message="Remotion 正在渲染")
        render(self.service.project_root, timeline_path, output, cover, mode, config["render_timeout_seconds"],
               lambda: self.repo.get_job(job.job_id).status == "CANCELLED", update)
        artifact = self.service.register_artifact(job, output, mode, "video/mp4")
        self.repo.update_artifact_metadata(artifact.artifact_id, {"dependency_fingerprint": dependency_fingerprint(job)})
        self.service.append_artifact(job.job_id, artifact, job.revision)
        if cover.is_file():
            self.service.append_artifact(job.job_id, self.service.register_artifact(job, cover, "cover", "image/png"), job.revision)
        captions_path = folder / "captions.srt"
        def timestamp(ms):
            value = round(ms)
            hours, rem = divmod(value, 3600000)
            minutes, rem = divmod(rem, 60000)
            seconds, millis = divmod(rem, 1000)
            return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"
        captions_path.write_text("\n\n".join(f"{i + 1}\n{timestamp(c.start_ms)} --> {timestamp(c.end_ms)}\n{c.text}" for i, c in enumerate(job.timeline.captions)), encoding="utf-8")
        self.service.append_artifact(job.job_id, self.service.register_artifact(job, captions_path, "captions", "text/plain"), job.revision)
