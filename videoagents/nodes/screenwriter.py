import re
from typing import Any
from urllib.parse import urlparse

from videoagents.contracts import (
    Asset,
    Brief,
    Job,
    Script,
    ScriptDiscussion,
    ScriptDiscussionRound,
    ScriptRewrite,
    ScriptSegment,
)
from videoagents.nodes.common import (
    agent_state,
    current_discussion,
    mark_feedback_applied,
    needs_script_revision,
    request_input,
    save_discussion,
    stage_feedback,
    start_stage,
    state_context,
)
from videoagents.prompts import compose, load_prompt
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository

# 编剧的创作标准由独立 Markdown 维护：统一风格圣经 + 文案角色标准；初稿与
# 讨论改稿共享同一叙事标准，避免改稿退回产品说明书。
NARRATIVE_PROMPT = compose("shared-style", "screenwriter")
PROMPT = NARRATIVE_PROMPT + "\n\n" + load_prompt("screenwriter-draft")
REWRITE_PROMPT = NARRATIVE_PROMPT + "\n\n" + load_prompt("screenwriter-rewrite")


def active_script_feedback(state: VideoState) -> tuple[str, dict[str, Any] | None]:
    """Prefer rejected-render feedback when it asks the writer to revise narration."""
    render_feedback = stage_feedback(state, "render")
    if render_feedback and (
        render_feedback.get("target") == "screenwriter"
        or needs_script_revision(str(render_feedback.get("note", "")))
    ):
        return "render", render_feedback
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
        job = start_stage(self.repo, state, "script", "编剧根据素材节点的来源与图片创作文案")
        discussion = current_discussion(self.repo, state, job)
        try:
            if discussion.enabled:
                return self.discuss(state, job, discussion)
            feedback_stage, feedback = active_script_feedback(state)
            script, research = self.write_script(job, state)
            job = self.repo.update_job(job.job_id, job.revision, script=script, script_discussion=None)
            self.service.write_json(job, "script.json", script.model_dump(), "script")
            if feedback:
                mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                      feedback_stage, "screenwriter")
            return state_context(self.repo, state, route="script_gate",
                                 research=research, gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "script", [str(exc)], getattr(exc, "fields", ["script"]), exc)

    def discuss(self, state: VideoState, job: Job, discussion: ScriptDiscussion) -> dict[str, Any]:
        research = state.get("research", {})
        feedback_stage, feedback = active_script_feedback(state)
        if feedback and discussion.rounds:
            reviewed = feedback.get("script")
            latest = discussion.rounds[-1].script.model_dump()
            if type(reviewed) is dict and not same_script_body(latest, reviewed):
                mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                      "script", "screenwriter")
                return state_context(self.repo, state, route="script_reviewer", research=research, gate_issues=[])
        # A saved unreviewed draft or terminal discussion is reused on replay.
        # Human revision feedback explicitly opens a new discussion turn.
        if feedback or not discussion.rounds or (discussion.status == "DISCUSSING" and discussion.rounds[-1].critique):
            if not discussion.rounds:
                script, research = self.write_script(job, state)
                response = ""
            else:
                discussion.status = "DISCUSSING"
                script, response = self.rewrite(job, discussion, state)
                if feedback:
                    # 人工返工开启新的机器审查周期，沿用冻结的轮数上限。
                    # 旧讨论已有不可变产物；不能把新稿追加到已用满的旧周期，
                    # 也不能沿用旧稿的通过结果。先改稿再重置，以便失败重放复用模型回执。
                    discussion.rounds = []
            discussion.rounds.append(ScriptDiscussionRound(round=len(discussion.rounds) + 1,
                                                           script=script, response=response))
            job = save_discussion(self.repo, state, discussion)
            if feedback:
                mark_feedback_applied(self.repo, self.service, self.repo.get_job(job.job_id), state,
                                      feedback_stage, "screenwriter")
        else:
            job = self.repo.get_job(job.job_id)
        return state_context(self.repo, state, route="script_reviewer", research=research, gate_issues=[])

    def rewrite(self, job: Job, discussion: ScriptDiscussion,
                state: VideoState | None = None) -> tuple[Script, str]:
        # This path intentionally bypasses write_script's existing-draft cache.
        context = agent_state(self.repo, job, state)
        context["script_discussion"] = discussion.model_dump()
        _, feedback = active_script_feedback(context)
        if feedback and type(feedback.get("script")) is dict:
            context = {**context, "script": feedback["script"]}
        fields = ("brief", "script", "script_discussion", "research", "assets")
        if feedback:
            fields = (*fields, "extras")
        value = self.model.invoke(
            context, "screenwriter", REWRITE_PROMPT,
            fields=fields,
            command_id=(context.get("resume_command_id") or context.get("run_id", "")) + ":script-revise",
            output_schema=ScriptRewrite.model_json_schema(),
        )
        rewrite = ScriptRewrite.model_validate(value)
        script = rewrite.script.model_copy(update={"origin": "model", "revision": job.revision})
        if feedback and type(feedback.get("script")) is dict and same_script_body(script, feedback["script"]):
            raise ValueError("人工返工未产生文案修改，请补充更明确的修改意见")
        issues = script_issues(self.repo.get_job(job.job_id).model_copy(update={"script": script}))
        if issues:
            raise ValueError("讨论改稿未通过来源检查：" + "；".join(issues))
        return script, rewrite.response

    def write_script(self, job: Job, state: VideoState | None = None) -> tuple[Script, dict]:
        # 编剧不再检索或截图，只消费素材节点在模型调用前提交的冻结研究。
        context = agent_state(self.repo, job, state)
        brief = Brief.model_validate(context["brief"])
        assets = [Asset.model_validate(item) for item in context["assets"]]
        research = context.get("research", {"sources": [], "visuals": []})
        urls = [source["url"] for source in research.get("sources", [])] or list(brief.source_urls)
        _, feedback = active_script_feedback(context)
        if context.get("script") and not feedback:
            return Script.model_validate(context["script"]), research
        if context.get("script") and feedback:
            current = Script.model_validate(context["script"])
            reviewed = feedback.get("script")
            if type(reviewed) is dict and not same_script_body(current, reviewed):
                return current, research
            model_context = {**context, "script": reviewed} if type(reviewed) is dict else context
            value = self.model.invoke(
                model_context, "screenwriter", REWRITE_PROMPT,
                fields=("brief", "script", "research", "assets", "extras"),
                command_id=(context.get("resume_command_id") or context.get("run_id", "")) + ":script-revise",
                output_schema=ScriptRewrite.model_json_schema(),
            )
            rewrite = ScriptRewrite.model_validate(value)
            script = rewrite.script.model_copy(update={"origin": "model", "revision": job.revision})
            if type(reviewed) is dict and same_script_body(script, reviewed):
                raise ValueError("人工返工未产生文案修改，请补充更明确的修改意见")
            issues = script_issues(self.repo.get_job(job.job_id).model_copy(update={"script": script}))
            if issues:
                raise ValueError("人工返工改稿未通过来源检查：" + "；".join(issues))
            return script, research
        if brief.script_text.strip():
            chunks = [item.strip() for item in re.split(r"\n+", brief.script_text) if item.strip()]
            # This splits narrative paragraphs, never estimates speech timing.
            if len(chunks) == 1 and len(chunks[0]) > 72:
                chunks = [item.strip() for item in re.findall(r"[^。！？.!?]+[。！？.!?]?", chunks[0]) if item.strip()]
            available_urls = list(dict.fromkeys(urls + [asset.source_url for asset in assets if asset.source_url]))
            script = Script(title=(brief.topic or "用户提供文案")[:300], origin="user", revision=job.revision,
                            segments=[ScriptSegment(segment_id=f"s{index + 1}", narration=text, screen_text=text[:100],
                                                    source_refs=available_urls, asset_ids=[]) for index, text in enumerate(chunks)])
        else:
            if not research.get("sources"):
                raise CapabilityMissing("没有取得可读取的原始来源，请补充真实链接/证据素材", ["source_urls", "assets"])
            schema = Script.model_json_schema()
            value = self.model.invoke(
                context, "screenwriter", PROMPT, fields=("brief", "research", "assets"),
                output_schema=schema,
            )
            value.update(origin="model", revision=job.revision)
            script = Script.model_validate(value)
        return script, research

def script_issues(job: Job) -> list[str]:
    if not job.script:
        return ["没有有效短视频文案"]
    known_assets = {asset.asset_id: asset for asset in job.assets}
    known_sources = set(job.brief.source_urls) | {asset.source_url for asset in job.assets if asset.source_url}
    issues = []
    for segment in job.script.segments:
        # 旧任务曾用可朗读的观点标签表示纯主观段落，保留旧稿读取/校验兼容。
        # 新提示词不再要求这些标签；自然收束同样使用 source_refs 保留依据。
        if not segment.source_refs and not segment.narration.startswith(("观点：", "个人感受：")):
            issues.append(f"段落 {segment.segment_id} 缺少支撑本段内容的真实来源，请补充来源或删除无依据的说法")
        for source in segment.source_refs:
            parsed = urlparse(source)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
                issues.append(f"段落 {segment.segment_id} 来源 URL 无效")
            elif source not in known_sources:
                issues.append(f"段落 {segment.segment_id} 来源不在用户来源或真实素材清单中")
        for asset_id in segment.asset_ids:
            if asset_id not in known_assets:
                issues.append(f"段落 {segment.segment_id} 素材不存在")
    facts = [segment for segment in job.script.segments if segment.source_refs]
    if facts and not any(asset.role == "evidence" and asset.source_url for asset in job.assets):
        issues.append("事实性文案需要带原始出处的真实证据图片、截图或视频")
    return issues
