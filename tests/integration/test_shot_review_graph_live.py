"""Opt-in real Remotion smoke through the normal Graph driven by services directly.

The source text, imported test tone and script-review response are test fixtures.
Director, render node, Worker, checkpoint and human gate are real; no approval of
the director package is submitted and no production task is modified.
"""

import hashlib
import io
import json
import os
import wave
from pathlib import Path

import pytest

from videoagents.contracts import Brief, SettingsPatch
from videoagents.nodes.director_review import current_shot_review_artifact
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from worker.runner import Worker


@pytest.mark.skipif(os.getenv("VIDEOAGENTS_RUN_LIVE_RENDER") != "1", reason="opt-in real browser render")
def test_worker_graph_renders_every_shot_and_waits_for_human(tmp_path, monkeypatch):
    project = Path(__file__).resolve().parents[2]
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, project)
    SettingsService(repo).patch(SettingsPatch(
        script_discussion_enabled=False,
        role_models={role: {"enabled": False} for role in
                     ("materials", "screenwriter", "voice", "director", "editing")},
    ))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available",
                        lambda self, role: role == "script_reviewer")

    def reviewer(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert role == "script_reviewer"
        return {"decision": "APPROVE", "summary": "SMOKE: fixture script review only.",
                "strengths": [], "issues": []}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", reviewer)
    texts = ["观点：测试第一镜布局。", "观点：测试第二镜说明。"]
    job = repo.create_job(Brief(topic="SMOKE ONLY: real per-shot PNG gate", script_text="\n".join(texts),
                                target_seconds=12, width=1080, height=1920, fps=30,
                                usage="personal", platform="抖音"))
    media = io.BytesIO()
    with wave.open(media, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 16000 * 12)
    audio = media.getvalue()
    alignment = {"origin": "manual", "verified": True,
                 "audio_sha256": hashlib.sha256(audio).hexdigest(),
                 "note": "SMOKE: fixture timing over an imported silent test tone, not speech.",
                 "segments": [{"segment_id": f"s{index + 1}", "text": text,
                               "start_ms": index * 6000, "end_ms": (index + 1) * 6000}
                              for index, text in enumerate(texts)]}
    service.upload(job.job_id, audio, "smoke-tone.wav", "audio", alignment=alignment)
    job = repo.get_job(job.job_id)
    from videoagents.nodes.materials import collection_fingerprint
    from videoagents.nodes.screenwriter import ScreenwriterNode
    from videoagents.state import VideoState
    ScreenwriterNode(repo, service)(VideoState(job_id=job.job_id, revision=job.revision,
                                               action="produce", run_id="SMOKE-seed", thread_id="SMOKE-seed"))
    job = repo.get_job(job.job_id)
    service.write_json(job, "smoke-research.json", {
        "schema_version": "3", "status": "COMPLETED", "sources": [], "visuals": [],
        "limitations": ["SMOKE: explicit empty fixture research; no real cases or video content."],
        "collection_fingerprint": collection_fingerprint(job),
    }, "research")
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "SMOKE-produce"})
    assert Worker(repo, project).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN" and paused.pending_input["node_name"] == "human_review_script", paused.message
    repo.enqueue(job.job_id, {
        "base_revision": paused.revision, "pending_token": paused.pending_input["pending_token"],
        "decision": "confirm", "note": "SMOKE ONLY: approve fixture script to verify downstream PNG gate.",
        "idempotency_key": "SMOKE-fixture-script-confirm", "action": "resume",
    })
    assert Worker(repo, project).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN" and paused.stage == "director", paused.message
    assert paused.pending_input["review_mode"] == "per_shot_stills"
    assert len(paused.timeline.shots) == 2
    artifact, manifest = current_shot_review_artifact(repo, paused)
    assert len(manifest["items"]) == 2
    assert paused.pending_input["required_shot_ids"] == [item["shot_id"] for item in manifest["items"]]
    assert not any(item.kind in {"preview", "final"} for item in paused.artifacts)
    for item in manifest["items"]:
        image = repo.artifact_path(item["image"]["artifact_id"])[0].read_bytes()
        assert image.startswith(b"\x89PNG\r\n\x1a\n")
    # Store evidence outside the production runtime; do not include tokens.
    evidence = {"job_id": job.job_id, "revision": paused.revision, "status": paused.status,
                "stage": paused.stage, "mode": manifest["mode"],
                "dimensions": [manifest["width"], manifest["height"]],
                "shots": [{"shot_id": item["shot_id"], "frame": item["review_frame"],
                           "path": str(repo.artifact_path(item["image"]["artifact_id"])[0])}
                          for item in manifest["items"]],
                "manifest": str(repo.artifact_path(artifact.artifact_id)[0]),
                "fixture_inputs": "empty research, supplied test text, silent test tone, simulated script reviewer"}
    (tmp_path / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False))
