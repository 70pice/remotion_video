"""Real local subprocess checks; no provider or credential is involved."""

import ctypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from worker.process_manager import render


def test_renderer_structured_error_survives_fast_exit(tmp_path, monkeypatch):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "render-timeline.mjs").write_text(
        "import json, sys\nprint(json.dumps({'event':'error','message':'controlled bad timeline'}), flush=True)\nsys.exit(1)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("worker.process_manager.shutil.which", lambda _: sys.executable)
    with pytest.raises(ValueError, match="controlled bad timeline"):
        render(tmp_path, tmp_path / "input.json", tmp_path / "video.mp4", tmp_path / "cover.png", "final", 10, lambda: False, lambda _: None)


def windows_process_alive(process_id):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, process_id)
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        return bool(kernel.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
    finally:
        kernel.CloseHandle(handle)


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object is a Windows runtime contract")
def test_hard_killed_owner_closes_render_job_and_descendants(tmp_path):
    receipt = tmp_path / "owned-processes.json"
    child_code = (
        "import json,os,subprocess,sys,time; from pathlib import Path; "
        "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
        f"Path({str(receipt)!r}).write_text(json.dumps([os.getpid(),child.pid])); time.sleep(30)"
    )
    owner = tmp_path / "owner.py"
    owner.write_text(
        "import subprocess,sys,time\nfrom worker.windows_job import WindowsJob\n"
        "job=WindowsJob()\n"
        f"process=subprocess.Popen([sys.executable,'-c',{child_code!r}])\n"
        "job.assign(process)\ntime.sleep(30)\n",
        encoding="utf-8",
    )
    process = subprocess.Popen([sys.executable, str(owner)], cwd=Path(__file__).resolve().parents[2], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 10
        while not receipt.exists() and time.monotonic() < deadline:
            assert process.poll() is None, "Owner exited before assigning its render process"
            time.sleep(0.05)
        assert receipt.exists()
        descendants = json.loads(receipt.read_text())
        assert all(windows_process_alive(value) for value in descendants)
        # Simulates an abrupt worker death; no Python finally block can execute.
        process.kill()
        process.wait(timeout=5)
        deadline = time.monotonic() + 5
        while any(windows_process_alive(value) for value in descendants) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not any(windows_process_alive(value) for value in descendants)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
