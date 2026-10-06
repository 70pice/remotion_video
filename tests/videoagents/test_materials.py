import io
import json
import math
import struct
import wave

import pytest

from videoagents.contracts import Alignment, Asset, Brief, Script, ScriptSegment, SettingsPatch
from videoagents.graph import VideoProductionGraph
from videoagents.nodes.director import DirectorNode
from videoagents.nodes.materials import MaterialsNode
from videoagents.nodes.screenwriter import ScreenwriterNode
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Conflict, Repository
from videoagents.tools.media import sha256
from worker.process_manager import RenderCancelled
from worker.runner import Worker

PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT\x08\xd7c\xf8\xff\xff?"
    b"\x00\x05\xfe\x02\xfeA\xe2%\x1b\x00\x00\x00\x00IEND\xaeB`\x82"
)
MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomUNIT"


def make_repo(tmp_path):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    return repo, service


def state_for(job):
    return {
        "job_id": job.job_id,
        "revision": job.revision,
        "action": "produce",
        "run_id": "unit-run",
        "thread_id": "unit-thread",
        "gate_issues": [],
        "extras": {},
    }


def tone(seconds=2):
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(struct.pack("<h", int(500 * math.sin(i / 10))) for i in range(int(seconds * 16000))))
    return target.getvalue()


def patch_valid_image_probe(monkeypatch):
    monkeypatch.setattr("videoagents.nodes.materials.probe",
                        lambda path: {"streams": [{"codec_type": "video", "width": 64, "height": 64}]})


def patch_material_model(monkeypatch):
    calls = []

    def model_call(self, job_id, revision, role, instruction, context, command_id="", output_schema=None, **kwargs):
        assert role == "materials"
        calls.append((role, context, output_schema))
        folder = kwargs["research_directory"]
        source = folder / "source.txt"
        source.write_text("Muse is a test source.", encoding="utf-8")
        image = folder / "image.png"
        image.write_bytes(PNG_BYTES)
        return {"sources": [{"url": "https://example.com/muse", "title": "Muse", "platform": "web",
                             "text_file": source.name, "sha256": sha256(source)}],
                "visuals": [{"source_url": "https://example.com/muse", "kind": "screenshot",
                             "file": image.name, "sha256": sha256(image), "description": "Muse"}],
                "limitations": []}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model_call)
    patch_valid_image_probe(monkeypatch)
    return calls


def test_materials_rejects_tampered_frozen_research(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="Muse"))
    patch_material_model(monkeypatch)
    MaterialsNode(repo, service)(state_for(job))
    research = next(item for item in repo.get_job(job.job_id).artifacts if item.kind == "research")
    path, _, _ = repo.artifact_path(research.artifact_id)
    path.write_text(json.dumps({"status": "COMPLETED", "sources": []}), encoding="utf-8")

    with pytest.raises(Conflict):
        MaterialsNode(repo, service)(state_for(job))


def test_cancellation_between_active_check_and_material_commit_is_rejected(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="Muse是什么"))
    image = repo.root / "unit.png"
    image.write_bytes(PNG_BYTES)
    patch_valid_image_probe(monkeypatch)
    original = repo.update_job

    def cancel_at_commit(job_id, *args, **changes):
        if "assets" in changes:
            repo.cancel(job_id)
        return original(job_id, *args, **changes)

    monkeypatch.setattr(repo, "update_job", cancel_at_commit)
    with pytest.raises(Conflict):
        MaterialsNode(repo, service).attach_image(job, image, "https://example.com/muse", "source_image", "Muse")
    current = repo.get_job(job.job_id)
    assert current.status == "CANCELLED"
    assert current.assets == [] and current.artifacts == []


def test_materials_pause_and_resume_reruns_materials_before_screenwriter(tmp_path, monkeypatch):
    from videoagents.providers.llm import CapabilityMissing, JsonModel

    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="Muse", source_urls=["https://example.com/muse"]))
    calls = patch_material_model(monkeypatch)
    successful_call = JsonModel.call
    attempts = []

    def flaky_call(self, *args, **kwargs):
        attempts.append(args[2])
        if len(attempts) == 1:
            raise CapabilityMissing("unit transient model failure", ["role_models"])
        if args[2] == "screenwriter":
            raise CapabilityMissing("unit stop after materials", ["script"])
        return successful_call(self, *args, **kwargs)

    monkeypatch.setattr(JsonModel, "call", flaky_call)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "unit-produce"})
    assert Worker(repo, service.project_root).once()
    paused = repo.get_job(job.job_id)
    assert paused.status == "NEEDS_INPUT" and paused.stage == "materials"
    assert paused.pending_input["stage"] == "materials"

    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "resume", "decision": "confirm",
                              "note": "retry materials", "idempotency_key": "unit-resume",
                              "pending_token": paused.pending_input["pending_token"]})
    assert Worker(repo, service.project_root).once()
    current = repo.get_job(job.job_id)

    assert attempts == ["materials", "materials", "screenwriter"]
    assert len(calls) == 1
    assert any(item.kind == "research" for item in current.artifacts)
    assert current.status == "NEEDS_INPUT"
    assert current.stage == "script"


def test_actual_graph_invokes_materials_before_screenwriter(tmp_path, monkeypatch):
    from videoagents.nodes.common import request_input, state_context

    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="graph order"))
    calls = []

    def materials(self, state):
        calls.append("materials")
        self.repo.update_job(state["job_id"], state["revision"], status="RUNNING", stage="materials",
                             message="unit materials")
        return state_context(self.repo, state, route="screenwriter", research={"sources": []}, gate_issues=[])

    def writer(self, state):
        calls.append("screenwriter")
        return request_input(self.repo, state, "script", ["unit stop"], ["script"])

    monkeypatch.setattr("videoagents.nodes.materials.MaterialsNode.__call__", materials)
    monkeypatch.setattr("videoagents.nodes.screenwriter.ScreenwriterNode.__call__", writer)
    repo.enqueue(job.job_id, {"base_revision": job.revision, "action": "produce", "idempotency_key": "unit-graph"})
    command = repo.claim(12345)
    with VideoProductionGraph(repo, service.project_root) as graph:
        graph.execute(command)

    assert calls == ["materials", "screenwriter"]
    assert repo.get_job(job.job_id).pending_input["stage"] == "script"


def test_materials_node_rejects_cancelled_and_stale_revision_before_commit(tmp_path):
    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="stale"))
    before = repo.get_job(job.job_id)
    with pytest.raises(Conflict):
        MaterialsNode(repo, service)({**state_for(job), "revision": job.revision + 1})
    assert repo.get_job(job.job_id) == before

    repo.cancel(job.job_id)
    with pytest.raises(RenderCancelled):
        MaterialsNode(repo, service)(state_for(job))


def test_screenwriter_consumes_frozen_research_and_tamper_is_blocked(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret",
                                              role_models={"screenwriter": {"enabled": True, "model": "unit-writer"}},
                                              research_platforms=["web"], capture_enabled=True,
                                              research_download_images=False,
                                              script_discussion_enabled=False))
    job = repo.create_job(Brief(topic="Muse是什么"))
    patch_material_model(monkeypatch)
    MaterialsNode(repo, service)(state_for(job))
    calls = []

    def model_call(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, context))
        return {"title": "Muse是什么", "origin": "model", "revision": revision, "segments": [{
            "segment_id": "s1", "narration": "Muse 是测试来源里的产品。", "screen_text": "Muse",
            "source_refs": ["https://example.com/muse"], "asset_ids": [context["assets"][0]["asset_id"]],
        }]}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model_call)
    result = ScreenwriterNode(repo, service)(state_for(repo.get_job(job.job_id)))
    current = repo.get_job(job.job_id)

    assert result["route"] == "script_gate"
    assert calls[0][0] == "screenwriter"
    assert calls[0][1]["research"]["sources"][0]["url"] == "https://example.com/muse"
    assert current.script.segments[0].asset_ids == [current.assets[0].asset_id]

    research_artifact = next(item for item in current.artifacts if item.kind == "research")
    path, _, _ = repo.artifact_path(research_artifact.artifact_id)
    path.write_text(json.dumps({"sources": []}), encoding="utf-8")
    repo.update_job(job.job_id, job.revision, script=None)
    with pytest.raises(Conflict, match="上下文引用的阶段记录已改变"):
        ScreenwriterNode(repo, service).write_script(repo.get_job(job.job_id))


def test_screenwriter_helper_reads_shared_final_output_without_reopening_research(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="数据库原始主题"))
    node = ScreenwriterNode(repo, service)
    shared = {
        **state_for(job),
        "brief": job.brief.model_copy(update={"topic": "前节点交接的主题"}).model_dump(),
        "script": None,
        "assets": [],
        "research": {
            "sources": [{"url": "https://example.com/muse", "text": "前节点交接的正文。"}],
            "visuals": [],
            "tools": [{"platform": "unit", "status": "ok"}],
            "search_results": [{"snippet": "搜索过程不是事实依据"}],
        },
    }
    monkeypatch.setattr(node.model, "available", lambda role: True)
    monkeypatch.setattr(repo, "artifact_path", lambda *args: pytest.fail("Agent reopened research instead of consuming state"))

    def model_call(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        assert set(context) == {"brief", "research", "assets"}
        assert context["brief"]["topic"] == "前节点交接的主题"
        assert context["research"]["sources"][0]["text"] == "前节点交接的正文。"
        assert not {"tools", "search_results"}.intersection(context["research"])
        return {"title": context["brief"]["topic"], "segments": [{
            "segment_id": "s1", "narration": "Muse 是来源中的产品。",
            "source_refs": ["https://example.com/muse"], "asset_ids": [],
        }]}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model_call)

    script, _ = node.write_script(job, shared)

    assert script.title == "前节点交接的主题"
    assert script.origin == "model"


def test_materials_model_reads_inputs_from_shared_state(tmp_path, monkeypatch):
    from videoagents.nodes.common import state_context

    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="database topic"))
    node = MaterialsNode(repo, service)
    shared = state_context(repo, state_for(job))
    shared["brief"]["topic"] = "shared topic"
    calls = patch_material_model(monkeypatch)

    result = node.collect(job, shared)

    assert result["sources"][0]["url"] == "https://example.com/muse"
    assert len(calls) == 1
    assert calls[0][1]["brief"]["topic"] == "shared topic"
    assert set(calls[0][1]) == {"brief", "assets", "settings"}
    assert calls[0][2]["title"] == "MaterialResearch"


def test_materials_accepts_verified_video_visual_and_records_metadata(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="Muse 视频素材"))
    folder = repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "skills-research"
    folder.mkdir(parents=True, exist_ok=True)
    source = folder / "source.txt"
    source.write_text("官方视频展示 Muse 的实际界面。", encoding="utf-8")
    video = folder / "demo.mp4"
    video.write_bytes(MP4_BYTES)
    monkeypatch.setattr("videoagents.nodes.materials.detect_media", lambda data, path=None: ("video/mp4", ".mp4"))
    monkeypatch.setattr("videoagents.nodes.materials.video_metadata",
                        lambda path: {"duration_seconds": 8.5, "width": 688, "height": 1080, "frame_rate": 30.0})
    monkeypatch.setattr("videoagents.nodes.materials.decode_check", lambda path: None)

    research = MaterialsNode(repo, service).save_research(job, {
        "sources": [{"url": "https://example.com/muse", "title": "Muse", "platform": "web",
                     "text_file": source.name, "sha256": sha256(source)}],
        "visuals": [{"source_url": "https://example.com/muse", "kind": "video",
                     "file": video.name, "sha256": sha256(video), "media_url": "https://example.com/demo.mp4",
                     "description": "Muse 官方演示视频"}],
        "limitations": [],
    }, folder)

    current = repo.get_job(job.job_id)
    asset = current.assets[0]
    metadata = repo.asset_metadata(asset.asset_id)

    assert asset.mime_type == "video/mp4"
    assert asset.timeline_src.endswith(".mp4")
    assert asset.source_url == "https://example.com/muse"
    assert "真实来源视频" in asset.license_note
    assert metadata["duration_seconds"] == 8.5
    assert metadata["width"] == 688 and metadata["height"] == 1080
    assert research["visuals"][0]["kind"] == "video"
    assert research["visuals"][0]["media_url"] == "https://example.com/demo.mp4"


def test_director_matches_evidence_by_source_url_when_script_does_not_name_asset(tmp_path):
    repo, service = make_repo(tmp_path)
    job = repo.create_job(Brief(topic="Muse是什么", script_text="观点：Muse。", target_seconds=2, width=240, height=426, fps=15))
    image_path = repo.root / "evidence.png"
    image_path.write_bytes(PNG_BYTES)
    artifact = service.register_artifact(job, image_path, "asset", "image/png")
    evidence = Asset(asset_id="evidence-1", name="evidence.png", role="evidence", mime_type="image/png",
                     size_bytes=artifact.size_bytes, sha256=artifact.sha256, source_url="https://example.com/muse",
                     license_note="unit", artifact_id=artifact.artifact_id, url=artifact.url,
                     timeline_src=f"videoagents/{job.job_id}/assets/evidence-1.png")
    service.freeze_asset(evidence)
    job = repo.update_job(job.job_id, job.revision, assets=[evidence], artifacts=[artifact],
                          script=Script(title="Muse", origin="user", revision=job.revision, segments=[
                              ScriptSegment(segment_id="s1", narration="Muse 是测试来源里的产品。", screen_text="Muse",
                                            source_refs=["https://example.com/muse"], asset_ids=[])]))
    audio = service.upload(job.job_id, tone(), "tone.wav", "audio", license_note="unit audio", alignment={
        "origin": "manual", "verified": True,
        "segments": [{"segment_id": "s1", "text": "Muse 是测试来源里的产品。", "start_ms": 0, "end_ms": 1800}],
    })
    current = repo.get_job(job.job_id)
    alignment = Alignment.model_validate(repo.asset_metadata(audio.asset_id)["alignment"])

    timeline = DirectorNode(repo, service).plan(current, audio, alignment, 2.0, {"visuals": [{"asset_id": evidence.asset_id}]})

    assert timeline.shots[0].component_id == "evidence"
    assert timeline.shots[0].asset_src == evidence.timeline_src
    assert timeline.shots[0].source_label == "example.com"
