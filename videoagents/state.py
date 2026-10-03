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


def merge_extras(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge: omitted keys survive, explicit null remains a value."""
    if type(previous) is not dict or type(current) is not dict:
        raise ValueError("extras 必须是 JSON 对象")
    validate_json(previous)
    validate_json(current)
    return {**previous, **current}


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
    research: dict[str, Any]  # 素材节点冻结的研究包：检索规划、平台调用、原文回执、图片/截图引用与失败记录。
    audio_report: dict[str, Any] | None  # 配音核验报告，记录音频 hash、实测时长、来源及对齐核验状态。
    voice_guidance: dict[str, Any] | None  # 配音角色模型给出的发音、停顿、情绪建议和预检问题。
    editing_guidance: dict[str, Any] | None  # 剪辑角色模型给出的节奏、布局建议和渲染前预检问题。
    render: dict[str, Any]  # 按产物类型索引的预览、成片、封面、字幕及发布包引用。
    human_reviews: list[dict[str, Any]]  # 累计人工回复及阶段、成片核验回执，保留意见和产物关联。
    operations: list[dict[str, Any]]  # 当前版本的外部调用台账摘要，含提交状态、请求 ID、模型和失败原因。
    metrics: dict[str, int]  # 当前版本的预算计数，如模型调用次数、搜索次数和配音字符数。
    human_decision: dict[str, Any] | None  # 最近一次人工回复，包含 confirm/revise/cancel、说明及待办绑定信息。
    stage_review_pending: dict[str, Any] | None  # 阶段人工审核重试时保留的待办，延续原内容和审核要求。
    human_review_rounds: dict[str, int]  # 按人工审核节点名记录已处理轮次，用于生成不同轮次的待办身份。
    pending_snapshot: dict[str, Any] | None  # checkpoint 中的原始待办快照，防止旧回复被用于新的待办。
    settings: dict[str, Any]  # 模型和制作配置的公开快照；不含密钥，真实调用仍读取当时的配置。
    discussion_policy: dict[str, Any]  # 本次执行冻结的讨论开关、最大轮次及执行/版本身份。
    extras: Annotated[dict[str, Any], merge_extras]  # 自定义节点的 JSON 数据；浅合并，遗漏保留，None 留作空值。


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
