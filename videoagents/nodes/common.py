"""Shared job checks and input requests used directly by production nodes."""

import json
import math
import uuid
from typing import Any

from videoagents.contracts import Artifact, Job, ScriptDiscussion
from videoagents.services.jobs import INVALIDATED, JobService
from videoagents.services.settings import SettingsService
from videoagents.state import (
    VideoState,
    clean_handoff,
    job_context,
    job_from_state,
    merge_extras,
    validate_json,
)
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.storage.repository import dumps, fingerprint
from videoagents.tools.media import sha256
from videoagents.tools.timeline import safe_media_source
from worker.process_manager import RenderCancelled


def validate_context_assets(repository: Repository, job: Job) -> None:
    """Bind context-supplied media to this job's registered file receipts."""
    if len({item.asset_id for item in job.assets}) != len(job.assets):
        raise Conflict("上下文素材 ID 不能重复")
    for asset in job.assets:
        try:
            path, artifact, owner = repository.artifact_path(asset.artifact_id)
            if owner != job.job_id:
                raise Conflict("上下文素材不属于当前任务")
            declared = (asset.sha256, asset.size_bytes, asset.mime_type, asset.url)
            registered = (artifact.sha256, artifact.size_bytes, artifact.mime_type, artifact.url)
            if declared != registered or path.stat().st_size != asset.size_bytes or sha256(path) != asset.sha256:
                raise Conflict("上下文素材与登记文件不一致")
        except (NotFound, OSError) as exc:
            raise Conflict("上下文素材没有有效的登记文件") from exc
        safe_media_source(asset.timeline_src, job.job_id)
        if (asset.role == "audio") != asset.mime_type.startswith("audio/"):
            raise Conflict("上下文素材类型与用途不一致")
        metadata = repository.asset_metadata(asset.asset_id)
        validate_json(metadata)
        if asset.role == "audio":
            duration = metadata.get("duration_seconds")
            if type(duration) not in {float, int} or not math.isfinite(duration) or duration <= 0 or not metadata.get("origin"):
                raise Conflict("上下文音频缺少实测时长或来源元信息")


def current_job(repository: Repository, state: VideoState) -> Job:
    """节点入口校验与业务同步：保存合法上下文修改，补齐 state，并返回 Job。

    为恢复时复用已提交结果提供保护；外部调用的提交去重由操作台账负责。
    """
    # 1. 读取数据库中的最新任务，先确认这次执行仍然有效。
    job = repository.get_job(state["job_id"])
    # revision 是业务版本：用户保存新版本后，旧工作流不能继续处理旧稿。
    if job.revision != state["revision"]:
        raise Conflict("执行版本已失效")
    # 数据库中的取消状态优先，防止旧 checkpoint 继续执行已取消的任务。
    if job.status == "CANCELLED":
        raise RenderCancelled("任务已取消")

    # 2. 校验上下文，并找出需要保存的业务修改。
    # 此处只使用 merge_extras 的 JSON 校验能力，返回的合并结果不写入 state。
    merge_extras({}, state.get("extras", {}))
    # 将允许修改的字段合入 Job 并校验。
    # 若 SQL 的事件水位领先 checkpoint，直接复用 SQL 结果，避免旧上下文覆盖新结果。
    inputs = job_from_state(state, job)
    # getattr(inputs, name) 相当于 inputs.brief / inputs.script 等属性访问。
    # 只保存这四类业务字段中与数据库不同的值；相同输入不会重复写入任务。
    changes = {name: getattr(inputs, name) for name in ("brief", "script", "timeline", "assets")
               if getattr(inputs, name) != getattr(job, name)}
    if changes:
        # 3. 已进入本次文案讨论的输入被冻结，修改必须创建新版本，重新讨论。
        if (job.script_discussion and job.script_discussion.run_id == state.get("run_id")
                and job.script_discussion.enabled and job.script_discussion.rounds):
            raise Conflict("讨论中的文案及其输入请通过保存新版本修改，避免沿用旧稿的审查决定")
        # 人工回复绑定了原来的待审内容，不能在等待回复期间直接替换内容。
        if job.pending_input:
            raise Conflict("人工待办的内容已冻结，请修改并保存新版本后重新执行")
        # 素材有变化时，核验任务归属、登记信息、真实文件 hash、路径及音频元信息。
        if "assets" in changes:
            validate_context_assets(repository, inputs)

        # 4. 输入变化后，计算不能继续沿用的产物类型。
        # | 是集合并集：在通用下游失效清单上追加阶段人审和剪辑指导记录。
        invalidated = INVALIDATED | {"stage_review", "editing_guidance"}
        # 文案或制作要求改变后，旧稿件产物、对齐报告和朗读建议也需要重新生成。
        if "script" in changes or "brief" in changes:
            invalidated |= {"script", "alignment", "audio_report", "voice_guidance"}
        if "brief" in changes:
            # 制作要求改变后，旧研究与来源产物不再作为当前执行的冻结依据。
            invalidated |= {"research", "material_skill_manifest", "material_tool_audit", "source"}
            # 主题或原始文案改变，且没有同时提交不同的新稿时，清空旧生成稿。
            if "script" not in changes and (
                inputs.brief.topic != job.brief.topic or inputs.brief.script_text != job.brief.script_text
            ):
                changes["script"] = None
        # & 是集合交集：上游要求、文案或素材有变化，又未提交新分镜时，清空旧分镜。
        if set(changes) & {"brief", "script", "assets"} and "timeline" not in changes:
            changes["timeline"] = None
        # 清空旧审核、讨论和进度；移除当前任务对失效产物的引用，文件本身仍保留。
        changes.update(review=None, script_discussion=None, progress=None,
                       artifacts=[item for item in job.artifacts if item.kind not in invalidated],
                       status="RUNNING", message="节点已更新上下文，下游产物与审核已失效")

        # 5. 在阶段更新或暂停写入推进事件水位之前，先提交业务修改，防止合法增量丢失。
        # expected_event_id 是并发检查：读取后若有其他写入推进水位，本次提交会被拒绝。
        # **changes 将字典展开为 update_job 的关键字参数，例如 script=新稿。
        job = repository.update_job(job.job_id, job.revision, expected_event_id=job.latest_event_id, **changes)

    # 6. 原地补齐共享上下文，让当前节点拿到最新业务数据、配置及阶段回执。
    # 即使没有业务修改，也要刷新 state，兼容旧精简 checkpoint 和 SQL 领先的恢复场景。
    refreshed = state_context(repository, state)
    state.clear()
    state.update(refreshed)
    # 返回 Job 供本节点的业务方法使用；后续节点之间仍通过 VideoState 交接。
    return job


def state_context(repository: Repository, state: VideoState, **overrides: Any) -> VideoState:
    """恢复已提交的最终产物，清理工具过程后交给下一节点。"""
    # Include artifacts registered after the caller's earlier Job snapshot.
    job = repository.get_job(state["job_id"])
    if job.revision != state["revision"]:
        raise Conflict("执行版本已失效")
    context = {**state, **job_context(job)}
    # invoke() adds runtime Interrupt objects outside the VideoState channels.
    # The durable pending_input receipt carries the question as JSON instead.
    context.pop("__interrupt__", None)
    context.setdefault("human_decision", None)
    context.setdefault("stage_review_pending", None)
    context.setdefault("human_review_rounds", {})
    context.setdefault("pending_snapshot", None)
    context["settings"] = SettingsService(repository).public()
    context["extras"] = merge_extras(state.get("extras", {}), overrides.pop("extras", {}))
    metadata = {item.asset_id: repository.asset_metadata(item.asset_id) for item in job.assets}
    context["asset_metadata"] = metadata
    context["artifact_metadata"] = {item.artifact_id: repository.artifact_metadata(item.artifact_id)
                                    for item in job.artifacts}
    selected = repository.active_audio(job.job_id) or state.get("audio_asset_id")
    audio = next((item for item in reversed(job.assets) if item.role == "audio"
                  and (not selected or item.asset_id == selected)), None)
    audio_metadata = metadata.get(audio.asset_id, {}) if audio else {}
    context.update(audio=audio.model_dump() if audio else None,
                   audio_asset_id=audio.asset_id if audio else None,
                   alignment=audio_metadata.get("alignment"), duration_seconds=audio_metadata.get("duration_seconds"))
    context.update(research={}, audio_report=None, voice_guidance=None, editing_guidance=None,
                   render={item.kind: item.model_dump() for item in job.artifacts
                           if item.kind in {"preview", "final", "cover", "captions", "package"}})
    history = list(state.get("human_reviews", []))
    restored_component_study = False
    for artifact in job.artifacts:
        if artifact.revision != job.revision or artifact.kind not in {
            "research", "audio_report", "voice_guidance", "editing_guidance", "component_study",
            "stage_review", "human_review", "human_feedback_applied",
        }:
            continue
        path, _, owner = repository.artifact_path(artifact.artifact_id)
        if owner != job.job_id or sha256(path) != artifact.sha256:
            raise Conflict("上下文引用的阶段记录已改变")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if artifact.kind in {"stage_review", "human_review"}:
            receipt = {**receipt, "artifact_id": artifact.artifact_id}
            history = [item for item in history if item.get("artifact_id") != artifact.artifact_id] + [receipt]
        elif artifact.kind == "human_feedback_applied":
            stage = receipt.get("stage")
            current_feedback = context.get("extras", {}).get("human_feedback", {})
            current_entry = current_feedback.get(stage) if type(current_feedback) is dict else None
            if (type(stage) is str and type(current_entry) is dict
                    and current_entry.get("pending_token") == receipt.get("pending_token")):
                context["extras"] = merge_human_feedback(context["extras"], stage,
                    {"applied": True, "applied_artifact_id": artifact.artifact_id,
                     "applied_target": receipt.get("target")})
        elif artifact.kind == "component_study":
            context["extras"] = merge_extras(context["extras"], {"component_study": receipt})
            restored_component_study = True
        else:
            context[artifact.kind] = receipt
    if not restored_component_study and "component_study" in context.get("extras", {}):
        context["extras"] = merge_extras(context["extras"], {"component_study": None})
    decision = overrides.get("human_decision")
    if decision and not any(item.get("pending_token") == decision.get("pending_token") for item in history):
        history.append(decision)
    context["human_reviews"] = history
    if job.script_discussion and job.script_discussion.run_id == state.get("run_id"):
        context["discussion_policy"] = job.script_discussion.model_dump(include={"run_id", "revision", "enabled", "max_rounds"})
    with repository.connection() as db:
        context["metrics"] = {row[0]: row[1] for row in db.execute(
            "SELECT metric,value FROM run_metrics WHERE job_id=? AND revision=?", (job.job_id, job.revision))}
    context.update(overrides)
    return clean_handoff(context)



def merge_human_feedback(extras: dict[str, Any], stage: str, patch: dict[str, Any]) -> dict[str, Any]:
    feedback = extras.get("human_feedback", {})
    if type(feedback) is not dict:
        feedback = {}
    merged = dict(feedback)
    entry = dict(merged.get(stage, {})) if type(merged.get(stage, {})) is dict else {}
    entry.update(patch)
    merged[stage] = entry
    return merge_extras(extras, {"human_feedback": merged})


def stage_feedback(state: VideoState, *stages: str) -> dict[str, Any] | None:
    """Return unapplied final human revision feedback for one requested stage."""
    feedback = state.get("extras", {}).get("human_feedback", {})
    if type(feedback) is not dict:
        return None
    for stage in stages:
        item = feedback.get(stage)
        if (type(item) is dict and item.get("decision") == "revise" and item.get("note")
                and item.get("applied") is not True):
            return item
    return None


def mark_feedback_applied(repository: Repository, service: JobService, job: Job, state: VideoState,
                          stage: str, target: str) -> None:
    item = state.get("extras", {}).get("human_feedback", {}).get(stage)
    if type(item) is not dict or item.get("decision") != "revise" or item.get("applied") is True:
        return
    receipt = {"stage": stage, "target": target, "pending_token": item.get("pending_token"),
               "note": item.get("note"), "applied": True, "revision": job.revision}
    artifact = service.write_json(job, f"human-feedback-{stage}-{item.get('pending_token', 'unknown')}.json",
                                  receipt, "human_feedback_applied")
    state["extras"] = merge_human_feedback(state.get("extras", {}), stage,
                                            {"applied": True, "applied_artifact_id": artifact.artifact_id,
                                             "applied_target": target})

def agent_state(repository: Repository, job: Job, state: VideoState | None = None) -> VideoState:
    """图内角色共用传入 state；直接调用业务 helper 时也从相同恢复入口取产物。"""
    if state is not None:
        return state
    return state_context(repository, VideoState(job_id=job.job_id, revision=job.revision))


def start_stage(repository: Repository, state: VideoState, stage: str, message: str) -> Job:
    current_job(repository, state)
    return repository.update_job(state["job_id"], state["revision"], status="RUNNING", stage=stage,
                                 message=message, progress=None, pending_input=None)


def request_input(repository: Repository, state: VideoState, stage: str, issues: list[str],
                  fields: list[str] | None = None, exception: Exception | None = None) -> dict[str, Any]:
    current_job(repository, state)
    pending = {"kind": "input", "stage": stage, "issues": issues, "fields": fields or [],
               "thread_id": state["thread_id"], "revision": state["revision"], "pending_token": uuid.uuid4().hex}
    # Keep provider submission receipts when work must pause; UNKNOWN cannot be
    # treated as a fresh request on resume.
    for key in ("operation_status", "operation_id", "request_id"):
        value = getattr(exception, key, None)
        if value:
            pending[key] = value
    repository.update_job(state["job_id"], state["revision"], status="NEEDS_INPUT", stage=stage,
                          message="；".join(issues)[:2000], pending_input=pending)
    return state_context(repository, state, route="await_input", gate_issues=issues, pending_snapshot=pending)


def current_discussion(repository: Repository, state: VideoState, job: Job) -> ScriptDiscussion:
    # SQL may be one node ahead after a crash before checkpoint. Reuse the
    # committed turn, including its frozen policy, instead of calling again.
    if job.script_discussion and job.script_discussion.run_id == state["run_id"]:
        discussion = job.script_discussion.model_copy(deep=True)
    elif state.get("script_discussion") and state["script_discussion"].get("run_id") == state["run_id"]:
        discussion = ScriptDiscussion.model_validate(state["script_discussion"])
    elif state.get("discussion_policy") and state["discussion_policy"].get("run_id") == state["run_id"]:
        policy = state["discussion_policy"]
        discussion = ScriptDiscussion(**policy, status="DISCUSSING" if policy["enabled"] else "DISABLED")
    else:
        settings = SettingsService(repository).internal()
        enabled = settings["script_discussion_enabled"]
        discussion = ScriptDiscussion(run_id=state["run_id"], revision=job.revision, enabled=enabled,
            max_rounds=settings["script_discussion_max_rounds"], status="DISCUSSING" if enabled else "DISABLED")
        # Freeze policy before the first model request, including a request
        # that pauses without producing any draft or graph update.
        repository.update_job(job.job_id, job.revision, script_discussion=discussion)
    if discussion.run_id != state["run_id"] or discussion.revision != job.revision:
        raise Conflict("文案讨论对应的执行或版本已失效")
    state["discussion_policy"] = discussion.model_dump(include={"run_id", "revision", "enabled", "max_rounds"})
    return discussion


def save_discussion(repository: Repository, state: VideoState, discussion: ScriptDiscussion) -> Job:
    """Commit one immutable discussion receipt and its script together in SQL."""
    job = current_job(repository, state)
    script = discussion.rounds[-1].script
    script_changed = script != job.script
    invalidated = {"script", "script_discussion"} | (INVALIDATED if script_changed else set())
    artifacts = [item for item in job.artifacts if item.kind not in invalidated]
    folder = repository.root / "jobs" / job.job_id / "revisions" / str(job.revision)
    folder.mkdir(parents=True, exist_ok=True)
    for kind, value in (("script", script.model_dump()), ("script_discussion", discussion.model_dump())):
        encoded = dumps(value)
        artifact_id = fingerprint({"job_id": job.job_id, "run_id": discussion.run_id,
                                   "revision": job.revision, "kind": kind, "content": value})[:32]
        path = folder / f"{kind}-{artifact_id}.json"
        if path.exists():
            if path.read_text(encoding="utf-8") != encoded:
                raise Conflict("文案讨论的冻结记录已改变")
        else:
            temporary = path.with_suffix(".pending")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(path)
        artifact = Artifact(artifact_id=artifact_id, kind=kind, name=path.name, mime_type="application/json",
                            size_bytes=path.stat().st_size, sha256=sha256(path),
                            url=f"/api/artifacts/{artifact_id}", revision=job.revision)
        try:
            _, existing, _ = repository.artifact_path(artifact_id)
            if existing != artifact:
                raise Conflict("文案讨论产物与持久化记录不一致")
        except NotFound:
            repository.put_artifact(job.job_id, artifact, path)
        artifacts.append(artifact)
    changes: dict[str, Any] = {"script": script, "script_discussion": discussion, "artifacts": artifacts}
    if script_changed:
        changes.update(timeline=None, review=None)
    return repository.update_job(job.job_id, job.revision, **changes)
