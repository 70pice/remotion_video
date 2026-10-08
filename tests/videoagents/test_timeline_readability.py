"""Timeline Gate prevents components and evidence frames from flashing by."""

import pytest

from videoagents.contracts import Timeline
from videoagents.nodes.gates import timeline_readability_issues


def timeline(component_id: str, frames: int, *, fps: int = 30, source_label: str = "", props=None) -> Timeline:
    return Timeline(
        job_id="unit-job",
        revision=1,
        width=1080,
        height=1920,
        fps=fps,
        duration_in_frames=frames,
        audio_src="videoagents/unit-job/assets/audio.mp3",
        shots=[{
            "shot_id": "shot-1",
            "start_frame": 0,
            "end_frame": frames,
            "component_id": component_id,
            "title": "UNIT",
            "source_label": source_label,
            "props": props or {},
        }],
        captions=[],
    )


@pytest.mark.parametrize(
    ("component_id", "frames", "source_label", "minimum"),
    [
        ("keyword", 44, "", 45),
        ("evidence", 74, "", 75),
        ("keyword", 74, "example.com", 75),
    ],
)
def test_timeline_readability_rejects_flash_shots(component_id, frames, source_label, minimum):
    issues = timeline_readability_issues(
        timeline(component_id, frames, source_label=source_label)
    )

    assert len(issues) == 1
    assert f"只有 {frames} 帧" in issues[0]
    assert f"至少需要 {minimum} 帧" in issues[0]
    assert "一闪而过" in issues[0]


@pytest.mark.parametrize(
    ("component_id", "frames", "source_label"),
    [
        ("keyword", 45, ""),
        ("evidence", 75, ""),
        ("keyword", 75, "example.com"),
    ],
)
def test_timeline_readability_accepts_exact_boundaries(component_id, frames, source_label):
    assert not timeline_readability_issues(
        timeline(component_id, frames, source_label=source_label)
    )


def test_timeline_readability_scales_thresholds_with_fps():
    assert "36 帧" in timeline_readability_issues(timeline("keyword", 35, fps=24))[0]
    assert "60 帧" in timeline_readability_issues(timeline("steps", 59, fps=24))[0]


@pytest.mark.parametrize(
    ("component_id", "props"),
    [
        ("comparison", {"right_reveal_frame": 15}),
        ("data", {"items": [{"reveal_frame": 15}]}),
        ("steps", {"items": [{"reveal_frame": 15}]}),
    ],
)
def test_timeline_readability_rejects_last_card_that_flashes_at_cut(component_id, props):
    issues = timeline_readability_issues(timeline(component_id, 104, props=props))

    assert len(issues) == 1
    assert "只剩 74 帧完整可读" in issues[0]
    assert "至少需要 75 帧" in issues[0]
    assert "最后一张卡片" in issues[0]


@pytest.mark.parametrize(
    ("component_id", "props"),
    [
        ("comparison", {"right_reveal_frame": 15}),
        ("data", {"items": [{"reveal_frame": 15}]}),
        ("steps", {"items": [{"reveal_frame": 15}]}),
    ],
)
def test_timeline_readability_accepts_reveal_with_full_post_entrance_window(component_id, props):
    assert not timeline_readability_issues(timeline(component_id, 105, props=props))


def test_timeline_readability_reveal_threshold_scales_with_fps():
    props = {"items": [{"reveal_frame": 15}]}
    assert "只剩 59 帧完整可读" in timeline_readability_issues(
        timeline("steps", 89, fps=24, props=props)
    )[0]
    assert not timeline_readability_issues(timeline("steps", 90, fps=24, props=props))


def test_all_hidden_steps_cannot_leave_the_visual_empty_for_several_seconds():
    props = {"items": [{"title": "执行", "reveal_frame": 120}]}
    issues = timeline_readability_issues(timeline("steps", 300, props=props))
    assert len(issues) == 1
    assert "主体大面积空白" in issues[0]
    # Data labels are now visible from the opening, so delayed numbers remain valid.
    assert not timeline_readability_issues(timeline("data", 300, props={
        "items": [{"label": "用量", "value": "4倍", "reveal_frame": 120}],
    }))


def test_focus_region_needs_a_real_reading_window_after_camera_transition():
    props = {"focus_cues": [{"frame": 0}, {"frame": 120}]}
    assert not timeline_readability_issues(timeline("image_focus", 213, props=props))
    issues = timeline_readability_issues(timeline("image_focus", 212, props=props))
    assert len(issues) == 1
    assert "focus_cues[1]" in issues[0]
