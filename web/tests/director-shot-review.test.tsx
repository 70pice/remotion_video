import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Artifact, Job } from "../src/api/types";
import type { DirectorShotReviewManifest } from "../../contracts/generated/models";
import {
  directorShotReviewReady,
  formatShotReviewFeedback,
  validateDirectorShotReview,
} from "../src/features/review/directorShotReview";
import { DirectorShotReviewGallery } from "../src/features/review/DirectorShotReviewGallery";
import { RenderPanel, resolveDirectorShotReviewApproval } from "../src/features/render/RenderPanel";

const planArtifact: Artifact = {
  artifact_id: "plan-1", kind: "director_plan", name: "plan.json",
  mime_type: "application/json", size_bytes: 100, sha256: "plan-sha",
  url: "/api/artifacts/plan-1", revision: 4,
};
const image: Artifact = {
  artifact_id: "frame-1", kind: "shot_review_frame", name: "shot-1.png",
  mime_type: "image/png", size_bytes: 300, sha256: "image-sha",
  url: "/api/artifacts/frame-1", revision: 4,
};
const job = {
  job_id: "job-1", revision: 4, status: "NEEDS_HUMAN", stage: "director",
  artifacts: [planArtifact, image], assets: [], script: null,
  pending_input: { dependency_fingerprint: "dependency-1" },
  timeline: {
    job_id: "job-1", revision: 4, schema_version: "1", presentation: "production",
    width: 1080, height: 1920, fps: 30, duration_in_frames: 90,
    audio_src: null, captions: [], shots: [{
      shot_id: "shot-1", start_frame: 0, end_frame: 90,
      component_id: "evidence", title: "原文证据", body: "正文",
      asset_src: null, source_label: "真实来源", accent_color: "#fff",
      props: {}, layers: [], set_design: {
        set_id: "A05", content: { takeaway: "原文与放大窗同屏" }, parts: [],
      },
    }],
  },
} as unknown as Job;
const manifest: DirectorShotReviewManifest = {
  schema_version: 1, mode: "per_shot_stills", job_id: "job-1", revision: 4,
  director_plan_artifact_id: "plan-1", director_plan_sha256: "plan-sha",
  dependency_fingerprint: "dependency-1", timeline_fingerprint: "timeline-1",
  width: 1080, height: 1920, fps: 30, duration_in_frames: 90,
  items: [{
    shot_id: "shot-1", index: 1, start_frame: 0, end_frame: 90, review_frame: 45,
    component_id: "evidence", set_id: "A05",
    component_ids: ["MaterialFocus", "TextHighlight"], title: "原文证据", body: "正文",
    asset_src: null, source_label: "真实来源", narration: "这是这个镜头的真实口播。",
    component_reason: "保留原图和局部放大窗", visual_action: "圈出原文，再展示放大内容",
    image,
  }],
};

describe("director per-shot image review", () => {
  it("requires an exact current-plan bundle with a registered image for every ordered shot", () => {
    expect(validateDirectorShotReview(job, manifest, planArtifact)).toBeNull();
    expect(validateDirectorShotReview(job, { ...manifest, revision: 3 }, planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, { ...manifest, director_plan_sha256: "old" }, planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, { ...manifest, items: [] }, planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, { ...manifest, items: [manifest.items[0], manifest.items[0]] }, planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview({ ...job, artifacts: [planArtifact] }, manifest, planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview({ ...job, pending_input: {
      review_mode: "per_shot_stills", director_shot_review_artifact_id: "old-package",
    } }, manifest, planArtifact)).toBeTruthy();
  });

  it("rejects mismatched source choices, missing component IDs, and a frame outside its shot", () => {
    const change = (changes: Partial<DirectorShotReviewManifest["items"][number]>) => ({
      ...manifest, items: [{ ...manifest.items[0], ...changes }],
    });
    expect(validateDirectorShotReview(job, change({ component_id: "video" }), planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, change({ set_id: "A06" }), planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, change({ component_ids: [] }), planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, change({ review_frame: 90 }), planArtifact)).toBeTruthy();
    expect(validateDirectorShotReview(job, change({ image: { ...image, sha256: "old" } }), planArtifact)).toBeTruthy();
  });

  it("cannot confirm before every actual image is loaded and every shot is explicitly reviewed", () => {
    const all = new Set(["shot-1"]);
    expect(directorShotReviewReady(job, manifest, planArtifact, all, all)).toBe(true);
    expect(directorShotReviewReady(job, manifest, planArtifact, new Set(), all)).toBe(false);
    expect(directorShotReviewReady(job, manifest, planArtifact, all, new Set())).toBe(false);
    expect(directorShotReviewReady(job, null, planArtifact, all, all)).toBe(false);
  });

  it("renders the real component set, actual member IDs, narration, image, and shot-linked feedback", () => {
    const markup = renderToStaticMarkup(createElement(DirectorShotReviewGallery, {
      manifest, loadedShotIds: new Set(["shot-1"]), reviewedShotIds: new Set<string>(),
      failedShotIds: new Set<string>(), feedback: {}, locked: false,
      onImageLoad: () => undefined, onImageError: () => undefined,
      onReviewedChange: () => undefined, onFeedbackChange: () => undefined,
    }));
    expect(markup).toContain('src="/api/artifacts/frame-1"');
    expect(markup).toContain("A05");
    expect(markup).toContain("MaterialFocus / TextHighlight");
    expect(markup).toContain("这是这个镜头的真实口播。");
    expect(markup).toContain("shot-1");
    expect(markup).toContain("0.00–3.00 秒");
    expect(markup).toContain("镜头返工意见");
    expect(markup).not.toContain("30 秒 Demo");
  });

  it("keeps feedback attached to its shot and does not truncate the user's text", () => {
    expect(formatShotReviewFeedback("整体方向确认", { "shot-1": "放大窗太小", "shot-2": " " }))
      .toBe("整体方向确认\n\n[镜头 shot-1] 放大窗太小");
    const long = "字".repeat(3001);
    expect(formatShotReviewFeedback(long, {})).toBe(long);
  });

  it("accepts only a current whole-package receipt with every reviewed shot and the exact image manifest", () => {
    const reviewArtifact: Artifact = {
      artifact_id: "review-1", kind: "director_shot_review", name: "review.json",
      mime_type: "application/json", size_bytes: 100, sha256: "review-sha",
      url: "/api/artifacts/review-1", revision: 4,
    };
    const completed = { ...job, status: "DRAFT", pending_input: null,
      artifacts: [...job.artifacts, reviewArtifact] } as Job;
    const receipt = {
      node_name: "director_human_gate", stage: "director", decision: "confirm", revision: 4,
      review_mode: "per_shot_stills", director_shot_review_artifact_id: "review-1",
      reviewed_shot_ids: ["shot-1"], subject: {
        director_shot_review: manifest,
        director_plan: { review_mode: "per_shot_stills", timeline_fingerprint: "timeline-1",
          shot_reviews: manifest.items.map(({ shot_id, review_frame, component_reason, visual_action }) =>
            ({ shot_id, review_frame, component_reason, visual_action })) },
        timeline: completed.timeline, script: completed.script,
      },
    };
    expect(resolveDirectorShotReviewApproval(completed, [receipt], manifest)).toBe("confirmed");
    expect(resolveDirectorShotReviewApproval(completed, [{ ...receipt, reviewed_shot_ids: [] }], manifest)).toBe("blocked");
    expect(resolveDirectorShotReviewApproval(completed, [{ ...receipt, director_shot_review_artifact_id: "old" }], manifest)).toBe("blocked");
    expect(resolveDirectorShotReviewApproval(completed, [{ ...receipt, subject: undefined }], manifest)).toBe("blocked");
    expect(resolveDirectorShotReviewApproval(completed, [receipt, { ...receipt, decision: "revise" }], manifest)).toBe("blocked");
    expect(resolveDirectorShotReviewApproval(completed, [receipt], null)).toBe("blocked");
    const changed = { ...manifest, items: [{ ...manifest.items[0], image: { ...image, sha256: "changed" } }] };
    expect(resolveDirectorShotReviewApproval(completed, [receipt], changed)).toBe("blocked");
    const changedTimeline = { ...completed, timeline: { ...completed.timeline!, shots: [
      { ...completed.timeline!.shots[0], props: { zoom: 2 } },
    ] } };
    expect(resolveDirectorShotReviewApproval(changedTimeline, [receipt], manifest)).toBe("blocked");
  });

  it("shows per-shot review actions for production before any movie exists", () => {
    const markup = renderToStaticMarkup(createElement(RenderPanel, {
      job, locked: false, run: () => undefined, target: null,
    }));
    expect(markup).toContain("生成/更新逐镜审核图");
    expect(markup).toContain("导演逐镜组件与画面审核");
    expect(markup).not.toContain("30秒Demo");
  });
});
