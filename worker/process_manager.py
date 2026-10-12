"""Fixed renderer invocation; descendants are killed on cancellation and timeout."""

import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path

from worker.windows_job import WindowsJob


class RenderCancelled(Exception):
    pass


def terminate_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15, check=False)
    else:
        import signal
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def render(project_root: Path, timeline: Path, output: Path, cover: Path, mode: str, timeout: int,
           cancelled, progress, frame_range: tuple[int, int] | None = None) -> dict:
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js 未安装")
    script = project_root / "scripts" / "render-timeline.mjs"
    if not script.is_file():
        raise ValueError("Remotion 渲染入口尚未就绪")
    command = [node, str(script), "--timeline", str(timeline), "--output", str(output), "--mode", mode, "--cover", str(cover)]
    if frame_range is not None:
        if mode != "preview":
            raise ValueError("final render does not accept a frame range")
        start_frame, end_frame = frame_range
        if type(start_frame) is not int or type(end_frame) is not int or start_frame < 0 or end_frame <= start_frame:
            raise ValueError("frame_range must be a nonempty half-open frame interval")
        command.extend(["--start-frame", str(start_frame), "--end-frame", str(end_frame)])
    return _run_render(project_root, command, output, timeout, cancelled, progress)


def render_shot_reviews(project_root: Path, timeline: Path, request: Path, output_manifest: Path,
                        timeout: int, cancelled, progress) -> dict:
    """Render a complete one-PNG-per-shot batch from canonical timeline frames."""
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js 未安装")
    script = project_root / "scripts" / "render-timeline.mjs"
    if not script.is_file():
        raise ValueError("Remotion 渲染入口尚未就绪")
    if output_manifest.exists():
        raise ValueError("镜头审核 manifest 已存在，不能覆盖")
    try:
        requests = json.loads(request.read_text(encoding="utf-8-sig"))
        source = json.loads(timeline.read_text(encoding="utf-8-sig"))
        shots = source["shots"]
        width, height = source["width"], source["height"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ValueError("镜头审核请求或时间轴不可读取") from exc
    if not isinstance(requests, list) or len(requests) != len(shots) or not requests:
        raise ValueError("镜头审核请求须按顺序覆盖全部镜头")
    for item, shot in zip(requests, shots, strict=True):
        if (not isinstance(item, dict) or set(item) != {"shot_id", "frame"}
                or item["shot_id"] != shot["shot_id"] or type(item["frame"]) is not int
                or not shot["start_frame"] <= item["frame"] < shot["end_frame"]):
            raise ValueError("镜头审核请求 ID、顺序或绝对帧不匹配")
    command = [node, str(script), "--timeline", str(timeline), "--review-frames", str(request),
               "--output", str(output_manifest), "--mode", "shot-review"]
    result = _run_render(project_root, command, output_manifest, timeout, cancelled, progress)
    try:
        images = json.loads(output_manifest.read_text(encoding="utf-8-sig"))
        if not isinstance(images, list) or len(images) != len(requests) or result.get("images") != images:
            raise ValueError("镜头审核渲染结果必须完整匹配 manifest")
        for index, (image, requested) in enumerate(zip(images, requests, strict=True), 1):
            if (not isinstance(image, dict) or set(image) != {"shot_id", "frame", "width", "height", "path"}
                    or image["shot_id"] != requested["shot_id"] or image["frame"] != requested["frame"]
                    or type(image["frame"]) is not int or type(image["width"]) is not int
                    or type(image["height"]) is not int or (image["width"], image["height"]) != (width, height)):
                raise ValueError("镜头审核渲染的 ID、帧或原始尺寸不匹配")
            path = Path(image["path"])
            expected = output_manifest.parent / f"shot-{index:03}.png"
            if (not path.is_absolute() or path != expected or path.is_symlink() or not path.is_file()
                    or path.resolve() != expected.absolute() or path.stat().st_size == 0):
                raise ValueError("镜头审核 PNG 缺失或离开本次输出目录")
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError("镜头审核渲染输出校验失败：" + str(exc)) from exc
    return result


def _run_render(project_root: Path, command: list[str], output: Path, timeout: int,
                cancelled, progress) -> dict:
    """Own renderer lifetime identically for video and per-shot still batches."""
    job = WindowsJob()
    try:
        process = subprocess.Popen(command, cwd=project_root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", errors="replace", bufsize=1,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                   start_new_session=os.name != "nt")
    except BaseException:
        job.close()
        raise
    try:
        job.assign(process)
    except BaseException:
        terminate_tree(process)
        job.close()
        raise
    lines = queue.Queue()
    def read():
        try:
            for line in process.stdout:
                lines.put(line)
        finally:
            lines.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline, complete, last_error = time.monotonic() + timeout, None, ""
    try:
        # Read through EOF, including a completion/error emitted just before exit.
        while True:
            if cancelled():
                raise RenderCancelled("任务已取消")
            if time.monotonic() > deadline:
                raise TimeoutError("渲染超过配置时间上限")
            try:
                line = lines.get(timeout=0.25)
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                last_error = line.strip()[-500:]
                continue
            if event.get("event") == "progress":
                progress(float(event["progress"]))
            elif event.get("event") == "complete":
                complete = event
            elif event.get("event") == "error":
                last_error = str(event.get("message", "渲染器返回错误"))[-2000:]
        if process.wait() != 0 or not complete or not output.is_file():
            raise ValueError("Remotion 渲染失败：" + last_error)
        return complete
    finally:
        terminate_tree(process)
        job.close()
        reader.join(timeout=1)
        process.stdout.close()
