"""The editing Agent gets exact shot semantics without raw word-caption bloat."""

import copy

import pytest

from videoagents.contracts import Asset, Brief, Script, ScriptSegment, Timeline
from videoagents.nodes.editing import EditingNode, compact_timeline_for_editing
from videoagents.services.jobs import JobService
from videoagents.state import VideoState, job_context
from videoagents.storage import Repository

PENDING_REVIEW_LICENSE = "真实来源视频；尚未确认再利用许可，请在发布审核时核验"


def test_compact_timeline_for_editing_keeps_shots_and_projects_caption_windows():
    timeline = {
        "fps": 30,
        "duration_in_frames": 180,
        "shots": [
            {"shot_id": "shot-1", "start_frame": 0, "end_frame": 90},
            {"shot_id": "shot-2", "start_frame": 90, "end_frame": 180},
        ],
        "captions": [
            {"text": "第一句", "start_ms": 0.0, "end_ms": 2500.0},
            {"text": "跨镜", "start_ms": 2500.0, "end_ms": 3500.0},
            {"text": "第二句", "start_ms": 3500.0, "end_ms": 5900.0},
        ],
    }

    compact = compact_timeline_for_editing(timeline)

    assert "captions" not in compact
    assert compact["shots"] == timeline["shots"]
    assert compact["caption_summary"] == {
        "count": 3,
        "first_start_ms": 0.0,
        "last_end_ms": 5900.0,
        "windows": [
            {"shot_id": "shot-1", "start_ms": 0.0, "end_ms": 3000.0,
             "caption_start_ms": 0.0, "caption_end_ms": 3500.0, "text": "第一句跨镜"},
            {"shot_id": "shot-2", "start_ms": 3000.0, "end_ms": 6000.0,
             "caption_start_ms": 2500.0, "caption_end_ms": 5900.0, "text": "跨镜第二句"},
        ],
    }
    assert timeline["captions"][0]["text"] == "第一句"


@pytest.mark.parametrize("review", ["applied", "unapplied", "wrong-token", "wrong-revision", "unapproved"])
def test_editing_model_receives_renderable_visual_metadata_without_audio_alignment_or_mutating_inputs(
        tmp_path, monkeypatch, review):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="Muse", target_seconds=2, width=240, height=426, fps=15))
    audio = Asset(asset_id="unit-audio", name="unit.wav", role="audio", mime_type="audio/wav",
                  size_bytes=1, sha256="a" * 64, artifact_id="unit-audio-artifact",
                  url="/api/artifacts/unit-audio-artifact",
                  timeline_src=f"videoagents/{job.job_id}/assets/unit.wav")
    video = Asset(asset_id="unit-video", name="unit.mp4", role="evidence", mime_type="video/mp4",
                  size_bytes=1, sha256="b" * 64, artifact_id="unit-video-artifact",
                  url="/api/artifacts/unit-video-artifact", source_url="https://example.test/muse",
                  license_note=PENDING_REVIEW_LICENSE,
                  timeline_src=f"videoagents/{job.job_id}/assets/unit.mp4")
    blocked = Asset(asset_id="unit-blocked", name="blocked.png", role="evidence", mime_type="image/png",
                    size_bytes=1, sha256="c" * 64, artifact_id="unit-blocked-artifact",
                    url="/api/artifacts/unit-blocked-artifact", source_url="https://example.test/blocked",
                    license_note="真实网页截图；仅作核验依据，不直接发布",
                    timeline_src=f"videoagents/{job.job_id}/assets/blocked.png")
    script = Script(title="Muse", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：这是测试文案。",
                                            source_refs=["https://example.test/muse"], asset_ids=[video.asset_id])])
    timeline = Timeline(job_id=job.job_id, revision=job.revision, width=job.brief.width,
                        height=job.brief.height, fps=job.brief.fps, duration_in_frames=30,
                        audio_src=audio.timeline_src,
                        shots=[{"shot_id": "shot-1", "start_frame": 0, "end_frame": 30,
                                "component_id": "video", "title": "真实视频",
                                "asset_src": video.timeline_src, "source_label": "example.test",
                                "props": {"start_seconds": 0, "fit": "contain"}}],
                        captions=[{"text": "观点：这是测试文案。", "start_ms": 0.0, "end_ms": 1800.0}])
    job = repo.update_job(job.job_id, job.revision, assets=[audio, video, blocked],
                          script=script, timeline=timeline)
    repo.update_asset_metadata(audio.asset_id, {
        "duration_seconds": 2.0,
        "alignment": {"origin": "unit", "segments": [{"text": "should not reach editing"}]},
    })
    repo.update_asset_metadata(video.asset_id, {
        "duration_seconds": 2.4,
        "width": 960,
        "height": 540,
        "origin": "materials",
        "alignment": {"origin": "should be stripped"},
    })
    repo.update_asset_metadata(blocked.asset_id, {"width": 800, "height": 600, "origin": "materials"})
    original_script = job.script.model_dump()
    original_timeline = job.timeline.model_dump()
    note = "UNIT: 不用编程界面，使用已选收益图，旁白与音频保持不变。"
    revision = job.revision - 1 if review == "wrong-revision" else job.revision
    receipt = service.write_json(job, "unit-visual-revise.json", {
        "stage": "director", "node_name": "director_human_gate", "revision": revision,
        "review_mode": "per_shot_stills", "pending_token": "unit-visual-choice", "decision": "revise", "note": note,
        "subject": {"timeline": {"shots": [{"shot_id": "OLD-SNAPSHOT-MUST-NOT-LEAK"}]},
                    "script": {"title": "OLD-SCRIPT-MUST-NOT-LEAK"}},
    }, "stage_review")
    applied = service.write_json(job, "unit-visual-applied.json", {
        "stage": "director", "target": "director", "revision": revision,
        "pending_token": "unit-unrelated-token" if review == "wrong-token" else "unit-visual-choice",
        "note": note, "applied": review != "unapplied",
    }, "human_feedback_applied")
    confirmation = service.write_json(job, "unit-current-shot-confirmation.json", {
        "stage": "director", "node_name": "director_human_gate", "revision": job.revision,
        "review_mode": "per_shot_stills", "pending_token": "unit-current-package", "decision": "confirm",
        "note": "UNIT: 当前全部逐镜图已确认，继续成片。", "reviewed_shot_ids": ["shot-1"],
        "director_shot_review_artifact_id": "unit-current-package-artifact", "dependency_fingerprint": "unit-bound-current-plan",
        "subject": {"timeline": {"shots": [{"shot_id": "OLD-CONFIRMATION-SNAPSHOT"}]}},
    }, "stage_review")
    # Keep both immutable review receipts, as the real HumanReviewNode does.
    job = repo.update_job(job.job_id, artifacts=[receipt, applied, confirmation])
    monkeypatch.setattr("videoagents.nodes.editing.director_demo_is_approved", lambda *a: review != "unapproved")
    node = EditingNode(repo, service)
    monkeypatch.setattr(node.model, "available", lambda role: True)
    monkeypatch.setattr("videoagents.nodes.editing.render", lambda *args, **kwargs: pytest.fail("blocking preflight reached render"))
    calls = []

    def call(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((job_id, revision, role, context, command_id, output_schema))
        return {"pacing_notes": ["UNIT TEST：保留原时间轴"],
                "layout_notes": ["UNIT TEST：素材元数据已传入"],
                "findings": [{"severity": "error", "owner": "editing", "blocking": True,
                              "message": "UNIT TEST：停在模型预检，不渲染"}]}

    monkeypatch.setattr(node.model, "call", call)
    state = VideoState(**job_context(job), run_id="unit-editing-context", action="produce",
                       asset_metadata={audio.asset_id: {"alignment": {"origin": "state copy should not leak"}},
                                       video.asset_id: {"duration_seconds": 99, "alignment": {"origin": "state leak"}}},
                       extras={"human_feedback": {"director": {
                           "decision": "revise", "note": "UNTRUSTED-CHECKPOINT-NOTE", "applied": True,
                           "timeline": copy.deepcopy(original_timeline)}}, "unrelated": "MUST-NOT-LEAK"})

    with pytest.raises(ValueError, match="剪辑模型预检未通过"):
        node.render_video(job, "final", state=state)

    assert len(calls) == 1
    job_id, revision, role, context, command_id, schema = calls[0]
    assert (job_id, revision, role, command_id) == (
        job.job_id, job.revision, "editing", "unit-editing-context")
    assert schema["title"] == "EditingAdvice"
    assert audio.asset_id not in context["asset_metadata"]
    assert context["asset_metadata"][video.asset_id] == {
        "duration_seconds": 2.4,
        "width": 960,
        "height": 540,
        "origin": "materials",
        "renderable": True,
    }
    assert context["asset_metadata"][blocked.asset_id] == {
        "width": 800,
        "height": 600,
        "origin": "materials",
        "renderable": False,
    }
    assert all("alignment" not in metadata for metadata in context["asset_metadata"].values())
    assert "captions" not in context["timeline"]
    visual_review = context["extras"]["visual_review"]
    if review == "applied" or review == "unapproved":
        assert visual_review["applied_director_feedback"]["note"] == note
        assert visual_review["applied_director_feedback"]["review_artifact_id"] == receipt.artifact_id
        assert visual_review["applied_director_feedback"]["applied_artifact_id"] == applied.artifact_id
    else:
        assert "applied_director_feedback" not in visual_review
    if review != "unapproved":
        assert visual_review["shot_review_confirmation"]["pending_token"] == "unit-current-package"
        assert visual_review["shot_review_confirmation"]["reviewed_shot_ids"] == ["shot-1"]
    else:
        assert "shot_review_confirmation" not in visual_review
    assert "OLD-" not in repr(context) and "MUST-NOT-LEAK" not in repr(context)
    assert "UNTRUSTED-CHECKPOINT-NOTE" not in repr(context)
    assert repo.get_job(job.job_id).script.model_dump() == original_script
    assert repo.get_job(job.job_id).timeline.model_dump() == original_timeline


def test_editing_guidance_records_the_actual_instruction_and_frozen_inputs(tmp_path, monkeypatch):
    from videoagents.nodes.editing import editing_instruction_fingerprint
    from videoagents.nodes.reviewers import dependency_fingerprint

    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT", width=240, height=426, fps=15))
    job = repo.update_job(job.job_id, timeline=Timeline(job_id=job.job_id, revision=job.revision,
        width=240, height=426, fps=15, duration_in_frames=30,
        shots=[{"shot_id": "shot", "start_frame": 0, "end_frame": 30, "component_id": "title", "title": "UNIT"}]))
    node = EditingNode(repo, service)
    monkeypatch.setattr(node.model, "available", lambda role: True)
    monkeypatch.setattr(node.model, "invoke", lambda *args, **kwargs: {
        "pacing_notes": [], "layout_notes": [], "findings": [
            {"severity": "error", "owner": "editing", "blocking": True, "message": "UNIT：不渲染"}]})
    with pytest.raises(ValueError, match="剪辑模型预检未通过"):
        node.render_video(job, "final")
    artifact = next(a for a in repo.get_job(job.job_id).artifacts if a.kind == "editing_guidance")
    assert repo.artifact_metadata(artifact.artifact_id) == {
        "instruction_fingerprint": editing_instruction_fingerprint(job),
        "dependency_fingerprint": dependency_fingerprint(job),
    }


def test_editing_prompt_includes_selected_kit_bindings_and_actual_layer_roles(tmp_path):
    import json

    from videoagents.nodes.editing import editing_prompt
    from videoagents.tools.component_sets import allowed_component_set_templates
    from videoagents.tools.components import native_component_capabilities

    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="UNIT", usage="personal"))
    template = allowed_component_set_templates(job.brief.usage)["A12"]
    job = repo.update_job(job.job_id, timeline=Timeline(job_id=job.job_id, revision=job.revision,
        width=1080, height=1920, fps=30, duration_in_frames=180, shots=[
            {"shot_id": "set", "start_frame": 0, "end_frame": 90,
             "component_id": template["main_component_id"], "title": "本期标题",
             "set_design": {"set_id": "A12", "content": {"takeaway": "本期结论"}}},
            {"shot_id": "layer", "start_frame": 90, "end_frame": 180, "component_id": "title",
             "title": "持续标题", "layers": [{"component_id": "Snapcn-TextReveal", "role": "title",
                 "start_frame": 0, "end_frame": 90, "title": "实际强调"}]}]))
    prompt = editing_prompt(job)
    capabilities = json.loads(prompt.rsplit("\n", 1)[1])
    assert capabilities["component_sets"] == [template]
    assert capabilities["layer_roles"] == {
        "Snapcn-TextReveal": sorted(native_component_capabilities()["layer_roles"]["Snapcn-TextReveal"])}
    assert "本期标题" not in prompt and "本期结论" not in prompt
    assert "shot.layers" in prompt and "shot.set_design" in prompt
    assert "不是 layers 或 parts" in prompt
