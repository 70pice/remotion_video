import os
import time

from videoagents.contracts import Brief
from videoagents.storage import Repository


def test_live_process_is_never_reclaimed_by_expired_lease(tmp_path):
    repo = Repository(tmp_path)
    job = repo.create_job(Brief(topic="unit-test"))
    repo.enqueue(job.job_id, {"base_revision": 1, "action": "produce", "idempotency_key": "one-command"})
    command = repo.claim(os.getpid())
    with repo.connection() as db:
        db.execute("UPDATE commands SET lease_until=? WHERE command_id=?", (time.time() - 60, command["command_id"]))
    assert repo.claim(os.getpid()) is None


def test_dead_process_reclaims_same_command_not_a_second_run(tmp_path):
    repo = Repository(tmp_path)
    job = repo.create_job(Brief(topic="unit-test"))
    repo.enqueue(job.job_id, {"base_revision": 1, "action": "produce", "idempotency_key": "one-command"})
    command = repo.claim(os.getpid())
    with repo.connection() as db:
        db.execute("UPDATE commands SET lease_until=?,pid=? WHERE command_id=?", (time.time() - 60, 2147483647, command["command_id"]))
    claimed = repo.claim(os.getpid())
    assert claimed["command_id"] == command["command_id"]
    with repo.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM commands").fetchone()[0] == 1
