"""Process ownership and complete-batch checks without Remotion or providers."""

import json
import sys

import pytest

from worker.process_manager import RenderCancelled, render_shot_reviews


def renderer_fixture(tmp_path, monkeypatch, code):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "render-timeline.mjs").write_text(code, encoding="utf-8")
    monkeypatch.setattr("worker.process_manager.shutil.which", lambda _: sys.executable)
    timeline = tmp_path / "timeline.json"
    timeline.write_text(json.dumps({"width": 1080, "height": 1920,
        "shots": [{"shot_id": "first", "start_frame": 0, "end_frame": 30},
                  {"shot_id": "second", "start_frame": 30, "end_frame": 90}]}), encoding="utf-8")
    request = tmp_path / "request.json"
    request.write_text(json.dumps([{"shot_id": "first", "frame": 24},
                                  {"shot_id": "second", "frame": 60}]), encoding="utf-8")
    return timeline, request, tmp_path / "review" / "manifest.json"


def fixture_code(images_expression="images", complete=True):
    return (
        "import json, sys\nfrom pathlib import Path\n"
        "args=sys.argv[1:]\n"
        "output=Path(args[args.index('--output')+1])\n"
        "output.parent.mkdir(parents=True, exist_ok=True)\n"
        "request=json.loads(Path(args[args.index('--review-frames')+1]).read_text())\n"
        "images=[]\n"
        "for i, item in enumerate(request, 1):\n"
        "  path=output.parent / f'shot-{i:03}.png'\n"
        "  path.write_bytes(b'fixture PNG')\n"
        "  images.append({**item, 'width':1080, 'height':1920, 'path':str(path)})\n"
        f"result={images_expression}\n"
        "output.write_text(json.dumps(result), encoding='utf-8')\n"
        "(output.parent / 'argv.json').write_text(json.dumps(args))\n"
        + ("print(json.dumps({'event':'complete','output':str(output),'images':result}), flush=True)\n" if complete else "")
    )


def test_shot_review_process_forwards_request_and_returns_complete_images(tmp_path, monkeypatch):
    timeline, request, output = renderer_fixture(tmp_path, monkeypatch, fixture_code())
    progress = []
    result = render_shot_reviews(tmp_path, timeline, request, output, 10, lambda: False, progress.append)
    argv = json.loads((output.parent / "argv.json").read_text())
    assert argv[argv.index("--mode") + 1] == "shot-review"
    assert argv[argv.index("--review-frames") + 1] == str(request)
    assert "--cover" not in argv and "--start-frame" not in argv
    assert result["event"] == "complete"
    assert [item["shot_id"] for item in result["images"]] == ["first", "second"]
    assert [item["frame"] for item in result["images"]] == [24, 60]


@pytest.mark.parametrize("expression", ["images[:1]", "list(reversed(images))",
    "[images[0], images[0]]", "[{**images[0], 'frame':0}, images[1]]",
    "[{**images[0], 'width':540}, images[1]]",
    "[{**images[0], 'path':str(output.parent.parent / 'outside.png')}, images[1]]"])
def test_shot_review_process_rejects_incomplete_or_mismatched_batch(tmp_path, monkeypatch, expression):
    timeline, request, output = renderer_fixture(tmp_path, monkeypatch, fixture_code(expression))
    with pytest.raises(ValueError, match="镜头|shot|review"):
        render_shot_reviews(tmp_path, timeline, request, output, 10, lambda: False, lambda _: None)


def test_shot_review_process_requires_complete_event(tmp_path, monkeypatch):
    timeline, request, output = renderer_fixture(tmp_path, monkeypatch, fixture_code(complete=False))
    with pytest.raises(ValueError, match="渲染失败"):
        render_shot_reviews(tmp_path, timeline, request, output, 10, lambda: False, lambda _: None)


def test_shot_review_process_surfaces_fast_structured_error(tmp_path, monkeypatch):
    timeline, request, output = renderer_fixture(tmp_path, monkeypatch,
        "import json,sys\nprint(json.dumps({'event':'error','message':'failed shot second'}), flush=True)\nsys.exit(1)\n")
    with pytest.raises(ValueError, match="failed shot second"):
        render_shot_reviews(tmp_path, timeline, request, output, 10, lambda: False, lambda _: None)


def test_shot_review_process_missing_image_never_returns_success(tmp_path, monkeypatch):
    code = fixture_code() + "Path(images[1]['path']).unlink()\n"
    timeline, request, output = renderer_fixture(tmp_path, monkeypatch, code)
    with pytest.raises(ValueError, match="镜头|shot|review"):
        render_shot_reviews(tmp_path, timeline, request, output, 10, lambda: False, lambda _: None)


@pytest.mark.parametrize("cancelled, timeout, error", [(True, 10, RenderCancelled), (False, 0, TimeoutError)])
def test_shot_review_process_preserves_cancellation_and_timeout_ownership(tmp_path, monkeypatch, cancelled, timeout, error):
    timeline, request, output = renderer_fixture(tmp_path, monkeypatch, "import time\ntime.sleep(10)\n")
    with pytest.raises(error):
        render_shot_reviews(tmp_path, timeline, request, output, timeout, lambda: cancelled, lambda _: None)
    assert not output.exists()
