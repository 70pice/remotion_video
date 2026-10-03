import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Job } from "../src/api/types";
import { ReviewPanel } from "../src/features/review/ReviewPanel";
import { StageReviewPanel } from "../src/features/review/StageReviewPanel";
import {
  canConfirmStageReview,
  getStageReviewPending,
  stageReviewIdentity,
} from "../src/features/review/stageReview";

const baseJob = {
  job_id: "job-1",
  revision: 4,
  status: "NEEDS_HUMAN",
  stage: "script",
  message: "",
  progress: null,
  created_at: "2026-10-03T00:00:00Z",
  updated_at: "2026-10-03T00:00:00Z",
  brief: {
    topic: "测试",
    script_text: "",
    audience: "",
    platform: "",
    usage: "unspecified",
    target_seconds: 30,
    width: 1080,
    height: 1920,
    fps: 30,
    source_urls: [],
  },
  script: null,
  script_discussion: null,
  timeline: null,
  assets: [],
  artifacts: [],
  review: null,
  latest_event_id: 1,
} satisfies Omit<Job, "pending_input">;

function jobWithPending(pending_input: Record<string, unknown>): Job {
  return { ...baseJob, pending_input } as Job;
}

describe("stage review pending state", () => {
  it("parses the stage review contract and defaults minimum note length", () => {
    const pending = getStageReviewPending(
      jobWithPending({
        kind: "stage_review",
        title: "文案人工审核",
        stage: "script",
        node_name: "script_human_gate",
        confirmation_requirements: ["事实来源已核对", "素材用途已核对"],
        pending_token: "stage-review-token-0001",
        revision: 4,
        thread_id: "thread-1",
        dependency_fingerprint: "fp-1",
      }),
    );

    expect(pending?.title).toBe("文案人工审核");
    expect(pending?.confirmationRequirements).toEqual([
      "事实来源已核对",
      "素材用途已核对",
    ]);
    expect(pending?.minNoteLength).toBe(10);
  });

  it("requires revision, token, checklist acknowledgement, and enough notes", () => {
    const job = jobWithPending({
      kind: "stage_review",
      title: "导演人工审核",
      stage: "director",
      node_name: "director_human_gate",
      confirmation_requirements: [],
      min_note_length: 6,
      pending_token: "stage-review-token-0002",
      revision: 4,
      thread_id: "thread-2",
      dependency_fingerprint: "fp-2",
    });
    const pending = getStageReviewPending(job);
    expect(pending).not.toBeNull();

    expect(canConfirmStageReview(job, pending!, "已核", true)).toBe(false);
    expect(canConfirmStageReview(job, pending!, "已经核对完成", false)).toBe(
      false,
    );
    expect(
      canConfirmStageReview(
        { ...job, revision: 5 },
        pending!,
        "已经核对完成",
        true,
      ),
    ).toBe(false);
    expect(canConfirmStageReview(job, pending!, "已经核对完成", true)).toBe(
      true,
    );
  });

  it("changes identity when backend sends a new token, revision, or fingerprint", () => {
    const first = getStageReviewPending(
      jobWithPending({
        kind: "stage_review",
        title: "剪辑人工审核",
        stage: "render",
        node_name: "editing_human_gate",
        confirmation_requirements: [],
        pending_token: "stage-review-token-0003",
        revision: 4,
        thread_id: "thread-3",
        dependency_fingerprint: "fp-3",
      }),
    );
    const second = getStageReviewPending(
      jobWithPending({
        kind: "stage_review",
        title: "剪辑人工审核",
        stage: "render",
        node_name: "editing_human_gate",
        confirmation_requirements: [],
        pending_token: "stage-review-token-0004",
        revision: 5,
        thread_id: "thread-3",
        dependency_fingerprint: "fp-4",
      }),
    );

    expect(stageReviewIdentity(first)).not.toBe(stageReviewIdentity(second));
  });

  it("rejects unrelated pending kinds and invalid stage-review payloads", () => {
    expect(
      getStageReviewPending(
        jobWithPending({
          kind: "final_review",
          pending_token: "stage-review-token-0005",
        }),
      ),
    ).toBeNull();
    expect(
      getStageReviewPending(
        jobWithPending({
          kind: "stage_review",
          title: "缺 revision",
          stage: "script",
          node_name: "script_human_gate",
          pending_token: "stage-review-token-0005",
          thread_id: "thread-5",
          dependency_fingerprint: "fp-5",
        }),
      ),
    ).toBeNull();
  });

  it("allows zero-length notes and counts emoji like Python len", () => {
    const zeroNoteJob = jobWithPending({
      kind: "stage_review",
      title: "零字说明",
      stage: "script",
      node_name: "script_human_gate",
      min_note_length: 0,
      pending_token: "stage-review-token-0006",
      revision: 4,
      thread_id: "thread-6",
      dependency_fingerprint: "fp-6",
    });
    const zeroNotePending = getStageReviewPending(zeroNoteJob);
    expect(zeroNotePending?.minNoteLength).toBe(0);
    expect(canConfirmStageReview(zeroNoteJob, zeroNotePending!, "", true)).toBe(
      true,
    );

    const emojiJob = jobWithPending({
      kind: "stage_review",
      title: "emoji说明",
      stage: "script",
      node_name: "script_human_gate",
      min_note_length: 1,
      pending_token: "stage-review-token-0007",
      revision: 4,
      thread_id: "thread-7",
      dependency_fingerprint: "fp-7",
    });
    const emojiPending = getStageReviewPending(emojiJob);
    expect(canConfirmStageReview(emojiJob, emojiPending!, "👍", true)).toBe(
      true,
    );
  });

  it("blocks bad tokens and stale revisions", () => {
    const job = jobWithPending({
      kind: "stage_review",
      title: "坏 token",
      stage: "script",
      node_name: "script_human_gate",
      min_note_length: 0,
      pending_token: "short",
      revision: 4,
      thread_id: "thread-8",
      dependency_fingerprint: "fp-8",
    });
    const pending = getStageReviewPending(job);
    expect(canConfirmStageReview(job, pending!, "", true)).toBe(false);
    expect(
      canConfirmStageReview(
        {
          ...job,
          revision: 3,
        },
        { ...pending!, pendingToken: "stage-review-token-0008" },
        "",
        true,
      ),
    ).toBe(false);
  });

  it("renders the stage card without final review data", () => {
    const job = jobWithPending({
      kind: "stage_review",
      title: "文案人工审核",
      stage: "script",
      node_name: "script_human_gate",
      confirmation_requirements: ["事实来源已核对"],
      min_note_length: 0,
      pending_token: "stage-review-token-0009",
      revision: 4,
      thread_id: "thread-9",
      dependency_fingerprint: "fp-9",
    });
    const pending = getStageReviewPending(job);
    const markup = renderToStaticMarkup(
      createElement(StageReviewPanel, {
        job,
        pending: pending!,
        locked: false,
        resume: () => undefined,
      }),
    );

    expect(markup).toContain("文案人工审核");
    expect(markup).toContain("事实来源已核对");
    expect(markup).toContain("确认本阶段通过");
    expect(markup).toContain('maxLength="3000"');
    expect(markup).not.toContain("script_human_gate");
  });

  it("does not render the final video confirmation action during stage review", () => {
    const job = {
      ...jobWithPending({
        kind: "stage_review",
        title: "剪辑人工审核",
        stage: "render",
        node_name: "editing_human_gate",
        pending_token: "stage-review-token-0010",
        revision: 4,
        thread_id: "thread-10",
        dependency_fingerprint: "fp-10",
      }),
      review: {
        status: "needs_human",
        findings: [],
        media_sha256: "media",
        dependency_fingerprint: "fp-10",
        coverage: [],
        human_confirmed: false,
      },
    };
    const markup = renderToStaticMarkup(
      createElement(ReviewPanel, {
        job,
        locked: false,
        run: () => undefined,
        resume: () => undefined,
        seek: () => undefined,
      }),
    );

    expect(markup).toContain("当前正在等待阶段人工审核");
    expect(markup).not.toContain("确认已核对当前版本");
  });
});
