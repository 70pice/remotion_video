import { describe, expect, it } from "vitest";
import type { Brief } from "../src/api/types";
import { finishBriefSave } from "../src/api/draftState";

const brief: Brief = {
  topic: "测试",
  creative_direction: "",
  script_text: "",
  audience: "普通观众",
  platform: "通用竖屏",
  usage: "personal",
  target_seconds: 60,
  width: 1080,
  height: 1920,
  fps: 30,
  source_urls: [],
};

describe("brief save response", () => {
  it("clears the unchanged submitted draft after acknowledgement", () => {
    expect(finishBriefSave(brief, brief)).toBeNull();
  });
  it("preserves edits made while an earlier snapshot was being saved", () => {
    const submitted = { ...brief };
    const newerDraft = { ...submitted, audience: "新观众", target_seconds: 90 };
    const afterResponse = finishBriefSave(newerDraft, submitted);
    expect(afterResponse).toBe(newerDraft);
    expect(afterResponse?.audience).toBe("新观众");
    expect(afterResponse?.target_seconds).toBe(90);
  });
});
