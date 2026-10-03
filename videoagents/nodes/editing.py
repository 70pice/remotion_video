"""Freeze verified media, render a real MP4 and register inspectable outputs."""

import uuid

from videoagents.agents.reviewers import dependency_fingerprint
from videoagents.contracts import Job
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline
from worker.process_manager import render


class EditingNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service

    def run(self, job: Job, mode: str) -> None:
        if not job.timeline:
            raise ValueError("没有可执行分镜")
        validate_timeline(job.timeline, job)
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
