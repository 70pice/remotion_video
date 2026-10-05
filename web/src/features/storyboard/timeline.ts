import type { Shot, Timeline } from "../../api/types";
import componentManifest from "../../../../videoagents/component-manifest.json";

export const componentNames: Record<string, string> = {
  ...Object.fromEntries(
    componentManifest.entries.map((entry) => [entry.component_id, entry.name]),
  ),
  video: "真实视频",
};
const communityComponentIds = new Set(
  componentManifest.entries
    .filter((entry) => entry.kind === "preset")
    .map((entry) => entry.component_id),
);

export const isCommunityComponent = (componentId: string) =>
  communityComponentIds.has(componentId);

export function defaultProps(component: string): Record<string, unknown> {
  if (component === "video") return { start_seconds: 0, fit: "contain" };
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
  if (shot.props.right_reveal_frame !== undefined ||
      (Array.isArray(shot.props.items) && shot.props.items.some((item) =>
        item && typeof item === "object" && "reveal_frame" in item)))
    throw new Error("镜头含按口播设置的逐项出现帧，请先调整或清除出现帧再拆分，避免改变音画对应时刻。");
  const middle = Math.floor((shot.start_frame + shot.end_frame) / 2);
  const first = { ...shot, props: structuredClone(shot.props) };
  const second = {
    ...structuredClone(shot),
    shot_id: crypto.randomUUID(),
    start_frame: middle,
  };
  if (shot.component_id === "video") {
    const props = shot.props;
    const startSeconds = numberProp(props.start_seconds, 0);
    const endSeconds =
      props.end_seconds === undefined ? undefined : numberProp(props.end_seconds);
    const firstSeconds = (middle - shot.start_frame) / timeline.fps;
    const fullSeconds = (shot.end_frame - shot.start_frame) / timeline.fps;
    if (startSeconds === null || endSeconds === null)
      throw new Error("视频镜头的起止秒数必须是有限数字。");
    if (endSeconds !== undefined && endSeconds - startSeconds + 0.001 < fullSeconds)
      throw new Error("视频素材截取时长不足，无法拆分镜头。");
    const splitSeconds = roundSeconds(startSeconds + firstSeconds);
    first.props = { ...first.props, start_seconds: startSeconds, end_seconds: splitSeconds };
    second.props = { ...second.props, start_seconds: splitSeconds };
    if (endSeconds !== undefined) second.props.end_seconds = endSeconds;
  }
  first.end_frame = middle;
  return {
    ...timeline,
    shots: [
      ...timeline.shots.slice(0, index),
      first,
      second,
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
    if (shot.asset_src && shot.component_id !== "video" && !/\.(png|jpe?g|webp)$/i.test(shot.asset_src))
      errors.push(`${label}图片素材必须是 PNG、JPEG 或 WebP。`);
    if (
      ["evidence", "image_focus"].includes(shot.component_id) &&
      !shot.asset_src
    )
      errors.push(`${label}需要选择真实图片。`);
    if (shot.component_id === "evidence" && !shot.source_label.trim())
      errors.push(`${label}证据截图需填写来源说明。`);
    validateProps(shot, label, errors, timeline.fps);
  });
  if (expectedStart !== timeline.duration_in_frames)
    errors.push(`最后一个镜头应结束于第 ${timeline.duration_in_frames} 帧。`);
  return errors;
}

function validateProps(shot: Shot, label: string, errors: string[], fps: number) {
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
  const cue = (value: unknown) => {
    if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0 || value > shot.end_frame - shot.start_frame - 15)
      errors.push(`${label}的出现帧必须是 0 到镜头时长减 15 的整数。`);
  };
  if (shot.component_id === "comparison") {
    for (const key of ["left_title", "right_title"])
      if (!text(props[key], 48, true))
        errors.push(`${label}需填写两侧标题（最多 48 字）。`);
    for (const key of ["left_body", "right_body"])
      if (!text(props[key], 160, true))
        errors.push(`${label}需填写两侧对比内容（最多 160 字）。`);
    if (props.right_reveal_frame !== undefined) cue(props.right_reveal_frame);
  }
  if (shot.component_id === "video") {
    if (!shot.asset_src) errors.push(`${label}需要选择真实视频。`);
    else if (!/\.mp4$/i.test(shot.asset_src))
      errors.push(`${label}视频素材必须是 MP4。`);
    if (!shot.source_label.trim()) errors.push(`${label}视频素材需填写来源说明。`);
    const startSeconds = numberProp(props.start_seconds, 0);
    const endSeconds =
      props.end_seconds === undefined ? undefined : numberProp(props.end_seconds);
    if (startSeconds === null || startSeconds < 0)
      errors.push(`${label}视频起始秒数必须是非负有限数字。`);
    if (endSeconds === null || (endSeconds !== undefined && startSeconds !== null && endSeconds <= startSeconds))
      errors.push(`${label}视频结束秒数必须晚于起始秒数。`);
    if (startSeconds !== null && endSeconds !== undefined && endSeconds !== null) {
      const shotSeconds = (shot.end_frame - shot.start_frame) / fps;
      if (endSeconds - startSeconds + 0.001 < shotSeconds)
        errors.push(`${label}视频截取时长不足以覆盖镜头。`);
    }
    if (props.fit !== undefined && props.fit !== "contain" && props.fit !== "cover")
      errors.push(`${label}视频填充方式只能是 contain 或 cover。`);
    if (props.crop !== undefined && !validRect(props.crop))
      errors.push(`${label}视频裁剪框必须在画面内部且面积非零。`);
  }
  if (shot.component_id === "image_focus") {
    for (const key of ["focal_x", "focal_y"]) {
      const value = props[key];
      if (value !== undefined && (typeof value !== "number" || !Number.isFinite(value) || value < 0 || value > 1))
        errors.push(`${label}图片焦点必须在 0 到 1 之间。`);
    }
    if (props.crop !== undefined && !validRect(props.crop))
      errors.push(`${label}图片裁剪框必须在画面内部且面积非零。`);
  }
  if (["data", "steps"].includes(shot.component_id)) {
    if (shot.component_id === "steps" && props.layout !== undefined && props.layout !== "cards" && props.layout !== "flow")
      errors.push(`${label}的步骤布局只能是 cards 或 flow。`);
    const items = props.items;
    if (!Array.isArray(items) || items.length < 1 || items.length > 4) {
      errors.push(`${label}需有 1–4 个内容项。`);
      return;
    }
    let previousCue = 0;
    for (const item of items as Record<string, unknown>[]) {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        errors.push(`${label}的内容项未填完整。`);
        continue;
      }
      const valid =
        shot.component_id === "data"
          ? text(item.label, 48, true) &&
            text(item.value, 40, true) &&
            (item.detail === undefined || text(item.detail, 64))
          : text(item.title, 48, true) &&
            (item.body === undefined || text(item.body, 96));
      if (!valid) errors.push(`${label}的内容项未填完整或文字过长。`);
      if (item.reveal_frame !== undefined) cue(item.reveal_frame);
      const localCue = item.reveal_frame ?? 0;
      if (typeof localCue === "number" && localCue < previousCue)
        errors.push(`${label}的出现帧需按顺序非递减；未设置时按 0 计算。`);
      if (typeof localCue === "number") previousCue = localCue;
    }
  }
}

function numberProp(value: unknown, fallback: number): number | null;
function numberProp(value: unknown): number | null | undefined;
function numberProp(value: unknown, fallback?: number): number | null | undefined {
  if (value === undefined) return fallback;
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function validRect(value: unknown) {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const rect = value as Record<string, unknown>;
  const keys = ["x", "y", "width", "height"] as const;
  if (
    Object.keys(rect).length !== keys.length ||
    !keys.every((key) => typeof rect[key] === "number" && Number.isFinite(rect[key]))
  )
    return false;
  const x = rect.x as number;
  const y = rect.y as number;
  const width = rect.width as number;
  const height = rect.height as number;
  return (
    x >= 0 &&
    y >= 0 &&
    width > 0 &&
    height > 0 &&
    x + width <= 1 &&
    y + height <= 1
  );
}

function roundSeconds(value: number) {
  return Math.round(value * 1000) / 1000;
}
