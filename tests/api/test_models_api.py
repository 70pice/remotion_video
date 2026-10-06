"""Session-protected catalog API with explicit cache refresh and custom names."""

import json

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from videoagents.contracts import ModelCatalog, ModelChoice
from videoagents.providers import model_catalog
from videoagents.providers.model_catalog import ModelCatalogService


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "runtime", tmp_path / "project")) as client:
        yield client


def bootstrap(client):
    client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]


def test_models_endpoint_requires_session_and_forwards_provider_refresh(client, monkeypatch):
    calls = []
    def get(self, provider, refresh=False):
        calls.append((provider, refresh))
        return ModelCatalog(provider=provider, status="ready", message="UNIT TEST local cache", fetched_at="2026-10-03T07:00:00Z",
                            models=[ModelChoice(id="opaque/model:中文", display_name="Opaque model", hidden=True)])
    monkeypatch.setattr(ModelCatalogService, "get", get)
    assert client.get("/api/models/codex_cli").status_code == 401
    assert calls == []
    bootstrap(client)
    result = client.get("/api/models/codex_cli?refresh=true")
    assert result.status_code == 200
    assert calls == [("codex_cli", True)]
    assert ModelCatalog.model_validate(result.json()).models[0].id == "opaque/model:中文"
    assert result.json()["models"][0]["hidden"] is True
    assert client.get("/api/models/codex_cli").status_code == 200
    assert calls[-1] == ("codex_cli", False)
    assert client.get("/api/models/claude_code_cli?refresh=false").status_code == 200
    assert calls[-1] == ("claude_code_cli", False)
    assert client.get("/api/models/trae_cli?refresh=false").status_code == 200
    assert calls[-1] == ("trae_cli", False)
    before = len(calls)
    assert client.get("/api/models/http").status_code == 422
    assert client.get("/api/models/codex_cli?refresh=not-a-boolean").status_code == 422
    assert len(calls) == before


def test_real_cache_refresh_preserves_settings_and_custom_claude_name(client, tmp_path, monkeypatch):
    home = tmp_path / "only-cache-fixture"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setattr(model_catalog, "executable_prefix", lambda _: ["unit-fixture-never-executed"])
    cache = home / "models_cache.json"
    def write(slug, timestamp):
        cache.write_text(json.dumps({"fetched_at": timestamp, "client_version": "unit", "models": [{
            "slug": slug, "display_name": "Unit " + slug, "description": "fixture", "visibility": "hide"}]}), encoding="utf-8")
    write("local-first", "2026-10-03T07:00:00Z")
    bootstrap(client)
    # Catalog availability does not restrict opaque user-supplied CLI names.
    name = "opaque-claude-name-for-user-account"
    saved = client.patch("/api/settings", json={"role_models": {"review": {
        "enabled": True, "provider": "claude_code_cli", "model": name}}})
    assert saved.status_code == 200
    before = client.app.state.repository.setting_values().copy()
    first = client.get("/api/models/codex_cli?refresh=true")
    assert first.status_code == 200 and first.json()["models"][0]["id"] == "local-first"
    assert first.json()["fetched_at"] == "2026-10-03T07:00:00Z"
    write("local-after-refresh", "2026-10-03T08:00:00Z")
    next_result = client.get("/api/models/codex_cli?refresh=true")
    assert next_result.status_code == 200 and next_result.json()["models"][0]["id"] == "local-after-refresh"
    assert next_result.json()["fetched_at"] == "2026-10-03T08:00:00Z"
    fallback = client.get("/api/models/claude_code_cli?refresh=true")
    assert fallback.status_code == 200 and fallback.json()["status"] == "unavailable"
    assert fallback.json()["models"] == []
    assert client.app.state.repository.setting_values() == before
    assert client.get("/api/settings").json()["role_models"]["review"]["model"] == name
