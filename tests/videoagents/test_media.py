from pathlib import Path

import pytest

from videoagents.tools import media


def test_detect_media_uses_probe_to_distinguish_mp4_video_from_m4a_audio(tmp_path, monkeypatch):
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42unit")

    monkeypatch.setattr(media, "probe", lambda value: {"streams": [{"codec_type": "video"}]})

    assert media.detect_media(path.read_bytes(), path) == ("video/mp4", ".mp4")

    monkeypatch.setattr(media, "probe", lambda value: {"streams": [{"codec_type": "audio"}]})
    assert media.detect_media(path.read_bytes(), path) == ("audio/mp4", ".m4a")


def test_video_metadata_requires_real_duration_dimensions_and_frame_rate(tmp_path, monkeypatch):
    path = tmp_path / "sample.mp4"
    path.write_bytes(b"unit")
    monkeypatch.setattr(media, "probe", lambda value: {
        "format": {"duration": "4.5"},
        "streams": [{"codec_type": "video", "width": 640, "height": 360, "avg_frame_rate": "30000/1001"}],
    })

    result = media.video_metadata(Path(path))

    assert result["duration_seconds"] == 4.5
    assert result["width"] == 640
    assert result["height"] == 360
    assert result["frame_rate"] == pytest.approx(29.97002997)
