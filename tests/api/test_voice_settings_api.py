"""Voice protocol configuration and write-only keys, without external calls."""

import pytest
from fastapi.testclient import TestClient

from server.main import create_app

WS_ENDPOINT = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
HTTP_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "runtime", tmp_path / "project")) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        yield client


def test_ws_key_only_configuration_is_complete_without_app_id(client):
    secret = "test-only-voice-api-key"
    response = client.patch("/api/settings", json={"voice_provider": "byte_ws", "voice_api_key": secret,
        "voice_resource_id": "seed-icl-2.0", "voice_id": "S_TEST_ONLY", "voice_model": "seed-tts-2.0-standard"})
    assert response.status_code == 200
    saved = response.json()
    assert saved["voice_configured"] is True and saved["voice_api_key_configured"] is True
    assert saved["voice_access_token_configured"] is False
    assert saved["voice_app_id"] == "" and saved["voice_endpoint"] == WS_ENDPOINT
    assert secret not in response.text and "voice_api_key" not in saved
    assert secret not in client.get("/api/settings").text
    # Storage contains the protected value, not the plain test credential.
    encrypted = client.app.state.repository.setting_values()["voice_api_key"]
    assert encrypted.startswith(("dpapi:", "local:")) and secret not in encrypted
    saved = client.patch("/api/settings", json={"voice_model": "another-supported-model"}).json()
    assert saved["voice_api_key_configured"] is True and saved["voice_model"] == "another-supported-model"


def test_switching_protocol_uses_matching_endpoint_and_preserves_saved_key(client):
    client.patch("/api/settings", json={"voice_provider": "byte_ws", "voice_api_key": "test-only-key"})
    saved = client.patch("/api/settings", json={"voice_provider": "none"}).json()
    assert saved["voice_endpoint"] == WS_ENDPOINT and saved["voice_configured"] is False
    assert saved["voice_api_key_configured"] is True
    saved = client.patch("/api/settings", json={"voice_provider": "byte_http"}).json()
    assert saved["voice_endpoint"] == HTTP_ENDPOINT and saved["voice_api_key_configured"] is True
    sse = HTTP_ENDPOINT + "/sse"
    client.patch("/api/settings", json={"voice_endpoint": sse})
    assert client.patch("/api/settings", json={"voice_provider": "byte_http"}).json()["voice_endpoint"] == sse
    assert client.patch("/api/settings", json={"voice_provider": "byte_ws"}).json()["voice_endpoint"] == WS_ENDPOINT


@pytest.mark.parametrize("endpoint", [HTTP_ENDPOINT, "ws://openspeech.bytedance.com/api/v3/tts/bidirection",
    "wss://elsewhere.example/api/v3/tts/bidirection", WS_ENDPOINT + "?key=private"])
def test_ws_rejects_mismatched_or_untrusted_endpoint_atomically(client, endpoint):
    before = client.get("/api/settings").json()
    response = client.patch("/api/settings", json={"voice_provider": "byte_ws", "voice_endpoint": endpoint,
                                                 "voice_api_key": "test-only-private"})
    assert response.status_code == 422 and "test-only-private" not in response.text
    assert client.get("/api/settings").json() == before


def test_ws_requires_api_key_even_when_legacy_auth_is_present(client):
    response = client.patch("/api/settings", json={"voice_provider": "byte_ws", "voice_id": "S_TEST_ONLY",
        "voice_resource_id": "seed-icl-2.0", "voice_app_id": "test-app", "voice_access_token": "test-only-token"})
    assert response.status_code == 200
    assert response.json()["voice_configured"] is False
    assert response.json()["voice_access_token_configured"] is True
    assert "test-only-token" not in response.text


def test_voice_performance_settings_round_trip_and_defaults(client):
    defaults = client.get("/api/settings").json()
    assert defaults["voice_style"] == "" and defaults["voice_speech_rate"] == 10
    result = client.patch("/api/settings", json={"voice_style": "自然、有情绪起伏，开头突出疑问。", "voice_speech_rate": -12})
    assert result.status_code == 200
    saved = client.get("/api/settings").json()
    assert saved["voice_style"] == "自然、有情绪起伏，开头突出疑问。" and saved["voice_speech_rate"] == -12


def test_ws_defaults_to_one_point_one_but_legacy_http_keeps_native_rate(client):
    assert client.patch("/api/settings", json={"voice_provider": "byte_ws"}).json()["voice_speech_rate"] == 10
    assert client.patch("/api/settings", json={"voice_provider": "byte_http"}).json()["voice_speech_rate"] == 0
    assert client.patch("/api/settings", json={"voice_provider": "byte_ws", "voice_speech_rate": 0}).json()["voice_speech_rate"] == 0


@pytest.mark.parametrize("patch", [{"voice_style": "字" * 2001}, {"voice_speech_rate": -51},
    {"voice_speech_rate": 101}, {"voice_speech_rate": True}, {"voice_speech_rate": 0.5}, {"voice_speech_rate": "10"}])
def test_voice_performance_settings_reject_invalid_values_atomically(client, patch):
    before = client.get("/api/settings").json()
    assert client.patch("/api/settings", json=patch).status_code == 422
    assert client.get("/api/settings").json() == before
