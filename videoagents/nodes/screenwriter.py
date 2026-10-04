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
    request_input,
    save_discussion,
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
            script, research = self.write_script(job, state)
            job = self.repo.update_job(job.job_id, job.revision, script=script, script_discussion=None)
            self.service.write_json(job, "script.json", script.model_dump(), "script")
            return state_context(self.repo, state, route="script_gate",
                                 research=research, gate_issues=[])
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "script", [str(exc)], getattr(exc, "fields", ["script"]), exc)

    def discuss(self, state: VideoState, job: Job, discussion: ScriptDiscussion) -> dict[str, Any]:
        research = state.get("research", {})
        # A saved unreviewed draft or terminal discussion is reused on replay.
        if not discussion.rounds or (discussion.status == "DISCUSSING" and discussion.rounds[-1].critique):
            if not discussion.rounds:
                script, research = self.write_script(job, state)
                response = ""
            else:
                script, response = self.rewrite(job, discussion, state)
            discussion.rounds.append(ScriptDiscussionRound(round=len(discussion.rounds) + 1,
                                                           script=script, response=response))
            job = save_discussion(self.repo, state, discussion)
        else:
            job = self.repo.get_job(job.job_id)
        return state_context(self.repo, state, route="script_reviewer", research=research, gate_issues=[])

    def rewrite(self, job: Job, discussion: ScriptDiscussion,
                state: VideoState | None = None) -> tuple[Script, str]:
        # This path intentionally bypasses write_script's existing-draft cache.
        context = agent_state(self.repo, job, state)
        context["script_discussion"] = discussion.model_dump()
        value = self.model.invoke(
            context, "screenwriter", REWRITE_PROMPT,
            fields=("brief", "script", "script_discussion", "research", "assets"),
            output_schema=ScriptRewrite.model_json_schema(),
        )
        rewrite = ScriptRewrite.model_validate(value)
        script = rewrite.script.model_copy(update={"origin": "model", "revision": job.revision})
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
        if context.get("script"):
            return Script.model_validate(context["script"]), research
        if brief.script_text.strip():
            chunks = [item.strip() for item in re.split(r"\n+", brief.script_text) if item.strip()]
            # This splits narrative paragraphs, never estimates speech timing.
            if len(chunks) == 1 and len(chunks[0]) > 72:
                chunks = [item.strip() for item in re.findall(r"[^。！？.!?]+[。！？.!?]?", chunks[0]) if item.strip()]
            evidence = [asset.asset_id for asset in assets if asset.role == "evidence"]
            available_urls = list(dict.fromkeys(urls + [asset.source_url for asset in assets if asset.source_url]))
            script = Script(title=(brief.topic or "用户提供文案")[:300], origin="user", revision=job.revision,
                            segments=[ScriptSegment(segment_id=f"s{index + 1}", narration=text, screen_text=text[:100],
                                                    source_refs=available_urls, asset_ids=evidence[:1]) for index, text in enumerate(chunks)])
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
        if not segment.source_refs and not segment.narration.startswith(("观点：", "个人感受：")):
            issues.append(f"段落 {segment.segment_id} 缺少事实来源；纯观点请明确标注“观点：”")
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
        issues.append("事实性文案需要至少一张带原始出处的真实证据图片/截图")
    return issues
