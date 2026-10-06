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
from videoagents.tools.timeline import media_coverage_report, validate_media_coverage, validate_timeline


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
    assert result["route"] == "timeline_gate"
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
    instruction, context, schema = calls[1]
    assert instruction == PROMPT
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
    assert set(props["image_focus"]) == {"focal_x", "focal_y", "crop"}
    assert set(props["image_focus"]["crop"]) == {"x", "y", "width", "height"}
    assert set(props["evidence"]["highlight"]) == {"x", "y", "width", "height"}
    assert set(props["video"]) == {"start_seconds", "end_seconds", "fit", "crop"}
    for requirement in [
        "steps.items 必须是 1 到 4 个对象", "必填 title（最多48字），可选 body（最多96字）",
        "data.items 必须是 1 到 4 个对象", "必填 label（最多48字）和 value（最多40字），可选 detail（最多64字）",
        "left_title/right_title（最多48字）及 left_body/right_body（最多160字）四项",
        "eyebrow（最多48字）", "keyword（最多40字）", "call_to_action（最多72字）",
        "video 仅可选 start_seconds、end_seconds、fit、crop",
        "image_focus 仅可选 focal_x/focal_y/crop",
        "x + width <= 1 且 y + height <= 1", "width/height 必须大于0", "所有文字字段必须非空",
        "title 最多100字、body 最多240字、source_label 最多160字",
        "eligible_capacity_ratio", "actual_media_ratio", "至少 70%",
        "占当前可用内容区约 70%～85%", "跨入无关联段落",
    ]:
        assert requirement in instruction
    assert "HyperFrames" not in instruction
    if image:
        for component, example in props.items():
            if component == "video":
                continue
            candidate = copy.deepcopy(context["timeline"])
            candidate["shots"][0].update(component_id=component, props=example)
            if component in {"image_focus", "evidence"}:
                candidate["shots"][0].update(asset_src=expected[0], source_label="example.test")
            validate_timeline(Timeline.model_validate(candidate), job)


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
    assert context["asset_metadata"] == {"unit-image": {"description": "最终图片描述"}}
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
    node, job, audio, alignment = director_job(tmp_path, production=True)
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

    with pytest.raises(ValueError, match="足以覆盖全片 70%.*实际图片/视频镜头仅覆盖 0.0%"):
        node.plan(job, audio, alignment, 2.0)


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
