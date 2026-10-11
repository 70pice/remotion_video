import pytest

from videoagents.contracts import Brief, Caption, Shot, Timeline
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import state_context
from videoagents.nodes.director_demo import DirectorDemoNode
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository


def test_component_demo_command_starts_at_component_demo_and_never_enters_editing(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="组件套样片路径"))
    seen = {"component_demo": [], "director_demo": 0}

    class FakeComponentDemoNode:
        def __init__(self, repository, service):
            self.repo = repository

        def __call__(self, state):
            seen["component_demo"].append(state["extras"]["component_demo"])
            return state_context(self.repo, state, route="director_demo")

    monkeypatch.setattr("videoagents.graph.video_graph.ComponentDemoNode", FakeComponentDemoNode)
    monkeypatch.setattr(MaterialsNode, "__call__", lambda *args, **kwargs: pytest.fail("component demo entered materials"))
    monkeypatch.setattr(EditingNode, "__call__", lambda *args, **kwargs: pytest.fail("component demo entered editing"))

    def finish_demo(node, state):
        seen["director_demo"] += 1
        assert state["action"] == "component_demo"
        repo.update_job(state["job_id"], state["revision"], status="DRAFT", stage="director", message="组件套样片已生成，等待人工品鉴反馈")
        return state_context(repo, state, route="end")

    monkeypatch.setattr(DirectorDemoNode, "__call__", finish_demo)
    command = {
        "command_id": "c" * 32,
        "job_id": job.job_id,
        "payload": {
            "base_revision": job.revision,
            "action": "component_demo",
            "idempotency_key": "component-demo-key",
            "component_demo": {"set_id": "A01", "asset_id": "asset-demo-1", "duration_seconds": 10},
        },
    }

    with VideoProductionGraph(repo, tmp_path / "project") as graph:
        result = graph.execute(command)

    assert seen == {
        "component_demo": [{"set_id": "A01", "asset_id": "asset-demo-1", "duration_seconds": 10}],
        "director_demo": 1,
    }
    assert result["route"] == "end"
    current = repo.get_job(job.job_id)
    assert current.status == "DRAFT"
    assert "品鉴反馈" in current.message


def test_director_demo_component_demo_action_finishes_draft_without_human_gate_or_final_render(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="组件套样片 Demo 结束"))
    monkeypatch.setattr("videoagents.nodes.director_demo.current_plan_artifact", lambda repository, current: (object(), {}))
    monkeypatch.setattr("videoagents.nodes.director_demo.current_demo_artifact", lambda repository, current: (object(), {}))
    monkeypatch.setattr(EditingNode, "render_video", lambda *args, **kwargs: pytest.fail("component demo rendered final video"))

    state = state_context(repo, VideoState(
        job_id=job.job_id,
        revision=job.revision,
        action="component_demo",
        run_id="component-demo-run",
        thread_id="component-demo-thread",
        extras={"component_demo": {"set_id": "A01", "asset_id": "asset-demo-1", "duration_seconds": 10}},
    ))

    result = DirectorDemoNode(repo, service)(state)

    assert result["route"] == "end"
    current = repo.get_job(job.job_id)
    assert current.status == "DRAFT"
    assert current.stage == "director"
    assert current.progress == 1
    assert "组件套样片已生成，等待人工品鉴反馈" == current.message


def sample_timeline(**changes):
    payload = {
        "job_id": "component-sample-job",
        "revision": 1,
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "duration_in_frames": 60,
        "shots": [Shot(shot_id="shot-1", start_frame=0, end_frame=60, component_id="Bits-KenBurns", title="组件样片镜头")],
    }
    payload.update(changes)
    return Timeline(**payload)


def test_timeline_production_presentation_is_omitted_from_serialized_legacy_payloads():
    timeline = sample_timeline()

    assert timeline.presentation == "production"
    assert "presentation" not in timeline.model_dump()


def test_timeline_component_sample_requires_silent_captionless_payload():
    timeline = sample_timeline(presentation="component_sample")

    assert timeline.model_dump()["presentation"] == "component_sample"

    with pytest.raises(ValueError, match="不能包含音频或字幕"):
        sample_timeline(presentation="component_sample", audio_src="videoagents/unit/audio.wav")
    with pytest.raises(ValueError, match="不能包含音频或字幕"):
        sample_timeline(
            presentation="component_sample",
            captions=[Caption(text="不应有字幕", start_ms=0, end_ms=500)],
        )


def test_timeline_production_still_requires_real_audio_for_captions():
    with pytest.raises(ValueError, match="带字幕的时间轴必须有真实音频"):
        sample_timeline(captions=[Caption(text="生产字幕", start_ms=0, end_ms=500)])
