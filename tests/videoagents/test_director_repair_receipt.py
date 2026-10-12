import copy
import io
import json
import os
import struct
import wave
import zlib

from videoagents.contracts import Brief, Script, ScriptSegment
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.common import state_context
from videoagents.nodes.editing import EditingNode
from videoagents.providers.llm import JsonModel
from videoagents.services.jobs import JobService
from videoagents.state import VideoState
from videoagents.storage import Repository
from worker.runner import Worker


def test_repair_receipt_is_completed_and_bound_to_job_role_revision(tmp_path):
    repo = Repository(tmp_path)
    job = repo.create_job(Brief(topic="UNIT repair receipt"))
    other = repo.create_job(Brief(topic="UNIT unrelated job"))
    result = {"shots": [{"shot_id": "UNIT recorded candidate"}]}
    operation = repo.start_operation(job.job_id, "first", "llm:director", {"revision": job.revision})
    repo.finish_operation(operation["operation_id"], "COMPLETED", {"revision": job.revision, "result": result})
    repo.start_operation(job.job_id, "pending", "llm:director", {"revision": job.revision})
    wrong_revision = repo.start_operation(job.job_id, "other-revision", "llm:director", {"revision": job.revision + 1})
    repo.finish_operation(wrong_revision["operation_id"], "COMPLETED", {"revision": job.revision + 1, "result": {"shots": []}})
    assert repo.latest_completed_operation(job.job_id, "llm:director", job.revision)["result"] == result
    assert repo.latest_completed_operation(other.job_id, "llm:director", job.revision) is None
    assert repo.latest_completed_operation(job.job_id, "llm:voice", job.revision) is None


def test_first_rejected_director_candidate_resumes_with_frozen_audio_and_completed_receipt(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="UNIT: director recovery", width=240, height=426, fps=30,
                                target_seconds=2, usage="personal"))
    narration = "测试：这是当前旁白。"
    media = io.BytesIO()
    with wave.open(media, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 36800)
    audio = service.upload(job.job_id, media.getvalue(), "unit.wav", "audio", alignment={
        "origin": "manual", "verified": True,
        "segments": [
            {"segment_id": "s1", "text": "测试：", "start_ms": 120, "end_ms": 1100},
            {"segment_id": "s1", "text": "这是当前旁白。", "start_ms": 1350, "end_ms": 2175},
        ],
    })
    job = repo.get_job(job.job_id)
    job = repo.update_job(job.job_id, job.revision, script=Script(
        title="UNIT: current script", origin="user", revision=job.revision,
        segments=[ScriptSegment(segment_id="s1", narration=narration)],
    ))
    original_audio_metadata = copy.deepcopy(repo.asset_metadata(audio.asset_id))
    calls, completed_candidates = [], []
    monkeypatch.setattr(JsonModel, "available", lambda self, role: role == "director")

    def model(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert role == "director"
        calls.append((command_id, copy.deepcopy(context)))
        assert context["timeline"]["audio_src"] == audio.timeline_src
        assert context["timeline"]["captions"] == [
            {key: item[key] for key in ("text", "start_ms", "end_ms")}
            for item in original_audio_metadata["alignment"]["segments"]
        ]
        shots = copy.deepcopy(context["timeline"]["shots"])
        if len(calls) == 1:
            layer = {"component_id": "Snapcn-TextHighlight", "role": "emphasis", "start_frame": 0,
                     "end_frame": 30, "title": "UNIT: duplicate highlight"}
            shots[0]["layers"] = [layer, copy.deepcopy(layer)]
        else:
            candidate = context["extras"]["timeline_repair_candidate"]
            assert candidate == {"operation_id": completed_candidates[0]["operation_id"],
                                 "result": completed_candidates[0]["result"]}
            assert "同一镜头不能重复组件层 ID" in "；".join(context["extras"]["timeline_repair_issues"])
            assert "layers" not in shots[0]
            shots[0]["title"] = "UNIT: repaired visual"
        result = {
            "shots": shots,
            "segment_performances": [{"segment_id": "s1", "shot_ids": [shots[0]["shot_id"]],
                                      "component_reason": "UNIT: represent the current narration.",
                                      "visual_action": "UNIT: show the repaired continuous shot."}],
            "shot_reviews": [{"shot_id": shots[0]["shot_id"], "review_frame": 30,
                              "component_reason": "UNIT: explain this shot's component choice.",
                              "visual_action": "UNIT: show the repaired stable frame."}],
        }
        operation = repo.start_operation(job_id, command_id, "llm:director", {"revision": revision})
        repo.finish_operation(operation["operation_id"], "COMPLETED", {"revision": revision, "result": result})
        completed_candidates.append({"operation_id": operation["operation_id"], "result": result})
        return result

    monkeypatch.setattr(JsonModel, "call", model)

    def render_frames(project, timeline_path, request_path, output_manifest, timeout, cancelled, progress):
        images = []
        for item in json.loads(request_path.read_text(encoding="utf-8")):
            width, height = 240, 426
            def chunk(name, data):
                return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data))
            header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
            pixels = b"".join(b"\0" + b"\x11\x22\x33" * width for _ in range(height))
            path = output_manifest.parent / "unit-frame.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
                             + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))
            images.append({**item, "width": width, "height": height, "path": str(path)})
        output_manifest.write_text(json.dumps(images), encoding="utf-8")
        return {"images": images}

    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews", render_frames)
    monkeypatch.setattr(EditingNode, "render_video", lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("director input confirmation must not approve a final render")))
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce",
                             "idempotency_key": "unit-first-director"})
    command = repo.claim(os.getpid())
    thread_id = f"job:{job.job_id}:run:{command['command_id']}"
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}
    with VideoProductionGraph(repo, service.project_root) as graph:
        # This fixture starts at a completed audio gate, with an actual imported
        # WAV and its frozen timing metadata; upstream production is unrelated.
        state = state_context(repo, VideoState(job_id=job.job_id, revision=job.revision, action="produce",
                                              run_id=command["command_id"], thread_id=thread_id,
                                              route="director", gate_issues=[], extras={}))
        graph.graph.update_state(config, state, as_node="audio_gate")
        graph.execute(command)
    repo.finish(command["command_id"])
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.pending_input["stage"] == "director"
    assert "同一镜头不能重复组件层 ID" in "；".join(paused.pending_input["issues"])
    assert paused.timeline is None and len(calls) == 1
    assert not any(item.kind in {"director_plan", "storyboard", "timeline", "stage_review"}
                   for item in paused.artifacts)
    assert repo.latest_completed_operation(job.job_id, "llm:director", job.revision)["result"] == completed_candidates[0]["result"]

    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "resume", "decision": "confirm",
                             "note": "UNIT: retry the invalid candidate without changing the audio.",
                             "idempotency_key": "unit-repair-director",
                             "pending_token": paused.pending_input["pending_token"]})
    assert Worker(repo, service.project_root).once()
    saved = repo.get_job(job.job_id)
    assert saved.status == "NEEDS_HUMAN" and saved.pending_input["node_name"] == "director_human_gate", saved.message
    assert len(calls) == 2 and calls[0][0] != calls[1][0]
    assert saved.timeline.shots[0].title == "UNIT: repaired visual"
    assert saved.timeline.audio_src == audio.timeline_src
    assert saved.timeline.duration_in_frames == 69
    assert [item.model_dump() for item in saved.timeline.captions] == calls[0][1]["timeline"]["captions"]
    assert repo.asset_metadata(audio.asset_id) == original_audio_metadata
    assert not any(item.kind in {"stage_review", "final"} for item in saved.artifacts)
    assert repo.operation(job.job_id, calls[0][0], "llm:director")["status"] == "COMPLETED"
    with VideoProductionGraph(repo, service.project_root) as graph:
        checkpoint = graph.graph.get_state(config)
        assert checkpoint.values["alignment"] == original_audio_metadata["alignment"]
        assert checkpoint.interrupts[0].value["pending_token"] == saved.pending_input["pending_token"]
