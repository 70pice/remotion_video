import json
import subprocess

import pytest

from videoagents.contracts import Brief, Job, Timeline
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
