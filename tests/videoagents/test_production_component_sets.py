import json
from pathlib import Path

import pytest

from videoagents.contracts import Asset, Brief, Job, Shot, Timeline
from videoagents.tools.components import PRODUCTION_COMPONENT_ID_SET
from videoagents.tools.timeline import validate_timeline

SET_IDS = [f"A{index:02d}" for index in range(1, 13)] + [f"B{index:02d}" for index in range(1, 19)]
SAFE_BOX = {"x": 64 / 1080, "y": 96 / 1920, "width": 952 / 1080, "height": 1304 / 1920}


def _component_set_templates():
    try:
        from videoagents.tools.component_sets import component_set_templates
    except ModuleNotFoundError as exc:
        pytest.fail(f"videoagents.tools.component_sets helper is missing: {exc}")
    return component_set_templates()


def _resolve_component_set_shots(shots, assets, metadata):
    try:
        from videoagents.tools.component_sets import resolve_component_set_shots
    except ModuleNotFoundError as exc:
        pytest.fail(f"videoagents.tools.component_sets helper is missing: {exc}")
    return resolve_component_set_shots(shots, assets, metadata)


def _validate_component_set_shot(job, timeline, shot, metadata=None):
    try:
        from videoagents.tools.component_sets import validate_component_set_shot
    except ModuleNotFoundError as exc:
        pytest.fail(f"videoagents.tools.component_sets helper is missing: {exc}")
    return validate_component_set_shot(job, timeline, shot, metadata or {})


def _template(set_id: str) -> dict:
    templates = _component_set_templates()
    assert set(templates) == set(SET_IDS)
    template = templates[set_id]
    assert isinstance(template, dict)
    return template


def _main_component(set_id: str) -> str:
    template = _template(set_id)
    return template.get("main_component_id") or template.get("component_id")


def _default_part_ids(set_id: str) -> list[str]:
    parts = _template(set_id).get("parts") or []
    return [part["part_id"] for part in parts]



def _normalized_box(box: dict) -> dict:
    if max(box["x"], box["y"], box["width"], box["height"]) <= 1:
        return dict(box)
    return {
        "x": box["x"] / 1080,
        "y": box["y"] / 1920,
        "width": box["width"] / 1080,
        "height": box["height"] / 1920,
    }


def _full_parts(set_id: str, *, frames=450, overrides=None) -> list[dict]:
    overrides = {part["part_id"]: part for part in (overrides or [])}
    definitions = _template(set_id).get("parts") or []
    parts = []
    for index, part in enumerate(definitions):
        default = {
            "part_id": part["part_id"],
            "start_frame": 0,
            "end_frame": frames,
            "box": {"x": 0.07, "y": 0.07 + min(index, 8) * 0.10, "width": 0.86, "height": 0.075},
        }
        default.update(overrides.get(part["part_id"], {}))
        parts.append(default)
    return parts


def _focus_steps_for_items(items: list[str], frames: int) -> list[dict]:
    cut1 = frames // 3
    cut2 = frames * 2 // 3
    return [
        {"instruction": items[0], "start_frame": 0, "end_frame": cut1, "target": {"x": 0.12, "y": 0.24, "width": 0.40, "height": 0.12}},
        {"instruction": items[1], "start_frame": cut1, "end_frame": cut2, "target": {"x": 0.18, "y": 0.54, "width": 0.42, "height": 0.10}},
        {"instruction": items[2], "start_frame": cut2, "end_frame": frames, "target": {"x": 0.10, "y": 0.68, "width": 0.60, "height": 0.14}},
    ]


def _asset(job_id="job-sets", *, asset_id="asset-image", owner_job_id=None, mime_type="image/png", ext="png"):
    owner = owner_job_id or job_id
    return Asset(
        asset_id=asset_id,
        name=f"{asset_id}.{ext}",
        role="evidence",
        mime_type=mime_type,
        size_bytes=10,
        sha256="a" * 64,
        source_url="https://example.test/source",
        license_note="unit",
        artifact_id=f"artifact-{asset_id}",
        url=f"/api/artifacts/artifact-{asset_id}",
        timeline_src=f"videoagents/{owner}/assets/{asset_id}.{ext}",
    )


def _job(*, assets=None, usage="personal"):
    return Job(
        job_id="job-sets",
        revision=1,
        status="DRAFT",
        stage="idle",
        created_at="test",
        updated_at="test",
        message="",
        brief=Brief(
            topic="组件套生产测试",
            width=1080,
            height=1920,
            fps=30,
            usage=usage,
            source_urls=["https://example.test/source"],
        ),
        assets=assets or [],
    )


def _content(set_id="B08", **changes):
    payload = {"takeaway": "先核实身份再继续", "source_refs": ["https://example.test/source"]}
    three_items = ["看对方身份", "看收费动作", "找家人复核"]
    three_supporting = ["聊天记录", "付款页面", "视频邀请"]
    if set_id == "B01":
        payload.update({"items": three_items, "metric": {"label": "演示条目", "value": "3项", "detail": "来自三项内容"}})
    elif set_id == "B02":
        payload.update({"items": three_items, "metric": {"label": "演示条目", "value": "3项", "detail": "来自三项内容"}})
    elif set_id == "B03":
        payload.update({"items": ["AI文字陪聊", "真人视频接管"], "numeric_items": ["文字:8次", "视频:2次"]})
    elif set_id in {"B04", "B07", "B08", "B10"}:
        payload.update({"numeric_items": ["会员:100元", "礼物:100元", "视频:100元"], "metric": {"label": "演示合计", "value": "300元", "detail": "来自三项相加"}})
        if set_id != "B04":
            payload["items"] = three_items
    elif set_id == "B05":
        payload.update({"items": three_items, "supporting_items": three_supporting, "metric": {"label": "判断步骤", "value": "3项", "detail": "来自三步"}})
    elif set_id == "B06":
        payload.update({"items": three_items, "supporting_items": ["对方要求充值", "先截图给家人"], "metric": {"label": "提醒条目", "value": "3项", "detail": "来自三条提醒"}})
    elif set_id == "B09":
        payload.update({"items": ["自述金额", "核实金额"], "numeric_items": ["自述:100元", "核实:60元"], "metric": {"label": "差额", "value": "40元", "detail": "来自两项对比"}})
    elif set_id in {"B11", "B12"}:
        payload.update({"items": three_items, "supporting_items": three_supporting, "metric": {"label": "分类数量", "value": "3项", "detail": "来自三项内容"}})
    elif set_id == "B13":
        payload.update({"items": ["旧说法", "新说法"], "supporting_items": three_supporting, "metric": {"label": "核实状态", "value": "3项", "detail": "来自三类状态"}})
    elif set_id == "B14":
        payload.update({"items": three_items, "supporting_items": ["先问来源", "再问动作"], "metric": {"label": "问题拆解", "value": "3项", "detail": "来自三个问题"}})
    elif set_id == "B15":
        payload.update({"items": three_items, "supporting_items": three_supporting, "numeric_items": ["自述:100元", "来源:100元", "待核:100元"], "metric": {"label": "演示合计", "value": "300元", "detail": "来自三项相加"}})
    elif set_id == "B16":
        payload.update({"items": three_items, "supporting_items": three_supporting, "metric": {"label": "演示条目", "value": "3项", "detail": "来自三项内容"}})
    elif set_id == "B17":
        payload.update({"items": three_items, "supporting_items": ["发送前", "发送后"], "metric": {"label": "检查点", "value": "3项", "detail": "来自三步检查"}})
    elif set_id == "B18":
        payload.update({"items": ["原来做法", "调整后做法"], "supporting_items": three_supporting, "numeric_items": ["原来:1项", "现在:3项"], "metric": {"label": "状态分类", "value": "3项", "detail": "来自核实分类"}})
    elif set_id in {"A07", "A08", "A11", "A12"}:
        payload.update({"items": three_items, "supporting_items": three_supporting})
    elif set_id == "A09":
        payload.update({"items": three_items, "supporting_items": three_supporting, "metric": {"label": "操作口令", "value": "3项", "detail": "来自三步操作"}})
    elif set_id == "A10":
        payload.update({"items": three_items, "numeric_items": ["会员:100元", "礼物:100元", "视频:100元"], "metric": {"label": "演示合计", "value": "300元", "detail": "来自三项相加"}})
    else:
        payload.update({"items": three_items, "supporting_items": three_supporting, "metric": {"label": "演示条目", "value": "3项", "detail": "来自三项内容"}})
    payload.update(changes)
    return payload

def _set_design(set_id="B08", **changes):
    payload = {"set_id": set_id, "content": _content(set_id)}
    payload.update(changes)
    return payload


def _shot(set_id="B08", *, frames=450, component_id=None, set_design=None, asset_src=None, props=None, layers=None):
    return Shot(
        shot_id=f"shot-{set_id.lower()}",
        start_frame=0,
        end_frame=frames,
        component_id=component_id or _main_component(set_id),
        title="生产组件套镜头",
        body="这段口播来自当前任务，不使用样片文案。",
        asset_src=asset_src,
        source_label="example.test" if asset_src else "",
        props=props or {},
        layers=layers or [],
        set_design=set_design if set_design is not None else _set_design(set_id),
    )


def _timeline(shot, *, frames=None):
    duration = frames or shot.end_frame
    return Timeline(
        job_id="job-sets",
        revision=1,
        width=1080,
        height=1920,
        fps=30,
        duration_in_frames=duration,
        shots=[shot],
    )


def _validate(shot, *, job=None, timeline=None, metadata=None):
    job = job or _job(assets=[_asset()])
    timeline = timeline or _timeline(shot)
    _validate_component_set_shot(job, timeline, shot, metadata or {})
    validate_timeline(timeline, job, metadata or {})


@pytest.mark.parametrize("bad_design", [
    {"set_id": "C01", "content": {"takeaway": "不合法 ID"}},
    {"set_id": "B01", "content": {}},
    {"set_id": "B01", "content": {"takeaway": "合法结论", "title": "不允许把样片标题塞进 content"}},
    {"set_id": "B01", "content": {"takeaway": "合法结论"}, "unknown": True},
    {"set_id": "B01", "content": {"takeaway": "合法结论"}, "parts": [{"part_id": "BadCase", "start_frame": 0, "end_frame": 90, "box": SAFE_BOX}]},
    {"set_id": "B01", "content": {"takeaway": "合法结论"}, "focus_steps": [{"instruction": "看这里", "start_frame": 0, "end_frame": 90, "target": {"x": 0.9, "y": 0.2, "width": 0.2, "height": 0.2}}]},
])
def test_typed_set_design_schema_rejects_bad_ids_fields_and_boxes(bad_design):
    with pytest.raises(ValueError):
        _shot("B01", component_id="title", set_design=bad_design)


def test_component_set_metadata_covers_all_thirty_sets_with_real_registry_component_ids():
    templates = _component_set_templates()

    assert set(templates) == set(SET_IDS)
    assert len(templates) == 30
    for set_id, template in templates.items():
        main = template.get("main_component_id")
        assert main in PRODUCTION_COMPONENT_ID_SET, set_id
        parts = template.get("parts")
        assert isinstance(parts, list) and parts, set_id
        part_ids = [part.get("part_id") for part in parts]
        assert len(part_ids) == len(set(part_ids)), set_id
        for part in parts:
            assert part.get("component_id") in PRODUCTION_COMPONENT_ID_SET, (set_id, part)
            assert 0 <= part.get("start_ratio", -1) < part.get("end_ratio", -1) <= 1, (set_id, part)

    registry_path = Path("videoagents/component-set-capabilities.json")
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    registered_ids = {item["set_id"] for item in payload["sets"]}
    assert registered_ids == set(SET_IDS)


@pytest.mark.parametrize("set_id", SET_IDS)
def test_resolve_component_set_shots_expands_defaults_for_all_thirty_without_sample_markers(set_id):
    template = _template(set_id)
    needs_video = template.get("material_kind") == "video"
    asset = _asset(mime_type="video/mp4" if needs_video else "image/png", ext="mp4" if needs_video else "png")
    job = _job(assets=[asset])
    metadata = {asset.asset_id: {"width": 720, "height": 1280, "duration_seconds": 30, "frame_count": 900, "frame_rate": 30}}
    asset_src = asset.timeline_src if set_id.startswith("A") else None
    content = _content(set_id)
    design = {"set_id": set_id, "content": content}
    if set_id == "A09":
        design["focus_steps"] = _focus_steps_for_items(content["items"], 720)
    shot = _shot(set_id, frames=720, asset_src=asset_src, set_design=design)

    [resolved] = _resolve_component_set_shots([shot], job.assets, metadata)

    assert resolved.component_id == _main_component(set_id)
    assert resolved.set_design is not None
    assert resolved.set_design.parts
    assert {part.part_id for part in resolved.set_design.parts} == set(_default_part_ids(set_id))
    assert resolved.set_design.content.takeaway == "先核实身份再继续"
    assert "component_set" not in resolved.props
    assert "rich_content" not in resolved.props
    assert "composition" not in resolved.props
    dumped = resolved.model_dump(mode="json")
    assert "title" not in dumped["set_design"]["content"]
    assert "body" not in dumped["set_design"]["content"]

    _validate(resolved, job=job, timeline=_timeline(resolved, frames=720), metadata=metadata)


def test_changed_part_timing_and_box_are_retained_after_default_expansion():
    first_part = _default_part_ids("B08")[0]
    override = {"part_id": first_part, "start_frame": 45, "end_frame": 210, "box": {"x": 0.10, "y": 0.12, "width": 0.70, "height": 0.22}}
    shot = _shot("B08", set_design=_set_design("B08", parts=_full_parts("B08", overrides=[override])))

    [resolved] = _resolve_component_set_shots([shot], [], {})
    part = next(part for part in resolved.set_design.parts if part.part_id == first_part)

    assert part.start_frame == 45
    assert part.end_frame == 210
    assert part.box.model_dump() == override["box"]


def test_component_set_validation_rejects_missing_main_component_and_legacy_sample_props():
    shot = _shot("B08", component_id="title")
    with pytest.raises(ValueError, match="component_id|main_component"):
        _validate_component_set_shot(_job(), _timeline(shot), shot)

    sample_marker = _shot("B08", props={"component_set": "B08"})
    with pytest.raises(ValueError, match="props|component_set|set_design"):
        _validate_component_set_shot(_job(), _timeline(sample_marker), sample_marker)


def test_component_set_validation_rejects_malformed_unknown_colliding_and_unsafe_parts():
    known_parts = _default_part_ids("B08")
    first, second = known_parts[0], known_parts[1]

    unknown = _shot("B08", set_design=_set_design("B08", parts=[{"part_id": "unknown_part", "start_frame": 0, "end_frame": 120, "box": SAFE_BOX}]))
    with pytest.raises(ValueError, match="part_id"):
        _resolve_component_set_shots([unknown], [], {})

    colliding = _shot("B08", set_design=_set_design("B08", parts=_full_parts("B08", overrides=[
        {"part_id": first, "start_frame": 0, "end_frame": 180, "box": {"x": 0.10, "y": 0.10, "width": 0.60, "height": 0.30}},
        {"part_id": second, "start_frame": 30, "end_frame": 210, "box": {"x": 0.20, "y": 0.20, "width": 0.60, "height": 0.30}},
    ])))
    with pytest.raises(ValueError, match="遮挡|overlap"):
        _validate_component_set_shot(_job(), _timeline(colliding), colliding)

    unsafe = _shot("B08", set_design=_set_design("B08", parts=_full_parts("B08", overrides=[
        {"part_id": first, "start_frame": 0, "end_frame": 180, "box": {"x": 0.01, "y": 0.01, "width": 0.30, "height": 0.20}},
    ])))
    with pytest.raises(ValueError):
        _validate_component_set_shot(_job(), _timeline(unsafe), unsafe)

def test_component_set_validation_rejects_too_short_part_but_allows_long_production_shots():
    first_part = _default_part_ids("B08")[0]
    too_short = _shot("B08", set_design=_set_design("B08", parts=_full_parts("B08", overrides=[{"part_id": first_part, "start_frame": 0, "end_frame": 12, "box": SAFE_BOX}])))
    with pytest.raises(ValueError, match="阅读|显示|时长|区间"):
        _validate_component_set_shot(_job(), _timeline(too_short), too_short)

    long_shot = _shot(
        "B08",
        frames=900,
        set_design={
            "set_id": "B08",
            "content": _content("B08", takeaway="长镜头也只按可读性校验"),
            "parts": _full_parts("B08", frames=900),
        },
    )
    _validate(long_shot, job=_job(), timeline=_timeline(long_shot, frames=900))


def test_component_set_validation_rejects_material_asset_isolation_and_missing_material():
    current_asset = _asset()
    other_job_asset = _asset(asset_id="foreign", owner_job_id="other-job")
    metadata = {current_asset.asset_id: {"width": 1200, "height": 900}}

    missing = _shot("A01", asset_src=None, set_design=_set_design("A01", parts=_full_parts("A01")))
    with pytest.raises(ValueError):
        _validate_component_set_shot(_job(assets=[current_asset]), _timeline(missing), missing)

    foreign = _shot("A01", asset_src=other_job_asset.timeline_src, set_design=_set_design("A01", parts=_full_parts("A01")))
    with pytest.raises(ValueError):
        _validate_component_set_shot(_job(assets=[current_asset]), _timeline(foreign), foreign)

    valid = _shot("A01", asset_src=current_asset.timeline_src, set_design={"set_id": "A01", "content": _content("A01"), "parts": _full_parts("A01")})
    [resolved] = _resolve_component_set_shots([valid], [current_asset], metadata)
    _validate(resolved, job=_job(assets=[current_asset]), timeline=_timeline(resolved), metadata=metadata)



def test_material_component_sets_require_source_label_and_evidence_main_uses_evidence_asset():
    asset = _asset()
    metadata = {asset.asset_id: {"width": 1200, "height": 900}}
    blank_label = _shot(
        "A01",
        asset_src=asset.timeline_src,
        set_design={"set_id": "A01", "content": _content("A01"), "parts": _full_parts("A01")},
    ).model_copy(update={"source_label": ""})
    with pytest.raises(ValueError, match="出处|source_label"):
        _validate_component_set_shot(_job(assets=[asset]), _timeline(blank_label), blank_label, metadata)

    illustration = asset.model_copy(update={"role": "illustration"})
    wrong_role = _shot(
        "A05",
        asset_src=illustration.timeline_src,
        set_design={"set_id": "A05", "content": _content("A05"), "parts": _full_parts("A05")},
    )
    with pytest.raises(ValueError, match="证据|evidence|来源"):
        _validate_component_set_shot(_job(assets=[illustration]), _timeline(wrong_role), wrong_role, metadata)

    no_source = asset.model_copy(update={"source_url": ""})
    missing_source = _shot(
        "A05",
        asset_src=no_source.timeline_src,
        set_design={"set_id": "A05", "content": _content("A05"), "parts": _full_parts("A05")},
    )
    with pytest.raises(ValueError, match="证据|来源|source"):
        _validate_component_set_shot(_job(assets=[no_source]), _timeline(missing_source), missing_source, metadata)



def test_focus_steps_require_renderer_supported_component_set_metadata():
    asset = _asset()
    frames = 720
    metadata = {asset.asset_id: {"width": 1200, "height": 900}}
    content = _content("A01")
    focus = _focus_steps_for_items(content["items"], frames)
    unsupported = _shot(
        "A01",
        frames=frames,
        asset_src=asset.timeline_src,
        set_design={
            "set_id": "A01",
            "content": content,
            "parts": _full_parts("A01", frames=frames),
            "focus_steps": focus,
            "source_size": {"width": 1200, "height": 900},
        },
    )
    with pytest.raises(ValueError, match="圈选|focus|支持"):
        _validate_component_set_shot(_job(assets=[asset]), _timeline(unsupported, frames=frames), unsupported, metadata)

    video_asset = _asset(mime_type="video/mp4", ext="mp4")
    video_metadata = {video_asset.asset_id: {"width": 720, "height": 1280, "duration_seconds": 30, "frame_count": 900, "frame_rate": 30}}
    a09_content = _content("A09")
    supported = _shot(
        "A09",
        frames=frames,
        asset_src=video_asset.timeline_src,
        set_design={
            "set_id": "A09",
            "content": a09_content,
            "parts": _full_parts("A09", frames=frames),
            "focus_steps": _focus_steps_for_items(a09_content["items"], frames),
            "source_size": {"width": 720, "height": 1280},
        },
    )
    _validate(supported, job=_job(assets=[video_asset]), timeline=_timeline(supported, frames=frames), metadata=video_metadata)


def test_component_set_validation_rejects_numeric_content_without_source_refs():
    shot = _shot("B08", set_design={"set_id": "B08", "content": _content("B08", source_refs=[]), "parts": _full_parts("B08")})

    with pytest.raises(ValueError, match="source|数字|来源"):
        _validate_component_set_shot(_job(), _timeline(shot), shot)


def test_component_set_validation_requires_focus_steps_source_size_and_measured_metadata_for_material_focus_sets():
    asset = _asset(mime_type="video/mp4", ext="mp4")
    job = _job(assets=[asset])
    content = _content("A09")
    frames = 720
    focus_steps = _focus_steps_for_items(content["items"], frames)
    shot = _shot("A09", frames=frames, asset_src=asset.timeline_src, set_design={"set_id": "A09", "content": content, "parts": _full_parts("A09", frames=frames), "focus_steps": focus_steps})

    measured = {asset.asset_id: {"width": 720, "height": 1280, "duration_seconds": 30, "frame_count": 900, "frame_rate": 30}}
    with pytest.raises(ValueError, match="source_size|尺寸|元数据"):
        _validate_component_set_shot(job, _timeline(shot, frames=frames), shot, measured)

    valid = _shot(
        "A09",
        frames=frames,
        asset_src=asset.timeline_src,
        set_design={
            "set_id": "A09",
            "content": content,
            "parts": _full_parts("A09", frames=frames),
            "focus_steps": focus_steps,
            "source_size": {"width": 720, "height": 1280},
        },
    )
    _validate(valid, job=job, timeline=_timeline(valid, frames=frames), metadata=measured)




def test_component_set_validation_rejects_unknown_source_refs_and_negative_video_start():
    bad_ref = _shot(
        "B08",
        set_design={"set_id": "B08", "content": _content("B08", source_refs=["https://example.test/not-in-job"]), "parts": _full_parts("B08")},
    )
    with pytest.raises(ValueError, match="source_refs|来源"):
        _validate_component_set_shot(_job(), _timeline(bad_ref), bad_ref)

    asset = _asset(mime_type="video/mp4", ext="mp4")
    metadata = {asset.asset_id: {"width": 720, "height": 1280, "duration_seconds": 20, "frame_count": 600, "frame_rate": 30}}
    negative_start = _shot(
        "A03",
        frames=300,
        asset_src=asset.timeline_src,
        props={"start_seconds": -0.25, "fit": "contain"},
        set_design={"set_id": "A03", "content": _content("A03"), "parts": _full_parts("A03", frames=300)},
    )
    with pytest.raises(ValueError, match="非负|截取|起始"):
        _validate_component_set_shot(_job(assets=[asset]), _timeline(negative_start, frames=300), negative_start, metadata)



def test_component_set_native_count_uses_only_valid_actual_mounted_parts():
    from videoagents.tools.components import component_requirement_usage, validate_component_requirements

    shot = _shot(
        "B08",
        frames=720,
        set_design={"set_id": "B08", "content": _content("B08"), "parts": _full_parts("B08", frames=720)},
    )
    timeline = _timeline(shot, frames=720)
    usage = component_requirement_usage(timeline, "personal")
    expected_ids = {part["component_id"] for part in _template("B08")["parts"]}

    assert set(usage["library_ids"]) == expected_ids
    assert usage["main_count"] == 1
    assert usage["layer_count"] == len(expected_ids) - 1
    assert "component_set_fingerprint" in usage

    short_part = _default_part_ids("B08")[0]
    invalid = _shot(
        "B08",
        frames=720,
        set_design={
            "set_id": "B08",
            "content": _content("B08"),
            "parts": _full_parts("B08", frames=720, overrides=[{"part_id": short_part, "start_frame": 0, "end_frame": 12, "box": SAFE_BOX}]),
        },
    )
    invalid_usage = component_requirement_usage(_timeline(invalid, frames=720), "personal")
    assert invalid_usage["library_count"] == 0
    with pytest.raises(ValueError, match="显示区间|阅读|统计校验失败"):
        validate_component_requirements(_timeline(invalid, frames=720), "personal", required=1)



def test_media_coverage_counts_component_set_main_visible_interval_not_whole_shot():
    from videoagents.contracts import Script, ScriptSegment
    from videoagents.tools.timeline import media_coverage_report, validate_media_coverage

    asset = _asset(mime_type="video/mp4", ext="mp4")
    job = _job(assets=[asset]).model_copy(update={
        "script": Script(
            title="组件套媒体覆盖",
            origin="user",
            revision=1,
            segments=[ScriptSegment(
                segment_id="s1",
                narration="这段旁白需要真实视频素材覆盖。",
                source_refs=[asset.source_url],
                asset_ids=[asset.asset_id],
            )],
        )
    })
    metadata = {asset.asset_id: {"width": 720, "height": 1280, "duration_seconds": 10, "frame_count": 300, "frame_rate": 30}}
    shot = _shot(
        "A03",
        frames=300,
        asset_src=asset.timeline_src,
        props={"start_seconds": 0, "fit": "contain"},
        set_design={
            "set_id": "A03",
            "content": _content("A03"),
            "parts": _full_parts("A03", frames=300, overrides=[{"part_id": "main", "start_frame": 60, "end_frame": 240, "box": SAFE_BOX}]),
        },
    )
    timeline = Timeline.model_validate({
        **_timeline(shot, frames=300).model_dump(mode="json"),
        "audio_src": "videoagents/job-sets/assets/unit.wav",
        "captions": [{"text": job.script.segments[0].narration, "start_ms": 0.0, "end_ms": 9900.0}],
    })

    report = media_coverage_report(timeline, job, metadata)

    assert report["eligible_capacity_frames"] == 300
    assert report["required"] is True
    assert report["actual_media_frames"] == 180
    assert report["source_evidence_frames"] == 180
    with pytest.raises(ValueError, match="70%|覆盖"):
        validate_media_coverage(timeline, job, metadata)


def test_director_plan_preserves_selected_component_set_and_expands_parts(tmp_path, monkeypatch):
    from tests.videoagents.test_director_model_contract import director_job
    from videoagents.state import VideoState, job_context

    node, job, audio, alignment = director_job(tmp_path, production=True, image=False)
    frames = 720
    state = VideoState(**job_context(job), run_id="unit-component-set-director", action="produce")
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert command_id == "unit-component-set-director:timeline"
        assert "ComponentSetDesign" in output_schema["$defs"]
        assert "B02" in output_schema["$defs"]["ComponentSetDesign"]["properties"]["set_id"]["enum"]
        assert context["timeline"]["audio_src"] == audio.timeline_src
        assert context["timeline"]["captions"] == [{"text": alignment.segments[0].text, "start_ms": 0.0, "end_ms": 1800.0}]
        return {
            "shots": [{
                "shot_id": "shot-set-b02",
                "start_frame": 0,
                "end_frame": frames,
                "component_id": _main_component("B02"),
                "title": "组件套摄影选择",
                "body": "摄影模型选择整套组件，音频和字幕由程序保留。",
                "set_design": {"set_id": "B02", "content": _content("B02", source_refs=["https://example.test/muse"])},
            }],
            "segment_performances": [{
                "segment_id": "s1",
                "shot_ids": ["shot-set-b02"],
                "component_reason": "选择 B02 无素材组件套承载本段结论和步骤。",
                "visual_action": "使用默认 parts 展开内部组件，不改写音频和字幕。",
            }],
            "shot_reviews": [{
                "shot_id": "shot-set-b02", "review_frame": frames // 2,
                "component_reason": "选择 B02 无素材组件套承载本段结论和步骤。",
                "visual_action": "在内部组件展开后检查代表帧，保留音频和字幕。",
            }],
        }

    monkeypatch.setattr(node.model, "call", model)
    timeline = node.plan(job, audio, alignment, frames / job.brief.fps, state=state)

    assert timeline.audio_src == audio.timeline_src
    assert [caption.model_dump(mode="json") for caption in timeline.captions] == [
        {"text": alignment.segments[0].text, "start_ms": 0.0, "end_ms": 1800.0}
    ]
    shot = timeline.shots[0]
    assert shot.set_design.set_id == "B02"
    assert {part.part_id for part in shot.set_design.parts} == set(_default_part_ids("B02"))
    assert node._last_director_plan["origin"] == "model"
    assert node._last_director_plan["shots"][0]["set_design"]["set_id"] == "B02"
