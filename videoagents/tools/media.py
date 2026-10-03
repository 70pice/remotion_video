"""Real media inspection and bounded process execution."""

import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe(path: Path) -> dict:
    executable = shutil.which("ffprobe")
    if not executable:
        raise ValueError("ffprobe 未安装，无法实测媒体时长")
    result = subprocess.run([executable, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError("媒体不能被 ffprobe 解码")
    return json.loads(result.stdout)


def audio_duration(path: Path) -> float:
    info = probe(path)
    if not any(item.get("codec_type") == "audio" for item in info["streams"]):
        raise ValueError("文件不包含音频轨道")
    duration = float(info.get("format", {}).get("duration", 0))
    if not 0 < duration <= 1800:
        raise ValueError("音频时长必须在 0 到 1800 秒之间")
    return duration


def decode_check(path: Path) -> None:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise ValueError("ffmpeg 未安装，无法完成全片解码审核")
    result = subprocess.run([executable, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"],
                            capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise ValueError("媒体全片解码失败")


def detect_media(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav", ".wav"
    if data.startswith(b"ID3") or (len(data) > 1 and data[0] == 255 and data[1] & 0xE0 == 0xE0):
        return "audio/mpeg", ".mp3"
    if len(data) > 12 and data[4:8] == b"ftyp":
        return "audio/mp4", ".m4a"
    if data.startswith(b"OggS"):
        return "audio/ogg", ".ogg"
    raise ValueError("只支持可解码的 PNG/JPEG/WebP 图片或 WAV/MP3/M4A/AAC/Ogg 音频")
