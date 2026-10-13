"""Bind the approval before collection to this revision's script and evidence."""

import json

from videoagents.contracts import Job
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


def script_before_materials_is_approved(repository: Repository, job: Job) -> bool:
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
        return (receipt.get("kind") == "stage_review" and receipt.get("stage") == "script"
                and receipt.get("revision") == job.revision and receipt.get("decision") == "confirm"
                and receipt.get("dependency_fingerprint") == expected
                and receipt.get("policy_fingerprint") == fingerprint(SCRIPT_REVIEW_POLICY))
    return False
