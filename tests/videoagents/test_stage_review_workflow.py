"""Exercise default interrupt/resume wiring without paid models or real renders."""

from collections import Counter
from copy import deepcopy

import pytest
from langgraph.types import Command

from videoagents.contracts import (
    Brief,
    Script,
    ScriptCritique,
    ScriptDiscussion,
    ScriptDiscussionRound,
    ScriptSegment,
    SettingsPatch,
    Shot,
    Timeline,
)
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import state_context
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.gates import AudioGateNode, ScriptGateNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.script_reviewer import ScriptReviewerNode
from videoagents.nodes.voice import VoiceNode
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState, merge_extras
from videoagents.storage import Repository


@pytest.fixture
def staged_pipeline(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    project = tmp_path / "project"
    service = JobService(repo, project)
    job = repo.create_job(Brief(topic="UNIT：阶段审核编排"))
    calls = Counter()
    feedback_seen = []

    def stub(name, route, stage):
        def invoke(node, state):
            calls[name] += 1
            current = repo.get_job(state["job_id"])
            changes = {"stage": stage, "status": "RUNNING"}
            feedback = state.get("extras", {}).get("human_feedback", {})
            render_feedback = feedback.get("render", {})
            render_script_revision = (
                render_feedback.get("applied") is False
                and any(value in render_feedback.get("note", "") for value in ("改旁白文案", "重写文案", "防御性文案"))
            )
            if name in {"screenwriter", "director"}:
                target = "script" if name == "screenwriter" else "director"
                if name == "screenwriter" and render_script_revision:
                    target = "render"
                elif name == "director" and feedback.get("render", {}).get("applied") is False:
                    target = "render"
                entry = feedback.get(target)
                routed_to_writer = name == "director" and target == "render" and render_script_revision
                if entry and entry.get("decision") == "revise" and not entry.get("applied") and not routed_to_writer:
                    feedback_seen.append((name, target, entry["note"]))
                    feedback = {**feedback, target: {**entry, "applied": True}}
                    state["extras"] = merge_extras(state.get("extras", {}), {"human_feedback": feedback})
            if name == "screenwriter":
                changes["script"] = Script(title="UNIT 文案", origin="model", revision=current.revision,
                    segments=[ScriptSegment(segment_id="s1", narration=f"UNIT 第 {calls[name]} 稿。",
                                             screen_text="UNIT 文案", source_refs=[], asset_ids=[])])
            if name == "director":
                changes["timeline"] = Timeline(job_id=current.job_id, revision=current.revision,
                    width=1080, height=1920, fps=30, duration_in_frames=30,
                    shots=[Shot(shot_id="shot-1", start_frame=0, end_frame=30, component_id="keyword",
                                title=f"UNIT 第 {calls[name]} 版分镜")])
            if name == "editing":
                changes["status"] = "DRAFT"
                changes["progress"] = 1
            current = repo.update_job(current.job_id, current.revision, **changes)
            if name == "editing":
                # JSON bytes explicitly represent a fake render receipt, never a playable video.
                service.write_json(current, f"unit-render-{calls[name]}.json",
                                   {"unit_render": calls[name]}, "final")
            next_route = "screenwriter" if name == "director" and render_script_revision else route
            return state_context(repo, state, route=next_route)
        return invoke

    for cls, name, route, stage in (
        (MaterialsNode, "materials", "screenwriter", "materials"),
        (ScreenwriterNode, "screenwriter", "script_reviewer", "script"),
        (ScriptReviewerNode, "script_reviewer", "human_review_script", "script"),
        (ScriptGateNode, "script_gate", "voice", "script"),
        (VoiceNode, "voice", "audio_gate", "voice"),
        (AudioGateNode, "audio_gate", "director", "voice"),
        (DirectorNode, "director", "editing", "director"),
        (EditingNode, "editing", "end", "render"),
    ):
        monkeypatch.setattr(cls, "__call__", stub(name, route, stage))
    return repo, project, job, calls, feedback_seen


def run_or_resume(pipeline, decision=None, note="UNIT：已核对当前阶段内容，确认继续。"):
    repo, project, job, _, _ = pipeline
    config = {"configurable": {"thread_id": "UNIT-stage-pipeline"}, "recursion_limit": 200}
    with VideoProductionGraph(repo, project) as graph:
        if decision:
            checkpoint = graph.graph.get_state(config)
            paused = checkpoint.interrupts[0]
            value = Command(resume={paused.id: {"decision": decision, "note": note,
                                                "pending_token": paused.value["pending_token"]}})
        else:
            value = VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                               run_id="UNIT-stage-pipeline", thread_id="UNIT-stage-pipeline")
        graph.graph.invoke(value, config)
        checkpoint = graph.graph.get_state(config)
    return repo.get_job(job.job_id), checkpoint


def test_default_flow_requires_only_script_approval_before_rendering(staged_pipeline):
    _, _, _, calls, _ = staged_pipeline
    current, checkpoint = run_or_resume(staged_pipeline)
    assert current.pending_input["node_name"] == "human_review_script"
    assert checkpoint.interrupts and calls["voice"] == calls["director"] == calls["editing"] == 0

    current, checkpoint = run_or_resume(staged_pipeline, "confirm")
    assert not checkpoint.interrupts
    assert calls["voice"] == calls["director"] == calls["editing"] == 1
    assert len(checkpoint.values["human_reviews"]) == 1
    assert current.status == "DRAFT" and current.stage == "render" and current.progress == 1
    assert current.review is None


def test_script_revise_returns_to_writer_and_requires_a_fresh_approval(staged_pipeline):
    _, _, _, calls, feedback_seen = staged_pipeline
    current, _ = run_or_resume(staged_pipeline)
    token = current.pending_input["pending_token"]
    before = calls.copy()
    note = "UNIT：请根据 script 当前内容修改画面或表达，重新审核。"
    current, checkpoint = run_or_resume(staged_pipeline, "revise", note)
    assert current.pending_input["node_name"] == "human_review_script" and checkpoint.interrupts
    assert current.pending_input["pending_token"] != token
    assert calls["screenwriter"] == before["screenwriter"] + 1
    assert feedback_seen[-1] == ("screenwriter", "script", note)
    assert calls["voice"] == before["voice"] and calls["editing"] == before["editing"]
    assert current.status == "NEEDS_HUMAN"


@pytest.mark.parametrize("prior_rounds", [1, 2, 5])
def test_discussion_rewrite_sql_before_feedback_receipt_replays_without_second_model_call(tmp_path, monkeypatch, prior_rounds):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT：讨论返工恢复"))
    original = Script(title="UNIT", origin="user", revision=job.revision,
                      segments=[ScriptSegment(segment_id="s1", narration="观点：UNIT 旧稿。")])
    discussion = ScriptDiscussion(run_id="UNIT-discussion-replay", revision=job.revision,
        enabled=True, max_rounds=max(2, prior_rounds), status="APPROVED",
        rounds=[ScriptDiscussionRound(round=index + 1, script=original,
                                      critique=ScriptCritique(decision="APPROVE", summary="UNIT 机器已审旧稿。"))
                for index in range(prior_rounds)])
    repo.update_job(job.job_id, job.revision, script=original, script_discussion=discussion)
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {"enabled": True}}))
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision,
        run_id=discussion.run_id, thread_id="UNIT-discussion-replay", action="produce",
        extras={"human_feedback": {"script": {"decision": "revise", "stage": "script",
            "note": "UNIT：请改写当前稿件，之后重新进行文案审核。", "pending_token": "UNIT-new-feedback",
            "applied": False, "script": original.model_dump()}}}))
    checkpoint_before_node = deepcopy(state)
    calls = []

    def model(*args, **kwargs):
        calls.append(1)
        rewritten = original.model_dump()
        rewritten["segments"][0]["narration"] = "观点：UNIT 已实际改写的稿件。"
        return {"script": rewritten, "response": "UNIT：已修改稿件，等待复审。"}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model)
    from videoagents.nodes import screenwriter

    save_receipt = screenwriter.mark_feedback_applied

    def crash_before_receipt(*args, **kwargs):
        raise SystemExit("UNIT：模拟新稿已提交，反馈消费回执未提交")

    monkeypatch.setattr(screenwriter, "mark_feedback_applied", crash_before_receipt)
    with pytest.raises(SystemExit):
        ScreenwriterNode(repo, service)(state)
    saved = repo.get_job(job.job_id).script_discussion
    assert saved.status == "DISCUSSING"
    assert saved.max_rounds == discussion.max_rounds
    assert len(saved.rounds) == 1 and saved.rounds[0].critique is None
    assert saved.rounds[0].round == 1

    monkeypatch.setattr(screenwriter, "mark_feedback_applied", save_receipt)
    result = ScreenwriterNode(repo, service)(checkpoint_before_node)
    assert calls == [1]
    assert len(repo.get_job(job.job_id).script_discussion.rounds) == 1
    assert result["route"] == "script_reviewer"
    assert result["extras"]["human_feedback"]["script"]["applied"] is True
