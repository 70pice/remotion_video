"""Bind the approval before collection to this revision's script and evidence."""

import json
from pathlib import Path

from videoagents.contracts import Artifact, Job, Script
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.media import sha256

SCRIPT_REVIEW_NODE = "script_human_gate"
SCRIPT_REVIEW_TITLE = "文案人工审核（素材采集前）"
SCRIPT_REVIEW_REQUIREMENTS = (
    "首句尽早给出有来源的关键事实与观看理由；内容递进，结尾回应问题",
    "逐段核对口播、来源与事实边界，编剧读取记录可供查看",
    "画面需求明确；本门不要求素材采集完成",
    "人工确认本版文案后才允许调用素材节点",
)
SCRIPT_REVIEW_POLICY = {
    "node_name": SCRIPT_REVIEW_NODE, "stage": "script", "title": SCRIPT_REVIEW_TITLE,
    "requirements": SCRIPT_REVIEW_REQUIREMENTS, "min_note_length": 10,
    "finish_on_confirm": False, "revise_route": "screenwriter",
}


def script_review_fingerprint(repository: Repository, job: Job) -> str:
    if not job.script or job.script.revision != job.revision:
        raise Conflict("素材采集前需要本版有效文案及人工确认")
    artifacts = [item for item in job.artifacts if item.revision == job.revision
                 and item.kind in {"script", "writer_tool_audit"}]
    for artifact in artifacts:
        try:
            path, recorded, owner = repository.artifact_path(artifact.artifact_id)
            if owner != job.job_id or recorded != artifact or sha256(path) != artifact.sha256:
                raise Conflict("待审文案或编剧读取记录已改变，请重新生成并审核")
        except (NotFound, OSError) as exc:
            raise Conflict("待审文案或编剧读取记录缺失，请重新生成并审核") from exc
    # Material/audio outputs must not invalidate the already reviewed script.
    return fingerprint({"revision": job.revision, "brief": job.brief.model_dump(),
                        "script": job.script.model_dump(),
                        "artifacts": [item.model_dump() for item in artifacts]})


def _approval(repository: Repository, job: Job, depth: int = 0) -> Artifact | None:
    if depth > 64:
        raise Conflict("素材重启批准链过长或无效")
    expected = script_review_fingerprint(repository, job)
    for artifact in reversed(job.artifacts):
        if artifact.kind != "stage_review" or artifact.revision != job.revision:
            continue
        try:
            path, recorded, owner = repository.artifact_path(artifact.artifact_id)
            if owner != job.job_id or recorded != artifact or sha256(path) != artifact.sha256:
                raise Conflict("文案人工审核回执已改变，不能进入素材采集")
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (NotFound, OSError, ValueError) as exc:
            raise Conflict("文案人工审核回执缺失或无效，不能进入素材采集") from exc
        if receipt.get("node_name") != SCRIPT_REVIEW_NODE:
            continue
        # The latest decision wins; a later revise can never inherit a confirm.
        if (receipt.get("kind") == "stage_review" and receipt.get("stage") == "script"
                and receipt.get("revision") == job.revision and receipt.get("decision") == "confirm"
                and receipt.get("dependency_fingerprint") == expected
                and receipt.get("policy_fingerprint") == fingerprint(SCRIPT_REVIEW_POLICY)):
            return artifact
        return None
    authorization = repository.materials_restart_receipt(job.job_id, job.revision)
    if not authorization:
        return None
    try:
        original = Job.model_validate(authorization["previous_job"])
        preserved = authorization["preserved_script"]
        if (original.job_id != job.job_id or original.revision + 1 != job.revision
                or authorization["source_revision"] != original.revision
                or authorization.get("acknowledge_possible_usage") is not True
                or job.brief != original.brief or not job.script or not original.script
                or job.script.model_copy(update={"revision": original.revision}) != original.script):
            raise Conflict("仅素材重启不能沿用已修改的文案或制作要求")
        retained = {item.artifact_id: item for item in job.artifacts}
        for raw in preserved["artifacts"]:
            artifact = Artifact.model_validate(raw)
            path, recorded, owner = repository.artifact_path(artifact.artifact_id)
            if (retained.get(artifact.artifact_id) != artifact or recorded != artifact
                    or owner != job.job_id or sha256(path) != artifact.sha256):
                raise Conflict("素材重启的原文案、来源或批准记录已改变")
        _validate_preserved_sources(repository, original, preserved["source_files"])
        approval = _approval(repository, original, depth + 1)
        if not approval or approval.artifact_id != preserved["approval_artifact_id"]:
            raise Conflict("素材重启缺少原文案人工批准依据")
        return approval
    except (KeyError, ValueError, NotFound, OSError) as exc:
        raise Conflict("素材重启的原文案批准链或来源文件缺失，不能采集") from exc


def script_before_materials_is_approved(repository: Repository, job: Job) -> bool:
    return _approval(repository, job) is not None


def _validate_preserved_sources(repository: Repository, job: Job, files: list[dict]) -> None:
    folder = repository.root / "jobs" / job.job_id / "revisions"
    for item in files:
        path = Path(item["path"])
        relative = path.relative_to(folder) if path.is_relative_to(folder) else Path()
        if (len(relative.parts) != 3 or not relative.parts[0].isdigit()
                or not 1 <= int(relative.parts[0]) <= job.revision
                or relative.parts[1] != "skills-research" or path.suffix != ".txt"
                or path.resolve() != path or not path.is_file()
                or path.stat().st_size != item["size_bytes"] or sha256(path) != item["sha256"]):
            raise Conflict("素材重启时保存的正文快照已改变或缺失")


def preserve_approved_script(repository: Repository, job: Job) -> dict:
    """Bind existing approval and source bytes without minting a confirm receipt.

    Source snapshots are an additional restart-time check. Older script gates
    bound script/audit artifacts, not these unregistered source files.
    """
    approval = _approval(repository, job)
    if not approval or not job.script:
        raise Conflict("仅素材重启要求原文案已获人工确认")
    if any(segment.asset_ids for segment in job.script.segments):
        raise Conflict("已审文案绑定旧素材，不能清空素材后直接沿用；请重新审核")
    artifacts = [item for item in job.artifacts
                 if item.kind in {"script", "writer_tool_audit", "source"}
                 or item.artifact_id == approval.artifact_id]
    scripts = [item for item in artifacts if item.kind == "script"]
    if not scripts or (job.script.origin == "model" and not any(item.kind == "writer_tool_audit" for item in artifacts)):
        raise Conflict("仅素材重启缺少原文案或编剧读取审计产物")
    for artifact in artifacts:
        path, recorded, owner = repository.artifact_path(artifact.artifact_id)
        if (recorded != artifact or owner != job.job_id
                or not path.is_relative_to(repository.root / "jobs" / job.job_id)
                or sha256(path) != artifact.sha256):
            raise Conflict("仅素材重启的原文案、读取审计或来源产物已改变")
    try:
        path, _, _ = repository.artifact_path(scripts[-1].artifact_id)
        saved = Script.model_validate_json(path.read_text(encoding="utf-8"))
        if saved.model_copy(update={"revision": job.revision}) != job.script:
            raise Conflict("已审文案与保存的实体文件不一致")
    except (ValueError, OSError) as exc:
        raise Conflict("原文案实体文件无效") from exc
    folder = repository.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "skills-research"
    files = []
    if folder.exists():
        if folder.resolve() != folder:
            raise Conflict("编剧来源目录指向链接或离开原版本")
        # Both research roles can write UTF-8 text at this directory's root.
        # This binds currently available bytes, not historical writer provenance
        # or completeness, which older script gates never captured.
        # Never walk CLI auth/temp folders or failed materials' research subtree.
        for path in sorted(folder.glob("*.txt")):
            if path.resolve() != path or not path.is_file() or not 0 < path.stat().st_size <= 1024 * 1024:
                raise Conflict("重启时的正文快照越界、为空或过大")
            path.read_text(encoding="utf-8")
            files.append({"path": str(path), "sha256": sha256(path), "size_bytes": path.stat().st_size})
    prior = repository.materials_restart_receipt(job.job_id, job.revision)
    if prior:
        files = prior["preserved_script"]["source_files"]
    if (job.script.origin == "model" and any(segment.source_refs for segment in job.script.segments)
            and not files and not any(item.kind == "source" for item in artifacts)):
        raise Conflict("重启时没有可得的来源正文，不能只重采素材")
    return {"approval_artifact_id": approval.artifact_id, "approval_revision": approval.revision,
            "artifacts": [item.model_dump() for item in artifacts], "source_files": files,
            "source_snapshot_scope": "restart_time_research_root_texts"}
