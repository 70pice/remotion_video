"""Canonical transport and production contracts. Extra properties are rejected."""

import math
import re
from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Brief(Contract):
    topic: str = Field(default="", max_length=2000)
    creative_direction: str = Field(default="", max_length=30000)
    # Historical jobs may contain a supplied, ready-to-read script.
    script_text: str = Field(default="", max_length=30000)
    audience: str = Field(default="关心 AI 如何影响自己的钱、工作和生活的普通人，无需技术背景", max_length=500)
    platform: str = Field(default="抖音竖屏", max_length=100)
    usage: Literal["personal", "commercial", "unspecified"] = "personal"
    target_seconds: float = Field(default=60, ge=1, le=1800)
    width: int = Field(default=1080, ge=240, le=3840)
    height: int = Field(default=1920, ge=240, le=3840)
    fps: int = Field(default=30, ge=15, le=60)
    source_urls: list[str] = Field(default_factory=list, max_length=50)

    @field_validator("source_urls")
    @classmethod
    def source_links(cls, links: list[str]) -> list[str]:
        for link in links:
            parsed = urlparse(link)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                raise ValueError("来源必须是无凭据的 HTTP/HTTPS URL")
        return links

    @model_validator(mode="after")
    def dimensions(self) -> "Brief":
        if self.width % 2 or self.height % 2:
            raise ValueError("视频宽高必须为偶数")
        return self


class ScriptSegment(Contract):
    segment_id: str = Field(min_length=1, max_length=100)
    narration: str = Field(min_length=1, max_length=5000)
    screen_text: str = Field(default="", max_length=2000)
    source_refs: list[str] = Field(default_factory=list, max_length=30)
    asset_ids: list[str] = Field(default_factory=list, max_length=30)


class Script(Contract):
    title: str = Field(min_length=1, max_length=300)
    title_hook: str = Field(default="", max_length=15)
    opening_visual: str = Field(default="", max_length=300)
    final_answer: str = Field(default="", max_length=300)
    segments: list[ScriptSegment] = Field(min_length=1, max_length=200)
    origin: Literal["user", "model"] = "user"
    revision: int = Field(ge=1)

    @model_validator(mode="after")
    def identifiers(self) -> "Script":
        ids = [item.segment_id for item in self.segments]
        if len(ids) != len(set(ids)):
            raise ValueError("文案段落 ID 必须唯一")
        return self


class ScriptCritiqueIssue(Contract):
    segment_id: str = Field(default="", max_length=100)
    category: Literal["fact", "logic", "hook", "clarity", "visual", "rights"]
    concern: str = Field(min_length=1, max_length=1500)
    suggestion: str = Field(min_length=1, max_length=1500)


class ScriptCritique(Contract):
    decision: Literal["APPROVE", "REVISE"]
    summary: str = Field(min_length=1, max_length=1500)
    strengths: list[str] = Field(default_factory=list, max_length=20)
    issues: list[ScriptCritiqueIssue] = Field(default_factory=list, max_length=30)

    @field_validator("strengths")
    @classmethod
    def readable_strengths(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("文案优点须为非空文本，每条最多 500 字")
        return values

    @model_validator(mode="after")
    def decision_matches_issues(self) -> "ScriptCritique":
        if (self.decision == "REVISE") != bool(self.issues):
            raise ValueError("要求修改必须指出具体问题；通过时不能保留未解决问题")
        return self


class ScriptRewrite(Contract):
    script: Script
    response: str = Field(min_length=1, max_length=3000)


class ScriptDiscussionRound(Contract):
    round: int = Field(ge=1, le=5)
    script: Script
    response: str = Field(default="", max_length=3000)
    critique: ScriptCritique | None = None


class ScriptDiscussion(Contract):
    run_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(ge=1)
    enabled: bool = False
    max_rounds: int = Field(default=2, ge=1, le=5)
    status: Literal["DISABLED", "DISCUSSING", "APPROVED", "EXHAUSTED", "FINAL_REWRITE"] = "DISABLED"
    rounds: list[ScriptDiscussionRound] = Field(default_factory=list, max_length=5)
    final_script: Script | None = None
    final_response: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def ordered_rounds(self) -> "ScriptDiscussion":
        if len(self.rounds) > self.max_rounds or any(
            item.round != index + 1 or item.script.revision != self.revision
            for index, item in enumerate(self.rounds)
        ):
            raise ValueError("讨论轮数、顺序或文案版本不一致")
        if self.final_script and (self.status != "FINAL_REWRITE" or self.final_script.revision != self.revision
                                  or not self.rounds or not self.rounds[-1].critique
                                  or self.rounds[-1].critique.decision != "REVISE"):
            raise ValueError("最终改稿必须对应本次讨论最后一轮的修改意见")
        if self.status == "FINAL_REWRITE" and not self.final_script:
            raise ValueError("最终改稿缺少文案")
        return self


class Asset(Contract):
    asset_id: str
    name: str
    role: Literal["evidence", "illustration", "decoration", "audio"]
    mime_type: str
    size_bytes: int
    sha256: str
    source_url: str = ""
    license_note: str = ""
    artifact_id: str
    url: str
    timeline_src: str


class Artifact(Contract):
    artifact_id: str
    kind: str
    name: str
    mime_type: str
    size_bytes: int
    sha256: str
    url: str
    revision: int


class Caption(Contract):
    text: str = Field(min_length=1, max_length=72)
    start_ms: float = Field(ge=0)
    end_ms: float = Field(gt=0)

    @field_validator("text")
    @classmethod
    def readable(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError("字幕文字不能为空或含控制字符")
        return value

    @model_validator(mode="after")
    def interval(self) -> "Caption":
        if self.end_ms <= self.start_ms:
            raise ValueError("字幕结束时间必须晚于开始时间")
        return self


class AlignmentSegment(Caption):
    segment_id: str = Field(min_length=1, max_length=100)


class Alignment(Contract):
    origin: Literal["provider", "manual", "aligner"]
    verified: bool
    audio_sha256: str = Field(min_length=64, max_length=64)
    segments: list[AlignmentSegment] = Field(min_length=1, max_length=5000)
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def ordered(self) -> "Alignment":
        previous = 0.0
        for item in self.segments:
            if item.start_ms < previous:
                raise ValueError("对齐段落必须按时间排序且不重叠")
            previous = item.end_ms
        return self


ProductionId = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]


ComponentSetId = Literal[
    "A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A11", "A12",
    "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12",
    "B13", "B14", "B15", "B16", "B17", "B18",
]
SetText = Annotated[str, Field(min_length=1, max_length=96)]


class ComponentSetBox(Contract):
    """Normalized rectangle inside the production content area, never the captions."""

    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def bounds(self) -> "ComponentSetBox":
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("组件位置尺寸必须在安全区域内")
        return self


class ComponentSetMetric(Contract):
    label: SetText
    value: str = Field(min_length=1, max_length=24)
    detail: str = Field(default="", max_length=96)


class ComponentSetContent(Contract):
    """Current job's meaning; layout overrides cannot introduce additional facts."""

    takeaway: SetText
    items: list[SetText] = Field(default_factory=list, max_length=6, exclude_if=lambda value: not value)
    supporting_items: list[SetText] = Field(default_factory=list, max_length=6, exclude_if=lambda value: not value)
    metric: ComponentSetMetric | None = Field(default=None, exclude_if=lambda value: value is None)
    numeric_items: list[SetText] = Field(default_factory=list, max_length=6, exclude_if=lambda value: not value)
    source_refs: list[str] = Field(default_factory=list, max_length=30, exclude_if=lambda value: not value)


class ComponentSetPart(Contract):
    part_id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    box: ComponentSetBox

    @model_validator(mode="after")
    def interval(self) -> "ComponentSetPart":
        if self.end_frame <= self.start_frame:
            raise ValueError("组件显示区间无效")
        return self


class ComponentSetFocusStep(Contract):
    instruction: SetText
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    target: ComponentSetBox

    @model_validator(mode="after")
    def interval(self) -> "ComponentSetFocusStep":
        if self.end_frame <= self.start_frame:
            raise ValueError("素材引导步骤区间无效")
        return self


class ComponentSetSourceSize(Contract):
    width: int = Field(gt=0, le=16384)
    height: int = Field(gt=0, le=16384)


class ComponentSetDesign(Contract):
    set_id: ComponentSetId
    content: ComponentSetContent
    parts: list[ComponentSetPart] = Field(default_factory=list, max_length=12)
    focus_steps: list[ComponentSetFocusStep] = Field(default_factory=list, max_length=6,
                                                   exclude_if=lambda value: not value)
    source_size: ComponentSetSourceSize | None = Field(default=None, exclude_if=lambda value: value is None)


class ShotLayer(Contract):
    """A real library title/emphasis, timed locally over one continuous shot."""

    component_id: ProductionId
    role: Literal["title", "emphasis"]
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=32)
    body: str = Field(default="", max_length=64)
    accent_color: str = Field(default="#38BDF8", pattern=r"^#[0-9a-fA-F]{6}$")
    props: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def interval(self) -> "ShotLayer":
        if not self.title.strip() or self.end_frame - self.start_frame < 30:
            raise ValueError("组件层须有真实文字并至少可见 30 帧")
        return self


class Shot(Contract):
    shot_id: str = Field(min_length=1, max_length=100)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    component_id: ProductionId
    title: str = Field(default="", max_length=100)
    body: str = Field(default="", max_length=240)
    asset_src: str | None = None
    source_label: str = Field(default="", max_length=160)
    media_usage: Literal["source_evidence", "context_example"] = Field(
        default="source_evidence",
        exclude_if=lambda value: value == "source_evidence",
        description=(
            "source_evidence means the media supports the current narrated claim; "
            "context_example means a real same-topic imported asset from another case, "
            "which must be labeled as 另案示例 with the source hostname and must not use the evidence component."
        ),
    )
    accent_color: str = Field(default="#8cffb8", pattern=r"^#[0-9a-fA-F]{6}$")
    props: dict[str, Any] = Field(default_factory=dict)
    layers: list[ShotLayer] = Field(default_factory=list, max_length=2, exclude_if=lambda value: not value)
    set_design: ComponentSetDesign | None = Field(default=None, exclude_if=lambda value: value is None)

    @field_validator("component_id")
    @classmethod
    def production_component(cls, value: str) -> str:
        # Imported lazily so the canonical contract module does not couple its
        # import order to catalog/API construction.
        from videoagents.tools.components import PRODUCTION_COMPONENT_ID_SET

        if value not in PRODUCTION_COMPONENT_ID_SET:
            raise ValueError("镜头组件不在生产清单中")
        return value

    @field_validator("shot_id", "title", "body", "source_label")
    @classmethod
    def readable(cls, value: str) -> str:
        if any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError("镜头文字含控制字符")
        return value

    @model_validator(mode="after")
    def interval(self) -> "Shot":
        if not self.title.strip() or not self.shot_id.strip():
            raise ValueError("镜头标题及 ID 不能为空")
        if self.end_frame <= self.start_frame:
            raise ValueError("镜头区间无效")
        duration = self.end_frame - self.start_frame
        if self.set_design:
            if self.layers:
                raise ValueError("组件套通过 parts 调整内部组件，不能另外叠加 layers")
            ids = [part.part_id for part in self.set_design.parts]
            if len(ids) != len(set(ids)):
                raise ValueError("组件套内 part_id 不能重复")
            if any(part.end_frame > duration for part in self.set_design.parts):
                raise ValueError("组件套显示区间必须位于镜头本地时间内")
            if any(step.end_frame > duration for step in self.set_design.focus_steps):
                raise ValueError("素材引导步骤必须位于镜头本地时间内")
        for index, layer in enumerate(self.layers):
            if layer.end_frame > duration:
                raise ValueError("组件层须在所属镜头的本地区间内")
            if layer.component_id == self.component_id:
                raise ValueError("组件层不能重复所属镜头组件")
            for other in self.layers[:index]:
                if layer.component_id == other.component_id:
                    raise ValueError("同一镜头不能重复组件层 ID")
                if layer.role == other.role and max(layer.start_frame, other.start_frame) < min(layer.end_frame, other.end_frame):
                    raise ValueError("同一角色的组件层不能重叠")
        if self.media_usage == "context_example":
            if self.component_id == "evidence":
                raise ValueError("另案示例不能使用 evidence 组件")
            if "另案示例" not in self.source_label:
                raise ValueError("另案示例必须在 source_label 中标明")
            if not re.search(r"(?<![\w-])(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?![\w-])", self.source_label):
                raise ValueError("另案示例必须在 source_label 中包含来源域名")
        return self


class Timeline(Contract):
    schema_version: Literal["1"] = "1"
    job_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    revision: int = Field(ge=1)
    width: int = Field(ge=240, le=3840)
    height: int = Field(ge=240, le=3840)
    fps: int = Field(ge=15, le=60)
    duration_in_frames: int = Field(gt=0, le=108000)
    presentation: Literal["production", "component_sample"] = Field(
        default="production",
        exclude_if=lambda value: value == "production",
    )
    audio_src: str | None = None
    shots: list[Shot] = Field(min_length=1, max_length=400)
    captions: list[Caption] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def coverage(self) -> "Timeline":
        if self.width % 2 or self.height % 2:
            raise ValueError("视频宽高必须为偶数")
        if self.presentation == "component_sample" and (self.audio_src or self.captions):
            raise ValueError("组件样片时间轴不能包含音频或字幕")
        if self.captions and not self.audio_src:
            raise ValueError("带字幕的时间轴必须有真实音频")
        if self.duration_in_frames > self.fps * 1800:
            raise ValueError("时间轴超过 1800 秒时长限制")
        previous = 0
        ids: set[str] = set()
        for shot in self.shots:
            if shot.start_frame != previous or shot.shot_id in ids:
                raise ValueError("镜头必须从第 0 帧连续覆盖、不可重叠且 ID 唯一")
            previous = shot.end_frame
            ids.add(shot.shot_id)
        if previous != self.duration_in_frames:
            raise ValueError("镜头必须完整覆盖视频时长")
        previous_ms = 0.0
        duration_ms = 1000 * self.duration_in_frames / self.fps
        for caption in self.captions:
            if caption.start_ms < previous_ms or caption.end_ms > duration_ms + 0.001:
                raise ValueError("字幕必须有序、不重叠且处于视频范围内")
            previous_ms = caption.end_ms
        return self


class DirectorShotReviewSpec(Contract):
    """The director's chosen absolute frame and explanation for one shot."""

    shot_id: str = Field(min_length=1, max_length=100)
    review_frame: int = Field(ge=0)
    component_reason: str = Field(min_length=1, max_length=600)
    visual_action: str = Field(min_length=1, max_length=800)

    @field_validator("shot_id", "component_reason", "visual_action")
    @classmethod
    def readable_review_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("逐镜审核设计不能为空")
        return value


class DirectorShotReviewItem(DirectorShotReviewSpec):
    """A real rendered still with its executable component selection."""

    index: int = Field(ge=1, le=400)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    component_id: str = Field(min_length=1, max_length=100)
    set_id: str | None = Field(default=None, max_length=100)
    component_ids: list[str] = Field(min_length=1, max_length=40)
    title: str = Field(default="", max_length=1000)
    body: str = Field(default="", max_length=6000)
    asset_src: str | None = None
    source_label: str | None = None
    narration: str = Field(default="", max_length=30000)
    image: Artifact

    @model_validator(mode="after")
    def valid_frame_and_image(self) -> "DirectorShotReviewItem":
        if not self.start_frame <= self.review_frame < self.end_frame:
            raise ValueError("审核代表帧必须落在对应镜头内")
        if self.image.kind != "shot_review_frame" or self.image.mime_type != "image/png":
            raise ValueError("逐镜审核必须绑定真实PNG帧产物")
        if self.component_id not in self.component_ids or len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("审核组件清单必须含主组件且不能重复")
        return self


class DirectorShotReviewManifest(Contract):
    """Complete review pack bound to one job revision and director plan."""

    schema_version: Literal[1] = 1
    mode: Literal["per_shot_stills"] = "per_shot_stills"
    job_id: str = Field(min_length=1, max_length=100)
    revision: int = Field(ge=1)
    director_plan_artifact_id: str = Field(min_length=1, max_length=100)
    director_plan_sha256: str = Field(min_length=64, max_length=64)
    dependency_fingerprint: str = Field(min_length=64, max_length=64)
    timeline_fingerprint: str = Field(min_length=64, max_length=64)
    width: int = Field(ge=240, le=3840)
    height: int = Field(ge=240, le=3840)
    fps: int = Field(ge=15, le=60)
    duration_in_frames: int = Field(gt=0)
    items: list[DirectorShotReviewItem] = Field(min_length=1, max_length=400)

    @model_validator(mode="after")
    def complete_unique_pack(self) -> "DirectorShotReviewManifest":
        previous = 0
        shot_ids: set[str] = set()
        image_ids: set[str] = set()
        for index, item in enumerate(self.items, 1):
            if item.index != index or item.start_frame != previous or item.shot_id in shot_ids:
                raise ValueError("逐镜审核必须按顺序完整覆盖时间轴，镜头ID不能重复")
            if item.image.artifact_id in image_ids or item.image.revision != self.revision:
                raise ValueError("逐镜审核图片必须唯一且属于当前版本")
            previous = item.end_frame
            shot_ids.add(item.shot_id)
            image_ids.add(item.image.artifact_id)
        if previous != self.duration_in_frames:
            raise ValueError("逐镜审核缺少镜头或时间轴覆盖不完整")
        return self


class Finding(Contract):
    finding_id: str
    severity: Literal["error", "warning", "info"]
    category: str
    message: str
    owner: str
    blocking: bool
    start_frame: int | None = None
    end_frame: int | None = None


class Review(Contract):
    status: str
    findings: list[Finding] = Field(default_factory=list)
    media_sha256: str | None = None
    dependency_fingerprint: str
    coverage: list[str] = Field(default_factory=list)
    human_confirmed: bool = False


class ComponentEntry(Contract):
    component_id: str
    name: str
    description: str
    use_case: str
    library: str
    kind: Literal["adapter", "preset"]
    props_mode: Literal["typed", "material_slots"]
    material_capability: Literal["native_slots", "overlay"]
    orientation: str
    production_ready: bool
    min_frames: int
    allowed_usages: list[Literal["personal", "commercial", "unspecified"]]
    license_note: str
    preview_url: str | None = None


Status = Literal["DRAFT", "QUEUED", "RUNNING", "NEEDS_INPUT", "NEEDS_HUMAN", "READY_FOR_PUBLISH", "REJECTED", "FAILED", "CANCELLED"]
Stage = Literal["idle", "materials", "script", "voice", "director", "render", "review", "complete"]


class DirectorRequirements(Contract):
    min_library_components: int = Field(default=0, ge=0, le=187)


class Job(Contract):
    job_id: str
    revision: int
    status: Status
    stage: Stage
    message: str
    progress: float | None = None
    created_at: str
    updated_at: str
    brief: Brief
    director_requirements: DirectorRequirements | None = Field(default=None, exclude_if=lambda value: value is None)
    script: Script | None = None
    script_discussion: ScriptDiscussion | None = None
    timeline: Timeline | None = None
    assets: list[Asset] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    review: Review | None = None
    pending_input: dict[str, Any] | None = None
    latest_event_id: int = 0


class DraftRequest(Contract):
    base_revision: int = Field(ge=1)
    brief: Brief | None = None
    script: Script | None = None
    timeline: Timeline | None = None


class RunRequest(Contract):
    base_revision: int = Field(ge=1)
    action: Literal["produce", "voice", "storyboard", "preview", "final", "review"]
    idempotency_key: str = Field(min_length=8, max_length=200)
    continue_from: Literal["voice"] | None = None
    rebuild_from: Literal["director"] | None = None

    @model_validator(mode="after")
    def continuation_target(self):
        if self.continue_from is not None and self.rebuild_from is not None:
            raise ValueError("续跑与重做画面不能同时指定")
        if (self.continue_from is not None or self.rebuild_from is not None) and self.action not in {"produce", "storyboard", "preview", "final"}:
            raise ValueError("配音完成后的续跑需指定分镜或视频制作目标")
        return self


class RetryFailedRunRequest(Contract):
    base_revision: int = Field(ge=1)
    retry_command_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-f0-9]{32}$")
    idempotency_key: str = Field(min_length=8, max_length=200)


class ComponentDemoTutorialTarget(Contract):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_source(self) -> "ComponentDemoTutorialTarget":
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("教学圈选区域必须完整落在素材画面内")
        return self


class ComponentDemoTutorialStep(Contract):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    instruction: str = Field(min_length=1, max_length=24)
    target: ComponentDemoTutorialTarget

    @field_validator("instruction")
    @classmethod
    def readable_instruction(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError("教学口令不能为空或含控制字符")
        return value

    @model_validator(mode="after")
    def interval(self) -> "ComponentDemoTutorialStep":
        if self.end_frame - self.start_frame < 30:
            raise ValueError("每个教学步骤至少显示 30 帧")
        return self


class ComponentDemoMetric(Contract):
    label: str = Field(min_length=1, max_length=24)
    value: str = Field(min_length=1, max_length=20)
    detail: str | None = Field(default=None, min_length=1, max_length=32)

    @field_validator("label", "value", "detail")
    @classmethod
    def readable_metric_text(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in value)):
            raise ValueError("指标文字不能为空或含控制字符")
        return value


class ComponentDemoContent(Contract):
    title: str = Field(min_length=1, max_length=24)
    body: str = Field(min_length=1, max_length=90)
    takeaway: str = Field(min_length=1, max_length=24)
    items: list[str] | None = Field(default=None, min_length=2, max_length=4)
    metric: ComponentDemoMetric | None = None
    numeric_items: list[str] | None = Field(default=None, min_length=2, max_length=4)
    supporting_items: list[str] | None = Field(default=None, min_length=2, max_length=4)

    @field_validator("title", "body", "takeaway")
    @classmethod
    def readable_content_text(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError("无素材组件文案不能为空或含控制字符")
        return value

    @staticmethod
    def _readable_string_list(value: list[str] | None, *, item_limit: int, total_limit: int, message: str) -> list[str] | None:
        if value is None:
            return value
        for item in value:
            if not item.strip() or len(item) > item_limit or any(ord(char) < 32 and char not in "\t\r\n" for char in item):
                raise ValueError(message)
        if sum(len(item) for item in value) > total_limit:
            raise ValueError(message)
        return value

    @field_validator("items")
    @classmethod
    def readable_items(cls, value: list[str] | None) -> list[str] | None:
        return cls._readable_string_list(value, item_limit=32, total_limit=64, message="无素材组件列表项必须是 32 字以内非空文本且合计不能超过 64 字")

    @field_validator("numeric_items")
    @classmethod
    def readable_numeric_items(cls, value: list[str] | None) -> list[str] | None:
        return cls._readable_string_list(value, item_limit=24, total_limit=64, message="rich numeric_items 必须是 24 字以内非空文本且合计不超过 64 字")

    @field_validator("supporting_items")
    @classmethod
    def readable_supporting_items(cls, value: list[str] | None) -> list[str] | None:
        return cls._readable_string_list(value, item_limit=24, total_limit=64, message="rich supporting_items 必须是 24 字以内非空文本且合计不超过 64 字")


def _component_demo_metric_parts(value: str) -> tuple[int, str] | None:
    match = re.fullmatch(r"([0-9]{1,5})([\u4e00-\u9fff]{1,2})", value)
    if not match:
        return None
    number = int(match.group(1))
    if number > 99999:
        return None
    return number, match.group(2)


def _component_demo_numeric_item_parts(value: str) -> tuple[int, str] | None:
    match = re.fullmatch(r"[^:\n]{1,12}:([0-9]{1,5})([\u4e00-\u9fff]{1,2})", value)
    if not match:
        return None
    number = int(match.group(1))
    if number > 99999:
        return None
    return number, match.group(2)


def _validate_component_demo_metric(metric: ComponentDemoMetric | None, *, required: bool, context: str) -> tuple[int, str] | None:
    if metric is None:
        if required:
            raise ValueError(f"{context} 必须提供 metric")
        return None
    parts = _component_demo_metric_parts(metric.value)
    if parts is None:
        raise ValueError(f"{context} metric.value 必须是 0..99999 的 ASCII 整数加 1 到 2 个汉字单位，不能使用百分比、小数、全角数字或混合文本")
    return parts


def _validate_component_demo_numeric_items(items: list[str] | None, *, count: int | None, context: str) -> tuple[list[tuple[int, str]], str]:
    if items is None:
        raise ValueError(f"{context} 必须提供 numeric_items")
    if count is not None and len(items) != count:
        raise ValueError(f"{context} numeric_items 必须提供 exactly {count} 项")
    parsed: list[tuple[int, str]] = []
    unit: str | None = None
    for item in items:
        parts = _component_demo_numeric_item_parts(item)
        if parts is None:
            raise ValueError(f"{context} numeric_items 每项必须是 标签:ASCII整数+1到2个汉字单位")
        if unit is None:
            unit = parts[1]
        elif unit != parts[1]:
            raise ValueError(f"{context} numeric_items 必须使用同一个单位")
        parsed.append(parts)
    return parsed, unit or ""


BASIC_MATERIAL_SET_IDS = {"A01", "A02", "A03", "A04", "A05", "A06"}
MATERIAL_RICH_SET_IDS = {"A07", "A08", "A09", "A10", "A11", "A12"}
B_BASIC_SET_IDS = {"B01", "B02", "B03", "B04", "B05", "B06"}
B_RICH_SET_IDS = {f"B{index:02d}" for index in range(1, 19)}
B_RICH_ONLY_SET_IDS = B_RICH_SET_IDS - B_BASIC_SET_IDS
MATERIAL_RICH_RULES: dict[str, dict[str, object]] = {
    "A07": {"items": 3, "supporting": 3},
    "A08": {"items": 3, "supporting": 3},
    "A09": {"items": 3, "supporting": 3, "metric": "items_count", "focus_items": True},
    "A10": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "A11": {"items": 3, "supporting": 3},
    "A12": {"items": 3, "supporting": 3},
}
B_RICH_RULES: dict[str, dict[str, object]] = {
    "B01": {"items": 3, "metric": "items_count"},
    "B02": {"items": 3, "metric": "items_count"},
    "B03": {"items": 2, "numeric": 2},
    "B04": {"numeric": 3, "metric": "numeric_sum"},
    "B05": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B06": {"items_range": (2, 3), "supporting": 2, "metric": "items_count"},
    "B07": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "B08": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "B09": {"items": 2, "numeric": 2, "metric": "numeric_diff"},
    "B10": {"items": 3, "numeric": 3, "metric": "numeric_sum"},
    "B11": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B12": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B13": {"items": 2, "supporting": 3, "metric": "supporting_count"},
    "B14": {"items": 3, "supporting": 2, "metric": "items_count"},
    "B15": {"items": 3, "supporting": 3, "numeric": 3, "metric": "numeric_sum"},
    "B16": {"items": 3, "supporting": 3, "metric": "items_count"},
    "B17": {"items": 3, "supporting": 2, "metric": "items_count"},
    "B18": {"items": 2, "supporting": 3, "numeric": 2, "metric": "supporting_count_and_numeric_max"},
}


def _expect_component_demo_items(items: list[str] | None, rule: dict[str, object], context: str) -> int | None:
    if "items" in rule:
        expected = int(rule["items"])
        if items is None or len(items) != expected:
            raise ValueError(f"{context} rich 必须提供 exactly {expected} 个 items")
        return len(items)
    if "items_range" in rule:
        lower, upper = rule["items_range"]  # type: ignore[misc]
        if items is None or not int(lower) <= len(items) <= int(upper):
            raise ValueError(f"{context} rich 必须提供 {lower} 到 {upper} 个 items")
        return len(items)
    if items is not None:
        raise ValueError(f"{context} rich 不接受 items")
    return None


def _expect_component_demo_supporting(items: list[str] | None, rule: dict[str, object], context: str) -> int | None:
    expected = rule.get("supporting")
    if expected is None:
        if items is not None:
            raise ValueError(f"{context} rich 不接受 supporting_items")
        return None
    if items is None or len(items) != int(expected):
        raise ValueError(f"{context} rich 必须提供 exactly {expected} 个 supporting_items")
    return len(items)


def _validate_component_demo_rich_metric(
    set_id: str,
    *,
    metric: ComponentDemoMetric | None,
    metric_rule: object,
    item_count: int | None,
    supporting_count: int | None,
    numeric_parts: list[tuple[int, str]] | None,
    numeric_unit: str | None,
) -> None:
    metric_parts = _validate_component_demo_metric(metric, required=True, context=f"{set_id} rich")
    if metric_parts is None:
        raise ValueError(f"{set_id} rich 必须提供 metric")
    metric_number, metric_unit = metric_parts
    if metric_rule == "items_count":
        if item_count is None or metric_number != item_count:
            raise ValueError(f"{set_id} rich metric.value 数字必须等于 items 条数")
    elif metric_rule == "supporting_count":
        if supporting_count is None or metric_number != supporting_count:
            raise ValueError(f"{set_id} rich metric.value 数字必须等于 supporting_items 条数")
    elif metric_rule == "numeric_sum":
        if numeric_parts is None or numeric_unit is None or metric_unit != numeric_unit or metric_number != sum(number for number, _ in numeric_parts):
            raise ValueError(f"{set_id} rich metric.value 必须等于 numeric_items 的同单位求和")
    elif metric_rule == "numeric_diff":
        if numeric_parts is None or numeric_unit is None or metric_unit != numeric_unit or len(numeric_parts) != 2 or metric_number != abs(numeric_parts[1][0] - numeric_parts[0][0]):
            raise ValueError(f"{set_id} rich metric.value 必须等于两个 numeric_items 的同单位差值")
    elif metric_rule == "supporting_count_and_numeric_max":
        if supporting_count is None or metric_number != supporting_count:
            raise ValueError(f"{set_id} rich metric.value 数字必须等于 supporting_items 条数")
        if numeric_parts is None or numeric_unit is None or metric_unit != numeric_unit or metric_number != max(number for number, _ in numeric_parts):
            raise ValueError(f"{set_id} rich metric.value 必须等于 numeric_items 最大值")
    else:
        raise ValueError(f"{set_id} rich metric 规则未登记")


class ComponentDemoRequest(Contract):
    base_revision: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=200)
    set_id: Literal["A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "A10", "A11", "A12", "B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B09", "B10", "B11", "B12", "B13", "B14", "B15", "B16", "B17", "B18"]
    asset_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    duration_seconds: float = Field(default=10, ge=6, le=20)
    composition: Literal["basic", "rich"] = "basic"
    tutorial_steps: list[ComponentDemoTutorialStep] | None = Field(default=None, min_length=1, max_length=8)
    focus_steps: list[ComponentDemoTutorialStep] | None = Field(default=None, min_length=1, max_length=8)
    content: ComponentDemoContent | None = None

    @model_validator(mode="after")
    def demo_steps_contract(self) -> "ComponentDemoRequest":
        is_material_set = self.set_id.startswith("A")
        if is_material_set:
            if not self.asset_id:
                raise ValueError("A 组件套必须指定当前任务已导入的 asset_id")
            if self.set_id in MATERIAL_RICH_SET_IDS:
                if self.composition != "rich":
                    raise ValueError(f"{self.set_id} 只支持 rich composition")
                if self.content is None:
                    raise ValueError(f"{self.set_id} rich 必须提供 content")
                self._validate_material_rich_content()
            elif self.composition != "basic":
                raise ValueError("A01-A06 组件套只支持 basic composition")
            elif self.content is not None:
                raise ValueError("A 组件套不接受无素材 content")
        else:
            if self.asset_id is not None:
                raise ValueError("B 无素材组件套不接受 asset_id")
            if self.tutorial_steps is not None or self.focus_steps is not None:
                raise ValueError("B 无素材组件套不接受教学或重点圈选步骤")
            if self.content is None:
                raise ValueError("B 无素材组件套必须提供 content")
            if self.composition == "rich":
                self._validate_rich_b_content()
            else:
                if self.set_id in B_RICH_ONLY_SET_IDS:
                    raise ValueError(f"{self.set_id} 只支持 rich composition")
                self._validate_basic_b_content()
            return self
        if self.tutorial_steps is not None and self.focus_steps is not None:
            raise ValueError("教学步骤和重点圈选步骤不能同时提供")
        if self.set_id in MATERIAL_RICH_SET_IDS:
            if self.tutorial_steps is not None:
                raise ValueError("A07-A12 rich 素材组件套不接受 tutorial_steps")
            if self.set_id == "A09":
                if self.focus_steps is None:
                    raise ValueError("A09 rich 必须提供 focus_steps")
                assert self.content is not None and self.content.items is not None
                if [step.instruction for step in self.focus_steps] != self.content.items:
                    raise ValueError("A09 focus_steps.instruction 必须逐项等于 content.items")
            elif self.focus_steps is not None:
                raise ValueError(f"{self.set_id} rich 不接受 focus_steps")
        steps = self.tutorial_steps or self.focus_steps
        if steps is None:
            return self
        if self.set_id not in MATERIAL_RICH_SET_IDS and self.tutorial_steps is not None and self.set_id != "A02":
            raise ValueError("教学步骤只允许用于 A02 App 对象组件套")
        if self.focus_steps is not None and self.set_id not in {"A03", "A04", "A05", "A06", "A09"}:
            raise ValueError("重点圈选步骤只允许用于 A03-A06 素材组件套")
        frames = math.ceil(self.duration_seconds * 30)
        previous = 0
        for step in steps:
            if step.start_frame != previous:
                raise ValueError("步骤必须从 0 开始连续覆盖整个样片")
            previous = step.end_frame
        if previous != frames:
            raise ValueError("步骤必须连续覆盖整个样片帧段")
        return self

    def _validate_material_rich_content(self) -> None:
        assert self.content is not None
        if self.duration_seconds < 12:
            raise ValueError("rich 有素材组件套 duration_seconds 至少 12 秒")
        if len(self.content.title) > 18 or len(self.content.body) > 60 or len(self.content.takeaway) > 18:
            raise ValueError("rich content title/body/takeaway 分别不能超过 18/60/18 字")
        rule = MATERIAL_RICH_RULES[self.set_id]
        item_count = _expect_component_demo_items(self.content.items, rule, self.set_id)
        supporting_count = _expect_component_demo_supporting(self.content.supporting_items, rule, self.set_id)
        numeric_parts: list[tuple[int, str]] | None = None
        numeric_unit: str | None = None
        numeric_count = rule.get("numeric")
        if numeric_count is None:
            if self.content.numeric_items is not None:
                raise ValueError(f"{self.set_id} rich 不接受 numeric_items")
        else:
            numeric_parts, numeric_unit = _validate_component_demo_numeric_items(self.content.numeric_items, count=int(numeric_count), context=f"{self.set_id} rich")
        metric_rule = rule.get("metric")
        if metric_rule is None:
            if self.content.metric is not None:
                raise ValueError(f"{self.set_id} rich 不接受 metric")
            return
        _validate_component_demo_rich_metric(
            self.set_id,
            metric=self.content.metric,
            metric_rule=metric_rule,
            item_count=item_count,
            supporting_count=supporting_count,
            numeric_parts=numeric_parts,
            numeric_unit=numeric_unit,
        )

    def _validate_basic_b_content(self) -> None:
        assert self.content is not None
        if self.content.numeric_items is not None or self.content.supporting_items is not None:
            raise ValueError("basic B 无素材组件套不接受 numeric_items 或 supporting_items")
        if self.set_id in {"B01", "B02"} and (self.content.items is not None or self.content.metric is not None):
            raise ValueError(f"{self.set_id} 只接受 title/body/takeaway")
        if self.set_id == "B03" and (self.content.items is None or len(self.content.items) != 2 or self.content.metric is not None):
            raise ValueError("B03 对比组件必须提供 exactly 2 个 items 且不能提供 metric")
        if self.set_id == "B04":
            if self.content.items is not None or self.content.metric is None:
                raise ValueError("B04 数字组件必须只提供 metric")
            _validate_component_demo_metric(self.content.metric, required=True, context="B04")
        if self.set_id == "B05" and (self.content.items is None or len(self.content.items) != 3 or self.content.metric is not None):
            raise ValueError("B05 步骤组件必须提供 exactly 3 个 items 且不能提供 metric")
        if self.set_id == "B06" and (self.content.items is None or not 2 <= len(self.content.items) <= 3 or self.content.metric is not None):
            raise ValueError("B06 结论组件必须提供 2 到 3 个 items 且不能提供 metric")

    def _validate_rich_b_content(self) -> None:
        assert self.content is not None
        if self.set_id not in B_RICH_SET_IDS:
            raise ValueError("未知 rich B 无素材组件套")
        if self.duration_seconds < 12:
            raise ValueError("rich B 无素材组件套 duration_seconds 至少 12 秒")
        if len(self.content.title) > 18 or len(self.content.body) > 60 or len(self.content.takeaway) > 18:
            raise ValueError("rich content title/body/takeaway 分别不能超过 18/60/18 字")
        if self.content.items is not None:
            if any(len(item) > 24 for item in self.content.items) or sum(len(item) for item in self.content.items) > 64:
                raise ValueError("rich items 每项不能超过 24 字且合计不超过 64 字")
        rule = B_RICH_RULES[self.set_id]
        item_count = _expect_component_demo_items(self.content.items, rule, self.set_id)
        supporting_count = _expect_component_demo_supporting(self.content.supporting_items, rule, self.set_id)
        numeric_parts: list[tuple[int, str]] | None = None
        numeric_unit: str | None = None
        numeric_count = rule.get("numeric")
        if numeric_count is None:
            if self.content.numeric_items is not None:
                raise ValueError(f"{self.set_id} rich 不接受 numeric_items")
        else:
            numeric_parts, numeric_unit = _validate_component_demo_numeric_items(self.content.numeric_items, count=int(numeric_count), context=f"{self.set_id} rich")
        metric_rule = rule.get("metric")
        if metric_rule is None:
            if self.content.metric is not None:
                raise ValueError(f"{self.set_id} rich 不接受 metric")
            return
        _validate_component_demo_rich_metric(
            self.set_id,
            metric=self.content.metric,
            metric_rule=metric_rule,
            item_count=item_count,
            supporting_count=supporting_count,
            numeric_parts=numeric_parts,
            numeric_unit=numeric_unit,
        )



class ResumeRequest(Contract):
    base_revision: int = Field(ge=1)
    decision: Literal["confirm", "revise", "cancel"]
    note: str = Field(default="", max_length=3000)
    idempotency_key: str = Field(min_length=8, max_length=200)
    pending_token: str = Field(min_length=16, max_length=100)
    stop_after: Literal["voice"] | None = None
    director_requirements: DirectorRequirements | None = Field(default=None, exclude_if=lambda value: value is None)
    reviewed_shot_ids: list[Annotated[str, Field(min_length=1, max_length=100)]] | None = Field(
        default=None, min_length=1, max_length=400, exclude_if=lambda value: value is None,
    )

    @field_validator("reviewed_shot_ids")
    @classmethod
    def unique_reviewed_shots(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (len(set(value)) != len(value) or any(not item.strip() for item in value)):
            raise ValueError("已阅镜头ID不能为空或重复")
        return value

    @model_validator(mode="after")
    def stop_after_confirmation(self):
        if self.reviewed_shot_ids is not None and self.decision != "confirm":
            raise ValueError("已阅镜头只可随逐镜审核确认提交")
        if self.stop_after is not None and self.decision != "confirm":
            raise ValueError("只跑配音需确认当前文案或继续配音中断")
        if self.director_requirements is not None and self.decision != "revise":
            raise ValueError("导演制作要求只能随导演返工提交")
        return self


RoleId = Literal["materials", "screenwriter", "script_reviewer", "voice", "director", "editing", "review"]
ModelProvider = Literal["codex_cli", "trae_cli", "claude_code_cli"]


class ModelChoice(Contract):
    id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=3000)
    is_default: bool = False
    hidden: bool = False


class ModelCatalog(Contract):
    provider: ModelProvider
    status: Literal["ready", "unavailable", "error"]
    models: list[ModelChoice] = Field(default_factory=list, max_length=2000)
    message: str = Field(max_length=1000)
    fetched_at: str


class RoleModelConfig(Contract):
    enabled: bool = False
    provider: ModelProvider = "codex_cli"
    model: str = Field(default="", max_length=200)
    timeout_seconds: int = Field(default=900, ge=30, le=1800)


class RoleModels(Contract):
    materials: RoleModelConfig = Field(default_factory=RoleModelConfig)
    screenwriter: RoleModelConfig = Field(default_factory=RoleModelConfig)
    script_reviewer: RoleModelConfig = Field(default_factory=RoleModelConfig)
    voice: RoleModelConfig = Field(default_factory=RoleModelConfig)
    director: RoleModelConfig = Field(default_factory=RoleModelConfig)
    editing: RoleModelConfig = Field(default_factory=RoleModelConfig)
    review: RoleModelConfig = Field(default_factory=RoleModelConfig)


class ModelFinding(Contract):
    severity: Literal["error", "warning", "info"]
    message: str = Field(min_length=1, max_length=1500)
    owner: Literal["materials", "screenwriter", "voice", "director", "editing", "review", "user"]
    blocking: bool


class VoiceSegmentPerformance(Contract):
    segment_id: str = Field(min_length=1, max_length=100)
    delivery_style: str = Field(min_length=1, max_length=500)
    pause_after_ms: int = Field(default=0, ge=0, le=1200)

    @field_validator("delivery_style")
    @classmethod
    def readable_style(cls, value: str) -> str:
        if not value.strip() or any(ord(char) < 32 and char not in "\t\r\n" for char in value):
            raise ValueError("逐段表演指令不能为空或含控制字符")
        return value


class VoiceAdvice(Contract):
    delivery_notes: list[str] = Field(default_factory=list, max_length=30)
    segment_performances: list[VoiceSegmentPerformance] = Field(default_factory=list, max_length=200)
    pronunciation_notes: list[str] = Field(default_factory=list, max_length=30)
    findings: list[ModelFinding] = Field(default_factory=list, max_length=30)

    @field_validator("delivery_notes", "pronunciation_notes")
    @classmethod
    def readable_notes(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("配音建议须为非空文本，每条最多 500 字")
        return values

    @model_validator(mode="after")
    def unique_segment_performances(self) -> "VoiceAdvice":
        ids = [item.segment_id for item in self.segment_performances]
        if len(ids) != len(set(ids)):
            raise ValueError("逐段表演计划的段落 ID 必须唯一")
        return self


class EditingFinding(ModelFinding):
    owner: Literal["director", "editing"]


class EditingAdvice(Contract):
    pacing_notes: list[str] = Field(default_factory=list, max_length=30)
    layout_notes: list[str] = Field(default_factory=list, max_length=30)
    findings: list[EditingFinding] = Field(default_factory=list, max_length=30)

    @field_validator("pacing_notes", "layout_notes")
    @classmethod
    def readable_notes(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("剪辑建议须为非空文本，每条最多 500 字")
        return values


class ContentReviewAdvice(Contract):
    findings: list[ModelFinding] = Field(default_factory=list, max_length=30)


class MaterialSourceFile(Contract):
    """技能读取的真实正文；文件和散列由素材节点再次核验。"""

    url: str = Field(min_length=1, max_length=4000)
    title: str = Field(min_length=1, max_length=500)
    platform: str = Field(min_length=1, max_length=100)
    text_file: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class MaterialVisualFile(Contract):
    """实际下载的原图、截图或视频，必须关联已读取的来源。"""

    source_url: str = Field(min_length=1, max_length=4000)
    kind: Literal["image", "screenshot", "video"]
    file: str = Field(min_length=1, max_length=500)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    image_url: str = Field(default="", max_length=4000)
    media_url: str = Field(default="", max_length=4000)
    description: str = Field(min_length=1, max_length=1000)


class MaterialResearch(Contract):
    """素材 Agent 的最终清单，不包含原始工具对话。"""

    sources: list[MaterialSourceFile] = Field(max_length=30)
    visuals: list[MaterialVisualFile]
    limitations: list[str] = Field(max_length=40)

    @field_validator("limitations")
    @classmethod
    def readable_limitations(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError("检索缺口须为非空文本，每条最多 1000 字")
        return values


class SettingsPatch(Contract):
    role_models: dict[RoleId, RoleModelConfig] | None = None
    script_discussion_enabled: bool | None = None  # 兼容旧客户端；执行时始终开启讨论。
    script_discussion_max_rounds: int | None = Field(default=None, ge=1, le=5)
    ark_api_key: str | None = None
    search_provider: Literal["none", "opencli_google", "tavily", "google_cse"] | None = None
    search_api_key: str | None = None
    google_search_engine_id: str | None = Field(default=None, max_length=200)
    research_platforms: list[str] | None = Field(default=None, min_length=1, max_length=40)
    research_results_per_platform: int | None = Field(default=None, ge=1, le=5)
    research_max_searches: int | None = Field(default=None, ge=1, le=32)
    research_max_sources: int | None = Field(default=None, ge=1, le=30)
    research_max_visuals: int | None = Field(default=None, ge=0, deprecated=True)  # 兼容旧客户端；不再限制素材数量。
    research_download_images: bool | None = None
    voice_provider: Literal["none", "byte_http", "byte_ws"] | None = None
    voice_app_id: str | None = None
    voice_access_token: str | None = None
    voice_api_key: str | None = None
    voice_resource_id: str | None = None
    voice_id: str | None = None
    voice_endpoint: str | None = None
    voice_model: str | None = Field(default=None, max_length=200)
    voice_style: str | None = Field(default=None, max_length=2000)  # 自然语言配音风格，不修改旁白正文。
    voice_speech_rate: int | None = Field(default=None, ge=-50, le=100)  # 字节语速百分比调整，0 为默认语速。
    aligner_url: str | None = None
    aligner_api_key: str | None = None
    capture_enabled: bool | None = None
    max_llm_calls: int | None = Field(default=None, ge=1, le=100)
    max_voice_chars: int | None = Field(default=None, ge=1, le=100000)
    render_timeout_seconds: int | None = Field(default=None, ge=30, le=7200)

    @field_validator("research_platforms")
    @classmethod
    def supported_platforms(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        from videoagents.tools.research import PLATFORM_CATALOG
        known = {item["id"] for item in PLATFORM_CATALOG}
        if len(set(values)) != len(values) or not set(values) <= known:
            raise ValueError("素材平台必须来自工具目录，且不能重复")
        return values
