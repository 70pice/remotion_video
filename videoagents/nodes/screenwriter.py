"""The writer comes first: it designs segments with its own read-only research."""

import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from videoagents.contracts import (
    Brief,
    Job,
    Script,
    ScriptRewrite,
    ScriptSegment,
)
from videoagents.nodes.common import (
    agent_state,
    mark_feedback_applied,
    needs_script_revision,
    request_input,
    stage_feedback,
    start_stage,
    state_context,
)
from videoagents.nodes.script_review import SCRIPT_REVIEW_NODE
from videoagents.prompts import load_prompt
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository

NARRATIVE_PROMPT = load_prompt("screenwriter")
PROMPT = NARRATIVE_PROMPT
REWRITE_PROMPT = NARRATIVE_PROMPT + "\n\n" + load_prompt("screenwriter-rewrite")
SOURCE_DIGEST = re.compile(r"^[a-f0-9]{64}$")

# The writer may discover and read sources, but never download footage: the
# materials node owns real files so every asset is frozen and audited once.
WRITER_RESEARCH_TOOLS = ("skill", "search", "source")


def active_script_feedback(state: VideoState) -> tuple[str, dict[str, Any] | None]:
    """Prefer rejected-render feedback when it asks the writer to revise narration."""
    render_feedback = stage_feedback(state, "render")
    if render_feedback and (
        render_feedback.get("target") == "screenwriter"
        or needs_script_revision(str(render_feedback.get("note", "")))
    ):
        return "render", render_feedback
    director_feedback = stage_feedback(state, "director")
    if director_feedback and (
        director_feedback.get("target") == "screenwriter"
        or needs_script_revision(str(director_feedback.get("note", "")))
    ):
        return "director", director_feedback
    return "script", stage_feedback(state, "script")


def same_script_body(script: Script | dict[str, Any], snapshot: dict[str, Any]) -> bool:
    current = Script.model_validate(script).model_dump() if isinstance(script, dict) else script.model_dump()
    reviewed = Script.model_validate(snapshot).model_dump()
    for item in (current, reviewed):
        item.pop("origin", None)
        item.pop("revision", None)
    return current == reviewed


class ScreenwriterNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "script", "编剧正在检索真实来源并设计段落与口播")
        try:
            script = self.current_or_new(job, state)
            issues = script_issues(job.model_copy(update={"script": script}), strict=False)
            if issues:
                raise ValueError("；".join(issues))
            self.save(job, script)
            return state_context(self.repo, state, route=SCRIPT_REVIEW_NODE, gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "script", [str(exc)], getattr(exc, "fields", ["script"]), exc)

    def current_or_new(self, job: Job, state: VideoState) -> Script:
        """Reuse a saved draft on replay; otherwise write fresh or revise from feedback."""
        feedback_stage, feedback = active_script_feedback(state)
        current = next((item for item in reversed(job.artifacts)
                        if item.kind == "script" and item.revision == job.revision), None)
        context = agent_state(self.repo, job, state)
        if current is not None and not feedback:
            path, _, owner = self.repo.artifact_path(current.artifact_id)
            if owner == job.job_id:
                return Script.model_validate_json(path.read_text(encoding="utf-8"))
        if feedback:
            # SQL may have committed the rewrite before the applied receipt; a
            # saved script that already differs from the reviewed snapshot is
            # the finished rewrite, so never call the model a second time.
            if current is not None and type(feedback.get("script")) is dict:
                path, _, owner = self.repo.artifact_path(current.artifact_id)
                if owner == job.job_id:
                    saved = Script.model_validate_json(path.read_text(encoding="utf-8"))
                    if not same_script_body(saved, feedback["script"]):
                        mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                              feedback_stage, "screenwriter")
                        return saved
            script = self.rewrite(job, context, feedback)
            # Commit the rewrite before the applied receipt: a crash between
            # the two must replay from the saved script, not call the model
            # twice for one revision.
            self.save(job, script)
            mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                  feedback_stage, "screenwriter")
            return script
        return self.write(job, context)

    def save(self, job: Job, script: Script) -> Job:
        current = self.repo.get_job(job.job_id)
        script = script.model_copy(update={"origin": script.origin or "model", "revision": job.revision})
        job = self.repo.update_job(job.job_id, job.revision, script=script,
                                   status="RUNNING", stage="script",
                                   message="文案段落与口播已生成，等待人工确认后再采集素材",
                                   expected_event_id=current.latest_event_id)
        self.service.write_json(job, "script.json", script.model_dump(), "script")
        return job

    def _research_directory(self, job: Job) -> tuple[Path, Path]:
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "skills-research"
        folder.mkdir(parents=True, exist_ok=True)
        audit_path = folder.parent / f"writer-tool-events-{uuid.uuid4().hex[:12]}.jsonl"
        return folder, audit_path

    def _register_audit(self, job: Job, audit_path: Path) -> None:
        if not audit_path.exists() or not audit_path.stat().st_size:
            return
        folder = audit_path.parent
        snapshot = folder / f"writer-tool-audit-{uuid.uuid4().hex[:12]}.jsonl"
        snapshot.write_bytes(audit_path.read_bytes())
        current = self.repo.get_job(job.job_id)
        # Distinct from the materials node's audit kind so the two roles never
        # clobber each other's tool trail within one revision.
        artifact = self.service.register_artifact(current, snapshot, "writer_tool_audit", "application/x-ndjson")
        self.repo.update_job(job.job_id, job.revision, expected_event_id=current.latest_event_id,
                             artifacts=[item for item in current.artifacts if item.kind != "writer_tool_audit"] + [artifact])

    def write(self, job: Job, context: dict[str, Any]) -> Script:
        brief = Brief.model_validate(context["brief"])
        # Ready-to-read scripts skip research, but still require human approval.
        if brief.script_text.strip():
            chunks = [item.strip() for item in re.split(r"\n+", brief.script_text) if item.strip()]
            if len(chunks) == 1 and len(chunks[0]) > 72:
                chunks = [item.strip() for item in re.findall(r"[^。！？.!?]+[。！？.!?]?", chunks[0]) if item.strip()]
            urls = list(dict.fromkeys(list(brief.source_urls)))
            return Script(title=(brief.topic or "用户提供文案")[:300], origin="user", revision=job.revision,
                          segments=[ScriptSegment(segment_id=f"s{index + 1}", narration=text, screen_text=text[:100],
                                                  source_refs=urls, asset_ids=[],
                                                  visual_need="按本段内容寻找真实画面" if urls else "")
                                    for index, text in enumerate(chunks)])
        folder, audit_path = self._research_directory(job)
        try:
            value = self.model.invoke(
                context, "screenwriter", PROMPT, fields=("brief", "settings"),
                output_schema=Script.model_json_schema(),
                research_directory=folder, audit_path=audit_path,
                research_tools=WRITER_RESEARCH_TOOLS,
            )
        except BaseException:
            try:
                self._register_audit(job, audit_path)
            except Exception:
                pass
            raise
        self._register_audit(job, audit_path)
        value.update(origin="model", revision=job.revision)
        return Script.model_validate(value)

    def rewrite(self, job: Job, context: dict[str, Any], feedback: dict[str, Any]) -> Script:
        if type(feedback.get("script")) is dict:
            context = {**context, "script": feedback["script"]}
        fields = ("brief", "script", "research", "assets", "settings")
        if context.get("extras", {}).get("human_feedback"):
            fields = (*fields, "extras")
        folder, audit_path = self._research_directory(job)
        try:
            value = self.model.invoke(
                context, "screenwriter", REWRITE_PROMPT,
                fields=fields,
                command_id=(context.get("resume_command_id") or context.get("run_id", "")) + ":script-revise",
                output_schema=ScriptRewrite.model_json_schema(),
                research_directory=folder, audit_path=audit_path,
                research_tools=WRITER_RESEARCH_TOOLS,
            )
        except BaseException:
            try:
                self._register_audit(job, audit_path)
            except Exception:
                pass
            raise
        self._register_audit(job, audit_path)
        rewrite = ScriptRewrite.model_validate(value)
        script = rewrite.script.model_copy(update={"origin": "model", "revision": job.revision})
        if type(feedback.get("script")) is dict and same_script_body(script, feedback["script"]):
            raise ValueError("人工返工未产生文案修改，请补充更明确的修改意见")
        return script


def valid_source_url(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
            and parsed.username is None and parsed.password is None)


def trusted_research_source_urls(job: Job, research: dict | None) -> set[str]:
    """Return URLs whose source text was already frozen by the materials node."""

    if type(research) is not dict or research.get("status") != "COMPLETED":
        return set()
    source_artifacts = {
        (artifact.artifact_id, artifact.sha256)
        for artifact in job.artifacts
        if artifact.kind == "source"
    }
    urls: set[str] = set()
    for item in research.get("sources", []):
        if type(item) is not dict:
            continue
        text = item.get("text")
        digest = item.get("sha256")
        artifact_id = item.get("artifact_id")
        if not (isinstance(text, str) and text.strip()):
            continue
        if item.get("knowledge_status") != "skill_read":
            continue
        if not (isinstance(digest, str) and SOURCE_DIGEST.fullmatch(digest)):
            continue
        if not (isinstance(artifact_id, str) and artifact_id.strip()):
            continue
        if (artifact_id, digest) not in source_artifacts:
            continue
        for key in ("url", "final_url"):
            url = item.get(key)
            if isinstance(url, str) and valid_source_url(url):
                urls.add(url)
    return urls


def script_issues(job: Job, research: dict | None = None, *, strict: bool = True) -> list[str]:
    """Validate the script; strict mode additionally requires frozen evidence.

    The writer runs before materials, so its own pass only checks structure and
    URL shape (strict=False). Gates after materials keep the full trust check:
    every citation must trace to a frozen source and real evidence assets.
    """
    if not job.script:
        return ["没有有效短视频文案"]
    known_assets = {asset.asset_id: asset for asset in job.assets}
    research_sources = trusted_research_source_urls(job, research)
    known_sources = set(job.brief.source_urls) | {asset.source_url for asset in job.assets if asset.source_url} | research_sources
    issues = []
    for segment in job.script.segments:
        if not segment.source_refs and not segment.narration.startswith(("观点：", "个人感受：")):
            if strict:
                issues.append(f"段落 {segment.segment_id} 缺少支撑本段内容的真实来源，请补充来源或删除无依据的说法")
        for source in segment.source_refs:
            if not valid_source_url(source):
                issues.append(f"段落 {segment.segment_id} 来源 URL 无效")
            elif strict and source not in known_sources:
                issues.append(f"段落 {segment.segment_id} 来源不在用户来源或真实素材清单中")
        for asset_id in segment.asset_ids:
            if asset_id not in known_assets:
                issues.append(f"段落 {segment.segment_id} 素材不存在")
    if strict:
        facts = [segment for segment in job.script.segments if segment.source_refs]
        if facts and not any(asset.role == "evidence" and asset.source_url for asset in job.assets):
            issues.append("事实性文案需要带原始出处的真实证据图片、截图或视频")
    return issues
