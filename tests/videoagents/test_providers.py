import json

import httpx
import pytest

from videoagents.contracts import SettingsPatch
from videoagents.providers.byte_voice import SubmissionUnknown, synthesize
from videoagents.providers.llm import CapabilityMissing
from videoagents.services.settings import SettingsService
from videoagents.storage import Repository


@pytest.fixture
def configured(tmp_path):
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(voice_provider="byte_http", voice_api_key="fake-unit-test-secret",
        voice_resource_id="seed-icl-2.0", voice_id="unit-test-own-voice",
        voice_model="seed-tts-2.0-standard", voice_style="", voice_speech_rate=0))
    return repo


def mock_client(monkeypatch, handler):
    original = httpx.Client
    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)
    monkeypatch.setattr("videoagents.providers.byte_voice.httpx.Client", client)


@pytest.mark.parametrize("status", [500, 408])
def test_uncertain_http_never_resubmits_paid_voice(configured, monkeypatch, status):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, headers={"X-Tt-Logid": "unit-trace"})
    mock_client(monkeypatch, handle)
    with pytest.raises(SubmissionUnknown):
        synthesize(configured, "job-test", 1, "unit text", "first-command")
    with pytest.raises(SubmissionUnknown):
        synthesize(configured, "job-test", 1, "unit text", "new-command")
    assert len(calls) == 1
    with configured.connection() as db:
        row = db.execute("SELECT status,body FROM operations").fetchone()
    assert row[0] == "UNKNOWN"
    assert json.loads(row[1])["provider_trace_id"] == "unit-trace"


def test_eof_without_success_terminator_is_unknown(configured, monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=b'{"code":0,"data":"dGVzdA=="}\n')
    mock_client(monkeypatch, handle)
    with pytest.raises(SubmissionUnknown):
        synthesize(configured, "job-test", 1, "unit text", "command-a")
    with pytest.raises(SubmissionUnknown):
        synthesize(configured, "job-test", 1, "unit text", "command-b")
    assert len(calls) == 1


def test_known_rejection_can_retry_only_a_new_explicit_command(configured, monkeypatch):
    calls = []
    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(401)
        # Synthetic protocol bytes, never represented as production audio.
        return httpx.Response(200, content=b'{"code":0,"data":"dGVzdA=="}\n{"code":20000000,"data":null,"message":"ok"}')
    mock_client(monkeypatch, handle)
    with pytest.raises(CapabilityMissing):
        synthesize(configured, "job-test", 1, "unit text", "command-a")
    with pytest.raises(SubmissionUnknown):
        synthesize(configured, "job-test", 1, "unit text", "command-a")
    result = synthesize(configured, "job-test", 1, "unit text", "command-b")
    assert len(calls) == 2
    assert result["attempt"] == 2
    repeated = synthesize(configured, "job-test", 1, "unit text", "command-c")
    assert repeated["path"] == result["path"] and len(calls) == 2


@pytest.mark.parametrize("origin", ["byte_http", "byte_ws"])
def test_generated_voice_with_changed_script_is_not_reused(monkeypatch, tmp_path, origin):
    from videoagents.contracts import Asset, Brief, Script, ScriptSegment
    from videoagents.nodes.voice import VoiceNode
    from videoagents.services.jobs import JobService
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    SettingsService(repo).patch(SettingsPatch(voice_provider="byte_ws", voice_model="seed-tts-2.0-expressive"))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: {
        "delivery_notes": ["UNIT TEST: preserve narration and speak naturally."], "findings": [],
    })
    job = repo.create_job(Brief(topic="test"))
    old = Asset(asset_id="old-generated", name="old.mp3", role="audio", mime_type="audio/mpeg", size_bytes=1,
        sha256="a" * 64, artifact_id="old-artifact", url="/api/artifacts/old-artifact", timeline_src=f"videoagents/{job.job_id}/assets/old.mp3")
    changed = Script(title="test", revision=1, origin="user", segments=[ScriptSegment(segment_id="s1", narration="New script")])
    repo.update_job(job.job_id, script=changed, assets=[old])
    repo.update_asset_metadata(old.asset_id, {"origin": origin, "script_fingerprint": "obsolete", "voice_fingerprint": "obsolete"})
    repo.select_audio(job.job_id, old.asset_id)
    calls = []
    def request(*args, **kwargs):
        calls.append(args[3])
        raise CapabilityMissing("test missing new voice credentials")
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", request)
    with pytest.raises(CapabilityMissing):
        VoiceNode(repo, service).prepare_audio(repo.get_job(job.job_id), "new-command")
    assert calls == ["New script"]


@pytest.mark.parametrize("status", ["UNKNOWN", "SUBMITTING"])
def test_ws_unsettled_submission_cannot_be_bypassed_by_http(configured, monkeypatch, status):
    operation = configured.start_operation("job-test", "old-ws-input", "byte_ws", {"revision": 1, "request_id": "unit-request"})
    configured.finish_operation(operation["operation_id"], status, {"revision": 1, "request_id": "unit-request"})
    monkeypatch.setattr("videoagents.providers.byte_voice.httpx.Client", lambda *a, **k: pytest.fail("unsettled WS reached HTTP"))
    SettingsService(configured).patch(SettingsPatch(voice_id="different-unit-voice"))
    with pytest.raises(SubmissionUnknown) as failure:
        synthesize(configured, "job-test", 1, "new text", "new-command")
    assert failure.value.operation_id == operation["operation_id"]
    assert failure.value.request_id == "unit-request"


def test_ws_model_change_invalidates_generated_audio(monkeypatch, tmp_path):
    from videoagents.contracts import Asset, Brief, Script, ScriptSegment
    from videoagents.nodes.voice import VoiceNode
    from videoagents.services.jobs import JobService
    from videoagents.storage.repository import fingerprint

    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(voice_provider="byte_ws", voice_id="unit-voice", voice_resource_id="seed-icl-2.0"))
    service = JobService(repo, tmp_path / "project")
    job = repo.create_job(Brief(topic="TEST model invalidation"))
    script = Script(title="TEST", revision=1, origin="user", segments=[ScriptSegment(segment_id="s1", narration="Same narration")])
    old = Asset(asset_id="old-ws", name="old.mp3", role="audio", mime_type="audio/mpeg", size_bytes=1,
        sha256="a" * 64, artifact_id="old-artifact", url="/api/artifacts/old-artifact", timeline_src=f"videoagents/{job.job_id}/assets/old.mp3")
    repo.update_job(job.job_id, script=script, assets=[old])
    repo.update_asset_metadata(old.asset_id, {"origin": "byte_ws",
        "script_fingerprint": fingerprint([{"segment_id": "s1", "narration": "Same narration"}]),
        "voice_fingerprint": fingerprint({"voice_id": "unit-voice", "resource_id": "seed-icl-2.0", "provider": "byte_ws", "model": "seed-tts-2.0-standard"})})
    repo.select_audio(job.job_id, old.asset_id)
    SettingsService(repo).patch(SettingsPatch(voice_model="seed-tts-2.0-expressive"))
    monkeypatch.setattr("videoagents.providers.llm.JsonModel.call", lambda *args, **kwargs: {
        "delivery_notes": ["UNIT TEST: preserve narration and speak naturally."], "findings": [],
    })
    calls = []
    def request(*args, **kwargs):
        calls.append(args[3])
        assert kwargs["cancelled"]() is False
        raise CapabilityMissing("TEST new synthesis needed")
    monkeypatch.setattr("videoagents.nodes.voice.synthesize", request)
    with pytest.raises(CapabilityMissing):
        VoiceNode(repo, service).prepare_audio(repo.get_job(job.job_id), "new-model-command")
    assert calls == ["Same narration"]


def test_tcp_validation_pins_public_resolution_and_rejects_rebinding(monkeypatch):
    import httpcore

    from videoagents.providers.network import PublicNetworkBackend
    resolves, connects = [], []
    def resolve(host, port, **kwargs):
        resolves.append(host)
        return [(2, 1, 6, "", ("93.184.216.34", port))]
    monkeypatch.setattr("videoagents.providers.network.socket.getaddrinfo", resolve)
    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", lambda self, host, *args: connects.append(host) or "unit-stream")
    assert PublicNetworkBackend().connect_tcp("example.com", 443) == "unit-stream"
    assert resolves == ["example.com"] and connects == ["93.184.216.34"]
    monkeypatch.setattr("videoagents.providers.network.socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("127.0.0.1", 443))])
    with pytest.raises(httpcore.ConnectError):
        PublicNetworkBackend().connect_tcp("example.com", 443)
    assert connects == ["93.184.216.34"]


@pytest.mark.parametrize("submitted", [False, True])
def test_llm_rejection_retry_is_explicit_and_unknown_stays_blocked(tmp_path, monkeypatch, submitted):
    from videoagents.providers.cli_runner import CliFailure, CliResult
    from videoagents.providers.llm import JsonModel
    repo = Repository(tmp_path / "runtime")
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {"enabled": True, "model": "unit-model"}}))
    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *a: ["unit-cli"])
    calls = []
    def handle(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            raise CliFailure("unit-test-failure", submitted=submitted)
        return CliResult({"text": "unit result"})
    monkeypatch.setattr("videoagents.providers.llm.run_cli", handle)
    model = JsonModel(repo)
    with pytest.raises(CapabilityMissing):
        model.call("job-test", 1, "screenwriter", "JSON only", {}, "command-a")
    with pytest.raises(CapabilityMissing):
        model.call("job-test", 1, "screenwriter", "JSON only", {}, "command-a")
    if not submitted:
        assert model.call("job-test", 1, "screenwriter", "JSON only", {}, "command-b") == {"text": "unit result"}
        assert len(calls) == 2
        assert model.call("job-test", 1, "screenwriter", "JSON only", {}, "command-c") == {"text": "unit result"}
        assert len(calls) == 2
    else:
        with pytest.raises(CapabilityMissing):
            model.call("job-test", 1, "screenwriter", "JSON only", {}, "command-b")
        assert len(calls) == 1


@pytest.mark.parametrize("supplied_urls", [[], ["https://example.com/source"]])
def test_unknown_model_cannot_bypass_barrier_by_refreshing_source_receipts(tmp_path, monkeypatch, supplied_urls):
    from videoagents.contracts import Brief
    from videoagents.nodes.materials import MaterialsNode
    from videoagents.nodes.screenwriter import ScreenwriterNode
    from videoagents.providers.cli_runner import CliFailure
    from videoagents.services.jobs import JobService
    repo = Repository(tmp_path / "runtime")
    service = JobService(repo, tmp_path / "project")
    SettingsService(repo).patch(SettingsPatch(role_models={"screenwriter": {"enabled": True, "model": "unit-model"}},
                                             capture_enabled=False, research_download_images=False))
    job = repo.create_job(Brief(topic="测试来源研究", source_urls=supplied_urls))
    from videoagents.tools.media import sha256

    monkeypatch.setattr("videoagents.providers.llm.executable_prefix", lambda *args: ["unit-cli"])
    reads, calls = [], []
    materials = MaterialsNode(repo, service)

    def research(state, role, prompt, **kwargs):
        path = kwargs["research_directory"] / "source.txt"
        path.write_bytes(b"frozen source content UNIT TEST")
        reads.append(path)
        return {"sources": [{"url": "https://example.com/source", "title": "unit source", "platform": "web",
                             "text_file": path.name, "sha256": sha256(path)}], "visuals": [], "limitations": []}

    monkeypatch.setattr(materials.model, "invoke", research)
    def handler(*args, **kwargs):
        calls.append(args)
        raise CliFailure("unit_unknown")
    monkeypatch.setattr("videoagents.providers.llm.run_cli", handler)
    materials.collect(job)
    writer = ScreenwriterNode(repo, service)
    with pytest.raises(CapabilityMissing) as first_failure:
        writer.write_script(job)
    assert first_failure.value.operation_status == "UNKNOWN"
    first = repo.get_job(job.job_id)
    source = next(item for item in first.artifacts if item.kind == "source")
    original_path = repo.artifact_path(source.artifact_id)[0]
    before = original_path.read_bytes()
    with pytest.raises(CapabilityMissing):
        materials.collect(job)
        writer.write_script(job)  # Deliberately replay the original stale snapshot.
    assert len(reads) == 1 and len(calls) == 1
    assert original_path.read_bytes() == before
    posted_context = json.loads(calls[0][3].split("上下文：\n", 1)[1])
    assert posted_context["brief"]["source_urls"] == ["https://example.com/source"]
    # Even if metadata/context changes, a logical role/revision UNKNOWN is
    # an independent barrier, not just an exact JSON cache hash.
    from videoagents.providers.llm import JsonModel
    with pytest.raises(CapabilityMissing):
        JsonModel(repo).call(job.job_id, job.revision, "screenwriter", "different volatile metadata", {"retrieved_at": "new-clock"}, "new-command")
    assert len(calls) == 1
