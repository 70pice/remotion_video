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


def patch_discovery(monkeypatch, *, results, failures=()):
    """Patch the materials node's public discovery seam; no network calls."""
    calls = []

    def fake_discover(repository, query, platform_ids, **kwargs):
        calls.append(("discover", query, tuple(platform_ids), kwargs))
        rows = [item for item in results if item.get("platform", "web") not in failures]
        tools = [{"platform": item, "backend": "unit", "status": "error" if item in failures else "ok"} for item in platform_ids]
        return {"query": query, "results": rows, "images": [], "tools": tools}

    monkeypatch.setattr("videoagents.nodes.materials.discover", fake_discover)
    return calls


def patch_fetch(monkeypatch, text_by_url=None, *, fail_urls=(), images_by_url=None):
    text_by_url = text_by_url or {}
    images_by_url = images_by_url or {}
    calls = []

    def fake_fetch(url, path):
        calls.append(url)
        if url in fail_urls:
            raise RuntimeError("unit fetch failure")
        text = text_by_url.get(url, "Muse 是测试来源。")
        path.write_text(f"<html><title>unit</title><body>{text}</body></html>", encoding="utf-8")
        return {
            "url": url,
            "final_url": url,
            "content_type": "text/html",
            "retrieved_at": "unit-clock",
            "sha256": sha256(path),
            "text": text,
            "title": "unit source",
            "images": list(images_by_url.get(url, [])),
        }

    monkeypatch.setattr("videoagents.nodes.materials.fetch_source", fake_fetch)
    return calls


def patch_valid_image_probe(monkeypatch):
    monkeypatch.setattr("videoagents.nodes.materials.probe",
                        lambda path: {"streams": [{"codec_type": "video", "width": 64, "height": 64}]})


def test_materials_node_collects_platform_sources_with_partial_failure_and_visual_receipts(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(
        search_provider="tavily",
        search_api_key="unit-secret",
        research_platforms=["web", "reddit", "youtube"],
        research_download_images=True,
        research_max_visuals=3,
        capture_enabled=True,
    ))
    job = repo.create_job(Brief(topic="Muse是什么"))
    calls = patch_discovery(monkeypatch, results=[
        {"url": "https://example.com/muse", "title": "Muse intro", "snippet": "web", "platform": "web", "backend": "unit",
         "images": [{"url": "https://cdn.example.com/muse.png", "source_url": "https://example.com/muse", "description": "unit image"}]},
        {"url": "https://www.youtube.com/watch?v=unit", "title": "Muse video", "snippet": "video", "platform": "youtube", "backend": "unit", "images": []},
    ], failures={"reddit"})
    patch_fetch(monkeypatch, {"https://example.com/muse": "Muse 是一个测试来源。", "https://www.youtube.com/watch?v=unit": "视频资料。"})
    patch_valid_image_probe(monkeypatch)
    safe_get_calls = []
    capture_calls = []
    monkeypatch.setattr("videoagents.nodes.materials.safe_get",
                        lambda url, max_bytes=0: safe_get_calls.append(url) or (PNG_BYTES, "image/png", url))

    def fake_capture(url, output):
        capture_calls.append(url)
        output.write_bytes(PNG_BYTES)

    monkeypatch.setattr("videoagents.nodes.materials.capture_source", fake_capture)

    result = MaterialsNode(repo, service)(state_for(job))
    saved = repo.get_job(job.job_id)

    assert result["route"] == "screenwriter"
    assert saved.stage == "materials"
    assert {"https://example.com/muse", "https://www.youtube.com/watch?v=unit"} <= set(saved.brief.source_urls)
    assert len(result["research"]["sources"]) == 2
    assert any(item.get("platform") == "reddit" for item in result["research"]["failures"]) or any(
        item.get("platform") == "reddit" and item.get("status") == "error" for item in result["research"].get("tools", [])
    )
    assert safe_get_calls == ["https://cdn.example.com/muse.png"]
    assert capture_calls == ["https://example.com/muse", "https://www.youtube.com/watch?v=unit"]
    visuals = result["research"]["visuals"]
    assert {item["kind"] for item in visuals} >= {"image", "screenshot"}
    visual_asset_ids = {item["asset_id"] for item in visuals}
    assert visual_asset_ids <= {asset.asset_id for asset in saved.assets}
    for asset in saved.assets:
        if asset.asset_id in visual_asset_ids:
            assert asset.role == "evidence"
            assert asset.source_url.startswith("https://")
            assert service.project_root.joinpath("public", asset.timeline_src).is_file()
            metadata = repo.asset_metadata(asset.asset_id)
            assert metadata["origin"] in {"capture", "source_image"}
            assert metadata["source_url"] == asset.source_url
    assert calls


def test_materials_replay_uses_frozen_research_without_repeating_external_calls(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret",
                                              research_platforms=["web"], capture_enabled=False,
                                              research_download_images=False))
    job = repo.create_job(Brief(topic="Muse是什么"))
    patch_discovery(monkeypatch, results=[
        {"url": "https://example.com/muse", "title": "Muse", "snippet": "unit", "platform": "web", "backend": "unit", "images": []},
    ])
    fetch_calls = patch_fetch(monkeypatch)

    first = MaterialsNode(repo, service)(state_for(job))
    monkeypatch.setattr("videoagents.nodes.materials.fetch_source", lambda *args, **kwargs: pytest.fail("frozen research fetched again"))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: pytest.fail("frozen research planned again"))
    second = MaterialsNode(repo, service)(state_for(job))

    assert fetch_calls == ["https://example.com/muse"]
    assert second["research"] == first["research"]
    assert len([item for item in repo.get_job(job.job_id).artifacts if item.kind == "research"]) == 1


def test_materials_rejects_tampered_frozen_research(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret",
                                              research_platforms=["web"], capture_enabled=False,
                                              research_download_images=False))
    job = repo.create_job(Brief(topic="Muse是什么"))
    patch_discovery(monkeypatch, results=[
        {"url": "https://example.com/muse", "title": "Muse", "snippet": "unit", "platform": "web", "backend": "unit", "images": []},
    ])
    patch_fetch(monkeypatch)
    MaterialsNode(repo, service)(state_for(job))
    research = next(item for item in repo.get_job(job.job_id).artifacts if item.kind == "research")
    path, _, _ = repo.artifact_path(research.artifact_id)
    path.write_text(json.dumps({"status": "COMPLETED", "sources": []}), encoding="utf-8")

    with pytest.raises(Conflict, match="已改变"):
        MaterialsNode(repo, service)(state_for(job))


def test_materials_reuses_partial_source_receipt_before_research_freeze(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(capture_enabled=False, research_download_images=False))
    job = repo.create_job(Brief(topic="Muse是什么", source_urls=["https://example.com/muse"]))
    fetch_calls = patch_fetch(monkeypatch)
    folder = repo.root / "jobs" / job.job_id / "revisions" / str(job.revision) / "sources"
    folder.mkdir(parents=True)
    MaterialsNode(repo, service).source(job, "https://example.com/muse", folder, 0)
    monkeypatch.setattr("videoagents.nodes.materials.fetch_source", lambda *args, **kwargs: pytest.fail("source receipt fetched twice"))

    research = MaterialsNode(repo, service).collect(job)

    assert fetch_calls == ["https://example.com/muse"]
    assert research["sources"][0]["url"] == "https://example.com/muse"
    assert len([item for item in repo.get_job(job.job_id).artifacts if item.kind == "source"]) == 1
    assert len([item for item in repo.get_job(job.job_id).artifacts if item.kind == "research"]) == 1


def test_materials_model_plans_query_once_with_own_role_schema(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret",
                                              role_models={"materials": {"enabled": True, "model": "unit-materials"}},
                                              research_platforms=["web"], capture_enabled=False,
                                              research_download_images=False))
    job = repo.create_job(Brief(topic="Muse是什么"))
    model_calls = []

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.available", lambda self, role: role == "materials")

    def model_call(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        model_calls.append((role, context, output_schema))
        return {"query": "Muse AI wearable", "focus_notes": ["产品定位"], "ambiguities": ["Muse 乐队同名"]}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model_call)
    discovery_calls = patch_discovery(monkeypatch, results=[
        {"url": "https://example.com/muse", "title": "Muse", "snippet": "unit", "platform": "web", "backend": "unit", "images": []},
    ])
    patch_fetch(monkeypatch)

    first = MaterialsNode(repo, service)(state_for(job))
    second = MaterialsNode(repo, service)(state_for(job))

    assert [item[0] for item in model_calls] == ["materials"]
    assert model_calls[0][2]["title"] == "MaterialPlan"
    assert first["research"]["plan"]["query"] == "Muse AI wearable"
    assert any(call[1] == "Muse AI wearable" for call in discovery_calls)
    assert second["research"] == first["research"]
    assert len(model_calls) == 1


def test_materials_does_not_search_when_manual_url_or_raw_script_is_present(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(search_provider="tavily", search_api_key="unit-secret",
                                              capture_enabled=False, research_download_images=False))
    manual = repo.create_job(Brief(topic="Muse是什么", source_urls=["https://example.com/muse"]))
    patch_fetch(monkeypatch)
    monkeypatch.setattr("videoagents.nodes.materials.discover", lambda *args, **kwargs: pytest.fail("manual URL triggered search"))
    MaterialsNode(repo, service)(state_for(manual))

    scripted = repo.create_job(Brief(topic="Muse是什么", script_text="观点：我已经有文案。"))
    monkeypatch.setattr("videoagents.nodes.materials.fetch_source", lambda *args, **kwargs: pytest.fail("raw script fetched sources"))
    MaterialsNode(repo, service)(state_for(scripted))


def test_materials_skips_unrelated_images_and_safe_get_blocks_ssrf(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(capture_enabled=False, research_download_images=True))
    job = repo.create_job(Brief(topic="Muse是什么", source_urls=["https://example.com/muse"]))
    patch_fetch(monkeypatch, images_by_url={"https://example.com/muse": [
        {"url": "https://cdn.example.com/unrelated.png", "source_url": "https://other.example.com/page", "description": "skip"},
        {"url": "http://127.0.0.1/private.png", "source_url": "https://example.com/muse", "description": "blocked"},
    ]})

    result = MaterialsNode(repo, service)(state_for(job))

    assert result["route"] == "screenwriter"
    assert result["research"]["visuals"] == []
    assert result["research"]["failures"] == [{
        "url": "http://127.0.0.1/private.png",
        "source_url": "https://example.com/muse",
        "reason": "ValueError",
        "stage": "image",
    }]
    assert repo.get_job(job.job_id).assets == []


def test_materials_cancellation_during_image_download_prevents_asset_commit(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(capture_enabled=False, research_download_images=True))
    job = repo.create_job(Brief(topic="Muse是什么", source_urls=["https://example.com/muse"]))
    patch_fetch(monkeypatch, images_by_url={"https://example.com/muse": [
        {"url": "https://cdn.example.com/muse.png", "source_url": "https://example.com/muse", "description": "unit image"},
    ]})
    patch_valid_image_probe(monkeypatch)

    def cancel_then_return_image(url, max_bytes=0):
        repo.cancel(job.job_id)
        return PNG_BYTES, "image/png", url

    monkeypatch.setattr("videoagents.nodes.materials.safe_get", cancel_then_return_image)

    with pytest.raises(RenderCancelled):
        MaterialsNode(repo, service)(state_for(job))
    assert repo.get_job(job.job_id).assets == []


def test_image_failure_does_not_skip_later_valid_candidate(tmp_path, monkeypatch):
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(capture_enabled=False, research_max_visuals=2))
    url = "https://example.com/muse"
    job = repo.create_job(Brief(topic="Muse是什么", source_urls=[url]))
    patch_fetch(monkeypatch, images_by_url={url: [
        {"url": "https://cdn.example.com/bad.png", "source_url": url},
        {"url": "https://cdn.example.com/good.png", "source_url": url},
    ]})
    patch_valid_image_probe(monkeypatch)
    monkeypatch.setattr("videoagents.nodes.materials.safe_get", lambda image_url, **kwargs:
                        (b"not an image" if "bad" in image_url else PNG_BYTES, "image/png", image_url))
    research = MaterialsNode(repo, service).collect(job)
    assert len(research["failures"]) == 1
    assert len(research["visuals"]) == 1
    assert research["visuals"][0]["image_url"] == "https://cdn.example.com/good.png"


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
    repo, service = make_repo(tmp_path)
    SettingsService(repo).patch(SettingsPatch(capture_enabled=False, research_download_images=False))
    job = repo.create_job(Brief(topic="Muse是什么", source_urls=["https://example.com/muse"]))
    attempts = []

    def flaky_fetch(url, path):
        attempts.append(url)
        if len(attempts) == 1:
            raise RuntimeError("unit transient source failure")
        path.write_text("<html>Muse 是测试来源。</html>", encoding="utf-8")
        return {"url": url, "final_url": url, "content_type": "text/html", "retrieved_at": "unit-clock",
                "sha256": sha256(path), "text": "Muse 是测试来源。", "title": "unit", "images": []}

    monkeypatch.setattr("videoagents.nodes.materials.fetch_source", flaky_fetch)
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: (_ for _ in ()).throw(
        RuntimeError("screenwriter reached after materials resume")))

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

    assert attempts == ["https://example.com/muse", "https://example.com/muse"]
    assert any(item.kind == "research" for item in current.artifacts)
    assert current.status in {"NEEDS_INPUT", "FAILED"}
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
                                              research_download_images=False))
    job = repo.create_job(Brief(topic="Muse是什么"))
    patch_discovery(monkeypatch, results=[
        {"url": "https://example.com/muse", "title": "Muse", "snippet": "unit", "platform": "web", "backend": "unit", "images": []},
    ])
    patch_fetch(monkeypatch)
    patch_valid_image_probe(monkeypatch)
    monkeypatch.setattr("videoagents.nodes.materials.capture_source", lambda url, output: output.write_bytes(PNG_BYTES))
    MaterialsNode(repo, service)(state_for(job))
    calls = []

    def model_call(self, job_id, revision, role, instruction, context, command_id="", output_schema=None):
        calls.append((role, context))
        return {"title": "Muse是什么", "origin": "model", "revision": revision, "segments": [{
            "segment_id": "s1", "narration": "Muse 是测试来源里的产品。", "screen_text": "Muse",
            "source_refs": ["https://example.com/muse"], "asset_ids": [context["assets"][0]["asset_id"]],
        }]}

    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", model_call)
    monkeypatch.setattr("videoagents.nodes.materials.fetch_source", lambda *args, **kwargs: pytest.fail("screenwriter fetched sources"))
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
    with pytest.raises(ValueError, match="素材研究记录已改变"):
        ScreenwriterNode(repo, service).write_script(repo.get_job(job.job_id))


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
