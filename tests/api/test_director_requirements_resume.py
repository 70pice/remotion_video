from fastapi.testclient import TestClient

from server.main import create_app


def test_resume_api_accepts_director_requirements_only_on_revise_after_pending_token(tmp_path):
    app = create_app(tmp_path / "runtime", tmp_path / "project")
    with TestClient(app) as client:
        client.headers["X-CSRF-Token"] = client.get("/api/session").json()["csrf_token"]
        created = client.post("/api/jobs", json={"topic": "组件约束", "script_text": "讲清组件约束。"})
        assert created.status_code == 201
        job = created.json()
        repo = client.app.state.repository
        pending = {
            "kind": "stage_review",
            "stage": "director",
            "node_name": "director_human_gate",
            "thread_id": "job:unit:director",
            "pending_token": "director-token-0001",
        }
        repo.update_job(job["job_id"], job["revision"], status="NEEDS_HUMAN", stage="director", pending_input=pending)

        confirm = client.post(f"/api/jobs/{job['job_id']}/resume", json={
            "base_revision": job["revision"],
            "decision": "confirm",
            "note": "确认",
            "pending_token": pending["pending_token"],
            "idempotency_key": "UNIT-confirm-requirements",
            "director_requirements": {"min_library_components": 60},
        })
        assert confirm.status_code == 422

        response = client.post(f"/api/jobs/{job['job_id']}/resume", json={
            "base_revision": job["revision"],
            "decision": "revise",
            "note": "请至少使用 60 个不同的原生库组件。",
            "pending_token": pending["pending_token"],
            "idempotency_key": "UNIT-revise-requirements",
            "director_requirements": {"min_library_components": 60},
        })
        assert response.status_code == 202
        assert response.json()["status"] == "QUEUED"
        with repo.connection() as db:
            payload = db.execute("SELECT payload FROM commands WHERE idempotency_key=?", ("UNIT-revise-requirements",)).fetchone()[0]
        assert '"director_requirements":{"min_library_components":60}' in payload.replace(" ", "")
