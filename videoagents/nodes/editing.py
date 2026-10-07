"""Freeze verified media, render a real MP4 and register inspectable outputs."""

import copy
import uuid
from typing import Any

from videoagents.contracts import EditingAdvice, Job
from videoagents.nodes.common import agent_state, request_input, start_stage, state_context
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.prompts import compose
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline
from worker.process_manager import render

PROMPT = compose("shared-style", "editing")


def has_unapplied_human_feedback(extras: dict[str, Any]) -> bool:
    """Only expose revision feedback that still needs an agent response.

    Applied receipts retain the reviewed script/timeline snapshot for audit
    purposes.  Passing those immutable snapshots back to the editor after the
    director has already changed ``job.timeline`` lets the model mistake the
    old reviewed Timeline for the current executable one.
    """

    feedback = extras.get("human_feedback", {})
    if type(feedback) is not dict:
        return False
    return any(
        type(item) is dict
        and item.get("decision") == "revise"
        and item.get("applied") is not True
        for item in feedback.values()
    )


def compact_timeline_for_editing(timeline: dict[str, Any]) -> dict[str, Any]:
    """Project word captions into per-shot windows for the no-tool editor.

    The authoritative Timeline remains unchanged in state and on disk.  The
    editor needs exact shot bounds and the words audible inside each shot, but
    not more than a thousand individual caption objects.  This final-output
    projection keeps those semantics while avoiding output-format failures
    caused by an unnecessarily large CLI context.
    """

    result = copy.deepcopy(timeline)
    captions = result.pop("captions", [])
    fps = result.get("fps")
    windows = []
    if type(fps) is int and fps > 0:
        for shot in result.get("shots", []):
            start_ms = shot["start_frame"] * 1000 / fps
            end_ms = shot["end_frame"] * 1000 / fps
            active = [item for item in captions if item["end_ms"] > start_ms and item["start_ms"] < end_ms]
            windows.append({
                "shot_id": shot["shot_id"],
                "start_ms": start_ms,
                "end_ms": end_ms,
                "caption_start_ms": active[0]["start_ms"] if active else None,
                "caption_end_ms": active[-1]["end_ms"] if active else None,
                "text": "".join(item["text"] for item in active),
            })
    result["caption_summary"] = {
        "count": len(captions),
        "first_start_ms": captions[0]["start_ms"] if captions else None,
        "last_end_ms": captions[-1]["end_ms"] if captions else None,
        "windows": windows,
    }
    return result


class EditingNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "render", "剪辑正在冻结素材并调用 Remotion")
        mode = "preview" if state["action"] == "preview" else "final"
        try:
            self.render_video(job, mode, state=state)
        except (CapabilityMissing, ValueError, TimeoutError) as exc:
            return request_input(self.repo, state, "render", [str(exc)], getattr(exc, "fields", ["render"]), exc)
        if mode == "preview":
            job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="真实预览已渲染，可试听并调整分镜", stage="render", progress=1)
            return state_context(self.repo, state, route="end")
        job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="成片已渲染完成，可人工查看后决定是否发布", stage="complete", progress=1)
        return state_context(self.repo, state, route="end")

    def render_video(self, job: Job, mode: str, state: VideoState | None = None) -> None:
        if not job.timeline:
            raise ValueError("没有可执行分镜")
        metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
        validate_timeline(job.timeline, job, metadata)
        if self.model.available("editing"):
            context = agent_state(self.repo, job, state)
            if state is None:
                context = {**context, "action": mode}
            context = {**context, "timeline": compact_timeline_for_editing(context["timeline"])}
            fields = ("brief", "script", "timeline", "assets", "action")
            if has_unapplied_human_feedback(context.get("extras", {})):
                fields = (*fields, "extras")
            value = self.model.invoke(context, "editing", PROMPT,
                fields=fields,
                command_id=context.get("resume_command_id", context.get("run_id", "")),
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
