
import type {TimelineCaption} from './types';

export type CaptionPage = {text: string; start_ms: number; end_ms: number};
export type CaptionBoundary = {start_ms: number; end_ms: number};
type CaptionOptions = {
  boundaries?: CaptionBoundary[];
  maxChars?: number;
  maxDurationMs?: number;
  minDurationMs?: number;
  maxGapMs?: number;
};

const defaultOptions = Object.freeze({
  maxChars: 20,
  maxDurationMs: 2600,
  minDurationMs: 650,
  maxGapMs: 360,
});

const textLength = (text: string) => [...String(text ?? '').replace(/\s+/g, '')].length;
const isPunctuationOnly = (text: string) => /^[\s，。！？、；：,.!?;:…—-]+$/u.test(text);
const endsWithBoundaryPunctuation = (text: string) => /[。！？!?；;：:]\s*$/u.test(text);
const endsWithSoftPunctuation = (text: string) => /[，,、]\s*$/u.test(text);
const isDenseCaption = (caption: CaptionPage) => {
  const length = textLength(caption.text);
  const duration = caption.end_ms - caption.start_ms;
  return length <= 6 && duration <= 520;
};

const findBoundaryIndex = (boundaries: CaptionBoundary[], start: number, end: number) => {
  if (!boundaries?.length) return -1;
  return boundaries.findIndex((boundary) => start >= boundary.start_ms - 0.001 && end <= boundary.end_ms + 0.001);
};

const sameBoundary = (boundaries: CaptionBoundary[], startA: number, endA: number, startB: number, endB: number) => {
  const first = findBoundaryIndex(boundaries, startA, endA);
  const second = findBoundaryIndex(boundaries, startB, endB);
  return first === second;
};

const copyCaption = (caption: TimelineCaption): CaptionPage => ({text: caption.text, start_ms: caption.start_ms, end_ms: caption.end_ms});

export const buildCaptionPages = (captions: TimelineCaption[], rawOptions: CaptionOptions = {}): CaptionPage[] => {
  const options = {...defaultOptions, ...rawOptions};
  const boundaries = rawOptions.boundaries ?? [];
  if (!Array.isArray(captions) || captions.length === 0) return [];
  const pages: CaptionPage[] = [];
  let group: CaptionPage[] = [];

  const groupText = (items: CaptionPage[]) => items.map((item) => item.text).join('');
  const flush = () => {
    if (!group.length) return;
    const page = {text: groupText(group), start_ms: group[0].start_ms, end_ms: group[group.length - 1].end_ms};
    group = [];
    const previous = pages[pages.length - 1];
    const gap = previous ? page.start_ms - previous.end_ms : Number.POSITIVE_INFINITY;
    if (
      previous &&
      (isPunctuationOnly(page.text) || page.end_ms - page.start_ms < options.minDurationMs) &&
      gap <= options.maxGapMs &&
      textLength(previous.text + page.text) <= options.maxChars &&
      previous.end_ms - previous.start_ms + gap + page.end_ms - page.start_ms <= options.maxDurationMs &&
      sameBoundary(boundaries, previous.start_ms, previous.end_ms, page.start_ms, page.end_ms)
    ) {
      previous.text += page.text;
      previous.end_ms = page.end_ms;
      return;
    }
    pages.push(page);
  };

  for (const raw of captions) {
    const caption = copyCaption(raw);
    if (!isDenseCaption(caption) && !isPunctuationOnly(caption.text)) {
      flush();
      pages.push(caption);
      continue;
    }
    if (group.length) {
      const first = group[0];
      const previous = group[group.length - 1];
      const candidateText = groupText(group) + caption.text;
      const gap = caption.start_ms - previous.end_ms;
      const crossesGap = gap > options.maxGapMs;
      const crossesBoundary = !sameBoundary(boundaries, first.start_ms, previous.end_ms, caption.start_ms, caption.end_ms);
      const tooLong = textLength(candidateText) > options.maxChars;
      const tooSlow = caption.end_ms - first.start_ms > options.maxDurationMs;
      if (crossesGap || crossesBoundary || tooLong || tooSlow) flush();
    }
    group.push(caption);
    const currentText = groupText(group);
    const currentDuration = group[group.length - 1].end_ms - group[0].start_ms;
    if (endsWithBoundaryPunctuation(currentText) && currentDuration >= options.minDurationMs) {
      flush();
    } else if (endsWithSoftPunctuation(currentText) && textLength(currentText) >= Math.min(12, options.maxChars) && currentDuration >= options.minDurationMs) {
      flush();
    }
  }
  flush();
  return pages;
};
