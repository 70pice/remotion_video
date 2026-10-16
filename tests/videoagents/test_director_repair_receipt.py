import copy
import io
import json
import os
import struct
import wave
import zlib

import pytest
from test_director_model_contract import director_job

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


@pytest.mark.parametrize("failure", ["duplicate_layer", "render_fit", "legacy_render_fit"])
def test_first_rejected_director_candidate_resumes_with_frozen_audio_and_completed_receipt(tmp_path, monkeypatch, failure):
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
    issue = ("同一镜头不能重复组件层 ID" if failure == "duplicate_layer" else
             "Remotion 渲染失败：ProgressSteps production slot 476x220 cannot fit 3 steps at 34px "
             "with at most two lines per step. Increase this slot or split the steps.")
    render_calls = []
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
        if len(calls) == 1 and failure == "duplicate_layer":
            layer = {"component_id": "Snapcn-TextHighlight", "role": "emphasis", "start_frame": 0,
                     "end_frame": 30, "title": "UNIT: duplicate highlight"}
            shots[0]["layers"] = [layer, copy.deepcopy(layer)]
        elif len(calls) > 1:
            candidate = context["extras"]["timeline_repair_candidate"]
            assert candidate == {"operation_id": completed_candidates[0]["operation_id"],
                                 "result": completed_candidates[0]["result"]}
            assert issue in "；".join(context["extras"]["timeline_repair_issues"])
            assert context["extras"].get("timeline_repair_note") == (
                "UNIT: retry the invalid candidate without changing the audio.")
            assert not shots[0].get("layers")
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
        render_calls.append(str(timeline_path))
        if failure != "duplicate_layer" and len(render_calls) == 1:
            raise ValueError(issue)
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
    if failure == "legacy_render_fit":
        # Persist the former render-only pause, then recover it through the
        # current normal resume path without patching its checkpoint or SQL.
        monkeypatch.setattr("videoagents.nodes.director_demo.render_text_fit_issues", lambda issues: False)
    for node in ("screenwriter.ScreenwriterNode", "materials.MaterialsNode", "voice.VoiceNode"):
        monkeypatch.setattr(f"videoagents.nodes.{node}.__call__", lambda *args: pytest.fail("Must retain upstream"))
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
    assert issue in "；".join(paused.pending_input["issues"])
    assert len(calls) == 1
    if failure == "duplicate_layer":
        assert paused.timeline is None
        assert not any(item.kind in {"director_plan", "storyboard", "timeline", "stage_review"}
                       for item in paused.artifacts)
    else:
        assert paused.timeline is not None
        assert (paused.pending_input.get("retry_node") == "director_demo") == (failure == "legacy_render_fit")
        assert not any(item.kind in {"director_shot_review", "shot_review_frame", "stage_review", "final"}
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


@pytest.mark.parametrize("case", [
    "current", "stage_review", "human_review", "voice", "stale_token", "missing_token",
    "no_pending", "revise", "cancel", "empty", "whitespace", "not_text", "no_issues", "no_decision",
])
def test_director_repair_note_is_bound_to_current_input_confirmation(tmp_path, monkeypatch, case):
    node, job, audio, alignment = director_job(tmp_path, image=False)
    pending = {"kind": "input", "stage": "director", "pending_token": "UNIT current token"}
    decision = {**pending, "decision": "confirm", "note": "UNIT current repair requirement",
                "approval_ledger": "UNIT not a model input"}
    state = VideoState(job_id=job.job_id, revision=job.revision, pending_snapshot=pending,
        gate_issues=["UNIT rejected visual"], human_decision=decision,
        human_reviews=[{"approved": True, "note": "UNIT not a model input"}],
        extras={"director_note": "UNIT older recovery note", "timeline_repair_note": "UNIT stale note"})
    if case in {"stage_review", "human_review"}:
        pending["kind"] = case
    elif case == "voice":
        pending["stage"] = "voice"
    elif case == "stale_token":
        decision["pending_token"] = "UNIT old token"
    elif case == "missing_token":
        pending.pop("pending_token")
        decision.pop("pending_token")
    elif case == "no_pending":
        state["pending_snapshot"] = None
    elif case in {"revise", "cancel"}:
        decision["decision"] = case
    elif case in {"empty", "whitespace", "not_text"}:
        decision["note"] = {"empty": "", "whitespace": " \n\t", "not_text": 42}[case]
    elif case == "no_issues":
        state["gate_issues"] = []
    elif case == "no_decision":
        state["human_decision"] = None
    original = copy.deepcopy(state)
    captured = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        captured.append((instruction, copy.deepcopy(context)))
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    node.plan(job, audio, alignment, 2.0, state=state)
    instruction, context = captured[0]
    assert "human_decision" not in context and "human_reviews" not in context
    assert "approval_ledger" not in json.dumps(context)
    assert context["extras"]["director_note"] == "UNIT older recovery note"
    if case == "current":
        assert context["extras"]["timeline_repair_note"] == decision["note"]
        assert "优先于 extras.director_note" in instruction
        assert "确认意见不代表审核通过" in instruction
    else:
        assert "timeline_repair_note" not in context["extras"]
        assert "阅读 extras.timeline_repair_note" not in instruction
    assert state == original
    assert node.repo.get_job(job.job_id) == job


def test_empty_confirmation_keeps_original_director_request_fingerprint(tmp_path, monkeypatch):
    from videoagents.nodes.director import director_prompt
    from videoagents.providers.llm import request_fingerprint

    node, job, audio, alignment = director_job(tmp_path, image=False)
    state = VideoState(job_id=job.job_id, revision=job.revision,
        pending_snapshot={"kind": "input", "stage": "director", "pending_token": "UNIT current token"},
        gate_issues=["UNIT rejected visual"], extras={"director_note": "UNIT older recovery note"})
    captured = []
    monkeypatch.setattr(node.model, "available", lambda role: True)

    def model(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        captured.append((instruction, copy.deepcopy(output_schema), copy.deepcopy(context)))
        return {"shots": context["timeline"]["shots"]}

    monkeypatch.setattr(node.model, "call", model)
    node.plan(job, audio, alignment, 2.0, state=state)
    state["human_decision"] = {"decision": "confirm", "pending_token": "UNIT current token", "note": ""}
    node.plan(job, audio, alignment, 2.0, state=state)
    state["human_decision"]["note"] = "UNIT add concrete repair details"
    node.plan(job, audio, alignment, 2.0, state=state)
    config = {"provider": "codex_cli", "model": "UNIT fixture", "codex_reasoning_effort": "xhigh"}
    identities = [request_fingerprint(job.revision, config, *request) for request in captured]
    assert captured[0] == captured[1]
    assert captured[0][0] == director_prompt(job.brief.usage)
    assert identities[0] == identities[1] and identities[1] != identities[2]
