import io
import math
import struct
import wave

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from videoagents.contracts import Review


def tone(seconds=2):
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(struct.pack("<h", int(1000 * math.sin(index * 2 * math.pi * 440 / 16000))) for index in range(int(seconds * 16000))))
    return target.getvalue()


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "runtime", tmp_path / "project")
    with TestClient(app) as client:
        token = client.get("/api/session").json()["csrf_token"]
        client.headers["X-CSRF-Token"] = token
        yield client


def create(client):
    response = client.post("/api/jobs", json={"topic": "测试素材", "script_text": "观点：测试流程。", "target_seconds": 2,
                                              "width": 240, "height": 426, "fps": 15, "usage": "personal", "platform": "测试平台"})
    assert response.status_code == 201
    return response.json()


def test_session_csrf_and_cross_origin_before_mutation(client):
    assert client.post("/api/jobs", headers={"X-CSRF-Token": ""}, json={"topic": "test"}).status_code == 403
    assert client.post("/api/jobs", headers={"Origin": "https://untrusted.example"}, json={"topic": "test"}).status_code == 403
    assert client.get("/api/jobs", headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/jobs", json={"topic": "test"}).status_code == 201
    assert len(client.get("/api/jobs").json()) == 1


def test_durable_idempotency_and_revision_conflict(client):
    job = create(client)
    command = {"base_revision": 1, "action": "produce", "idempotency_key": "unique-command"}
    assert client.post(f"/api/jobs/{job['job_id']}/runs", json=command).status_code == 202
    assert client.post(f"/api/jobs/{job['job_id']}/runs", json=command).status_code == 202
    changed = dict(command, action="voice")
    assert client.post(f"/api/jobs/{job['job_id']}/runs", json=changed).status_code == 409
    repo = client.app.state.repository
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 1
    assert client.patch(f"/api/jobs/{job['job_id']}/draft", json={"base_revision": 1, "brief": job["brief"]}).status_code == 409
    assert client.post(f"/api/jobs/{job['job_id']}/cancel").status_code == 200
    assert client.patch(f"/api/jobs/{job['job_id']}/draft", json={"base_revision": 9, "brief": job["brief"]}).status_code == 409
    result = client.patch(f"/api/jobs/{job['job_id']}/draft", json={"base_revision": 1, "brief": job["brief"]})
    assert result.status_code == 200
    assert result.json()["revision"] == 2


def test_upload_real_audio_range_and_explicit_alignment_hash(client):
    job = create(client)
    response = client.post(f"/api/jobs/{job['job_id']}/assets", files={"file": ("test-tone.wav", tone(), "audio/wav")},
                           data={"role": "audio", "license_note": "测试信号，自有素材，仅用于测试"})
    assert response.status_code == 201
    asset = response.json()
    assert asset["timeline_src"].startswith(f"videoagents/{job['job_id']}/")
    assert ":\\" not in response.text and "/runtime/" not in response.text
    media = client.get(asset["url"], headers={"Range": "bytes=0-43"})
    assert media.status_code == 206
    assert len(media.content) == 44
    assert media.headers["content-range"].startswith("bytes 0-43/")
    job = client.get(f"/api/jobs/{job['job_id']}").json()
    alignment = {"origin": "manual", "verified": True, "audio_sha256": "a" * 64,
                 "segments": [{"segment_id": "s1", "text": "观点：测试流程。", "start_ms": 0, "end_ms": 1700}]}
    url = f"/api/jobs/{job['job_id']}/alignment"
    assert client.post(url, json={"base_revision": job["revision"], "asset_id": asset["asset_id"], "alignment": alignment}).status_code == 422
    assert client.get(f"/api/jobs/{job['job_id']}").json()["revision"] == job["revision"]
    alignment["audio_sha256"] = ""
    response = client.post(url, json={"base_revision": job["revision"], "asset_id": asset["asset_id"], "alignment": alignment})
    assert response.status_code == 200
    result = client.get(url).json()
    assert result["alignment"]["audio_sha256"] == asset["sha256"]
    assert result["duration_seconds"] == pytest.approx(2)


def test_settings_write_only_credentials_and_validation_never_echoes_them(client):
    secret = "test-only-secret-not-production"
    result = client.patch("/api/settings", json={"llm_api_key": secret, "llm_model": "test-model", "voice_api_key": secret})
    assert result.status_code == 200
    assert secret not in result.text
    assert result.json()["llm_configured"] is True
    response = client.get("/api/settings")
    assert secret not in response.text
    assert not any(key.endswith("api_key") or key.endswith("access_token") for key in response.json())
    invalid = client.patch("/api/settings", json={"voice_provider": secret})
    assert invalid.status_code == 422
    assert secret not in invalid.text
    raw = client.app.state.repository.db.read_bytes()
    assert secret.encode() not in raw  # Windows DPAPI; no plaintext SQL credential.


def test_draft_revision_invalidates_previous_release(client):
    job = create(client)
    repo = client.app.state.repository
    repo.update_job(job["job_id"], status="READY_FOR_PUBLISH", review=Review(status="PASS", findings=[], media_sha256="b" * 64,
                                                                         dependency_fingerprint="old", human_confirmed=True))
    response = client.patch(f"/api/jobs/{job['job_id']}/draft", json={"base_revision": 1, "brief": dict(job["brief"], usage="commercial")})
    assert response.status_code == 200
    assert response.json()["review"] is None
    assert response.json()["pending_input"] is None
    assert response.json()["status"] == "DRAFT"


def test_artifact_id_cannot_traverse_local_files(client):
    assert client.get("/api/artifacts/does-not-exist").status_code == 404
    assert client.get("/api/artifacts/%2e%2e%2fsettings.json").status_code == 404


def test_event_ids_survive_api_restart_and_replay(tmp_path):
    root = tmp_path / "runtime"
    first = create_app(root, tmp_path / "project")
    with TestClient(first) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        job = create(client)
    second = create_app(root, tmp_path / "project")
    repo = second.state.repository
    assert repo.get_job(job["job_id"]).latest_event_id == job["latest_event_id"]
    replay = repo.events_after(job["job_id"], 0)
    assert replay[0]["event_id"] == job["latest_event_id"]
    assert repo.events_after(job["job_id"], replay[-1]["event_id"]) == []
