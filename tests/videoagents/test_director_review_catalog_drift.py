import json

import pytest

from videoagents.contracts import (
    Alignment,
    AlignmentSegment,
    Brief,
    DirectorRequirements,
    Script,
    ScriptSegment,
    Shot,
    Timeline,
)
from videoagents.nodes.director import _performance_payload
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.nodes.reviewers import dependency_fingerprint
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Conflict, Repository
from videoagents.tools import components

NOTE = "UNIT：旧版 Demo 审核后只要求摄影重做画面，不应被新的组件清单约束卡死。"


def write_native_manifest(tmp_path, monkeypatch, *, min_visible_frames: int) -> None:
    path = tmp_path / "native-component-capabilities.json"
    path.write_text(json.dumps({
        "schema_version": "1",
        "entries": [{
            "component_id": "Rve-QuoteCard",
            "roles": ["main"],
            "source": "quote-card.tsx",
            "renderer": "NativeMediaScene:QuoteCard",
            "use_case": "纯文字引用卡",
            "content_constraints": {
                "items_min": 1,
                "asset_forbidden": True,
                "min_visible_frames": min_visible_frames,
            },
        }],
    }, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(components, "NATIVE_COMPONENT_CAPABILITIES_PATH", path)
    components.native_component_capabilities.cache_clear()


def seeded_director_review(tmp_path, monkeypatch):
    write_native_manifest(tmp_path, monkeypatch, min_visible_frames=30)
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(script_text="观点：旧摄影计划。", target_seconds=2, usage="personal"))
    script = Script(
        title="旧摄影计划",
        origin="user",
        revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration="观点：旧摄影计划。")],
    )
    timeline = Timeline(
        job_id=job.job_id,
        revision=job.revision,
        width=1080,
        height=1920,
        fps=30,
        duration_in_frames=60,
        audio_src="videoagents/unit/audio.wav",
        shots=[Shot(
            shot_id="s1",
            start_frame=0,
            end_frame=60,
            component_id="Rve-QuoteCard",
            title="当时满足最低帧数",
            body="用于证明旧 plan 在生成时有效",
            props={"items": ["AI 交友风险"]},
        )],
    )
    job = repo.update_job(
        job.job_id,
        script=script,
        timeline=timeline,
        director_requirements=DirectorRequirements(min_library_components=1),
        status="NEEDS_HUMAN",
        stage="director",
    )
    alignment = Alignment(
        origin="manual",
        verified=True,
        audio_sha256="a" * 64,
        segments=[AlignmentSegment(segment_id="s1", text="观点：旧摄影计划。", start_ms=0, end_ms=2000)],
    )
    plan = _performance_payload("UNIT", job, timeline, alignment)
    plan_artifact = service.write_json(job, "director-plan.json", plan, "director_plan")
    job = repo.get_job(job.job_id)

    preview_path = repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "director-demo.mp4"
    preview_path.write_bytes(b"UNIT demo bytes")
    preview = service.register_artifact(job, preview_path, "preview", "video/mp4")
    job = service.append_artifact(job.job_id, preview, job.revision)
    repo.update_artifact_metadata(preview.artifact_id, {
        "dependency_fingerprint": dependency_fingerprint(job),
        "director_plan_sha256": plan_artifact.sha256,
        "frame_range": [0, 60],
    })
    job = repo.get_job(job.job_id)
    node = HumanReviewNode(
        repo,
        node_name="director_human_gate",
        stage="director",
        title="摄影 Demo 审核",
        confirmation_requirements=("核对 Demo",),
        min_note_length=0,
        revise_route="director",
    )
    state = VideoState(
        job_id=job.job_id,
        revision=job.revision,
        action="produce",
        run_id="UNIT-drift",
        thread_id="UNIT-drift",
    )
    pending = node._pending(state, job)
    job = repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", stage="director", pending_input=pending)
    state = VideoState(**state, stage_review_pending=pending)
    return repo, job, node, state, pending


def drift_manifest(tmp_path, monkeypatch):
    write_native_manifest(tmp_path, monkeypatch, min_visible_frames=90)


def answer_with(monkeypatch, pending, decision):
    monkeypatch.setattr("videoagents.nodes.human_review.interrupt", lambda value: {
        "decision": decision,
        "note": NOTE,
        "pending_token": pending["pending_token"],
    })


def stage_review_receipts(job):
    return [item for item in job.artifacts if item.kind == "stage_review"]


def test_director_demo_revise_survives_native_catalog_drift(tmp_path, monkeypatch):
    repo, job, node, state, pending = seeded_director_review(tmp_path, monkeypatch)
    drift_manifest(tmp_path, monkeypatch)
    answer_with(monkeypatch, pending, "revise")

    result = node(state)

    assert result["route"] == "revise"
    current = repo.get_job(job.job_id)
    assert current.status == "RUNNING" and current.stage == "director"
    receipt = stage_review_receipts(current)
    assert len(receipt) == 1
    feedback = result["extras"]["human_feedback"]["director"]
    assert feedback["decision"] == "revise"
    assert feedback["target"] == "director"
    assert feedback["applied"] is False
    assert feedback["script"]["segments"][0]["narration"] == "观点：旧摄影计划。"
    assert feedback["timeline"]["shots"][0]["component_id"] == "Rve-QuoteCard"
    assert feedback["director_plan"]["component_usage"]["library_ids"] == ["Rve-QuoteCard"]


def test_director_demo_confirm_still_requires_current_native_validation(tmp_path, monkeypatch):
    repo, job, node, state, pending = seeded_director_review(tmp_path, monkeypatch)
    drift_manifest(tmp_path, monkeypatch)
    answer_with(monkeypatch, pending, "confirm")

    with pytest.raises((Conflict, ValueError)):
        node(state)

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN"
    assert stage_review_receipts(current) == []


@pytest.mark.parametrize("tamper", ["plan_bytes", "timeline"])
def test_director_demo_revise_still_rejects_plan_or_timeline_tampering(tmp_path, monkeypatch, tamper):
    repo, job, node, state, pending = seeded_director_review(tmp_path, monkeypatch)
    drift_manifest(tmp_path, monkeypatch)
    if tamper == "plan_bytes":
        artifact = next(item for item in job.artifacts if item.kind == "director_plan")
        path = repo.artifact_path(artifact.artifact_id)[0]
        path.write_text(path.read_text(encoding="utf-8").replace("AI 交友风险", "被篡改"), encoding="utf-8")
    else:
        timeline = job.timeline.model_copy(deep=True)
        timeline.shots[0].title = "被篡改的时间轴"
        repo.update_job(job.job_id, job.revision, timeline=timeline)
    answer_with(monkeypatch, pending, "revise")

    with pytest.raises((Conflict, ValueError)):
        node(state)

    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN"
    assert stage_review_receipts(current) == []
