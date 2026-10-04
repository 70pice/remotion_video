"""The serializable context shared by built-in and user-composed nodes."""

import math
from typing import Annotated, Any, TypedDict

from videoagents.contracts import Job
from videoagents.storage import Conflict


def validate_json(value: Any) -> None:
    """Accept JSON values only; checkpoint serialization must never coerce objects."""
    active: set[int] = set()

    def visit(item: Any) -> None:
        if item is None or type(item) in {str, bool, int}:
            return
        if type(item) is float and math.isfinite(item):
            return
        if type(item) not in {dict, list}:
            raise ValueError("上下文只能包含 JSON 数据，不能包含文件字节、路径对象或运行时对象")
        if id(item) in active:
            raise ValueError("上下文不能包含循环引用")
        if len(active) >= 100:
            raise ValueError("上下文 JSON 嵌套过深")
        active.add(id(item))
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("上下文字段名称必须是字符串")
            for child in item.values():
                visit(child)
        else:
            for child in item:
                visit(child)
        active.remove(id(item))

    visit(value)


# 这些名称专门表示执行历史；最终业务字段及素材正文不使用它们。
# tools / operations 名称也可表示业务清单，只在顶层运行记录和素材审计投影中清除。
TOOL_HISTORY_FIELDS = frozenset({
    "messages", "chat_history", "tool_messages", "tool_calls", "tool_call_id",
    "tool_results", "tool_result", "tool_output", "tool_outputs", "tool_use",
    "tool_trace", "tool_traces", "tool_events", "intermediate_steps",
    "function_call", "function_calls", "search_results",
})


def clear_tool_history(value: Any) -> Any:
    """递归清空工具历史容器，保留最终正文、结论和媒体引用的内容。"""
    validate_json(value)

    def clean(item: Any) -> Any:
        if type(item) is dict:
            return {key: clean(child) for key, child in item.items() if key not in TOOL_HISTORY_FIELDS}
        if type(item) is list:
            return [clean(child) for child in item]
        return item

    return clean(value)


def merge_extras(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge: omitted keys survive, explicit null remains a value."""
    if type(previous) is not dict or type(current) is not dict:
        raise ValueError("extras 必须是 JSON 对象")
    validate_json(previous)
    validate_json(current)
    # 仅省略字段会被 LangGraph reducer 保留；必须清理合并后的结果，防止旧记录回流。
    return clear_tool_history({**previous, **current})


def latest_resume(previous: str, current: str) -> str:
    return current


class VideoState(TypedDict, total=False):
    """节点共享的 JSON 上下文；total=False 允许初始化或旧 checkpoint 暂缺字段。"""

    # 任务身份与图执行控制，由执行入口及恢复流程维护。
    job_id: str  # 视频任务的唯一 ID，用于关联数据库记录、素材与产物。
    revision: int  # 当前任务版本；节点执行前核对，阻止旧版本继续制作或审核。
    action: str  # 本次制作目标，如 produce、voice、storyboard、preview、final、review。
    run_id: str  # 本次执行的命令 ID；崩溃重放保持不变，恢复命令另有 ID。
    thread_id: str  # LangGraph checkpoint 的线程 ID，用于定位同一次执行和暂停现场。
    route: str  # 节点返回的路由标记，条件边据此选择下一节点或结束。
    gate_issues: list[str]  # 当前检查节点或阶段发现的阻塞问题，供暂停提示和人工处理。
    resume_command_id: Annotated[str, latest_resume]  # 最近一次人工恢复的命令 ID；合并时保留最新值。

    # 任务业务数据；数据库维护状态和提交记录，节点可交接 brief/script/timeline/assets。
    status: str  # 任务整体状态，如 RUNNING、NEEDS_INPUT、NEEDS_HUMAN；以数据库为准。
    stage: str  # 当前制作阶段，如 materials、script、voice、director、render、review。
    message: str  # 当前进展、暂停原因或执行结果的说明，供工作台展示。
    progress: float | None  # 当前进度，取值 0～1；无法确定进度时为 None。
    created_at: str  # 任务创建时间，使用 ISO 8601 字符串。
    updated_at: str  # 任务最近一次持久化更新时间，使用 ISO 8601 字符串。
    brief: dict[str, Any]  # 制作要求：主题、原始文案、受众、平台、尺寸、用途和来源链接。
    script: dict[str, Any] | None  # 当前完整口播稿及段落的画面文字、来源和素材引用；未生成时为 None。
    script_discussion: dict[str, Any] | None  # 编剧与文案审查的每轮稿件、意见、回应及讨论状态。
    timeline: dict[str, Any] | None  # 可执行分镜：镜头、帧区间、字幕、音频路径及 Remotion 参数。
    assets: list[dict[str, Any]]  # 真实素材清单，包含用途、来源、许可、hash 和文件引用。
    artifacts: list[dict[str, Any]]  # 当前任务保留的产物清单，如研究记录、音频、分镜、成片和审核报告。
    review: dict[str, Any] | None  # 成片检查结果、阻塞项、内容指纹及最终人工确认状态。
    pending_input: dict[str, Any] | None  # 数据库中的当前人工待办，包含问题、目标阶段和回复绑定 token。
    latest_event_id: int  # 数据库事件水位；比 checkpoint 更新时优先恢复已提交结果，避免旧数据覆盖。

    # 各阶段的结果与回执，媒体文件本身通过素材或产物引用传递。
    audio_asset_id: str | None  # 当前选用的音频素材 ID，对应 assets 中的一项。
    audio: dict[str, Any] | None  # 当前音频素材的完整描述及受控访问 URL，不包含音频字节。
    alignment: dict[str, Any] | None  # 与音频 hash 绑定的字幕时间戳、段落对应关系及核验信息。
    duration_seconds: float | None  # 当前音频的实测时长，单位秒，供导演计算镜头帧数。
    asset_metadata: dict[str, dict[str, Any]]  # 按素材 ID 索引的附加信息，如来源、音频时长和对齐记录。
    artifact_metadata: dict[str, dict[str, Any]]  # 按产物 ID 索引的附加信息，如渲染时绑定的输入指纹。
    research: dict[str, Any]  # 素材节点最终研究产物：检索歧义、来源正文、图片/截图引用及资料局限；不含工具调用过程。
    audio_report: dict[str, Any] | None  # 配音核验报告，记录音频 hash、实测时长、来源及对齐核验状态。
    voice_guidance: dict[str, Any] | None  # 配音角色模型给出的发音、停顿、情绪建议和预检问题。
    editing_guidance: dict[str, Any] | None  # 剪辑角色模型给出的节奏、布局建议和渲染前预检问题。
    render: dict[str, Any]  # 按产物类型索引的预览、成片、封面、字幕及发布包引用。
    human_reviews: list[dict[str, Any]]  # 累计人工回复及阶段、成片核验回执，保留意见和产物关联。
    metrics: dict[str, int]  # 当前版本的预算计数，如模型调用次数、搜索次数和配音字符数。
    human_decision: dict[str, Any] | None  # 最近一次人工回复，包含 confirm/revise/cancel、说明及待办绑定信息。
    stage_review_pending: dict[str, Any] | None  # 阶段人工审核重试时保留的待办，延续原内容和审核要求。
    human_review_rounds: dict[str, int]  # 按人工审核节点名记录已处理轮次，用于生成不同轮次的待办身份。
    pending_snapshot: dict[str, Any] | None  # checkpoint 中的原始待办快照，防止旧回复被用于新的待办。
    settings: dict[str, Any]  # 模型和制作配置的公开快照；不含密钥，真实调用仍读取当时的配置。
    discussion_policy: dict[str, Any]  # 本次执行冻结的讨论开关、最大轮次及执行/版本身份。
    extras: Annotated[dict[str, Any], merge_extras]  # 自定义最终 JSON；浅合并，遗漏保留、None 留值，工具历史字段清除。


def research_output(research: dict[str, Any]) -> dict[str, Any]:
    """交接素材节点的最终证据；完整搜索及工具回执仍保存在 research.json。"""
    result = {key: research[key] for key in ("schema_version", "status", "query", "collected_at")
              if key in research}
    fields = {
        "sources": ("url", "final_url", "title", "text", "content_type", "retrieved_at", "sha256",
                    "artifact_id", "artifact_url", "platform", "knowledge_status", "asset_ids"),
        "visuals": ("asset_id", "kind", "source_url", "image_url", "title", "description",
                    "knowledge_excerpt", "license_status", "artifact_id", "artifact_url"),
    }
    for name, allowed in fields.items():
        if name in research:
            result[name] = [{key: item[key] for key in allowed if key in item} for item in research[name]]
    # 资料局限属于最终研究结论，而异常类型、调用参数、尝试次数属于工具过程。
    limitations = list(research.get("limitations", []))
    for item in research.get("failures", []):
        subject = item.get("source_url") or item.get("url") or item.get("platform") or "部分来源"
        detail = "图片未取得，不能用于画面" if item.get("stage") == "image" else "正文未取得，不能作为已核验事实"
        limitations.append(f"{subject}：{detail}")
    for item in research.get("capture_notes", []):
        limitations.append(f"{item.get('url', '部分来源')}：未取得截图")
    success_statuses = {"ok", "success", "completed", "ready", "native_ready"}
    covered = {item.get("platform") for item in research.get("tools", []) if item.get("status") in success_statuses}
    for item in research.get("tools", []):
        if item.get("status") not in success_statuses and item.get("platform") not in covered:
            limitations.append(f"{item.get('platform', '部分平台')}：本次未完成检索，不能据此判断没有相关资料")
    if limitations:
        result["limitations"] = list(dict.fromkeys(limitations))
    return result


def clean_handoff(state: VideoState) -> VideoState:
    """对应 TradingAgents 的消息清理：只保留业务结果和必要运行控制。

    本项目 CLI 返回最终 JSON，不把聊天或工具消息写进图；旧记录恢复和节点
    返回也使用同一投影，防止工具过程从数据库或旧 checkpoint 再次混入。
    自定义节点的最终业务结果放 extras，不要把工具轨迹存入 extras。
    """
    result = VideoState(**{key: value for key, value in state.items() if key in VideoState.__annotations__})
    if "research" in result:
        result["research"] = research_output(result["research"])
    asset_fields = {"origin", "source_url", "image_url", "description", "width", "height", "collection_key",
                    "duration_seconds", "alignment", "script_fingerprint", "voice_fingerprint",
                    "voice_model", "voice_style", "voice_speech_rate"}
    artifact_fields = {"source_url", "dependency_fingerprint"}
    for name, allowed in (("asset_metadata", asset_fields), ("artifact_metadata", artifact_fields)):
        if name in result:
            result[name] = {identifier: {key: value for key, value in metadata.items() if key in allowed}
                            for identifier, metadata in result[name].items()}
    if "artifacts" in result:
        hidden = {item["artifact_id"] for item in result["artifacts"]
                  if item.get("kind") in {"material_discovery", "material_tool_audit", "material_skill_manifest"}}
        result["artifacts"] = [item for item in result["artifacts"]
                               if item.get("kind") not in {"material_discovery", "material_tool_audit", "material_skill_manifest"}]
        if "artifact_metadata" in result:
            result["artifact_metadata"] = {key: value for key, value in result["artifact_metadata"].items()
                                           if key not in hidden}
    return VideoState(**clear_tool_history(result))


def job_context(job: Job) -> VideoState:
    """Return the serializable business context carried through LangGraph."""
    return VideoState(
        job_id=job.job_id,
        revision=job.revision,
        status=job.status,
        stage=job.stage,
        message=job.message,
        progress=job.progress,
        created_at=job.created_at,
        updated_at=job.updated_at,
        brief=job.brief.model_dump(),
        script=job.script.model_dump() if job.script else None,
        script_discussion=job.script_discussion.model_dump() if job.script_discussion else None,
        timeline=job.timeline.model_dump() if job.timeline else None,
        assets=[item.model_dump() for item in job.assets],
        artifacts=[item.model_dump() for item in job.artifacts],
        review=job.review.model_dump() if job.review else None,
        pending_input=job.pending_input,
        latest_event_id=job.latest_event_id,
    )


def job_from_state(state: VideoState, persisted: Job) -> Job:
    """Validate writable inputs, while committed SQL receipts win on crash replay."""
    if state["job_id"] != persisted.job_id or state["revision"] != persisted.revision:
        raise Conflict("执行版本已失效")
    watermark = state.get("latest_event_id")
    if watermark is not None:
        if type(watermark) is not int or watermark > persisted.latest_event_id:
            raise Conflict("上下文的持久化版本无效")
        if watermark < persisted.latest_event_id:
            return persisted
    value = persisted.model_dump()
    for name in ("brief", "script", "timeline", "assets"):
        if name in state:
            validate_json(state[name])
            value[name] = state[name]
    job = Job.model_validate(value)
    if job.script and job.script.revision != job.revision:
        raise Conflict("上下文文案对应的任务版本已失效")
    if job.timeline and (job.timeline.revision != job.revision or job.timeline.job_id != job.job_id):
        raise Conflict("上下文分镜对应的任务或版本已失效")
    return job
