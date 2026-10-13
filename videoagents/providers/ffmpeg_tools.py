"""Resolve a capable ffmpeg/ffprobe instead of trusting PATH order.

PATH 上第一个 ffmpeg/ffprobe 可能来自某个 IDE 的裁剪构建，连标准 PCM WAV
都无法解码。这里在候选中逐个做真实能力探活：能解码一段内嵌的最小 WAV 才
可用。显式配置优先：环境变量 ``VIDEOAGENTS_FFMPEG`` / ``VIDEOAGENTS_FFPROBE``
或设置里的 ``ffmpeg_path`` / ``ffprobe_path``。
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

PROBE_TIMEOUT_SECONDS = 20

# A complete 16 kHz mono 16-bit PCM WAV (~0.05 s of silence). Embedded so the
# capability check needs no fixture on disk and works on any checkout.
_SILENT_WAV = io.BytesIO()
with wave.open(_SILENT_WAV, "wb") as _media:
    _media.setnchannels(1)
    _media.setsampwidth(2)
    _media.setframerate(16000)
    _media.writeframes(b"\x00\x00" * 800)


class FFmpegMissing(ValueError):
    """No capable binary was found; the message explains how to fix it."""


def _candidates(name: str, override: str | None) -> list[str]:
    if override:
        resolved = Path(override).expanduser()
        return [str(resolved)]
    found: list[str] = []
    seen: set[str] = set()
    for directory in os.getenv("PATH", "").split(os.pathsep):
        base = Path(directory) / name
        for candidate in (base, base.with_suffix(".exe")):
            try:
                text = str(candidate.resolve())
            except OSError:
                continue
            if text in seen:
                continue
            seen.add(text)
            if candidate.is_file() and os.access(candidate, os.X_OK):
                found.append(text)
    return found


def _ffprobe_decodes_wav(executable: str) -> bool:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="videoagents-ffprobe-check-") as directory:
        source = Path(directory) / "probe.wav"
        # Close the writer before spawning: Windows locks open temporary files.
        source.write_bytes(_SILENT_WAV.getvalue())
        try:
            result = subprocess.run(
                [executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(source)],
                capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
    if result.returncode:
        return False
    try:
        info = json.loads(result.stdout)
    except ValueError:
        return False
    return any(stream.get("codec_type") == "audio" for stream in info.get("streams", []))


def _ffmpeg_decodes_wav(executable: str) -> bool:
    import tempfile

    with tempfile.TemporaryDirectory(prefix="videoagents-ffmpeg-check-") as directory:
        source = Path(directory) / "probe.wav"
        source.write_bytes(_SILENT_WAV.getvalue())
        try:
            result = subprocess.run(
                [executable, "-v", "error", "-xerror", "-i", str(source), "-f", "null", "-"],
                capture_output=True, text=True, timeout=PROBE_TIMEOUT_SECONDS, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
    return result.returncode == 0


def _resolve(name: str, override: str | None, capable) -> str:
    candidates = _candidates(name, override)
    for candidate in candidates:
        if capable(candidate):
            return candidate
    if candidates:
        raise FFmpegMissing(
            f"PATH 上的 {name} 无法解码标准 WAV（可能是某个应用自带的裁剪构建）。"
            f"请安装完整版本（macOS: brew install ffmpeg）或用环境变量 "
            f"VIDEOAGENTS_{name.upper()} 指定路径。")
    raise FFmpegMissing(
        f"未找到可用的 {name}。请安装 ffmpeg（macOS: brew install ffmpeg，"
        f"Windows: 下载后将目录加入 PATH），或用环境变量 VIDEOAGENTS_{name.upper()} 指定路径。")


@lru_cache(maxsize=None)
def ffmpeg_executable() -> str:
    return _resolve("ffmpeg", os.getenv("VIDEOAGENTS_FFMPEG"), _ffmpeg_decodes_wav)


@lru_cache(maxsize=None)
def ffprobe_executable() -> str:
    return _resolve("ffprobe", os.getenv("VIDEOAGENTS_FFPROBE"), _ffprobe_decodes_wav)


def reset_resolution_cache() -> None:
    """Tests monkeypatch the environment; clear the memoized binaries."""
    ffmpeg_executable.cache_clear()
    ffprobe_executable.cache_clear()


def which_ffmpeg() -> str:
    return ffmpeg_executable()


def which_ffprobe() -> str:
    return ffprobe_executable()
