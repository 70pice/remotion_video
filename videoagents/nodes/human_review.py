"""Composable stage approval. It never grants final publication approval."""

import json
import re
from typing import Any

from langgraph.types import interrupt

from videoagents.contracts import Artifact, Job
from videoagents.nodes.common import current_job, state_context
from videoagents.state import VideoState
from videoagents.storage import Conflict, NotFound, Repository
from videoagents.storage.repository import dumps, fingerprint
from videoagents.tools.media import sha256


class HumanReviewNode:
    """Return routes ``continue``, ``revise``, ``retry`` or ``end``.

    ``confirm`` continues, ``revise`` either returns to the caller-provided
    model node or keeps the legacy standalone behavior, and ``cancel``
    terminates the job. Register a self-edge for ``retry`` so invalid answers
    produce a new interrupt without replaying a loop inside this node.
    """

    def __init__(self, repository: Repository, *, node_name: str = "human_review", stage: str = "script",
                 title: str = "人工审核", confirmation_requirements: tuple[str, ...] = ("核对本阶段产物",),
                 min_note_length: int = 10, finish_on_confirm: bool = False, revise_route: str | None = None):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", node_name):
            raise ValueError("人工审核节点名称只能包含字母、数字、下划线和连字符")
        if stage not in {"materials", "script", "voice", "director", "render", "review"}:
            raise ValueError("人工审核需指定现有制作阶段")
        if not title.strip() or len(title) > 200:
            raise ValueError("人工审核标题需为 1–200 字符")
        if not 1 <= len(confirmation_requirements) <= 30 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 500 for item in confirmation_requirements
        ):
            raise ValueError("人工审核需提供 1–30 项非空检查事项，每项最多 500 字符")
        if type(min_note_length) is not int or not 0 <= min_note_length <= 3000:
            raise ValueError("审核说明最小长度需为 0–3000 的整数")
        self.repo = repository
        self.node_name, self.stage, self.title = node_name, stage, title.strip()
        self.requirements = tuple(item.strip() for item in confirmation_requirements)
        if revise_route is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", revise_route):
            raise ValueError("返工路由节点名称只能包含字母、数字、下划线和连字符")
        self.min_note_length = min_note_length
        self.finish_on_confirm = finish_on_confirm
        self.revise_route = revise_route

    def _job(self, state: VideoState) -> Job:
        return current_job(self.repo, state)

    def _inputs(self, job: Job) -> str:
        artifacts = [item for item in job.artifacts if item.kind != "stage_review"]
        # Bind actual bytes and imported/generated timing metadata, not only
        # declared hashes. Approval must not survive media changes in-place.
        media = {item.artifact_id: item.sha256 for item in artifacts}
        media.update({item.artifact_id: item.sha256 for item in job.assets})
        for artifact_id, expected in media.items():
            try:
                path, _, _ = self.repo.artifact_path(artifact_id)
                if sha256(path) != expected:
                    raise Conflict("待审素材或产物文件已改变，请重新生成并审核")
            except (NotFound, OSError) as exc:
                raise Conflict("待审素材或产物文件缺失，请重新生成并审核") from exc
        return fingerprint({
            "job": job.model_dump(include={"revision", "brief", "script", "timeline", "assets", "review"}),
            "artifacts": [item.model_dump() for item in artifacts],
            "asset_metadata": {item.asset_id: self.repo.asset_metadata(item.asset_id) for item in job.assets},
        })

    def _pending(self, state: VideoState, job: Job) -> dict[str, Any]:
        inputs = self._inputs(job)
        policy_payload = {"node_name": self.node_name, "stage": self.stage, "title": self.title,
                          "requirements": self.requirements, "min_note_length": self.min_note_length,
                          "finish_on_confirm": self.finish_on_confirm}
        if self.revise_route is not None:
            policy_payload["revise_route"] = self.revise_route
        policy = fingerprint(policy_payload)
        previous = state.get("stage_review_pending")
        if previous and previous.get("node_name") == self.node_name:
            if previous["dependency_fingerprint"] != inputs or previous["policy_fingerprint"] != policy:
                raise Conflict("人工审核的内容或检查要求已改变，请重新发起制作")
            return previous
        identity = {"thread_id": state["thread_id"], "revision": job.revision, "node_name": self.node_name,
                    "round": state.get("human_review_rounds", {}).get(self.node_name, 0),
                    "inputs": inputs, "policy": policy}
        return {"kind": "stage_review", "stage": self.stage, "node_name": self.node_name, "title": self.title,
                "thread_id": state["thread_id"], "revision": job.revision, "pending_token": fingerprint(identity)[:32],
                "dependency_fingerprint": inputs, "policy_fingerprint": policy,
                "confirmation_requirements": list(self.requirements), "min_note_length": self.min_note_length}

    def _subject_snapshot(self, job: Job) -> dict[str, Any]:
        if self.stage == "script":
            return {"script": job.script.model_dump() if job.script else None}
        if self.stage == "director":
            return {"timeline": job.timeline.model_dump() if job.timeline else None}
        if self.stage == "render":
            return {"script": job.script.model_dump() if job.script else None,
                    "timeline": job.timeline.model_dump() if job.timeline else None,
                    "render_artifacts": [item.model_dump() for item in job.artifacts
                                          if item.kind in {"preview", "final", "cover", "captions"}]}
        return {}

    def _record(self, job: Job, receipt: dict[str, Any], status: str, message: str) -> None:
        # Deterministic file + artifact ID make SQL-before-checkpoint replay
        # idempotent, including a crash between artifact registration and save.
        token = receipt["pending_token"]
        folder = self.repo.root / "jobs" / job.job_id / "revisions" / str(job.revision)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"stage-review-{self.node_name}-{token}.json"
        encoded = dumps(receipt)
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != receipt:
                raise Conflict("此人工审核待办已经记录了不同的决定")
        else:
            temporary = path.with_suffix(".pending")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(path)
        artifact_id = fingerprint({"job_id": job.job_id, "pending_token": token})[:32]
        artifact = Artifact(artifact_id=artifact_id, kind="stage_review", name=path.name,
                            mime_type="application/json", size_bytes=path.stat().st_size, sha256=sha256(path),
                            url=f"/api/artifacts/{artifact_id}", revision=job.revision)
        try:
            _, existing, _ = self.repo.artifact_path(artifact_id)
            if existing != artifact:
                raise Conflict("人工审核记录与已持久化产物不一致")
        except NotFound:
            self.repo.put_artifact(job.job_id, artifact, path)
        artifacts = [item for item in job.artifacts if item.artifact_id != artifact_id] + [artifact]
        self.repo.update_job(job.job_id, job.revision, status=status, stage=self.stage, message=message,
                             pending_input=None, artifacts=artifacts)

    def __call__(self, state: VideoState) -> dict[str, Any]:
        job = self._job(state)
        pending = self._pending(state, job)
        if job.pending_input != pending or job.status != "NEEDS_HUMAN":
            self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", stage=self.stage,
                                 message=self.title + "：等待人工核对", pending_input=pending)
        answer = interrupt(pending)
        job = self._job(state)
        if self._inputs(job) != pending["dependency_fingerprint"]:
            raise Conflict("人工审核的内容已改变，请重新发起制作")
        if not isinstance(answer, dict) or answer.get("pending_token") != pending["pending_token"]:
            raise Conflict("人工审核回复绑定的待办已失效")
        decision, note = answer.get("decision"), answer.get("note", "")
        if decision not in {"confirm", "revise", "cancel"} or not isinstance(note, str) or len(note) > 3000:
            raise Conflict("人工审核决定或说明无效")
        note = note.strip()
        if decision in {"confirm", "revise"} and len(note) < self.min_note_length:
            pending = dict(pending, pending_token=fingerprint({"previous": pending["pending_token"],
                           "purpose": "stage_review_note"})[:32], issues=[f"审核说明至少填写 {self.min_note_length} 个字符"])
            job = self.repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", pending_input=pending,
                                       message=pending["issues"][0])
            return state_context(self.repo, state, route="retry", stage_review_pending=pending)
        receipt = dict(pending, decision=decision, note=note)
        artifact_id = fingerprint({"job_id": job.job_id, "pending_token": pending["pending_token"]})[:32]
        feedback = {self.stage: {"stage": self.stage, "node_name": self.node_name,
                                 "pending_token": pending["pending_token"],
                                 "decision": decision, "note": note, "target": self.revise_route,
                                 "artifact_id": artifact_id, "applied": False,
                                 **self._subject_snapshot(job)}} if decision == "revise" else {}
        if decision == "confirm":
            status = "DRAFT" if self.finish_on_confirm else "RUNNING"
            message = self.title + ("已确认，本次执行结束" if self.finish_on_confirm else "已确认，继续工作流")
            route = "continue"
        elif decision == "revise" and self.revise_route:
            status, message, route = "RUNNING", self.title + "要求返工，已返回对应模型节点", "revise"
        elif decision == "revise":
            status, message, route = "DRAFT", "人工审核要求返工，请修改对应产物并提交新版本", "end"
        else:
            status, message, route = "CANCELLED", "人工审核已取消任务", "end"
        # Persist the complete revision instruction as part of the immutable
        # review receipt.  The checkpoint still carries the same payload for
        # the normal in-run route, while the durable copy lets a versioned
        # draft recover an unapplied instruction after an UNKNOWN operation
        # makes the old graph execution unsafe to resume.
        recorded_receipt = dict(receipt, feedback=feedback[self.stage]) if feedback else receipt
        self._record(job, recorded_receipt, status, message)
        rounds = dict(state.get("human_review_rounds", {}))
        rounds[self.node_name] = rounds.get(self.node_name, 0) + 1
        overrides = {"human_decision": receipt, "stage_review_pending": None, "human_review_rounds": rounds}
        if feedback:
            overrides["extras"] = {"human_feedback": feedback}
        return state_context(self.repo, state, route=route, **overrides)
