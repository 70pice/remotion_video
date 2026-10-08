from types import SimpleNamespace

import pytest

from videoagents.contracts import Brief
from videoagents.graph import VideoProductionGraph
from videoagents.storage import Conflict, Repository


@pytest.fixture
def failed_run(tmp_path):
    repo = Repository(tmp_path / "runtime")
    project = tmp_path / "project"
    job = repo.create_job(Brief(topic="UNIT：失败制作恢复"))
    job = repo.update_job(job.job_id, job.revision, status="FAILED", message="unit failed")
    command = {
        "command_id": "UNIT-recovery-command",
        "job_id": job.job_id,
        "payload": {
            "base_revision": job.revision,
            "action": "produce",
            "idempotency_key": "UNIT-recovery-command",
            "failed_run_thread_id": "UNIT-failed-thread",
        },
    }
    return repo, project, job, command


def snapshot(job, *, action="produce", next_nodes=("editing",), interrupts=()):
    return SimpleNamespace(
        values={"job_id": job.job_id, "revision": job.revision, "action": action, "route": "editing"},
        next=next_nodes,
        interrupts=interrupts,
    )


def test_failed_production_recovery_invokes_saved_next_node(failed_run, monkeypatch):
    repo, project, job, command = failed_run
    seen = {}

    with VideoProductionGraph(repo, project) as graph:
        saved = snapshot(job)
        monkeypatch.setattr(graph.graph, "get_state", lambda config: saved)

        def invoke(value, config):
            seen["value"] = value
            seen["config"] = config
            repo.update_job(job.job_id, job.revision, stage="render", status="DRAFT")
            return {**saved.values, "stage": "render", "route": "end"}

        monkeypatch.setattr(graph.graph, "invoke", invoke)
        result = graph.execute(command)

    assert seen["value"] is None
    assert seen["config"]["configurable"]["thread_id"] == "UNIT-failed-thread"
    assert result["stage"] == "render"


@pytest.mark.parametrize("saved", [
    SimpleNamespace(values={}, next=("editing",), interrupts=()),
    SimpleNamespace(values={"job_id": "other", "revision": 1, "action": "produce"}, next=("editing",), interrupts=()),
    SimpleNamespace(values=None, next=("editing",), interrupts=()),
], ids=["missing-values", "wrong-job", "none-values"])
def test_failed_production_recovery_rejects_missing_or_mismatched_state(failed_run, monkeypatch, saved):
    repo, project, _, command = failed_run

    with VideoProductionGraph(repo, project) as graph:
        monkeypatch.setattr(graph.graph, "get_state", lambda config: saved)
        monkeypatch.setattr(graph.graph, "invoke", lambda *args, **kwargs: pytest.fail("unsafe checkpoint was invoked"))
        with pytest.raises(Conflict, match="状态缺失|版本已变化"):
            graph.execute(command)


@pytest.mark.parametrize("saved", [
    SimpleNamespace(values=None, next=(), interrupts=()),
    SimpleNamespace(values=None, next=("editing",), interrupts=(SimpleNamespace(value={"kind": "input"}),)),
], ids=["completed", "interrupted"])
def test_failed_production_recovery_rejects_completed_or_interrupted_checkpoint(failed_run, monkeypatch, saved):
    repo, project, job, command = failed_run
    saved.values = {"job_id": job.job_id, "revision": job.revision, "action": "produce", "route": "editing"}

    with VideoProductionGraph(repo, project) as graph:
        monkeypatch.setattr(graph.graph, "get_state", lambda config: saved)
        monkeypatch.setattr(graph.graph, "invoke", lambda *args, **kwargs: pytest.fail("unsafe checkpoint was invoked"))
        with pytest.raises(Conflict, match="检查点"):
            graph.execute(command)


def test_failed_production_recovery_rejects_different_checkpoint_action(failed_run, monkeypatch):
    repo, project, job, command = failed_run

    with VideoProductionGraph(repo, project) as graph:
        monkeypatch.setattr(graph.graph, "get_state", lambda config: snapshot(job, action="final"))
        monkeypatch.setattr(graph.graph, "invoke", lambda *args, **kwargs: pytest.fail("wrong action was invoked"))
        with pytest.raises(Conflict, match="状态缺失|版本已变化"):
            graph.execute(command)
