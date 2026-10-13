"""Capability probes must expose a readable WAV and remove temporary files."""

import subprocess
import sys
from pathlib import Path

import pytest

from videoagents.providers import ffmpeg_tools


@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe"])
def test_capability_probe_child_can_reopen_temporary_wav(monkeypatch, name):
    run = subprocess.run
    paths = []

    def child_probe(args, **kwargs):
        assert args[0] == "fixture-executable"
        source = args[args.index("-i") + 1] if name == "ffmpeg" else args[-1]
        paths.append(Path(source))
        code = (
            "import json,sys,wave; "
            "media=wave.open(sys.argv[1],'rb'); "
            "assert (media.getnchannels(),media.getsampwidth(),media.getframerate(),media.getnframes())"
            "==(1,2,16000,800); "
            "assert len(media.readframes(800))==1600; "
            "media.close(); print(json.dumps({'streams':[{'codec_type':'audio'}]}))"
        )
        return run([sys.executable, "-c", code, source], **kwargs)

    monkeypatch.setattr(ffmpeg_tools.subprocess, "run", child_probe)
    probe = getattr(ffmpeg_tools, f"_{name}_decodes_wav")
    assert probe("fixture-executable") is True
    assert len(paths) == 1 and not paths[0].exists()


@pytest.mark.parametrize("name", ["ffmpeg", "ffprobe"])
@pytest.mark.parametrize("failure", ["nonzero", "timeout", "launch"])
def test_capability_probe_cleans_wav_after_failure(monkeypatch, name, failure):
    paths = []

    def failed_probe(args, **kwargs):
        source = args[args.index("-i") + 1] if name == "ffmpeg" else args[-1]
        paths.append(Path(source))
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        if failure == "launch":
            raise OSError("fixture launch failure")
        return subprocess.CompletedProcess(args, 1, "", "fixture unsupported WAV")

    monkeypatch.setattr(ffmpeg_tools.subprocess, "run", failed_probe)
    probe = getattr(ffmpeg_tools, f"_{name}_decodes_wav")
    assert probe("fixture-executable") is False
    assert len(paths) == 1 and not paths[0].exists()
