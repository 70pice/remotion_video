import type { DirectorShotReviewManifest, DirectorShotReviewSpec } from "../../../../contracts/generated/models";
import type { Artifact, Job } from "../../api/types";

export function latestShotReviewManifest(job: Job): Artifact | undefined {
  return job.artifacts.filter((artifact) =>
    artifact.revision === job.revision && artifact.kind === "director_shot_review",
  ).at(-1);
}

export function usesShotReview(job: Job, plan?: { review_mode?: string } | null): boolean {
  if (job.timeline?.presentation === "component_sample") return false;
  return plan?.review_mode === "per_shot_stills" || Boolean(latestShotReviewManifest(job));
}

export function validateDirectorShotReview(
  job: Job,
  manifest: DirectorShotReviewManifest | null,
  planArtifact?: Artifact,
  plan?: { timeline_fingerprint?: string; shot_reviews?: DirectorShotReviewSpec[] } | null,
): string | null {
  const timeline = job.timeline;
  if (!timeline || !manifest || !planArtifact) return "当前导演方案和逐镜审核包尚未齐全。";
  if (
    manifest.schema_version !== 1 || manifest.mode !== "per_shot_stills" ||
    manifest.job_id !== job.job_id || manifest.revision !== job.revision ||
    timeline.job_id !== job.job_id || timeline.revision !== job.revision ||
    manifest.width !== timeline.width || manifest.height !== timeline.height ||
    manifest.fps !== timeline.fps ||
    manifest.duration_in_frames !== timeline.duration_in_frames ||
    manifest.director_plan_artifact_id !== planArtifact.artifact_id ||
    manifest.director_plan_sha256 !== planArtifact.sha256 ||
    typeof manifest.timeline_fingerprint !== "string" || !manifest.timeline_fingerprint ||
    typeof manifest.dependency_fingerprint !== "string" || !manifest.dependency_fingerprint
  ) return "逐镜审核包与当前版本、导演方案或画幅不匹配，请刷新后重新生成。";
  // The gate fingerprint binds the entire review package; the manifest's
  // dependency fingerprint binds production inputs. They are different hashes.
  if (job.pending_input?.review_mode === "per_shot_stills" &&
      job.pending_input.director_shot_review_artifact_id !== latestShotReviewManifest(job)?.artifact_id)
    return "待审事项绑定的逐镜审核包已过期，不能审核旧图。";
  if (plan && (manifest.timeline_fingerprint !== plan.timeline_fingerprint ||
      !Array.isArray(plan.shot_reviews) || plan.shot_reviews.length !== manifest.items?.length))
    return "逐镜审核包与导演设计的时间轴或代表帧不匹配。";
  if (!Array.isArray(manifest.items) || !manifest.items.length || manifest.items.length !== timeline.shots.length)
    return "逐镜审核图片没有覆盖全部镜头。";
  const registered = new Map(job.artifacts.map((artifact) => [artifact.artifact_id, artifact]));
  const imageIds = new Set<string>();
  for (const [index, shot] of timeline.shots.entries()) {
    const item = manifest.items[index];
    const spec = plan?.shot_reviews?.[index];
    if (
      !item || item.index !== index + 1 || item.shot_id !== shot.shot_id ||
      item.start_frame !== shot.start_frame || item.end_frame !== shot.end_frame ||
      item.component_id !== shot.component_id || (item.set_id ?? null) !== (shot.set_design?.set_id ?? null) ||
      item.title !== shot.title || item.body !== shot.body ||
      (item.asset_src ?? null) !== (shot.asset_src ?? null) ||
      (item.source_label ?? "") !== (shot.source_label ?? "") ||
      !Number.isInteger(item.review_frame) || item.review_frame < shot.start_frame || item.review_frame >= shot.end_frame ||
      !Array.isArray(item.component_ids) || !item.component_ids.length ||
      item.component_ids.some((id) => typeof id !== "string" || !id.trim()) ||
      typeof item.narration !== "string" ||
      typeof item.component_reason !== "string" || !item.component_reason.trim() ||
      typeof item.visual_action !== "string" || !item.visual_action.trim()
    ) return `镜头 ${shot.shot_id} 的审核图或组件说明与当前方案不匹配。`;
    if (spec && (spec.shot_id !== item.shot_id || spec.review_frame !== item.review_frame ||
        spec.component_reason !== item.component_reason || spec.visual_action !== item.visual_action))
      return `镜头 ${shot.shot_id} 的代表帧或导演说明已改变。`;
    if (!item.set_id) {
      const expectedIds = [...new Set([shot.component_id, ...(shot.layers ?? []).map((layer) => layer.component_id)])];
      if (JSON.stringify(item.component_ids) !== JSON.stringify(expectedIds))
        return `镜头 ${shot.shot_id} 的实际组件列表不完整。`;
    }
    const image = item.image;
    const artifact = image && registered.get(image.artifact_id);
    if (
      !image || !artifact || imageIds.has(image.artifact_id) ||
      image.kind !== "shot_review_frame" || image.mime_type !== "image/png" ||
      image.revision !== job.revision || image.size_bytes <= 0 ||
      artifact.kind !== image.kind || artifact.mime_type !== image.mime_type ||
      artifact.revision !== image.revision || artifact.sha256 !== image.sha256 ||
      artifact.url !== image.url || artifact.size_bytes !== image.size_bytes
    ) return `镜头 ${shot.shot_id} 缺少当前任务实际注册的 PNG 图片。`;
    imageIds.add(image.artifact_id);
  }
  return null;
}

export function directorShotReviewReady(
  job: Job,
  manifest: DirectorShotReviewManifest | null,
  planArtifact: Artifact | undefined,
  loadedShotIds: ReadonlySet<string>,
  reviewedShotIds: ReadonlySet<string>,
  plan?: { timeline_fingerprint?: string; shot_reviews?: DirectorShotReviewSpec[] } | null,
): boolean {
  return validateDirectorShotReview(job, manifest, planArtifact, plan) === null && Boolean(
    manifest?.items.every((item) => loadedShotIds.has(item.shot_id) && reviewedShotIds.has(item.shot_id)),
  );
}

export function formatShotReviewFeedback(note: string, feedback: Record<string, string>): string {
  const items = Object.entries(feedback).filter(([, value]) => value.trim())
    .map(([shotId, value]) => `[镜头 ${shotId}] ${value.trim()}`);
  return [note.trim(), ...items].filter(Boolean).join("\n\n");
}
