"""Dependency fingerprints binding renders to the exact inputs they reviewed."""

from videoagents.contracts import Job
from videoagents.storage.repository import fingerprint


def dependency_fingerprint(job: Job) -> str:
    return fingerprint({"revision": job.revision, "brief": job.brief.model_dump(),
                        "script": job.script.model_dump() if job.script else None,
                        "timeline": job.timeline.model_dump() if job.timeline else None,
                        "assets": [item.model_dump() for item in job.assets]})
