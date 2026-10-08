"""技能研究的边界和交接契约；不请求实际网络/模型。"""

import hashlib
import json

import pytest

from videoagents.contracts import Brief, SettingsPatch
from videoagents.nodes.materials import MaterialsNode
from videoagents.providers.llm import JsonModel
from videoagents.services.jobs import JobService
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository
from worker.process_manager import RenderCancelled

URL = "https://example.com/muse"
PNG = b"\x89PNG\r\n\x1a\n" + b"unit-image" * 10


@pytest.fixture
def setup(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {"enabled": True}}))
    job = repo.create_job(Brief(topic="Muse是什么"))
    node = MaterialsNode(repo, service)
    monkeypatch.setattr("videoagents.nodes.materials.probe",
                        lambda path: {"streams": [{"codec_type": "video", "width": 64, "height": 64}]})
    monkeypatch.setattr("videoagents.nodes.materials.detect_media", lambda data, path=None: ("image/png", ".png"))
    return repo, service, node, job


def install_output(monkeypatch, node, *, mutate=None, callback=None):
    calls = []

    def invoke(state, role, prompt, **kwargs):
        calls.append(kwargs)
        assert role == "materials" and "$agent-reach" in prompt
        assert set(kwargs["fields"]) == {"brief", "assets", "settings"}
        assert kwargs["output_schema"]["title"] == "MaterialResearch"
        assert "plan" not in kwargs["output_schema"]["properties"]
        folder = kwargs["research_directory"]
        text = "已读取的测试正文：Muse 有多种含义。".encode()
        (folder / "source.txt").write_bytes(text)
        (folder / "image.png").write_bytes(PNG)
        kwargs["audit_path"].write_text('{"type":"item.completed","item_type":"web_search"}\n', encoding="utf-8")
        data = {
            "sources": [{"url": URL, "title": "Muse", "platform": "web", "text_file": "source.txt",
                         "sha256": hashlib.sha256(text).hexdigest()}],
            "visuals": [{"source_url": URL, "kind": "image", "file": "image.png",
                         "sha256": hashlib.sha256(PNG).hexdigest(), "image_url": "https://example.com/image.png",
                         "description": "来源原图"}],
            "limitations": ["Reddit 未登录，本次未完成检索。"],
        }
        if mutate:
            mutate(data, folder)
        if callback:
            callback()
        return data

    monkeypatch.setattr(node.model, "invoke", invoke)
    return calls


def state(job):
    return {"job_id": job.job_id, "revision": job.revision, "action": "produce", "run_id": "unit",
            "thread_id": "unit", "extras": {}}


def test_skills_ingests_real_files_freezes_results_and_removes_tool_artifacts(setup, monkeypatch):
    repo, _, node, job = setup
    calls = install_output(monkeypatch, node)
    first = node(state(job))
    saved = repo.get_job(job.job_id)
    assert first["route"] == "screenwriter"
    assert first["research"]["sources"][0]["text"].startswith("已读取的测试正文")
    assert first["research"]["sources"][0]["asset_ids"] == [saved.assets[0].asset_id]
    assert first["research"]["limitations"] == ["Reddit 未登录，本次未完成检索。"]
    assert not {"tools", "search_results", "text_file", "tool_calls"}.intersection(first["research"])
    assert {item.kind for item in saved.artifacts} >= {"source", "research", "material_tool_audit", "asset"}
    assert "plan" not in first["research"]
    assert not any(item.kind == "material_plan" for item in saved.artifacts)
    assert "material_tool_audit" not in {item["kind"] for item in first["artifacts"]}
    assert URL in saved.brief.source_urls
    assert node(state(saved))["research"] == first["research"]
    assert len(calls) == 1
    assert not calls[0]["audit_path"].is_relative_to(calls[0]["research_directory"])


def test_skills_strips_browser_only_url_fragments_before_validation(setup, monkeypatch):
    repo, _, node, job = setup

    def add_fragments(data, _folder):
        data["sources"][0]["url"] = URL + "#overview"
        data["visuals"][0]["source_url"] = URL + "#overview"
        data["visuals"][0]["image_url"] = "https://example.com/image.png?size=large#center"

    install_output(monkeypatch, node, mutate=add_fragments)
    result = node(state(job))
    saved = repo.get_job(job.job_id)

    assert result["route"] == "screenwriter"
    assert result["research"]["sources"][0]["url"] == URL
    assert result["research"]["visuals"][0]["source_url"] == URL
    assert result["research"]["visuals"][0]["image_url"] == "https://example.com/image.png?size=large"
    metadata = repo.asset_metadata(saved.assets[0].asset_id)
    assert metadata["image_url"] == "https://example.com/image.png?size=large"


def test_skills_freezes_more_than_twenty_visuals_despite_legacy_limit(setup, monkeypatch):
    repo, _, node, job = setup
    repo.write_settings({"research_max_visuals": json.dumps(8)})

    def add_distinct_visuals(data, folder):
        data["visuals"] = []
        for index in range(25):
            contents = PNG + bytes([index])
            filename = f"image-{index}.png"
            (folder / filename).write_bytes(contents)
            data["visuals"].append({
                "source_url": URL, "kind": "image", "file": filename,
                "sha256": hashlib.sha256(contents).hexdigest(),
                "description": f"测试来源的不同画面 {index}",
            })

    install_output(monkeypatch, node, mutate=add_distinct_visuals)
    result = node(state(job))
    saved = repo.get_job(job.job_id)
    assert result["route"] == "screenwriter"
    assert len(result["research"]["visuals"]) == len(saved.assets) == 25
    assert len({asset.sha256 for asset in saved.assets}) == 25


def test_material_model_context_drops_legacy_visual_limit(setup, monkeypatch):
    repo, _, _, job = setup
    model = JsonModel(repo)
    contexts = []

    def capture(job_id, revision, role, instruction, context, command_id="", **kwargs):
        contexts.append(context)
        return {}

    monkeypatch.setattr(model, "call", capture)
    model.invoke({**state(job), "settings": {"research_max_visuals": 8, "capture_enabled": True}},
                 "materials", "test", fields=("settings",), research_directory=repo.root)
    assert contexts == [{"settings": {"capture_enabled": True}}]


def test_skills_audit_rebuilds_whitelist_instead_of_publishing_file_contents(setup, monkeypatch):
    repo, _, node, job = setup

    def replace_audit(data, folder):
        events = next(folder.parent.glob("material-tool-events-*.jsonl"))
        events.write_text('{"type":"item.completed","item_type":"command_execution",'
                          '"status":"completed","command":"unit-private-command","output":"unit-private-output"}\n'
                          'unit-private-garbage\n', encoding="utf-8")

    install_output(monkeypatch, node, mutate=replace_audit)
    assert node(state(job))["route"] == "screenwriter"
    artifact = next(item for item in repo.get_job(job.job_id).artifacts if item.kind == "material_tool_audit")
    content = repo.artifact_path(artifact.artifact_id)[0].read_text(encoding="utf-8")
    assert "unit-private" not in content
    assert json.loads(content) == {"type": "item.completed", "item_type": "command_execution", "status": "completed"}


@pytest.mark.parametrize("mutation", [
    lambda data, folder: data["sources"][0].update(text_file="../outside.txt"),
    lambda data, folder: data["sources"][0].update(text_file=str(folder / "source.txt")),
    lambda data, folder: data["sources"][0].update(sha256="0" * 64),
    lambda data, folder: data["sources"][0].update(url="https://127.0.0.1/private"),
    lambda data, folder: data["visuals"][0].update(source_url="https://other.example.com/unread"),
    lambda data, folder: data["sources"].append(dict(data["sources"][0])),
])
def test_skills_rejects_untrusted_manifest_before_registering_sources(setup, monkeypatch, mutation):
    repo, _, node, job = setup
    install_output(monkeypatch, node, mutate=mutation)
    result = node(state(job))
    assert result["route"] == "await_input"
    assert not repo.get_job(job.job_id).assets
    assert not any(item.kind in {"source", "research"} for item in repo.get_job(job.job_id).artifacts)


def test_skills_enforces_visual_settings(setup, monkeypatch):
    repo, _, node, job = setup
    SettingsService(repo).patch(SettingsPatch(research_download_images=False))
    install_output(monkeypatch, node)
    assert node(state(job))["route"] == "await_input"
    assert not repo.get_job(job.job_id).assets


def test_skills_checks_cancellation_after_model_completion(setup, monkeypatch):
    repo, _, node, job = setup
    install_output(monkeypatch, node, callback=lambda: repo.update_job(job.job_id, job.revision, status="CANCELLED"))
    with pytest.raises(RenderCancelled):
        node(state(job))
    assert not repo.get_job(job.job_id).assets


def test_skills_never_freezes_empty_research(setup, monkeypatch):
    repo, _, node, job = setup
    install_output(monkeypatch, node, mutate=lambda data, folder: data.update(sources=[], visuals=[]))
    assert node(state(job))["route"] == "await_input"
    assert not any(item.kind == "research" for item in repo.get_job(job.job_id).artifacts)


def test_skills_requires_codex_and_does_not_silently_fallback(setup, monkeypatch):
    repo, _, node, job = setup
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {"provider": "claude_code_cli"}}))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("unsupported provider reached CLI"))
    result = node(state(job))
    assert result["route"] == "await_input"
    assert "Codex CLI" in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("inputs", [
    {"source_urls": [URL]},
    {"script_text": "观点：这是用户已经提供的文案。"},
    {"topic": "", "script_text": "观点：只有文案也需要素材。"},
])
def test_collect_launches_model_for_user_provided_inputs(setup, monkeypatch, inputs):
    repo, _, node, _ = setup
    job = repo.create_job(Brief(topic="Muse是什么").model_copy(update=inputs))
    calls = install_output(monkeypatch, node)
    assert node(state(job))["route"] == "screenwriter"
    assert len(calls) == 1


def test_disabled_materials_model_pauses_without_fixed_tool_fallback(setup, monkeypatch):
    repo, _, node, job = setup
    SettingsService(repo).patch(SettingsPatch(role_models={"materials": {"enabled": False}}))
    monkeypatch.setattr("videoagents.providers.llm.run_cli", lambda *a, **k: pytest.fail("disabled model reached CLI"))
    result = node(state(job))
    assert result["route"] == "await_input"
    assert repo.get_job(job.job_id).pending_input["fields"] == ["role_models"]
    assert not any(item.kind == "research" for item in repo.get_job(job.job_id).artifacts)
