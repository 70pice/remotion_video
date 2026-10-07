"""Nodes work directly with state, without graph-owned business wrappers."""

import json

import pytest

from videoagents.contracts import Brief, SettingsPatch
from videoagents.nodes.await_input import AwaitInputNode
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.gates import AudioGateNode, ReviewGateNode, ScriptGateNode, TimelineGateNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.reviewers import ReviewersNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.script_reviewer import ScriptReviewerNode
from videoagents.nodes.voice import VoiceNode
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.process_manager import RenderCancelled

NODE_TYPES = [MaterialsNode, ScreenwriterNode, ScriptReviewerNode, VoiceNode, DirectorNode, EditingNode, ReviewersNode,
              ScriptGateNode, AudioGateNode, TimelineGateNode, ReviewGateNode, AwaitInputNode, HumanReviewNode]


def make_node(node_type, repo, service):
    if node_type is AwaitInputNode:
        return node_type(repo, service)
    if node_type in {MaterialsNode, ScreenwriterNode, ScriptReviewerNode, VoiceNode, DirectorNode, EditingNode, ReviewersNode}:
        return node_type(repo, service)
    return node_type(repo)


@pytest.mark.parametrize("node_type", NODE_TYPES, ids=lambda item: item.__name__)
@pytest.mark.parametrize("invalid", ["revision", "cancelled"])
def test_every_node_rejects_invalid_job_before_processing(tmp_path, monkeypatch, node_type, invalid):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：节点版本校验。"))
    if invalid == "cancelled":
        repo.cancel(job.job_id)
    before = repo.get_job(job.job_id)
    node = make_node(node_type, repo, service)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: pytest.fail("Invalid job reached a model"))
    state = VideoState(job_id=job.job_id, revision=job.revision + (invalid == "revision"),
                       action="produce", thread_id="UNIT-direct-node", run_id="UNIT-command")
    with pytest.raises(Conflict if invalid == "revision" else RenderCancelled):
        node(state)
    assert repo.get_job(job.job_id) == before
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 0


def test_screenwriter_node_saves_output_and_routes_without_a_graph(tmp_path):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False))
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：我喜欢这个配色。"))
    state = VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                       thread_id="UNIT-direct-node", run_id="UNIT-command")

    result = ScreenwriterNode(repo, service)(state)
    saved = repo.get_job(job.job_id)
    assert result["route"] == "script_reviewer" and not result["gate_issues"]
    assert saved.stage == "script" and saved.status == "RUNNING"
    assert saved.script.segments[0].narration == job.brief.script_text
    artifact = next(item for item in saved.artifacts if item.kind == "script")
    assert json.loads(repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8")) == saved.script.model_dump()
    reviewer = ScriptReviewerNode(repo, service)
    reviewer.model.call = lambda *args, **kwargs: {
        "decision": "APPROVE", "summary": "UNIT TEST：文案可进入人工审核。", "strengths": [], "issues": [],
    }
    review = reviewer({**state, **result})
    assert review["route"] == "human_review_script" and review["gate_issues"] == []
    assert review["script"] == saved.script.model_dump()
    assert review["brief"] == saved.brief.model_dump()
    assert review["assets"] == [item.model_dump() for item in saved.assets]
