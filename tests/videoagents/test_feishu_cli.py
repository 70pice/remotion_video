"""Lark executable resolution and shell-free, UTF-8 subprocess transport."""

import json
import os
import subprocess

import pytest

from videoagents.providers import cli_runner, feishu


def test_lark_explicit_executable_is_preserved(tmp_path, monkeypatch):
    executable = tmp_path / "native lark.exe"
    executable.write_bytes(b"fixture executable")
    monkeypatch.setenv("VIDEOAGENTS_LARK_CLI_EXECUTABLE", str(executable))
    assert cli_runner.executable_prefix("lark_cli") == [str(executable.resolve())]


@pytest.mark.skipif(os.name != "nt", reason="Windows npm shim")
def test_lark_windows_npm_shim_uses_installed_native_binary(tmp_path, monkeypatch):
    shim = tmp_path / "lark-cli.cmd"
    shim.write_text("shell content must never execute")
    native = tmp_path / "node_modules/@larksuite/cli/bin/lark-cli.exe"
    native.parent.mkdir(parents=True)
    native.write_bytes(b"fixture native executable")
    monkeypatch.setenv("VIDEOAGENTS_LARK_CLI_EXECUTABLE", str(shim))
    monkeypatch.setattr(cli_runner.shutil, "which", lambda name: None)
    assert cli_runner.executable_prefix("lark_cli") == [str(native.resolve())]
    native.unlink()
    # A JS installer wrapper is insufficient: do not auto-install a binary.
    wrapper = tmp_path / "node_modules/@larksuite/cli/scripts/run.js"
    wrapper.parent.mkdir()
    wrapper.write_text("throw new Error('must never execute installer wrapper')")
    assert cli_runner.executable_prefix("lark_cli") is None


def test_lark_transport_preserves_utf8_json_arguments_without_shell(tmp_path, monkeypatch):
    executable = tmp_path / "native lark.exe"
    executable.write_bytes(b"fixture executable")
    monkeypatch.setenv("VIDEOAGENTS_LARK_CLI_EXECUTABLE", str(executable))
    payload = json.dumps({"create_records": [{"口播": "中文 \"引号\" & echo ${not_a_command}\n下一行"}]}, ensure_ascii=False)
    arguments = ["base", "+record-batch-create", "--json", payload]

    def fake_run(argv, **kwargs):
        assert argv == [str(executable.resolve()), *arguments, "--format", "json"]
        assert kwargs["shell"] is False
        assert kwargs["encoding"] == "utf-8" and kwargs["timeout"] == 180
        return subprocess.CompletedProcess(argv, 0, '{"ok":true,"data":{"name":"中文"}}', "")

    monkeypatch.setattr(feishu.subprocess, "run", fake_run)
    assert feishu._run(arguments, timeout=180) == {"ok": True, "data": {"name": "中文"}}


def test_lark_missing_binary_fails_without_launch(monkeypatch):
    monkeypatch.delenv("VIDEOAGENTS_LARK_CLI_EXECUTABLE", raising=False)
    monkeypatch.setattr(cli_runner.shutil, "which", lambda name: None)
    monkeypatch.setattr(feishu.subprocess, "run", lambda *a, **k: pytest.fail("no executable to launch"))
    with pytest.raises(feishu.FeishuUnavailable, match="lark-cli"):
        feishu._run(["auth", "status"])
