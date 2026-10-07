"""The editing Agent gets exact shot semantics without raw word-caption bloat."""

from videoagents.nodes.editing import compact_timeline_for_editing, has_unapplied_human_feedback


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


def test_editing_only_receives_unapplied_human_feedback():
    reviewed_timeline = {"shots": [{"shot_id": "shot-old"}]}
    applied = {
        "human_feedback": {
            "render": {
                "decision": "revise",
                "applied": True,
                "timeline": reviewed_timeline,
            }
        }
    }
    pending = {
        "human_feedback": {
            "render": {
                "decision": "revise",
                "applied": False,
                "timeline": reviewed_timeline,
            }
        }
    }

    assert not has_unapplied_human_feedback(applied)
    assert has_unapplied_human_feedback(pending)
    assert not has_unapplied_human_feedback({"human_feedback": []})
