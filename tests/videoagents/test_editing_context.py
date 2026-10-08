"""The editing Agent gets exact shot semantics without raw word-caption bloat."""

import pytest

from videoagents.contracts import Asset, Brief, Script, ScriptSegment, Timeline
from videoagents.nodes.editing import (
    DirectorInputError,
    EditingNode,
    bound_component_contracts_for_editing,
    compact_timeline_for_editing,
    compact_visual_feedback,
)
from videoagents.services.jobs import JobService
from videoagents.state import VideoState, job_context
from videoagents.storage import Repository
from videoagents.tools.components import component_study_payload

PENDING_REVIEW_LICENSE = "真实来源视频；尚未确认再利用许可，请在发布审核时核验"


@pytest.mark.parametrize("source_changed", [False, True])
def test_editing_checks_saved_component_source_before_model_calls_and_render(tmp_path, monkeypatch, source_changed):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="来源漂移", target_seconds=1))
    timeline = Timeline(job_id=job.job_id, revision=job.revision, width=1080, height=1920,
                        fps=30, duration_in_frames=30,
                        audio_src=f"videoagents/{job.job_id}/assets/audio.wav",
                        shots=[{"shot_id": "one", "start_frame": 0, "end_frame": 30,
                                "component_id": "title", "title": "真实内容"}], captions=[])
    job = repo.update_job(job.job_id, job.revision, timeline=timeline)
    payload = component_study_payload(job.brief.usage)
    study = {
        "manifest_fingerprint": payload["manifest_fingerprint"],
        "source_fingerprint": "0" * 64 if source_changed else payload["source_fingerprint"],
        "usage": job.brief.usage, "reviewed_preset_ids": payload["all_preset_ids"],
        "allowed_component_ids": payload["allowed_component_ids"], "video_first": True,
        "selection_principles": ["真实素材", "来源对应", "完整学习", "清楚表达"],
        "component_groups": [{"group": str(index), "use": "本组资料已学习"} for index in range(6)],
        "limits": ["未逐像素看完全部预设"],
    }
    service.write_json(job, "component-study.json", study, "component_study")
    node = EditingNode(repo, service)
    monkeypatch.setattr(node.model, "invoke", lambda *args, **kwargs: pytest.fail("drift reached model call"))
    monkeypatch.setattr("videoagents.nodes.editing.render", lambda *args, **kwargs: pytest.fail("drift reached renderer"))

    def reached_timeline(*args, **kwargs):
        raise ValueError("CURRENT_SOURCE_REACHED_TIMELINE_VALIDATION")

    monkeypatch.setattr("videoagents.nodes.editing.validate_timeline", reached_timeline)
    if source_changed:
        with pytest.raises(DirectorInputError, match="组件源码已变化"):
            node.render_video(job, "final")
    else:
        with pytest.raises(ValueError, match="CURRENT_SOURCE_REACHED_TIMELINE_VALIDATION"):
            node.render_video(job, "final")


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


@pytest.mark.parametrize("applied", [True, False])
def test_editing_receives_visual_acceptance_notes_without_historical_snapshots(applied):
    reviewed_timeline = {"shots": [{"shot_id": "shot-old"}]}
    extras = {
        "human_feedback": {
            "render": {
                "decision": "revise",
                "note": "已实测原图区域；数字出现前展示任务参照",
                "applied": applied,
                "timeline": reviewed_timeline,
                "script": {"title": "old"},
            },
            "script": {"decision": "revise", "note": "上游意见不属于剪辑输入"},
        },
        "unrelated": {"timeline": reviewed_timeline},
    }
    projected = compact_visual_feedback(extras)
    assert projected == {"human_feedback": {"render": {
        "decision": "revise", "note": extras["human_feedback"]["render"]["note"], "applied": applied,
    }}}
    assert extras["human_feedback"]["render"]["timeline"] == reviewed_timeline
    assert compact_visual_feedback({"human_feedback": []}) == {}
    assert compact_visual_feedback({"human_feedback": {"director": {"decision": "revise", "note": " "}}}) == {}


def test_bound_component_contracts_for_editing_only_include_current_bound_props():
    timeline = {
        "shots": [
            {"shot_id": "fixed", "component_id": "Rve-StatCounter", "props": {}},
            {"shot_id": "counter", "component_id": "Rve-StatCounter", "props": {
                "value": 4700, "label": "AI身份", "change": "", "period": "两周",
                "suffix": "+", "source_ref": "https://example.test/muse",
            }},
            {"shot_id": "title", "component_id": "title", "props": {"eyebrow": "测试"}},
        ],
    }

    contracts = bound_component_contracts_for_editing(timeline)

    assert set(contracts) == {"Rve-StatCounter"}
    assert contracts["Rve-StatCounter"]["schema"]["required"] == [
        "value", "label", "change", "period", "suffix", "source_ref",
    ]
    assert contracts["Rve-StatCounter"]["chart"] is False
    assert contracts["Rve-StatCounter"]["sourced"] is True
    assert contracts["Rve-StatCounter"]["used_shot_ids"] == ["counter"]


def test_editing_model_receives_renderable_visual_metadata_without_audio_alignment_or_mutating_inputs(tmp_path, monkeypatch):
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
                        height=job.brief.height, fps=job.brief.fps, duration_in_frames=60,
                        audio_src=audio.timeline_src,
                        shots=[{"shot_id": "shot-1", "start_frame": 0, "end_frame": 30,
                                "component_id": "Rve-StatCounter", "title": "AI身份数量",
                                "asset_src": None, "source_label": "example.test",
                                "props": {"value": 4700, "label": "AI身份", "change": "",
                                          "period": "两周", "suffix": "+",
                                          "source_ref": "https://example.test/muse"}},
                               {"shot_id": "shot-2", "start_frame": 30, "end_frame": 60,
                                "component_id": "video", "title": "真实视频",
                                "asset_src": video.timeline_src, "source_label": "example.test",
                                "props": {"start_seconds": 0, "fit": "contain"}}],
                        captions=[{"text": "观点：这是测试文案。", "start_ms": 0.0, "end_ms": 3600.0}])
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
    visual_note = "原图区域已按像素实测，保持普通聊天参照可见"
    state = VideoState(**job_context(job), run_id="unit-editing-context", action="produce",
                       extras={"human_feedback": {"director": {
                           "decision": "revise", "note": visual_note, "applied": True,
                           "timeline": {"shots": [{"shot_id": "obsolete-plan"}]},
                       }}},
                       asset_metadata={audio.asset_id: {"alignment": {"origin": "state copy should not leak"}},
                                       video.asset_id: {"duration_seconds": 99, "alignment": {"origin": "state leak"}}})

    with pytest.raises(ValueError, match="剪辑模型预检未通过"):
        node.render_video(job, "final", state=state)

    assert len(calls) == 1
    job_id, revision, role, context, command_id, schema = calls[0]
    assert (job_id, revision, role, command_id) == (
        job.job_id, job.revision, "editing", "unit-editing-context")
    assert schema["title"] == "EditingAdvice"
    assert set(context["extras"]) == {"human_feedback", "production_bindings", "media_coverage_report"}
    assert context["extras"]["human_feedback"] == {"director": {
        "decision": "revise", "note": visual_note, "applied": True,
    }}
    counter_contract = context["extras"]["production_bindings"]["Rve-StatCounter"]
    assert counter_contract["chart"] is False
    assert counter_contract["sourced"] is True
    assert counter_contract["used_shot_ids"] == ["shot-1"]
    assert counter_contract["schema"]["required"] == [
        "value", "label", "change", "period", "suffix", "source_ref",
    ]
    coverage = context["extras"]["media_coverage_report"]
    assert coverage["actual_media_frames"] == 30
    assert coverage["actual_chart_frames"] == 0
    assert coverage["actual_visual_frames"] == 30
    assert coverage["actual_media_ratio"] == 0.5
    assert coverage["actual_chart_ratio"] == 0.0
    assert state["extras"]["human_feedback"]["director"]["timeline"]["shots"][0]["shot_id"] == "obsolete-plan"
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
    assert "audio_report" not in context["extras"]
    assert "timeline" not in context["extras"]["human_feedback"]["director"]
    assert repo.get_job(job.job_id).script.model_dump() == original_script
    assert repo.get_job(job.job_id).timeline.model_dump() == original_timeline
