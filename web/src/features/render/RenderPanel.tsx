import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { Job, RunAction } from "../../api/types";
import type { DirectorShotReviewManifest, DirectorShotReviewSpec } from "../../../../contracts/generated/models";
import { Empty, formatBytes, Notice } from "../../components/ui";
import { latestShotReviewManifest, validateDirectorShotReview } from "../review/directorShotReview";

export interface SeekTarget {
  seconds: number;
  request: number;
}

export function RenderPanel({
  job,
  run,
  locked,
  target,
}: {
  job: Job;
  run: (action: RunAction) => void;
  locked: boolean;
  target: SeekTarget | null;
}) {
  const videos = job.artifacts.filter((artifact) =>
    artifact.mime_type.startsWith("video/"),
  );
  const [selected, setSelected] = useState(videos.at(-1)?.artifact_id ?? "");
  const videoRef = useRef<HTMLVideoElement>(null);
  const video =
    videos.find((artifact) => artifact.artifact_id === selected) ??
    videos.at(-1);
  const currentVideo = video?.revision === job.revision;
  const approval = useDirectorApproval(job);
  const directorApproved = approval.status === "confirmed";
  const legacyDemo = usesLegacyDemo(job);
  const finalRenderBlocked = Boolean(job.timeline) && !directorApproved;
  useEffect(() => {
    if (
      videos.length &&
      (!selected || !videos.some((item) => item.artifact_id === selected))
    )
      setSelected(videos.at(-1)!.artifact_id);
  }, [videos, selected]);
  const seekTo = () => {
    if (videoRef.current && target)
      videoRef.current.currentTime = Math.min(
        target.seconds,
        videoRef.current.duration || target.seconds,
      );
  };
  useEffect(() => {
    seekTo();
  }, [target]);
  const currentArtifacts = job.artifacts.filter(
    (artifact) =>
      artifact.revision === job.revision &&
      !artifact.mime_type.startsWith("video/") &&
      !artifact.mime_type.startsWith("audio/"),
  );
  return (
    <div className="feature-section">
      <div className="section-heading">
        <div>
          <h2>剪辑与交付</h2>
          <p>{legacyDemo ? "先确认导演方案和 Demo，再渲染完整成片。" : "逐一审阅每个镜头的组件选择和实际图片，整套方案通过后再渲染完整成片。"}</p>
        </div>
        <div className="button-row">
          <button
            className="button secondary"
            disabled={locked || !job.timeline}
            onClick={() => run("preview")}
          >
            {legacyDemo ? "生成/更新Demo" : "生成/更新逐镜审核图"}
          </button>
          <button
            className="button primary"
            disabled={locked || !job.timeline || !directorApproved}
            title={
              finalRenderBlocked
                ? approval.message
                : undefined
            }
            onClick={() => run("final")}
          >
            渲染最终视频
          </button>
        </div>
      </div>
      {finalRenderBlocked && (
        <Notice tone="error">
          {approval.message} 后端会在渲染前复核当前导演方案和{legacyDemo ? " Demo" : "全部镜头审核图片"}是否与审批记录匹配。
        </Notice>
      )}
      {job.stage === "render" && ["RUNNING", "QUEUED"].includes(job.status) && (
        <div className="panel render-progress">
          <strong>{job.message || "正在渲染"}</strong>
          {job.progress != null ? (
            <>
              <progress max="1" value={job.progress} />
              <span>{Math.round(job.progress * 100)}%</span>
            </>
          ) : (
            <span className="muted">等待渲染器报告进度</span>
          )}
        </div>
      )}
      {video ? (
        <div className="panel player-panel">
          <div className="inline-spread">
            <h3>视频预览</h3>
            <select
              aria-label="选择视频版本"
              value={video.artifact_id}
              onChange={(event) => setSelected(event.target.value)}
            >
              {videos.map((artifact) => (
                <option key={artifact.artifact_id} value={artifact.artifact_id}>
                  {artifact.name} · 第 {artifact.revision} 版
                </option>
              ))}
            </select>
          </div>
          {!currentVideo && (
            <Notice>
              当前播放第 {video.revision} 版，任务已更新到第 {job.revision}{" "}
              版。旧审核结论不适用于新内容。
            </Notice>
          )}
          <video
            key={video.artifact_id}
            ref={videoRef}
            controls
            preload="metadata"
            src={video.url}
            onLoadedMetadata={seekTo}
            playsInline
          />
          {target && (
            <small className="muted">
              已定位到 {target.seconds.toFixed(2)} 秒，可播放检查此处画面。
            </small>
          )}
          <div className="inline-spread">
            <small className="muted">
              {formatBytes(video.size_bytes)} · {job.brief.width} ×{" "}
              {job.brief.height}
            </small>
            <a
              className="button secondary"
              href={video.url}
              download={video.name}
            >
              下载视频 ↓
            </a>
          </div>
        </div>
      ) : (
        <Empty title="成片将在这里出现">
          {legacyDemo ? "完成分镜后点击「生成/更新Demo」，画面会由 Remotion 实际渲染。" : "完整成片会在逐镜审核通过后出现；每个镜头的 PNG 审核图在导演阶段查看。"}
        </Empty>
      )}
      {currentArtifacts.length > 0 && (
        <div className="panel deliverables">
          <h3>当前版本的其他产物</h3>
          <div className="download-list">
            {currentArtifacts.map((artifact) => (
              <a
                href={artifact.url}
                key={artifact.artifact_id}
                download={artifact.name}
              >
                <span>
                  {artifact.mime_type.startsWith("image/") ? "▧" : "▤"}
                </span>
                <strong>{artifact.name}</strong>
                <small>{formatBytes(artifact.size_bytes)}</small>
                <span>↓</span>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

type DirectorApprovalStatus = "loading" | "confirmed" | "blocked" | "error";

interface DirectorReviewReceipt {
  node_name?: unknown;
  stage?: unknown;
  decision?: unknown;
  revision?: unknown;
  review_mode?: unknown;
  director_shot_review_artifact_id?: unknown;
  reviewed_shot_ids?: unknown;
  subject?: {
    director_shot_review?: DirectorShotReviewManifest;
    director_plan?: { review_mode?: string; timeline_fingerprint?: string; shot_reviews?: DirectorShotReviewSpec[] };
    timeline?: unknown;
    script?: unknown;
  };
}

interface DirectorApprovalState {
  key: string;
  status: DirectorApprovalStatus;
  message: string;
}

function directorApprovalKey(job: Job): string {
  return [
    job.revision,
    job.status,
    String(job.pending_input?.pending_token ?? ""),
    artifactIdentity(latestRevisionArtifact(job, "director_plan")),
    artifactIdentity(latestRevisionVideo(job, ["preview"])),
    artifactIdentity(latestShotReviewManifest(job)),
    ...job.artifacts.filter((artifact) => artifact.revision === job.revision && artifact.kind === "shot_review_frame").map(artifactIdentity),
    timelineIdentity(job),
    ...stageReviewArtifacts(job).map(artifactIdentity),
  ].join("|");
}

function latestRevisionArtifact(job: Job, kind: string) {
  return job.artifacts
    .filter((artifact) => artifact.revision === job.revision && artifact.kind === kind)
    .at(-1);
}

function latestRevisionVideo(job: Job, kinds: string[]) {
  return job.artifacts
    .filter(
      (artifact) =>
        artifact.revision === job.revision &&
        kinds.includes(artifact.kind) &&
        artifact.mime_type.startsWith("video/"),
    )
    .at(-1);
}

function artifactIdentity(artifact?: Job["artifacts"][number]): string {
  if (!artifact) return "missing";
  return [
    artifact.artifact_id,
    artifact.kind,
    artifact.revision,
    artifact.sha256,
    artifact.url,
  ].join(":");
}

function timelineIdentity(job: Job): string {
  const timeline = job.timeline;
  if (!timeline) return "no-timeline";
  return JSON.stringify({ timeline, script: job.script, assets: job.assets, brief: job.brief });
}

function stageReviewArtifacts(job: Job) {
  return job.artifacts.filter(
    (artifact) =>
      artifact.revision === job.revision && artifact.kind === "stage_review",
  );
}

function isPendingDirectorGate(job: Job): boolean {
  const pending = job.pending_input;
  return (
    job.status === "NEEDS_HUMAN" &&
    pending?.kind === "stage_review" &&
    pending.node_name === "director_human_gate"
  );
}

function confirmedDirectorReceipt(
  job: Job,
  receipt: DirectorReviewReceipt,
): boolean {
  return (
    receipt.node_name === "director_human_gate" &&
    receipt.stage === "director" &&
    receipt.decision === "confirm" &&
    receipt.revision === job.revision
  );
}

export function resolveDirectorDemoApproval(
  job: Job,
  receipts: DirectorReviewReceipt[],
): DirectorApprovalStatus {
  if (isPendingDirectorGate(job)) return "blocked";
  for (const receipt of [...receipts].reverse()) {
    if (receipt.node_name !== "director_human_gate") continue;
    return confirmedDirectorReceipt(job, receipt) ? "confirmed" : "blocked";
  }
  return "blocked";
}

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object")
    return `{${Object.entries(value).sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entry]) => `${JSON.stringify(key)}:${canonicalJson(entry)}`).join(",")}}`;
  return JSON.stringify(value) ?? "undefined";
}

export function resolveDirectorShotReviewApproval(
  job: Job,
  receipts: DirectorReviewReceipt[],
  manifest: DirectorShotReviewManifest | null,
): DirectorApprovalStatus {
  if (isPendingDirectorGate(job)) return "blocked";
  const artifact = latestShotReviewManifest(job);
  const plan = latestRevisionArtifact(job, "director_plan");
  const receipt = [...receipts].reverse().find((item) => item.node_name === "director_human_gate");
  if (!receipt || !artifact || !manifest || !confirmedDirectorReceipt(job, receipt) ||
      receipt.review_mode !== "per_shot_stills" || receipt.director_shot_review_artifact_id !== artifact.artifact_id ||
      receipt.subject?.director_plan?.review_mode !== "per_shot_stills" ||
      validateDirectorShotReview(job, manifest, plan, receipt.subject.director_plan) !== null)
    return "blocked";
  const expectedIds = manifest.items.map((item) => item.shot_id);
  if (canonicalJson(receipt.reviewed_shot_ids) !== canonicalJson(expectedIds) ||
      canonicalJson(receipt.subject.director_shot_review) !== canonicalJson(manifest) ||
      canonicalJson(receipt.subject.timeline) !== canonicalJson(job.timeline) ||
      canonicalJson(receipt.subject.script) !== canonicalJson(job.script)) return "blocked";
  return "confirmed";
}

function usesLegacyDemo(job: Job): boolean {
  return job.timeline?.presentation === "component_sample" ||
    (!latestShotReviewManifest(job) && Boolean(latestRevisionVideo(job, ["preview"])));
}

function approvalMessage(status: DirectorApprovalStatus, legacyDemo: boolean): string {
  const label = legacyDemo ? "导演 Demo" : "导演逐镜画面";
  if (status === "loading")
    return `正在读取当前版本的${label}审核记录，读取完成前不会开始完整成片渲染。`;
  if (status === "error")
    return `${label}审核记录读取失败，请刷新后再试；读取失败时不会开始完整成片渲染。`;
  return legacyDemo
    ? "当前版本还没有通过「导演表演与30秒Demo审核」。请先生成/查看 Demo，并在阶段审核中确认通过；确认前不会开始完整成片渲染。"
    : "当前版本还没有通过「导演逐镜组件与画面审核」。请逐一查看所有镜头图片并确认整套方案；确认前不会开始完整成片渲染。";
}

function useDirectorApproval(job: Job): DirectorApprovalState {
  const key = directorApprovalKey(job);
  const artifacts = stageReviewArtifacts(job);
  const legacyDemo = usesLegacyDemo(job);
  const manifestArtifact = latestShotReviewManifest(job);
  const initialStatus: DirectorApprovalStatus =
    isPendingDirectorGate(job) || artifacts.length === 0 ? "blocked" : "loading";
  const [state, setState] = useState<DirectorApprovalState>({
    key,
    status: initialStatus,
    message: approvalMessage(initialStatus, legacyDemo),
  });
  const current =
    state.key === key
      ? state
      : { key, status: initialStatus, message: approvalMessage(initialStatus, legacyDemo) };

  useEffect(() => {
    let cancelled = false;
    if (isPendingDirectorGate(job) || artifacts.length === 0) {
      const status: DirectorApprovalStatus = "blocked";
      setState({ key, status, message: approvalMessage(status, legacyDemo) });
      return;
    }
    setState({ key, status: "loading", message: approvalMessage("loading", legacyDemo) });
    void Promise.all([
      Promise.all(artifacts.map((artifact) =>
        api.artifactJson<DirectorReviewReceipt>(artifact.url),
      )),
      !legacyDemo && manifestArtifact ? api.artifactJson<DirectorShotReviewManifest>(manifestArtifact.url) : Promise.resolve(null),
    ]).then(([receipts, manifest]) => {
        if (cancelled) return;
        const status = legacyDemo ? resolveDirectorDemoApproval(job, receipts) : resolveDirectorShotReviewApproval(job, receipts, manifest);
        setState({ key, status, message: approvalMessage(status, legacyDemo) });
      })
      .catch(() => {
        if (!cancelled)
          setState({ key, status: "error", message: approvalMessage("error", legacyDemo) });
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return current;
}
