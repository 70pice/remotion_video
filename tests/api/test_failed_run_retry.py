import json

from fastapi.testclient import TestClient

from server.main import create_app
from videoagents.storage.repository import dumps, fingerprint, now


def client_with_session(tmp_path):
    app = create_app(tmp_path / "runtime", tmp_path / "project")
    client = TestClient(app)
    client.__enter__()
    token = client.get("/api/session").json()["csrf_token"]
    client.headers["X-CSRF-Token"] = token
    return client


def create_job(client):
    response = client.post("/api/jobs", json={
        "topic": "失败续跑测试",
        "script_text": "观点：测试流程。",
        "target_seconds": 2,
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "usage": "personal",
        "platform": "抖音",
    })
    assert response.status_code == 201
    return response.json()


def mark_failed(repo, job, command_id="a" * 32, payload=None, status="FAILED"):
    payload = payload or {
        "base_revision": job["revision"],
        "action": "produce",
        "idempotency_key": "original-produce",
    }
    with repo.connection(immediate=True) as db:
        db.execute(
            "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (command_id, job["job_id"], payload["idempotency_key"], dumps(payload), fingerprint(payload), status, now()),
        )
    repo.update_job(job["job_id"], job["revision"], status="FAILED", stage="director", message="unit failure")
    return command_id


def queued_retry_payload(repo, job_id, key="retry-unit-command"):
    with repo.connection() as db:
        row = db.execute(
            "SELECT command_id,payload,status FROM commands WHERE job_id=? AND idempotency_key=?",
            (job_id, key),
        ).fetchone()
    assert row is not None
    return row["command_id"], json.loads(row["payload"]), row["status"]


def test_retry_failed_run_queues_original_thread_and_is_idempotent(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        failed_id = mark_failed(repo, job)

        body = {
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-unit-command",
        }
        first = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json=body)
        assert first.status_code == 202
        assert first.json()["status"] == "QUEUED"

        second = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json=body)
        assert second.status_code == 202

        _, payload, status = queued_retry_payload(repo, job["job_id"])
        assert status == "PENDING"
        assert payload == {
            **body,
            "action": "retry",
            "continuation_thread_id": f"job:{job['job_id']}:run:{failed_id}",
        }
        with repo.connection() as db:
            assert db.execute(
                "SELECT COUNT(*) FROM commands WHERE job_id=? AND idempotency_key=?",
                (job["job_id"], "retry-unit-command"),
            ).fetchone()[0] == 1
    finally:
        client.__exit__(None, None, None)


def test_retry_failed_run_reuses_resume_pending_thread(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        failed_id = mark_failed(repo, job, payload={
            "base_revision": job["revision"],
            "action": "resume",
            "decision": "confirm",
            "pending_token": "t" * 16,
            "idempotency_key": "original-resume",
            "pending_input": {"thread_id": "job:unit:existing-thread"},
        })

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-unit-command",
        })

        assert response.status_code == 202
        _, payload, _ = queued_retry_payload(repo, job["job_id"])
        assert payload["continuation_thread_id"] == "job:unit:existing-thread"
    finally:
        client.__exit__(None, None, None)


def test_retry_failed_run_rejects_unsafe_states_without_enqueue(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        failed_id = mark_failed(repo, job)
        repo.update_job(job["job_id"], job["revision"], status="NEEDS_HUMAN", pending_input={"pending_token": "x"})

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-unit-command",
        })

        assert response.status_code == 409
        with repo.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM commands WHERE idempotency_key='retry-unit-command'").fetchone()[0] == 0
    finally:
        client.__exit__(None, None, None)


def test_retry_failed_run_rejects_non_failed_original_command(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        done_id = mark_failed(repo, job, command_id="b" * 32, status="DONE")

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": done_id,
            "idempotency_key": "retry-unit-command",
        })

        assert response.status_code == 409
    finally:
        client.__exit__(None, None, None)


def test_retry_failed_run_rejects_older_failure_after_later_current_revision_command(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        failed_id = mark_failed(repo, job)
        later_payload = {
            "base_revision": job["revision"],
            "action": "produce",
            "idempotency_key": "later-failed-produce",
        }
        with repo.connection(immediate=True) as db:
            db.execute(
                "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
                "VALUES(?,?,?,?,?,'FAILED',?)",
                ("d" * 32, job["job_id"], "later-failed-produce", dumps(later_payload), fingerprint(later_payload), now()),
            )

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-unit-command",
        })

        assert response.status_code == 409
        assert "最新失败命令" in response.json()["detail"]
        with repo.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM commands WHERE idempotency_key='retry-unit-command'").fetchone()[0] == 0
    finally:
        client.__exit__(None, None, None)


def test_retry_failed_run_rejects_stale_failed_command_revision(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        failed_id = mark_failed(repo, job, payload={
            "base_revision": job["revision"] - 1,
            "action": "produce",
            "idempotency_key": "old-revision-produce",
        })

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-unit-command",
        })

        assert response.status_code == 409
    finally:
        client.__exit__(None, None, None)


def test_retry_failed_run_rejects_active_commands_and_unknown_operations(tmp_path):
    client = client_with_session(tmp_path)
    try:
        job = create_job(client)
        repo = client.app.state.repository
        failed_id = mark_failed(repo, job)
        with repo.connection(immediate=True) as db:
            active_payload = {"base_revision": job["revision"], "action": "produce", "idempotency_key": "active"}
            db.execute(
                "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
                "VALUES(?,?,?,?,?,'PENDING',?)",
                ("c" * 32, job["job_id"], "active", dumps(active_payload), fingerprint(active_payload), now()),
            )

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-unit-command",
        })
        assert response.status_code == 409

        with repo.connection(immediate=True) as db:
            db.execute("UPDATE commands SET status='CANCELLED' WHERE idempotency_key='active'")
            db.execute(
                "INSERT INTO operations(operation_id,job_id,input_hash,provider,status,body) VALUES(?,?,?,?,?,?)",
                ("op-unknown", job["job_id"], "hash", "voice", "UNKNOWN", dumps({"revision": job["revision"]})),
            )

        response = client.post(f"/api/jobs/{job['job_id']}/retry-failed-run", json={
            "base_revision": job["revision"],
            "retry_command_id": failed_id,
            "idempotency_key": "retry-after-unknown",
        })
        assert response.status_code == 409
    finally:
        client.__exit__(None, None, None)
