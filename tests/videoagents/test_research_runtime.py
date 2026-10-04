import os
import sys
from pathlib import Path

from videoagents.tools import research


def test_command_prefix_falls_back_to_user_local_bin(tmp_path, monkeypatch):
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    executable = local_bin / ("yt-dlp.exe" if os.name == "nt" else "yt-dlp")
    executable.write_text("", encoding="utf-8")

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(research, "_user_local_bin", lambda: local_bin)

    assert research._command_prefix("yt-dlp") == [str(executable.resolve())]


def test_run_prepends_user_local_bin_and_sets_utf8_env(tmp_path, monkeypatch):
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    monkeypatch.setattr(research, "_user_local_bin", lambda: local_bin)
    monkeypatch.setenv("PATH", str(tmp_path / "existing"))
    monkeypatch.delenv("PYTHONUTF8", raising=False)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)

    output = research._run([
        sys.executable,
        "-c",
        "import json, os; print(json.dumps({'path': os.environ['PATH'], "
        "'pythonutf8': os.environ.get('PYTHONUTF8'), "
        "'pythonioencoding': os.environ.get('PYTHONIOENCODING')}))",
    ])

    data = research.json.loads(output)
    assert data["path"].split(os.pathsep)[0] == str(local_bin)
    if os.name == "nt":
        assert data["pythonutf8"] == "1"
        assert data["pythonioencoding"] == "utf-8"


def test_command_prefix_keeps_path_precedence(tmp_path, monkeypatch):
    local_bin = tmp_path / ".local" / "bin"
    path_bin = tmp_path / "path-bin"
    local_bin.mkdir(parents=True)
    path_bin.mkdir()
    suffix = ".exe" if os.name == "nt" else ""
    local_executable = local_bin / f"bili{suffix}"
    path_executable = path_bin / f"bili{suffix}"
    local_executable.write_text("", encoding="utf-8")
    path_executable.write_text("", encoding="utf-8")

    monkeypatch.setenv("PATH", str(path_bin))
    monkeypatch.setattr(research, "_user_local_bin", lambda: local_bin)

    assert research._command_prefix("bili") == [str(Path(path_executable).resolve())]


def test_youtube_search_uses_flat_metadata(monkeypatch):
    calls = []
    monkeypatch.setattr(research, "_command_prefix", lambda name: ["yt-dlp.exe"])

    def fake_run(args, **kwargs):
        calls.append(args)
        return (
            '{"webpage_url":"https://www.youtube.com/watch?v=unit","title":"Unit",'
            '"description":"short","thumbnails":[{"url":"https://i.ytimg.com/unit.jpg"}]}\n'
        )

    monkeypatch.setattr(research, "_run", fake_run)

    assert research._youtube("Muse", 1)[0]["images"] == [{
        "url": "https://i.ytimg.com/unit.jpg",
        "source_url": "https://www.youtube.com/watch?v=unit",
        "description": "Unit",
    }]
    assert calls == [["yt-dlp.exe", "--flat-playlist", "--dump-json", "ytsearch1:Muse"]]
