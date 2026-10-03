import type { Alignment, Script } from "../../api/types";

export interface AlignmentRow {
  id: string;
  segment_id: string;
  text: string;
  start: string;
  end: string;
}

export function createAlignmentRows(script: Script | null): AlignmentRow[] {
  // Splitting text is only a transcription aid. Timing remains blank until verified.
  return (
    script?.segments.flatMap((segment) => {
      const chars = Array.from(segment.narration);
      const rows: AlignmentRow[] = [];
      for (let index = 0; index < chars.length; index += 72)
        rows.push({
          id: crypto.randomUUID(),
          segment_id: segment.segment_id,
          text: chars.slice(index, index + 72).join(""),
          start: "",
          end: "",
        });
      return rows;
    }) ?? []
  );
}

export function buildAlignment(
  rows: AlignmentRow[],
  script: Script | null,
  note: string,
): Alignment {
  if (!script || !rows.length)
    throw new Error("请先保存口播文案，再填写实测时间。");
  const segments = rows.map((row, index) => {
    if (!row.start.trim() || !row.end.trim())
      throw new Error(`第 ${index + 1} 条字幕缺少实际开始或结束时间。`);
    const start = Number(row.start),
      end = Number(row.end);
    if (
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      start < 0 ||
      end <= start
    )
      throw new Error(`第 ${index + 1} 条字幕的时间区间不正确。`);
    if (!row.text || Array.from(row.text).length > 72)
      throw new Error(`第 ${index + 1} 条字幕需为 1–72 个字。`);
    return {
      segment_id: row.segment_id,
      text: row.text,
      start_ms: Math.round(start * 1000),
      end_ms: Math.round(end * 1000),
    };
  });
  for (const segment of script.segments) {
    if (
      segments
        .filter((row) => row.segment_id === segment.segment_id)
        .map((row) => row.text)
        .join("") !== segment.narration
    )
      throw new Error(
        "同一口播段落的字幕拼接必须与已保存文案完全一致。请保留原文的标点和空格。",
      );
  }
  for (let index = 1; index < segments.length; index++)
    if (segments[index].start_ms < segments[index - 1].end_ms)
      throw new Error("字幕时间必须按声音顺序排列，不能重叠。");
  return { origin: "manual", verified: true, segments, note };
}
