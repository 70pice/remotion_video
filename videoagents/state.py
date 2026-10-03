from typing import Annotated, Any, TypedDict


def latest_resume(previous: str, current: str) -> str:
    return current


class VideoState(TypedDict, total=False):
    job_id: str
    revision: int
    action: str
    run_id: str
    thread_id: str
    audio_asset_id: str
    alignment: dict[str, Any]
    duration_seconds: float
    research: dict[str, Any]
    gate_issues: list[str]
    route: str
    human_decision: dict[str, Any]
    pending_snapshot: dict[str, Any]
    resume_command_id: Annotated[str, latest_resume]
