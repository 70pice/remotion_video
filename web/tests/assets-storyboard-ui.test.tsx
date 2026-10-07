import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Job } from "../src/api/types";
import { AssetsPanel } from "../src/features/assets/AssetsPanel";
import { CreateJobPage } from "../src/pages/CreateJobPage";

const job: Job = {
  job_id: "ui-video-test",
  revision: 1,
  status: "DRAFT",
  stage: "idle",
  message: "",
  progress: null,
  created_at: "unit",
  updated_at: "unit",
  latest_event_id: 1,
  brief: {
    topic: "Muse是什么",
    creative_direction: "",
    script_text: "",
    audience: "普通观众",
    platform: "抖音",
    usage: "personal",
    target_seconds: 60,
    width: 1080,
    height: 1920,
    fps: 30,
    source_urls: [],
  },
  script: null,
  script_discussion: null,
  timeline: null,
  assets: [
    {
      asset_id: "video-asset",
      name: "official-demo.mp4",
      role: "evidence",
      mime_type: "video/mp4",
      size_bytes: 1024,
      sha256: "a".repeat(64),
      source_url: "https://example.com/demo",
      license_note: "unit",
      artifact_id: "video-artifact",
      url: "/api/artifacts/video-artifact",
      timeline_src: "videoagents/ui-video-test/assets/official-demo.mp4",
    },
  ],
  artifacts: [],
  review: null,
  pending_input: null,
};

describe("asset and fixed-format UI", () => {
  it("renders mp4 assets with a real video element instead of an image tag", () => {
    const markup = renderToStaticMarkup(
      createElement(AssetsPanel, {
        job,
        locked: false,
        refresh: async () => undefined,
      }),
    );

    expect(markup).toContain("<video");
    expect(markup).toContain('src="/api/artifacts/video-artifact"');
    expect(markup).not.toContain('<img src="/api/artifacts/video-artifact"');
    expect(markup).toContain("下载素材");
  });

  it("shows the fixed Douyin portrait format on new jobs", () => {
    const markup = renderToStaticMarkup(createElement(CreateJobPage));

    expect(markup).toContain("抖音竖屏 · 1080 × 1920 · 30 fps");
    expect(markup).toContain("本期创作方向");
    expect(markup).not.toContain("已有口播文案");
    expect(markup).not.toContain("通用横屏");
    expect(markup).not.toContain("16:9");
    expect(markup).not.toContain(">帧率<");
  });
});
