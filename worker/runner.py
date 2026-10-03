"""Lease/heartbeat loop and crash-safe execution of persisted commands."""

import os
import threading
from pathlib import Path

from videoagents.graph import VideoProductionGraph
from videoagents.providers.llm import CapabilityMissing
from videoagents.storage import Repository
from worker.process_manager import RenderCancelled


class Worker:
    def __init__(self, repository: Repository, project_root: Path | None = None):
        self.repo = repository
        self.project_root = project_root

    def once(self) -> bool:
        self.repo.heartbeat()
        command = self.repo.claim(os.getpid())
        if not command:
            return False
        stop = threading.Event()
        def maintain():
            while not stop.wait(5):
                self.repo.renew(command["command_id"], os.getpid())
        thread = threading.Thread(target=maintain, daemon=True)
        thread.start()
        try:
            with VideoProductionGraph(self.repo, self.project_root) as graph:
                graph.execute(command)
            self.repo.finish(command["command_id"])
        except RenderCancelled:
            self.repo.cancel(command["job_id"])
            self.repo.finish(command["command_id"], "CANCELLED")
        except CapabilityMissing as exc:
            job = self.repo.get_job(command["job_id"])
            if job.status != "CANCELLED":
                self.repo.update_job(job.job_id, job.revision, status="NEEDS_INPUT", message=str(exc)[:2000],
                                     pending_input={"kind": "configuration", "fields": exc.fields})
            self.repo.finish(command["command_id"], "FAILED")
        except Exception as exc:
            job = self.repo.get_job(command["job_id"])
            if job.status != "CANCELLED":
                # No raw request/response/credential dump is exposed through events.
                self.repo.update_job(job.job_id, job.revision, status="FAILED", message="执行失败：" + type(exc).__name__ + ": " + str(exc)[:700], pending_input=None)
            self.repo.finish(command["command_id"], "FAILED")
        finally:
            stop.set()
            thread.join(timeout=1)
            self.repo.heartbeat()
        return True
