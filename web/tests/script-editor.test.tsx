import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Job } from "../src/api/types";
import { ScriptEditor } from "../src/features/script/ScriptEditor";

const job: Job = {
  job_id: "script-editor-test",
  revision: 3,
  status: "DRAFT",
  stage: "script",
  message: "",
  progress: null,
  created_at: "unit",
  updated_at: "unit",
  latest_event_id: 1,
  brief: {
    topic: "AI应用怎么选",
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
  script: {
    title: "AI应用怎么选",
    title_hook: "先看场景",
    opening_visual: "展示一个人在多个AI应用之间犹豫。",
    final_answer: "先看你要解决哪件事，再选择工具。",
    origin: "model",
    revision: 3,
    segments: [
      {
        segment_id: "s1",
        narration: "先别急着看榜单，先想清楚你要解决哪件事。",
        screen_text: "先看任务",
        source_refs: [],
        asset_ids: [],
      },
    ],
  },
  script_discussion: null,
  timeline: null,
  assets: [],
  artifacts: [],
  review: null,
  pending_input: null,
};

describe("ScriptEditor", () => {
  it("renders script creative fields as editable review context outside narration", () => {
    const markup = renderToStaticMarkup(
      createElement(ScriptEditor, {
        job,
        locked: false,
        onUpdate: () => undefined,
        onDirty: () => undefined,
      }),
    );

    expect(markup).toContain("前3秒画面字");
    expect(markup).toContain('maxLength="15"');
    expect(markup).toContain('value="先看场景"');
    expect(markup).toContain("开头画面建议");
    expect(markup).toContain("一句主答案");
    expect(markup).toContain("创作信息，用来审开头屏幕字，不会当成口播。");
    expect(markup).toContain("先别急着看榜单");
    expect(markup).not.toContain("title_hook");
    expect(markup).not.toContain("opening_visual");
    expect(markup).not.toContain("final_answer");
  });
});
