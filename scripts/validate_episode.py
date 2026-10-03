"""Check the generated delivery timeline and the assets it actually consumes."""
import json
import math
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "src/episode.generated.json").read_text(encoding="utf-8"))
fps = data["fps"]
cursor = 0
assert len({shot["id"] for shot in data["shots"]}) == len(data["shots"])
for index, shot in enumerate(data["shots"]):
    assert shot["from"] == cursor, f"Timeline gap at {shot['id']}"
    expected = shot["durationInFrames"] + (data["transitionFrames"] if index < len(data["shots"]) - 1 else 0)
    assert shot["sequenceDurationInFrames"] == expected
    audio = ROOT / "public" / shot["audio"]
    assert audio.exists() and audio.stat().st_size > 1000
    assert math.ceil(shot["audioDurationSeconds"] * fps) <= shot["durationInFrames"] - 18
    cursor += shot["durationInFrames"]
assert cursor == data["durationInFrames"]
assert sum(s["sequenceDurationInFrames"] for s in data["shots"]) - data["transitionFrames"] * (len(data["shots"]) - 1) == cursor
previous = -1
for caption in data["captions"]:
    assert caption["text"] and caption["startMs"] >= previous
    assert 0 <= caption["startMs"] < caption["endMs"] <= cursor / fps * 1000
    previous = caption["endMs"]
for name in ("source-board.png", "source-team.png"):
    assert (ROOT / "public/episodes/001-ai-coding" / name).exists()
video = ROOT / "out/ai-coding-v1.mp4"
if video.exists():
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)], capture_output=True, text=True, check=True).stdout)
    visual = next(s for s in probe["streams"] if s["codec_type"] == "video")
    audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
    assert (visual["width"], visual["height"]) == (data["width"], data["height"])
    assert visual["r_frame_rate"] == f"{fps}/1"
    assert abs(float(probe["format"]["duration"]) - cursor / fps) < 0.15
    assert audio["codec_name"] == "aac" and visual["codec_name"] == "h264"
    print("MP4 checked: H.264, AAC, 1080x1920, 30 fps, matching duration")
print(f"Timeline checked: {len(data['shots'])} shots, {len(data['captions'])} timed tokens, {cursor/fps:.2f}s")
