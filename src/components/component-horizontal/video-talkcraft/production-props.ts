export type TalkcraftShotLike = {
  title?: string;
  body?: string;
  source_label?: string;
  accent_color?: string;
  props?: Record<string, unknown> | null;
};

export type TalkcraftTitleCopy = {
  title: string;
  body: string;
  source: string;
  accent: string;
  keyword: string;
  lines: string[];
  items: string[];
};

const DEFAULT_ACCENT = '#FF6B6B';

const clean = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
};

const splitText = (value: string): string[] => value
  .split(/[\n｜|。；;]/)
  .map((part) => part.trim())
  .filter(Boolean);

export const talkcraftStrings = (value: unknown): string[] => Array.isArray(value)
  ? value.map(clean).filter((item): item is string => typeof item === 'string' && item.length <= 64)
  : [];

export const resolveTalkcraftTitleCopy = (shot: TalkcraftShotLike): TalkcraftTitleCopy => {
  const props = shot.props ?? {};
  const title = clean(props.title) ?? clean(shot.title) ?? '';
  const body = clean(props.body) ?? clean(shot.body) ?? '';
  const source = clean(props.source_label) ?? clean(shot.source_label) ?? '';
  const accent = clean(props.accent_color) ?? clean(shot.accent_color) ?? DEFAULT_ACCENT;
  const items = talkcraftStrings(props.items);
  const explicitLines = talkcraftStrings(props.lines);
  const lines = (explicitLines.length ? explicitLines : [...splitText(title), ...splitText(body)]).slice(0, 6);
  const keyword = clean(props.highlight) ?? clean(props.keyword) ?? items[0] ?? lines.find((line) => line.length <= 12) ?? title;
  return {title, body, source, accent, keyword, lines, items};
};

export const takeTalkcraftLines = (copy: TalkcraftTitleCopy, count: number): string[] => {
  const seen = new Set<string>();
  const ordered = [...copy.lines, ...copy.items, copy.title, copy.body].filter(Boolean);
  return ordered.filter((line) => {
    if (seen.has(line)) return false;
    seen.add(line);
    return true;
  }).slice(0, count);
};
