"""Scoped partial decisions and their immutable, current-revision receipts."""

import json
from typing import Any

from videoagents.contracts import Job, MaterialSelectionRequest
from videoagents.storage import Conflict, Repository
from videoagents.tools.media import sha256

MATERIAL_SELECTION_NODE = "human_review_script"


def validate_material_selection(job: Job, pending: dict[str, Any], request: MaterialSelectionRequest) -> None:
    if (job.status != "NEEDS_HUMAN" or job.stage != "script"
            or pending.get("kind") != "stage_review" or pending.get("stage") != "script"
            or pending.get("node_name") != MATERIAL_SELECTION_NODE
            or pending.get("revision") != job.revision or request.base_revision != job.revision
            or pending.get("pending_token") != request.pending_token):
        raise Conflict("素材部分取舍仅适用于当前文案与素材人工审核待办")
    selected = set(request.accepted_asset_ids) | set(request.rejected_asset_ids)
    assets = {item.asset_id: item for item in job.assets}
    if selected - assets.keys():
        raise Conflict("素材取舍包含不属于当前任务有效素材的ID")
    if any(assets[key].role == "audio" or not assets[key].mime_type.startswith(("image/", "video/"))
           for key in selected):
        raise Conflict("素材取舍只能指定当前图片或视频，不能修改配音")
    bound = {key for segment in job.script.segments for key in segment.asset_ids} if job.script else set()
    if bound & set(request.rejected_asset_ids):
        raise Conflict("被拒素材已绑定已审文案；不能通过素材取舍静默改稿")
    if job.timeline:
        raise Conflict("已有分镜不能在文案与素材门中部分取舍，请通过画面返工处理")


def selection_receipts(repo: Repository, job: Job) -> list[dict[str, Any]]:
    """Read committed receipts only; historical registry files are not decisions."""
    receipts = []
    for artifact in job.artifacts:
        if artifact.kind != "stage_review" or artifact.revision != job.revision:
            continue
        path, registered, owner = repo.artifact_path(artifact.artifact_id)
        if owner != job.job_id or registered != artifact or sha256(path) != artifact.sha256:
            raise Conflict("素材取舍审核记录已改变")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("decision") == "select_materials":
            if receipt.get("node_name") != MATERIAL_SELECTION_NODE or receipt.get("revision") != job.revision:
                raise Conflict("素材取舍审核记录不属于当前人工门")
            receipts.append(receipt)
    return receipts
