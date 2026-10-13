"""Cleanup cannot rewrite a real local CLI's paid-operation outcome."""

import json
import os
import shutil
import sys

import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers import cli_runner
from videoagents.providers.cli_runner import CliFailure, CliResult, run_cli
from videoagents.providers.llm import CapabilityMissing, JsonModel
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


@pytest.fixture
def local_cli(tmp_path, monkeypatch):
    source_home = tmp_path / "source-home"
    source_home.mkdir()
    source_auth = source_home / "auth.json"
    source_auth.write_text('{"test_only_token":"fixture-secret"}', encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(source_home))
    script = tmp_path / "fixture.py"
    prefix = [sys.executable, "-u", str(script)]
    monkeypatch.setattr(cli_runner, "executable_prefix", lambda _: prefix)
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda _: prefix)

    def configure(outcome):
        code = "import json,sys,time\n"
        code += "sys.stdout.reconfigure(encoding='utf-8',errors='strict')\n"
        code += "sys.stdin.buffer.read().decode('utf-8')\n"
        if outcome == "success":
            code += "print(json.dumps({'type':'thread.started'}),flush=True)\n"
            code += "wire={'response_json':json.dumps({'text':'中文结果'},ensure_ascii=False)}\n"
            code += (
                "print(json.dumps({'type':'item.completed','item':{'type':'agent_message',"
                "'text':json.dumps(wire,ensure_ascii=False)}},ensure_ascii=False))\n"
                "print(json.dumps({'type':'turn.completed','usage':{'output_tokens':2}}))\n"
            )
        else:
            # No thread.started: cleanup must still remove the staged credential.
            code += "time.sleep(30)\n"
        script.write_text(code, encoding="utf-8")
        if outcome == "launch":
            prefix[:] = [str(tmp_path / "does-not-exist.exe")]

    return configure, source_auth


@pytest.fixture
def locked_cleanup(monkeypatch):
    original_cleanup = cli_runner.tempfile.TemporaryDirectory.cleanup
    directories = []
    attempts = []
    original_job = cli_runner.WindowsJob

    def configure(resource, failures=None):
        if resource == "directory":
            def cleanup(directory):
                if directory not in directories:
                    directories.append(directory)
                attempts.append(True)
                if failures is None or len(attempts) <= failures:
                    raise PermissionError("fixture-secret arbitrary cleanup filename")
                original_cleanup(directory)
            monkeypatch.setattr(cli_runner.tempfile.TemporaryDirectory, "cleanup", cleanup)
        elif resource == "job":
            class LockedJob(original_job):
                def close(self):
                    super().close()
                    attempts.append(True)
                    raise PermissionError("fixture-secret arbitrary job close error")
            monkeypatch.setattr(cli_runner, "WindowsJob", LockedJob)
        else:
            original_terminate = cli_runner.terminate_tree

            def terminate(process):
                original_terminate(process)
                attempts.append(True)
                raise PermissionError("fixture-secret arbitrary process cleanup error")

            monkeypatch.setattr(cli_runner, "terminate_tree", terminate)
        return attempts

    yield configure
    # Tests create only their own temporary control directories; leave no residue.
    for directory in directories:
        original_cleanup(directory)


@pytest.mark.parametrize("resource", ["directory", "job", "process_tree"])
@pytest.mark.parametrize("outcome", ["success", "timeout", "launch"])
def test_cleanup_preserves_real_cli_result_and_ledger(
    tmp_path, monkeypatch, caplog, local_cli, locked_cleanup, resource, outcome,
):
    configure, source_auth = local_cli
    configure(outcome)
    attempts = locked_cleanup(resource)
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {
        "provider": "codex_cli", "model": "fixture", "timeout_seconds": 30,
    }}))
    actual_run_cli = run_cli

    def bounded_fixture(provider, model, timeout, *args, **kwargs):
        return actual_run_cli(provider, model, 0.2 if outcome == "timeout" else 5, *args, **kwargs)

    monkeypatch.setattr("videoagents.providers.llm.run_cli", bounded_fixture)
    model = JsonModel(repo)
    workspace = tmp_path / "research"
    if outcome == "success":
        assert model.call("fixture", 1, "materials", "中文任务", {}, research_directory=workspace) == {
            "text": "中文结果",
        }
        expected_status, expected_reason = "COMPLETED", None
    else:
        with pytest.raises(CapabilityMissing) as failure:
            model.call("fixture", 1, "materials", "中文任务", {}, research_directory=workspace)
        expected_status = "UNKNOWN" if outcome == "timeout" else "REJECTED"
        expected_reason = "cli_timeout" if outcome == "timeout" else "cli_launch_failed"
        assert failure.value.operation_status == expected_status
    with repo.connection() as db:
        rows = db.execute("SELECT operation_id,status,body FROM operations").fetchall()
    assert len(rows) == 1 and rows[0][1] == expected_status
    ledger = json.loads(rows[0][2])
    assert ledger.get("reason") == expected_reason
    if outcome == "success":
        assert ledger["result"] == {"text": "中文结果"} and ledger["usage"] == {"output_tokens": 2}
    if outcome == "launch" and resource == "process_tree":
        assert not attempts  # No process exists to terminate before launch.
    else:
        assert attempts and "CLI cleanup incomplete" in caplog.text
    assert "fixture-secret" not in caplog.text and "arbitrary" not in caplog.text
    assert source_auth.read_text(encoding="utf-8") == '{"test_only_token":"fixture-secret"}'
    for control in tmp_path.glob(".videoagents-cli-*"):
        assert not (control / "codex-home" / "auth.json").exists()
    if outcome in {"success", "timeout"}:
        monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("must not replay"))
        if outcome == "success":
            assert model.call("fixture", 1, "materials", "中文任务", {}, research_directory=workspace) == {
                "text": "中文结果",
            }
        else:
            with pytest.raises(CapabilityMissing) as second:
                model.call("fixture", 1, "materials", "changed", {}, research_directory=workspace)
            assert second.value.operation_status == "UNKNOWN" and second.value.operation_id == rows[0][0]
        with repo.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM operations").fetchone()[0] == 1


def test_transient_directory_lock_is_retried_before_returning_result(tmp_path, caplog, local_cli, locked_cleanup):
    configure, _ = local_cli
    configure("success")
    attempts = locked_cleanup("directory", failures=1)
    assert run_cli("codex_cli", "fixture", 5, "中文任务", {}, research_directory=tmp_path / "research") == (
        CliResult({"text": "中文结果"}, {"output_tokens": 2})
    )
    assert len(attempts) == 2 and not list(tmp_path.glob(".videoagents-cli-*"))
    assert not caplog.text


def test_cleanup_does_not_hide_permission_error_during_output_processing(tmp_path, monkeypatch, local_cli):
    configure, _ = local_cli
    configure("success")

    def fail_output(*args, **kwargs):
        raise PermissionError("fixture-secret output processing error")

    monkeypatch.setattr(cli_runner, "_codex_event", fail_output)
    with pytest.raises(CliFailure) as failure:
        run_cli("codex_cli", "fixture", 5, "fixture", {}, research_directory=tmp_path / "research")
    assert failure.value.reason == "invalid_cli_output" and failure.value.submitted
    assert "fixture-secret" not in str(failure.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows file-sharing lock regression")
def test_real_windows_file_lock_preserves_success_and_removes_staged_auth(tmp_path, monkeypatch, caplog, local_cli):
    import ctypes
    from ctypes import wintypes

    configure, source_auth = local_cli
    configure("success")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    original_popen = cli_runner.subprocess.Popen
    handles, controls = [], []

    def launch_with_locked_sqlite(*args, **kwargs):
        if args[0][0] == sys.executable:
            home = cli_runner.Path(kwargs["env"]["CODEX_HOME"])
            locked_file = home / "sqlite" / "fixture.sqlite"
            locked_file.write_text("fixture-only SQLite lock", encoding="utf-8")
            # Share read/write, but hold back FILE_SHARE_DELETE like a live SQLite handle.
            handle = kernel.CreateFileW(str(locked_file), 0x80000000, 0x3, None, 3, 0x80, None)
            if handle == wintypes.HANDLE(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            handles.append(handle)
            controls.append(home.parent)
        return original_popen(*args, **kwargs)

    monkeypatch.setattr(cli_runner.subprocess, "Popen", launch_with_locked_sqlite)
    try:
        result = run_cli("codex_cli", "fixture", 5, "中文任务", {}, research_directory=tmp_path / "research")
        assert result == CliResult({"text": "中文结果"}, {"output_tokens": 2})
        assert len(controls) == 1 and controls[0].exists()
        assert not (controls[0] / "codex-home" / "auth.json").exists() and source_auth.exists()
        assert "CLI cleanup incomplete (control_directory)" in caplog.text
        assert "fixture-secret" not in caplog.text and "fixture.sqlite" not in caplog.text
    finally:
        for handle in handles:
            kernel.CloseHandle(handle)
        for control in controls:
            assert control.resolve().is_relative_to(tmp_path.resolve())
            assert control.name.startswith(".videoagents-cli-")
            shutil.rmtree(control, ignore_errors=False)
