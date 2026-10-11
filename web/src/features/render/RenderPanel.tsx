import { useEffect, useRef, useState } from "react";
import { api } from "../../api/client";
import type { Job, RunAction } from "../../api/types";
import { Empty, formatBytes, Notice } from "../../components/ui";

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
  const approval = useDirectorDemoApproval(job);
  const directorDemoApproved = approval.status === "confirmed";
  const finalRenderBlocked = Boolean(job.timeline) && !directorDemoApproved;
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
          <p>先确认导演方案和 30 秒 Demo，再渲染完整成片。</p>
        </div>
        <div className="button-row">
          <button
            className="button secondary"
            disabled={locked || !job.timeline}
            onClick={() => run("preview")}
          >
            生成/更新30秒Demo
          </button>
          <button
            className="button primary"
            disabled={locked || !job.timeline || !directorDemoApproved}
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
          {approval.message} 后端仍会在渲染前复核当前导演方案与 Demo 是否匹配。
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
          完成分镜后点击「生成预览」，画面会由 Remotion 实际渲染。
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
  return [
    timeline.revision,
    timeline.fps,
    timeline.duration_in_frames,
    timeline.width,
    timeline.height,
    timeline.shots
      .map((shot) =>
        [
          shot.shot_id,
          shot.start_frame,
          shot.end_frame,
          shot.component_id,
          shot.asset_src ?? "",
        ].join("@"),
      )
      .join(";"),
  ].join(":");
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

function approvalMessage(status: DirectorApprovalStatus): string {
  if (status === "loading")
    return "正在读取当前版本的导演 Demo 审核记录，读取完成前不会开始完整成片渲染。";
  if (status === "error")
    return "导演 Demo 审核记录读取失败，请刷新后再试；读取失败时不会开始完整成片渲染。";
  return "当前版本还没有通过「导演表演与30秒Demo审核」。请先生成/查看 Demo，并在阶段审核中确认通过；确认前不会开始完整成片渲染。";
}

function useDirectorDemoApproval(job: Job): DirectorApprovalState {
  const key = directorApprovalKey(job);
  const artifacts = stageReviewArtifacts(job);
  const initialStatus: DirectorApprovalStatus =
    isPendingDirectorGate(job) || artifacts.length === 0 ? "blocked" : "loading";
  const [state, setState] = useState<DirectorApprovalState>({
    key,
    status: initialStatus,
    message: approvalMessage(initialStatus),
  });
  const current =
    state.key === key
      ? state
      : { key, status: initialStatus, message: approvalMessage(initialStatus) };

  useEffect(() => {
    let cancelled = false;
    if (isPendingDirectorGate(job) || artifacts.length === 0) {
      const status: DirectorApprovalStatus = "blocked";
      setState({ key, status, message: approvalMessage(status) });
      return;
    }
    setState({ key, status: "loading", message: approvalMessage("loading") });
    void Promise.all(
      artifacts.map((artifact) =>
        api.artifactJson<DirectorReviewReceipt>(artifact.url),
      ),
    )
      .then((receipts) => {
        if (cancelled) return;
        const status = resolveDirectorDemoApproval(job, receipts);
        setState({ key, status, message: approvalMessage(status) });
      })
      .catch(() => {
        if (!cancelled)
          setState({ key, status: "error", message: approvalMessage("error") });
      });
    return () => {
      cancelled = true;
    };
  }, [key]);

  return current;
}
