"""Render every production shot for review; preserve legacy/component demos."""

import json
import uuid
from pathlib import Path
from typing import Any

from videoagents.contracts import DirectorShotReviewManifest
from videoagents.nodes.common import (
    render_text_fit_issues,
    request_input,
    start_stage,
    state_context,
    validate_context_assets,
)
from videoagents.nodes.director_review import (
    SHOT_REVIEW_MODE,
    checked_review_png,
    current_demo_artifact,
    current_plan_artifact,
    current_shot_review_artifact,
    shot_review_details,
)
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.context_media import validate_production_timeline
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.process_manager import render_shot_reviews


class DirectorDemoNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.renderer = EditingNode(repository, service)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "director", "摄影正在准备逐镜审核画面")
        try:
            _, plan = current_plan_artifact(self.repo, job)
        except ValueError as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["director_plan"], exc)
        per_shot = plan.get("review_mode") == SHOT_REVIEW_MODE
        try:
            try:
                if per_shot:
                    current_shot_review_artifact(self.repo, job)
                else:
                    current_demo_artifact(self.repo, job)
            except ValueError:
                if per_shot:
                    self.render_shots(job)
                else:
                    self.renderer.render_video(job, "preview", state=state)
            current = self.repo.get_job(job.job_id)
            if per_shot:
                current_shot_review_artifact(self.repo, current)
            else:
                current_demo_artifact(self.repo, current)
        except (CapabilityMissing, ValueError, TimeoutError, OSError) as exc:
            if isinstance(exc, ValueError) and render_text_fit_issues([str(exc)]):
                return request_input(self.repo, state, "director", [str(exc)], ["timeline", "render"], exc)
            return request_input(self.repo, state, "director", [str(exc)], ["render"], exc,
                                 retry_node="director_demo")
        if state.get("action") in {"preview", "component_demo"} or (per_shot and state.get("action") == "storyboard"):
            message = ("组件套样片已生成，等待人工品鉴反馈"
                       if state.get("action") == "component_demo"
                       else "全部镜头的逐镜审核图片已生成，本次执行结束" if per_shot
                       else "摄影Demo已生成，本次预览执行结束")
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message=message, progress=1)
            return state_context(self.repo, state, route="end")
        self.repo.update_job(job.job_id, job.revision, status="RUNNING", stage="director",
                             message="全部镜头的组件选择和真实审核图片已就绪，准备人工审核" if per_shot
                             else "摄影方案和Demo已就绪，准备人工审核", progress=1)
        return state_context(self.repo, state, route="director_human_gate")

    def render_shots(self, job) -> None:
        plan_artifact, plan = current_plan_artifact(self.repo, job)
        validate_context_assets(self.repo, job)
        metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
        validate_production_timeline(self.repo, job, job.timeline, metadata)
        for asset in job.assets:
            self.service.freeze_asset(asset)
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "shot-reviews" / uuid.uuid4().hex
        folder.mkdir(parents=True, exist_ok=True)
        timeline_path, request_path, output_manifest = folder / "timeline.json", folder / "request.json", folder / "rendered-frames.json"
        timeline_path.write_text(job.timeline.model_dump_json(indent=2), encoding="utf-8")
        request = [{"shot_id": item["shot_id"], "frame": item["review_frame"]} for item in plan["shot_reviews"]]
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        config = SettingsService(self.repo).internal()

        def progress(value):
            self.repo.update_job(job.job_id, job.revision, progress=max(0, min(1, value)),
                                 message="Remotion 正在按摄影设计渲染每个镜头的审核图片")

        result = render_shot_reviews(self.service.project_root, timeline_path, request_path, output_manifest,
            config["render_timeout_seconds"], lambda: self.repo.get_job(job.job_id).status == "CANCELLED", progress)
        rendered = json.loads(output_manifest.read_text(encoding="utf-8"))
        if result.get("images") != rendered or not isinstance(rendered, list) or len(rendered) != len(request):
            raise ValueError("逐镜审核渲染结果没有完整覆盖当前镜头")
        current = self.repo.get_job(job.job_id)
        current_plan, _ = current_plan_artifact(self.repo, current)
        if current_plan != plan_artifact or dependency_fingerprint(current) != dependency_fingerprint(job):
            raise Conflict("逐镜渲染期间摄影设计或制作输入已改变，请重新生成审核包")
        images, items = [], []
        image_metadata = {"dependency_fingerprint": dependency_fingerprint(job),
                          "director_plan_sha256": plan_artifact.sha256}
        for index, (shot, spec, output) in enumerate(zip(job.timeline.shots, plan["shot_reviews"], rendered, strict=True), 1):
            if (not isinstance(output, dict) or output.get("shot_id") != shot.shot_id
                    or output.get("frame") != spec["review_frame"]
                    or (output.get("width"), output.get("height")) != (job.timeline.width, job.timeline.height)):
                raise ValueError("逐镜审核渲染结果的镜头、代表帧或画幅不一致")
            path = Path(output.get("path", "")).resolve()
            if not path.is_file() or path.parent != folder.resolve():
                raise ValueError("逐镜审核图片没有保存在本次任务的渲染目录")
            checked_review_png(path, job.timeline.width, job.timeline.height)
            image = self.service.register_artifact(job, path, "shot_review_frame", "image/png")
            images.append(image)
            self.repo.update_artifact_metadata(image.artifact_id, {**image_metadata,
                "shot_id": shot.shot_id, "review_frame": spec["review_frame"],
                "width": job.timeline.width, "height": job.timeline.height})
            items.append({**shot_review_details(job, shot, spec, index), "image": image.model_dump(mode="json")})
        manifest = DirectorShotReviewManifest(job_id=job.job_id, revision=job.revision,
            director_plan_artifact_id=plan_artifact.artifact_id, director_plan_sha256=plan_artifact.sha256,
            dependency_fingerprint=dependency_fingerprint(job), timeline_fingerprint=plan["timeline_fingerprint"],
            width=job.timeline.width, height=job.timeline.height, fps=job.timeline.fps,
            duration_in_frames=job.timeline.duration_in_frames, items=items)
        manifest_path = folder / "director-shot-review.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        artifact = self.service.register_artifact(job, manifest_path, "director_shot_review", "application/json")
        self.repo.update_artifact_metadata(artifact.artifact_id, {**image_metadata, "review_mode": SHOT_REVIEW_MODE})
        current = self.repo.get_job(job.job_id)
        artifacts = [item for item in current.artifacts if item.kind not in {"director_shot_review", "shot_review_frame"}]
        # Publish only the complete set. append_artifact replaces equal kinds,
        # so appending PNGs one by one would silently retain just the last shot.
        self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                             artifacts=[*artifacts, *images, artifact])
