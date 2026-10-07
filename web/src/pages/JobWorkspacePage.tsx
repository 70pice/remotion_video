import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, explainError, newCommandKey } from "../api/client";
import type { Brief, Decision, RunAction } from "../api/types";
import { useJob } from "../api/useJob";
import { displayedStatus } from "../api/jobStatus";
import { finishBriefSave } from "../api/draftState";
import { blocksPaidRun, hasUnknownOperation } from "../api/pendingState";
import {
  Empty,
  formatDate,
  Notice,
  stageLabels,
  StatusBadge,
} from "../components/ui";
import { ScriptEditor } from "../features/script/ScriptEditor";
import { AssetsPanel } from "../features/assets/AssetsPanel";
import { MaterialsPanel } from "../features/materials/MaterialsPanel";
import { VoicePanel } from "../features/voice/VoicePanel";
import { StoryboardEditor } from "../features/storyboard/StoryboardEditor";
import { RenderPanel, type SeekTarget } from "../features/render/RenderPanel";
import { ReviewPanel } from "../features/review/ReviewPanel";
import { StageReviewPanel } from "../features/review/StageReviewPanel";
import { getStageReviewPending } from "../features/review/stageReview";
import { ScriptDiscussionPanel } from "../features/script/ScriptDiscussionPanel";

const tabs = [
  ["materials", "素材研究", "01"],
  ["script", "文案", "02"],
  ["assets", "素材库", "03"],
  ["voice", "配音", "04"],
  ["storyboard", "分镜", "05"],
  ["render", "剪辑", "06"],
  ["review", "历史审核", "07"],
] as const;
type Tab = (typeof tabs)[number][0];

function tabForStageReview(stage: string): Tab {
  if (stage === "script") return "script";
  if (stage === "director") return "storyboard";
  if (stage === "render") return "render";
  return "review";
}

export function JobWorkspacePage({ jobId }: { jobId: string }) {
  const { job, setJob, error: loadError, live, refresh } = useJob(jobId);
  const [tab, setTab] = useState<Tab>("materials");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [error, setError] = useState("");
  const [target, setTarget] = useState<SeekTarget | null>(null);
  const commandKeys = useRef(new Map<string, string>());
  const stageReviewRef = useRef<HTMLDivElement | null>(null);
  const [briefDraft, setBriefDraft] = useState<Brief | null>(null);
  const [briefRevision, setBriefRevision] = useState(0);
  const [scriptDirty, setScriptDirty] = useState(false);
  const [timelineDirty, setTimelineDirty] = useState(false);
  const [alignmentDirty, setAlignmentDirty] = useState(false);
  const markScriptDirty = useCallback(
    (dirty: boolean) => setScriptDirty(dirty),
    [],
  );
  const markTimelineDirty = useCallback(
    (dirty: boolean) => setTimelineDirty(dirty),
    [],
  );
  const markAlignmentDirty = useCallback(
    (dirty: boolean) => setAlignmentDirty(dirty),
    [],
  );
  const hasUnsaved =
    scriptDirty || timelineDirty || alignmentDirty || briefDraft !== null;
  const unknown = hasUnknownOperation(job?.pending_input ?? null);
  const stageReviewPending = job ? getStageReviewPending(job) : null;
  const unknownRecoveryHint =
    job?.stage === "voice"
      ? "可以导入已获得的音频并保存实测时间，或取消此任务。"
      : "可以核对服务商记录、保存修改后的任务版本，或手动填写文案和分镜。";

  useEffect(() => {
    if (stageReviewPending) setTab(tabForStageReview(stageReviewPending.stage));
  }, [stageReviewPending?.pendingToken, stageReviewPending?.stage]);

  // Keep keys on uncertain network errors: a retry sends the same persisted command.
  const submit = async (
    identity: string,
    operation: (key: string) => ReturnType<typeof api.run>,
  ) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    const key = commandKeys.current.get(identity) ?? newCommandKey();
    commandKeys.current.set(identity, key);
    try {
      setJob(await operation(key));
      commandKeys.current.delete(identity);
    } catch (cause) {
      setError(explainError(cause));
      if (
        cause instanceof ApiError &&
        cause.status >= 400 &&
        cause.status < 500
      )
        commandKeys.current.delete(identity);
      await refresh();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };

  const run = (action: RunAction) => {
    if (!job) return;
    if (
      unknown &&
      blocksPaidRun(
        action,
        job.assets.some((asset) => asset.role === "audio"),
      )
    ) {
      setError(
        `服务提交受理情况待确认，暂不重新提交付费生成。${unknownRecoveryHint}`,
      );
      return;
    }
    if (hasUnsaved) {
      setError("先保存文案、字幕时间、分镜或制作要求的编辑，再启动制作。");
      return;
    }
    void submit(`${job.revision}:${action}`, (key) =>
      api.run(job, action, key),
    );
  };
  const resume = (decision: Decision, note: string) => {
    if (!job) return;
    if (hasUnsaved && decision !== "cancel") {
      setError("请先保存正在编辑的内容，再提交复核或返工。");
      return;
    }
    void submit(
      `${job.revision}:${job.pending_input?.pending_token}:${decision}:${note}`,
      (key) => api.resume(job, decision, note, key),
    );
  };
  const showStageReview = () => {
    stageReviewRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  };
  const seek = (seconds: number) => {
    setTarget({ seconds, request: Date.now() });
    setTab("render");
  };
  const saveBrief = async () => {
    if (!job || !briefDraft || busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    const submitted = briefDraft;
    try {
      const next = await api.saveDraft(job.job_id, briefRevision, {
        brief: {
          ...submitted,
          platform: "抖音",
          width: 1080,
          height: 1920,
          fps: 30,
        },
      });
      setJob(next);
      setBriefRevision(next.revision);
      setBriefDraft((current) => finishBriefSave(current, submitted));
    } catch (cause) {
      setError(explainError(cause));
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  };
  if (!job)
    return (
      <>
        {loadError && <Notice tone="error">{loadError}</Notice>}
        <Empty title={loadError ? "任务暂时无法读取" : "正在打开制作工作台…"}>
          {loadError && (
            <button
              className="button secondary"
              onClick={() => {
                void refresh();
              }}
            >
              重新读取
            </button>
          )}
        </Empty>
      </>
    );
  const active = ["RUNNING", "QUEUED"].includes(job.status);
  const locked = busy || active;
  const pendingMessage =
    job.pending_input &&
    [
      job.pending_input.message,
      job.pending_input.reason,
      job.pending_input.note,
    ].find((value) => typeof value === "string");
  return (
    <>
      <a className="back-link" href="#/">
        ← 返回任务列表
      </a>
      <div className="workspace-heading">
        <div>
          <div className="eyebrow">VIDEO PRODUCTION WORKSPACE</div>
          <h1>{job.script?.title || job.brief.topic || "我的视频"}</h1>
          <div className="workspace-meta">
            <StatusBadge status={displayedStatus(job)} />
            <span>第 {job.revision} 版</span>
            <span>
              {job.brief.platform} · {job.brief.target_seconds} 秒
            </span>
            <span>更新于 {formatDate(job.updated_at)}</span>
          </div>
        </div>
        <div className="button-row">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => {
              void refresh();
            }}
          >
            刷新
          </button>
          {active ? (
            <button
              className="button danger"
              disabled={busy}
              onClick={() => {
                void submit(`cancel:${job.revision}`, () =>
                  api.cancel(job.job_id),
                );
              }}
            >
              取消制作
            </button>
          ) : job.status === "NEEDS_HUMAN" ? (
            <button
              className="button primary"
              onClick={() => {
                if (stageReviewPending) showStageReview();
                else setTab("review");
              }}
            >
              {stageReviewPending ? "查看待审核 →" : "查看历史审核 →"}
            </button>
          ) : (
            <button
              className="button primary"
              disabled={locked || hasUnsaved || unknown}
              onClick={() => run("produce")}
            >
              开始制作 →
            </button>
          )}
          {unknown && !active && job.status !== "CANCELLED" && (
            <button
              className="button danger"
              disabled={busy}
              onClick={() => {
                void submit(`cancel:${job.revision}`, () =>
                  api.cancel(job.job_id),
                );
              }}
            >
              取消制作
            </button>
          )}
        </div>
      </div>
      {(error || loadError) && (
        <Notice tone="error">{error || loadError}</Notice>
      )}
      {unknown ? (
        <Notice tone="error">
          服务提交受理情况待确认（UNKNOWN）。请先核对服务商的原请求记录，确认结果前不会自动重新提交原请求。
          {unknownRecoveryHint}
        </Notice>
      ) : (
        job.pending_input && (
          <Notice>
            {typeof pendingMessage === "string"
              ? pendingMessage
              : job.message || "需要补充信息，请在对应工作区完成。"}{" "}
            <a href="#/settings">查看服务设置 ↗</a>
          </Notice>
        )
      )}
      {stageReviewPending && (
        <div id="stage-review" ref={stageReviewRef}>
          <StageReviewPanel
            job={job}
            pending={stageReviewPending}
            locked={locked}
            resume={resume}
          />
        </div>
      )}
      <div className="panel workflow-status">
        <div>
          <span className={`connection-dot ${live ? "connected" : ""}`} />
          <strong>{stageLabels[job.stage] ?? job.stage}</strong>
          <span>{job.message || "准备开始制作"}</span>
        </div>
        <small className="muted">
          {live ? "实时同步" : "定时同步 · 连接恢复中"}
        </small>
        {active && job.progress != null && (
          <progress max="1" value={job.progress} />
        )}
      </div>
      <details className="brief-details panel">
        <summary>
          制作要求 · {job.brief.audience} ·{" "}
          {job.brief.usage === "commercial"
            ? "商业用途"
            : job.brief.usage === "personal"
              ? "个人用途"
              : "用途待确认"}{" "}
          <span>编辑要求</span>
        </summary>
        <div className="form-panel">
          {!briefDraft ? (
            <button
              className="button secondary"
              disabled={locked}
              onClick={() => {
                setBriefDraft({
                  ...job.brief,
                  platform: "抖音",
                  width: 1080,
                  height: 1920,
                  fps: 30,
                });
                setBriefRevision(job.revision);
              }}
            >
              修改受众、用途和抖音格式
            </button>
          ) : (
            <fieldset className="editor-fieldset" disabled={locked}>
              <Notice>
                保存后将作为新版本制作要求：抖音竖屏 · 1080 × 1920 · 30 fps
              </Notice>
              <div className="form-grid">
                <label>
                  本期创作方向
                  <textarea
                    rows={5}
                    value={briefDraft.creative_direction}
                    onChange={(event) =>
                      setBriefDraft({
                        ...briefDraft,
                        creative_direction: event.target.value,
                      })
                    }
                    placeholder="本期想讲的问题、角度和重点；不需要写成口播稿。"
                  />
                </label>
                <label>
                  目标受众
                  <input
                    value={briefDraft.audience}
                    onChange={(event) =>
                      setBriefDraft({
                        ...briefDraft,
                        audience: event.target.value,
                      })
                    }
                  />
                </label>
                <label>
                  用途
                  <select
                    value={briefDraft.usage}
                    onChange={(event) =>
                      setBriefDraft({
                        ...briefDraft,
                        usage: event.target.value as Brief["usage"],
                      })
                    }
                  >
                    <option value="unspecified">待确认</option>
                    <option value="personal">个人用途</option>
                    <option value="commercial">商业用途</option>
                  </select>
                </label>
                <label>
                  目标时长（秒）
                  <input
                    type="number"
                    min="5"
                    max="1800"
                    value={briefDraft.target_seconds}
                    onChange={(event) =>
                      setBriefDraft({
                        ...briefDraft,
                        target_seconds: Number(event.target.value),
                      })
                    }
                  />
                </label>
              </div>
              <div className="button-row">
                <button
                  className="button primary"
                  disabled={locked}
                  onClick={() => {
                    void saveBrief();
                  }}
                >
                  保存新版本要求
                </button>
                <button
                  className="button secondary"
                  onClick={() => setBriefDraft(null)}
                >
                  放弃编辑
                </button>
              </div>
            </fieldset>
          )}
        </div>
      </details>
      <div className="workspace-tabs" role="tablist" aria-label="视频制作步骤">
        {tabs.map(([value, label, number]) => (
          <button
            key={value}
            id={`tab-${value}`}
            role="tab"
            aria-selected={tab === value}
            aria-controls={`panel-${value}`}
            onClick={() => setTab(value)}
            className={tab === value ? "selected" : ""}
          >
            <small>{number}</small>
            {label}
          </button>
        ))}
      </div>
      {/* Keep editors mounted when switching tabs so unsaved work isn't discarded. */}
      <div
        hidden={tab !== "materials"}
        role="tabpanel"
        id="panel-materials"
        aria-labelledby="tab-materials"
      >
        <MaterialsPanel job={job} />
      </div>
      <div
        hidden={tab !== "script"}
        role="tabpanel"
        id="panel-script"
        aria-labelledby="tab-script"
      >
        <ScriptEditor
          job={job}
          onUpdate={setJob}
          locked={locked}
          onDirty={markScriptDirty}
        />
        <ScriptDiscussionPanel job={job} />
      </div>
      <div
        hidden={tab !== "assets"}
        role="tabpanel"
        id="panel-assets"
        aria-labelledby="tab-assets"
      >
        <AssetsPanel job={job} refresh={refresh} locked={locked} />
      </div>
      <div
        hidden={tab !== "voice"}
        role="tabpanel"
        id="panel-voice"
        aria-labelledby="tab-voice"
      >
        <VoicePanel
          job={job}
          refresh={refresh}
          onUpdate={setJob}
          run={run}
          locked={locked}
          onDirty={markAlignmentDirty}
          paidGenerationBlocked={unknown}
        />
      </div>
      <div
        hidden={tab !== "storyboard"}
        role="tabpanel"
        id="panel-storyboard"
        aria-labelledby="tab-storyboard"
      >
        <StoryboardEditor
          job={job}
          onUpdate={setJob}
          run={run}
          locked={locked}
          seek={seek}
          onDirty={markTimelineDirty}
        />
      </div>
      <div
        hidden={tab !== "render"}
        role="tabpanel"
        id="panel-render"
        aria-labelledby="tab-render"
      >
        <RenderPanel job={job} run={run} locked={locked} target={target} />
      </div>
      <div
        hidden={tab !== "review"}
        role="tabpanel"
        id="panel-review"
        aria-labelledby="tab-review"
      >
        <ReviewPanel
          job={job}
          locked={locked}
          run={run}
          resume={resume}
          seek={seek}
        />
      </div>
    </>
  );
}
