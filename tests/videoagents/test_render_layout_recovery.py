"""Text-fit failures need photography changes, not an unchanged render retry."""

import pytest
from test_director_shot_review import node_state
from test_director_shot_review import shot_subject as shot_subject

from videoagents.nodes.await_input import AwaitInputNode
from videoagents.nodes.director_demo import DirectorDemoNode

STEPS_ERROR = ("Remotion 渲染失败：ProgressSteps production slot 476x220 cannot fit 3 steps at 34px "
               "with at most two lines per step. Increase this slot or split the steps.")
WORDS_ERROR = ("Remotion 渲染失败：WordFlip production slot 200x110 cannot fit its words at 42px "
               "with at most two lines. Increase this slot or split the words.")


@pytest.mark.parametrize("message", [STEPS_ERROR, WORDS_ERROR])
def test_render_text_fit_failure_requests_timeline_repair(shot_subject, monkeypatch, message):
    repo, service, job, _, _ = shot_subject

    def fail(*args, **kwargs):
        raise ValueError(message)

    monkeypatch.setattr(DirectorDemoNode, "render_shots", fail)
    result = DirectorDemoNode(repo, service)(node_state(repo, job))
    pending = repo.get_job(job.job_id).pending_input
    assert result["route"] == "await_input"
    assert pending["fields"] == ["timeline", "render"]
    assert "retry_node" not in pending
    assert pending["issues"] == [message]
    assert repo.get_job(job.job_id).timeline == job.timeline
    assert not any(item.kind in {"stage_review", "final"} for item in repo.get_job(job.job_id).artifacts)


@pytest.mark.parametrize("message, expected_route", [
    (STEPS_ERROR, "director"), (WORDS_ERROR, "director"),
    ("Remotion 渲染失败：ProgressSteps production slot 98x100 cannot fit the step marker and readable labels. Increase this slot.", "director"),
    ("渲染超过配置时间上限", "director_demo"),
    ("Node.js 未安装", "director_demo"),
    ("逐镜审核渲染结果没有完整覆盖当前镜头", "director_demo"),
    ("Remotion 渲染失败：net::ERR_FILE_NOT_FOUND", "director_demo"),
    ("Some unrelated cannot fit error", "director_demo"),
])
def test_legacy_render_pause_routes_only_known_layout_failures(shot_subject, monkeypatch, message, expected_route):
    repo, service, job, _, _ = shot_subject
    pending = {"kind": "input", "stage": "director", "revision": job.revision,
               "issues": [message], "fields": ["render"], "retry_node": "director_demo",
               "thread_id": "UNIT-layout", "pending_token": "UNIT-layout-token"}
    repo.update_job(job.job_id, status="NEEDS_INPUT", stage="director", pending_input=pending)
    answer = {"decision": "confirm", "pending_token": pending["pending_token"], "note": "UNIT increase available space"}
    monkeypatch.setattr("videoagents.nodes.await_input.interrupt", lambda value: answer)
    state = node_state(repo, repo.get_job(job.job_id))
    state.update(pending_snapshot=pending, gate_issues=[])
    result = AwaitInputNode(repo, service)(state)
    assert result["route"] == expected_route
    assert result["human_decision"]["note"] == answer["note"]
    if expected_route == "director":
        assert result["gate_issues"] == [message]
    assert repo.get_job(job.job_id).timeline == job.timeline
    assert not any(item.kind in {"stage_review", "final"} for item in repo.get_job(job.job_id).artifacts)


@pytest.mark.parametrize("decision", ["revise", "cancel"])
def test_layout_failure_does_not_override_nonconfirmation(shot_subject, monkeypatch, decision):
    repo, service, job, _, _ = shot_subject
    pending = {"kind": "input", "stage": "director", "revision": job.revision,
               "issues": [STEPS_ERROR], "fields": ["render"], "retry_node": "director_demo",
               "thread_id": "UNIT-layout", "pending_token": "UNIT-layout-token"}
    repo.update_job(job.job_id, status="NEEDS_INPUT", stage="director", pending_input=pending)
    state = node_state(repo, repo.get_job(job.job_id))
    state["pending_snapshot"] = pending
    monkeypatch.setattr("videoagents.nodes.await_input.interrupt", lambda value: {"decision": decision})
    assert AwaitInputNode(repo, service)(state)["route"] == "end"
    assert repo.get_job(job.job_id).status == ("DRAFT" if decision == "revise" else "CANCELLED")


@pytest.mark.parametrize("change", ["different_stage", "different_fields", "provider_unknown", "mixed_issues"])
def test_legacy_recovery_is_limited_to_render_layout_inputs(shot_subject, monkeypatch, change):
    repo, service, job, _, _ = shot_subject
    pending = {"kind": "input", "stage": "director", "revision": job.revision,
               "issues": [STEPS_ERROR], "fields": ["render"], "retry_node": "director_demo",
               "thread_id": "UNIT-layout", "pending_token": "UNIT-layout-token"}
    if change == "different_stage":
        pending["stage"] = "voice"
    elif change == "different_fields":
        pending["fields"] = ["assets"]
    elif change == "provider_unknown":
        pending["operation_status"] = "UNKNOWN"
    else:
        pending["issues"].append("另一个素材无法读取")
    repo.update_job(job.job_id, status="NEEDS_INPUT", stage="director", pending_input=pending)
    state = node_state(repo, repo.get_job(job.job_id))
    state["pending_snapshot"] = pending
    monkeypatch.setattr("videoagents.nodes.await_input.interrupt", lambda value: {"decision": "confirm"})
    assert AwaitInputNode(repo, service)(state)["route"] == "director_demo"
