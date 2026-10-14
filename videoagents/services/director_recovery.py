"""Carry genuine joint approval and frozen audio into a photography revision."""

import json
import math
from copy import deepcopy

from videoagents.contracts import Alignment, Artifact, Job, Script, VoiceAdvice
from videoagents.nodes.common import needs_script_revision, needs_voice_revision, validate_context_assets
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.script_review import (
    JOINT_REVIEW_NODE,
    JOINT_REVIEW_POLICY,
    script_before_materials_is_approved,
)
from videoagents.nodes.voice import validate_alignment, validate_segment_performances
from videoagents.services.jobs import INVALIDATED
from videoagents.services.settings import SettingsService, voice_fingerprint
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.media import audio_duration, sha256

DIRECTOR_DERIVED = INVALIDATED | {"editing_guidance", "human_review", "human_feedback_applied"}
VOICE_DERIVED = {"voice_guidance", "alignment", "audio_report"}


def _file(repository: Repository, job: Job, artifact: Artifact):
    try:
        path, recorded, owner = repository.artifact_path(artifact.artifact_id)
        if (owner != job.job_id or recorded != artifact or path.stat().st_size != artifact.size_bytes
                or sha256(path) != artifact.sha256):
            raise Conflict("摄影恢复引用的产物文件或登记信息已改变")
        return path
    except (NotFound, OSError) as exc:
        raise Conflict("摄影恢复引用的产物文件缺失") from exc


def _json(repository: Repository, job: Job, artifact: Artifact) -> dict:
    try:
        value = json.loads(_file(repository, job, artifact).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("expected object")
        return value
    except (ValueError, OSError) as exc:
        raise Conflict("摄影恢复引用的 JSON 产物无效") from exc


def retained_director_inputs(repository: Repository, job: Job) -> list[Artifact]:
    """Drop derived references; original records and files remain registered."""
    result = []
    for artifact in job.artifacts:
        if artifact.kind in DIRECTOR_DERIVED:
            continue
        if artifact.kind == "stage_review" and _json(repository, job, artifact).get("stage") != "script":
            continue
        result.append(artifact)
    return result


def _audio(repository: Repository, job: Job):
    validate_context_assets(repository, job)
    selected = repository.active_audio(job.job_id)
    candidates = [item for item in job.assets if item.role == "audio"
                  and (not selected or item.asset_id == selected)]
    if len(candidates) != 1:
        raise Conflict("摄影恢复需要唯一且明确选用的真实音频")
    audio = candidates[0]
    metadata = repository.asset_metadata(audio.asset_id)
    path, _, _ = repository.artifact_path(audio.artifact_id)
    duration = audio_duration(path)
    recorded_duration = metadata.get("duration_seconds")
    if (type(recorded_duration) not in {int, float} or not math.isfinite(recorded_duration)
            or abs(duration - recorded_duration) > .08):
        raise Conflict("摄影恢复音频的实测时长与保存记录不匹配")
    try:
        alignment = Alignment.model_validate(metadata.get("alignment"))
    except ValueError as exc:
        raise Conflict("摄影恢复缺少有效的实测 alignment") from exc
    issues = validate_alignment(job, audio, alignment, duration)
    if issues:
        raise Conflict("摄影恢复音频不匹配：" + "；".join(issues))
    if metadata.get("origin") in {"byte_ws", "byte_http"}:
        expected = fingerprint([{"segment_id": item.segment_id, "narration": item.narration}
                                for item in job.script.segments])
        if (metadata.get("script_fingerprint") != expected
                or metadata.get("voice_fingerprint") != voice_fingerprint(SettingsService(repository).internal())):
            raise Conflict("摄影恢复的生成音频与文案或配音设置不匹配")
    artifacts = retained_director_inputs(repository, job)
    if not any(item.artifact_id == audio.artifact_id for item in artifacts):
        raise Conflict("摄影恢复音频缺少当前产物引用")
    for kind in ("alignment", "audio_report"):
        artifact = next((item for item in reversed(artifacts) if item.kind == kind), None)
        if not artifact:
            raise Conflict("摄影恢复缺少原 alignment 或 audio_report 产物")
        value = _json(repository, job, artifact)
        if kind == "alignment":
            if value != alignment.model_dump():
                raise Conflict("摄影恢复 alignment 产物与音频元数据不匹配")
        elif (value.get("audio_sha256") != audio.sha256 or value.get("verified") is not True
              or value.get("origin") != metadata.get("origin")
              or value.get("alignment_origin") != alignment.origin
              or type(value.get("duration_seconds")) not in {int, float}
              or not math.isfinite(value["duration_seconds"])
              or abs(value["duration_seconds"] - duration) > .08):
            raise Conflict("摄影恢复 audio_report 与真实音频不匹配")
    if metadata.get("origin") in {"byte_ws", "byte_http"}:
        guidance = next((item for item in reversed(artifacts) if item.kind == "voice_guidance"), None)
        if not guidance:
            raise Conflict("摄影恢复缺少已有生成音频的配音指导")
        try:
            advice = VoiceAdvice.model_validate(_json(repository, job, guidance))
            if advice.segment_performances:
                validate_segment_performances(job, advice.segment_performances)
            if (not advice.delivery_notes and not advice.segment_performances
                    or any(item.blocking or item.severity == "error" for item in advice.findings)):
                raise ValueError("invalid original guidance")
        except ValueError as exc:
            raise Conflict("摄影恢复的原配音指导无效或不匹配") from exc
    return audio


def _projection(repository: Repository, job: Job, audio) -> tuple[Job, Artifact]:
    # An old confirm often has no subject snapshot. Only exact fingerprint
    # equality proves that surviving pre-voice inputs are still the reviewed ones.
    artifacts = retained_director_inputs(repository, job)
    approval = None
    for artifact in reversed(artifacts):
        if artifact.kind != "stage_review" or artifact.revision != job.revision:
            continue
        receipt = _json(repository, job, artifact)
        if receipt.get("stage") != "script":
            continue
        if (receipt.get("node_name") != JOINT_REVIEW_NODE or receipt.get("kind") != "stage_review"
                or receipt.get("revision") != job.revision or receipt.get("decision") != "confirm"
                or receipt.get("policy_fingerprint") != fingerprint(JOINT_REVIEW_POLICY)
                or artifact.artifact_id != fingerprint({"job_id": job.job_id,
                                                       "pending_token": receipt.get("pending_token")})[:32]):
            raise Conflict("摄影恢复要求最新文案与素材联合人工确认")
        approval = artifact
        break
    if not approval:
        raise Conflict("摄影恢复缺少当前文案与素材联合人工确认")
    gate = HumanReviewNode(repository, node_name=JOINT_REVIEW_NODE)
    base = job.model_copy(update={"timeline": None, "review": None, "artifacts": artifacts})
    # Imported audio can already be in the reviewed subject. Generated audio is
    # appended afterwards; remove only that active audio and known voice outputs.
    without_voice_outputs = base.model_copy(update={
        "artifacts": [item for item in artifacts if item.kind not in VOICE_DERIVED],
    })
    candidates = [base, without_voice_outputs, without_voice_outputs.model_copy(update={
        "assets": [item for item in base.assets if item.asset_id != audio.asset_id],
        "artifacts": [item for item in without_voice_outputs.artifacts if item.artifact_id != audio.artifact_id],
    })]
    for projected in candidates:
        if gate._inputs(projected) == receipt["dependency_fingerprint"]:
            return projected, approval
    raise Conflict("无法还原联合审核的原输入指纹，不能继承批准")


def preserve_director_inputs(repository: Repository, job: Job, note: str) -> dict:
    if needs_script_revision(note) or needs_voice_revision(note):
        raise Conflict("director_only 的要求不能修改已审文案或音频")
    preserved = verify_director_recovery_inputs(repository, job)
    candidate = _candidate_continuation(repository, job, preserved)
    if candidate:
        preserved["candidate_continuation"] = candidate
    return preserved


def verify_director_recovery_inputs(repository: Repository, job: Job) -> dict:
    """Read-only preflight: verify evidence without authorizing or submitting."""
    if not job.script or job.script.revision != job.revision:
        raise Conflict("摄影恢复需要当前已审文案")
    audio = _audio(repository, job)
    prior = repository.director_restart_receipt(job.job_id, job.revision)
    if prior:
        previous = validate_director_restart(repository, job)
        projection = Job.model_validate(previous["approval_projection"])
        approval = next(item for item in projection.artifacts
                        if item.artifact_id == previous["approval_artifact_id"])
    else:
        if not script_before_materials_is_approved(repository, job):
            raise Conflict("摄影恢复缺少素材前原文案批准链")
        projection, approval = _projection(repository, job, audio)
    artifacts = retained_director_inputs(repository, job)
    for artifact in artifacts:
        _file(repository, job, artifact)
    scripts = [item for item in artifacts if item.kind == "script"]
    if not scripts:
        raise Conflict("摄影恢复缺少原文案实体")
    try:
        saved = Script.model_validate(_json(repository, job, scripts[-1]))
        if saved.model_copy(update={"revision": job.revision}) != job.script:
            raise Conflict("摄影恢复文案与原稿实体不一致")
    except ValueError as exc:
        raise Conflict("摄影恢复原稿实体无效") from exc
    return {"approval_artifact_id": approval.artifact_id, "approval_projection": projection.model_dump(),
            "audio_asset_id": audio.asset_id, "artifacts": [item.model_dump() for item in artifacts],
            "asset_metadata": {item.asset_id: repository.asset_metadata(item.asset_id) for item in job.assets}}


def validate_director_restart(repository: Repository, job: Job) -> dict:
    """Recheck original evidence before a new run; no approval is synthesized."""
    authorization = repository.director_restart_receipt(job.job_id, job.revision)
    try:
        original = Job.model_validate(authorization["previous_job"])
        preserved = authorization["preserved_director"]
        if (authorization.get("acknowledge_possible_usage") is not True
                or original.job_id != job.job_id or original.revision + 1 != job.revision
                or authorization["source_revision"] != original.revision
                or authorization["provider"] != "llm:director"
                or original.brief != job.brief or not job.script
                or job.script.model_copy(update={"revision": original.revision}) != original.script
                or job.assets != original.assets or job.director_requirements != original.director_requirements):
            raise Conflict("摄影恢复的文案、Brief、素材或摄影约束已改变")
        current = {item.artifact_id: item for item in job.artifacts}
        for raw in preserved["artifacts"]:
            artifact = Artifact.model_validate(raw)
            if current.get(artifact.artifact_id) != artifact:
                raise Conflict("摄影恢复的原始证据引用已改变")
            _file(repository, job, artifact)
        if preserved["asset_metadata"] != {item.asset_id: repository.asset_metadata(item.asset_id)
                                            for item in job.assets}:
            raise Conflict("摄影恢复的素材或音频元数据已改变")
        projection = Job.model_validate(preserved["approval_projection"])
        receipt_artifact = next(item for item in projection.artifacts
                                if item.artifact_id == preserved["approval_artifact_id"])
        receipt = _json(repository, job, receipt_artifact)
        if (projection.job_id != job.job_id or projection.brief != job.brief or not projection.script
                or projection.script.model_copy(update={"revision": job.revision}) != job.script
                or receipt.get("decision") != "confirm" or receipt.get("node_name") != JOINT_REVIEW_NODE
                or receipt.get("policy_fingerprint") != fingerprint(JOINT_REVIEW_POLICY)
                or HumanReviewNode(repository, node_name=JOINT_REVIEW_NODE)._inputs(projection)
                != receipt.get("dependency_fingerprint")
                or not script_before_materials_is_approved(repository, projection)):
            raise Conflict("摄影恢复的原联合批准输入或批准链已改变")
        if _audio(repository, job).asset_id != preserved["audio_asset_id"]:
            raise Conflict("摄影恢复选用的音频已改变")
        if preserved.get("candidate_continuation"):
            _validate_candidate_receipt(repository, job, preserved, preserved["candidate_continuation"])
        return preserved
    except (KeyError, TypeError, StopIteration, ValueError, NotFound, OSError) as exc:
        raise Conflict("摄影恢复的批准链或媒体凭据缺失或无效") from exc


def _model_identity(repository: Repository) -> dict:
    """Read only nonsecret model configuration; never decrypt credentials."""
    from videoagents.default_config import DEFAULT_SETTINGS
    from videoagents.providers.cli_runner import GLM_CONTEXT_TOKENS, GLM_MODEL

    with repository.connection() as db:
        stored = {row[0]: json.loads(row[1]) for row in db.execute(
            "SELECT key,value FROM settings WHERE key IN ('role_models','glm_reasoning_effort')")}
    config = deepcopy(stored.get("role_models", DEFAULT_SETTINGS["role_models"])["director"])
    identity = {"cli_provider": config["provider"], "model": config["model"]}
    if config["provider"] == "claude_code_cli" and config["model"].lower().startswith("glm-"):
        if config["model"].lower().removesuffix("[1m]") != "glm-5.3":
            raise Conflict("摄影候选模型配置不是支持的 GLM-5.3[1m]")
        config["model"] = identity["model"] = GLM_MODEL
        identity.update(reasoning_effort=stored.get("glm_reasoning_effort", DEFAULT_SETTINGS["glm_reasoning_effort"]),
                        context_tokens=GLM_CONTEXT_TOKENS)
    elif config["provider"] == "codex_cli" and config.get("codex_reasoning_effort") is not None:
        identity["reasoning_effort"] = config["codex_reasoning_effort"]
    if not config["enabled"]:
        raise Conflict("摄影完成候选接续需要启用原摄影模型")
    return {"config": config, "ledger": identity}


def _business_fingerprint(job: Job, preserved: dict) -> str:
    return fingerprint({"job_id": job.job_id, "brief": job.brief.model_dump(),
        "script": job.script.model_copy(update={"revision": 0}).model_dump(),
        "assets": [asset.model_dump() for asset in job.assets],
        "director_requirements": job.director_requirements.model_dump() if job.director_requirements else None,
        "approval_artifact_id": preserved["approval_artifact_id"], "audio_asset_id": preserved["audio_asset_id"],
        "asset_metadata": preserved["asset_metadata"], "artifacts": preserved["artifacts"]})


def _completed_by_id(repository: Repository, job_id: str, operation_id: str) -> dict:
    with repository.connection() as db:
        row = db.execute("SELECT job_id,input_hash,provider,status,body FROM operations WHERE operation_id=?",
                         (operation_id,)).fetchone()
    if not row or row[0] != job_id or row[2] != "llm:director" or row[3] != "COMPLETED":
        raise Conflict("摄影候选必须来自同任务已完成的摄影回执")
    body = json.loads(row[4])
    if (not isinstance(body.get("result"), dict) or not isinstance(body["result"].get("shots"), list)
            or not body["result"]["shots"] or any(type(shot) is not dict for shot in body["result"]["shots"])):
        raise Conflict("已完成摄影回执没有完整候选")
    return {"operation_id": operation_id, "input_hash": row[1], "body": body}


def _unknown_source(repository: Repository, job_id: str, revision: int, pending: dict) -> dict:
    if (pending.get("kind") != "input" or pending.get("stage") != "director"
            or pending.get("revision") != revision or pending.get("operation_status") != "UNKNOWN"):
        raise Conflict("摄影候选接续缺少源版本的未知修复提交关联")
    with repository.connection() as db:
        row = db.execute("SELECT job_id,input_hash,provider,status,body FROM operations WHERE operation_id=?",
                         (pending.get("operation_id"),)).fetchone()
    if (not row or row[0] != job_id or row[2] != "llm:director" or row[3] != "UNKNOWN"
            or json.loads(row[4]).get("revision") != revision):
        raise Conflict("摄影候选接续的源未知操作归属或状态不匹配")
    return {"operation_id": pending["operation_id"], "input_hash": row[1], "body": json.loads(row[4])}


def _validate_candidate_receipt(repository: Repository, job: Job, preserved: dict, candidate: dict) -> dict:
    operation = _completed_by_id(repository, job.job_id, candidate["operation_id"])
    unknown = _unknown_source(repository, job.job_id, candidate["source_revision"], candidate["source_pending"])
    if (operation["body"].get("revision") != candidate["source_revision"]
            or fingerprint(operation) != candidate["operation_fingerprint"]
            or fingerprint(unknown) != candidate["unknown_operation_fingerprint"]
            or _model_identity(repository)["ledger"] != candidate["model_identity"]
            or _business_fingerprint(job, preserved) != candidate["business_fingerprint"]):
        raise Conflict("摄影完成候选的回执、模型或已审输入已改变")
    return operation


def _candidate_continuation(repository: Repository, job: Job, preserved: dict) -> dict | None:
    """Prove an old COMPLETE result without submitting, accepting or rewriting it."""
    current = job
    while True:
        authorization = repository.director_restart_receipt(job.job_id, current.revision)
        current_preserved = (validate_director_restart(repository, current) if authorization
                             else verify_director_recovery_inputs(repository, current))
        if _business_fingerprint(current, current_preserved) != _business_fingerprint(job, preserved):
            raise Conflict("摄影候选源版本与当前已审上游不一致")
        inherited = current_preserved.get("candidate_continuation")
        if inherited:
            _validate_candidate_receipt(repository, job, preserved, inherited)
            return inherited
        if current.timeline is not None:
            # This bridge repairs rejected, uncommitted candidates. A previous
            # accepted timeline has its existing feedback/rebuild semantics.
            return None
        completed = repository.latest_completed_operation(job.job_id, "llm:director", current.revision)
        if completed:
            operation = _completed_by_id(repository, job.job_id, completed["operation_id"])
            return _prove_initial_candidate(repository, current, current_preserved, operation)
        if not authorization:
            return None
        current = Job.model_validate(authorization["previous_job"])


def _prove_initial_candidate(repository: Repository, source: Job, preserved: dict, operation: dict) -> dict:
    from videoagents.nodes.common import state_context
    from videoagents.nodes.director import DirectorNode
    from videoagents.providers.llm import request_fingerprint
    from videoagents.state import VideoState, clean_handoff

    model = _model_identity(repository)
    body = operation["body"]
    if any(body.get(key) != value for key, value in model["ledger"].items()):
        raise Conflict("摄影完成候选与当前模型配置不一致")
    if source.timeline is not None:
        raise Conflict("摄影候选的初始请求无法从当前源版本证明")

    class SourceRepository:
        """Only substitute the proven historical Job; all other reads stay authoritative."""
        def get_job(self, job_id):
            if job_id != source.job_id:
                raise Conflict("摄影候选上下文引用其他任务")
            return source

        def __getattr__(self, name):
            return getattr(repository, name)

    captured = []

    class CaptureModel:
        def available(self, role):
            return role == "director"

        def invoke(self, state, role, instruction, *, fields, command_id="", output_schema=None):
            if role != "director" or captured:
                raise Conflict("摄影候选只读捕获调用不匹配")
            shared = clean_handoff(state)
            context = {key: shared[key] for key in fields if key in shared}
            value = request_fingerprint(source.revision, model["config"], instruction, output_schema, context,
                                        glm_reasoning_effort=model["ledger"].get("reasoning_effort"))
            if value != operation["input_hash"]:
                raise Conflict("无法复算摄影完成候选的原输入指纹，不能继承")
            captured.append(value)
            return deepcopy(body["result"])

    snapshot = SourceRepository()
    state = state_context(snapshot, VideoState(job_id=source.job_id, revision=source.revision,
        action="produce", route="director", gate_issues=[], extras={}))
    audio = next(asset for asset in source.assets if asset.asset_id == preserved["audio_asset_id"])
    metadata = preserved["asset_metadata"][audio.asset_id]
    node = DirectorNode(snapshot, None)
    node.model = CaptureModel()
    issues = []
    try:
        node.plan(source, audio, Alignment.model_validate(metadata["alignment"]),
                  metadata["duration_seconds"], state=state, restore_candidate=False)
    except ValueError as exc:
        if not captured:
            raise Conflict("无法在原摄影构造入口证明候选") from exc
        issues = [str(exc)]
    if not captured:
        raise Conflict("摄影候选未进入原模型请求构造入口")
    return {"operation_id": operation["operation_id"], "source_revision": source.revision,
            "operation_fingerprint": fingerprint(operation), "input_hash": operation["input_hash"],
            "model_identity": model["ledger"], "business_fingerprint": _business_fingerprint(source, preserved),
            "repair_issues": issues, "shot_count": len(body["result"]["shots"]),
            "source_pending": deepcopy(source.pending_input),
            "unknown_operation_fingerprint": fingerprint(
                _unknown_source(repository, source.job_id, source.revision, source.pending_input or {}))}


def verify_director_candidate_continuation(repository: Repository, job: Job) -> dict:
    """Read-only discovery; no candidate contents, new revision, approval or provider call."""
    preserved = verify_director_recovery_inputs(repository, job)
    candidate = _candidate_continuation(repository, job, preserved)
    safe_keys = ("operation_id", "source_revision", "operation_fingerprint", "input_hash", "model_identity",
                 "business_fingerprint", "repair_issues", "shot_count", "unknown_operation_fingerprint")
    return {"available": candidate is not None,
            **({key: candidate[key] for key in safe_keys} if candidate else {})}


def director_repair_candidate(repository: Repository, job: Job) -> dict | None:
    authorization = repository.director_restart_receipt(job.job_id, job.revision)
    if not authorization:
        return None
    preserved = validate_director_restart(repository, job)
    candidate = preserved.get("candidate_continuation")
    if not candidate:
        return None
    operation = _validate_candidate_receipt(repository, job, preserved, candidate)
    return {"operation_id": candidate["operation_id"], "result": operation["body"]["result"],
            "repair_issues": candidate["repair_issues"]}
