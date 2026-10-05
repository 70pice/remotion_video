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
    expect(markup).toContain("确认通过，继续下一阶段");
    expect(markup).toContain("提交返工原因");
    expect(markup).toContain('maxLength="3000"');
    expect(markup).not.toContain("script_human_gate");
  });

  it("renders script review with the actual script and short-video checklist", () => {
    const job = {
      ...jobWithPending({
        kind: "stage_review",
        title: "文案人工审核",
        stage: "script",
        node_name: "script_human_gate",
        confirmation_requirements: [],
        min_note_length: 0,
        pending_token: "stage-review-token-0011",
        revision: 4,
        thread_id: "thread-11",
        dependency_fingerprint: "fp-11",
      }),
      script: {
        title: "Muse 是什么",
        origin: "model",
        revision: 4,
        segments: [
          {
            segment_id: "s1",
            narration: "如果你的电脑能自己安排今天的工作，会发生什么？",
            screen_text: "AI 个人助手",
            source_refs: ["https://example.com/source"],
            asset_ids: [],
          },
        ],
      },
    } as Job;
    const pending = getStageReviewPending(job);
    const markup = renderToStaticMarkup(
      createElement(StageReviewPanel, {
        job,
        pending: pending!,
        locked: false,
        resume: () => undefined,
      }),
    );

    expect(markup).toContain("待审文案");
    expect(markup).toContain("Muse 是什么");
    expect(markup).toContain("如果你的电脑能自己安排今天的工作");
    expect(markup).toContain("首句具体，尽早建立观看理由");
  });

  it("renders director review with timeline shots and asset mapping", () => {
    const job = {
      ...jobWithPending({
        kind: "stage_review",
        title: "导演人工审核",
        stage: "director",
        node_name: "director_human_gate",
        min_note_length: 0,
        pending_token: "stage-review-token-0012",
        revision: 4,
        thread_id: "thread-12",
        dependency_fingerprint: "fp-12",
      }),
      assets: [
        {
          asset_id: "asset-1",
          name: "Muse 官方演示.mp4",
          role: "evidence",
          mime_type: "video/mp4",
          size_bytes: 1024,
          sha256: "sha",
          source_url: "https://example.com",
          license_note: "待核验",
          artifact_id: "artifact-1",
          url: "/api/artifacts/asset-1",
          timeline_src: "videoagents/job-1/muse.mp4",
        },
      ],
      timeline: {
        schema_version: "1",
        job_id: "job-1",
        revision: 4,
        width: 1080,
        height: 1920,
        fps: 30,
        duration_in_frames: 90,
        audio_src: null,
        captions: [],
        shots: [
          {
            shot_id: "shot-1",
            start_frame: 0,
            end_frame: 90,
            component_id: "video",
            title: "真实操作画面",
            body: "展示普通人如何使用助手",
            asset_src: "videoagents/job-1/muse.mp4",
            source_label: "官方演示",
            accent_color: "#B7F36B",
            props: {},
          },
        ],
      },
    } as Job;
    const pending = getStageReviewPending(job);
    const markup = renderToStaticMarkup(
      createElement(StageReviewPanel, {
        job,
        pending: pending!,
        locked: false,
        resume: () => undefined,
      }),
    );

    expect(markup).toContain("待审导演分镜");
    expect(markup).toContain("真实操作画面");
    expect(markup).toContain("Muse 官方演示.mp4");
    expect(markup).toContain("竖屏主体清楚");
  });

  it("renders render review with the latest current preview or final video only", () => {
    const job = {
      ...jobWithPending({
        kind: "stage_review",
        title: "剪辑人工审核",
        stage: "render",
        node_name: "render_human_gate",
        min_note_length: 0,
        pending_token: "stage-review-token-0013",
        revision: 4,
        thread_id: "thread-13",
        dependency_fingerprint: "fp-13",
      }),
      artifacts: [
        {
          artifact_id: "old-video",
          kind: "final",
          name: "旧版.mp4",
          mime_type: "video/mp4",
          size_bytes: 100,
          sha256: "old",
          url: "/api/artifacts/old-video",
          revision: 3,
        },
        {
          artifact_id: "raw-asset-video",
          kind: "asset",
          name: "原始素材.mp4",
          mime_type: "video/mp4",
          size_bytes: 4096,
          sha256: "raw",
          url: "/api/artifacts/raw-asset-video",
          revision: 4,
        },
        {
          artifact_id: "current-video",
          kind: "preview",
          name: "当前预览.mp4",
          mime_type: "video/mp4",
          size_bytes: 2048,
          sha256: "current",
          url: "/api/artifacts/current-video",
          revision: 4,
        },
        {
          artifact_id: "latest-video",
          kind: "final",
          name: "当前成片.mp4",
          mime_type: "video/mp4",
          size_bytes: 3072,
          sha256: "latest",
          url: "/api/artifacts/latest-video",
          revision: 4,
        },
      ],
    } as Job;
    const pending = getStageReviewPending(job);
    const markup = renderToStaticMarkup(
      createElement(StageReviewPanel, {
        job,
        pending: pending!,
        locked: false,
        resume: () => undefined,
      }),
    );

    expect(markup).toContain("待审成片");
    expect(markup).toContain("当前成片.mp4");
    expect(markup).toContain('src="/api/artifacts/latest-video"');
    expect(markup).not.toContain("旧版.mp4");
    expect(markup).not.toContain("原始素材.mp4");
    expect(markup).toContain("音频、画面和字幕同步");
  });

  it("does not treat a raw video asset artifact as a render deliverable", () => {
    const job = {
      ...jobWithPending({
        kind: "stage_review",
        title: "剪辑人工审核",
        stage: "render",
        node_name: "render_human_gate",
        min_note_length: 0,
        pending_token: "stage-review-token-0014",
        revision: 4,
        thread_id: "thread-14",
        dependency_fingerprint: "fp-14",
      }),
      artifacts: [
        {
          artifact_id: "raw-asset-video",
          kind: "asset",
          name: "原始素材.mp4",
          mime_type: "video/mp4",
          size_bytes: 4096,
          sha256: "raw",
          url: "/api/artifacts/raw-asset-video",
          revision: 4,
        },
      ],
    } as Job;
    const pending = getStageReviewPending(job);
    const markup = renderToStaticMarkup(
      createElement(StageReviewPanel, {
        job,
        pending: pending!,
        locked: false,
        resume: () => undefined,
      }),
    );

    expect(markup).toContain("还没有可审核成片");
    expect(markup).not.toContain('src="/api/artifacts/raw-asset-video"');
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
