"""Generate a voice clip per shot, real TTS timestamps, and a frame timeline.

Only the edited narration is sent to Microsoft Edge's online TTS service.
Existing audio + matching text hashes are reused; delete that shot's cache to redo it.
"""
import asyncio
import hashlib
import json
import math
import subprocess
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "episodes/001-ai-coding/episode.json"


def probe_duration(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


async def main():
    episode = json.loads(EPISODE.read_text(encoding="utf-8"))
    media = ROOT / "public/episodes" / episode["id"]
    cache = ROOT / ".runtime/tts" / episode["id"]
    media.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    captions = []
    cursor = 0
    fps = episode["fps"]
    for shot in episode["shots"]:
        audio = media / (shot["id"] + ".mp3")
        metadata = cache / (shot["id"] + ".json")
        digest = hashlib.sha256(json.dumps({
            "text": shot["narration"], "voice": episode["voice"],
            "rate": episode["voiceRate"], "boundary": "WordBoundary"
        }, ensure_ascii=False).encode()).hexdigest()
        saved = json.loads(metadata.read_text(encoding="utf-8")) if metadata.exists() else {}
        if saved.get("hash") == digest and audio.exists():
            words = saved["words"]
        else:
            words = []
            communicator = edge_tts.Communicate(
                shot["narration"], episode["voice"], rate=episode["voiceRate"],
                boundary="WordBoundary"
            )
            temporary = audio.with_suffix(".part")
            with temporary.open("wb") as output:
                async for chunk in communicator.stream():
                    if chunk["type"] == "audio":
                        output.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        words.append({
                            "text": chunk["text"], "startMs": chunk["offset"] / 10000,
                            "endMs": (chunk["offset"] + chunk["duration"]) / 10000,
                            "timestampMs": None, "confidence": None
                        })
            if not words or temporary.stat().st_size < 1000:
                raise RuntimeError("TTS did not return usable audio and timestamps")
            temporary.replace(audio)
            metadata.write_text(json.dumps({"hash": digest, "words": words}, ensure_ascii=False, indent=2), encoding="utf-8")
        duration = probe_duration(audio)
        if words[-1]["endMs"] > duration * 1000 + 150:
            raise RuntimeError("Timestamp extends beyond audio")
        # Equal tail silence for every shot; transitions occupy the tail, never speech.
        content_frames = math.ceil(duration * fps) + 18
        shot.update({
            "audio": f"episodes/{episode['id']}/{shot['id']}.mp3",
            "audioDurationSeconds": duration,
            "from": cursor,
            "durationInFrames": content_frames,
            "sequenceDurationInFrames": content_frames + (episode["transitionFrames"] if shot != episode["shots"][-1] else 0),
        })
        narration_cursor = 0
        for word in words:
            # Edge omits punctuation in word-boundary text. Restore punctuation
            # from the exact spoken script while retaining its real word times.
            text = word["text"]
            found = shot["narration"].casefold().find(text.casefold(), narration_cursor)
            if found >= 0:
                end = found + len(text)
                while end < len(shot["narration"]) and shot["narration"][end] in "，。？！：；、,.?!:;":
                    end += 1
                text = shot["narration"][narration_cursor:end]
                narration_cursor = end
            captions.append({**word, "text": text, "startMs": word["startMs"] + cursor / fps * 1000,
                             "endMs": word["endMs"] + cursor / fps * 1000})
        cursor += content_frames
        print(f"{shot['id']}: {duration:.2f}s, {len(words)} timed tokens", flush=True)
    episode.update({"durationInFrames": cursor, "captions": captions,
                    "voiceEngine": "Microsoft Edge online TTS via edge-tts", "version": 1})
    (ROOT / "src").mkdir(exist_ok=True)
    (ROOT / "src/episode.generated.json").write_text(json.dumps(episode, ensure_ascii=False, indent=2), encoding="utf-8")
    (media / "captions.json").write_text(json.dumps(captions, ensure_ascii=False, indent=2), encoding="utf-8")
    script = "\n\n".join(f"{i+1}. {s['narration']}\n画面：{s['visual']}\n时间：{s['from']/fps:.2f}s ～ {(s['from']+s['durationInFrames'])/fps:.2f}s" for i,s in enumerate(episode["shots"]))
    (EPISODE.parent / "script-and-storyboard.md").write_text("# 第一版口播与分镜\n\n" + script, encoding="utf-8")
    print(f"Ready: {cursor} frames, {cursor/fps:.2f}s", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
