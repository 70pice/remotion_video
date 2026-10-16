"""Bounded motion review reuses the production renderer without final approval."""

import pytest
from test_director_shot_review import shot_subject as shot_subject

from videoagents.nodes.editing import EditingNode


def renderer(subject, monkeypatch):
    repo, service, job, _, _ = subject
    calls = []
    monkeypatch.setattr("videoagents.nodes.editing.validate_production_timeline", lambda *a: None)
    monkeypatch.setattr("videoagents.nodes.editing.timeline_readability_issues", lambda *a: [])
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available",
                        lambda *a: pytest.fail("motion review must not invoke the editor model"))

    def render(project, timeline, output, cover, mode, timeout, cancelled, progress, *, frame_range=None):
        calls.append((mode, frame_range))
        output.write_bytes(b"UNIT renderer output")

    monkeypatch.setattr("videoagents.nodes.editing.render", render)
    return repo, job, EditingNode(repo, service), calls


def test_explicit_motion_preview_uses_exact_range_and_plan_binding(shot_subject, monkeypatch):
    repo, job, node, calls = renderer(shot_subject, monkeypatch)
    node.render_video(job, "preview", frame_range=(15, 90))
    current = repo.get_job(job.job_id)
    preview = next(item for item in current.artifacts if item.kind == "preview")
    metadata = repo.artifact_metadata(preview.artifact_id)
    assert calls == [("preview", (15, 90))]
    assert metadata["frame_range"] == [15, 90]
    assert metadata["motion_preview"] is True
    assert metadata["director_plan_sha256"] == shot_subject[3].sha256
    assert current.timeline == job.timeline and current.status == job.status
    assert not any(item.kind in {"final", "stage_review"} for item in current.artifacts)


@pytest.mark.parametrize("mode,bounds", [
    ("final", (0, 30)), ("preview", (-1, 30)), ("preview", (0, 121)),
    ("preview", (30, 30)), ("preview", (60, 30)), ("preview", (False, 30)),
    ("preview", (0, 30.0)), ("preview", [0, 30]), ("preview", (0,)),
])
def test_invalid_motion_range_is_rejected_before_render(shot_subject, monkeypatch, mode, bounds):
    repo, job, node, calls = renderer(shot_subject, monkeypatch)
    before = repo.get_job(job.job_id)
    with pytest.raises(ValueError, match="30秒"):
        node.render_video(job, mode, frame_range=bounds)
    assert calls == [] and repo.get_job(job.job_id) == before


def test_motion_preview_cannot_render_more_than_thirty_seconds(shot_subject, monkeypatch):
    _, job, node, calls = renderer(shot_subject, monkeypatch)
    job = job.model_copy(update={"timeline": job.timeline.model_copy(update={"duration_in_frames": 1200})})
    with pytest.raises(ValueError, match="30秒"):
        node.render_video(job, "preview", frame_range=(0, 901))
    assert calls == []


def test_per_shot_plan_without_range_does_not_invent_demo(shot_subject, monkeypatch):
    _, job, node, calls = renderer(shot_subject, monkeypatch)
    with pytest.raises(ValueError, match="必须指定连续帧范围"):
        node.render_video(job, "preview")
    assert calls == []


def test_legacy_demo_range_is_preserved(shot_subject, monkeypatch):
    repo, job, node, calls = renderer(shot_subject, monkeypatch)
    artifact, plan = shot_subject[3:]
    plan = {**plan, "demo": {"start_frame": 0, "end_frame": 90}}
    monkeypatch.setattr("videoagents.nodes.editing.current_plan_artifact", lambda *a: (artifact, plan))
    node.render_video(job, "preview")
    assert calls == [("preview", (0, 90))]
    preview = next(item for item in repo.get_job(job.job_id).artifacts if item.kind == "preview")
    assert "motion_preview" not in repo.artifact_metadata(preview.artifact_id)


@pytest.mark.parametrize("approved", [True, False])
def test_editor_inherits_checked_visual_revision_only_after_current_package_confirmed(
        shot_subject, monkeypatch, approved):
    from videoagents.nodes.editing import editing_visual_review_context

    repo, service, job, _, _ = shot_subject
    service.write_json(job, "unit-confirm.json", {
        "revision": job.revision, "stage": "director", "node_name": "director_human_gate",
        "decision": "confirm", "note": "UNIT: reviewed current complete package",
    }, "stage_review")
    job = repo.get_job(job.job_id)
    checked = {"note": "UNIT: cycle pictures, show steps earlier", "shot_ids": ["shot1", "shot2"],
               "source_revision": 1, "target_revision": 2, "source_review_artifact_id": "unit-review",
               "preview": True, "frame_range": [0, 120]}
    calls = []

    def revision_context(repository, current):
        calls.append(current.job_id)
        return checked

    monkeypatch.setattr("videoagents.nodes.editing.director_demo_is_approved", lambda *a: approved)
    monkeypatch.setattr("videoagents.services.director_recovery.visual_revision_context", revision_context)
    context = editing_visual_review_context(repo, job)
    if approved:
        assert context["visual_revision"] == checked and calls == [job.job_id]
    else:
        assert "visual_revision" not in context and not calls
