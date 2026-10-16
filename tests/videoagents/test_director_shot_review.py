"""Every production shot must have a bound real frame before approval."""

import copy
import json
import os
import struct
import zlib

import pytest

from videoagents.contracts import (
    Alignment,
    AlignmentSegment,
    Artifact,
    Brief,
    Script,
    ScriptSegment,
    Shot,
    Timeline,
)
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import state_context
from videoagents.nodes.director import DirectorNode, _performance_payload
from videoagents.nodes.director_demo import DirectorDemoNode
from videoagents.nodes.director_review import (
    current_shot_review_artifact,
    director_demo_is_approved,
    director_review_fingerprint,
)
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from worker.runner import Worker


def png_bytes(width=240, height=426):
    def chunk(name, data):
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = b"".join(b"\0" + b"\x11\x22\x33" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


@pytest.fixture
def shot_subject(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT: shot review", width=240, height=426, fps=30))
    script = Script(title="UNIT", revision=job.revision, origin="user", segments=[
        ScriptSegment(segment_id="s1", narration="第一镜。第二镜。"),
    ])
    timeline = Timeline(job_id=job.job_id, revision=job.revision, width=240, height=426, fps=30,
        duration_in_frames=120, shots=[
            Shot(shot_id="shot1", start_frame=0, end_frame=60, component_id="title", title="第一镜"),
            Shot(shot_id="shot2", start_frame=60, end_frame=120, component_id="keyword", title="第二镜"),
        ])
    job = repo.update_job(job.job_id, script=script, timeline=timeline)
    alignment = Alignment(origin="manual", verified=True, audio_sha256="a" * 64, segments=[
        AlignmentSegment(segment_id="s1", text="第一镜。第二镜。", start_ms=0, end_ms=4000),
    ])
    plan = _performance_payload("UNIT", job, timeline, alignment)
    plan.pop("demo", None)
    plan.update(review_mode="per_shot_stills", shot_reviews=[
        {"shot_id": shot.shot_id, "review_frame": shot.start_frame + 30,
         "component_reason": "UNIT: explain this exact component choice.",
         "visual_action": "UNIT: review the stable state of this shot."}
        for shot in timeline.shots
    ])
    plan_artifact = service.write_json(job, "unit-plan.json", plan, "director_plan")
    return repo, service, repo.get_job(job.job_id), plan_artifact, plan


def write_review_package(subject):
    repo, service, job, plan_artifact, plan = subject
    items = []
    for index, (shot, spec) in enumerate(zip(job.timeline.shots, plan["shot_reviews"], strict=True), 1):
        path = repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / f"unit-shot-{index}.png"
        path.write_bytes(png_bytes())
        image = service.register_artifact(job, path, "shot_review_frame", "image/png")
        repo.update_artifact_metadata(image.artifact_id, {
            "dependency_fingerprint": dependency_fingerprint(job),
            "director_plan_sha256": plan_artifact.sha256,
            "shot_id": shot.shot_id, "review_frame": spec["review_frame"],
            "width": 240, "height": 426,
        })
        items.append({**spec, "index": index, "start_frame": shot.start_frame,
            "end_frame": shot.end_frame, "component_id": shot.component_id, "set_id": None,
            "component_ids": [shot.component_id], "title": shot.title, "body": shot.body,
            "asset_src": shot.asset_src, "source_label": shot.source_label,
            "narration": "", "image": image.model_dump(mode="json")})
    manifest = {
        "schema_version": 1, "mode": "per_shot_stills", "job_id": job.job_id, "revision": job.revision,
        "director_plan_artifact_id": plan_artifact.artifact_id, "director_plan_sha256": plan_artifact.sha256,
        "dependency_fingerprint": dependency_fingerprint(job), "timeline_fingerprint": plan["timeline_fingerprint"],
        "width": 240, "height": 426, "fps": 30, "duration_in_frames": 120, "items": items,
    }
    repo.update_job(job.job_id, job.revision,
                    artifacts=job.artifacts + [Artifact.model_validate(item["image"]) for item in items])
    artifact = service.write_json(job, "unit-shot-review.json", manifest, "director_shot_review")
    repo.update_artifact_metadata(artifact.artifact_id, {
        "dependency_fingerprint": dependency_fingerprint(job), "director_plan_sha256": plan_artifact.sha256,
        "review_mode": "per_shot_stills",
    })
    return repo.get_job(job.job_id), artifact, manifest


def review_node(repo):
    return HumanReviewNode(repo, node_name="director_human_gate", stage="director", revise_route="director",
                          min_note_length=0)


def test_new_plan_cannot_be_approved_by_legacy_partial_demo(shot_subject):
    repo, service, job, plan_artifact, _ = shot_subject
    preview = service.write_json(job, "old-demo.json", {"synthetic": True}, "preview")
    repo.update_artifact_metadata(preview.artifact_id, {
        "dependency_fingerprint": dependency_fingerprint(job), "director_plan_sha256": plan_artifact.sha256,
        "frame_range": [0, 30],
    })
    with pytest.raises(ValueError, match="逐镜|审核包"):
        director_review_fingerprint(repo, repo.get_job(job.job_id))


@pytest.mark.parametrize("change", ["missing", "duplicate", "wrong_frame", "wrong_component", "wrong_plan",
                                    "wrong_revision", "wrong_job", "metadata", "image_bytes"])
def test_review_package_rejects_incomplete_or_changed_subject(shot_subject, change):
    repo, service, _, _, _ = shot_subject
    job, artifact, manifest = write_review_package(shot_subject)
    assert current_shot_review_artifact(repo, job)[0] == artifact
    broken = copy.deepcopy(manifest)
    if change == "missing":
        broken["items"].pop()
    elif change == "duplicate":
        broken["items"][1] = copy.deepcopy(broken["items"][0])
    elif change == "wrong_frame":
        broken["items"][0]["review_frame"] = 60
    elif change == "wrong_component":
        broken["items"][0]["component_id"] = "keyword"
    elif change == "wrong_plan":
        broken["director_plan_sha256"] = "f" * 64
    elif change == "wrong_revision":
        broken["revision"] += 1
    elif change == "wrong_job":
        broken["job_id"] = "another-job"
    elif change == "metadata":
        image = broken["items"][0]["image"]
        repo.update_artifact_metadata(image["artifact_id"], {"review_frame": 0})
    else:
        repo.artifact_path(broken["items"][0]["image"]["artifact_id"])[0].write_bytes(b"changed")
    if change not in {"metadata", "image_bytes"}:
        service.write_json(job, "broken-shot-review.json", broken, "director_shot_review")
    with pytest.raises((Conflict, ValueError)):
        current_shot_review_artifact(repo, repo.get_job(job.job_id))


@pytest.mark.parametrize("ids", [None, [], ["shot1"], ["shot1", "shot1"], ["shot1", "foreign"]])
def test_confirmation_requires_explicit_complete_reviewed_shot_ids(shot_subject, monkeypatch, ids):
    repo, _, _, _, _ = shot_subject
    job, _, _ = write_review_package(shot_subject)
    node = review_node(repo)
    state = VideoState(job_id=job.job_id, revision=job.revision, thread_id="UNIT-all-shots", action="produce")
    pending = node._pending(state, job)
    answer = {"decision": "confirm", "note": "UNIT", "pending_token": pending["pending_token"]}
    if ids is not None:
        answer["reviewed_shot_ids"] = ids
    monkeypatch.setattr("videoagents.nodes.human_review.interrupt", lambda value: answer)
    with pytest.raises(Conflict, match="逐镜|所有镜头|每个镜头"):
        node(state)
    assert not any(item.kind == "stage_review" for item in repo.get_job(job.job_id).artifacts)


def test_every_shot_confirmation_is_bound_and_keeps_unpublished_state(shot_subject, monkeypatch):
    repo, _, _, _, _ = shot_subject
    job, _, _ = write_review_package(shot_subject)
    node = review_node(repo)
    state = VideoState(job_id=job.job_id, revision=job.revision, thread_id="UNIT-all-shots", action="produce")
    pending = node._pending(state, job)
    assert pending["review_mode"] == "per_shot_stills"
    assert pending["required_shot_ids"] == ["shot1", "shot2"]
    monkeypatch.setattr("videoagents.nodes.human_review.interrupt", lambda value: {
        "decision": "confirm", "note": "UNIT", "pending_token": pending["pending_token"],
        "reviewed_shot_ids": ["shot2", "shot1"],
    })
    result = node(state)
    assert result["route"] == "continue"
    current = repo.get_job(job.job_id)
    assert director_demo_is_approved(repo, current)
    assert current.status == "RUNNING" and current.stage == "director"
    receipt = next(item for item in current.artifacts if item.kind == "stage_review")
    value = json.loads(repo.artifact_path(receipt.artifact_id)[0].read_text(encoding="utf-8"))
    assert value["reviewed_shot_ids"] == ["shot1", "shot2"]
    assert value["subject"]["director_shot_review"]["director_plan_sha256"] == shot_subject[3].sha256


def frame_render_double(calls, *, omit_last=False):
    def render(project, timeline, request, output_manifest, timeout, cancelled, progress):
        requested = json.loads(request.read_text(encoding="utf-8"))
        calls.append(copy.deepcopy(requested))
        images = []
        for index, item in enumerate(requested, 1):
            path = output_manifest.parent / f"shot-{index:03d}.png"
            if not omit_last or index < len(requested):
                path.write_bytes(png_bytes())
            images.append({**item, "width": 240, "height": 426, "path": str(path)})
        output_manifest.write_text(json.dumps(images), encoding="utf-8")
        return {"event": "complete", "output": str(output_manifest), "images": images}
    return render


def node_state(repo, job):
    return state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                                        thread_id="UNIT-shot-node", run_id="UNIT-shot-node", extras={}))


def test_new_production_node_renders_every_frame_and_reuses_complete_package(shot_subject, monkeypatch):
    repo, service, job, _, _ = shot_subject
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls))
    monkeypatch.setattr(EditingNode, "render_video", lambda *a, **k: pytest.fail("new production rendered demo"))
    node = DirectorDemoNode(repo, service)
    state = node_state(repo, job)
    result = node(state)
    assert result["route"] == "director_human_gate"
    _, manifest = current_shot_review_artifact(repo, repo.get_job(job.job_id), validate_components=False)
    assert manifest["items"][1]["image"]["kind"] == "shot_review_frame"
    current = repo.get_job(job.job_id)
    images = [item for item in current.artifacts if item.kind == "shot_review_frame"]
    assert len(images) == 2 and len({item.artifact_id for item in images}) == 2
    assert not any(item.kind in {"preview", "final", "stage_review"} for item in current.artifacts)
    assert node(result)["route"] == "director_human_gate"
    assert len(calls) == 1
    assert calls[0] == [{"shot_id": "shot1", "frame": 30}, {"shot_id": "shot2", "frame": 90}]
    assert [item.artifact_id for item in repo.get_job(job.job_id).artifacts if item.kind == "shot_review_frame"] == [
        item.artifact_id for item in images]


def test_partial_render_never_publishes_an_incomplete_review_package(shot_subject, monkeypatch):
    repo, service, job, _, _ = shot_subject
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls, omit_last=True))
    result = DirectorDemoNode(repo, service)(node_state(repo, job))
    assert result["route"] == "await_input"
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT"
    assert current.pending_input["retry_node"] == "director_demo"
    assert not any(item.kind in {"director_shot_review", "shot_review_frame", "stage_review", "final"}
                   for item in current.artifacts)


def test_storyboard_renders_every_shot_pack_then_finishes_without_final(shot_subject, monkeypatch):
    repo, service, job, _, _ = shot_subject
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls))
    monkeypatch.setattr(EditingNode, "render_video", lambda *a, **k: pytest.fail("storyboard rendered video"))
    state = node_state(repo, job)
    state["action"] = "storyboard"
    assert DirectorNode(repo, service).next_route(state) == "director_demo"
    result = DirectorDemoNode(repo, service)(state)
    assert result["route"] == "end"
    current = repo.get_job(job.job_id)
    assert current.status == "DRAFT" and current.stage == "director"
    assert len(calls) == 1 and "逐镜" in current.message
    assert not any(item.kind in {"preview", "final", "stage_review"} for item in current.artifacts)


def test_missing_shot_package_blocks_final_even_with_old_confirmation(shot_subject, monkeypatch):
    repo, service, job, _, _ = shot_subject
    service.write_json(job, "unit-old-review.json", {
        "node_name": "director_human_gate", "revision": job.revision, "decision": "confirm",
        "dependency_fingerprint": "f" * 64,
    }, "stage_review")
    monkeypatch.setattr(EditingNode, "render_video", lambda *a, **k: pytest.fail("unreviewed final rendered"))
    assert EditingNode(repo, service)(node_state(repo, job))["route"] == "director_demo"


def test_graph_waits_for_all_shots_and_resume_forwards_explicit_review_ids(shot_subject, monkeypatch):
    repo, service, job, _, _ = shot_subject
    rendered = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(rendered))
    final_calls = []

    def final(node, current, mode, state=None):
        assert mode == "final"
        final_calls.append(current.job_id)
        artifact = service.write_json(current, "unit-final.json", {"synthetic": True}, "final")
        repo.update_artifact_metadata(artifact.artifact_id, {"dependency_fingerprint": dependency_fingerprint(current)})

    monkeypatch.setattr(EditingNode, "render_video", final)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "unit-shot-start"})
    command = repo.claim(os.getpid())
    thread_id = f"job:{job.job_id}:run:{command['command_id']}"
    state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
        run_id=command["command_id"], thread_id=thread_id, route="director_demo", extras={}))
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.graph.update_state({"configurable": {"thread_id": thread_id}}, state, as_node="clear_director")
        graph.execute(command)
    repo.finish(command["command_id"])
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN" and paused.pending_input["review_mode"] == "per_shot_stills"
    assert paused.pending_input["required_shot_ids"] == ["shot1", "shot2"]
    assert not final_calls
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "resume", "decision": "confirm",
        "note": "UNIT: reviewed every actual rendered frame and component choice.",
        "reviewed_shot_ids": ["shot2", "shot1"], "pending_token": paused.pending_input["pending_token"],
        "idempotency_key": "unit-shot-approved"})
    assert Worker(repo, service.project_root).once()
    current = repo.get_job(job.job_id)
    assert current.status == "DRAFT" and current.stage == "complete"
    assert len(rendered) == 1 and final_calls == [job.job_id]
    assert director_demo_is_approved(repo, current)


def test_refresh_shots_forces_same_plan_once_and_reuses_published_package(shot_subject, monkeypatch):
    repo, service, _, plan_artifact, _ = shot_subject
    job, old_review, _ = write_review_package(shot_subject)
    timeline = job.timeline.model_dump()
    calls = []
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", frame_render_double(calls))
    monkeypatch.setattr(EditingNode, "render_video", lambda *a, **k: pytest.fail("refresh rendered video"))
    state = node_state(repo, job)
    state.update(action="refresh_shots", run_id="unit-refresh-command")
    node = DirectorDemoNode(repo, service)
    result = node(state)
    current = repo.get_job(job.job_id)
    review, _ = current_shot_review_artifact(repo, current)
    assert len(calls) == 1
    assert review.artifact_id != old_review.artifact_id
    assert repo.artifact_metadata(review.artifact_id)["refresh_command_id"] == state["run_id"]
    assert current.timeline.model_dump() == timeline
    assert plan_artifact in current.artifacts
    assert result["route"] == "director_human_gate"
    assert node(result)["route"] == "director_human_gate"
    assert len(calls) == 1
    assert not director_demo_is_approved(repo, current)
