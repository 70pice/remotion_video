import json
import subprocess

import pytest

from videoagents.contracts import Asset, Brief, Job, Script, ScriptSegment, Timeline
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


def sourced_job(source_ref="https://example.com/report"):
    return job().model_copy(update={
        "brief": Brief(topic="test", width=240, height=426, fps=15, source_urls=[source_ref]),
        "script": Script(title="test", revision=1, segments=[
            ScriptSegment(segment_id="s1", narration="测试旁白。", source_refs=[source_ref]),
        ]),
    })


def video_job():
    asset = Asset(asset_id="unit-video", name="unit.mp4", role="evidence", mime_type="video/mp4",
                  size_bytes=10, sha256="a" * 64, source_url="https://example.com/video",
                  license_note="unit", artifact_id="unit-video-artifact", url="/api/artifacts/unit-video",
                  timeline_src="videoagents/unit-test/assets/unit.mp4")
    return job().model_copy(update={"assets": [asset]})


def image_job():
    asset = Asset(asset_id="unit-image", name="unit.png", role="evidence", mime_type="image/png",
                  size_bytes=10, sha256="b" * 64, source_url="https://example.com/image",
                  license_note="unit", artifact_id="unit-image-artifact", url="/api/artifacts/unit-image",
                  timeline_src="videoagents/unit-test/assets/unit.png")
    return job().model_copy(update={"assets": [asset]})


def node_validate(data) -> subprocess.CompletedProcess:
    module = (PROJECT_ROOT / "src/video-production/validation.mjs").as_uri()
    code = "import {validateTimeline} from " + json.dumps(module) + "; let input=''; for await(const c of process.stdin) input+=c; try{validateTimeline(JSON.parse(input));process.exit(0)}catch{process.exit(1)}"
    return subprocess.run(["node", "--input-type=module", "-e", code], input=json.dumps(data), text=True, capture_output=True, check=False)


def image_timeline(component="evidence", props=None):
    data = timeline(component, props or {})
    data["duration_in_frames"] = 60
    data["shots"][0]["end_frame"] = 60
    data["shots"][0]["asset_src"] = "videoagents/unit-test/assets/unit.png"
    data["shots"][0]["source_label"] = "example.com"
    return data


def chart_timeline(visualization="bars", **props):
    data = timeline("data", {
        "visualization": visualization,
        "source_ref": "https://example.com/report",
        "unit": "倍",
        "scale_max": 10,
        "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}],
        **props,
    })
    data["shots"][0]["source_label"] = "example.com/report"
    return data


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


@pytest.mark.parametrize("props", [
    {"visualization": "cards", "items": [{"label": "价格", "value": "20"}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 10,
     "reference_value": 5, "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4, "reveal_frame": 0}]},
    {"visualization": "donuts", "source_ref": "https://example.com/report", "unit": "%",
     "items": [{"label": "缓存", "value": "86%", "numeric_value": 86},
               {"label": "人工", "value": "29%", "numeric_value": 29, "reveal_frame": 15}]},
])
def test_python_and_node_accept_data_visualizations_without_rewriting_facts(props):
    data = timeline("data", props)
    if props["visualization"] != "cards":
        data["shots"][0]["source_label"] = "来源"
    candidate = Timeline.model_validate(data)
    validate_timeline(candidate, sourced_job())
    assert candidate.model_dump(mode="json") == data
    assert node_validate(data).returncode == 0


@pytest.mark.parametrize("props", [
    {"items": [{"label": "价格", "value": "20", "numeric_value": 20}]},
    {"visualization": "cards", "source_ref": "https://example.com/report", "items": [{"label": "价格", "value": "20"}]},
    {"visualization": "cards", "unit": "倍", "items": [{"label": "价格", "value": "20"}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍"}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": "4"}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": True}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 3,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "x" * 25, "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 10,
     "reference_value": 11, "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}]},
    {"visualization": "donuts", "source_ref": "https://example.com/report", "unit": "倍",
     "items": [{"label": "缓存", "value": "86%", "numeric_value": 86}]},
    {"visualization": "donuts", "source_ref": "https://example.com/report", "unit": "%", "scale_max": 100,
     "items": [{"label": "缓存", "value": "86%", "numeric_value": 86}]},
    {"visualization": "donuts", "source_ref": "https://example.com/report", "unit": "%",
     "items": [{"label": "缓存", "value": "101%", "numeric_value": 101}]},
    {"visualization": "donuts", "source_ref": "https://example.com/report", "unit": "%",
     "items": [{"label": "一", "value": "1%", "numeric_value": 1},
               {"label": "二", "value": "2%", "numeric_value": 2},
               {"label": "三", "value": "3%", "numeric_value": 3}]},
    {"visualization": "bars", "source_ref": "not-a-url", "unit": "倍", "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}]},
])
def test_python_and_node_reject_invalid_data_visualization_contract(props):
    data = timeline("data", props)
    data["shots"][0]["source_label"] = "来源"
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(data), sourced_job())
    assert node_validate(data).returncode == 1


@pytest.mark.parametrize("props", [
    {"visualization": "bars", "source_ref": "https://example.com/unapproved", "unit": "倍", "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": float("inf"),
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}]},
    {"visualization": "bars", "source_ref": "https://example.com/report", "unit": "倍", "scale_max": 10,
     "items": [{"label": "用量", "value": "4 倍", "numeric_value": float("inf")}]},
])
def test_python_rejects_unapproved_and_non_json_chart_values(props):
    data = timeline("data", props)
    data["shots"][0]["source_label"] = "来源"
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(data), sourced_job())


def test_python_and_node_reject_source_derived_chart_without_source_label():
    data = chart_timeline()
    data["shots"][0]["source_label"] = ""
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(data), sourced_job())
    assert node_validate(data).returncode == 1


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
    raw = timeline("image_focus", {"focal_x": 0.25, "focal_y": 0.75})
    raw["shots"][0]["asset_src"] = "videoagents/unit-test/assets/unit.png"
    candidate = Timeline.model_validate(raw)
    validate_timeline(candidate, image_job())
    assert candidate.model_dump(mode="json") == raw

    raw["shots"][0]["props"] = {"crop": {"x": 0.2, "y": 0.1, "width": 0.6, "height": 0.7}}
    validate_timeline(Timeline.model_validate(raw), image_job())

    raw["shots"][0]["props"] = {"crop": {"x": 0.8, "y": 0, "width": 0.3, "height": 1}}
    with pytest.raises(ValueError, match="裁切框"):
        validate_timeline(Timeline.model_validate(raw), image_job())


@pytest.mark.parametrize("component", ["evidence", "image_focus"])
def test_python_and_node_accept_focus_cues_overview_focus_overview(component):
    cues = [
        {"frame": 0, "label": "总览"},
        {"frame": 20, "region": {"x": 0.1, "y": 0.2, "width": 0.45, "height": 0.35}, "label": "重点"},
        {"frame": 40},
    ]
    raw = image_timeline(component, {"focus_cues": cues})
    candidate = Timeline.model_validate(raw)
    validate_timeline(candidate, image_job())
    assert candidate.model_dump(mode="json") == raw
    assert node_validate(raw).returncode == 0


def test_python_and_node_accept_legacy_image_highlight_crop_and_focal_props():
    for raw in [
        image_timeline("evidence", {"highlight": {"x": 0.1, "y": 0.1, "width": 0.4, "height": 0.4}}),
        image_timeline("image_focus", {"focal_x": 0.25, "focal_y": 0.75}),
        image_timeline("image_focus", {"crop": {"x": 0.2, "y": 0.1, "width": 0.6, "height": 0.7}}),
    ]:
        candidate = Timeline.model_validate(raw)
        validate_timeline(candidate, image_job())
        assert candidate.model_dump(mode="json") == raw
        assert node_validate(raw).returncode == 0


@pytest.mark.parametrize(("component", "props"), [
    ("evidence", {"focus_cues": [{"frame": 46}]}),
    ("evidence", {"focus_cues": [{"frame": True}]}),
    ("image_focus", {"focus_cues": [{"frame": 0}, {"frame": 0}]}),
    ("image_focus", {"focus_cues": [{"frame": 0}, {"frame": 10}, {"frame": 5}]}),
    ("evidence", {"focus_cues": [{"frame": 10}]}),
    ("evidence", {"focus_cues": [{"frame": 0, "extra": "bad"}]}),
    ("evidence", {"focus_cues": [{"frame": 0}], "highlight": {"x": 0, "y": 0, "width": 1, "height": 1}}),
    ("image_focus", {"focus_cues": [{"frame": 0}], "crop": {"x": 0, "y": 0, "width": 1, "height": 1}}),
    ("image_focus", {"focus_cues": [{"frame": 0}], "focal_x": 0.5}),
    ("evidence", {"focus_cues": [{"frame": 0, "label": "字" * 25}]}),
    ("evidence", {"focus_cues": {"frame": 0}}),
    ("evidence", {"focus_cues": []}),
    ("evidence", {"focus_cues": [{"frame": 0, "region": {"x": 0.8, "y": 0, "width": 0.3, "height": 1}}]}),
])
def test_python_and_node_reject_invalid_focus_cues(component, props):
    raw = image_timeline(component, props)
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(raw), image_job())
    assert node_validate(raw).returncode == 1


@pytest.mark.parametrize("props", [
    {"focus_cues": [{"frame": 0.5}]},
    {"focus_cues": [{"frame": 0, "region": {"x": float("nan"), "y": 0, "width": 1, "height": 1}}]},
])
def test_python_rejects_non_json_focus_cue_numbers(props):
    raw = image_timeline("evidence", props)
    with pytest.raises(ValueError):
        validate_timeline(Timeline.model_validate(raw), image_job())
