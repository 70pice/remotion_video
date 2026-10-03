"""Discuss the current script with its writer before audio or video production."""

import json
from typing import Any

from videoagents.contracts import ScriptCritique
from videoagents.nodes.common import (
    current_discussion,
    request_input,
    save_discussion,
    start_stage,
    state_context,
)
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository


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
                research = {}
                artifact = next((item for item in reversed(job.artifacts)
                                 if item.kind == "research" and item.revision == job.revision), None)
                if artifact:
                    research = json.loads(self.repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8"))
                segment_ids = [item.segment_id for item in turn.script.segments]
                schema = ScriptCritique.model_json_schema()
                # 每次调用仅允许当前稿件的段落 ID；空字符串表示全稿问题。
                schema["$defs"]["ScriptCritiqueIssue"]["properties"]["segment_id"]["enum"] = ["", *segment_ids]
                value = self.model.call(job.job_id, job.revision, "script_reviewer",
                    "与编剧讨论短视频文案。检查事实与来源、逻辑、开头吸引力、口播清晰度、画面素材对应及用途风险。"
                    "阅读之前的审查和编剧回应，确认问题是否真的解决；不要重复已解决的问题。"
                    "需要修改时返回REVISE及具体段落、问题concern、修改建议suggestion；没有未解决问题才APPROVE。"
                    "每条 issues[].segment_id 只能逐字使用 draft.segments 中的一个 segment_id；全稿问题使用空字符串。"
                    "不得使用范围（如 s1–s8）、组合 ID 或新 ID；多个段落的具体问题分别列出，整体问题使用空字符串。"
                    "只能核验给定来源快照与素材信息，不得虚构证据或声称已看图、已听音频、视频已具备发布资格。",
                    {"brief": job.brief.model_dump(), "draft": turn.script.model_dump(), "writer_response": turn.response,
                     "history": [item.model_dump() for item in discussion.rounds[:-1]], "research": research,
                     "assets": [item.model_dump() for item in job.assets if item.role != "audio"]},
                    output_schema=schema)
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
