"""Real approval receipts prove context media; no model, TTS or rendering calls."""

import json

import pytest
from test_director_only_restart import (
    REAL_DIRECTOR_PLAN,
    operations,
    request,
)
from test_director_only_restart import photography_unknown as photography_unknown

from videoagents.contracts import Alignment, Brief, DraftRequest, Timeline
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.director_demo import DirectorDemoNode
from videoagents.nodes.editing import EditingNode
from videoagents.nodes.human_review import HumanReviewNode
from videoagents.providers.llm import JsonModel, semantic
from videoagents.services.context_media import approved_context_sources
from videoagents.services.director_recovery import verify_director_recovery_inputs
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict
from videoagents.storage.repository import fingerprint
from videoagents.tools.timeline import media_coverage_report, validate_media_coverage, validate_timeline

context_job = pytest.mark.parametrize("photography_unknown", ["context"], indirect=True)
LABEL = "另案示例｜context.example｜同类示意｜非报告涉案"


def timeline(job):
    context, report, audio = job.assets
    return Timeline.model_validate({
        "job_id": job.job_id, "revision": job.revision, "width": 1080, "height": 1920, "fps": 30,
        "duration_in_frames": 180, "audio_src": audio.timeline_src,
        "captions": [{"text": job.script.segments[0].narration, "start_ms": 100, "end_ms": 5800}],
        "shots": [
            {"shot_id": "context", "start_frame": 0, "end_frame": 90, "component_id": "Snapcn-PhoneFrame",
             "title": "同类产品界面", "asset_src": context.timeline_src, "source_label": LABEL,
             "media_usage": "context_example", "props": {"content_mode": "media"}},
            {"shot_id": "report", "start_frame": 90, "end_frame": 180, "component_id": "evidence",
             "title": "本报告", "asset_src": report.timeline_src, "source_label": "example.org"},
        ],
    })


@context_job
@pytest.mark.parametrize("recovered", [False, True])
def test_exact_joint_approval_allows_unlinked_context_without_mutating_input(photography_unknown, recovered):
    repo, service, job, _ = photography_unknown
    if recovered:
        job = service.restart_unknown(job.job_id, request(job))
    candidate = timeline(job)
    before, events, ledger = job.model_dump(), repo.events_after(job.job_id, 0), operations(repo, job.job_id)
    assert not job.script.segments[0].asset_ids
    assert job.assets[0].source_url not in job.script.segments[0].source_refs
    with pytest.raises(ValueError, match="文案已关联"):
        validate_timeline(candidate, job)
    proof = approved_context_sources(repo, job, candidate)
    assert proof == {job.assets[0].timeline_src}
    validate_timeline(candidate, job, approved_context_sources=proof)
    report = validate_media_coverage(candidate, job, approved_context_sources=proof)
    assert (report["actual_media_frames"], report["context_example_frames"], report["source_evidence_frames"]) == (180, 90, 90)
    assert report["segments"][0]["eligible_asset_ids"] == [job.assets[1].asset_id]
    assert report["eligible_capacity_frames"] == 180
    # Frozen research retains a rejected third visual. It must not become proof.
    research = next(item for item in job.artifacts if item.kind == "research")
    frozen = json.loads(repo.artifact_path(research.artifact_id)[0].read_text(encoding="utf-8"))
    assert "UNIT-visual-2" in {item["asset_id"] for item in frozen["visuals"]}
    assert job.model_dump() == before and repo.get_job(job.job_id) == job
    assert repo.events_after(job.job_id, 0) == events and operations(repo, job.job_id) == ledger


@pytest.mark.parametrize("photography_unknown", ["context_missing_visual", "context_missing_source_link",
                                                 "context_string_asset_ids"], indirect=True)
def test_approved_media_still_requires_both_frozen_research_links(photography_unknown):
    repo, _, job, _ = photography_unknown
    candidate = timeline(job)
    assert approved_context_sources(repo, job, candidate) == set()
    with pytest.raises(ValueError, match="文案已关联"):
        validate_timeline(candidate, job, approved_context_sources=set())


@context_job
@pytest.mark.parametrize("change", ["missing_approval", "expired", "revise", "file", "metadata", "foreign_path",
                                   "foreign_owner", "script", "research", "unapproved_asset"])
def test_unverified_inputs_never_grant_context_permission(photography_unknown, change):
    repo, service, job, _ = photography_unknown
    candidate = timeline(job)
    if change == "missing_approval":
        approval_id = verify_director_recovery_inputs(repo, job)["approval_artifact_id"]
        job = job.model_copy(update={"artifacts": [item for item in job.artifacts if item.artifact_id != approval_id]})
    elif change == "expired":
        job = job.model_copy(update={"revision": 2, "script": job.script.model_copy(update={"revision": 2})})
    elif change == "revise":
        artifact = next(item for item in reversed(job.artifacts) if item.kind == "stage_review")
        receipt = json.loads(repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8"))
        receipt.update(decision="revise", pending_token="UNIT-later-revise", note="UNIT request revision")
        HumanReviewNode(repo, node_name="human_review_script")._record(job, receipt, "NEEDS_INPUT", "UNIT revise")
        job = repo.get_job(job.job_id)
    elif change in {"file", "research"}:
        artifact_id = job.assets[0].artifact_id if change == "file" else next(
            item.artifact_id for item in job.artifacts if item.kind == "research")
        path = repo.artifact_path(artifact_id)[0]
        data = path.read_bytes()
        path.write_bytes(bytes([data[0] ^ 1]) + data[1:])
    elif change == "metadata":
        metadata = repo.asset_metadata(job.assets[0].asset_id)
        repo.update_asset_metadata(job.assets[0].asset_id, {**metadata, "width": 999})
    elif change == "foreign_path":
        job = job.model_copy(deep=True)
        job.assets[0].timeline_src = "videoagents/another-job/assets/0.png"
    elif change == "foreign_owner":
        other = repo.create_job(Brief(topic="UNIT another task"))
        path, _, _ = repo.artifact_path(job.assets[0].artifact_id)
        foreign = service.register_artifact(other, path, "asset", "image/png")
        job = job.model_copy(deep=True)
        job.assets[0].artifact_id, job.assets[0].url = foreign.artifact_id, foreign.url
    elif change == "unapproved_asset":
        path, _, _ = repo.artifact_path(job.assets[0].artifact_id)
        imported = service.upload(job.job_id, path.read_bytes(), "unreviewed.png", "illustration",
                                  source_url=job.assets[0].source_url)
        job = repo.get_job(job.job_id)
        candidate.shots[0].asset_src = imported.timeline_src
    else:
        job = job.model_copy(deep=True)
        job.script.segments[0].narration += " altered"
    with pytest.raises((Conflict, ValueError)):
        approved_context_sources(repo, job, candidate)


@context_job
@pytest.mark.parametrize("label", [
    "另案示例｜context.example", "另案示例｜context.example｜同类示意",
    "另案示例｜context.example｜非涉案", "同类示意｜非涉案｜context.example",
    "另案示例｜同类示意｜非涉案", "另案示例｜同类示意｜非涉案｜wrong.example",
])
def test_unlinked_context_requires_visible_explanation_and_real_domain(photography_unknown, label):
    repo, _, job, _ = photography_unknown
    candidate = timeline(job)
    candidate.shots[0].source_label = label
    proof = approved_context_sources(repo, job, candidate)
    for validator in (validate_timeline, media_coverage_report):
        with pytest.raises(ValueError, match="另案示例"):
            validator(candidate, job, approved_context_sources=proof)


@context_job
@pytest.mark.parametrize("misuse", ["source_evidence", "evidence_component", "restricted", "decoration"])
def test_context_proof_never_grants_evidence_or_prohibited_media(photography_unknown, misuse):
    repo, _, job, _ = photography_unknown
    candidate = timeline(job)
    proof = approved_context_sources(repo, job, candidate)
    if misuse == "source_evidence":
        candidate.shots[0].media_usage = "source_evidence"
        with pytest.raises(ValueError, match="语义关联"):
            validate_media_coverage(candidate, job, approved_context_sources=proof)
        return
    if misuse == "evidence_component":
        candidate.shots[0].component_id = "evidence"
    else:
        job = job.model_copy(deep=True)
        if misuse == "restricted":
            job.assets[0].license_note = "仅作核验依据"
        else:
            job.assets[0].role = "decoration"
    with pytest.raises(ValueError, match="另案示例"):
        validate_timeline(candidate, job, approved_context_sources=proof)


@context_job
def test_linked_other_case_and_component_sample_keep_existing_rules(photography_unknown, monkeypatch):
    repo, _, job, _ = photography_unknown
    candidate = timeline(job)
    job = job.model_copy(deep=True)
    job.script.segments[0].asset_ids = [job.assets[0].asset_id]
    candidate.shots[0].source_label = "另案示例｜context.example"
    monkeypatch.setattr("videoagents.services.director_recovery.verify_director_recovery_inputs",
                        lambda *args: pytest.fail("Linked media must use the existing rule"))
    assert approved_context_sources(repo, job, candidate) == set()
    validate_timeline(candidate, job)
    candidate.presentation = "component_sample"
    job.script.segments[0].asset_ids = []
    assert approved_context_sources(repo, job, candidate) == set()


@context_job
def test_imported_timeline_uses_same_proof_and_does_not_inherit_changed_script(photography_unknown):
    repo, service, job, _ = photography_unknown
    candidate = timeline(job)
    changed = job.script.model_copy(deep=True)
    changed.segments[0].narration += " changed"
    with pytest.raises(Conflict):
        service.draft(job.job_id, DraftRequest(base_revision=job.revision, timeline=candidate, script=changed))
    assert repo.get_job(job.job_id) == job
    saved = service.draft(job.job_id, DraftRequest(base_revision=job.revision, timeline=candidate))
    assert saved.timeline.shots == candidate.shots and saved.revision == job.revision + 1
    assert saved.script.segments == job.script.segments


@context_job
def test_photography_and_render_prechecks_share_context_proof(photography_unknown, monkeypatch):
    repo, service, job, _ = photography_unknown
    candidate = timeline(job)
    audio = job.assets[-1]
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])
    node = DirectorNode(repo, service)
    calls = []

    def model(job_id, revision, role, instruction, context, command_id="", **kwargs):
        assert role == "director" and "approved_context_sources" not in str(context)
        assert context["extras"]["media_coverage"]["source_evidence_frames"] == 180
        calls.append(context)
        return {"shots": [shot.model_dump() for shot in candidate.shots],
                "segment_performances": [{"segment_id": "s1", "shot_ids": ["context", "report"],
                    "component_reason": "UNIT approved context remains visibly separate", "visual_action": "UNIT read"}],
                "shot_reviews": [{"shot_id": shot.shot_id, "review_frame": shot.start_frame + 30,
                    "component_reason": "UNIT reviewed media", "visual_action": "UNIT visible source"}
                    for shot in candidate.shots]}

    monkeypatch.setattr(node.model, "call", model)
    produced = REAL_DIRECTOR_PLAN(node, job, audio, alignment, 6.0)
    assert produced.shots == candidate.shots and len(calls) == 1
    job = repo.update_job(job.job_id, timeline=produced)
    service.write_json(job, "director_plan.json", node._last_director_plan, "director_plan")
    job = repo.get_job(job.job_id)
    assert REAL_DIRECTOR_PLAN(node, job, audio, alignment, 6.0) == produced and len(calls) == 1

    class PassedPrecheck(Exception):
        pass

    def freeze(asset):
        raise PassedPrecheck

    monkeypatch.setattr(service, "freeze_asset", freeze)
    editing = EditingNode(repo, service)
    monkeypatch.setattr(editing.model, "available", lambda role: False)
    for run in (lambda: DirectorDemoNode(repo, service).render_shots(job),
                lambda: editing.render_video(job, "final")):
        with pytest.raises(PassedPrecheck):
            run()


@context_job
def test_exact_completed_photography_receipt_replays_without_resubmission(photography_unknown, monkeypatch):
    repo, service, job, _ = photography_unknown
    job = service.restart_unknown(job.job_id, request(job))
    candidate = timeline(job)
    audio = job.assets[-1]
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])
    node = DirectorNode(repo, service)
    captured = []
    result = {"shots": [shot.model_dump() for shot in candidate.shots],
              "segment_performances": [{"segment_id": "s1", "shot_ids": ["context", "report"],
                  "component_reason": "UNIT context separated from evidence", "visual_action": "UNIT readable"}],
              "shot_reviews": [{"shot_id": shot.shot_id, "review_frame": shot.start_frame + 30,
                  "component_reason": "UNIT media component", "visual_action": "UNIT review"}
                  for shot in candidate.shots]}

    def capture(job_id, revision, role, instruction, context, command_id="", output_schema=None):
        config = SettingsService(repo).internal()["role_models"][role]
        inputs = {"revision": revision, "provider": config["provider"], "model": config["model"],
                  "instruction": instruction, "schema": output_schema, "context": semantic(context)}
        if config.get("codex_reasoning_effort") is not None:
            inputs["reasoning_effort"] = config["codex_reasoning_effort"]
        captured.append(fingerprint(inputs))
        return result

    monkeypatch.setattr(node.model, "call", capture)
    expected = REAL_DIRECTOR_PLAN(node, job, audio, alignment, 6.0)
    operation = repo.start_operation(job.job_id, captured[0], "llm:director", {"revision": job.revision})
    repo.finish_operation(operation["operation_id"], "COMPLETED", {"revision": job.revision, "result": result})
    before = operations(repo, job.job_id)
    monkeypatch.setattr(node.model, "call", JsonModel(repo).call)
    assert REAL_DIRECTOR_PLAN(node, job, audio, alignment, 6.0) == expected
    assert operations(repo, job.job_id) == before
    assert repo.operation(job.job_id, captured[0], "llm:director")["result"] == result
