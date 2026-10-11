from types import SimpleNamespace

import pytest
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from videoagents.contracts import Brief
from videoagents.graph import VideoProductionGraph
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository


def test_retry_resumes_failed_node_and_stops_at_new_human_gate(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT failed director retry"))
    thread = f"job:{job.job_id}:run:unit-first"
    config = {"configurable": {"thread_id": thread}}
    calls = {"start": 0, "director": 0, "editing": 0}

    def start(state):
        calls["start"] += 1
        return {}

    def director(state):
        calls["director"] += 1
        if calls["director"] == 1:
            raise Conflict("UNIT exhausted model budget")
        assert state["resume_command_id"] == "unit-retry"
        return {}

    def gate(state):
        pending = {"kind": "stage_review", "stage": "director", "node_name": "director_human_gate",
                   "thread_id": thread, "pending_token": "UNIT-new-demo"}
        repo.update_job(job.job_id, status="NEEDS_HUMAN", stage="director", pending_input=pending)
        interrupt(pending)
        return {}

    def editing(state):
        calls["editing"] += 1
        pytest.fail("retry must not approve the demo")

    with VideoProductionGraph(repo, tmp_path / "project") as production:
        flow = StateGraph(VideoState)
        for name, node in (("start", start), ("director", director), ("gate", gate), ("editing", editing)):
            flow.add_node(name, node)
        flow.add_edge(START, "start")
        flow.add_edge("start", "director")
        flow.add_edge("director", "gate")
        flow.add_edge("gate", "editing")
        flow.add_edge("editing", END)
        production.graph = flow.compile(checkpointer=production.checkpointer)
        inputs = {name: job.model_dump().get(name) for name in ("brief", "script", "assets", "director_requirements")}
        with pytest.raises(Conflict, match="budget"):
            production.graph.invoke(VideoState(job_id=job.job_id, revision=job.revision, thread_id=thread, **inputs), config)
        assert production.graph.get_state(config).next == ("director",)
        command = {"command_id": "unit-retry", "job_id": job.job_id,
                   "payload": {"action": "retry", "base_revision": job.revision, "continuation_thread_id": thread}}
        production.execute(command)
        assert calls == {"start": 1, "director": 2, "editing": 0}
        assert repo.get_job(job.job_id).status == "NEEDS_HUMAN"
        assert repo.get_job(job.job_id).pending_input["pending_token"] == "UNIT-new-demo"
        # Reclaiming the same retry command must retain the question unanswered.
        production.execute(command)
        assert calls == {"start": 1, "director": 2, "editing": 0}


@pytest.mark.parametrize("invalid", ["owner", "revision", "inputs", "missing", "finished"])
def test_retry_rejects_unbound_or_changed_checkpoint(tmp_path, monkeypatch, invalid):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT retry binding"))
    thread = f"job:{job.job_id}:run:first"
    state = {name: job.model_dump().get(name) for name in ("brief", "script", "assets", "director_requirements")}
    state.update(job_id=job.job_id, revision=job.revision)
    if invalid == "owner":
        thread = "job:another:run:first"
    elif invalid == "revision":
        state["revision"] += 1
    elif invalid == "inputs":
        state["brief"] = {**state["brief"], "topic": "changed"}
    elif invalid == "missing":
        state = {}
    snapshot = SimpleNamespace(values=state, next=() if invalid == "finished" else ("director",), interrupts=())
    with VideoProductionGraph(repo, tmp_path / "project") as production:
        monkeypatch.setattr(production.graph, "get_state", lambda config: snapshot)
        monkeypatch.setattr(production.graph, "invoke", lambda *args: pytest.fail("invalid checkpoint invoked"))
        with pytest.raises(Conflict):
            production.execute({"command_id": "retry", "job_id": job.job_id,
                                "payload": {"action": "retry", "base_revision": job.revision,
                                            "continuation_thread_id": thread}})
