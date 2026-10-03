import io
import math
import os
import struct
import wave

import pytest

from videoagents.agents.reviewers import dependency_fingerprint
from videoagents.contracts import Brief, Finding, Review, Script, ScriptSegment
from videoagents.graph import VideoProductionGraph
from videoagents.services.jobs import JobService
from videoagents.storage import Repository
from worker.runner import Worker


def _tone(seconds=2):
    output = io.BytesIO()
    with wave.open(output, "wb") as media:
        media.setnchannels(1)
        media.setsampwidth(2)
        media.setframerate(16000)
        media.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(i / 10))) for i in range(int(seconds * 16000))))
    return output.getvalue()


@pytest.fixture
def manual_job(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="明确标注的测试流程", script_text="观点：测试流程。", target_seconds=2,
                                width=240, height=426, fps=15, usage="personal", platform="测试平台"))
    alignment = {"origin": "manual", "verified": True, "segments": [{"segment_id": "s1", "text": "观点：测试流程。", "start_ms": 0, "end_ms": 1800}]}
    asset = service.upload(job.job_id, _tone(), "test-tone.wav", "audio", license_note="自有测试音，仅用于自动化测试", alignment=alignment)
    return repo, service, repo.get_job(job.job_id), asset


def enqueue(repo, job, action="produce", key="first-command"):
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": action, "idempotency_key": key})
    return repo.get_job(job.job_id)


def test_missing_voice_is_persisted_interrupt_not_fake_audio(tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="观点：测试流程。"))
    enqueue(repo, job)
    assert Worker(repo, tmp_path / "project").once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.stage == "voice"
    assert not any(item.role == "audio" for item in paused.assets)
    assert paused.pending_input["thread_id"]
    assert paused.pending_input["pending_token"]
    with VideoProductionGraph(repo, tmp_path / "project") as graph:
        saved = graph.graph.get_state({"configurable": {"thread_id": paused.pending_input["thread_id"]}})
        assert saved.interrupts
        assert saved.interrupts[0].value["pending_token"] == paused.pending_input["pending_token"]


def test_fact_source_gate_does_not_trigger_tts(monkeypatch, tmp_path):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(script_text="测试数字是十。"))
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", lambda *a, **k: pytest.fail("unverified script reached paid TTS"))
    enqueue(repo, job)
    Worker(repo, tmp_path / "project").once()
    result = repo.get_job(job.job_id)
    assert result.status == "NEEDS_INPUT" and result.stage == "script"


def test_real_imported_audio_measured_timing_generates_storyboard(manual_job):
    repo, service, job, asset = manual_job
    enqueue(repo, job, "storyboard")
    Worker(repo, service.project_root).once()
    result = repo.get_job(job.job_id)
    assert result.status == "DRAFT" and result.stage == "director"
    assert result.timeline.audio_src == asset.timeline_src
    assert result.timeline.duration_in_frames == 30
    assert result.timeline.captions[0].end_ms == 1800
    assert result.timeline.shots[0].start_frame == 0 and result.timeline.shots[-1].end_frame == 30


def test_selected_older_audio_is_used_for_storyboard(manual_job):
    repo, service, job, first = manual_job
    second = service.upload(job.job_id, _tone(3), "second-test-tone.wav", "audio", license_note="自有测试音")
    current = repo.get_job(job.job_id)
    assert repo.active_audio(job.job_id) == second.asset_id
    service.set_alignment(job.job_id, current.revision, first.asset_id, {"origin": "manual", "verified": True,
        "segments": [{"segment_id": "s1", "text": "观点：测试流程。", "start_ms": 0, "end_ms": 1800}]})
    current = repo.get_job(job.job_id)
    enqueue(repo, current, "storyboard")
    Worker(repo, service.project_root).once()
    result = repo.get_job(job.job_id)
    assert result.timeline.audio_src == first.timeline_src
    assert result.timeline.duration_in_frames == 30


def install_isolated_review_doubles(monkeypatch):
    """No real media claim: these doubles test state transitions/fault windows only."""
    def edit(self, job, mode):
        path = self.repo.root / (job.job_id + "-synthetic-render-unit-test.mp4")
        path.write_bytes(b"synthetic-render-unit-test-not-a-production-video")
        artifact = self.service.register_artifact(job, path, "final", "video/mp4")
        self.repo.update_artifact_metadata(artifact.artifact_id, {"dependency_fingerprint": dependency_fingerprint(job)})
        self.service.append_artifact(job.job_id, artifact, job.revision)
    def review(self, job, human_confirmed=False, model_review=True):
        final = next(item for item in job.artifacts if item.kind == "final")
        return Review(status="PASS" if human_confirmed else "NEEDS_HUMAN", findings=[] if human_confirmed else [Finding(
            finding_id="unit-human", severity="warning", category="human_full_review", owner="user", blocking=True, message="UNIT TEST DOUBLE: verify simulated transition")],
            media_sha256=final.sha256, dependency_fingerprint=dependency_fingerprint(job),
            coverage=["unit_test_double"], human_confirmed=human_confirmed)
    monkeypatch.setattr("videoagents.nodes.editing.EditingNode.run", edit)
    monkeypatch.setattr("videoagents.agents.reviewers.Reviewers.run", review)


def resume(repo, job, decision, note="", key="resume-command"):
    payload = {"base_revision": job.revision, "action": "resume", "decision": decision, "note": note,
               "idempotency_key": key, "pending_token": job.pending_input["pending_token"]}
    repo.enqueue(job.job_id, payload)
    return payload


@pytest.mark.parametrize("decision", ["cancel", "revise"])
def test_short_human_note_then_cancel_or_revise_never_publishes(manual_job, monkeypatch, decision):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    worker = Worker(repo, service.project_root)
    enqueue(repo, job)
    worker.once()
    paused = repo.get_job(job.job_id)
    first_token = paused.pending_input["pending_token"]
    resume(repo, paused, "confirm", "short", "first-resume")
    worker.once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN"
    assert paused.pending_input["pending_token"] != first_token
    resume(repo, paused, decision, "完整播放并核验内容、音画和许可的测试说明", "second-resume")
    worker.once()
    result = repo.get_job(job.job_id)
    assert result.status == ("CANCELLED" if decision == "cancel" else "DRAFT"), result.message
    assert not result.review.human_confirmed


def test_resume_reclaim_does_not_answer_a_new_interrupt(manual_job, monkeypatch):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    # Force an initial configuration gate before actual rendering.
    original = VideoProductionGraph.node_timeline_gate
    first = [True]
    def initially_blocked(self, state):
        if first[0]:
            first[0] = False
            return self.blocked(state, "render", ["UNIT TEST: configure render"], ["render"])
        return original(self, state)
    monkeypatch.setattr(VideoProductionGraph, "node_timeline_gate", initially_blocked)
    worker = Worker(repo, service.project_root)
    enqueue(repo, job)
    worker.once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT"
    resume(repo, paused, "confirm", "仅确认配置修复，并未观看任何成片", "configuration-resume")
    command = repo.claim(os.getpid())
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
    human = repo.get_job(job.job_id)
    assert human.status == "NEEDS_HUMAN"
    assert human.pending_input["pending_token"] != paused.pending_input["pending_token"]
    # Simulate crash after graph checkpoint, before command DONE, then execute
    # the same claimed command again: old confirmation must not reach review.
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_HUMAN"
    assert current.pending_input["pending_token"] == human.pending_input["pending_token"]
    assert current.review.human_confirmed is False
    repo.finish(command["command_id"])


def test_finalization_recovers_after_sql_ready_before_graph_checkpoint(manual_job, monkeypatch):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    resume(repo, paused, "confirm", "UNIT TEST 完整播放并核验事实、音画、字幕和素材许可。")
    command = repo.claim(os.getpid())
    original = repo.update_job
    hit = [False]
    def injected(job_id, expected_revision=None, **changes):
        result = original(job_id, expected_revision, **changes)
        if changes.get("status") == "READY_FOR_PUBLISH" and not hit[0]:
            hit[0] = True
            raise SystemExit("UNIT TEST simulated process loss after terminal SQL commit")
        return result
    monkeypatch.setattr(repo, "update_job", injected)
    with VideoProductionGraph(repo, service.project_root) as graph, pytest.raises(SystemExit):
        graph.execute(command)
    assert repo.get_job(job.job_id).status == "READY_FOR_PUBLISH"
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)
    repo.finish(command["command_id"])
    current = repo.get_job(job.job_id)
    assert current.status == "READY_FOR_PUBLISH"
    assert len([item for item in current.artifacts if item.kind == "package"]) == 1


@pytest.mark.parametrize("unknown", [False, True])
def test_reviewer_provider_failure_has_real_resumable_interrupt(manual_job, monkeypatch, unknown):
    install_isolated_review_doubles(monkeypatch)
    from videoagents.providers.llm import CapabilityMissing
    failure = CapabilityMissing("UNIT TEST missing model", ["llm"], operation_status="UNKNOWN" if unknown else None,
        operation_id="unit-unknown-operation" if unknown else None)
    monkeypatch.setattr("videoagents.agents.reviewers.Reviewers.run", lambda *args, **kwargs: (_ for _ in ()).throw(failure))
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT"
    assert paused.pending_input["thread_id"] and paused.pending_input["pending_token"]
    if unknown:
        assert paused.pending_input["operation_status"] == "UNKNOWN"
        assert paused.pending_input["operation_id"] == "unit-unknown-operation"


def test_201_measured_byte_words_fit_alignment_contract():
    from videoagents.contracts import Job
    from videoagents.nodes.voice import from_byte_sentences
    text = "字" * 201
    script = Script(title="测试", origin="user", revision=1, segments=[ScriptSegment(segment_id="s1", narration=text)])
    job = Job(job_id="test", revision=1, status="DRAFT", stage="idle", created_at="test", updated_at="test", message="",
              brief=Brief(topic="test"), script=script)
    words = [{"word": "字", "startTime": i * 0.1, "endTime": (i + 1) * 0.1, "confidence": 1} for i in range(201)]
    result = from_byte_sentences(job, "a" * 64, [{"words": words}])
    assert result is not None and len(result.segments) == 201


def test_human_confirmation_reruns_hard_checks_and_cannot_waive_failure(manual_job, monkeypatch):
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    worker = Worker(repo, service.project_root)
    worker.once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_HUMAN"
    original = VideoProductionGraph.__init__
    def with_new_hard_failure(self, *args, **kwargs):
        original(self, *args, **kwargs)
        def fail_review(job, **kwargs):
            return Review(status="REVISE", findings=[Finding(finding_id="changed-media", severity="error", category="media_hash",
                owner="editing", blocking=True, message="UNIT TEST: final media changed after first review")],
                media_sha256="new-hash", dependency_fingerprint=dependency_fingerprint(job), human_confirmed=False)
        self.reviewers.run = fail_review
    monkeypatch.setattr(VideoProductionGraph, "__init__", with_new_hard_failure)
    resume(repo, paused, "confirm", "UNIT TEST完整播放并核验事实、声音、画面与素材许可。")
    worker.once()
    current = repo.get_job(job.job_id)
    assert current.status == "NEEDS_INPUT"
    assert current.review.status == "REVISE" and not current.review.human_confirmed
    assert current.pending_input["pending_token"] != paused.pending_input["pending_token"]


def test_generated_attachment_rolls_back_metadata_with_job_on_crash(manual_job, monkeypatch):
    from videoagents.contracts import Asset
    repo, service, job, _ = manual_job
    path = repo.root / "unit-generated.wav"
    path.write_bytes(_tone())
    artifact = service.register_artifact(job, path, "voice", "audio/wav")
    generated = Asset(asset_id="unit-generated", name="unit.wav", role="audio", mime_type="audio/wav", size_bytes=artifact.size_bytes,
        sha256=artifact.sha256, artifact_id=artifact.artifact_id, url=artifact.url, timeline_src=f"videoagents/{job.job_id}/assets/unit-generated.wav")
    before = repo.active_audio(job.job_id)
    def crash(*args, **kwargs):
        raise SystemExit("UNIT TEST injected transaction crash")
    monkeypatch.setattr(repo, "_save", crash)
    with pytest.raises(SystemExit):
        repo.attach_generated_audio(job.job_id, job.revision, generated, artifact, {"origin": "byte_http", "alignment": {"test": "fixture"}})
    assert all(asset.asset_id != generated.asset_id for asset in repo.get_job(job.job_id).assets)
    assert repo.asset_metadata(generated.asset_id) == {}
    assert repo.active_audio(job.job_id) == before


def test_stale_pending_token_same_revision_is_rejected(manual_job, monkeypatch):
    from videoagents.storage import Conflict
    install_isolated_review_doubles(monkeypatch)
    repo, service, job, _ = manual_job
    enqueue(repo, job)
    worker = Worker(repo, service.project_root)
    worker.once()
    paused = repo.get_job(job.job_id)
    resume(repo, paused, "confirm", "short", "old-short-answer")
    worker.once()
    current = repo.get_job(job.job_id)
    assert current.revision == paused.revision
    with pytest.raises(Conflict):
        repo.enqueue(job.job_id, {"action": "resume", "base_revision": current.revision, "decision": "confirm",
            "note": "UNIT TEST old answer", "pending_token": paused.pending_input["pending_token"], "idempotency_key": "stale-old-answer"})
