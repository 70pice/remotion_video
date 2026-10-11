"""Bind director approval to the exact plan, demo and production inputs."""

import json

from videoagents.contracts import Artifact, Job
from videoagents.nodes.director import load_current_director_plan
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.media import sha256


def checked_artifact(repository: Repository, job: Job, artifact: Artifact):
    try:
        path, registered, owner = repository.artifact_path(artifact.artifact_id)
        if owner != job.job_id or registered != artifact or sha256(path) != artifact.sha256:
            raise Conflict("导演待审产物已改变，请重新生成并审核")
        return path
    except (NotFound, OSError) as exc:
        raise Conflict("导演待审产物缺失，请重新生成并审核") from exc


def current_plan_artifact(repository: Repository, job: Job, *, validate_components: bool = True) -> tuple[Artifact, dict]:
    artifact = next((item for item in reversed(job.artifacts)
                     if item.kind == "director_plan" and item.revision == job.revision), None)
    if artifact is None:
        raise ValueError("缺少当前导演镜头及Demo设计，请返回导演节点")
    checked_artifact(repository, job, artifact)
    plan = load_current_director_plan(repository, job, validate_components=validate_components)
    if plan is None or plan.get("job_id") != job.job_id or plan.get("revision") != job.revision:
        raise ValueError("导演方案与当前任务或分镜不一致，请重新设计")
    demo = plan.get("demo", {})
    start, end = demo.get("start_frame"), demo.get("end_frame")
    if (not job.timeline or type(start) is not int or type(end) is not int
            or not 0 <= start < end <= job.timeline.duration_in_frames
            or end - start > 30 * job.timeline.fps):
        raise ValueError("导演Demo必须是当前时间轴内最长30秒的连续区间")
    return artifact, plan


def current_demo_artifact(repository: Repository, job: Job, *, validate_components: bool = True) -> Artifact:
    plan_artifact, plan = current_plan_artifact(repository, job, validate_components=validate_components)
    preview = next((item for item in reversed(job.artifacts)
                    if item.kind == "preview" and item.revision == job.revision), None)
    if preview is None:
        raise ValueError("当前导演方案尚未生成真实Demo")
    checked_artifact(repository, job, preview)
    metadata = repository.artifact_metadata(preview.artifact_id)
    demo = plan["demo"]
    if (metadata.get("dependency_fingerprint") != dependency_fingerprint(job)
            or metadata.get("director_plan_sha256") != plan_artifact.sha256
            or metadata.get("frame_range") != [demo["start_frame"], demo["end_frame"]]):
        raise ValueError("Demo与当前导演方案、素材或时间区间不一致，请重新生成")
    return preview


def director_review_fingerprint(repository: Repository, job: Job, *, validate_components: bool = True) -> str:
    plan_artifact, _ = current_plan_artifact(repository, job, validate_components=validate_components)
    preview = current_demo_artifact(repository, job, validate_components=validate_components)
    for asset in job.assets:
        try:
            path, registered, owner = repository.artifact_path(asset.artifact_id)
            if (owner != job.job_id or registered.sha256 != asset.sha256
                    or sha256(path) != asset.sha256):
                raise Conflict("导演待审素材已改变，请重新生成并审核")
        except (NotFound, OSError) as exc:
            raise Conflict("导演待审素材缺失，请重新生成并审核") from exc
    # Downstream editing advice and final outputs must not invalidate replay.
    job_payload = job.model_dump(include={"revision", "brief", "script", "timeline", "assets"})
    if job.director_requirements is not None:
        job_payload["director_requirements"] = job.director_requirements.model_dump()
    return fingerprint({
        "job": job_payload,
        "plan": plan_artifact.model_dump(), "demo": preview.model_dump(),
        "demo_metadata": repository.artifact_metadata(preview.artifact_id),
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
        return receipt.get("dependency_fingerprint") == director_review_fingerprint(repository, job)
    except ValueError:
        return False
