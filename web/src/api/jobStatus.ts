import type { Job } from "./types";

export function isProductionComplete(job: Job): boolean {
  if (job.status !== "DRAFT" || job.stage !== "complete") return false;
  return job.artifacts.some(
    (artifact) =>
      artifact.kind === "final" &&
      artifact.revision === job.revision &&
      artifact.mime_type.startsWith("video/"),
  );
}

// A transport status alone isn't proof that a matching final file was reviewed.
export function isPublishReady(job: Job): boolean {
  if (
    job.status !== "READY_FOR_PUBLISH" ||
    !job.review?.media_sha256 ||
    job.review.status !== "PASS" ||
    !job.review.human_confirmed
  )
    return false;
  return job.artifacts.some(
    (artifact) =>
      artifact.kind === "final" &&
      artifact.revision === job.revision &&
      artifact.mime_type.startsWith("video/") &&
      artifact.sha256 === job.review?.media_sha256,
  );
}

export function displayedStatus(job: Job): string {
  if (isProductionComplete(job)) return "PRODUCTION_COMPLETE";
  return job.status === "READY_FOR_PUBLISH" && !isPublishReady(job)
    ? "NEEDS_HUMAN"
    : job.status;
}
