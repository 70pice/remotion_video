from videoagents.contracts import Brief
from videoagents.storage import Repository


def test_repair_receipt_is_completed_and_bound_to_job_role_revision(tmp_path):
    repo = Repository(tmp_path)
    job = repo.create_job(Brief(topic="UNIT repair receipt"))
    other = repo.create_job(Brief(topic="UNIT unrelated job"))
    result = {"shots": [{"shot_id": "UNIT recorded candidate"}]}
    operation = repo.start_operation(job.job_id, "first", "llm:director", {"revision": job.revision})
    repo.finish_operation(operation["operation_id"], "COMPLETED", {"revision": job.revision, "result": result})
    repo.start_operation(job.job_id, "pending", "llm:director", {"revision": job.revision})
    wrong_revision = repo.start_operation(job.job_id, "other-revision", "llm:director", {"revision": job.revision + 1})
    repo.finish_operation(wrong_revision["operation_id"], "COMPLETED", {"revision": job.revision + 1, "result": {"shots": []}})
    assert repo.latest_completed_operation(job.job_id, "llm:director", job.revision)["result"] == result
    assert repo.latest_completed_operation(other.job_id, "llm:director", job.revision) is None
    assert repo.latest_completed_operation(job.job_id, "llm:voice", job.revision) is None
