"""Synchronize paused review content without producing or approving anything."""

import json

import pytest

from videoagents.contracts import Brief, Script, ScriptSegment
from videoagents.main import build_parser
from videoagents.providers.feishu import FeishuReviewBase
from videoagents.storage import Repository


def test_sync_review_root_preserves_job_and_never_schedules(tmp_path, monkeypatch, capsys):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="审核"))
    job = repo.update_job(job.job_id, job.revision, status="NEEDS_HUMAN", stage="script",
        script=Script(title="t", origin="user", revision=job.revision,
            segments=[ScriptSegment(segment_id=f"s{i}", narration=f"第{i}段。") for i in range(7)]),
        pending_input={"node_name": "script_human_gate", "pending_token": "pending1",
                       "confirmation_requirements": ["逐段审核"]})
    calls = []

    def sync(base, received):
        assert received == job and base.allow_root_creation
        calls.append("script")
        return "private-base-token"

    monkeypatch.setattr(FeishuReviewBase, "sync_script", sync)
    monkeypatch.setattr(FeishuReviewBase, "submit_review", lambda *args: calls.append("review"))
    monkeypatch.setattr(FeishuReviewBase, "poll_decision", lambda *a: pytest.fail("must not poll"))
    monkeypatch.setattr(Repository, "enqueue", lambda *a: pytest.fail("must not enqueue"))
    monkeypatch.setattr("videoagents.main._worker", lambda *a: pytest.fail("must not run worker"))
    args = build_parser().parse_args(["--runtime-dir", str(repo.root), "sync-review", job.job_id, "--root"])
    assert args.handler(args) == 0
    assert calls == ["script", "review"]
    assert repo.get_job(job.job_id) == job
    output = json.loads(capsys.readouterr().out)
    assert output["synced"] and output["status"] == "NEEDS_HUMAN"
    assert "private-base-token" not in json.dumps(output)


def test_sync_review_refuses_active_job_before_external_call(tmp_path, monkeypatch, capsys):
    repo = Repository(tmp_path / "runtime")
    job = repo.create_job(Brief(topic="还没有审核待办"))
    monkeypatch.setattr(FeishuReviewBase, "sync_script", lambda *a: pytest.fail("must not sync"))
    args = build_parser().parse_args(["--runtime-dir", str(repo.root), "sync-review", job.job_id, "--root"])
    assert args.handler(args) == 2
    assert "error" in json.loads(capsys.readouterr().out)
