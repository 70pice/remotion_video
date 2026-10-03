import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { Job, ScriptDiscussion } from "../src/api/types";
import { ScriptDiscussionPanel } from "../src/features/script/ScriptDiscussionPanel";

const baseJob: Job = {
  job_id: "job-script-discussion",
  revision: 7,
  status: "RUNNING",
  stage: "script",
  message: "",
  progress: null,
  created_at: "2026-10-03T00:00:00Z",
  updated_at: "2026-10-03T00:00:00Z",
  brief: {
    topic: "酒店短视频",
    script_text: "",
    audience: "住客",
    platform: "抖音",
    usage: "commercial",
    target_seconds: 45,
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
  pending_input: null,
  latest_event_id: 1,
};

function discussion(
  overrides: Partial<ScriptDiscussion> = {},
): ScriptDiscussion {
  return {
    run_id: "run-discussion-1",
    revision: 7,
    enabled: true,
    max_rounds: 2,
    status: "DISCUSSING",
    rounds: [
      {
        round: 1,
        response: "",
        script: {
          title: "第一稿",
          origin: "model",
          revision: 7,
          segments: [
            {
              segment_id: "s1",
              narration: "开头先给一个真实冲突。",
              screen_text: "真实冲突",
              source_refs: ["https://example.test/source"],
              asset_ids: ["asset-1"],
            },
          ],
        },
        critique: {
          decision: "REVISE",
          summary: "钩子清楚，但事实来源还要更具体。",
          strengths: ["有明确痛点"],
          issues: [
            {
              segment_id: "s1",
              category: "hook",
              concern: "房价对比缺少来源。",
              suggestion: "补充截图或公开来源链接。",
            },
          ],
        },
      },
      {
        round: 2,
        response: "已补充来源，并把口播改短。",
        script: {
          title: "第二稿",
          origin: "model",
          revision: 7,
          segments: [
            {
              segment_id: "s1",
              narration: "这次用一张截图说明为什么要提前订。",
              screen_text: "提前订更稳",
              source_refs: ["https://example.test/source"],
              asset_ids: ["asset-1"],
            },
          ],
        },
        critique: {
          decision: "APPROVE",
          summary: "事实和画面证据已经对应。",
          strengths: ["来源清楚", "画面能承接口播"],
          issues: [],
        },
      },
    ],
    ...overrides,
  };
}

function render(job: Job): string {
  return renderToStaticMarkup(createElement(ScriptDiscussionPanel, { job }));
}

describe("ScriptDiscussionPanel", () => {
  it("renders multiple rounds with critique issues, responses, and full scripts", () => {
    const markup = render({
      ...baseJob,
      script_discussion: discussion({ status: "APPROVED" }),
    });

    expect(markup).toContain("文案讨论");
    expect(markup).toContain("第 1 轮");
    expect(markup).toContain("第 2 轮");
    expect(markup).toContain("审查建议：修改");
    expect(markup).toContain("审查建议：通过");
    expect(markup).toContain("开头吸引力");
    expect(markup).toContain("房价对比缺少来源");
    expect(markup).toContain("补充截图或公开来源链接");
    expect(markup).toContain("已补充来源，并把口播改短");
    expect(markup).toContain("查看本轮完整稿件");
    expect(markup).toContain("标题：第二稿");
    expect(markup).toContain("来源：https://example.test/source");
    expect(markup).toContain("素材：asset-1");
    expect(markup).toContain("这次用一张截图说明为什么要提前订");
    expect(markup).toContain("后续仍需来源与素材检查");
    expect(markup).not.toContain("run-discussion-1");
    expect(markup).not.toContain("运行 ID");
    expect(markup).not.toContain("READY_FOR_PUBLISH");
  });

  it("shows running and exhausted states without granting publish readiness", () => {
    const running = render({
      ...baseJob,
      script_discussion: discussion({
        status: "DISCUSSING",
        max_rounds: 3,
        rounds: [
          ...discussion().rounds,
          {
            round: 3,
            response: "按第二轮意见又补了一版，等待审查。",
            script: {
              title: "第三稿",
              origin: "model",
              revision: 7,
              segments: [
                {
                  segment_id: "s1",
                  narration: "先看这张来源截图，再决定要不要提前订。",
                  screen_text: "先看来源",
                  source_refs: ["https://example.test/source"],
                  asset_ids: ["asset-1"],
                },
              ],
            },
            critique: null,
          },
        ],
      }),
    });
    expect(running).toContain("文案讨论正在进行");
    expect(running).toContain("已完成 2 轮审查");
    expect(running).toContain("剩余 1 轮审查额度");
    expect(running).toContain("稿件轮数：3");
    expect(running).toContain("等待审查");

    const exhausted = render({
      ...baseJob,
      script_discussion: discussion({ status: "EXHAUSTED" }),
    });
    expect(exhausted).toContain("达到 2 轮上限");
    expect(exhausted).toContain("流程会等待补充或人工处理");
    expect(exhausted).not.toContain("审核通过");
  });

  it("marks stale discussion records as historical instead of current approval", () => {
    const markup = render({
      ...baseJob,
      revision: 8,
      script_discussion: discussion({ status: "APPROVED", revision: 7 }),
    });

    expect(markup).toContain("历史第 7 版");
    expect(markup).toContain("当前任务是第 8 版");
    expect(markup).toContain("不把历史通过状态当作当前文案通过");
    expect(markup).not.toContain(">文案讨论通过</span>");
  });

  it("escapes script and critique text from model output", () => {
    const markup = render({
      ...baseJob,
      script_discussion: discussion({
        rounds: [
          {
            round: 1,
            response: "<img src=x onerror=alert(1)>",
            script: {
              title: "<script>alert(1)</script>",
              origin: "model",
              revision: 7,
              segments: [
                {
                  segment_id: "s1",
                  narration: "<script>alert('xss')</script>",
                  screen_text: "<b>不要执行</b>",
                  source_refs: [],
                  asset_ids: [],
                },
              ],
            },
            critique: {
              decision: "REVISE",
              summary: "<svg onload=alert(1)>",
              strengths: ["<strong>escaped</strong>"],
              issues: [
                {
                  segment_id: "",
                  category: "clarity",
                  concern: "<iframe src=bad></iframe>",
                  suggestion: "<a href=javascript:alert(1)>bad</a>",
                },
              ],
            },
          },
        ],
      }),
    });

    expect(markup).toContain("&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;");
    expect(markup).toContain("&lt;img src=x onerror=alert(1)&gt;");
    expect(markup).toContain("&lt;iframe src=bad&gt;&lt;/iframe&gt;");
    expect(markup).not.toContain("<script>alert");
    expect(markup).not.toContain("<iframe src=bad>");
    expect(markup).not.toContain("dangerouslySetInnerHTML");
  });
});
