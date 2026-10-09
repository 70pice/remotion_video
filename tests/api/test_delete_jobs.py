import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.sqlite import SqliteSaver

from server.main import create_app
from videoagents.contracts import Artifact, Asset
from videoagents.storage.repository import dumps, fingerprint, now


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "runtime", tmp_path / "project")
    with TestClient(app) as value:
        value.headers["X-CSRF-Token"] = value.get("/api/session").json()["csrf_token"]
        yield value


def create_job(client, topic="删除测试"):
    response = client.post("/api/jobs", json={"topic": topic})
    assert response.status_code == 201
    return response.json()


def count_rows(repo, table, where="", params=()):
    with repo.connection() as db:
        return db.execute(f"SELECT COUNT(*) FROM {table} {where}", params).fetchone()[0]


def stored_artifact(client, job, artifact_id, name="artifact.json"):
    repo = client.app.state.repository
    folder = repo.root / "jobs" / job["job_id"] / "revisions" / "1"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_text("{}", encoding="utf-8")
    artifact = Artifact(
        artifact_id=artifact_id,
        kind="source",
        name=name,
        mime_type="application/json",
        size_bytes=path.stat().st_size,
        sha256="a" * 64,
        url=f"/api/artifacts/{artifact_id}",
        revision=1,
    )
    repo.put_artifact(job["job_id"], artifact, path)
    repo.update_artifact_metadata(artifact_id, {"source_url": "https://example.test/source"})
    return artifact, path


def attach_asset(client, job, asset_id, artifact):
    repo = client.app.state.repository
    asset = Asset(
        asset_id=asset_id,
        name="asset.png",
        role="evidence",
        mime_type="image/png",
        size_bytes=artifact.size_bytes,
        sha256=artifact.sha256,
        source_url="https://example.test/asset",
        license_note="unit",
        artifact_id=artifact.artifact_id,
        url=artifact.url,
        timeline_src=f"videoagents/{job['job_id']}/assets/{asset_id}.png",
    )
    current = repo.get_job(job["job_id"])
    repo.update_job(job["job_id"], current.revision, assets=[*current.assets, asset], artifacts=[*current.artifacts, artifact])
    repo.update_asset_metadata(asset_id, {"origin": "unit"})
    return asset


def write_checkpoint(runtime, thread_id):
    with sqlite3.connect(runtime / "checkpoints.sqlite", check_same_thread=False) as db:
        saver = SqliteSaver(db)
        saver.setup()
        db.execute(
            "INSERT INTO checkpoints(thread_id,checkpoint_ns,checkpoint_id,parent_checkpoint_id,type,checkpoint,metadata) "
            "VALUES(?,?,?,?,?,?,?)",
            (thread_id, "", "1", None, "json", b"{}", b"{}"),
        )
        db.execute(
            "INSERT INTO writes(thread_id,checkpoint_ns,checkpoint_id,task_id,idx,channel,type,value) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (thread_id, "", "1", "task", 0, "channel", "json", b"{}"),
        )


def checkpoint_threads(runtime):
    with sqlite3.connect(runtime / "checkpoints.sqlite", check_same_thread=False) as db:
        rows = db.execute(
            "SELECT thread_id FROM checkpoints UNION SELECT thread_id FROM writes ORDER BY thread_id"
        ).fetchall()
    return [row[0] for row in rows]


def test_delete_requires_session_csrf_origin_and_cors_allows_delete(client):
    job = create_job(client)
    url = f"/api/jobs/{job['job_id']}?base_revision={job['revision']}"

    assert client.delete(url, headers={"X-CSRF-Token": ""}).status_code == 403
    assert client.delete(url, headers={"Origin": "https://untrusted.example"}).status_code == 403
    preflight = client.options(
        f"/api/jobs/{job['job_id']}",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )
    assert preflight.status_code == 200
    assert "DELETE" in preflight.headers["access-control-allow-methods"]


def test_delete_requires_base_revision_cancelled_status_and_current_revision(client):
    job = create_job(client)
    url = f"/api/jobs/{job['job_id']}"

    assert client.delete(url).status_code == 422
    assert client.delete(f"{url}?base_revision=0").status_code == 422
    assert client.delete(f"{url}?base_revision={job['revision']}").status_code == 409

    updated = client.patch(url + "/draft", json={"base_revision": job["revision"], "brief": job["brief"]})
    assert updated.status_code == 200
    assert client.post(url + "/cancel").status_code == 200

    assert client.delete(f"{url}?base_revision={job['revision']}").status_code == 409
    response = client.delete(f"{url}?base_revision={updated.json()['revision']}")
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(url).status_code == 404


@pytest.mark.parametrize("status", ["PENDING", "CLAIMED"])
def test_delete_rejects_pending_or_claimed_commands_even_after_cancel(client, status):
    job = create_job(client)
    repo = client.app.state.repository
    payload = {"base_revision": job["revision"], "action": "produce", "idempotency_key": f"active-{status.lower()}"}
    assert client.post(f"/api/jobs/{job['job_id']}/cancel").status_code == 200
    with repo.connection(immediate=True) as db:
        db.execute(
            "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (f"cmd-{status.lower()}", job["job_id"], payload["idempotency_key"], dumps(payload), fingerprint(payload), status, now()),
        )

    response = client.delete(f"/api/jobs/{job['job_id']}?base_revision={job['revision']}")

    assert response.status_code == 409
    assert count_rows(repo, "jobs", "WHERE job_id=?", (job["job_id"],)) == 1
    assert count_rows(repo, "commands", "WHERE job_id=?", (job["job_id"],)) == 1


def test_delete_rejects_completed_job_even_after_cancel_and_keeps_records_and_files(client):
    repo = client.app.state.repository
    job = create_job(client)
    artifact, _ = stored_artifact(client, job, "complete-artifact")
    repo.update_job(job["job_id"], job["revision"], status="DRAFT", stage="complete", message="成片已完成")
    assert client.post(f"/api/jobs/{job['job_id']}/cancel").status_code == 200

    response = client.delete(f"/api/jobs/{job['job_id']}?base_revision={job['revision']}")

    assert response.status_code == 409
    assert count_rows(repo, "jobs", "WHERE job_id=?", (job["job_id"],)) == 1
    assert count_rows(repo, "artifacts", "WHERE artifact_id=?", (artifact.artifact_id,)) == 1
    assert (repo.root / "jobs" / job["job_id"]).exists()


def test_delete_cleans_records_checkpoints_runtime_and_public_files_without_touching_other_jobs(client):
    repo = client.app.state.repository
    project_root = client.app.state.service.project_root
    target = create_job(client, "目标任务")
    other = create_job(client, "其他任务")
    target_artifact, _ = stored_artifact(client, target, "target-artifact")
    other_artifact, _ = stored_artifact(client, other, "other-artifact")
    target_asset = attach_asset(client, target, "target-asset", target_artifact)
    other_asset = attach_asset(client, other, "other-asset", other_artifact)

    old_path = repo.root / "jobs" / target["job_id"] / "revisions" / "0" / "old.json"
    old_path.parent.mkdir(parents=True, exist_ok=True)
    old_path.write_text("{}", encoding="utf-8")
    old_artifact = Artifact(
        artifact_id="target-old-artifact",
        kind="review",
        name="old.json",
        mime_type="application/json",
        size_bytes=2,
        sha256="b" * 64,
        url="/api/artifacts/target-old-artifact",
        revision=0,
    )
    repo.put_artifact(target["job_id"], old_artifact, old_path)
    repo.update_artifact_metadata(old_artifact.artifact_id, {"old": True})
    with repo.connection(immediate=True) as db:
        db.execute("INSERT INTO job_inputs VALUES(?,?,?)", (target["job_id"], "active_audio_asset_id", target_asset.asset_id))
        db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?)", ("target-op", target["job_id"], "hash", "unit", "DONE", "{}"))
        db.execute("INSERT INTO run_metrics VALUES(?,?,?,?)", (target["job_id"], 1, "voice_chars", 3))
        db.execute(
            "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            ("target-done", target["job_id"], "target-done", "{}", fingerprint({}), "DONE", now()),
        )
        db.execute("INSERT INTO job_inputs VALUES(?,?,?)", (other["job_id"], "active_audio_asset_id", other_asset.asset_id))
        db.execute("INSERT INTO operations VALUES(?,?,?,?,?,?)", ("other-op", other["job_id"], "hash", "unit", "DONE", "{}"))
        db.execute("INSERT INTO run_metrics VALUES(?,?,?,?)", (other["job_id"], 1, "voice_chars", 7))
        db.execute(
            "INSERT INTO commands(command_id,job_id,idempotency_key,payload,payload_hash,status,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            ("other-done", other["job_id"], "other-done", "{}", fingerprint({}), "DONE", now()),
        )

    target_runtime = repo.root / "jobs" / target["job_id"]
    other_runtime = repo.root / "jobs" / other["job_id"]
    target_public = project_root / "public" / "videoagents" / target["job_id"]
    other_public = project_root / "public" / "videoagents" / other["job_id"]
    for folder in (target_public, other_public):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "asset.png").write_text("x", encoding="utf-8")
    write_checkpoint(repo.root, f"job:{target['job_id']}:run:target-command")
    write_checkpoint(repo.root, f"job:{other['job_id']}:run:other-command")
    write_checkpoint(repo.root, f"manual:{target['job_id']}")

    assert client.post(f"/api/jobs/{target['job_id']}/cancel").status_code == 200
    response = client.delete(f"/api/jobs/{target['job_id']}?base_revision={repo.get_job(target['job_id']).revision}")

    assert response.status_code == 204
    for table in ("jobs", "events", "commands", "artifacts", "job_inputs", "operations", "run_metrics"):
        assert count_rows(repo, table, "WHERE job_id=?", (target["job_id"],)) == 0
        assert count_rows(repo, table, "WHERE job_id=?", (other["job_id"],)) >= 1
    assert repo.asset_metadata(target_asset.asset_id) == {}
    assert repo.artifact_metadata(target_artifact.artifact_id) == {}
    assert repo.artifact_metadata(old_artifact.artifact_id) == {}
    assert repo.asset_metadata(other_asset.asset_id) == {"origin": "unit"}
    assert repo.artifact_metadata(other_artifact.artifact_id) == {"source_url": "https://example.test/source"}
    assert not target_runtime.exists()
    assert not target_public.exists()
    assert other_runtime.exists()
    assert other_public.exists()
    assert checkpoint_threads(repo.root) == [f"job:{other['job_id']}:run:other-command", f"manual:{target['job_id']}"]


def test_delete_rejects_artifact_paths_outside_the_job_directory_before_removing_records(client, tmp_path):
    repo = client.app.state.repository
    job = create_job(client)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    artifact = Artifact(
        artifact_id="unsafe-artifact",
        kind="source",
        name="outside.json",
        mime_type="application/json",
        size_bytes=2,
        sha256="c" * 64,
        url="/api/artifacts/unsafe-artifact",
        revision=1,
    )
    with repo.connection(immediate=True) as db:
        db.execute("INSERT INTO artifacts VALUES(?,?,?,?)", (artifact.artifact_id, job["job_id"], str(outside), artifact.model_dump_json()))
    assert client.post(f"/api/jobs/{job['job_id']}/cancel").status_code == 200

    response = client.delete(f"/api/jobs/{job['job_id']}?base_revision={job['revision']}")

    assert response.status_code == 422
    assert count_rows(repo, "jobs", "WHERE job_id=?", (job["job_id"],)) == 1
    assert count_rows(repo, "artifacts", "WHERE artifact_id=?", (artifact.artifact_id,)) == 1


def test_file_delete_failure_keeps_cancelled_job_records_for_retry(client, monkeypatch):
    repo = client.app.state.repository
    job = create_job(client)
    artifact, _ = stored_artifact(client, job, "retry-artifact")
    runtime_dir = repo.root / "jobs" / job["job_id"]
    assert client.post(f"/api/jobs/{job['job_id']}/cancel").status_code == 200

    def fail_once(path):
        if Path(path) == runtime_dir:
            raise PermissionError("unit locked")

    monkeypatch.setattr("videoagents.services.jobs.shutil.rmtree", fail_once)
    response = client.delete(f"/api/jobs/{job['job_id']}?base_revision={job['revision']}")

    assert response.status_code == 422
    assert count_rows(repo, "jobs", "WHERE job_id=?", (job["job_id"],)) == 1
    assert count_rows(repo, "artifacts", "WHERE artifact_id=?", (artifact.artifact_id,)) == 1
    assert runtime_dir.exists()
