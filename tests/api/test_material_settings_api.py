"""Old visual-count settings cannot reintroduce a collection cap."""

import json

import pytest
from fastapi.testclient import TestClient

from server.main import create_app


@pytest.mark.parametrize("legacy_limit", [0, 8, 20, 100])
def test_visual_collection_is_unlimited_for_new_and_saved_settings(tmp_path, legacy_limit):
    app = create_app(tmp_path / "runtime", tmp_path / "project")
    with TestClient(app) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        assert "research_max_visuals" not in client.get("/api/settings").json()
        app.state.repository.write_settings({"research_max_visuals": json.dumps(legacy_limit)})
        assert "research_max_visuals" not in client.get("/api/settings").json()
        response = client.patch("/api/settings", json={
            "research_max_visuals": legacy_limit, "research_max_sources": 12,
        })
        assert response.status_code == 200
        assert "research_max_visuals" not in response.json()
        assert response.json()["research_max_sources"] == 12
        assert app.state.repository.setting_values()["research_max_visuals"] == json.dumps(legacy_limit)
