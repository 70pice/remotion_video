"""Model-assisted shot choices, grounded in actual audio boundaries and real assets."""

import json
import math
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from videoagents.contracts import Alignment, Asset, Caption, DirectorShotReviewSpec, Job, Shot, Timeline
from videoagents.default_config import PROJECT_ROOT
from videoagents.nodes.common import (
    DIRECTOR_VOICE_REVISION_ISSUE,
    agent_state,
    mark_feedback_applied,
    needs_script_revision,
    needs_voice_revision,
    request_input,
    stage_feedback,
    start_stage,
    state_context,
)
from videoagents.nodes.gates import timeline_readability_issues
from videoagents.prompts import render as render_prompt
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from videoagents.storage.repository import fingerprint
from videoagents.tools.component_sets import (
    allowed_component_set_templates,
    resolve_component_set_shots,
)
from videoagents.tools.components import (
    available_component_ids,
    component_requirement_usage,
    native_component_capabilities,
    prompt_component_catalog,
    prompt_native_component_requirements,
    prompt_scene_playbook,
    validate_component_requirements,
)
from videoagents.tools.media import sha256
from videoagents.tools.timeline import (
    asset_renderable,
    media_coverage_report,
    validate_media_coverage,
    validate_timeline,
)

COMPONENT_PROPS_EXAMPLES = {
    "title": {"eyebrow": "给定主题"}, "keyword": {"keyword": "给定关键词"},
    "evidence": {"highlight": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
    # 裁剪仅演示参数形状；摄影必须使用对应素材经像素核验的区域。
    "image_focus": {"focal_x": 0.5, "focal_y": 0.5,
                    "crop": {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}},
    "video": {"start_seconds": 0, "end_seconds": 4.2, "fit": "contain",
              "crop": {"x": 0.2, "y": 0.0, "width": 0.6, "height": 1.0}},
    "comparison": {"left_title": "给定左标题", "left_body": "给定左正文",
                   "right_title": "给定右标题", "right_body": "给定右正文", "right_reveal_frame": 15},
    # 局部帧只是参数形状示例；真实揭示时机由摄影根据当前镜头和实测字幕选择。
    "data": {"items": [
        {"label": "来源中的第一标签", "value": "来源中的第一值", "detail": "来源中的第一说明", "reveal_frame": 0},
        {"label": "来源中的第二标签", "value": "来源中的第二值", "detail": "来源中的第二说明", "reveal_frame": 15},
    ]},
    "steps": {"layout": "flow", "items": [
        {"title": "给定第一步骤", "body": "给定第一说明", "reveal_frame": 0},
        {"title": "给定第二步骤", "body": "给定第二说明", "reveal_frame": 15},
    ]},
    "conclusion": {"call_to_action": "文案中的行动建议"},
}


MAX_DEMO_SECONDS = 30
COMPONENT_SET_REGISTRY_PATH = PROJECT_ROOT / "docs" / "component-set-registry.json"


class DirectorSegmentPerformance(BaseModel):
    """A reviewable performance note for one script segment."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    segment_id: str = Field(min_length=1, max_length=100)
    shot_ids: list[str] = Field(min_length=1, max_length=80)
    component_reason: str = Field(min_length=1, max_length=600)
    visual_action: str = Field(min_length=1, max_length=800)

    @field_validator("segment_id", "component_reason", "visual_action")
    @classmethod
    def not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("摄影表演方案文字不能为空")
        return stripped

    @field_validator("shot_ids")
    @classmethod
    def shot_ids_not_blank(cls, value: list[str]) -> list[str]:
        stripped = [item.strip() for item in value]
        if any(not item for item in stripped):
            raise ValueError("摄影表演方案镜头 ID 不能为空")
        return stripped


class DirectorDemo(BaseModel):
    """End-exclusive continuous range for the director demo render."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=600)

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("摄影 Demo 原因不能为空")
        return stripped


class DirectorPerformancePlan(BaseModel):
    """Review payload persisted after director planning."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    segment_performances: list[DirectorSegmentPerformance] = Field(min_length=1, max_length=500)
    demo: DirectorDemo | None = None
    shot_reviews: list[DirectorShotReviewSpec] | None = Field(default=None, max_length=400)


class DirectorPlan(BaseModel):
    """摄影交付镜头及可审核表演方案；实测音频、字幕和画幅由程序合入最终 Timeline。"""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)
    shots: list[Shot] = Field(min_length=1, max_length=400)
    segment_performances: list[DirectorSegmentPerformance] | None = Field(default=None, max_length=500)
    demo: DirectorDemo | None = None
    shot_reviews: list[DirectorShotReviewSpec] | None = Field(default=None, max_length=400)

    @model_validator(mode="after")
    def minimum_shot_length(self) -> "DirectorPlan":
        if any(shot.end_frame - shot.start_frame < 15 for shot in self.shots):
            raise ValueError("镜头至少需要 15 帧")
        return self


def production_portrait(job: Job) -> bool:
    return (job.brief.width, job.brief.height, job.brief.fps) == (1080, 1920, 30)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "素材来源")[:160]


def _video_covers(asset: Asset, metadata: dict[str, dict[str, Any]], shot_seconds: float) -> bool:
    duration = metadata.get(asset.asset_id, {}).get("duration_seconds")
    return isinstance(duration, (int, float)) and not isinstance(duration, bool) and math.isfinite(duration) and duration >= shot_seconds


def timeline_fingerprint(timeline: Timeline) -> str:
    return fingerprint(timeline.model_dump(mode="json"))


def _artifact_json(repository: Repository, job: Job, kind: str) -> dict[str, Any] | None:
    for artifact in reversed(job.artifacts):
        if artifact.kind != kind or artifact.revision != job.revision:
            continue
        path, _, owner = repository.artifact_path(artifact.artifact_id)
        if owner != job.job_id or sha256(path) != artifact.sha256:
            continue
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_current_director_plan(repository: Repository, job: Job, *, validate_components: bool = True) -> dict[str, Any] | None:
    """Return the current revision director plan only when it matches job.timeline."""

    if not job.timeline:
        return None
    payload = _artifact_json(repository, job, "director_plan")
    if not payload:
        return None
    try:
        _validate_director_plan_payload(payload, job, job.timeline, validate_components=validate_components)
    except ValueError:
        return None
    return payload


def _overlap_ids(timeline: Timeline, start_frame: int, end_frame: int) -> list[str]:
    return [
        shot.shot_id for shot in timeline.shots
        if shot.start_frame < end_frame and shot.end_frame > start_frame
    ]


def _segment_window(alignment: Alignment, segment_id: str, timeline: Timeline) -> tuple[int, int]:
    aligned = [item for item in alignment.segments if item.segment_id == segment_id]
    if not aligned:
        raise ValueError(f"摄影表演方案缺少文案段落 {segment_id} 的实测字幕时间")
    start = math.floor(min(item.start_ms for item in aligned) * timeline.fps / 1000)
    end = math.ceil(max(item.end_ms for item in aligned) * timeline.fps / 1000)
    start = max(0, min(start, timeline.duration_in_frames - 1))
    end = max(start + 1, min(end, timeline.duration_in_frames))
    return start, end



def _required_library_components(job: Job) -> int:
    requirements = getattr(job, "director_requirements", None)
    return requirements.min_library_components if requirements else 0


def _compact_registry_text(value: object) -> str:
    if isinstance(value, list):
        text = "；".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, dict):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value or "").strip()
    text = " ".join(text.split())
    return text


def _registry_content_fields(content_input: dict[str, Any]) -> list[str]:
    """Describe sample input fields without copying sample facts into production."""

    fields = [f"content.{name}" for name in content_input.get("common", [])]
    specific = content_input.get("specific") or content_input.get("example") or {}
    if isinstance(specific, dict):
        for name, value in specific.items():
            if isinstance(value, dict):
                fields.extend(f"content.{name}.{key}" for key in value)
            else:
                fields.append(f"content.{name}")
    return list(dict.fromkeys(fields))


def prompt_component_set_registry(path=COMPONENT_SET_REGISTRY_PATH) -> str:
    """Return the review-aware component-set registry summary for prompt injection."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (
            "组件套登记摘要不可读取；只能使用本 prompt 的完整组件清单和当前任务真实素材。"
            "不得声称已读取 docs/component-set-registry.json。"
        )
    sets = payload.get("sets") if isinstance(payload, dict) else None
    if not isinstance(sets, list):
        return "组件套登记摘要格式无效；不能把任何组件套称为已验收。"
    lines = [
        "组件套登记摘要来自 docs/component-set-registry.json；普通生产通过 Shot.set_design 选择整套。",
        "registration_status=registered 表示完成备案，不等于 review_status=approved；每期仍需摄影 Demo 人工审核。",
        "review_status=approved 才是已验收范例；pending/registered_pending_review/in_development/not_rendered 只能待品鉴参考。",
        "A01-A12、B01-B18 可通过 set_design.set_id 选择；content 使用本期内容，parts 调整内部组件的局部显示时间和安全区域位置尺寸。",
        "生产分镜只能使用当前任务素材和定稿旁白；旧 props.component_set/composition/rich_content 样片标记仍不可用于生产，不能照搬模拟素材、示例坐标或演示数字。",
    ]
    for item in sets:
        if not isinstance(item, dict):
            continue
        set_id = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        category = str(item.get("category") or "").strip()
        review_status = str(item.get("review_status") or "").strip()
        registration_status = str(item.get("registration_status") or "").strip()
        status_note = "已验收范例" if review_status == "approved" else "待品鉴参考，不能称已验收"
        components = item.get("components") if isinstance(item.get("components"), dict) else {}
        native_ids = components.get("native_ids") if isinstance(components, dict) else []
        semantic_ids = components.get("semantic_ids") if isinstance(components, dict) else []
        adapter_capabilities = components.get("adapter_capabilities") if isinstance(components, dict) else []
        asset_requirements = item.get("asset_requirements") if isinstance(item.get("asset_requirements"), dict) else {}
        request = item.get("component_demo_request") if isinstance(item.get("component_demo_request"), dict) else {}
        content_input = item.get("content_input") if isinstance(item.get("content_input"), dict) else {}
        guidance = item.get("director_guidance") if isinstance(item.get("director_guidance"), dict) else {}
        accepted_media = asset_requirements.get("accepted_media") if isinstance(asset_requirements, dict) else []
        asset_text = (
            f"asset_id_required={asset_requirements.get('asset_id_required')}; "
            f"accepted_media={accepted_media or []}; "
            f"requirements={_compact_registry_text(asset_requirements.get('requirements'))}"
        )
        input_bits = []
        required = request.get("required") if isinstance(request, dict) else []
        forbidden = request.get("forbidden") if isinstance(request, dict) else []
        changeable = request.get("changeable") if isinstance(request, dict) else []
        if required:
            input_bits.append("required=" + ",".join(str(value) for value in required))
        if forbidden:
            input_bits.append("forbidden=" + ",".join(str(value) for value in forbidden))
        if changeable:
            input_bits.append("changeable=" + ",".join(str(value) for value in changeable))
        if content_input:
            limits = content_input.get("limits") if isinstance(content_input.get("limits"), dict) else {}
            input_bits.append(f"content_fields={_registry_content_fields(content_input)}")
            input_bits.append(f"content_limits={limits}")
        sample_rules = [
            _compact_registry_text(value)
            for value in (
                request.get("fixed_boundaries"),
                content_input.get("rules"),
                content_input.get("numeric_semantics"),
            )
            if value
        ]
        lines.append(
            f"- {set_id} {name} | category={category} | review_status={review_status or 'unknown'} "
            f"({status_note}) | registration_status={registration_status or 'unknown'} | "
            f"用途={_compact_registry_text(item.get('usable_scope'))} | "
            f"真实组件ID={list(native_ids or []) + list(semantic_ids or [])}; adapter能力={list(adapter_capabilities or [])} | "
            f"什么时候用={_compact_registry_text(item.get('when_to_use'))} | "
            f"不适合={_compact_registry_text(item.get('not_for'))} | "
            f"表达顺序={_compact_registry_text(guidance.get('visual_sequence'))} | "
            f"普通生产怎么用={_compact_registry_text(guidance.get('production_adaptation'))} | "
            f"内容约束={_compact_registry_text(guidance.get('content_constraints'))} | "
            f"素材要求={asset_text} | 样片入参边界={' ; '.join(input_bits) or '无'} | "
            f"样片专用约束={'；'.join(sample_rules) or '无'}"
        )
    return "\n".join(lines)

def _review_plan_body(plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if not plan:
        return None
    return {key: plan.get(key) for key in ("shots", "segment_performances", "review_mode", "shot_reviews", "demo")}


def _validate_director_plan_payload(payload: dict[str, Any], job: Job, timeline: Timeline,
                                    alignment: Alignment | None = None, *, validate_components: bool = True) -> None:
    if payload.get("job_id") != job.job_id or payload.get("revision") != job.revision:
        raise ValueError("摄影方案任务版本不匹配")
    if payload.get("timeline_fingerprint") != timeline_fingerprint(timeline):
        raise ValueError("摄影方案不匹配当前时间轴")
    if payload.get("shots") != [shot.model_dump(mode="json") for shot in timeline.shots]:
        raise ValueError("摄影方案镜头快照不匹配当前时间轴")
    segment_performances = [
        DirectorSegmentPerformance.model_validate(item)
        for item in payload.get("segment_performances", [])
    ]
    script_segments = job.script.segments if job.script else []
    if script_segments:
        expected_ids = [segment.segment_id for segment in script_segments]
        actual_ids = [segment.segment_id for segment in segment_performances]
        if actual_ids != expected_ids:
            raise ValueError("摄影表演方案必须与文案段落一一对应")
    elif not segment_performances:
        raise ValueError("摄影表演方案不能为空")
    shot_ids = {shot.shot_id for shot in timeline.shots}
    for item in segment_performances:
        unknown = [shot_id for shot_id in item.shot_ids if shot_id not in shot_ids]
        if unknown:
            raise ValueError(f"摄影表演方案引用不存在的镜头：{', '.join(unknown)}")
        if alignment is not None and job.script and item.segment_id in {segment.segment_id for segment in script_segments}:
            start, end = _segment_window(alignment, item.segment_id, timeline)
            overlapping = set(_overlap_ids(timeline, start, end))
            if not overlapping.intersection(item.shot_ids):
                raise ValueError(f"摄影表演方案 {item.segment_id} 的 shot_ids 未覆盖实测段落窗口")
    if validate_components:
        required_components = _required_library_components(job)
        expected_usage = component_requirement_usage(timeline, job.brief.usage, required_components)
        usage = payload.get("component_usage")
        if usage is None:
            if required_components:
                raise ValueError("摄影方案缺少库组件使用统计证明")
        elif usage != expected_usage:
            raise ValueError("摄影方案库组件使用统计不匹配当前时间轴")
        if required_components:
            validate_component_requirements(timeline, job.brief.usage, required_components)
    review_mode = payload.get("review_mode")
    if review_mode is not None:
        if review_mode != "per_shot_stills" or timeline.presentation == "component_sample":
            raise ValueError("摄影审核模式与当前时间轴不一致")
        reviews = [DirectorShotReviewSpec.model_validate(item) for item in payload.get("shot_reviews", [])]
        if [item.shot_id for item in reviews] != [shot.shot_id for shot in timeline.shots]:
            raise ValueError("摄影逐镜审核设计必须按顺序覆盖每个镜头且不能重复")
        for review, shot in zip(reviews, timeline.shots, strict=True):
            if not shot.start_frame <= review.review_frame < shot.end_frame:
                raise ValueError(f"摄影逐镜审核代表帧必须落在镜头 {shot.shot_id} 内")
        return
    demo = DirectorDemo.model_validate(payload.get("demo"))
    max_demo_frames = min(timeline.duration_in_frames, timeline.fps * MAX_DEMO_SECONDS)
    if demo.end_frame <= demo.start_frame:
        raise ValueError("摄影 Demo 必须是连续时间区间")
    if demo.end_frame > timeline.duration_in_frames:
        raise ValueError("摄影 Demo 超出当前时间轴")
    if demo.end_frame - demo.start_frame > max_demo_frames:
        raise ValueError("摄影 Demo 必须是连续时间区间且不超过 30 秒")


def _performance_payload(origin: str, job: Job, timeline: Timeline, alignment: Alignment,
                         segment_performances: list[DirectorSegmentPerformance] | None = None,
                         demo: DirectorDemo | None = None, *,
                         review_mode: str | None = None,
                         shot_reviews: list[DirectorShotReviewSpec] | None = None) -> dict[str, Any]:
    if segment_performances is None:
        generated: list[DirectorSegmentPerformance] = []
        script_segments = job.script.segments if job.script else []
        for index, segment in enumerate(script_segments):
            start, end = _segment_window(alignment, segment.segment_id, timeline)
            overlapping = _overlap_ids(timeline, start, end) or [timeline.shots[min(index, len(timeline.shots) - 1)].shot_id]
            shots = [shot for shot in timeline.shots if shot.shot_id in overlapping]
            components = ", ".join(dict.fromkeys(shot.component_id for shot in shots))
            titles = "；".join(shot.title for shot in shots if shot.title)[:500]
            generated.append(DirectorSegmentPerformance(
                segment_id=segment.segment_id,
                shot_ids=overlapping,
                component_reason=f"{origin}: 使用 {components or '当前镜头'} 承接本段旁白，不改变实测音频和字幕。",
                visual_action=titles or f"{origin}: 按本段旁白时间 {start}-{end} 帧展示对应画面。",
            ))
        segment_performances = generated or [DirectorSegmentPerformance(
            segment_id="timeline",
            shot_ids=[shot.shot_id for shot in timeline.shots],
            component_reason=f"{origin}: 无分段文案，只能按当前时间轴镜头生成审核方案。",
            visual_action="按当前时间轴连续审核画面与旁白对应关系。",
        )]
    if review_mode is None and demo is None:
        end_frame = min(timeline.duration_in_frames, timeline.fps * MAX_DEMO_SECONDS)
        demo = DirectorDemo(start_frame=0, end_frame=max(1, end_frame),
                            reason="默认使用原时间轴前 30 秒作为摄影 Demo，不裁剪原 timeline。")
    payload = {
        "job_id": job.job_id,
        "revision": job.revision,
        "origin": origin,
        "timeline_fingerprint": timeline_fingerprint(timeline),
        "shots": [shot.model_dump(mode="json") for shot in timeline.shots],
        "segment_performances": [item.model_dump(mode="json") for item in segment_performances],
        "component_usage": component_requirement_usage(
            timeline, job.brief.usage, _required_library_components(job)
        ),
    }
    if review_mode is not None:
        if shot_reviews is None:
            shot_reviews = [DirectorShotReviewSpec(
                shot_id=shot.shot_id,
                review_frame=min(shot.end_frame - 1, shot.start_frame + max(timeline.fps, (shot.end_frame - shot.start_frame) // 2)),
                component_reason=f"{origin}: 使用 {shot.component_id} 承接本镜旁白。",
                visual_action=shot.title or f"{origin}: 查看当前镜头稳定画面。",
            ) for shot in timeline.shots]
        payload.update(review_mode=review_mode, shot_reviews=[item.model_dump(mode="json") for item in shot_reviews])
    elif demo is not None:
        payload["demo"] = demo.model_dump(mode="json")
    _validate_director_plan_payload(payload, job, timeline, alignment)
    return payload


def director_prompt(usage: str) -> str:
    """Build the complete component guide for this job's license context."""

    prompt = render_prompt(
        "director",
        component_props=json.dumps(COMPONENT_PROPS_EXAMPLES, ensure_ascii=False, separators=(",", ":")),
        component_scene_playbook=prompt_scene_playbook(usage),
        component_set_registry=prompt_component_set_registry(),
        component_catalog=prompt_component_catalog(usage),
    )
    # One immutable mapping drives the director, validator, renderer and counts.
    # It contains geometry/timing shapes, never sample content or asset paths.
    templates = allowed_component_set_templates(usage)
    return prompt + "\n\n生产组件套固定部件与默认布局（可调整 parts，不可替换内部组件 ID）：\n" + json.dumps(
        list(templates.values()), ensure_ascii=False, separators=(",", ":")
    )


# Compatibility for tests and callers that read the default prompt. Resolved
# lazily so importing this module (directly or via the graph) does not parse
# the three catalog JSON files on every process start. Jobs with an explicit
# commercial usage receive a license-filtered prompt at call time instead.
_DEFAULT_PROMPT: str | None = None


def __getattr__(name: str):
    if name == "PROMPT":
        global _DEFAULT_PROMPT
        if _DEFAULT_PROMPT is None:
            _DEFAULT_PROMPT = director_prompt("unspecified")
        return _DEFAULT_PROMPT
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class DirectorNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)
        self._last_director_plan: dict[str, Any] | None = None

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "director", "摄影根据实测旁白安排镜头与关键画面")
        try:
            feedback_stage = "render" if stage_feedback(state, "render") else "director"
            feedback = stage_feedback(state, feedback_stage)
            if feedback and feedback.get("note") and self._needs_script_revision(feedback["note"]):
                return state_context(self.repo, state, route="screenwriter", gate_issues=[])
            if feedback and feedback.get("note") and self._needs_voice_revision(feedback["note"]):
                return request_input(self.repo, state, "voice",
                    [DIRECTOR_VOICE_REVISION_ISSUE],
                    ["voice", "timeline"])
            audio = next((item for item in job.assets if item.asset_id == state.get("audio_asset_id")), None)
            if audio is None:
                raise ValueError(f"音频素材 {state.get('audio_asset_id')} 不在当前任务素材中，摄影无法安排镜头")
            if (not state.get("extras", {}).get("timeline_rebuild") and feedback and job.timeline
                    and type(feedback.get("timeline")) is dict and job.timeline.model_dump() != feedback["timeline"]):
                # SQL may commit before either artifact write; restore both outputs before continuing.
                director_plan = load_current_director_plan(self.repo, job)
                if not director_plan:
                    raise ValueError("当前分镜缺少匹配的摄影方案，不能用旧 timeline 冒充已审核设计")
                self.service.write_json(job, "director-plan.json", director_plan, "director_plan")
                self.service.write_json(job, "storyboard.json", job.timeline.model_dump(), "storyboard")
                self.service.write_json(job, "timeline.json", job.timeline.model_dump(), "timeline")
                mark_feedback_applied(self.repo, self.service, job, state, feedback_stage, "director")
                return state_context(self.repo, state, route=self.next_route(state), gate_issues=[])
            timeline = self.plan(job, audio, Alignment.model_validate(state["alignment"]), state["duration_seconds"],
                                 state.get("research", {}), state=state)
            if self._last_director_plan and self._last_director_plan.get("origin") == "model_missing_review_plan":
                raise ValueError("摄影模型必须输出 segment_performances 和 shot_reviews，不能只返回镜头后直接进入剪辑")
            director_plan = self._last_director_plan or _performance_payload(
                "fallback", job, timeline, Alignment.model_validate(state["alignment"]), review_mode="per_shot_stills")
            if feedback and type(feedback.get("timeline")) is dict:
                revised_timeline = timeline.model_dump(mode="json")
                previous_timeline = feedback["timeline"]
                same_timeline = (timeline.model_dump() == previous_timeline
                                 or revised_timeline == previous_timeline
                                 or revised_timeline.get("shots") == previous_timeline.get("shots"))
                previous_plan = _review_plan_body(feedback.get("director_plan"))
                same_plan = previous_plan is None or _review_plan_body(director_plan) == previous_plan
                if same_timeline and same_plan:
                    raise ValueError("人工返工未产生分镜修改，请补充更明确的修改意见")
            stale = {"preview", "final", "cover", "captions", "review", "package", "storyboard",
                     "timeline", "editing_guidance", "human_review", "component_study",
                     "director_shot_review", "shot_review_frame"}
            stale.add("director_plan")
            # Drop stale downstream artifacts from the snapshot read before planning.
            self.service.write_json(job, "director-plan.json", director_plan, "director_plan")
            current = self.repo.get_job(job.job_id)
            artifacts = [item for item in current.artifacts if item.kind not in stale or item.kind == "director_plan"]
            job = self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                                       timeline=timeline, review=None, progress=None, artifacts=artifacts)
            self.service.write_json(job, "storyboard.json", timeline.model_dump(), "storyboard")
            self.service.write_json(job, "timeline.json", timeline.model_dump(), "timeline")
            if feedback:
                mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                      feedback_stage, "director")
            if state.get("extras", {}).get("timeline_rebuild"):
                state["extras"] = {**state["extras"], "timeline_rebuild": None}
            return state_context(self.repo, state, route=self.next_route(state), gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["timeline"], exc)

    @staticmethod
    def _needs_script_revision(note: str) -> bool:
        return needs_script_revision(note)

    @staticmethod
    def _needs_voice_revision(note: str) -> bool:
        return needs_voice_revision(note)

    def next_route(self, state: VideoState) -> str:
        action = state.get("action")
        if action == "storyboard":
            job = self.repo.get_job(state["job_id"])
            plan = load_current_director_plan(self.repo, job)
            if plan and plan.get("review_mode") == "per_shot_stills":
                return "director_demo"
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message="分镜已生成，本次执行结束", progress=1, pending_input=None)
            return "end"
        if action == "review":
            job = self.repo.get_job(state["job_id"])
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message="已移除成片审核节点；请使用 produce/final 重新生成视频", progress=1,
                                 pending_input=None)
            return "end"
        return "director_demo"

    def plan(self, job: Job, audio: Asset, alignment: Alignment, duration: float,
             research: dict | None = None, state: VideoState | None = None) -> Timeline:
        self._last_director_plan = None
        asset_metadata = {asset.asset_id: self.repo.asset_metadata(asset.asset_id) for asset in job.assets}
        model_available = self.model.available("director")
        context = agent_state(self.repo, job, state)
        if state is None and research is not None:
            context = {**context, "research": research}
        feedback = stage_feedback(context, "director", "render")
        rebuilding = bool(context.get("extras", {}).get("timeline_rebuild"))
        pending = context.get("pending_snapshot") or {}
        external_repair_issues = list(context.get("gate_issues", [])) if pending.get("stage") == "director" else []
        repair_issues = list(external_repair_issues)
        required_components = _required_library_components(job)
        previous_plan = load_current_director_plan(self.repo, job) if job.timeline else None
        review_upgrade = bool(previous_plan and previous_plan.get("review_mode") != "per_shot_stills"
                              and job.timeline.presentation != "component_sample")
        if review_upgrade and not model_available:
            raise CapabilityMissing("旧摄影方案需要启用摄影模型，为每个镜头重新设计组件理由和审核代表帧",
                                    ["role_models", "director_plan"])
        if not rebuilding and feedback and job.timeline and type(feedback.get("timeline")) is dict and job.timeline.model_dump() != feedback["timeline"]:
            self._last_director_plan = load_current_director_plan(self.repo, job) or _performance_payload(
                "existing_timeline", job, job.timeline, alignment, review_mode="per_shot_stills")
            return job.timeline
        if rebuilding and not model_available:
            raise CapabilityMissing("重做画面需要启用摄影模型重新选择素材和编排镜头，不能直接复用旧分镜", ["role_models", "timeline"])
        if feedback and not model_available:
            raise CapabilityMissing("人工返工需要摄影模型读取审核意见并重新规划镜头；请启用摄影模型或提供新的人工分镜", ["role_models", "timeline"])
        if job.timeline and not feedback and not rebuilding:
            validate_timeline(job.timeline, job, asset_metadata)
            expected = [(item.text, item.start_ms, item.end_ms) for item in alignment.segments]
            actual = [(item.text, item.start_ms, item.end_ms) for item in job.timeline.captions]
            if expected != actual or job.timeline.audio_src != audio.timeline_src:
                raise ValueError("人工分镜必须保留当前实测音频及字幕时间轴")
            readability_issues = timeline_readability_issues(job.timeline) if production_portrait(job) else []
            repair_issues = list(dict.fromkeys([*external_repair_issues, *readability_issues]))
            if not repair_issues:
                validate_component_requirements(job.timeline, job.brief.usage, required_components)
                if not review_upgrade:
                    self._last_director_plan = previous_plan or _performance_payload(
                        "existing_timeline", job, job.timeline, alignment, review_mode="per_shot_stills")
                    return job.timeline
            if not model_available:
                raise ValueError("；".join(repair_issues))
        starts = {}
        for segment in alignment.segments:
            starts.setdefault(segment.segment_id, math.floor(segment.start_ms * job.brief.fps / 1000))
        total = math.ceil(duration * job.brief.fps)
        if total < 15:
            raise ValueError("视频时长过短，镜头至少需要 15 帧")
        # 段落仅提供候选切点。短段落合入相邻基线镜头，实际字幕全部保留；
        # 摄影可以基于这份提示自由拆镜、合镜或跨段落安排新的切点。
        cut_indices, cut_frames = [0], [0]
        for index, segment in enumerate(job.script.segments[1:], 1):
            boundary = starts[segment.segment_id]
            if boundary - cut_frames[-1] >= 15 and total - boundary >= 15:
                cut_indices.append(index)
                cut_frames.append(boundary)
        assets = {asset.asset_id: asset for asset in job.assets}
        shots = []
        for index, segment_index in enumerate(cut_indices):
            segment = job.script.segments[segment_index]
            start = cut_frames[index]
            end = cut_frames[index + 1] if index + 1 < len(cut_frames) else total
            next_segment_index = cut_indices[index + 1] if index + 1 < len(cut_indices) else len(job.script.segments)
            shot_seconds = (end - start) / job.brief.fps
            video = next((asset for asset in job.assets
                          if asset.mime_type.startswith("video/")
                          and (asset.asset_id in segment.asset_ids
                               or bool(asset.source_url and asset.source_url in segment.source_refs))
                          and asset_renderable(asset)
                          and _video_covers(asset, asset_metadata, shot_seconds)), None)
            image = next((assets[asset_id] for asset_id in segment.asset_ids
                          if asset_id in assets and assets[asset_id].mime_type.startswith("image/")
                          and asset_renderable(assets[asset_id])), None)
            if not image:
                # 编剧没有指定图片时，根据该段的出处匹配素材节点采集的真实画面。
                image = next((asset for asset in job.assets if asset.mime_type.startswith("image/")
                              and asset_renderable(asset) and asset.source_url in segment.source_refs), None)
            component = "video" if video else "evidence" if image and image.role == "evidence" and image.source_url else "image_focus" if image else "title" if index == 0 else "conclusion" if index == len(cut_indices) - 1 else "keyword"
            media = video or image
            shots.append(Shot(shot_id=f"shot-{index + 1}", start_frame=start, end_frame=end,
                              component_id=component, title=(segment.screen_text or job.script.title)[:100],
                              body="".join(item.narration for item in job.script.segments[segment_index:next_segment_index])[:240],
                              asset_src=media.timeline_src if media else None,
                              source_label=_host(media.source_url) if media and media.source_url else "",
                              props={"start_seconds": 0, "fit": "contain"} if video else {}))
        timeline = Timeline(job_id=job.job_id, revision=job.revision, width=job.brief.width, height=job.brief.height,
                            fps=job.brief.fps, duration_in_frames=total, audio_src=audio.timeline_src, shots=shots,
                            captions=[Caption(text=item.text, start_ms=item.start_ms, end_ms=item.end_ms) for item in alignment.segments])
        model_segment_performances: list[DirectorSegmentPerformance] | None = None
        model_demo: DirectorDemo | None = None
        model_shot_reviews: list[DirectorShotReviewSpec] | None = None
        if model_available:
            schema = DirectorPlan.model_json_schema()
            # Old saved payloads remain readable; a fresh director must
            # specify the representative frame and reason for every shot.
            schema["required"] = ["shots", "segment_performances", "shot_reviews"]
            schema["$defs"]["Shot"]["properties"]["component_id"]["enum"] = available_component_ids(
                job.brief.usage
            )
            if required_components:
                capabilities = native_component_capabilities()
                allowed = set(available_component_ids(job.brief.usage))
                schema["$defs"]["Shot"]["properties"]["component_id"]["enum"] = sorted(
                    allowed & (set(capabilities["main_component_ids"]) | set(COMPONENT_PROPS_EXAMPLES)
                               | {item["main_component_id"] for item in allowed_component_set_templates(job.brief.usage).values()})
                )
                schema["$defs"]["ShotLayer"]["properties"]["component_id"]["enum"] = sorted(
                    allowed & set(capabilities["layer_roles"])
                )
            # 仅当前任务已导入的图片/视频可作为渲染资产；研究链接不是资产路径。
            schema["$defs"]["Shot"]["properties"]["asset_src"]["enum"] = [
                asset.timeline_src for asset in job.assets
                if asset.mime_type.startswith(("image/", "video/"))
                and asset_renderable(asset)
            ] + [None]
            schema["$defs"]["ComponentSetDesign"]["properties"]["set_id"]["enum"] = list(
                allowed_component_set_templates(job.brief.usage)
            )
            # 实测基线只作为本次摄影输入；模型输出校验通过前不写入共享 state。
            reviewed_timeline = feedback.get("timeline") if feedback and type(feedback.get("timeline")) is dict else None
            if review_upgrade and reviewed_timeline is None:
                reviewed_timeline = job.timeline.model_dump()
            if repair_issues and not rebuilding and job.timeline is not None:
                reviewed_timeline = job.timeline.model_dump()
            planning_timeline = Timeline.model_validate(reviewed_timeline) if reviewed_timeline else timeline
            coverage = media_coverage_report(
                planning_timeline,
                job,
                asset_metadata,
                validate_relationships=False,
            )
            model_state = {**context, "timeline": planning_timeline.model_dump(),
                           # 音频对齐已在 timeline.captions 提供，避免在素材元信息中重复发送。
                           "asset_metadata": {asset.asset_id: {
                               **{key: value for key, value in {
                                   **context.get("asset_metadata", {}).get(asset.asset_id, {}),
                                   **asset_metadata[asset.asset_id],
                               }.items() if key != "alignment"},
                               **({"renderable": asset_renderable(asset)}
                                  if asset.mime_type.startswith(("image/", "video/")) else {}),
                           } for asset in job.assets},
                           "extras": {**context.get("extras", {}),
                                      "media_coverage": coverage, "timeline_repair_issues": repair_issues}}
            if repair_issues:
                candidate = self.repo.latest_completed_operation(job.job_id, "llm:director", job.revision)
                if candidate and isinstance(candidate["result"].get("shots"), list):
                    model_state["extras"]["timeline_repair_candidate"] = {
                        "operation_id": candidate["operation_id"], "result": candidate["result"],
                    }
            instruction = director_prompt(job.brief.usage)
            if coverage["required"]:
                instruction += ("\n\n本次提交的硬约束：图片/视频镜头至少覆盖 "
                                f"{coverage['target_frames']} 帧（全片 {total} 帧），"
                                f"asset_src=null 的纯解释镜头合计最多 {total - coverage['target_frames']} 帧。"
                                "先安排与本段旁白对应的真实素材，再保留必要解释镜头；"
                                "提交前按 end_frame-start_frame 求和核对。")
            if required_components:
                instruction += ("\n\n本次新增硬约束：最终 timeline 至少使用 "
                                f"{required_components} 个不同的原生库组件。基础语义组件和 adapter 不计数；"
                                "同一 component_id 重复只计一次；只有 native-component-capabilities 清单中的"
                                "可生产原生组件可计数；主镜头只有 roles 含 main 才能计数，"
                                "layers 必须使用该组件允许的 title/emphasis role 且在镜头内至少 30 帧。"
                                "不要为 60 个组件硬拆 60 个主镜头；优先 36-50 个有内容主镜头加层补足，"
                                "层时间必须对应原 caption 语义。\n"
                                + prompt_native_component_requirements(job.brief.usage))
                instruction += ("\n选用 set_design 的镜头由已登记整套渲染器承载，内部原生组件按实际展开 parts 统计；"
                                "不需要另加 layers 或为凑数切镜。套内部件只能调时间与位置尺寸，不能自由替换组件。")
            value = self.model.invoke(model_state, "director", instruction,
                fields=("brief", "script", "timeline", "research", "assets", "asset_metadata", "extras"),
                command_id=(context.get("resume_command_id") or context.get("run_id", "")) + ":timeline",
                output_schema=schema)
            plan = DirectorPlan.model_validate(value)
            model_segment_performances = plan.segment_performances
            model_demo = plan.demo
            model_shot_reviews = plan.shot_reviews
            # 镜头切点属于画面编排，不是音频对齐：只替换 shots，真实音频、
            # 字幕、画幅和总帧数保持程序实测值，连续覆盖由 Timeline 校验。
            resolved_shots = resolve_component_set_shots(plan.shots, job.assets, asset_metadata)
            timeline = Timeline.model_validate({**timeline.model_dump(), "shots": [shot.model_dump() for shot in resolved_shots]})
        validate_timeline(timeline, job, asset_metadata)
        issues = timeline_readability_issues(timeline) if production_portrait(job) else []
        if issues:
            raise ValueError("；".join(issues))
        if model_available:
            validate_media_coverage(timeline, job, asset_metadata)
        validate_component_requirements(timeline, job.brief.usage, required_components)
        self._last_director_plan = _performance_payload(
            "model" if model_available and model_segment_performances is not None and model_shot_reviews is not None
            else "model_missing_review_plan" if model_available else "baseline",
            job,
            timeline,
            alignment,
            model_segment_performances,
            model_demo,
            review_mode="per_shot_stills",
            shot_reviews=model_shot_reviews,
        )
        return timeline
