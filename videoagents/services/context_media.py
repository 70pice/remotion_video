"""Read-only approval proof for explanatory media absent from the script."""

from videoagents.contracts import Job, Timeline
from videoagents.storage import Repository
from videoagents.tools.timeline import _context_example_sources, asset_renderable


def approved_context_sources(repository: Repository, job: Job, timeline: Timeline) -> set[str]:
    """Prove the exact reviewed media without changing script links or model input."""
    if timeline.presentation == "component_sample":
        return set()
    linked = _context_example_sources(job)
    requested = {shot.asset_src for shot in timeline.shots
                 if shot.media_usage == "context_example" and shot.asset_src and shot.asset_src not in linked}
    if not requested:
        return set()

    # Keep this import local: recovery also depends on JobService and nodes.
    from videoagents.services.director_recovery import _json, verify_director_recovery_inputs

    proof = verify_director_recovery_inputs(repository, job)
    projection = Job.model_validate(proof["approval_projection"])
    approved = {asset.asset_id: asset for asset in projection.assets}
    artifact = next((item for item in reversed(projection.artifacts) if item.kind == "research"), None)
    if artifact is None:
        return set()
    research = _json(repository, job, artifact)
    sources, visuals = research.get("sources"), research.get("visuals")
    if not isinstance(sources, list) or not isinstance(visuals, list):
        return set()
    return {
        asset.timeline_src for asset in job.assets
        if asset.timeline_src in requested and approved.get(asset.asset_id) == asset
        and asset.role in {"evidence", "illustration"}
        and asset.mime_type.startswith(("image/", "video/")) and asset_renderable(asset)
        and asset.source_url
        and any(isinstance(item, dict) and item.get("asset_id") == asset.asset_id
                and item.get("source_url") == asset.source_url
                and item.get("artifact_id") == asset.artifact_id for item in visuals)
        and any(isinstance(item, dict) and item.get("url") == asset.source_url
                and isinstance(item.get("asset_ids"), list) and asset.asset_id in item["asset_ids"]
                for item in sources)
    }
