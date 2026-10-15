"""Completed-video visual revisions use real gates and isolated local renders."""

import copy
import json
import sys

import pytest
from test_workflow import (
    confirm_stage_reviews,
    director_model_response,
    install_isolated_render_double,
    stopped_voice_job,
)
from test_workflow import isolated_shot_review_render as isolated_shot_review_render
from test_workflow import manual_job as manual_job

from videoagents.graph import VideoProductionGraph
from videoagents.main import main
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.nodes.voice import VoiceNode

NOTE = "UNIT：仅修改首镜，在原时间窗内拆成连续短镜头；其他镜头、文案、音频与字幕保持不变。"


@pytest.fixture
def completed(manual_job, monkeypatch):
    repo, service, job, audio = manual_job
    job = repo.update_job(job.job_id, brief=job.brief.model_copy(update={"fps": 30}))
    repo, service, job, audio, worker = stopped_voice_job((repo, service, job, audio), monkeypatch)
    install_isolated_render_double(monkeypatch)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda self, role: role == "director")

    def initial(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        shot = context["timeline"]["shots"][0]
        return director_model_response(context, [
            {**shot, "shot_id": "shot-01", "end_frame": 30},
            {**shot, "shot_id": "shot-02", "start_frame": 30},
        ])

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", initial)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "continue_from": "voice",
                             "idempotency_key": "UNIT-initial-visuals"})
    assert worker.once()
    before = confirm_stage_reviews(repo, job.job_id, worker, "UNIT-initial-confirm")
    assert (before.status, before.stage) == ("DRAFT", "complete"), before.message
    result = repo, service, before, audio, worker
    monkeypatch.setattr("videoagents.main.PROJECT_ROOT", service.project_root)
    for node in (ScreenwriterNode, MaterialsNode, VoiceNode, EditingNode):
        monkeypatch.setattr(node, "__call__", lambda *a: pytest.fail("visual revision entered another production role"))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("external model call"))

    def preview(node, current, mode, state=None, *, frame_range=None):
        from videoagents.nodes.director_review import current_plan_artifact
        from videoagents.nodes.reviewers import dependency_fingerprint

        assert mode == "preview" and frame_range == (0, 30)
        plan, _ = current_plan_artifact(repo, current)
        artifact = service.write_json(current, "UNIT-motion-preview.json", {"synthetic": True}, "preview")
        repo.update_artifact_metadata(artifact.artifact_id, {
            "motion_preview": True, "director_plan_sha256": plan.sha256,
            "dependency_fingerprint": dependency_fingerprint(current), "frame_range": list(frame_range),
        })

    monkeypatch.setattr(EditingNode, "render_video", preview)
    return result


def cli(monkeypatch, capsys, repo, job, note_file, *args):
    monkeypatch.setattr(sys, "argv", ["videoagents", "--runtime-dir", str(repo.root),
        "revise-visuals", job.job_id, "--shot-ids", "shot-01", "--note-file", str(note_file),
        "--idempotency-key", "UNIT-visual-revision", *args])
    result = main()
    return result, json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("preview", [False, True])
def test_cli_visual_revision_preserves_frozen_inputs_and_stops_at_full_shot_gate(
        completed, monkeypatch, capsys, tmp_path, preview):
    repo, service, before, audio, worker = completed
    note_file = tmp_path / "visual-note.txt"
    note_file.write_text(NOTE, encoding="utf-8")
    before_files = {a.artifact_id: repo.artifact_path(a.artifact_id)[0].read_bytes() for a in before.artifacts}
    seen = []

    def revised(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        seen.append(copy.deepcopy(context))
        assert role == "director" and revision == before.revision + 1
        assert context["extras"]["director_note"] == NOTE
        assert context["extras"]["visual_revision"]["shot_ids"] == ["shot-01"]
        assert context["timeline"] == before.timeline.model_copy(update={"revision": revision}).model_dump()
        first, second = context["timeline"]["shots"]
        return director_model_response(context, [
            {**first, "shot_id": "shot-01-a", "end_frame": 15, "title": "UNIT first new view"},
            {**first, "shot_id": "shot-01-b", "start_frame": 15, "title": "UNIT second new view"},
            second,
        ])

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", revised)
    flags = ["--preview"] if preview else []
    code, response = cli(monkeypatch, capsys, repo, before, note_file, "--base-revision", str(before.revision), *flags)
    assert code == 0, response
    current = repo.get_job(before.job_id)
    assert (current.revision, current.status, current.stage) == (before.revision + 1, "NEEDS_HUMAN", "director")
    assert current.script.model_copy(update={"revision": before.revision}) == before.script
    assert current.assets == before.assets and current.timeline.audio_src == audio.timeline_src
    assert current.timeline.captions == before.timeline.captions
    assert current.timeline.shots[-1] == before.timeline.shots[-1]
    assert [s.shot_id for s in current.timeline.shots] == ["shot-01-a", "shot-01-b", "shot-02"]
    assert current.pending_input["required_shot_ids"] == ["shot-01-a", "shot-01-b", "shot-02"]
    assert current.pending_input["review_mode"] == "per_shot_stills"
    assert bool([a for a in current.artifacts if a.kind == "preview" and a.revision == current.revision]) is preview
    assert not any(a.kind == "final" and a.revision == current.revision for a in current.artifacts)
    assert len(seen) == 1
    assert all(repo.artifact_path(key)[0].read_bytes() == value for key, value in before_files.items())
    assert cli(monkeypatch, capsys, repo, current, note_file, *flags)[0] == 0
    assert repo.get_job(before.job_id).revision == current.revision and len(seen) == 1
    assert not worker.once()
    with repo.connection() as db:
        command = dict(db.execute("SELECT * FROM commands WHERE idempotency_key='UNIT-visual-revision'").fetchone())
    command.update(status="CLAIMED", payload=json.loads(command["payload"]))
    before_replay = repo.get_job(before.job_id)
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)  # Published gate before command settlement.
    assert repo.get_job(before.job_id).pending_input == before_replay.pending_input and len(seen) == 1
    assert repo.get_job(before.job_id).artifacts == before_replay.artifacts
    note_file.write_text(NOTE + "不同的要求。", encoding="utf-8")
    assert cli(monkeypatch, capsys, repo, current, note_file, *flags)[0] != 0
    assert len(seen) == 1


@pytest.mark.parametrize("drift", ["other-shot", "boundary", "untraceable-id", "unchanged"])
def test_visual_revision_rejects_out_of_scope_changes_before_frame_render(
        completed, monkeypatch, capsys, tmp_path, drift):
    repo, _, before, _, _ = completed
    note_file = tmp_path / "visual-note.txt"
    note_file.write_text(NOTE, encoding="utf-8")
    monkeypatch.setattr("videoagents.nodes.director_demo.render_shot_reviews",
                        lambda *a, **k: pytest.fail("invalid scoped plan reached renderer"))

    def bad(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        shots = copy.deepcopy(context["timeline"]["shots"])
        if drift == "other-shot":
            shots[0]["title"] = "UNIT valid selected edit"
            shots[1]["title"] = "UNIT forbidden change"
        elif drift == "boundary":
            shots[0]["end_frame"] = 31
            shots[1]["start_frame"] = 31
        elif drift == "untraceable-id":
            shots[0]["shot_id"] = "unrelated-new-shot"
        return director_model_response(context, shots)

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", bad)
    assert cli(monkeypatch, capsys, repo, before, note_file)[0] == 0
    current = repo.get_job(before.job_id)
    assert current.status == "NEEDS_INPUT" and current.stage == "director"
    assert current.timeline.shots == before.timeline.shots
    assert not any(a.kind == "director_plan" and a.revision == current.revision for a in current.artifacts)


@pytest.mark.parametrize("invalid", ["cas", "unknown", "active-command", "unknown-shot", "not-complete", "note",
                                     "audio-metadata", "script", "approval"])
def test_visual_revision_preflight_is_atomic(completed, monkeypatch, capsys, tmp_path, invalid):
    repo, _, before, _, _ = completed
    note_file = tmp_path / "visual-note.txt"
    note_file.write_text(" " if invalid == "note" else NOTE, encoding="utf-8")
    args = []
    if invalid == "cas":
        args += ["--base-revision", str(before.revision + 1)]
    elif invalid == "unknown":
        operation = repo.start_operation(before.job_id, "UNIT-pending", "llm:director", {"revision": before.revision})
        repo.finish_operation(operation["operation_id"], "UNKNOWN", {"revision": before.revision})
    elif invalid == "active-command":
        repo.enqueue(before.job_id, {"action": "produce", "base_revision": before.revision,
                                    "idempotency_key": "UNIT-active-command"})
    elif invalid == "unknown-shot":
        args += ["--shot-ids", "shot-missing"]
    elif invalid == "not-complete":
        repo.update_job(before.job_id, stage="director")
    elif invalid == "audio-metadata":
        audio = next(a for a in before.assets if a.role == "audio")
        metadata = repo.asset_metadata(audio.asset_id)
        metadata["duration_seconds"] += 1
        repo.update_asset_metadata(audio.asset_id, metadata)
    elif invalid == "script":
        script = before.script.model_copy(deep=True)
        script.segments[0].narration = "UNIT changed frozen narration"
        repo.update_job(before.job_id, script=script)
    elif invalid == "approval":
        repo.update_job(before.job_id, artifacts=[a for a in before.artifacts if a.kind != "stage_review"])
    before = repo.get_job(before.job_id)
    assert cli(monkeypatch, capsys, repo, before, note_file, *args)[0] != 0
    assert repo.get_job(before.job_id) == before
    with repo.connection() as db:
        assert not db.execute("SELECT 1 FROM commands WHERE idempotency_key='UNIT-visual-revision'").fetchone()
