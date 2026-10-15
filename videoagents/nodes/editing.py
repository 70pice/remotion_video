"""Freeze verified media, render a real MP4 and register inspectable outputs."""

import copy
import json
import uuid
from typing import Any

from videoagents.contracts import EditingAdvice, Job
from videoagents.nodes.common import agent_state, current_job, request_input, start_stage, state_context
from videoagents.nodes.director_review import (
    checked_artifact,
    current_plan_artifact,
    director_demo_is_approved,
)
from videoagents.nodes.gates import timeline_readability_issues
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.prompts import load_prompt
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.context_media import validate_production_timeline
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.component_sets import allowed_component_set_templates
from videoagents.tools.components import native_component_capabilities
from videoagents.tools.timeline import asset_renderable
from worker.process_manager import render

PROMPT = load_prompt("editing")


def editing_prompt(job: Job) -> str:
    """Give preflight the same executable kits and layer roles as production."""
    templates = allowed_component_set_templates(job.brief.usage)
    shots = job.timeline.shots if job.timeline else []
    selected = sorted({shot.set_design.set_id for shot in shots if shot.set_design})
    roles = native_component_capabilities()["layer_roles"]
    layer_ids = sorted({layer.component_id for shot in shots for layer in shot.layers})
    capabilities = {"component_sets": [templates[set_id] for set_id in selected],
                    "layer_roles": {component_id: sorted(roles.get(component_id, ())) for component_id in layer_ids}}
    return PROMPT + "\n\n当前生产镜内组合能力（固定绑定，不含示例素材或文案）：\n" + json.dumps(
        capabilities, ensure_ascii=False, separators=(",", ":"))


def editing_instruction_fingerprint(job: Job) -> str:
    return fingerprint({"instruction": editing_prompt(job)})


class DirectorInputError(ValueError):
    """A visual plan issue must return to its owning production node."""


def editing_visual_review_context(repository: Repository, job: Job) -> dict[str, Any]:
    """Pass durable visual decisions without any reviewed input snapshots."""
    reviews, applied = [], []
    for artifact in job.artifacts:
        if artifact.revision != job.revision or artifact.kind not in {"stage_review", "human_feedback_applied"}:
            continue
        value = json.loads(checked_artifact(repository, job, artifact).read_text(encoding="utf-8"))
        if value.get("revision") != job.revision or value.get("stage") != "director":
            continue
        if artifact.kind == "stage_review" and value.get("node_name") == "director_human_gate":
            reviews.append((artifact, value))
        elif (artifact.kind == "human_feedback_applied" and value.get("target") == "director"
                and value.get("applied") is True):
            applied.append((artifact, value))
    result = {}
    if applied:
        applied_artifact, committed = applied[-1]
        match = next(((artifact, value) for artifact, value in reversed(reviews)
                      if value.get("decision") == "revise"
                      and value.get("pending_token") == committed.get("pending_token")
                      and value.get("note") == committed.get("note")), None)
        if match:
            artifact, value = match
            result["applied_director_feedback"] = {
                **{key: value[key] for key in ("revision", "pending_token", "note")},
                "review_artifact_id": artifact.artifact_id, "applied_artifact_id": applied_artifact.artifact_id,
            }
    if reviews and reviews[-1][1].get("decision") == "confirm" and director_demo_is_approved(repository, job):
        artifact, value = reviews[-1]
        result["shot_review_confirmation"] = {
            **{key: value[key] for key in (
                "revision", "pending_token", "note", "review_mode", "reviewed_shot_ids",
                "director_shot_review_artifact_id", "dependency_fingerprint") if key in value},
            "review_artifact_id": artifact.artifact_id,
        }
        from videoagents.services.director_recovery import visual_revision_context

        revision = visual_revision_context(repository, job)
        if revision:
            result["visual_revision"] = revision
    return result


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
        job = current_job(self.repo, state)
        if state.get("action") == "preview" or not director_demo_is_approved(self.repo, job):
            # Old checkpoints and failure retries cannot bypass the new gate.
            return state_context(self.repo, state, route="director_demo")
        job = start_stage(self.repo, state, "render", "剪辑正在冻结素材并调用 Remotion")
        try:
            final = next((item for item in reversed(job.artifacts) if item.kind == "final"
                          and item.revision == job.revision
                          and self.repo.artifact_metadata(item.artifact_id).get("dependency_fingerprint")
                          == dependency_fingerprint(job)), None)
            if final:
                checked_artifact(self.repo, job, final)
            else:
                self.render_video(job, "final", state=state)
        except DirectorInputError as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["timeline"], exc)
        except (CapabilityMissing, ValueError, TimeoutError) as exc:
            return request_input(self.repo, state, "render", [str(exc)], getattr(exc, "fields", ["render"]), exc)
        job = self.repo.update_job(job.job_id, job.revision, status="DRAFT", message="成片已渲染完成，可人工查看后决定是否发布", stage="complete", progress=1)
        return state_context(self.repo, state, route="end")

    def render_video(self, job: Job, mode: str, state: VideoState | None = None, *,
                     frame_range: tuple[int, int] | None = None) -> None:
        if not job.timeline:
            raise ValueError("没有可执行分镜")
        explicit_range = frame_range is not None
        if explicit_range and (mode != "preview" or type(frame_range) is not tuple or len(frame_range) != 2
                or any(type(frame) is not int for frame in frame_range)
                or not 0 <= frame_range[0] < frame_range[1] <= job.timeline.duration_in_frames
                or frame_range[1] - frame_range[0] > job.timeline.fps * 30):
            raise ValueError("动态审核预览需要时间轴内不超过30秒的连续整数帧范围，且只能用于preview")
        metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
        validate_production_timeline(self.repo, job, job.timeline, metadata)
        issues = timeline_readability_issues(job.timeline) if (job.brief.width, job.brief.height, job.brief.fps) == (1080, 1920, 30) else []
        if issues:
            raise DirectorInputError("；".join(issues))
        if mode == "final" and self.model.available("editing"):
            context = agent_state(self.repo, job, state)
            if state is None:
                context = {**context, "action": mode}
            context = {**context, "timeline": compact_timeline_for_editing(context["timeline"]),
                       "asset_metadata": {asset.asset_id: {
                           **{key: value for key, value in metadata[asset.asset_id].items() if key != "alignment"},
                           "renderable": asset_renderable(asset),
                       } for asset in job.assets
                           if asset.mime_type.startswith(("image/", "video/"))}}
            fields = ("brief", "script", "timeline", "assets", "asset_metadata", "action")
            visual_review = editing_visual_review_context(self.repo, job)
            if visual_review:
                context = {**context, "extras": {"visual_review": visual_review}}
                fields = (*fields, "extras")
            instruction = editing_prompt(job)
            value = self.model.invoke(context, "editing", instruction,
                fields=fields,
                command_id=context.get("resume_command_id", context.get("run_id", "")),
                output_schema=EditingAdvice.model_json_schema())
            advice = EditingAdvice.model_validate(value)
            artifact = self.service.write_json(job, "editing_guidance.json", advice.model_dump(), "editing_guidance")
            self.repo.update_artifact_metadata(artifact.artifact_id, {
                "instruction_fingerprint": fingerprint({"instruction": instruction}),
                "dependency_fingerprint": dependency_fingerprint(job),
            })
            blocked = [item.message for item in advice.findings if item.blocking or item.severity == "error"]
            if blocked:
                if any(item.owner == "director" for item in advice.findings if item.blocking or item.severity == "error"):
                    raise DirectorInputError("剪辑发现分镜问题：" + "；".join(blocked))
                raise ValueError("剪辑模型预检未通过：" + "；".join(blocked))
        for asset in job.assets:
            self.service.freeze_asset(asset)
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "renders" / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        render_metadata = {"dependency_fingerprint": dependency_fingerprint(job)}
        if mode == "preview":
            plan_artifact, plan = current_plan_artifact(self.repo, job)
            if frame_range is None:
                demo = plan.get("demo")
                if not isinstance(demo, dict):
                    raise ValueError("逐镜审核方案的动态预览必须指定连续帧范围")
                frame_range = (demo["start_frame"], demo["end_frame"])
            if explicit_range:
                render_metadata["motion_preview"] = True
            render_metadata.update(director_plan_sha256=plan_artifact.sha256, frame_range=list(frame_range))
        timeline_path, output, cover = folder / "timeline.json", folder / f"{mode}.mp4", folder / "cover.png"
        timeline_path.write_text(job.timeline.model_dump_json(indent=2), encoding="utf-8")
        config = SettingsService(self.repo).internal()
        def update(value):
            self.repo.update_job(job.job_id, job.revision, progress=max(0, min(1, value)), message="Remotion 正在渲染")
        render(self.service.project_root, timeline_path, output, cover, mode, config["render_timeout_seconds"],
               lambda: self.repo.get_job(job.job_id).status == "CANCELLED", update, frame_range=frame_range)
        artifact = self.service.register_artifact(job, output, mode, "video/mp4")
        self.repo.update_artifact_metadata(artifact.artifact_id, render_metadata)
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
        start_ms, end_ms = (0, job.timeline.duration_in_frames * 1000 / job.timeline.fps)
        if frame_range:
            start_ms, end_ms = (frame * 1000 / job.timeline.fps for frame in frame_range)
        captions = [caption for caption in job.timeline.captions
                    if caption.end_ms > start_ms and caption.start_ms < end_ms]
        captions_path.write_text("\n\n".join(
            f"{i + 1}\n{timestamp(max(c.start_ms, start_ms) - start_ms)} --> "
            f"{timestamp(min(c.end_ms, end_ms) - start_ms)}\n{c.text}"
            for i, c in enumerate(captions)), encoding="utf-8")
        self.service.append_artifact(job.job_id, self.service.register_artifact(job, captions_path, "captions", "text/plain"), job.revision)
