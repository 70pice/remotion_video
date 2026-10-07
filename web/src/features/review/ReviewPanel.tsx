import type { Job } from "../../api/types";
import { displayedStatus, isProductionComplete } from "../../api/jobStatus";
import { Empty, Notice, StatusBadge } from "../../components/ui";
import { getStageReviewPending } from "./stageReview";

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
  seek,
}: {
  job: Job;
  locked?: boolean;
  run?: unknown;
  resume?: unknown;
  seek: (seconds: number) => void;
}) {
  const stageReviewPending = getStageReviewPending(job);
  const review = job.review;
  const hardErrors =
    review?.findings.some(
      (finding) => finding.blocking && finding.severity === "error",
    ) ?? false;
  const productionComplete = isProductionComplete(job);
  if (stageReviewPending) {
    return (
      <div className="feature-section">
        <div className="section-heading">
          <div>
            <h2>历史审核</h2>
            <p>当前正在等待阶段人工审核，请使用工作台顶部的审核卡处理。</p>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="feature-section">
      <div className="section-heading">
        <div>
          <h2>历史审核</h2>
          <p>查看旧流程留下的问题记录；当前制作流程生成成片后直接结束。</p>
        </div>
      </div>
      {productionComplete && (
        <Notice tone="success">
          当前成片已生成。发布前仍需人工按目标平台要求另行判断。
        </Notice>
      )}
      {!review ? (
        <Empty title="还没有审核结果">
          新流程不再发起成片审核；这里仅保留历史审核报告。
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
                历史报告针对当时产物与素材 ·{" "}
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
          {hardErrors && (
            <Notice tone="error">
              历史报告中存在阻止交付的错误，请在对应工作区修复后重新制作。
            </Notice>
          )}
        </>
      )}
    </div>
  );
}
