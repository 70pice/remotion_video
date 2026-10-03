"""Exercise the running studio with labelled test media, including an actual final render.

Run the studio first. This creates a visible TEST task and never confirms publishing.
"""

import argparse
import hashlib
import io
import json
import math
import struct
import sys
import time
import uuid
import wave
import zlib
from pathlib import Path

import httpx


def test_image() -> bytes:
    """A generated test pattern, not a source screenshot or factual evidence."""
    width, height = 96, 96
    rows = b"".join(b"\0" + bytes((28, 75 + row, 122)) * width for row in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def test_audio() -> bytes:
    """Two-second test tone. Deliberately not described as speech or voice cloning."""
    output = io.BytesIO()
    sample_rate = 24000
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"".join(struct.pack("<h", int(4000 * math.sin(2 * math.pi * 440 * index / sample_rate))) for index in range(sample_rate * 2)))
    return output.getvalue()


def require(response: httpx.Response):
    response.raise_for_status()
    return response.json()


def wait_job(client: httpx.Client, job_id: str, timeout: int = 180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = require(client.get(f"/api/jobs/{job_id}"))
        if job["status"] not in {"QUEUED", "RUNNING"}:
            return job
        time.sleep(0.5)
    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


def run(client: httpx.Client, job: dict, action: str):
    require(client.post(f"/api/jobs/{job['job_id']}/runs", json={"base_revision": job["revision"], "action": action, "idempotency_key": str(uuid.uuid4())}))
    return wait_job(client, job["job_id"])


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--evidence", type=Path, default=Path(".runtime/videoagents/smoke-evidence.json"))
    args = parser.parse_args()
    with httpx.Client(base_url=args.api, timeout=30, trust_env=False) as client:
        session = require(client.get("/api/session"))
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        health = require(client.get("/api/health"))
        if not health["worker_alive"]:
            raise RuntimeError("Start the separate worker before running the smoke test")
        settings = require(client.get("/api/settings"))
        if any(settings.get(key) for key in ("llm_configured", "voice_configured", "search_configured", "aligner_configured")):
            raise RuntimeError("Use an isolated unconfigured runtime for test fixtures; this smoke test must not call paid providers")
        job = require(client.post("/api/jobs", json={"topic": "TEST 工作台集成验证", "script_text": "观点：测试音用于工作台集成验证。", "platform": "本机集成测试", "usage": "personal", "width": 360, "height": 640, "fps": 30, "target_seconds": 2}))
        job = run(client, job, "produce")
        if not job.get("script"):
            raise AssertionError(f"Screenwriter did not produce a script: {job['message']}")
        image = test_image()
        image_asset = require(client.post(f"/api/jobs/{job['job_id']}/assets", files={"file": ("TEST-pattern.png", image, "image/png")}, data={"role": "illustration", "license_note": "本机程序生成的测试图案，仅用于集成测试"}))
        job = require(client.get(f"/api/jobs/{job['job_id']}"))
        script = job["script"]
        script["segments"][0]["asset_ids"] = [image_asset["asset_id"]]
        job = require(client.patch(f"/api/jobs/{job['job_id']}/draft", json={"base_revision": job["revision"], "script": script}))
        audio = test_audio()
        segments = job["script"]["segments"]
        if len(segments) != 1:
            raise AssertionError("The smoke fixture expects one short script segment")
        alignment = {"origin": "manual", "verified": True, "audio_sha256": hashlib.sha256(audio).hexdigest(), "segments": [{"segment_id": segments[0]["segment_id"], "text": segments[0]["narration"], "start_ms": 0, "end_ms": 2000}], "note": "TEST fixture timing for a two-second test tone; not a real speech alignment"}
        require(client.post(f"/api/jobs/{job['job_id']}/assets", files={"file": ("TEST-tone.wav", audio, "audio/wav")}, data={"role": "audio", "alignment": json.dumps(alignment, ensure_ascii=False), "license_note": "本机生成的440Hz测试音，不是复刻配音"}))
        job = require(client.get(f"/api/jobs/{job['job_id']}"))
        job = run(client, job, "produce")
        videos = [value for value in job["artifacts"] if value["kind"] == "final"]
        if not videos:
            raise AssertionError(f"No actual final video: {job['status']} {job['message']}")
        response = client.get(videos[-1]["url"], headers={"Range": "bytes=0-31"})
        assert response.status_code == 206 and len(response.content) == 32, "Media Range request failed"
        assert job["status"] != "READY_FOR_PUBLISH", "Test fixture must never automatically approve publishing"
        evidence = {"job_id": job["job_id"], "status": job["status"], "message": job["message"], "artifacts": [{"kind": value["kind"], "sha256": value["sha256"], "size_bytes": value["size_bytes"]} for value in job["artifacts"]], "range_status": response.status_code, "test_only": True, "live_voice_verified": False, "live_llm_verified": False}
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
