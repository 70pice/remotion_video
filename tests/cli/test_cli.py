"""The operator CLI drives the same durable services the graph has always used."""

import hashlib
import io
import json
import math
import struct
import wave
import zlib

from videoagents.contracts import Brief, SettingsPatch
from videoagents.main import build_parser
from videoagents.nodes.editing import EditingNode
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


def run_cli(argv: list[str]) -> object:
    args = build_parser().parse_args(argv)
    return args.handler(args)


def _tone(seconds: float = 12) -> bytes:
    media = io.BytesIO()
    with wave.open(media, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(
            struct.pack("<h", int(500 * math.sin(i / 10))) for i in range(int(seconds * 16000))))
    return media.getvalue()


def _synthetic_shot_render(monkeypatch):
    """Synthetic PNGs exercise gate receipts without bundling a render project."""
    def render(project, timeline_path, request_path, output_manifest, timeout, cancelled, progress):
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        width, height = timeline["width"], timeline["height"]

        def chunk(name, data):
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
        header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        pixels = b"".join(b"\0" + b"\x11\x22\x33" * width for _ in range(height))
        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")
        images = []
        for index, item in enumerate(json.loads(request_path.read_text(encoding="utf-8")), 1):
            path = output_manifest.parent / f"cli-{index}.png"
            path.write_bytes(png)
            images.append({**item, "width": width, "height": height, "path": str(path)})
        output_manifest.write_text(json.dumps(images), encoding="utf-8")
        return {"images": images}
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", render)


def test_create_status_settings_and_shots_listing(tmp_path, capsys):
    runtime = tmp_path / "runtime"
    brief = tmp_path / "brief.json"
    brief.write_text(json.dumps({"topic": "CLI 冒烟:普通人视角的 AI 进展",
                                 "creative_direction": "从一条真实新闻进入", "target_seconds": 180}),
                     encoding="utf-8")
    run_cli(["--runtime-dir", str(runtime), "create", "--brief", str(brief)])
    created = json.loads(capsys.readouterr().out)
    assert created["status"] == "DRAFT" and created["topic"].startswith("CLI 冒烟")

    run_cli(["--runtime-dir", str(runtime), "status"])
    listed = json.loads(capsys.readouterr().out)
    assert [item["job_id"] for item in listed] == [created["job_id"]]

    run_cli(["--runtime-dir", str(runtime), "settings", "get"])
    public = json.loads(capsys.readouterr().out)
    assert public["llm_configured"] is True and "zhipu_api_key" not in public

    run_cli(["--runtime-dir", str(runtime), "settings", "set", "research_max_searches", "5"])
    patched = json.loads(capsys.readouterr().out)
    assert patched["research_max_searches"] == 5


def test_run_pauses_at_script_gate_resume_confirms_and_shots_list(tmp_path, monkeypatch, capsys):
    runtime = tmp_path / "runtime"
    project = tmp_path / "project"
    repo = Repository(runtime)
    service = JobService(repo, project)
    SettingsService(repo).patch(SettingsPatch(script_discussion_enabled=False,
        role_models={role: {"enabled": False} for role in ("materials", "screenwriter", "voice", "director", "editing")}))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available",
                        lambda self, role: role == "script_reviewer")
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call",
                        lambda self, *a, **k: {"decision": "APPROVE", "summary": "CLI TEST：可进入人工审核。",
                                               "strengths": [], "issues": []})
    _synthetic_shot_render(monkeypatch)
    final_renders = []
    monkeypatch.setattr(EditingNode, "render_video",
                        lambda self, job, mode, state=None: final_renders.append(mode))
    argv_tail = ["--runtime-dir", str(runtime)]

    texts = ["观点：CLI 第一段。", "观点：CLI 第二段。"]
    job = repo.create_job(Brief(topic="CLI e2e", script_text="\n".join(texts), target_seconds=12,
                                usage="personal", platform="抖音"))
    tone = tmp_path / "tone.wav"
    tone.write_bytes(_tone())
    alignment = {"origin": "manual", "verified": True, "audio_sha256": hashlib.sha256(tone.read_bytes()).hexdigest(),
                 "note": "CLI TEST fixture timing", "segments": [
                     {"segment_id": f"s{index + 1}", "text": text, "start_ms": index * 6000, "end_ms": (index + 1) * 6000}
                     for index, text in enumerate(texts)]}
    alignment_file = tmp_path / "alignment.json"
    alignment_file.write_text(json.dumps(alignment, ensure_ascii=False), encoding="utf-8")
    run_cli([*argv_tail, "upload", job.job_id, str(tone), "--role", "audio",
             "--alignment", str(alignment_file), "--license-note", "CLI TEST fixture tone"])
    capsys.readouterr()
    service.write_json(repo.get_job(job.job_id), "cli-research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["CLI TEST: explicit empty fixture research."]}, "research")

    run_cli([*argv_tail, "run", job.job_id])
    paused = json.loads(capsys.readouterr().out)
    assert paused["status"] == "NEEDS_HUMAN" and paused["stage"] == "script", paused
    run_cli([*argv_tail, "status", job.job_id])
    detail = json.loads(capsys.readouterr().out)
    assert detail["pending_input"]["node_name"] == "human_review_script"

    run_cli([*argv_tail, "resume", job.job_id, "--decision", "confirm",
             "--note", "CLI TEST：确认文案与素材，继续制作。"])
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["stage"] == "director" and resumed["status"] == "NEEDS_HUMAN", resumed

    run_cli([*argv_tail, "shots", job.job_id])
    shots = json.loads(capsys.readouterr().out)
    assert len(shots["shots"]) == 2
    assert all(item["image"].endswith(".png") for item in shots["shots"])
    assert shots["required_shot_ids"] == [item["shot_id"] for item in shots["shots"]]

    run_cli([*argv_tail, "resume", job.job_id, "--decision", "confirm",
             "--note", "CLI TEST：逐镜整包确认，允许渲染成片。",
             "--shot-ids", ",".join(item["shot_id"] for item in shots["shots"])])
    final = json.loads(capsys.readouterr().out)
    # The editing node reached its final render (doubled here); a real
    # end-to-end MP4 smoke runs in the opt-in live test.
    assert final == {**final, "stage": "complete", "status": "DRAFT"}
    assert final_renders == ["final"]
