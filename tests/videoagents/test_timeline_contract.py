import json
import subprocess

import pytest

from videoagents.contracts import Asset, Brief, Job, Timeline
from videoagents.default_config import PROJECT_ROOT
from videoagents.tools.timeline import validate_timeline


def timeline(component="title", props=None):
    return {"schema_version": "1", "job_id": "unit-test", "revision": 1, "width": 240, "height": 426, "fps": 15,
            "duration_in_frames": 30, "audio_src": None, "captions": [], "shots": [{"shot_id": "shot-1", "start_frame": 0,
            "end_frame": 30, "component_id": component, "title": "测试画面", "body": "", "asset_src": None,
            "source_label": "", "accent_color": "#8cffb8", "props": props or {}}]}


def job(usage="unspecified"):
    return Job(job_id="unit-test", revision=1, status="DRAFT", stage="idle", created_at="test", updated_at="test", message="",
               brief=Brief(topic="test", width=240, height=426, fps=15, usage=usage))


def video_job():
    asset = Asset(asset_id="unit-video", name="unit.mp4", role="evidence", mime_type="video/mp4",
                  size_bytes=10, sha256="a" * 64, source_url="https://example.com/video",
                  license_note="unit", artifact_id="unit-video-artifact", url="/api/artifacts/unit-video",
                  timeline_src="videoagents/unit-test/assets/unit.mp4")
    return job().model_copy(update={"assets": [asset]})


@pytest.mark.parametrize(("component", "props"), [
    ("keyword", {"keyword": "字" * 41}), ("title", {"eyebrow": "字" * 49}),
    ("conclusion", {"call_to_action": "字" * 73}),
    ("comparison", {"left_title": "字" * 49, "left_body": "L", "right_title": "R", "right_body": "R"}),
    ("data", {"items": [{"label": "L", "value": "字" * 41}]}),
    ("data", {"items": [{"label": "L", "value": "1", "detail": "字" * 65}]}),
    ("steps", {"items": [{"title": "字" * 49}]}),
    ("steps", {"items": [{"title": "L", "body": "字" * 97}]}),
    ("keyword", {"keyword": " "}), ("title", {"eyebrow": "x\x01"}),
])
def test_python_and_node_reject_same_invalid_props(component, props):
    data = timeline(component, props)
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(data), job())
    module = (PROJECT_ROOT / "src/video-production/validation.mjs").as_uri()
    code = "import {validateTimeline} from " + json.dumps(module) + "; let input=''; for await(const c of process.stdin) input+=c; try{validateTimeline(JSON.parse(input));process.exit(0)}catch{process.exit(1)}"
    result = subprocess.run(["node", "--input-type=module", "-e", code], input=json.dumps(data), text=True, capture_output=True, check=False)
    assert result.returncode == 1


def test_props_fact_values_must_be_provided_not_invented():
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(timeline("data")), job())
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(timeline("comparison")), job())


@pytest.mark.parametrize(("component", "props"), [
    ("data", {"items": [{"label": "价格", "value": "20", "reveal_frame": -1}]}),
    ("data", {"items": [{"label": "价格", "value": "20", "reveal_frame": 16}]}),
    ("data", {"items": [{"label": "价格", "value": "20", "reveal_frame": True}]}),
    ("steps", {"items": [{"title": "提交", "reveal_frame": 1.5}]}),
    ("steps", {"items": [{"title": "提交", "reveal_frame": "5"}]}),
    ("steps", {"items": [{"title": "提交", "reveal_frame": None}]}),
    ("steps", {"items": [{"title": "提交", "reveal_frame": 10}, {"title": "检查"}]}),
    ("data", {"items": [{"label": "一", "value": "1", "reveal_frame": 10},
                         {"label": "二", "value": "2", "reveal_frame": 5}]}),
    ("steps", {"items": [{"title": "提交"}], "layout": "horizontal"}),
    ("steps", {"items": [{"title": "提交"}], "layout": []}),
    ("steps", {"items": [{"title": "提交"}], "layout": {}}),
    ("comparison", {"left_title": "之前", "left_body": "过程", "right_title": "之后",
                    "right_body": "结果", "right_reveal_frame": 16}),
    ("comparison", {"left_title": "之前", "left_body": "过程", "right_title": "之后",
                    "right_body": "结果", "right_reveal_frame": False}),
])
def test_python_and_node_reject_invalid_semantic_reveal_cues(component, props):
    data = timeline(component, props)
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(data), job())
    module = (PROJECT_ROOT / "src/video-production/validation.mjs").as_uri()
    code = "import {validateTimeline} from " + json.dumps(module) + "; let input=''; for await(const c of process.stdin) input+=c; try{validateTimeline(JSON.parse(input));process.exit(0)}catch{process.exit(1)}"
    result = subprocess.run(["node", "--input-type=module", "-e", code], input=json.dumps(data), text=True, capture_output=True, check=False)
    assert result.returncode == 1


@pytest.mark.parametrize(("component", "props"), [
    ("data", {"items": [{"label": "价格", "value": "20"}]}),
    ("data", {"items": [{"label": "价格", "value": "20", "reveal_frame": 0},
                         {"label": "结果", "value": "待核实", "reveal_frame": 15}]}),
    ("steps", {"items": [{"title": "提交"}, {"title": "检查", "reveal_frame": 15}], "layout": "flow"}),
    ("steps", {"items": [{"title": "提交", "reveal_frame": 0}, {"title": "检查", "reveal_frame": 0}], "layout": "cards"}),
    ("comparison", {"left_title": "之前", "left_body": "过程", "right_title": "之后", "right_body": "结果"}),
    ("comparison", {"left_title": "之前", "left_body": "过程", "right_title": "之后",
                    "right_body": "结果", "right_reveal_frame": 15}),
])
def test_python_and_node_accept_supplied_cues_without_changing_facts(component, props):
    data = timeline(component, props)
    candidate = Timeline.model_validate(data)
    validate_timeline(candidate, job())
    assert candidate.model_dump(mode="json") == data
    module = (PROJECT_ROOT / "src/video-production/validation.mjs").as_uri()
    code = "import {validateTimeline} from " + json.dumps(module) + "; let input=''; for await(const c of process.stdin) input+=c; const data=JSON.parse(input); const before=JSON.stringify(data);validateTimeline(data); if(JSON.stringify(data)!==before)process.exit(1)"
    result = subprocess.run(["node", "--input-type=module", "-e", code], input=json.dumps(data), text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr


def test_python_and_node_accept_verified_preset_and_reject_injected_values():
    data = timeline("Snapcn-TextReveal")
    validate_timeline(Timeline.model_validate(data), job())
    module = (PROJECT_ROOT / "src/video-production/validation.mjs").as_uri()
    code = "import {validateTimeline} from " + json.dumps(module) + "; let input=''; for await(const c of process.stdin) input+=c; try{validateTimeline(JSON.parse(input));process.exit(0)}catch{process.exit(1)}"
    result = subprocess.run(["node", "--input-type=module", "-e", code], input=json.dumps(data), text=True, capture_output=True, check=False)
    assert result.returncode == 0
    data["shots"][0]["props"] = {"src": "https://example.test/injected.png"}
    with pytest.raises(ValueError, match="不接受自定义 props"):
        validate_timeline(Timeline.model_validate(data), job())
    data["shots"][0]["props"] = {}
    data["shots"][0]["asset_src"] = "videoagents/unit-test/source.png"
    with pytest.raises(ValueError, match="不接受 asset_src"):
        validate_timeline(Timeline.model_validate(data), job())


def test_noncommercial_talkcraft_presets_are_open_but_rejected_for_commercial_jobs():
    candidate = Timeline.model_validate(timeline("Talkcraft-crash-zoom-punch"))
    validate_timeline(candidate, job("personal"))
    validate_timeline(candidate, job("unspecified"))
    with pytest.raises(ValueError, match="许可"):
        validate_timeline(candidate, job("commercial"))


def test_nan_timestamp_control_text_and_path_escape_are_rejected():
    raw = timeline()
    raw["audio_src"] = "videoagents/unit-test/assets/voice.wav"
    raw["captions"] = [{"text": "test", "start_ms": 0, "end_ms": float("nan")}]
    with pytest.raises(ValueError):
        Timeline.model_validate(raw)
    raw = timeline()
    raw["shots"][0]["title"] = "bad\x01text"
    with pytest.raises(ValueError):
        Timeline.model_validate(raw)
    raw = timeline()
    raw["shots"][0]["asset_src"] = "videoagents/unit-test/../secret.png"
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(raw), job())


def test_video_component_requires_registered_video_and_valid_trim_metadata():
    raw = timeline("video", {"start_seconds": 1, "end_seconds": 3, "fit": "cover",
                             "crop": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8}})
    raw["shots"][0]["asset_src"] = "videoagents/unit-test/assets/unit.mp4"
    raw["shots"][0]["source_label"] = "example.com"
    candidate = Timeline.model_validate(raw)

    validate_timeline(candidate, video_job(), {"unit-video": {"duration_seconds": 5}})
    with pytest.raises(ValueError, match="实测时长"):
        validate_timeline(candidate, video_job(), {})

    bad = Timeline.model_validate({**raw, "shots": [{**raw["shots"][0], "props": {"start_seconds": 4, "end_seconds": 5}}]})
    with pytest.raises(ValueError, match="覆盖镜头时长"):
        validate_timeline(bad, video_job(), {"unit-video": {"duration_seconds": 5}})

    bad_crop = Timeline.model_validate({**raw, "shots": [{**raw["shots"][0], "props": {
        "start_seconds": 0, "end_seconds": 3, "crop": {"x": 0.8, "y": 0, "width": 0.4, "height": 1}}}]})
    with pytest.raises(ValueError, match="裁剪框"):
        validate_timeline(bad_crop, video_job(), {"unit-video": {"duration_seconds": 5}})


def test_image_focus_accepts_optional_crop_without_requiring_it():
    asset = Asset(asset_id="unit-image", name="unit.png", role="evidence", mime_type="image/png",
                  size_bytes=10, sha256="b" * 64, source_url="https://example.com/image",
                  license_note="unit", artifact_id="unit-image-artifact", url="/api/artifacts/unit-image",
                  timeline_src="videoagents/unit-test/assets/unit.png")
    image_job = job().model_copy(update={"assets": [asset]})
    raw = timeline("image_focus", {"focal_x": 0.25, "focal_y": 0.75})
    raw["shots"][0]["asset_src"] = "videoagents/unit-test/assets/unit.png"
    candidate = Timeline.model_validate(raw)
    validate_timeline(candidate, image_job)
    assert candidate.model_dump(mode="json") == raw

    raw["shots"][0]["props"] = {"crop": {"x": 0.2, "y": 0.1, "width": 0.6, "height": 0.7}}
    validate_timeline(Timeline.model_validate(raw), image_job)

    raw["shots"][0]["props"] = {"crop": {"x": 0.8, "y": 0, "width": 0.3, "height": 1}}
    with pytest.raises(ValueError, match="裁切框"):
        validate_timeline(Timeline.model_validate(raw), image_job)
