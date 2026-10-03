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
           cancelled, progress) -> dict:
    node = shutil.which("node")
    if not node:
        raise ValueError("Node.js 未安装")
    script = project_root / "scripts" / "render-timeline.mjs"
    if not script.is_file():
        raise ValueError("Remotion 渲染入口尚未就绪")
    command = [node, str(script), "--timeline", str(timeline), "--output", str(output), "--mode", mode, "--cover", str(cover)]
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
