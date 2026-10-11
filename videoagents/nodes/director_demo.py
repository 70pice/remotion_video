"""Render the director-selected demo before entering the human review gate."""

from typing import Any

from videoagents.nodes.common import request_input, start_stage, state_context
from videoagents.nodes.director_review import current_demo_artifact, current_plan_artifact
from videoagents.nodes.editing import EditingNode
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository


class DirectorDemoNode:
    def __init__(self, repository: Repository, service: JobService):
        self.repo, self.service = repository, service
        self.renderer = EditingNode(repository, service)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = start_stage(self.repo, state, "director", "导演正在渲染最长30秒的Demo")
        try:
            current_plan_artifact(self.repo, job)
        except ValueError as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["director_plan"], exc)
        try:
            try:
                current_demo_artifact(self.repo, job)
            except ValueError:
                self.renderer.render_video(job, "preview", state=state)
            current_demo_artifact(self.repo, self.repo.get_job(job.job_id))
        except (CapabilityMissing, ValueError, TimeoutError) as exc:
            return request_input(self.repo, state, "director", [str(exc)], ["render"], exc,
                                 retry_node="director_demo")
        if state.get("action") in {"preview", "component_demo"}:
            message = ("组件套样片已生成，等待人工品鉴反馈"
                       if state.get("action") == "component_demo"
                       else "导演Demo已生成，本次预览执行结束")
            self.repo.update_job(job.job_id, job.revision, status="DRAFT", stage="director",
                                 message=message, progress=1)
            return state_context(self.repo, state, route="end")
        self.repo.update_job(job.job_id, job.revision, status="RUNNING", stage="director",
                             message="导演方案和Demo已就绪，准备人工审核", progress=1)
        return state_context(self.repo, state, route="director_human_gate")
