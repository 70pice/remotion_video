import { useEffect, useState } from "react";
import type { Artifact, Asset, Decision, Job, Shot } from "../../api/types";
import { Empty, formatBytes, stageLabels } from "../../components/ui";
import {
  canConfirmStageReview,
  stageReviewIdentity,
  type StageReviewPending,
} from "./stageReview";

export function StageReviewPanel({
  job,
  pending,
  locked,
  resume,
}: {
  job: Job;
  pending: StageReviewPending;
  locked: boolean;
  resume: (decision: Decision, note: string) => void;
}) {
  const [note, setNote] = useState("");
  const [checked, setChecked] = useState(false);
  const identity = stageReviewIdentity(pending);

  useEffect(() => {
    setNote("");
    setChecked(false);
  }, [identity]);

  const canConfirm = canConfirmStageReview(job, pending, note, checked);
  const noteReady = Array.from(note.trim()).length >= pending.minNoteLength;
  const canResolve =
    !locked &&
    job.status === "NEEDS_HUMAN" &&
    job.revision === pending.revision &&
    pending.pendingToken.length >= 16;
  const canRevise = canResolve && noteReady;
  const checklist = [...new Set([
    ...defaultStageChecklist(pending.stage),
    ...pending.confirmationRequirements,
  ])];

  return (
    <section className="panel form-panel stage-review-panel">
      <div className="inline-spread">
        <div>
          <h2>{pending.title}</h2>
          <p className="muted small">
            {stageLabels[pending.stage] ?? pending.stage} · 第{" "}
            {pending.revision} 版
          </p>
        </div>
        <span className="badge status-needs_human">阶段人工审核</span>
      </div>
      <div className="stage-review-checklist">
        <strong>检查清单</strong>
        {checklist.length ? (
          <ul>
            {checklist.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">当前节点未提供额外检查项。</p>
        )}
      </div>
      <StageReviewContent job={job} stage={pending.stage} />
      <label>
        审核说明
        <textarea
          rows={3}
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder={`至少 ${pending.minNoteLength} 个字，写明你核对了什么，或说明返工原因`}
          maxLength={3000}
          disabled={locked}
        />
      </label>
      <label className="check-label">
        <input
          type="checkbox"
          checked={checked}
          disabled={locked}
          onChange={(event) => setChecked(event.target.checked)}
        />
        我已核对本阶段待审内容，当前说明对应第 {pending.revision} 版
      </label>
      <div className="button-row">
        <button
          className="button primary"
          disabled={locked || !canConfirm}
          onClick={() => resume("confirm", note)}
        >
          确认通过，继续下一阶段
        </button>
        <button
          className="button secondary"
          disabled={!canRevise}
          onClick={() => resume("revise", note)}
        >
          提交返工原因
        </button>
        <button
          className="button danger"
          disabled={!canResolve}
          onClick={() => resume("cancel", note)}
        >
          结束当前任务
        </button>
      </div>
      {job.revision !== pending.revision && (
        <small className="danger-text">
          当前任务已切到第 {job.revision} 版，请刷新后处理最新审核待办。
        </small>
      )}
      <p className="muted small stage-review-footnote">
        确认会继续执行下一阶段；返工会把说明提交给对应模型节点重新处理；取消会停止当前任务。
      </p>
    </section>
  );
}

function defaultStageChecklist(stage: string): string[] {
  if (stage === "script")
    return [
      "文案方向贴近普通人，不是产品说明书",
      "首句具体，尽早建立观看理由",
      "表达有吸引力，能自然引到下一段",
      "结尾有自然收束，不突兀断掉",
    ];
  if (stage === "director")
    return [
      "每个镜头都对应具体口播信息",
      "素材使用和来源说明能支撑画面",
      "竖屏主体清楚，手机上能看懂文字",
      "镜头节奏有变化，不是静态堆图",
    ];
  if (stage === "render")
    return [
      "实际视频能播放，当前版本画面完整",
      "音频、画面和字幕同步",
      "字幕大小和位置适合竖屏观看",
      "整体节奏能留住普通观众",
    ];
  return [];
}

function StageReviewContent({ job, stage }: { job: Job; stage: string }) {
  if (stage === "script") return <ScriptStagePreview job={job} />;
  if (stage === "director") return <DirectorStagePreview job={job} />;
  if (stage === "render") return <RenderStagePreview job={job} />;
  return null;
}

function ScriptStagePreview({ job }: { job: Job }) {
  const script = job.script;
  if (!script)
    return (
      <Empty title="还没有可审核文案">
        文案节点完成后，这里会显示实际口播内容。
      </Empty>
    );
  return (
    <div className="stage-review-content">
      <div className="inline-spread">
        <h3>待审文案</h3>
        <small className="muted">第 {script.revision} 版 · {script.origin}</small>
      </div>
      <strong>{script.title}</strong>
      <div className="stage-review-script">
        {script.segments.map((segment, index) => (
          <article key={segment.segment_id}>
            <span className="number-label">{String(index + 1).padStart(2, "0")}</span>
            <p>{segment.narration}</p>
            {segment.screen_text && <small>画面文字：{segment.screen_text}</small>}
            {segment.source_refs.length > 0 && (
              <small>来源：{segment.source_refs.join(" / ")}</small>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}

function DirectorStagePreview({ job }: { job: Job }) {
  const timeline = job.timeline;
  if (!timeline)
    return (
      <Empty title="还没有可审核分镜">
        导演节点完成后，这里会显示实际镜头和素材对应关系。
      </Empty>
    );
  const assetsBySrc = new Map(
    job.assets.map((asset) => [asset.timeline_src, asset] as const),
  );
  return (
    <div className="stage-review-content">
      <div className="inline-spread">
        <h3>待审导演分镜</h3>
        <small className="muted">
          {timeline.shots.length} 镜头 · {(timeline.duration_in_frames / timeline.fps).toFixed(1)} 秒 · {timeline.width}×{timeline.height}
        </small>
      </div>
      <div className="stage-review-shots">
        {timeline.shots.map((shot, index) => (
          <ShotReviewRow
            key={shot.shot_id}
            index={index}
            shot={shot}
            asset={shot.asset_src ? assetsBySrc.get(shot.asset_src) : undefined}
            fps={timeline.fps}
          />
        ))}
      </div>
    </div>
  );
}

function ShotReviewRow({
  index,
  shot,
  asset,
  fps,
}: {
  index: number;
  shot: Shot;
  asset?: Asset;
  fps: number;
}) {
  return (
    <article>
      <span className="number-label">{String(index + 1).padStart(2, "0")}</span>
      <div>
        <strong>{shot.title}</strong>
        <small className="muted">
          {(shot.start_frame / fps).toFixed(2)}–{(shot.end_frame / fps).toFixed(2)} 秒 · {shot.component_id}
        </small>
        {shot.body && <p>{shot.body}</p>}
        <small>
          素材：{asset ? `${asset.name}（${asset.mime_type}）` : shot.asset_src || "无"}
        </small>
        {shot.source_label && <small>来源说明：{shot.source_label}</small>}
      </div>
    </article>
  );
}

function RenderStagePreview({ job }: { job: Job }) {
  const video = latestRevisionVideo(job.artifacts, job.revision);
  if (!video)
    return (
      <Empty title="还没有可审核成片">
        剪辑节点完成后，这里会显示当前版本实际渲染视频。
      </Empty>
    );
  return (
    <div className="stage-review-content stage-review-video">
      <div className="inline-spread">
        <h3>待审成片</h3>
        <small className="muted">
          {video.name} · {formatBytes(video.size_bytes)}
        </small>
      </div>
      <video src={video.url} controls preload="metadata" playsInline />
      <small className="muted">
        当前审核绑定第 {job.revision} 版视频，返工请说明具体秒点或问题。
      </small>
    </div>
  );
}

function latestRevisionVideo(artifacts: Artifact[], revision: number) {
  return artifacts
    .filter(
      (artifact) =>
        artifact.revision === revision &&
        ["preview", "final"].includes(artifact.kind) &&
        artifact.mime_type.startsWith("video/"),
    )
    .at(-1);
}
