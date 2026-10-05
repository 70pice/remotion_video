"""Canonical transport and production contracts. Extra properties are rejected."""

from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class Brief(Contract):
    topic: str = Field(default="", max_length=2000)
    script_text: str = Field(default="", max_length=30000)
    audience: str = Field(default="普通观众", max_length=500)
    platform: str = Field(default="抖音竖屏", max_length=100)
    usage: Literal["personal", "commercial", "unspecified"] = "unspecified"
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
    status: Literal["DISABLED", "DISCUSSING", "APPROVED", "EXHAUSTED"] = "DISABLED"
    rounds: list[ScriptDiscussionRound] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def ordered_rounds(self) -> "ScriptDiscussion":
        if len(self.rounds) > self.max_rounds or any(
            item.round != index + 1 or item.script.revision != self.revision
            for index, item in enumerate(self.rounds)
        ):
            raise ValueError("讨论轮数、顺序或文案版本不一致")
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


class Shot(Contract):
    shot_id: str = Field(min_length=1, max_length=100)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    component_id: ProductionId
    title: str = Field(default="", max_length=100)
    body: str = Field(default="", max_length=240)
    asset_src: str | None = None
    source_label: str = Field(default="", max_length=160)
    accent_color: str = Field(default="#8cffb8", pattern=r"^#[0-9a-fA-F]{6}$")
    props: dict[str, Any] = Field(default_factory=dict)

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
        return self


class Timeline(Contract):
    schema_version: Literal["1"] = "1"
    job_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    revision: int = Field(ge=1)
    width: int = Field(ge=240, le=3840)
    height: int = Field(ge=240, le=3840)
    fps: int = Field(ge=15, le=60)
    duration_in_frames: int = Field(gt=0, le=108000)
    audio_src: str | None = None
    shots: list[Shot] = Field(min_length=1, max_length=400)
    captions: list[Caption] = Field(default_factory=list, max_length=5000)

    @model_validator(mode="after")
    def coverage(self) -> "Timeline":
        if self.width % 2 or self.height % 2:
            raise ValueError("视频宽高必须为偶数")
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
    orientation: str
    production_ready: bool
    min_frames: int
    allowed_usages: list[Literal["personal", "commercial", "unspecified"]]
    license_note: str
    preview_url: str | None = None


Status = Literal["DRAFT", "QUEUED", "RUNNING", "NEEDS_INPUT", "NEEDS_HUMAN", "READY_FOR_PUBLISH", "REJECTED", "FAILED", "CANCELLED"]
Stage = Literal["idle", "materials", "script", "voice", "director", "render", "review", "complete"]


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


class ResumeRequest(Contract):
    base_revision: int = Field(ge=1)
    decision: Literal["confirm", "revise", "cancel"]
    note: str = Field(default="", max_length=3000)
    idempotency_key: str = Field(min_length=8, max_length=200)
    pending_token: str = Field(min_length=16, max_length=100)


RoleId = Literal["materials", "screenwriter", "script_reviewer", "voice", "director", "editing", "review"]
ModelProvider = Literal["codex_cli", "claude_code_cli"]


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
    timeout_seconds: int = Field(default=300, ge=30, le=1800)


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


class VoiceAdvice(Contract):
    delivery_notes: list[str] = Field(default_factory=list, max_length=30)
    pronunciation_notes: list[str] = Field(default_factory=list, max_length=30)
    findings: list[ModelFinding] = Field(default_factory=list, max_length=30)

    @field_validator("delivery_notes", "pronunciation_notes")
    @classmethod
    def readable_notes(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 500 for value in values):
            raise ValueError("配音建议须为非空文本，每条最多 500 字")
        return values


class EditingAdvice(Contract):
    pacing_notes: list[str] = Field(default_factory=list, max_length=30)
    layout_notes: list[str] = Field(default_factory=list, max_length=30)
    findings: list[ModelFinding] = Field(default_factory=list, max_length=30)

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
    visuals: list[MaterialVisualFile] = Field(max_length=20)
    limitations: list[str] = Field(max_length=40)

    @field_validator("limitations")
    @classmethod
    def readable_limitations(cls, values: list[str]) -> list[str]:
        if any(not value.strip() or len(value) > 1000 for value in values):
            raise ValueError("检索缺口须为非空文本，每条最多 1000 字")
        return values


class SettingsPatch(Contract):
    role_models: dict[RoleId, RoleModelConfig] | None = None
    script_discussion_enabled: bool | None = None
    script_discussion_max_rounds: int | None = Field(default=None, ge=1, le=5)
    search_provider: Literal["none", "opencli_google", "tavily", "google_cse"] | None = None
    search_api_key: str | None = None
    google_search_engine_id: str | None = Field(default=None, max_length=200)
    research_platforms: list[str] | None = Field(default=None, min_length=1, max_length=40)
    research_results_per_platform: int | None = Field(default=None, ge=1, le=5)
    research_max_searches: int | None = Field(default=None, ge=1, le=32)
    research_max_sources: int | None = Field(default=None, ge=1, le=30)
    research_max_visuals: int | None = Field(default=None, ge=0, le=20)
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
