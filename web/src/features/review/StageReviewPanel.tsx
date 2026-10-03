import { useEffect, useState } from "react";
import type { Decision, Job } from "../../api/types";
import { stageLabels } from "../../components/ui";
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
  const canResolve =
    !locked &&
    job.status === "NEEDS_HUMAN" &&
    job.revision === pending.revision &&
    pending.pendingToken.length >= 16;

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
        {pending.confirmationRequirements.length ? (
          <ul>
            {pending.confirmationRequirements.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : (
          <p className="muted small">当前节点未提供额外检查项。</p>
        )}
      </div>
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
          确认本阶段通过
        </button>
        <button
          className="button secondary"
          disabled={!canResolve}
          onClick={() => resume("revise", note)}
        >
          暂停，手动编辑新版本
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
        选择返工会让任务暂停，方便你修改文案、字幕时间、分镜或素材后再启动对应步骤。
      </p>
    </section>
  );
}
