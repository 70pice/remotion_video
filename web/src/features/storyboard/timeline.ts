import type { Shot, Timeline } from "../../api/types";
import componentManifest from "../../../../videoagents/component-manifest.json";

export const componentNames: Record<string, string> = Object.fromEntries(
  componentManifest.entries.map((entry) => [entry.component_id, entry.name]),
);
const communityComponentIds = new Set(
  componentManifest.entries
    .filter((entry) => entry.kind === "preset")
    .map((entry) => entry.component_id),
);

export const isCommunityComponent = (componentId: string) =>
  communityComponentIds.has(componentId);

export function defaultProps(component: string): Record<string, unknown> {
  if (component === "comparison")
    return { left_title: "", right_title: "", left_body: "", right_body: "" };
  if (component === "data")
    return { items: [{ label: "", value: "", detail: "" }] };
  if (component === "steps") return { items: [{ title: "", body: "" }] };
  return {};
}

export function splitShot(timeline: Timeline, index: number): Timeline {
  const shot = timeline.shots[index];
  if (shot.end_frame - shot.start_frame < 2)
    throw new Error("镜头至少需要两帧才能拆分。");
  const middle = Math.floor((shot.start_frame + shot.end_frame) / 2);
  return {
    ...timeline,
    shots: [
      ...timeline.shots.slice(0, index),
      { ...shot, end_frame: middle },
      {
        ...structuredClone(shot),
        shot_id: crypto.randomUUID(),
        start_frame: middle,
      },
      ...timeline.shots.slice(index + 1),
    ],
  };
}

export function removeShot(timeline: Timeline, index: number): Timeline {
  if (timeline.shots.length === 1) throw new Error("至少保留一个镜头。");
  const shots = timeline.shots.map((shot) => ({ ...shot }));
  const deleted = shots.splice(index, 1)[0];
  if (index > 0) shots[index - 1].end_frame = deleted.end_frame;
  else shots[0].start_frame = 0;
  return { ...timeline, shots };
}

export function validateTimeline(timeline: Timeline): string[] {
  const errors: string[] = [];
  let expectedStart = 0;
  const ids = new Set<string>();
  if (!timeline.shots.length) errors.push("至少需要一个镜头。");
  timeline.shots.forEach((shot, index) => {
    const label = `镜头 ${index + 1}`;
    if (ids.has(shot.shot_id)) errors.push(`${label}的编号重复。`);
    ids.add(shot.shot_id);
    if (
      !Number.isInteger(shot.start_frame) ||
      !Number.isInteger(shot.end_frame) ||
      shot.end_frame <= shot.start_frame
    )
      errors.push(`${label}需填写有效的整数帧区间。`);
    if (shot.start_frame !== expectedStart)
      errors.push(
        `${label}应从第 ${expectedStart} 帧开始，镜头不能重叠或留空。`,
      );
    expectedStart = shot.end_frame;
    if (!shot.title.trim() || Array.from(shot.title).length > 100)
      errors.push(`${label}标题需为 1–100 个字。`);
    if (
      Array.from(shot.body).length > 240 ||
      Array.from(shot.source_label).length > 160
    )
      errors.push(`${label}画面文字过长，请压缩内容。`);
    if (!/^#[0-9a-f]{6}$/i.test(shot.accent_color))
      errors.push(`${label}主题色格式不正确。`);
    if (!(shot.component_id in componentNames))
      errors.push(`${label}未选择生产可用组件。`);
    if (
      ["evidence", "image_focus"].includes(shot.component_id) &&
      !shot.asset_src
    )
      errors.push(`${label}需要选择真实图片。`);
    if (shot.component_id === "evidence" && !shot.source_label.trim())
      errors.push(`${label}证据截图需填写来源说明。`);
    validateProps(shot, label, errors);
  });
  if (expectedStart !== timeline.duration_in_frames)
    errors.push(`最后一个镜头应结束于第 ${timeline.duration_in_frames} 帧。`);
  return errors;
}

function validateProps(shot: Shot, label: string, errors: string[]) {
  const props = shot.props;
  if (isCommunityComponent(shot.component_id)) {
    if (Object.keys(props).length)
      errors.push(`${label}的社区预设不接受自定义参数。`);
    if (shot.asset_src)
      errors.push(`${label}的社区预设不接受额外图片素材。`);
    return;
  }
  const text = (value: unknown, max: number, required = false) =>
    typeof value === "string" &&
    Array.from(value).length <= max &&
    (!required || value.trim().length > 0);
  if (shot.component_id === "comparison") {
    for (const key of ["left_title", "right_title"])
      if (!text(props[key], 48, true))
        errors.push(`${label}需填写两侧标题（最多 48 字）。`);
    for (const key of ["left_body", "right_body"])
      if (!text(props[key], 160, true))
        errors.push(`${label}需填写两侧对比内容（最多 160 字）。`);
  }
  if (["data", "steps"].includes(shot.component_id)) {
    const items = props.items;
    if (!Array.isArray(items) || items.length < 1 || items.length > 4) {
      errors.push(`${label}需有 1–4 个内容项。`);
      return;
    }
    for (const item of items as Record<string, unknown>[]) {
      const valid =
        shot.component_id === "data"
          ? text(item.label, 48, true) &&
            text(item.value, 40, true) &&
            (item.detail === undefined || text(item.detail, 64))
          : text(item.title, 48, true) &&
            (item.body === undefined || text(item.body, 96));
      if (!valid) errors.push(`${label}的内容项未填完整或文字过长。`);
    }
  }
}
