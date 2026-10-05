"""Director transport guidance follows real assets and component validation."""

import copy
import json

import pytest

from videoagents.contracts import Alignment, Asset, Brief, Script, ScriptSegment, Timeline
from videoagents.nodes.director import COMPONENT_PROPS_EXAMPLES, PROMPT, DirectorNode
from videoagents.services.jobs import JobService
from videoagents.state import VideoState, job_context
from videoagents.storage import Repository
from videoagents.tools.timeline import validate_timeline


def director_job(tmp_path, image=True, usage="unspecified"):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="Muse", target_seconds=2, width=240, height=426, fps=15, usage=usage))
    audio = Asset(asset_id="unit-audio", name="unit.wav", role="audio", mime_type="audio/wav", size_bytes=1,
                  sha256="a" * 64, artifact_id="unit-audio-artifact", url="/api/artifacts/unit-audio-artifact",
                  timeline_src=f"videoagents/{job.job_id}/assets/unit.wav")
    assets = [audio]
    if image:
        assets.append(Asset(asset_id="unit-image", name="unit.png", role="evidence", mime_type="image/png",
                            size_bytes=1, sha256="b" * 64, artifact_id="unit-image-artifact",
                            url="/api/artifacts/unit-image-artifact", source_url="https://example.test/muse",
                            timeline_src=f"videoagents/{job.job_id}/assets/unit.png"))
    script = Script(title="Muse", origin="user", revision=job.revision,
                    segments=[ScriptSegment(segment_id="s1", narration="观点：这是测试文案。")])
    job = repo.update_job(job.job_id, job.revision, script=script, assets=assets)
    alignment = Alignment(origin="manual", verified=True, audio_sha256=audio.sha256,
                          segments=[{"segment_id": "s1", "text": script.segments[0].narration,
                                     "start_ms": 0.0, "end_ms": 1800.0}])
    return DirectorNode(repo, service), job, audio, alignment


@pytest.mark.parametrize("image", [False, True])
def test_director_guidance_limits_assets_and_describes_valid_component_props(tmp_path, monkeypatch, image):
    node, job, audio, alignment = director_job(tmp_path, image)
    calls = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((instruction, context, output_schema))
        return context["timeline"]

    monkeypatch.setattr(node.model, "call", model)
    research = {"visuals": [{"image_url": "https://cdn.example.test/muse.png",
                              "artifact_url": "/api/artifacts/unprovided-image"}]}
    node.plan(job, audio, alignment, 2.0, research)

    instruction, context, schema = calls[0]
    assert instruction == PROMPT
    assert set(context) == {"brief", "script", "timeline", "research", "assets", "asset_metadata"}
    assert "component_props_examples" not in context
    expected = [asset.timeline_src for asset in job.assets if asset.mime_type.startswith("image/")] + [None]
    assert schema["$defs"]["Shot"]["properties"]["asset_src"]["enum"] == expected
    components = schema["$defs"]["Shot"]["properties"]["component_id"]["enum"]
    assert len(components) == 160
    assert "Snapcn-TextReveal" in components
    assert "Talkcraft-crash-zoom-punch" in components
    assert "research.visuals" in instruction and "artifact_url" in instruction and "不得" in instruction
    assert "asset_src=null" in instruction and "字符串数组" in instruction
    assert "enum" not in Timeline.model_json_schema()["$defs"]["Shot"]["properties"]["asset_src"]
    props = COMPONENT_PROPS_EXAMPLES
    assert json.dumps(props, ensure_ascii=False, separators=(",", ":")) in instruction
    assert set(props["steps"]["items"][0]) == {"title", "body"}
    assert set(props["data"]["items"][0]) == {"label", "value", "detail"}
    assert set(props["comparison"]) == {"left_title", "left_body", "right_title", "right_body"}
    assert props["image_focus"] == {"focal_x": 0.5, "focal_y": 0.5}
    assert set(props["evidence"]["highlight"]) == {"x", "y", "width", "height"}
    for requirement in [
        "steps.items 必须是 1 到 4 个对象", "必填 title（最多48字），可选 body（最多96字）",
        "data.items 必须是 1 到 4 个对象", "必填 label（最多48字）和 value（最多40字），可选 detail（最多64字）",
        "left_title/right_title（最多48字）及 left_body/right_body（最多160字）四项",
        "eyebrow（最多48字）", "keyword（最多40字）", "call_to_action（最多72字）",
        "x + width <= 1 且 y + height <= 1", "width/height 必须大于0", "所有文字字段必须非空",
        "title 最多100字、body 最多240字、source_label 最多160字",
    ]:
        assert requirement in instruction
    if image:
        for component, example in props.items():
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
        return context["timeline"]

    monkeypatch.setattr(node.model, "call", model)
    node.plan(job, audio, alignment, 2.0)
    instruction, schema = calls[0]
    components = schema["$defs"]["Shot"]["properties"]["component_id"]["enum"]
    assert len(components) == 52
    assert "Snapcn-TextReveal" in components
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
        value = copy.deepcopy(context["timeline"])
        value["shots"][0].update(component_id=component, props=props, asset_src=asset_src)
        return value

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match=message):
        node.plan(job, audio, alignment, 2.0)


@pytest.mark.parametrize("change", ["audio", "caption", "frames"])
def test_director_guidance_keeps_immutable_audio_and_time_intervals(tmp_path, monkeypatch, change):
    node, job, audio, alignment = director_job(tmp_path)
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        value = copy.deepcopy(context["timeline"])
        if change == "audio":
            value["audio_src"] = f"videoagents/{job.job_id}/assets/different.wav"
        elif change == "caption":
            value["captions"][0]["end_ms"] = 1900.0
        else:
            value["shots"][0]["end_frame"] = value["duration_in_frames"] = 31
        return value

    monkeypatch.setattr(node.model, "call", model)
    with pytest.raises(ValueError, match="修改了实测音频时间轴"):
        node.plan(job, audio, alignment, 2.0)


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
        assert state == original_state and state["timeline"] is None
        assert context["timeline"]["audio_src"] == audio.timeline_src
        value = copy.deepcopy(context["timeline"])
        if reject:
            value["captions"][0]["end_ms"] = 1900.0
        return value
    monkeypatch.setattr(node.model, "call", model)
    if reject:
        with pytest.raises(ValueError, match="修改了实测音频时间轴"):
            node.plan(job, audio, alignment, 2.0, {"sources": [{"text": "不应覆盖共享state"}]}, state=state)
    else:
        timeline = node.plan(job, audio, alignment, 2.0, {"sources": [{"text": "不应覆盖共享state"}]}, state=state)
        assert timeline.audio_src == audio.timeline_src
    context, command = calls[0]
    assert context["research"]["sources"][0]["text"] == "已冻结的最终证据"
    assert "tools" not in context["research"]
    assert context["asset_metadata"] == {"unit-image": {"description": "最终图片描述"}}
    assert command == "unit-resume-command"
    assert state == original_state and node.repo.get_job(job.job_id).timeline is None
