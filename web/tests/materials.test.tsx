import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Job, Settings } from "../src/api/types";
import { MaterialsContent, MaterialsPanel, type ResearchPackage } from "../src/features/materials/MaterialsPanel";
import { createSettingsPayload, SettingsForm } from "../src/pages/SettingsPage";

const job: Job = {
  job_id: "materials-test", revision: 1, status: "RUNNING", stage: "materials",
  message: "", progress: null, created_at: "unit", updated_at: "unit", latest_event_id: 1,
  brief: { topic: "Muse是什么", script_text: "", audience: "初学者", platform: "抖音", usage: "commercial",
    target_seconds: 45, width: 1080, height: 1920, fps: 30, source_urls: [] },
  script: null, script_discussion: null, timeline: null, review: null, pending_input: null,
  artifacts: [], assets: [{ asset_id: "real-image", name: "Muse 来源截图", role: "evidence",
    mime_type: "image/png", size_bytes: 2000, sha256: "a".repeat(64), source_url: "https://example.org/muse",
    license_note: "待审查", artifact_id: "image-artifact", url: "/api/artifacts/image-artifact",
    timeline_src: "videoagents/materials-test/assets/real-image.png" }],
};

function renderResearch(research: ResearchPackage) {
  return renderToStaticMarkup(createElement(MaterialsContent, { job, research }));
}

describe("materials research workspace", () => {
  it("shows ambiguity, actual search backends and partial failures without inventing result counts", () => {
    const markup = renderResearch({ query: "Muse是什么", plan: { ambiguities: ["可能指乐队或 AI 产品"], focus_notes: ["先识别含义"] },
      tools: [
        { platform: "zhihu", backend: "opencli_google_indexed", status: "ok", results_count: 2 },
        { platform: "reddit", backend: "search", status: "skipped", error: "search_budget_exhausted" },
        { platform: "x", backend: "search", status: "error", error: "TimeoutError" },
      ] });
    expect(markup).toContain("可能指乐队或 AI 产品");
    expect(markup).toContain("opencli_google_indexed");
    expect(markup).toContain("2 条命中");
    expect(markup).toContain("检索预算已用完");
    expect(markup).toContain("检索失败");
    expect(markup).not.toContain("0 条命中");
  });

  it("previews registered assets and preserves source provenance rather than rendering remote candidates", () => {
    const markup = renderResearch({ visuals: [
      { asset_id: "real-image", kind: "screenshot", source_url: "https://example.org/muse", title: "定义截图", knowledge_excerpt: "原文摘录" },
      { asset_id: "missing", kind: "image", source_url: "https://unregistered.test/image" },
    ], sources: [{ url: "https://example.org/muse", text: "已下载的来源正文", artifact_url: "/api/artifacts/source-artifact" }] });
    expect(markup).toContain('src="/api/artifacts/image-artifact"');
    expect(markup).toContain("查看素材出处");
    expect(markup).toContain("原文摘录");
    expect(markup).toContain("再利用许可待审核");
    expect(markup).toContain("下载来源快照");
    expect(markup).not.toContain("https://unregistered.test/image");
  });

  it("ignores an old revision research artifact", () => {
    const old = { ...job, artifacts: [{ artifact_id: "old", name: "research.json", kind: "research", revision: 0,
      mime_type: "application/json", sha256: "b".repeat(64), size_bytes: 100, url: "/api/artifacts/old" }] };
    const markup = renderToStaticMarkup(createElement(MaterialsPanel, { job: old }));
    expect(markup).toContain("还没有素材研究包");
    expect(markup).not.toContain('href="/api/artifacts/old"');
  });

  it("saves free Google discovery and bounded platform selection without submitting catalog data or blank secrets", () => {
    const values: Settings = { search_provider: "opencli_google", search_api_key: "", research_platforms: ["x", "youtube", "reddit"],
      research_max_searches: 8, research_max_visuals: 0, capture_enabled: true, research_download_images: true,
      research_tools: [{ id: "x", label: "X / Twitter", status: "search_ready", detail: "公开索引检索" }] };
    const patch = createSettingsPayload(values, {});
    expect(patch).toEqual({ search_provider: "opencli_google", research_platforms: ["x", "youtube", "reddit"],
      research_max_searches: 8, research_max_visuals: 0, capture_enabled: true, research_download_images: true });
    const markup = renderToStaticMarkup(createElement(SettingsForm, { saved: values, values, busy: false,
      onChange: () => undefined, onSubmit: () => undefined }));
    expect(markup).toContain("无需搜索 API Key");
    expect(markup).toContain("公开索引检索");
    expect(markup).toContain("X / Twitter");
    expect(markup).toContain('aria-label="图片/截图采集尝试上限"');
  });
});
