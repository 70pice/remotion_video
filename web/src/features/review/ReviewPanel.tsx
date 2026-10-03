import { useEffect, useState } from "react";
import type { Decision, Job, RunAction } from "../../api/types";
import { displayedStatus, isPublishReady } from "../../api/jobStatus";
import { Empty, Notice, StatusBadge } from "../../components/ui";

const ownerNames: Record<string, string> = {
  screenwriter: "编剧",
  script: "编剧",
  voice: "配音",
  director: "导演",
  editing: "剪辑",
  render: "剪辑",
  reviewer: "审核",
  review: "审核",
  human: "人工复核",
};

export function ReviewPanel({
  job,
  locked,
  run,
  resume,
  seek,
}: {
  job: Job;
  locked: boolean;
  run: (action: RunAction) => void;
  resume: (decision: Decision, note: string) => void;
  seek: (seconds: number) => void;
}) {
  const [note, setNote] = useState("");
  const [played, setPlayed] = useState(false);
  useEffect(() => {
    setPlayed(false);
  }, [
    job.revision,
    job.review?.media_sha256,
    job.pending_input?.pending_token,
  ]);
  const review = job.review;
  const hardErrors =
    review?.findings.some(
      (finding) => finding.blocking && finding.severity === "error",
    ) ?? false;
  const pendingToken = job.pending_input?.pending_token;
  const hasPendingToken = typeof pendingToken === 'string' && pendingToken.length >= 16;
  const canConfirm =
    job.status === "NEEDS_HUMAN" && !hardErrors && hasPendingToken;
  const hasVideo = job.artifacts.some(
    (artifact) =>
      artifact.mime_type.startsWith("video/") &&
      artifact.revision === job.revision,
  );
  const actualReady = isPublishReady(job);
  return (
    <div className="feature-section">
      <div className="section-heading">
        <div>
          <h2>审核与复核</h2>
          <p>检查画面、音画对应、事实来源和素材用途。</p>
        </div>
        <button
          className="button secondary"
          disabled={locked || !hasVideo}
          onClick={() => run("review")}
        >
          审核当前视频
        </button>
      </div>
      {actualReady && (
        <Notice tone="success">
          当前成片通过内部交付审核。发布前仍需按目标平台要求确认。
        </Notice>
      )}
      {!review ? (
        <Empty title="还没有审核结果">
          生成当前版本视频后，发起审核查看问题与交付状态。
        </Empty>
      ) : (
        <>
          <div className="panel review-summary">
            <StatusBadge status={displayedStatus(job)} />
            <div>
              <strong>
                {review.findings.filter((finding) => finding.blocking).length}{" "}
                项需要处理
              </strong>
              <small className="muted">
                审核针对当前产物与素材 ·{" "}
                {review.human_confirmed ? "已完成人工复核" : "尚未人工确认"}
              </small>
            </div>
          </div>
          <div className="findings-list">
            {review.findings.map((finding) => (
              <article
                key={finding.finding_id}
                className={`panel finding-card finding-${finding.severity}`}
              >
                <div className="finding-indicator">
                  {finding.severity === "error"
                    ? "!"
                    : finding.severity === "warning"
                      ? "△"
                      : "i"}
                </div>
                <div>
                  <div className="inline-spread">
                    <strong>{finding.message}</strong>
                    <span className="badge">
                      {finding.blocking ? "阻止交付" : "提示"}
                    </span>
                  </div>
                  <div className="finding-meta">
                    <span>
                      责任环节：{ownerNames[finding.owner] ?? finding.owner}
                    </span>
                    <span>{finding.category}</span>
                    {finding.start_frame != null && (
                      <button
                        className="text-button"
                        onClick={() =>
                          seek(
                            finding.start_frame! /
                              (job.timeline?.fps ?? job.brief.fps),
                          )
                        }
                      >
                        定位{" "}
                        {(
                          finding.start_frame /
                          (job.timeline?.fps ?? job.brief.fps)
                        ).toFixed(2)}{" "}
                        秒 ↗
                      </button>
                    )}
                  </div>
                </div>
              </article>
            ))}
          </div>
          <div className="panel form-panel">
            <h3>人工复核</h3>
            <p className="muted small">
              完整播放当前成片，核对事实与授权。错误必须修复后重验，人工确认只处理可复核事项。
            </p>
            <label>
              复核或返工说明
              <textarea
                rows={3}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder="记录已核对的来源、授权说明，或需要调整的具体问题"
                disabled={locked}
              />
            </label>
            <label className="check-label">
              <input
                type="checkbox"
                checked={played}
                disabled={locked}
                onChange={(event) => setPlayed(event.target.checked)}
              />
              我已完整播放当前成片，核对事实、音画和素材用途
            </label>
            <div className="button-row">
              <button
                className="button primary"
                disabled={locked || !canConfirm || !note.trim() || !played}
                onClick={() => resume("confirm", note)}
              >
                确认已核对当前版本
              </button>
              <button
                className="button secondary"
                disabled={
                  locked ||
                  !hasPendingToken ||
                  ![
                    "NEEDS_INPUT",
                    "NEEDS_HUMAN",
                    "REJECTED",
                    "FAILED",
                  ].includes(job.status)
                }
                onClick={() => resume("revise", note)}
              >
                根据问题返工
              </button>
              <button
                className="button danger"
                disabled={
                  locked ||
                  !hasPendingToken ||
                  ![
                    "NEEDS_INPUT",
                    "NEEDS_HUMAN",
                    "REJECTED",
                    "FAILED",
                  ].includes(job.status)
                }
                onClick={() => resume("cancel", note)}
              >
                结束当前任务
              </button>
            </div>
            {hardErrors && (
              <small className="danger-text">
                存在阻止交付的错误，请在对应工作区修复后重新审核。
              </small>
            )}
          </div>
        </>
      )}
    </div>
  );
}
