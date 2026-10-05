"""新制作使用固定竖屏，旧版本可读取，拒绝请求不入队。"""

import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from videoagents.contracts import Brief


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "runtime", tmp_path / "project")) as value:
        value.headers["X-CSRF-Token"] = value.get("/api/session").json()["csrf_token"]
        yield value


@pytest.mark.parametrize("changes", [
    {"width": 1920, "height": 1080}, {"width": 1080, "height": 1080},
    {"fps": 60}, {"platform": "通用横屏"},
])
def test_new_job_rejects_non_production_format_without_creating(client, changes):
    response = client.post("/api/jobs", json={"topic": "测试", **changes})
    assert response.status_code == 422
    assert client.get("/api/jobs").json() == []


def test_legacy_job_readable_but_cannot_run_until_new_portrait_revision(client):
    repository = client.app.state.repository
    legacy = repository.create_job(Brief(topic="旧横版", width=1920, height=1080))
    assert client.get(f"/api/jobs/{legacy.job_id}").json()["brief"]["width"] == 1920
    command = {"base_revision": 1, "action": "produce", "idempotency_key": "old-format"}
    assert client.post(f"/api/jobs/{legacy.job_id}/runs", json=command).status_code == 422
    with repository.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 0
    portrait = legacy.brief.model_dump() | {"width": 1080, "height": 1920, "fps": 30, "platform": "抖音"}
    response = client.patch(f"/api/jobs/{legacy.job_id}/draft", json={"base_revision": 1, "brief": portrait})
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    command.update(base_revision=2, idempotency_key="portrait-format")
    assert client.post(f"/api/jobs/{legacy.job_id}/runs", json=command).status_code == 202


def test_draft_cannot_change_portrait_to_landscape(client):
    job = client.post("/api/jobs", json={"topic": "新竖版"}).json()
    brief = job["brief"] | {"width": 1920, "height": 1080}
    response = client.patch(f"/api/jobs/{job['job_id']}/draft", json={"base_revision": 1, "brief": brief})
    assert response.status_code == 422
    assert client.get(f"/api/jobs/{job['job_id']}").json()["revision"] == 1
