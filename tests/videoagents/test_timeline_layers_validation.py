from types import SimpleNamespace

import pytest

from videoagents.tools.timeline import validate_timeline


def _job():
    return SimpleNamespace(
        job_id="job-1",
        brief=SimpleNamespace(width=1080, height=1920, fps=30, usage="personal"),
        assets=[],
        script=None,
    )


def _timeline(layer):
    return SimpleNamespace(
        job_id="job-1",
        width=1080,
        height=1920,
        fps=30,
        audio_src=None,
        shots=[
            SimpleNamespace(
                shot_id="shot-1",
                start_frame=0,
                end_frame=90,
                component_id="conclusion",
                title="真实素材主镜头",
                body="",
                asset_src=None,
                source_label="",
                media_usage="source_evidence",
                props={},
                layers=[] if layer is None else [layer],
            )
        ],
    )


def test_timeline_layers_accept_safe_native_overlay_and_legacy_empty_layers():
    validate_timeline(
        _timeline(
            {
                "component_id": "Snapcn-TextReveal",
                "role": "title",
                "start_frame": 0,
                "end_frame": 30,
                "title": "AI 正在聊天",
                "body": "主镜头素材仍然保留",
                "accent_color": "#38BDF8",
                "props": {"items": ["30 秒 Demo 先看方向"]},
            }
        ),
        _job(),
    )
    validate_timeline(_timeline(None), _job())


@pytest.mark.parametrize(
    "layer, message",
    [
        (
            {
                "component_id": "title",
                "role": "title",
                "start_frame": 0,
                "end_frame": 30,
                "title": "语义适配器层",
                "body": "",
                "accent_color": "#38BDF8",
                "props": {},
            },
            "原生文字/强调组件",
        ),
        (
            {
                "component_id": "Snapcn-TextReveal",
                "role": "title",
                "start_frame": 0,
                "end_frame": 29,
                "title": "太短",
                "body": "",
                "accent_color": "#38BDF8",
                "props": {},
            },
            "30 帧",
        ),

        (
            {
                "component_id": "Snapcn-TextReveal",
                "role": "title",
                "start_frame": 0,
                "end_frame": 30,
                "title": "This native title is far too long to remain readable",
                "body": "",
                "accent_color": "#38BDF8",
                "props": {},
            },
            "32",
        ),
        (
            {
                "component_id": "Snapcn-TextRewrite",
                "role": "title",
                "start_frame": 0,
                "end_frame": 30,
                "title": "改口",
                "body": "",
                "accent_color": "#38BDF8",
                "props": {"from_text": "This previous wording is far too long to read"},
            },
            "32",
        ),
        (
            {
                "component_id": "Snapcn-TextReveal",
                "role": "title",
                "start_frame": 0,
                "end_frame": 30,
                "title": "危险 props",
                "body": "",
                "accent_color": "#38BDF8",
                "props": {"style": "background:url(https://example.com/a.svg)"},
            },
            "不接受参数",
        ),
    ],
)
def test_timeline_layers_reject_unsafe_overlay_shapes(layer, message):
    with pytest.raises(ValueError, match=message):
        validate_timeline(_timeline(layer), _job())
