import { useEffect, useRef, useState } from "react";
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
          <p>生成预览确认画面，再渲染最终版本。</p>
        </div>
        <div className="button-row">
          <button
            className="button secondary"
            disabled={locked || !job.timeline}
            onClick={() => run("preview")}
          >
            生成预览
          </button>
          <button
            className="button primary"
            disabled={locked || !job.timeline}
            onClick={() => run("final")}
          >
            渲染最终视频
          </button>
        </div>
      </div>
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
