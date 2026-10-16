"""Bind director approval to the exact plan, review media and production inputs."""

import json
import struct

from pydantic import ValidationError

from videoagents.contracts import Artifact, DirectorShotReviewManifest, Job, Shot
from videoagents.nodes.director import load_current_director_plan
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.component_sets import component_set_templates
from videoagents.tools.media import sha256

SHOT_REVIEW_MODE = "per_shot_stills"


def shot_review_details(job: Job, shot: Shot, spec: dict, index: int) -> dict:
    """Derive displayed facts from the executable timeline, never model guesses."""
    component_ids = [shot.component_id]
    if shot.set_design:
        template = component_set_templates()[shot.set_design.set_id]
        by_id = {part["part_id"]: part["component_id"] for part in template["parts"]}
        component_ids.extend(by_id[part.part_id] for part in shot.set_design.parts)
    component_ids.extend(layer.component_id for layer in shot.layers)
    start_ms = shot.start_frame * 1000 / job.timeline.fps
    end_ms = shot.end_frame * 1000 / job.timeline.fps
    narration = "".join(caption.text for caption in job.timeline.captions
                        if caption.start_ms < end_ms and caption.end_ms > start_ms)
    return {**spec, "index": index, "start_frame": shot.start_frame, "end_frame": shot.end_frame,
            "component_id": shot.component_id, "set_id": shot.set_design.set_id if shot.set_design else None,
            "component_ids": list(dict.fromkeys(component_ids)), "title": shot.title, "body": shot.body,
            "asset_src": shot.asset_src, "source_label": shot.source_label, "narration": narration}


def checked_review_png(path, width: int, height: int) -> None:
    with path.open("rb") as stream:
        header = stream.read(24)
    if (len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR"
            or struct.unpack(">II", header[16:24]) != (width, height)):
        raise ValueError("逐镜审核图片不是当前画幅的真实PNG帧")


def checked_artifact(repository: Repository, job: Job, artifact: Artifact):
    try:
        path, registered, owner = repository.artifact_path(artifact.artifact_id)
        if owner != job.job_id or registered != artifact or sha256(path) != artifact.sha256:
            raise Conflict("摄影待审产物已改变，请重新生成并审核")
        return path
    except (NotFound, OSError) as exc:
        raise Conflict("摄影待审产物缺失，请重新生成并审核") from exc


def current_plan_artifact(repository: Repository, job: Job, *, validate_components: bool = True) -> tuple[Artifact, dict]:
    artifact = next((item for item in reversed(job.artifacts)
                     if item.kind == "director_plan" and item.revision == job.revision), None)
    if artifact is None:
        raise ValueError("缺少当前摄影镜头设计，请返回摄影节点")
    checked_artifact(repository, job, artifact)
    plan = load_current_director_plan(repository, job, validate_components=validate_components)
    if plan is None or plan.get("job_id") != job.job_id or plan.get("revision") != job.revision:
        raise ValueError("摄影方案与当前任务或分镜不一致，请重新设计")
    if plan.get("review_mode") == SHOT_REVIEW_MODE:
        return artifact, plan
    demo = plan.get("demo", {})
    start, end = demo.get("start_frame"), demo.get("end_frame")
    if (not job.timeline or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= job.timeline.duration_in_frames
            or end - start > 30 * job.timeline.fps):
        raise ValueError("摄影Demo必须是当前时间轴内最长30秒的连续区间")
    return artifact, plan


def current_demo_artifact(repository: Repository, job: Job, *, validate_components: bool = True) -> Artifact:
    plan_artifact, plan = current_plan_artifact(repository, job, validate_components=validate_components)
    if plan.get("review_mode") == SHOT_REVIEW_MODE:
        raise ValueError("当前摄影设计需要逐镜审核包，不能使用旧的30秒Demo")
    preview = next((item for item in reversed(job.artifacts)
                    if item.kind == "preview" and item.revision == job.revision), None)
    if preview is None:
        raise ValueError("当前摄影方案尚未生成真实Demo")
    checked_artifact(repository, job, preview)
    metadata = repository.artifact_metadata(preview.artifact_id)
    demo = plan["demo"]
    if (metadata.get("dependency_fingerprint") != dependency_fingerprint(job)
            or metadata.get("director_plan_sha256") != plan_artifact.sha256
            or metadata.get("frame_range") != [demo["start_frame"], demo["end_frame"]]):
        raise ValueError("Demo与当前摄影方案、素材或时间区间不一致，请重新生成")
    return preview


def current_shot_review_artifact(repository: Repository, job: Job, *, validate_components: bool = True
                                 ) -> tuple[Artifact, dict]:
    plan_artifact, plan = current_plan_artifact(repository, job, validate_components=validate_components)
    if plan.get("review_mode") != SHOT_REVIEW_MODE:
        raise ValueError("当前摄影设计使用旧版Demo审核")
    artifact = next((item for item in reversed(job.artifacts)
                     if item.kind == "director_shot_review" and item.revision == job.revision), None)
    if artifact is None:
        raise ValueError("当前摄影设计缺少完整逐镜审核包")
    path = checked_artifact(repository, job, artifact)
    try:
        manifest = DirectorShotReviewManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, UnicodeError) as exc:
        raise ValueError("逐镜审核包格式无效或镜头不完整") from exc
    payload = manifest.model_dump(mode="json")
    expected = {"job_id": job.job_id, "revision": job.revision,
                "director_plan_artifact_id": plan_artifact.artifact_id,
                "director_plan_sha256": plan_artifact.sha256,
                "dependency_fingerprint": dependency_fingerprint(job),
                "timeline_fingerprint": plan["timeline_fingerprint"],
                "width": job.timeline.width, "height": job.timeline.height, "fps": job.timeline.fps,
                "duration_in_frames": job.timeline.duration_in_frames}
    if any(payload.get(key) != value for key, value in expected.items()):
        raise ValueError("逐镜审核包与当前任务、摄影设计或时间轴不一致")
    metadata = repository.artifact_metadata(artifact.artifact_id)
    if (metadata.get("dependency_fingerprint") != expected["dependency_fingerprint"]
            or metadata.get("director_plan_sha256") != plan_artifact.sha256
            or metadata.get("review_mode") != SHOT_REVIEW_MODE):
        raise ValueError("逐镜审核包登记信息与当前设计不一致")
    if len(manifest.items) != len(job.timeline.shots):
        raise ValueError("逐镜审核包没有覆盖所有镜头")
    for index, (item, shot, spec) in enumerate(zip(manifest.items, job.timeline.shots, plan["shot_reviews"], strict=True), 1):
        details = shot_review_details(job, shot, spec, index)
        actual = item.model_dump(mode="json", exclude={"image"})
        if actual != details:
            raise ValueError(f"逐镜审核 {shot.shot_id} 的组件、帧或画面设计与当前镜头不一致")
        image = item.image
        if image not in job.artifacts or image.revision != job.revision:
            raise ValueError("逐镜审核图片不属于当前任务版本")
        image_path = checked_artifact(repository, job, image)
        checked_review_png(image_path, manifest.width, manifest.height)
        image_metadata = repository.artifact_metadata(image.artifact_id)
        image_expected = {"dependency_fingerprint": expected["dependency_fingerprint"],
                          "director_plan_sha256": plan_artifact.sha256,
                          "shot_id": shot.shot_id, "review_frame": spec["review_frame"],
                          "width": manifest.width, "height": manifest.height}
        if any(image_metadata.get(key) != value for key, value in image_expected.items()):
            raise ValueError("逐镜审核图片的登记信息与摄影设计不一致")
    return artifact, payload


def director_review_fingerprint(repository: Repository, job: Job, *, validate_components: bool = True) -> str:
    plan_artifact, plan = current_plan_artifact(repository, job, validate_components=validate_components)
    if plan.get("review_mode") == SHOT_REVIEW_MODE:
        review_artifact, manifest = current_shot_review_artifact(repository, job, validate_components=validate_components)
        review_media = {"shot_review": review_artifact.model_dump(),
                        "shot_review_metadata": repository.artifact_metadata(review_artifact.artifact_id),
                        "shot_images": [{"artifact": item["image"],
                                         "metadata": repository.artifact_metadata(item["image"]["artifact_id"])}
                                        for item in manifest["items"]]}
    else:
        preview = current_demo_artifact(repository, job, validate_components=validate_components)
        review_media = {"demo": preview.model_dump(),
                        "demo_metadata": repository.artifact_metadata(preview.artifact_id)}
    for asset in job.assets:
        try:
            path, registered, owner = repository.artifact_path(asset.artifact_id)
            if (owner != job.job_id or registered.sha256 != asset.sha256
                    or sha256(path) != asset.sha256):
                raise Conflict("摄影待审素材已改变，请重新生成并审核")
        except (NotFound, OSError) as exc:
            raise Conflict("摄影待审素材缺失，请重新生成并审核") from exc
    # Downstream editing advice and final outputs must not invalidate replay.
    job_payload = job.model_dump(include={"revision", "brief", "script", "timeline", "assets"})
    if job.director_requirements is not None:
        job_payload["director_requirements"] = job.director_requirements.model_dump()
    return fingerprint({
        "job": job_payload,
        "plan": plan_artifact.model_dump(), **review_media,
        "asset_metadata": {asset.asset_id: repository.asset_metadata(asset.asset_id) for asset in job.assets},
    })


def director_demo_is_approved(repository: Repository, job: Job) -> bool:
    receipt = None
    for artifact in reversed(job.artifacts):
        if artifact.kind != "stage_review" or artifact.revision != job.revision:
            continue
        path = checked_artifact(repository, job, artifact)
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("node_name") == "director_human_gate":
            receipt = value
            break
    if not receipt or receipt.get("decision") != "confirm" or receipt.get("revision") != job.revision:
        return False
    try:
        _, plan = current_plan_artifact(repository, job)
        if plan.get("review_mode") == SHOT_REVIEW_MODE:
            expected_ids = [shot.shot_id for shot in job.timeline.shots]
            if receipt.get("review_mode") != SHOT_REVIEW_MODE or receipt.get("reviewed_shot_ids") != expected_ids:
                return False
        return receipt.get("dependency_fingerprint") == director_review_fingerprint(repository, job)
    except ValueError:
        return False


def validate_shot_refresh(repository: Repository, job: Job, request: dict, pending: dict) -> None:
    """Refresh only the exact unchanged subject of a current all-shots gate."""
    if (pending.get("kind") != "stage_review" or pending.get("stage") != "director"
            or pending.get("node_name") != "director_human_gate"
            or pending.get("review_mode") != SHOT_REVIEW_MODE
            or pending.get("revision") != job.revision
            or request.get("pending_token") != pending.get("pending_token")):
        raise Conflict("刷新镜头必须绑定当前摄影逐镜审核待办")
    try:
        plan_artifact, plan = current_plan_artifact(repository, job)
        inputs = director_review_fingerprint(repository, job)
    except ValueError as exc:
        raise Conflict(str(exc)) from exc
    if (plan.get("review_mode") != SHOT_REVIEW_MODE
            or request.get("director_plan_artifact_id") != plan_artifact.artifact_id
            or request.get("director_plan_sha256") != plan_artifact.sha256
            or pending.get("dependency_fingerprint") != inputs):
        raise Conflict("待刷新的摄影方案、审核包或制作输入已变化")
