"""Discuss the current script with its writer before audio or video production."""

from typing import Any

from videoagents.contracts import ScriptCritique
from videoagents.nodes.common import (
    agent_state,
    current_discussion,
    request_input,
    save_discussion,
    start_stage,
    state_context,
)
from videoagents.prompts import compose
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository

# 文案审查 Agent 的固定提示词来自独立 Markdown；讨论历史只包含各轮稿件、
# 回应和最终审查结果。
PROMPT = compose("shared-style", "script-reviewer")


class ScriptReviewerNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.model = JsonModel(repository)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "script", "文案审查正在讨论事实、表达与画面依据")
        discussion = current_discussion(self.repo, state, job)
        if not discussion.enabled:
            return state_context(self.repo, state, route="script_gate")
        try:
            if not discussion.rounds:
                raise ValueError("文案讨论缺少编剧提交的稿件")
            turn = discussion.rounds[-1]
            if turn.critique is None:
                context = agent_state(self.repo, job, state)
                context["script_discussion"] = discussion.model_dump()
                segment_ids = [item.segment_id for item in turn.script.segments]
                schema = ScriptCritique.model_json_schema()
                # 每次调用仅允许当前稿件的段落 ID；空字符串表示全稿问题。
                schema["$defs"]["ScriptCritiqueIssue"]["properties"]["segment_id"]["enum"] = ["", *segment_ids]
                value = self.model.invoke(
                    context, "script_reviewer", PROMPT,
                    fields=("brief", "script", "script_discussion", "research", "assets"),
                    output_schema=schema,
                )
                critique = ScriptCritique.model_validate(value)
                ids = set(segment_ids)
                if any(item.segment_id and item.segment_id not in ids for item in critique.issues):
                    raise ValueError("文案审查引用了不存在的段落 ID")
                turn.critique = critique
                discussion.status = ("APPROVED" if critique.decision == "APPROVE" else
                                     "EXHAUSTED" if len(discussion.rounds) >= discussion.max_rounds else "DISCUSSING")
                job = save_discussion(self.repo, state, discussion)
            else:
                job = self.repo.get_job(job.job_id)
            result = state_context(self.repo, state, gate_issues=[])
            if discussion.status == "APPROVED":
                return {**result, "route": "script_gate"}
            if discussion.status == "EXHAUSTED":
                issues = [f"文案讨论已达到 {discussion.max_rounds} 轮，仍未通过；请修改文案并保存新版本后重新制作。"]
                issues.extend(item.concern for item in turn.critique.issues)
                return {**result, **request_input(self.repo, state, "script", issues, ["script", "script_discussion"])}
            return {**result, "route": "screenwriter"}
        except (CapabilityMissing, ValueError) as exc:
            return request_input(self.repo, state, "script", [str(exc)], getattr(exc, "fields", ["script"]), exc)
