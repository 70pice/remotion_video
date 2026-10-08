"""Director transport guidance follows real assets and component validation."""

import copy
import json

import pytest

from videoagents.contracts import Alignment, Asset, Brief, Script, ScriptSegment, Timeline
from videoagents.nodes.director import COMPONENT_PROPS_EXAMPLES, PROMPT, DirectorNode
from videoagents.services.jobs import JobService
from videoagents.state import VideoState, job_context
from videoagents.storage import Repository
from videoagents.tools.components import component_study_payload
from videoagents.tools.timeline import (
    asset_renderable,
    media_coverage_report,
    validate_media_coverage,
    validate_timeline,
)


def valid_study(usage="unspecified", **overrides):
    payload = component_study_payload(usage)
    value = {
        "manifest_fingerprint": payload["manifest_fingerprint"],
        "source_fingerprint": payload["source_fingerprint"],
        "usage": usage,
        "reviewed_preset_ids": payload["all_preset_ids"],
        "allowed_component_ids": payload["allowed_component_ids"],
        "video_first": True,
        "selection_principles": ["视频优先", "证据对应", "解释关系", "控制阅读负担"],
        "component_groups": [
            {"group": "VideoAgents", "use": "承载真实素材、数据、步骤和结论"},
            {"group": "Snapcn", "use": "适合 AI 产品、问题引入和文字动效"},
            {"group": "RVE", "use": "适合图表、数字和对比"},
            {"group": "Remocn", "use": "适合搜索、Agent 与代码概念"},
            {"group": "RemotionUI", "use": "适合数据流和代码展示"},
            {"group": "Bits", "use": "适合对话、指标和巡看"},
            {"group": "Talkcraft", "use": "适合非商业短视频节目化包装"},
        ],
        "limits": ["学习来自组件说明、路径和源码 hash，没有逐像素复看全部动画"],
    }
    value.update(overrides)
    return value


def director_job(tmp_path, image=True, video=False, video_seconds=2.5, usage="unspecified", production=False):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="Muse", target_seconds=2, width=1080 if production else 240,
                                height=1920 if production else 426, fps=30 if production else 15,
                                usage=usage))
    audio = Asset(asset_id="unit-audio", name="unit.wav", role="audio", mime_type="audio/wav", size_bytes=1,
                  sha256="a" * 64, artifact_id="unit-audio-artifact", url="/api/artifacts/unit-audio-artifact",
                  timeline_src=f"videoagents/{job.job_id}/assets/unit.wav")
    assets = [audio]
    if image:
        assets.append(Asset(asset_id="unit-image", name="unit.png", role="evidence", mime_type="image/png",
                            size_bytes=1, sha256="b" * 64, artifact_id="unit-image-artifact",
                            url="/api/artifacts/unit-image-artifact", source_url="https://example.test/muse",
                            timeline_src=f"videoagents/{job.job_id}/assets/unit.png"))
    if video:
        assets.append(Asset(asset_id="unit-video", name="unit.mp4", role="evidence", mime_type="video/mp4",
                            size_bytes=1, sha256="c" * 64, artifact_id="unit-video-artifact",
                            url="/api/artifacts/unit-video-artifact", source_url="https://example.test/muse",
                            timeline_src=f"videoagents/{job.job_id}/assets/unit.mp4"))
    script = Script(title="Muse", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：这是测试文案。",
                                            source_refs=["https://example.test/muse"],
                                            asset_ids=["unit-video"] if video else [])])
    job = repo.update_job(job.job_id, job.revision, script=script, assets=assets)
    if video:
        repo.update_asset_metadata("unit-video", {"duration_seconds": video_seconds, "width": 960, "height": 540})
    alignment = Alignment(origin="manual", verified=True, audio_sha256=audio.sha256,
                          segments=[{"segment_id": "s1", "text": script.segments[0].narration,
                                     "start_ms": 0.0, "end_ms": 1800.0}])
    return DirectorNode(repo, service), job, audio, alignment


PENDING_REVIEW_LICENSE = "真实网页截图/来源图片；尚未确认再利用许可，请在发布审核时核验"


def with_license(job, repo, **notes):
    assets = [asset.model_copy(update={"license_note": notes[asset.asset_id]})
              if asset.asset_id in notes else asset for asset in job.assets]
    return repo.update_job(job.job_id, job.revision, assets=assets)


def test_director_returns_only_shots_and_keeps_provider_alignment_in_code(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    state = VideoState(**job_context(job), run_id="unit-compact-director",
        asset_metadata={audio.asset_id: {"duration_seconds": 2.0, "alignment": alignment.model_dump()},
                        "unit-image": {"description": "对应产品截图"}},
        extras={"component_study": valid_study(job.brief.usage)})
    original = copy.deepcopy(state)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert set(output_schema["properties"]) == {"shots"}
        assert "alignment" not in context["asset_metadata"][audio.asset_id]
        assert context["timeline"]["captions"][0]["end_ms"] == 1800.0
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    result = node.plan(job, audio, alignment, 2.0, state=state)
    assert result.audio_src == audio.timeline_src
    assert [caption.model_dump() for caption in result.captions] == [
        {"text": alignment.segments[0].text, "start_ms": 0.0, "end_ms": 1800.0}]
    assert result.duration_in_frames == 30
    assert state == original


def test_director_rounds_fractional_audio_duration_up_to_preserve_the_tail(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)

    result = node.plan(job, audio, alignment, 2.001)

    assert result.duration_in_frames == 31
    assert result.duration_in_frames / result.fps > 2.001


def test_visual_rebuild_uses_model_instead_of_reusing_completed_timeline(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    old = node.plan(job, audio, alignment, 2.0)
    old.shots[0].component_id = "keyword"
    old.shots[0].asset_src = None
    old.shots[0].props = {}
    job = node.repo.update_job(job.job_id, job.revision, timeline=old)
    state = VideoState(**job_context(job), run_id="unit-rebuild",
                       gate_issues=["素材覆盖不足"], pending_snapshot={"stage": "director"},
                       extras={"component_study": valid_study(job.brief.usage), "timeline_rebuild": True})
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        assert context["timeline"] != old.model_dump()
        assert context["timeline"]["shots"][0]["component_id"] == "evidence"
        assert context["extras"]["timeline_rebuild"] is True
        assert context["extras"]["media_coverage"]["actual_media_ratio"] == 1
        assert context["extras"]["media_coverage"]["required"] is True
        assert "至少覆盖 22 帧（全片 30 帧）" in instruction
        assert "真实图片/视频及有来源、对应当前旁白的数据图表合计" in instruction
        assert "合规比例图无需 asset_src" in instruction
        assert "asset_src=null 的纯解释镜头" not in instruction
        assert context["extras"]["timeline_repair_issues"] == ["素材覆盖不足"]
        shot = dict(context["timeline"]["shots"][0], title="重新选择素材的镜头",
                    component_id="image_focus", asset_src=job.assets[1].timeline_src)
        return {"shots": [shot]}

    monkeypatch.setattr(node.model, "call", model)
    result = node.plan(job, audio, alignment, 2.0, state=state)
    assert calls == ["director"]
    assert result.shots[0].title != old.shots[0].title
    assert result.audio_src == old.audio_src and result.captions == old.captions


@pytest.mark.parametrize("note,expected", [
    ("不改配音或字幕，只放大图表", False),
    ("不要重配音，保留现有声音", False),
    ("无需再次调整音频", False),
    ("不更改配音，只修改画面", False),
    ("不要调整语速", False),
    ("图表改大，调整配音的音量", True),
    ("不要改配音，但是语速太快", True),
    ("不能不改配音", True),
    ("读音错误，需要重新合成", True),
    ("保持当前声音，重新编排镜头", False),
])
def test_voice_revision_detection_respects_negated_visual_feedback(note, expected):
    assert DirectorNode._needs_voice_revision(note) is expected


def test_visual_rebuild_without_director_model_cannot_render_old_timeline(tmp_path, monkeypatch):
    from videoagents.providers.llm import CapabilityMissing

    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    old = node.plan(job, audio, alignment, 2.0)
    job = node.repo.update_job(job.job_id, job.revision, timeline=old)
    state = VideoState(**job_context(job), extras={"timeline_rebuild": True})
    with pytest.raises(CapabilityMissing, match="重做画面需要启用导演模型"):
        node.plan(job, audio, alignment, 2.0, state=state)


@pytest.mark.parametrize("with_feedback", [False, True])
def test_editing_blocked_director_resume_replans_the_current_timeline(tmp_path, monkeypatch, with_feedback):
    node, job, audio, alignment = director_job(tmp_path, production=True)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    state = VideoState(**job_context(job), extras={"component_study": valid_study(job.brief.usage)})
    old = node.plan(job, audio, alignment, 3.0, state=state)
    current = old.model_copy(update={"shots": [old.shots[0].model_copy(update={"title": "已返工但仍缺中文分工"})]})
    job = node.repo.update_job(job.job_id, job.revision, timeline=current)
    node.repo.update_asset_metadata(audio.asset_id, {
        "duration_seconds": 3.0, "alignment": alignment.model_dump(), "origin": "manual",
    })
    node.service.write_json(job, "component-study.json", valid_study(job.brief.usage), "component_study")
    job = node.repo.get_job(job.job_id)
    extras = {"component_study": valid_study(job.brief.usage)}
    if with_feedback:
        extras["human_feedback"] = {"director": {
            "decision": "revise", "pending_token": "visual-only", "note": "用中文解释真人和AI的分工",
            "timeline": old.model_dump(), "applied": False,
        }}
    issues = ["剪辑发现英文整图无法解释真人和AI的分工"]
    state = VideoState(**job_context(job), action="produce", run_id="visual-only", thread_id="visual-only",
        resume_command_id="repair-director", audio_asset_id=audio.asset_id, alignment=alignment.model_dump(),
        duration_seconds=3.0, pending_snapshot={"stage": "director"}, gate_issues=issues, extras=extras)
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(role)
        assert context["timeline"] == current.model_dump()
        assert context["extras"]["timeline_repair_issues"] == issues
        return {"shots": [dict(context["timeline"]["shots"][0], title="真人和AI各负责什么")]}

    monkeypatch.setattr(node.model, "call", model)
    result = node(state)
    assert calls == ["director"]
    assert result["route"] == "editing"
    saved = node.repo.get_job(job.job_id).timeline
    assert saved.shots[0].title == "真人和AI各负责什么"
    assert saved.audio_src == old.audio_src and saved.captions == old.captions


def test_editing_blocked_director_without_model_stays_paused(tmp_path, monkeypatch):
    from videoagents.providers.llm import CapabilityMissing

    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    old = node.plan(job, audio, alignment, 2.0)
    job = node.repo.update_job(job.job_id, job.revision, timeline=old)
    state = VideoState(**job_context(job), pending_snapshot={"stage": "director"}, gate_issues=["英文整图需返工"])
    with pytest.raises(CapabilityMissing, match="导演镜头仍有待修问题"):
        node.plan(job, audio, alignment, 2.0, state=state)


@pytest.mark.parametrize("applied,voice_token,director_token,target,expected", [
    (True, "voice-run", "voice-run", "voice", True),
    (False, "voice-run", "voice-run", "voice", False),
    (True, "older-run", "voice-run", "voice", False),
    (True, "voice-run", "new-director-run", "voice", False),
    (True, "voice-run", "voice-run", "director", False),
])
def test_mixed_feedback_requires_the_same_completed_voice_revision(
    applied, voice_token, director_token, target, expected,
):
    state = VideoState(extras={"voice_rebuild_id": "voice-run", "human_feedback": {
        "voice": {"decision": "revise", "pending_token": voice_token,
                  "applied": applied, "applied_target": target},
    }})
    assert DirectorNode._voice_feedback_was_applied(state, {"pending_token": director_token}) is expected


@pytest.mark.parametrize("source_changed", [False, True])
def test_visual_component_source_revision_can_reuse_the_correct_shot_plan(tmp_path, monkeypatch, source_changed):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    old = node.plan(job, audio, alignment, 2.0)
    job = node.repo.update_job(job.job_id, job.revision, timeline=old)
    node.repo.update_asset_metadata(audio.asset_id, {"duration_seconds": 2.0,
                                                   "alignment": alignment.model_dump(), "origin": "manual"})
    prior_study = valid_study(job.brief.usage)
    node.service.write_json(job, "component-study.json", prior_study, "component_study")
    job = node.repo.get_job(job.job_id)
    feedback = {"decision": "revise", "pending_token": "visual-only", "note": "保留当前声音，只修图表布局",
                "timeline": old.model_dump(), "applied": False}
    state = VideoState(**job_context(job), action="produce", run_id="visual-only", thread_id="visual-only",
                       audio_asset_id=audio.asset_id, alignment=alignment.model_dump(), duration_seconds=2.0,
                       extras={"timeline_rebuild": True, "component_study": prior_study,
                               "human_feedback": {"director": feedback}})

    def plan(*args, **kwargs):
        state["extras"]["component_study"] = {**prior_study, "source_fingerprint": "b" * 64 if source_changed else prior_study["source_fingerprint"]}
        return old

    monkeypatch.setattr(node, "plan", plan)
    result = node(state)
    assert result["route"] == ("editing" if source_changed else "await_input")
    if not source_changed:
        assert "人工返工未产生分镜修改" in node.repo.get_job(job.job_id).message


def test_voice_rebuild_plans_using_new_measured_captions_not_feedback_snapshot(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    old = node.plan(job, audio, alignment, 2.0)
    new_audio = audio.model_copy(update={"asset_id": "new-audio", "sha256": "c" * 64,
                                        "timeline_src": f"videoagents/{job.job_id}/assets/new.wav"})
    new_alignment = alignment.model_copy(update={"audio_sha256": new_audio.sha256, "segments": [
        alignment.segments[0].model_copy(update={"start_ms": 500.0, "end_ms": 3800.0}),
    ]})
    job = node.repo.update_job(job.job_id, job.revision, timeline=old, assets=[*job.assets, new_audio])
    feedback = {"decision": "revise", "note": "重配音并稳定图表视野", "pending_token": "voice-run",
                "timeline": old.model_dump(), "applied": False}
    state = VideoState(**job_context(job), extras={
        "component_study": valid_study(job.brief.usage), "timeline_rebuild": True,
        "voice_rebuild_id": "voice-run", "human_feedback": {
            "director": feedback,
            "voice": {**feedback, "applied": True, "applied_target": "voice"},
        },
    })
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert context["timeline"]["duration_in_frames"] == 60
        assert context["timeline"]["audio_src"] == new_audio.timeline_src
        assert context["timeline"]["captions"][0]["start_ms"] == 500
        assert context["timeline"]["captions"][0]["end_ms"] == 3800
        assert context["extras"]["human_feedback"]["director"]["timeline"] == old.model_dump()
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    result = node.plan(job, new_audio, new_alignment, 4.0, state=state)
    assert result.duration_in_frames == 60
    assert result.audio_src == new_audio.timeline_src
    assert result.captions[0].end_ms == 3800


def test_director_does_not_request_voice_again_after_the_same_mixed_note_was_applied(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: False)
    old = node.plan(job, audio, alignment, 2.0)
    job = node.repo.update_job(job.job_id, job.revision, timeline=old)
    node.repo.update_asset_metadata(audio.asset_id, {"duration_seconds": 2.0,
                                                   "alignment": alignment.model_dump(), "origin": "manual"})
    feedback = {"decision": "revise", "pending_token": "voice-run", "note": "重配音并调整图表",
                "timeline": old.model_dump(), "applied": False}
    state = VideoState(**job_context(job), action="produce", run_id="voice-run", thread_id="voice-run",
                       audio_asset_id=audio.asset_id,
                       alignment=alignment.model_dump(), duration_seconds=2.0, extras={
                           "voice_rebuild_id": "voice-run", "timeline_rebuild": True,
                           "human_feedback": {"director": feedback,
                                              "voice": {**feedback, "applied": True, "applied_target": "voice"}},
                       })
    revised = old.model_copy(update={"shots": [old.shots[0].model_copy(update={"title": "稳定趋势视野"})]})
    monkeypatch.setattr(node, "plan", lambda *args, **kwargs: revised)
    result = node(state)
    assert result["route"] == "editing"
    assert result["extras"]["human_feedback"]["director"]["applied"] is True
    assert node.repo.get_job(job.job_id).timeline.shots[0].title == "稳定趋势视野"


def test_director_node_retains_new_component_study_in_job_and_handoff(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    node.repo.update_asset_metadata(audio.asset_id, {
        "duration_seconds": 2.0, "alignment": alignment.model_dump(), "origin": "manual",
    })
    state = VideoState(**job_context(job), run_id="unit-study-handoff",
                       thread_id="unit-study-handoff", action="produce", extras={})
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(output_schema)
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    result = node(state)
    saved = node.repo.get_job(job.job_id)
    assert result["route"] == "editing"
    assert {item.kind for item in saved.artifacts} >= {"component_study", "storyboard", "timeline"}
    assert result["extras"]["component_study"] == valid_study(job.brief.usage)
    assert saved.timeline.audio_src == audio.timeline_src
    assert result["alignment"] == alignment.model_dump()

    # Re-entering this revision uses the committed study instead of studying again.
    node.plan(saved, audio, alignment, 2.0, state=result)
    assert sum("reviewed_preset_ids" in json.dumps(schema) for schema in calls) == 1


@pytest.mark.parametrize("image", [False, True])
def test_director_guidance_limits_assets_and_describes_valid_component_props(tmp_path, monkeypatch, image):
    node, job, audio, alignment = director_job(tmp_path, image)
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((instruction, context, output_schema))
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    research = {"visuals": [{"image_url": "https://cdn.example.test/muse.png",
                              "artifact_url": "/api/artifacts/unprovided-image"}]}
    node.plan(job, audio, alignment, 2.0, research)

    assert len(calls) == 2
    assert "组件研究助理" in calls[0][0]
    assert set(calls[0][1]) == {"brief"}
    instruction, context, schema = calls[1]
    assert instruction.startswith(PROMPT)
    assert ("本次提交的硬约束" in instruction) is image
    assert set(context) == {"brief", "script", "timeline", "research", "assets", "asset_metadata", "extras"}
    assert "component_study" in context["extras"]
    assert context["extras"]["media_coverage"]["target_ratio"] == 0.7
    assert context["extras"]["media_coverage"]["required"] is image
    assert "component_props_examples" not in context
    expected = [asset.timeline_src for asset in job.assets if asset.mime_type.startswith("image/")] + [None]
    assert schema["$defs"]["Shot"]["properties"]["asset_src"]["enum"] == expected
    components = schema["$defs"]["Shot"]["properties"]["component_id"]["enum"]
    assert len(components) == 161
    assert "video" in components
    assert "Snapcn-TextReveal" in components
    assert "Talkcraft-crash-zoom-punch" in components
    assert "research.visuals" in instruction and "artifact_url" in instruction and "不得" in instruction
    assert "asset_src=null" in instruction and "字符串数组" in instruction
    assert "enum" not in Timeline.model_json_schema()["$defs"]["Shot"]["properties"]["asset_src"]
    props = COMPONENT_PROPS_EXAMPLES
    assert json.dumps(props, ensure_ascii=False, separators=(",", ":")) in instruction
    assert props["steps"]["layout"] == "flow"
    assert all(set(item) == {"title", "body", "reveal_frame"} for item in props["steps"]["items"])
    assert [item["reveal_frame"] for item in props["steps"]["items"]] == [0, 15]
    assert all(set(item) == {"label", "value", "detail", "reveal_frame"} for item in props["data"]["items"])
    assert [item["reveal_frame"] for item in props["data"]["items"]] == [0, 15]
    assert set(props["comparison"]) == {"left_title", "left_body", "right_title", "right_body", "right_reveal_frame"}
    assert props["comparison"]["right_reveal_frame"] == 15
    assert set(props["image_focus"]) == {"focus_cues"}
    assert [item["frame"] for item in props["image_focus"]["focus_cues"]] == [0, 120, 300]
    assert set(props["image_focus"]["focus_cues"][1]["region"]) == {"x", "y", "width", "height"}
    assert set(props["evidence"]["highlight"]) == {"x", "y", "width", "height"}
    assert set(props["video"]) == {"start_seconds", "end_seconds", "fit", "crop"}
    for requirement in [
        "steps.items：1–4 个对象", "必填 title（≤48），可选 body（≤96）",
        "data.items：1–4 个对象", "必填 label（≤48）、value（≤40），可选 detail（≤64）",
        "必须齐全 left_title/right_title（≤48）与 left_body/right_body（≤160）",
        "eyebrow（≤48）", "keyword（≤40）", "call_to_action（≤72）",
        "video：可选 start_seconds（默认 0）、end_seconds（>start 且 ≤实测时长）、fit（contain|cover）、crop",
        "image_focus：可选 focal_x/focal_y/crop 或 focus_cues",
        "x+width≤1、y+height≤1", "width/height>0", "已提供的文字必须非空",
        "title≤100 字、body≤240 字、source_label≤160 字",
        "extras.media_coverage", "actual_media_ratio", "超过 70%",
        "约占内容区 70%–85%", "跨入无关联段落",
    ]:
        assert requirement in instruction
    assert "HyperFrames" not in instruction
    if image:
        for component, example in props.items():
            if component == "video":
                continue
            candidate = copy.deepcopy(context["timeline"])
            candidate["shots"][0].update(component_id=component, props=example)
            if component == "image_focus":
                # The continuous-reading example has three real camera holds,
                # unlike this fixture's original two-second single image.
                candidate["duration_in_frames"] = 450
                candidate["shots"][0]["end_frame"] = 450
            if component in {"image_focus", "evidence"}:
                candidate["shots"][0].update(asset_src=expected[0], source_label="example.test")
            validate_timeline(Timeline.model_validate(candidate), job)


def test_verification_only_image_is_excluded_from_schema_coverage_and_timeline(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, image=True)
    image = next(asset for asset in job.assets if asset.mime_type.startswith("image/"))
    blocked = image.model_copy(update={
        "license_note": "真实网页截图；尚未确认再利用许可，仅作核验依据，不直接发布",
    })
    job = node.repo.update_job(job.job_id, job.revision, assets=[audio, blocked])
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((context, output_schema))
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    result = node.plan(job, audio, alignment, 2.0)

    assert not asset_renderable(blocked)
    assert calls[1][0]["extras"]["media_coverage"]["required"] is False
    assert calls[1][0]["extras"]["media_coverage"]["eligible_capacity_frames"] == 0
    assert calls[1][1]["$defs"]["Shot"]["properties"]["asset_src"]["enum"] == [None]
    assert result.shots[0].asset_src is None
    invalid = result.model_copy(update={"shots": [result.shots[0].model_copy(update={
        "component_id": "evidence", "asset_src": blocked.timeline_src, "source_label": "example.test",
    })]})
    with pytest.raises(ValueError, match="许可回执明确仅供核验"):
        validate_timeline(invalid, job)


def test_pending_review_assets_enter_director_schema_baseline_and_coverage(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, image=True, video=True, video_seconds=2.5)
    image = next(asset for asset in job.assets if asset.mime_type.startswith("image/"))
    video = next(asset for asset in job.assets if asset.mime_type.startswith("video/"))
    job = with_license(job, node.repo, **{
        image.asset_id: PENDING_REVIEW_LICENSE,
        video.asset_id: PENDING_REVIEW_LICENSE.replace("图片", "视频"),
    })
    monkeypatch.setattr(node.model, "available", lambda role: True)
    calls = []

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((context, output_schema))
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        assert context["timeline"]["shots"][0]["component_id"] == "video"
        assert context["timeline"]["shots"][0]["asset_src"] == video.timeline_src
        coverage = context["extras"]["media_coverage"]
        assert coverage["required"] is True
        assert coverage["eligible_capacity_frames"] == 30
        assert coverage["actual_media_frames"] == 30
        assert coverage["actual_media_ratio"] == 1.0
        assert context["asset_metadata"][image.asset_id]["renderable"] is True
        assert context["asset_metadata"][video.asset_id]["renderable"] is True
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    timeline = node.plan(job, audio, alignment, 2.0)

    schema = calls[1][1]
    allowed_sources = schema["$defs"]["Shot"]["properties"]["asset_src"]["enum"]
    assert image.timeline_src in allowed_sources
    assert video.timeline_src in allowed_sources
    assert timeline.shots[0].component_id == "video"
    assert timeline.shots[0].asset_src == video.timeline_src


def test_pending_review_assets_still_make_seventy_percent_media_required(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, image=True)
    image = next(asset for asset in job.assets if asset.mime_type.startswith("image/"))
    job = with_license(job, node.repo, **{image.asset_id: PENDING_REVIEW_LICENSE})
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        assert context["extras"]["media_coverage"]["required"] is True
        shot = copy.deepcopy(context["timeline"]["shots"][0])
        shot.update(component_id="title", asset_src=None, source_label="", props={})
        return {"shots": [shot]}

    monkeypatch.setattr(node.model, "call", model)

    with pytest.raises(ValueError, match="足以覆盖全片超过 70%.*实际图片/视频镜头仅覆盖 0.0%"):
        node.plan(job, audio, alignment, 2.0)


def test_director_filters_noncommercial_presets_from_commercial_jobs(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, usage="commercial")
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((instruction, output_schema))
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    node.plan(job, audio, alignment, 2.0)
    instruction, schema = calls[1]
    components = schema["$defs"]["Shot"]["properties"]["component_id"]["enum"]
    assert len(components) == 53
    assert "Snapcn-TextReveal" in components
    assert "video" in components
    assert all(not component.startswith("Talkcraft-") for component in components)
    assert "Talkcraft-crash-zoom-punch" not in instruction


@pytest.mark.parametrize("component,props,asset_src,message", [
    ("image_focus", {}, "https://cdn.example.test/muse.png", "媒体路径"),
    ("image_focus", {}, "/api/artifacts/unit-image-artifact", "媒体路径"),
    ("steps", {"items": ["第一步", "第二步"]}, None, "字段不完整"),
    ("data", {"items": [{"label": "名称"}]}, None, "字段不完整"),
    ("comparison", {"left_title": "左"}, None, "非空四项"),
])
def test_director_still_rejects_external_assets_and_invalid_props(tmp_path, monkeypatch, component, props, asset_src, message):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        value = {"shots": copy.deepcopy(context["timeline"]["shots"])}
        value["shots"][0].update(component_id=component, props=props, asset_src=asset_src)
        return value

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match=message):
        node.plan(job, audio, alignment, 2.0)


@pytest.mark.parametrize("field,value", [
    ("audio_src", "different.wav"),
    ("captions", [{"text": "cannot replace", "start_ms": 0.0, "end_ms": 1900.0}]),
    ("duration_in_frames", 31), ("fps", 30), ("width", 1080), ("height", 1920),
    ("job_id", "other-job"), ("revision", 2),
])
def test_director_output_cannot_replace_measured_tracks_or_timeline_identity(tmp_path, monkeypatch, field, value):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        result = {"shots": copy.deepcopy(context["timeline"]["shots"]), field: value}
        return result

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match="Extra inputs"):
        node.plan(job, audio, alignment, 2.0)


@pytest.mark.parametrize("cuts", [
    [("hook", "提出问题", 0, 15), ("proof", "展示证据", 15, 40), ("answer", "回应问题", 40, 60)],
    [("continuous-proof", "连续演示证据", 0, 60)],
])
def test_director_can_split_merge_rename_and_retime_shots_across_narration_segments(tmp_path, monkeypatch, cuts):
    node, job, audio, _ = director_job(tmp_path)
    script = Script(title="问题与证据", origin="user", revision=job.revision, segments=[
        ScriptSegment(segment_id="s1", narration="问题是什么？"),
        ScriptSegment(segment_id="s2", narration="证据说明答案。"),
    ])
    job = node.repo.update_job(job.job_id, job.revision, script=script)
    alignment = Alignment(origin="manual", verified=True, audio_sha256=audio.sha256, segments=[
        {"segment_id": "s1", "text": "问题是什么？", "start_ms": 0.0, "end_ms": 1400.0},
        {"segment_id": "s2", "text": "证据说明答案。", "start_ms": 1500.0, "end_ms": 3800.0},
    ])
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        baseline = context["timeline"]["shots"]
        assert [(shot["start_frame"], shot["end_frame"]) for shot in baseline] == [(0, 22), (22, 60)]
        return {"shots": [dict(baseline[0], shot_id=identifier, title=title,
                              start_frame=start, end_frame=end) for identifier, title, start, end in cuts]}

    monkeypatch.setattr(node.model, "call", model)
    result = node.plan(job, audio, alignment, 4.0)

    assert [(shot.shot_id, shot.start_frame, shot.end_frame) for shot in result.shots] == [
        (identifier, start, end) for identifier, title, start, end in cuts]
    assert result.audio_src == audio.timeline_src
    assert result.duration_in_frames == 60
    assert (result.job_id, result.revision, result.width, result.height, result.fps) == (
        job.job_id, job.revision, job.brief.width, job.brief.height, job.brief.fps)
    assert [caption.model_dump() for caption in result.captions] == [
        {key: value for key, value in segment.model_dump().items() if key != "segment_id"}
        for segment in alignment.segments
    ]


@pytest.mark.parametrize("intervals,message", [
    ([], "at least 1"),
    ([("one", 0, 31)], "完整覆盖"),
    ([("one", 0, 29)], "完整覆盖"),
    ([("one", 1, 30)], "连续覆盖"),
    ([("one", 0, 15), ("two", 16, 31)], "连续覆盖"),
    ([("one", 0, 16), ("two", 15, 30)], "连续覆盖"),
    ([("same", 0, 15), ("same", 15, 30)], "ID 唯一"),
    ([("one", 0, 14), ("two", 14, 30)], "至少.*15.*帧"),
])
def test_director_free_cuts_still_require_valid_coverage_and_minimum_shot_length(tmp_path, monkeypatch, intervals, message):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        baseline = context["timeline"]["shots"][0]
        return {"shots": [dict(baseline, shot_id=identifier, start_frame=start, end_frame=end)
                          for identifier, start, end in intervals]}

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match=message):
        node.plan(job, audio, alignment, 2.0)


def test_director_free_cuts_cannot_overrun_a_video_excerpt(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, video=True, video_seconds=1.0)
    video = next(asset for asset in job.assets if asset.mime_type == "video/mp4")
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        baseline = context["timeline"]["shots"][0]
        return {"shots": [dict(baseline, shot_id="real-video", component_id="video", asset_src=video.timeline_src,
                              source_label="example.test", props={"start_seconds": 0.5}, end_frame=15),
                          dict(baseline, shot_id="next", start_frame=15, end_frame=30)]}

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match="截取区间必须.*覆盖镜头时长"):
        node.plan(job, audio, alignment, 2.0)


@pytest.mark.parametrize("model_available", [False, True])
@pytest.mark.parametrize("starts_ms", [(0.0, 200.0, 1500.0), (0.0, 1500.0, 1800.0), (0.0, 10.0, 1500.0)])
def test_short_narration_segments_are_not_forced_to_be_separate_shots(tmp_path, monkeypatch, model_available, starts_ms):
    node, job, audio, _ = director_job(tmp_path, image=False)
    script = Script(title="连续口播", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id=f"s{index}", narration=f"第{index}句话。")
                              for index in range(1, 4)])
    job = node.repo.update_job(job.job_id, job.revision, script=script)
    alignment = Alignment(origin="manual", verified=True, audio_sha256=audio.sha256, segments=[
        {"segment_id": segment.segment_id, "text": segment.narration,
         "start_ms": start, "end_ms": start + 1.0}
        for segment, start in zip(script.segments, starts_ms, strict=True)
    ])
    monkeypatch.setattr(node.model, "available", lambda role: model_available)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        return {"shots": [dict(context["timeline"]["shots"][0], shot_id="one-continuous-beat", end_frame=30)]}

    monkeypatch.setattr(node.model, "call", model)
    result = node.plan(job, audio, alignment, 2.0)
    assert result.shots[0].start_frame == 0 and result.shots[-1].end_frame == 30
    assert all(shot.end_frame - shot.start_frame >= 15 for shot in result.shots)
    assert [caption.text for caption in result.captions] == [segment.narration for segment in script.segments]
    assert result.shots[0].body == "".join(segment.narration for segment in script.segments)


@pytest.mark.parametrize("reject", [False, True])
def test_shared_final_state_is_read_without_committing_unvalidated_baseline(tmp_path, monkeypatch, reject):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: True)
    state = VideoState(**job_context(job), run_id="unit-original-command", resume_command_id="unit-resume-command",
        research={"sources": [{"url": "https://example.test/muse", "text": "已冻结的最终证据"}],
                  "tools": [{"status": "ok", "raw_result": "不可交接的工具过程"}]},
        asset_metadata={"unit-image": {"description": "最终图片描述", "provider_raw": "不可交接"}})
    original_state = copy.deepcopy(state)
    calls = []
    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((context, command_id))
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        assert state["timeline"] is None
        assert state["extras"]["component_study"] == valid_study(job.brief.usage)
        assert context["timeline"]["audio_src"] == audio.timeline_src
        value = {"shots": copy.deepcopy(context["timeline"]["shots"])}
        if reject:
            value["captions"] = [{"text": "cannot replace", "start_ms": 0.0, "end_ms": 1900.0}]
        return value
    monkeypatch.setattr(node.model, "call", model)
    if reject:
        with pytest.raises(ValueError, match="Extra inputs"):
            node.plan(job, audio, alignment, 2.0, {"sources": [{"text": "不应覆盖共享state"}]}, state=state)
    else:
        timeline = node.plan(job, audio, alignment, 2.0, {"sources": [{"text": "不应覆盖共享state"}]}, state=state)
        assert timeline.audio_src == audio.timeline_src
    assert calls[0][1] == "unit-resume-command:component-study"
    context, command = calls[1]
    assert context["research"]["sources"][0]["text"] == "已冻结的最终证据"
    assert "tools" not in context["research"]
    assert context["asset_metadata"]["unit-image"] == {"description": "最终图片描述", "renderable": True}
    assert context["asset_metadata"].get("unit-audio") == {}
    assert command == "unit-resume-command:timeline"
    expected_state = copy.deepcopy(original_state)
    expected_state["extras"] = {"component_study": valid_study(job.brief.usage)}
    assert state == expected_state and node.repo.get_job(job.job_id).timeline is None


@pytest.mark.parametrize("bad", ["missing_preset", "stale_fingerprint", "wrong_allowed"])
def test_director_rejects_incomplete_or_stale_component_study(tmp_path, monkeypatch, bad):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            study = valid_study(job.brief.usage)
            if bad == "missing_preset":
                study["reviewed_preset_ids"][-1] = study["reviewed_preset_ids"][0]
            elif bad == "stale_fingerprint":
                study["source_fingerprint"] = "0" * 64
            else:
                study["allowed_component_ids"] = study["allowed_component_ids"][:-1]
            return study
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match="组件学习"):
        node.plan(job, audio, alignment, 2.0)


def test_director_reuses_current_component_study_from_state(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path)
    state = VideoState(**job_context(job), run_id="unit-original-command",
                       extras={"component_study": valid_study(job.brief.usage)})
    monkeypatch.setattr(node.model, "available", lambda role: True)
    calls = []

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(command_id)
        assert "reviewed_preset_ids" not in json.dumps(output_schema or {})
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    timeline = node.plan(job, audio, alignment, 2.0, state=state)

    assert timeline.audio_src == audio.timeline_src
    assert calls == ["unit-original-command:timeline"]
    assert state["extras"]["component_study"] == valid_study(job.brief.usage)


def test_production_director_requires_component_study_when_model_is_disabled(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, production=True)
    monkeypatch.setattr(node.model, "available", lambda role: False)

    with pytest.raises(Exception, match="必须先完成全部竖版组件学习"):
        node.plan(job, audio, alignment, 2.0, state=VideoState(**job_context(job), run_id="unit"))


def test_production_manual_timeline_accepts_valid_component_study_without_model(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, production=True)
    timeline = Timeline(job_id=job.job_id, revision=job.revision, width=job.brief.width,
                        height=job.brief.height, fps=job.brief.fps, duration_in_frames=60,
                        audio_src=audio.timeline_src,
                        shots=[{"shot_id": "shot-1", "start_frame": 0, "end_frame": 60,
                                "component_id": "title", "title": "人工分镜"}],
                        captions=[{"text": alignment.segments[0].text, "start_ms": 0.0, "end_ms": 1800.0}])
    job = node.repo.update_job(job.job_id, job.revision, timeline=timeline)
    state = VideoState(**job_context(job), run_id="unit",
                       extras={"component_study": valid_study(job.brief.usage)})
    monkeypatch.setattr(node.model, "available", lambda role: False)

    result = node.plan(job, audio, alignment, 2.0, state=state)

    assert result == timeline


def test_stale_component_study_is_refreshed_when_director_model_is_enabled(tmp_path, monkeypatch):
    # Study renewal is independent of images; a two-second evidence shot is
    # intentionally invalid under production reading-duration constraints.
    node, job, audio, alignment = director_job(tmp_path, production=True, image=False)
    stale = valid_study(job.brief.usage, source_fingerprint="0" * 64)
    state = VideoState(**job_context(job), run_id="unit-refresh", extras={"component_study": stale})
    monkeypatch.setattr(node.model, "available", lambda role: True)
    calls = []

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append(command_id)
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    node.plan(job, audio, alignment, 2.0, state=state)

    assert calls == ["unit-refresh:component-study", "unit-refresh:timeline"]
    assert state["extras"]["component_study"] == valid_study(job.brief.usage)


@pytest.mark.parametrize("video_seconds,expected_component", [(2.5, "video"), (1.0, "evidence")])
def test_director_baseline_prefers_video_only_when_it_covers_the_shot(tmp_path, monkeypatch, video_seconds, expected_component):
    node, job, audio, alignment = director_job(tmp_path, image=True, video=True, video_seconds=video_seconds)
    monkeypatch.setattr(node.model, "available", lambda role: False)

    timeline = node.plan(job, audio, alignment, 2.0)

    assert timeline.shots[0].component_id == expected_component
    if expected_component == "video":
        assert timeline.shots[0].asset_src.endswith(".mp4")
        assert timeline.shots[0].props == {"start_seconds": 0, "fit": "contain"}


@pytest.mark.parametrize("video_seconds,expected_component", [(2.5, "video"), (1.0, "evidence")])
def test_director_baseline_matches_source_refs_video_before_image_when_duration_covers(tmp_path, monkeypatch, video_seconds, expected_component):
    node, job, audio, alignment = director_job(tmp_path, image=True, video=True, video_seconds=video_seconds)
    image = next(asset for asset in job.assets if asset.mime_type.startswith("image/"))
    video = next(asset for asset in job.assets if asset.mime_type.startswith("video/"))
    job = with_license(job, node.repo, **{
        image.asset_id: PENDING_REVIEW_LICENSE,
        video.asset_id: PENDING_REVIEW_LICENSE.replace("图片", "视频"),
    })
    script = Script(title="Muse", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：这是测试文案。",
                                            source_refs=["https://example.test/muse"], asset_ids=[])])
    job = node.repo.update_job(job.job_id, job.revision, script=script)
    monkeypatch.setattr(node.model, "available", lambda role: False)

    timeline = node.plan(job, audio, alignment, 2.0)

    assert timeline.shots[0].component_id == expected_component
    if expected_component == "video":
        assert timeline.shots[0].asset_src == video.timeline_src
    else:
        assert timeline.shots[0].asset_src == image.timeline_src


def test_model_director_requires_seventy_percent_media_when_linked_supply_is_sufficient(tmp_path, monkeypatch):
    node, job, audio, alignment = director_job(tmp_path, image=True)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        if "reviewed_preset_ids" in json.dumps(output_schema or {}):
            return valid_study(job.brief.usage)
        assert context["extras"]["media_coverage"]["required"] is True
        shot = copy.deepcopy(context["timeline"]["shots"][0])
        shot.update(component_id="title", asset_src=None, source_label="", props={})
        return {"shots": [shot]}

    monkeypatch.setattr(node.model, "call", model)

    with pytest.raises(ValueError, match="足以覆盖全片超过 70%.*实际图片/视频镜头仅覆盖 0.0%"):
        node.plan(job, audio, alignment, 2.0)


def test_media_coverage_must_be_strictly_above_seventy_percent(tmp_path):
    node, job, audio, _ = director_job(tmp_path, image=True)
    image = next(asset for asset in job.assets if asset.mime_type.startswith("image/"))
    base = {
        "job_id": job.job_id,
        "revision": job.revision,
        "width": job.brief.width,
        "height": job.brief.height,
        "fps": job.brief.fps,
        "duration_in_frames": 100,
        "audio_src": audio.timeline_src,
        "captions": [{"text": job.script.segments[0].narration, "start_ms": 0.0, "end_ms": 6000.0}],
    }

    def candidate(media_end: int) -> Timeline:
        return Timeline.model_validate({**base, "shots": [
            {"shot_id": "media", "start_frame": 0, "end_frame": media_end,
             "component_id": "evidence", "title": "真实证据", "asset_src": image.timeline_src,
             "source_label": "example.test"},
            {"shot_id": "explanation", "start_frame": media_end, "end_frame": 100,
             "component_id": "title", "title": "解释结论"},
        ]})

    with pytest.raises(ValueError, match="实际图片/视频镜头仅覆盖 70.0%"):
        validate_media_coverage(candidate(70), job)

    report = validate_media_coverage(candidate(71), job)
    assert report["target_frames"] == 71
    assert report["actual_media_ratio"] == 0.71


def test_media_coverage_allows_measurable_fallback_but_rejects_unrelated_media(tmp_path):
    node, job, audio, _ = director_job(tmp_path, image=True)
    image = next(asset for asset in job.assets if asset.mime_type.startswith("image/"))
    script = Script(title="两段内容", origin="user", revision=job.revision, segments=[
        ScriptSegment(segment_id="s1", narration="第一段证据。",
                      source_refs=["https://example.test/muse"]),
        ScriptSegment(segment_id="s2", narration="第二段没有素材。"),
    ])
    job = node.repo.update_job(job.job_id, job.revision, script=script)
    base = {
        "job_id": job.job_id,
        "revision": job.revision,
        "width": job.brief.width,
        "height": job.brief.height,
        "fps": job.brief.fps,
        "duration_in_frames": 30,
        "audio_src": audio.timeline_src,
        "captions": [
            {"text": "第一段证据。", "start_ms": 0.0, "end_ms": 800.0},
            {"text": "第二段没有素材。", "start_ms": 1000.0, "end_ms": 1900.0},
        ],
    }
    fallback = Timeline.model_validate({**base, "shots": [{
        "shot_id": "text-fallback", "start_frame": 0, "end_frame": 30,
        "component_id": "title", "title": "素材不足时使用解释画面",
    }]})

    report = validate_media_coverage(fallback, job)

    assert report["eligible_capacity_ratio"] == 0.5
    assert report["actual_media_ratio"] == 0.0
    assert report["required"] is False

    unrelated = Timeline.model_validate({**base, "shots": [
        {"shot_id": "linked", "start_frame": 0, "end_frame": 15,
         "component_id": "title", "title": "第一段"},
        {"shot_id": "unrelated", "start_frame": 15, "end_frame": 30,
         "component_id": "evidence", "title": "错误复用", "asset_src": image.timeline_src,
         "source_label": "example.test"},
    ]})
    with pytest.raises(ValueError, match="语义关联"):
        media_coverage_report(unrelated, job)


def test_media_capacity_does_not_count_the_same_video_duration_twice(tmp_path):
    node, job, audio, _ = director_job(
        tmp_path,
        image=False,
        video=True,
        video_seconds=1.0,
    )
    video = next(asset for asset in job.assets if asset.mime_type.startswith("video/"))
    script = Script(title="两段视频", origin="user", revision=job.revision, segments=[
        ScriptSegment(segment_id="s1", narration="第一段。", asset_ids=[video.asset_id]),
        ScriptSegment(segment_id="s2", narration="第二段。", asset_ids=[video.asset_id]),
    ])
    job = node.repo.update_job(job.job_id, job.revision, script=script)
    candidate = Timeline(
        job_id=job.job_id,
        revision=job.revision,
        width=job.brief.width,
        height=job.brief.height,
        fps=job.brief.fps,
        duration_in_frames=30,
        audio_src=audio.timeline_src,
        shots=[{"shot_id": "fallback", "start_frame": 0, "end_frame": 30,
                "component_id": "title", "title": "视频时长不足"}],
        captions=[
            {"text": "第一段。", "start_ms": 0.0, "end_ms": 800.0},
            {"text": "第二段。", "start_ms": 1000.0, "end_ms": 1900.0},
        ],
    )

    report = media_coverage_report(
        candidate,
        job,
        {video.asset_id: {"duration_seconds": 1.0}},
    )

    assert report["eligible_capacity_frames"] == 15
    assert report["eligible_capacity_ratio"] == 0.5
    assert report["required"] is False
