import { describe, expect, it } from "vitest";
import type { Script } from "../src/api/types";
import {
  buildAlignment,
  createAlignmentRows,
} from "../src/features/voice/alignment";

const script: Script = {
  title: "实测字幕",
  origin: "user",
  revision: 1,
  segments: [
    {
      segment_id: "s1",
      narration: "这是测试。",
      screen_text: "",
      source_refs: [],
      asset_ids: [],
    },
  ],
};

describe("manual audio alignment", () => {
  it("leaves timing blank when populating transcript text", () => {
    const rows = createAlignmentRows(script);
    expect(rows[0].text).toBe("这是测试。");
    expect(rows[0].start).toBe("");
    expect(rows[0].end).toBe("");
    expect(() => buildAlignment(rows, script, "")).toThrow("缺少实际");
  });
  it("supports measured split captions from one segment", () => {
    const result = buildAlignment(
      [
        { id: "a", segment_id: "s1", text: "这是", start: "0.125", end: "0.8" },
        { id: "b", segment_id: "s1", text: "测试。", start: "1", end: "1.725" },
      ],
      script,
      "逐句核对",
    );
    expect(
      result.segments.map((segment) => [segment.start_ms, segment.end_ms]),
    ).toEqual([
      [125, 800],
      [1000, 1725],
    ]);
    expect(result.origin).toBe("manual");
    expect(result.verified).toBe(true);
  });
  it("rejects altered transcription and overlapping times", () => {
    expect(() =>
      buildAlignment(
        [{ id: "a", segment_id: "s1", text: "改变文本", start: "0", end: "1" }],
        script,
        "",
      ),
    ).toThrow("完全一致");
    expect(() =>
      buildAlignment(
        [
          { id: "a", segment_id: "s1", text: "这是", start: "0", end: "1" },
          { id: "b", segment_id: "s1", text: "测试。", start: ".5", end: "2" },
        ],
        script,
        "",
      ),
    ).toThrow("不能重叠");
  });
});
