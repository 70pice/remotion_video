import { describe, expect, it } from "vitest";
import type { Timeline } from "../src/api/types";
import {createElement} from "react";
import {renderToStaticMarkup} from "react-dom/server";
import {ShotPropsEditor} from "../src/features/storyboard/ShotPropsEditor";
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

  it("accepts all registered presets but rejects custom preset props and assets", () => {
    const preset = timeline();
    preset.shots[0].component_id = "Snapcn-TextReveal";
    expect(validateTimeline(preset)).toEqual([]);
    preset.shots[0].props = { src: "https://example.test/injected.png" };
    expect(validateTimeline(preset).join(" ")).toContain("不接受自定义参数");
    preset.shots[0].props = {};
    preset.shots[0].asset_src = "videoagents/test/source.png";
    expect(validateTimeline(preset).join(" ")).toContain("不接受额外图片素材");
  });

  it("validates video trim, crop and mp4 source rules", () => {
    const next = timeline();
    Object.assign(next.shots[0], {
      component_id: "video",
      asset_src: "videoagents/test/assets/source.mp4",
      source_label: "official demo",
      props: {
        start_seconds: 1,
        end_seconds: 4,
        fit: "cover",
        crop: { x: 0.1, y: 0.1, width: 0.8, height: 0.8 },
      },
    });
    expect(validateTimeline(next)).toEqual([]);

    next.shots[0].props = { start_seconds: 1, end_seconds: 2 };
    expect(validateTimeline(next).join(" ")).toContain("截取时长不足");
    next.shots[0].props = {
      start_seconds: 0,
      end_seconds: 4,
      crop: { x: 0.8, y: 0, width: 0.3, height: 1 },
    };
    expect(validateTimeline(next).join(" ")).toContain("裁剪框");
    next.shots[0].asset_src = "videoagents/test/assets/source.png";
    expect(validateTimeline(next).join(" ")).toContain("MP4");
  });

  it("validates image_focus crop without requiring it", () => {
    const next = timeline();
    Object.assign(next.shots[0], {
      component_id: "image_focus",
      asset_src: "videoagents/test/assets/source.png",
      props: { focal_x: 0.25, focal_y: 0.75 },
    });
    expect(validateTimeline(next)).toEqual([]);

    next.shots[0].props = {
      crop: { x: 0.2, y: 0.1, width: 0.6, height: 0.7 },
    };
    expect(validateTimeline(next)).toEqual([]);

    next.shots[0].props = {
      crop: { x: 0.8, y: 0, width: 0.3, height: 1 },
    };
    expect(validateTimeline(next).join(" ")).toContain("图片裁剪框");
  });

  it("splits video shots by advancing trim times without mutating the original timeline", () => {
    const original = timeline();
    Object.assign(original.shots[0], {
      component_id: "video",
      asset_src: "videoagents/test/assets/source.mp4",
      source_label: "official demo",
      props: { start_seconds: 10, end_seconds: 13, fit: "contain" },
    });

    const next = splitShot(original, 0);

    expect(original.shots).toHaveLength(1);
    expect(original.shots[0].props).toEqual({
      start_seconds: 10,
      end_seconds: 13,
      fit: "contain",
    });
    expect(next.shots.map((shot) => shot.props)).toEqual([
      { start_seconds: 10, end_seconds: 11.5, fit: "contain" },
      { start_seconds: 11.5, end_seconds: 13, fit: "contain" },
    ]);
    expect(validateTimeline(next)).toEqual([]);
  });

  it("reports clearly when video trim cannot cover a split", () => {
    const original = timeline();
    Object.assign(original.shots[0], {
      component_id: "video",
      asset_src: "videoagents/test/assets/source.mp4",
      source_label: "official demo",
      props: { start_seconds: 10, end_seconds: 11 },
    });

    expect(() => splitShot(original, 0)).toThrow("视频素材截取时长不足");
    expect(original.shots).toHaveLength(1);
  });

  it("accepts semantic cues and flow without changing supplied facts", () => {
    const next = timeline();
    Object.assign(next.shots[0], {component_id: "steps", props: {
      layout: "flow", items: [{title: "提出任务"}, {title: "检查结果", reveal_frame: 75}],
    }});
    const original = structuredClone(next);
    expect(validateTimeline(next)).toEqual([]);
    expect(next).toEqual(original);
  });

  it("rejects bad local reveal cues and out-of-order content", () => {
    for (const cue of [-1, 76, 1.5, true, "10", null]) {
      const next = timeline();
      Object.assign(next.shots[0], {component_id: "comparison", props: {
        left_title: "之前", left_body: "过程", right_title: "之后", right_body: "结果", right_reveal_frame: cue,
      }});
      expect(validateTimeline(next).join(" ")).toContain("出现帧");
      Object.assign(next.shots[0], {component_id: "data", props: {
        items: [{label: "价格", value: "20", reveal_frame: cue}],
      }});
      expect(validateTimeline(next).join(" ")).toContain("出现帧");
    }
    const next = timeline();
    Object.assign(next.shots[0], {component_id: "steps", props: {
      items: [{title: "第一步", reveal_frame: 10}, {title: "第二步"}],
    }});
    expect(validateTimeline(next).join(" ")).toContain("非递减");
    next.shots[0].props = {layout: "horizontal", items: [{title: "第一步"}]};
    expect(validateTimeline(next).join(" ")).toContain("cards 或 flow");
  });

  it("exposes optional local cue and flow controls in the actual props editor", () => {
    const shot = timeline().shots[0];
    Object.assign(shot, {component_id: "steps", props: {
      layout: "flow", items: [{title: "提出任务"}, {title: "检查结果", reveal_frame: 60}],
    }});
    const html = renderToStaticMarkup(createElement(ShotPropsEditor, {shot, disabled: false, update: () => {}}));
    expect(html).toContain("连接流程");
    expect(html).toContain('value="flow" selected');
    expect(html).toMatch(/type="number" min="0" max="75" step="1"[^>]*value="60"/);
    Object.assign(shot, {component_id: "comparison", props: {
      left_title: "之前", left_body: "过程", right_title: "之后", right_body: "结果", right_reveal_frame: 30,
    }});
    expect(renderToStaticMarkup(createElement(ShotPropsEditor, {shot, disabled: false, update: () => {}})))
      .toMatch(/type="number" min="0" max="75" step="1"[^>]*value="30"/);
  });

  it("exposes optional image_focus crop controls in the props editor", () => {
    const shot = timeline().shots[0];
    Object.assign(shot, {component_id: "image_focus", props: {
      focal_x: 0.3, focal_y: 0.7, crop: {x: 0.2, y: 0.1, width: 0.6, height: 0.5},
    }});
    const html = renderToStaticMarkup(createElement(ShotPropsEditor, {shot, disabled: false, update: () => {}}));
    expect(html).toContain("手动裁切图片区域");
    expect(html).toMatch(/type="number" min="0" max="1" step="0.01"[^>]*value="0.3"/);
    expect(html).toMatch(/type="number" min="0" max="1" step="0.01"[^>]*value="0.6"/);
  });

  it("does not silently copy local cues into different shot boundaries on split", () => {
    const next = timeline();
    Object.assign(next.shots[0], {component_id: "steps", props: {
      layout: "flow", items: [{title: "提出任务"}, {title: "检查结果", reveal_frame: 75}],
    }});
    const original = structuredClone(next);
    expect(() => splitShot(next, 0)).toThrow("逐项出现帧");
    expect(next).toEqual(original);
    Object.assign(next.shots[0], {component_id: "comparison", props: {
      left_title: "之前", left_body: "过程", right_title: "之后", right_body: "结果", right_reveal_frame: 30,
    }});
    expect(() => splitShot(next, 0)).toThrow("逐项出现帧");
  });
});
