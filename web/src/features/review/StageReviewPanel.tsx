import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
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
  const directorReadyKey =
    pending.stage === "director" ? directorReviewReadyKey(job, pending) : "";
  const [directorReviewReady, setDirectorReviewReady] = useState({
    key: directorReadyKey,
    ready: pending.stage !== "director",
  });

  useEffect(() => {
    setNote("");
    setChecked(false);
    setDirectorReviewReady({
      key: directorReadyKey,
      ready: pending.stage !== "director",
    });
  }, [identity, pending.stage, directorReadyKey]);

  const handleDirectorReadyChange = useCallback((ready: boolean, key: string) => {
    setDirectorReviewReady({ ready, key });
  }, []);

  const directorCanConfirm =
    pending.stage !== "director" ||
    (directorReviewReady.ready && directorReviewReady.key === directorReadyKey);

  const canConfirm =
    canConfirmStageReview(job, pending, note, checked) && directorCanConfirm;
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
      <StageReviewContent
        job={job}
        stage={pending.stage}
        directorReadyKey={directorReadyKey}
        onDirectorReadyChange={handleDirectorReadyChange}
      />
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
      {pending.stage === "director" && !directorCanConfirm && (
        <small className="danger-text">
          请等待导演方案读取成功，并确认当前版本 30 秒 Demo 视频已显示后再通过审核。
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

function StageReviewContent({
  job,
  stage,
  directorReadyKey,
  onDirectorReadyChange,
}: {
  job: Job;
  stage: string;
  directorReadyKey: string;
  onDirectorReadyChange?: (ready: boolean, key: string) => void;
}) {
  if (stage === "script") return <ScriptStagePreview job={job} />;
  if (stage === "director")
    return (
      <DirectorStagePreview
        job={job}
        readyKey={directorReadyKey}
        onReadyChange={onDirectorReadyChange}
      />
    );
  if (stage === "render") return <RenderStagePreview job={job} />;
  return null;
}

interface DirectorSegmentPerformance {
  segment_id: string;
  shot_ids: string[];
  component_reason: string;
  visual_action: string;
}

interface DirectorDemoPlan {
  start_frame: number;
  end_frame: number;
  reason: string;
}

interface DirectorComponentUsage {
  required?: number;
  library_count?: number;
  library_ids?: string[];
  main_count?: number;
  layer_count?: number;
  native_manifest_fingerprint?: string | null;
}

interface DirectorPlanArtifact {
  segment_performances?: DirectorSegmentPerformance[];
  component_usage?: DirectorComponentUsage;
  demo?: DirectorDemoPlan;
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
      {(script.title_hook || script.opening_visual || script.final_answer) && (
        <div className="stage-review-script-meta">
          <small className="muted">
            创作信息仅用于审核开头画面和主答案，实际口播以段落内容为准。
          </small>
          {script.title_hook && <small>前3秒画面字：{script.title_hook}</small>}
          {script.opening_visual && (
            <small>开头画面建议：{script.opening_visual}</small>
          )}
          {script.final_answer && <small>一句主答案：{script.final_answer}</small>}
        </div>
      )}
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

function DirectorStagePreview({
  job,
  readyKey,
  onReadyChange,
}: {
  job: Job;
  readyKey: string;
  onReadyChange?: (ready: boolean, key: string) => void;
}) {
  const timeline = job.timeline;
  const planArtifact = latestRevisionArtifact(
    job.artifacts,
    job.revision,
    "director_plan",
  );
  const demoVideo = latestRevisionVideo(job.artifacts, job.revision, [
    "preview",
  ]);
  const [plan, setPlan] = useState<DirectorPlanArtifact | null>(null);
  const [planState, setPlanState] = useState<"idle" | "loading" | "loaded" | "error">(
    "idle",
  );

  useEffect(() => {
    let cancelled = false;
    setPlan(null);
    onReadyChange?.(false, readyKey);
    if (!planArtifact) {
      setPlanState("idle");
      return;
    }
    setPlanState("loading");
    void api
      .artifactJson<DirectorPlanArtifact>(planArtifact.url)
      .then((value) => {
        if (!cancelled) {
          setPlan(value);
          setPlanState("loaded");
        }
      })
      .catch(() => {
        if (!cancelled) setPlanState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [planArtifact?.artifact_id, planArtifact?.url, onReadyChange, readyKey]);

  const planReady = directorStageReviewReady(plan, planState, demoVideo);

  useEffect(() => {
    onReadyChange?.(planReady, readyKey);
  }, [onReadyChange, planReady, readyKey]);

  if (!timeline)
    return (
      <Empty title="还没有可审核分镜">
        导演节点完成后，这里会显示实际镜头和素材对应关系。
      </Empty>
    );
  const assetsBySrc = new Map(
    job.assets.map((asset) => [asset.timeline_src, asset] as const),
  );
  const layerCount = timeline.shots.reduce(
    (total, shot) => total + (shot.layers?.length ?? 0),
    0,
  );
  return (
    <div className="stage-review-content">
      <div className="inline-spread">
        <h3>待审导演分镜</h3>
        <small className="muted">
          {timeline.shots.length} 个主镜头 · {layerCount} 个叠加层 · {(timeline.duration_in_frames / timeline.fps).toFixed(1)} 秒 · {timeline.width}×{timeline.height}
        </small>
      </div>
      <p className="muted small">
        完整分镜包含主镜头和文字/强调叠加层；上方 Demo 只覆盖导演选出的 30 秒以内片段。
      </p>
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
      <DirectorPlanReview
        plan={plan}
        planState={planState}
        fps={timeline.fps}
        demoVideo={demoVideo}
        scriptSegments={job.script?.segments ?? []}
      />
    </div>
  );
}

export function DirectorPlanReview({
  plan,
  planState,
  fps,
  demoVideo,
  scriptSegments = [],
}: {
  plan: DirectorPlanArtifact | null;
  planState: "idle" | "loading" | "loaded" | "error";
  fps: number;
  demoVideo?: Artifact;
  scriptSegments?: Array<{ segment_id: string; narration: string }>;
}) {
  const performances = plan?.segment_performances ?? [];
  return (
    <div className="stage-review-director-plan">
      <div className="inline-spread">
        <h3>导演逐段表演方案</h3>
        <small className="muted">
          {plan?.demo ? formatDemoRange(plan.demo, fps) : "等待读取导演方案"}
        </small>
      </div>
      {planState === "loading" && (
        <p className="muted small">正在读取导演方案…</p>
      )}
      {planState === "error" && (
        <p className="danger-text small">
          导演方案读取失败，请刷新后再审核。
        </p>
      )}
      {planState === "idle" && (
        <p className="muted small">还没有导演方案，不能确认导演审核。</p>
      )}
      <ComponentUsageSummary usage={plan?.component_usage} />
      {plan?.demo && (
        <div className="stage-review-demo-card">
          <strong>30 秒 Demo 区间</strong>
          <small>
            {plan.demo.start_frame}–{plan.demo.end_frame} 帧 ·{" "}
            {formatDemoRange(plan.demo, fps)}
          </small>
          <p>{plan.demo.reason}</p>
          {demoVideo ? (
            <video src={demoVideo.url} controls preload="metadata" playsInline />
          ) : (
            <small className="muted">
              Demo 视频渲染完成后会在这里显示，未看到视频前不要确认通过。
            </small>
          )}
        </div>
      )}
      {performances.length > 0 && (
        <div className="stage-review-performances">
          {performances.map((item, index) => {
            const segment = scriptSegments.find(
              (entry) => entry.segment_id === item.segment_id,
            );
            return (
              <article key={item.segment_id}>
                <strong>
                  第 {index + 1} 段
                  {segment?.narration ? `：${segment.narration}` : ""}
                </strong>
                <small>
                  关联镜头：{item.shot_ids.join(" / ") || "未绑定镜头"}
                </small>
                <p>
                  <b>画面组件为什么这样用：</b>
                  {item.component_reason}
                </p>
                <p>
                  <b>这一段怎么演：</b>
                  {item.visual_action}
                </p>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}


function ComponentUsageSummary({
  usage,
}: {
  usage?: DirectorPlanArtifact["component_usage"];
}) {
  if (!usage) return null;
  const libraryIds = usage.library_ids ?? [];
  return (
    <div className="stage-review-demo-card">
      <strong>导演方案原生组件用量</strong>
      <small className="muted">
        要求至少 {usage.required ?? 0} 个，实际 {usage.library_count ?? libraryIds.length} 个；Demo 只是抽取其中 30 秒以内供先审。
      </small>
      <small>
        主镜头 {usage.main_count ?? 0} 个 · 叠加层 {usage.layer_count ?? 0} 个
      </small>
      {libraryIds.length > 0 && <small>原生组件：{libraryIds.join(" / ")}</small>}
      {usage.native_manifest_fingerprint && (
        <small className="muted">
          原生清单指纹：{usage.native_manifest_fingerprint.slice(0, 12)}
        </small>
      )}
    </div>
  );
}

function shotLayers(shot: Shot) {
  return shot.layers ?? [];
}

function LayerReviewRows({ shot, fps }: { shot: Shot; fps: number }) {
  const layers = shotLayers(shot);
  if (!layers.length) return null;
  return (
    <div className="stage-review-performances">
      {layers.map((layer, layerIndex) => (
        <article key={`${layer.component_id}-${layer.role}-${layerIndex}`}>
          <strong>
            叠加层 {layerIndex + 1}：{layer.role === "title" ? "标题" : "强调"} · {layer.component_id}
          </strong>
          <small>
            镜头内 {(layer.start_frame / fps).toFixed(2)}–{(layer.end_frame / fps).toFixed(2)} 秒
          </small>
          <p>{layer.title}</p>
          {layer.body && <small>{layer.body}</small>}
        </article>
      ))}
    </div>
  );
}

export function formatDemoRange(demo: DirectorDemoPlan, fps: number): string {
  const start = demo.start_frame / fps;
  const end = demo.end_frame / fps;
  return `${start.toFixed(2)}–${end.toFixed(2)} 秒`;
}

export function directorStageReviewReady(
  plan: DirectorPlanArtifact | null,
  planState: "idle" | "loading" | "loaded" | "error",
  demoVideo?: Artifact,
): boolean {
  return Boolean(
    planState === "loaded" &&
      plan?.demo &&
      Array.isArray(plan.segment_performances) &&
      demoVideo,
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
        <LayerReviewRows shot={shot} fps={fps} />
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


function directorReviewReadyKey(job: Job, pending: StageReviewPending): string {
  const plan = latestRevisionArtifact(job.artifacts, job.revision, "director_plan");
  const demo = latestRevisionVideo(job.artifacts, job.revision, ["preview"]);
  return [
    stageReviewIdentity(pending),
    artifactIdentity(plan),
    artifactIdentity(demo),
    timelineIdentity(job),
  ].join("|");
}

function artifactIdentity(artifact?: Artifact): string {
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
          shot.layers
            ?.map((layer) =>
              [
                layer.component_id,
                layer.role,
                layer.start_frame,
                layer.end_frame,
                layer.title,
              ].join("#"),
            )
            .join("~") ?? "",
        ].join("@"),
      )
      .join(";"),
  ].join(":");
}

function latestRevisionArtifact(
  artifacts: Artifact[],
  revision: number,
  kind: string,
) {
  return artifacts
    .filter((artifact) => artifact.revision === revision && artifact.kind === kind)
    .at(-1);
}

function latestRevisionVideo(
  artifacts: Artifact[],
  revision: number,
  kinds = ["preview", "final"],
) {
  return artifacts
    .filter(
      (artifact) =>
        artifact.revision === revision &&
        kinds.includes(artifact.kind) &&
        artifact.mime_type.startsWith("video/"),
    )
    .at(-1);
}
