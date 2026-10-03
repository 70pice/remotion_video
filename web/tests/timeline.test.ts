import { describe, expect, it } from "vitest";
import type { Timeline } from "../src/api/types";
import {
  removeShot,
  splitShot,
  validateTimeline,
} from "../src/features/storyboard/timeline";

function timeline(): Timeline {
  return {
    schema_version: "1",
    job_id: "test",
    revision: 1,
    width: 1080,
    height: 1920,
    fps: 30,
    duration_in_frames: 90,
    audio_src: "videoagents/test/audio.wav",
    captions: [],
    shots: [
      {
        shot_id: "one",
        start_frame: 0,
        end_frame: 90,
        component_id: "title",
        title: "测试镜头",
        body: "",
        asset_src: null,
        source_label: "",
        accent_color: "#3769ef",
        props: {},
      },
    ],
  };
}

describe("editable timeline boundaries", () => {
  it("splits a shot without changing the full coverage or mutating the saved timeline", () => {
    const original = timeline();
    const next = splitShot(original, 0);
    expect(
      next.shots.map((shot) => [shot.start_frame, shot.end_frame]),
    ).toEqual([
      [0, 45],
      [45, 90],
    ]);
    expect(next.shots[0].shot_id).not.toBe(next.shots[1].shot_id);
    expect(original.shots).toHaveLength(1);
    expect(validateTimeline(next)).toEqual([]);
  });

  it("merges a deleted shot duration into a neighbor without gaps", () => {
    const next = removeShot(splitShot(timeline(), 0), 0);
    expect(
      next.shots.map((shot) => [shot.start_frame, shot.end_frame]),
    ).toEqual([[0, 90]]);
    expect(validateTimeline(next)).toEqual([]);
    expect(() => removeShot(next, 0)).toThrow("至少保留");
  });

  it("rejects overlaps, empty evidence and missing comparison facts", () => {
    const next = splitShot(timeline(), 0);
    next.shots[1].start_frame = 40;
    next.shots[0].component_id = "evidence";
    next.shots[1].component_id = "comparison";
    const errors = validateTimeline(next).join(" ");
    expect(errors).toContain("不能重叠或留空");
    expect(errors).toContain("需要选择真实图片");
    expect(errors).toContain("来源说明");
    expect(errors).toContain("两侧对比内容");
  });
});
