from types import SimpleNamespace

import pytest

from videoagents.contracts import Asset, Brief, Job, Script, ScriptSegment, Timeline
from videoagents.tools.timeline import media_coverage_report, validate_media_coverage

SOURCE = "https://example.com/report"


def job_with_script(*segments: ScriptSegment) -> Job:
    image = Asset(
        asset_id="source-image",
        name="source.png",
        role="evidence",
        mime_type="image/png",
        size_bytes=1,
        sha256="a" * 64,
        source_url=SOURCE,
        license_note="unit",
        artifact_id="source-image-artifact",
        url="/api/artifacts/source-image",
        timeline_src="videoagents/chart-job/assets/source.png",
    )
    return Job(
        job_id="chart-job",
        revision=1,
        status="DRAFT",
        stage="idle",
        created_at="test",
        updated_at="test",
        message="",
        brief=Brief(topic="chart", width=240, height=426, fps=15, source_urls=[SOURCE]),
        script=Script(title="chart", revision=1, segments=list(segments)),
        assets=[image],
    )


def base_timeline(shots: list[dict], captions: list[dict] | None = None, duration: int = 100) -> Timeline:
    return Timeline.model_validate({
        "schema_version": "1",
        "job_id": "chart-job",
        "revision": 1,
        "width": 240,
        "height": 426,
        "fps": 15,
        "duration_in_frames": duration,
        "audio_src": "videoagents/chart-job/assets/voice.wav",
        "captions": (
            [{"text": "第一段。", "start_ms": 0.0, "end_ms": duration * 1000.0 / 15}]
            if captions is None
            else captions
        ),
        "shots": shots,
    })


def loose_timeline(shots: list[dict], duration: int = 100) -> SimpleNamespace:
    return SimpleNamespace(
        job_id="chart-job",
        revision=1,
        width=240,
        height=426,
        fps=15,
        duration_in_frames=duration,
        audio_src="videoagents/chart-job/assets/voice.wav",
        captions=[SimpleNamespace(text="第一段。", start_ms=0.0, end_ms=duration * 1000.0 / 15)],
        shots=[SimpleNamespace(**{"props": {}, "asset_src": None, "source_label": "", **shot}) for shot in shots],
    )


def title(start: int, end: int, shot_id: str = "title") -> dict:
    return {
        "shot_id": shot_id,
        "start_frame": start,
        "end_frame": end,
        "component_id": "title",
        "title": "解释",
    }


def raw_media(start: int, end: int, shot_id: str = "raw") -> dict:
    return {
        "shot_id": shot_id,
        "start_frame": start,
        "end_frame": end,
        "component_id": "evidence",
        "title": "真实截图",
        "asset_src": "videoagents/chart-job/assets/source.png",
        "source_label": "example.com",
    }


def data_chart(start: int, end: int, shot_id: str = "chart", source_ref: str = SOURCE) -> dict:
    return {
        "shot_id": shot_id,
        "start_frame": start,
        "end_frame": end,
        "component_id": "data",
        "title": "来源数据图表",
        "source_label": "example.com",
        "props": {
            "visualization": "bars",
            "source_ref": source_ref,
            "unit": "倍",
            "scale_max": 10,
            "items": [{"label": "用量", "value": "4 倍", "numeric_value": 4}],
        },
    }


def test_missing_script_or_caption_alignment_returns_zero_visual_groups():
    job = job_with_script(ScriptSegment(segment_id="s1", narration="第一段。", source_refs=[SOURCE]))
    timeline = base_timeline([data_chart(0, 100)], captions=[])

    report = media_coverage_report(timeline, job)

    assert report["actual_media_frames"] == 0
    assert report["actual_chart_frames"] == 0
    assert report["actual_visual_frames"] == 0


def test_raw_and_source_matched_charts_are_reported_separately_and_deduped():
    job = job_with_script(ScriptSegment(segment_id="s1", narration="第一段。", source_refs=[SOURCE]))
    timeline = base_timeline([raw_media(0, 60), data_chart(60, 100)])

    report = media_coverage_report(timeline, job)

    assert report["actual_media_frames"] == 60
    assert report["actual_chart_frames"] == 40
    assert report["actual_visual_frames"] == 100
    assert report["actual_visual_ratio"] == 1

    overlapped = loose_timeline([raw_media(0, 60), data_chart(30, 100)])
    report = media_coverage_report(overlapped, job)
    assert report["actual_media_frames"] == 60
    assert report["actual_chart_frames"] == 70
    assert report["actual_visual_frames"] == 100


def test_cards_and_presets_do_not_count_as_chart_coverage():
    job = job_with_script(ScriptSegment(segment_id="s1", narration="第一段。", source_refs=[SOURCE]))
    timeline = base_timeline([
        {
            "shot_id": "cards",
            "start_frame": 0,
            "end_frame": 50,
            "component_id": "data",
            "title": "旧卡片",
            "props": {"items": [{"label": "价格", "value": "20"}]},
        },
        {
            "shot_id": "preset",
            "start_frame": 50,
            "end_frame": 100,
            "component_id": "Snapcn-TextReveal",
            "title": "预设",
        },
    ])

    report = media_coverage_report(timeline, job)

    assert report["actual_media_frames"] == 0
    assert report["actual_chart_frames"] == 0
    assert report["actual_visual_frames"] == 0


def test_unrelated_and_cross_segment_chart_sources_are_rejected():
    job = job_with_script(
        ScriptSegment(segment_id="s1", narration="第一段。", source_refs=[SOURCE]),
        ScriptSegment(segment_id="s2", narration="第二段。", source_refs=[]),
    )
    captions = [
        {"text": "第一段。", "start_ms": 0.0, "end_ms": 3000.0},
        {"text": "第二段。", "start_ms": 3334.0, "end_ms": 6000.0},
    ]

    unrelated = base_timeline([title(0, 50), data_chart(50, 100)], captions=captions)
    with pytest.raises(ValueError, match="语义关联"):
        media_coverage_report(unrelated, job)

    crossing = base_timeline([title(0, 35, "pre"), data_chart(35, 65), title(65, 100, "post")], captions=captions)
    with pytest.raises(ValueError, match="跨入"):
        media_coverage_report(crossing, job)


def test_source_matched_charts_can_satisfy_visual_coverage_boundary():
    job = job_with_script(ScriptSegment(segment_id="s1", narration="第一段。", source_refs=[SOURCE]))

    with pytest.raises(ValueError, match="实际图片/视频镜头仅覆盖 0.0%.*来源数据图表覆盖 70.0%"):
        validate_media_coverage(base_timeline([data_chart(0, 70), title(70, 100)]), job)

    report = validate_media_coverage(base_timeline([data_chart(0, 71), title(71, 100)]), job)
    assert report["target_frames"] == 71
    assert report["actual_media_frames"] == 0
    assert report["actual_chart_frames"] == 71
    assert report["actual_visual_frames"] == 71
