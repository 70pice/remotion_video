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
    from videoagents.nodes.materials import collection_fingerprint
    from videoagents.nodes.screenwriter import ScreenwriterNode
    from videoagents.state import VideoState
    # The alignment upload advanced the revision; seed against the current one.
    job = repo.get_job(job.job_id)
    ScreenwriterNode(repo, service)(VideoState(job_id=job.job_id, revision=job.revision,
                                               action="produce", run_id="UNIT-seed", thread_id="UNIT-seed"))
    service.write_json(repo.get_job(job.job_id), "cli-research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["CLI TEST: explicit empty fixture research."],
        "collection_fingerprint": collection_fingerprint(repo.get_job(job.job_id))}, "research")

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


def test_poll_revise_on_per_shot_gate_never_sends_shot_ids(tmp_path, monkeypatch, capsys):
    """A Feishu 需修改 answer must not carry the whole-package shot list."""
    from videoagents.providers import feishu

    runtime = tmp_path / "runtime"
    repo = Repository(runtime)
    job = repo.create_job(Brief(topic="per-shot revise", script_text="观点：只此一段。"))
    pending = {"kind": "stage_review", "stage": "director", "node_name": "director_human_gate",
               "title": "摄影逐镜组件与画面审核", "thread_id": "UNIT-t", "revision": job.revision,
               "pending_token": "UNIT-token-123456", "review_mode": "per_shot_stills",
               "required_shot_ids": ["shot1", "shot2"], "confirmation_requirements": ["逐镜核对"],
               "min_note_length": 10}
    repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", stage="director",
                    message="等待人工核对", pending_input=pending)
    monkeypatch.setattr(feishu.FeishuReviewBase, "base_token", lambda self, job_id: "token123")
    monkeypatch.setattr(feishu.FeishuReviewBase, "_table_id", lambda self, token, table: "tbl1")
    monkeypatch.setattr(feishu.FeishuReviewBase, "_find_review", lambda self, token, table_id, tok: "rec1")
    monkeypatch.setattr(feishu.FeishuReviewBase, "poll_decision",
                        lambda self, job, tok, **kw: {"decision": "revise", "note": "第二镜换成真实截图再审核"})

    from videoagents.main import build_parser
    args = build_parser().parse_args(["--runtime-dir", str(runtime), "poll", job.job_id])
    args.handler(args)
    with repo.connection() as db:
        row = db.execute("SELECT payload FROM commands ORDER BY rowid DESC LIMIT 1").fetchone()
    payload = json.loads(row[0])
    assert payload["decision"] == "revise"
    assert "reviewed_shot_ids" not in payload


def test_run_failure_returns_nonzero_with_clean_json_stdout(tmp_path, monkeypatch, capsys):
    """A real execution failure exits non-zero while stdout stays pure JSON."""
    from videoagents.nodes.materials import MaterialsNode

    runtime = tmp_path / "runtime"
    repo = Repository(runtime)
    job = repo.create_job(Brief(topic="fail path", script_text="观点：失败路径。"))

    def boom(self, state):
        raise RuntimeError("UNIT injected failure")

    monkeypatch.setattr(MaterialsNode, "__call__", boom)
    from videoagents.main import build_parser
    args = build_parser().parse_args(["--runtime-dir", str(runtime), "run", job.job_id])
    rc = args.handler(args)
    out = capsys.readouterr().out
    assert rc == 1, out
    summary = json.loads(out)  # stdout must remain parseable JSON
    assert summary["status"] == "FAILED" and "UNIT injected failure" in summary["message"]
