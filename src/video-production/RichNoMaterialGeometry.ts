export const richNoMaterialGeometry = Object.freeze({
  title: {x: 64, y: 96, width: 952, height: 280},
  stage: {x: 56, y: 402, width: 968, height: 1068},
  emphasis: {x: 64, y: 1518, width: 952, height: 250},
  identity: {x: 70, y: 1810, width: 940, height: 42},
});

export const richNoMaterialMinimumFont = Object.freeze({
  headline: 70,
  body: 42,
  compact: 40,
});

export const richStageTimings = (durationInFrames: number) => {
  const duration = Math.max(1, Math.floor(durationInFrames));
  const intro = 0;
  const expand = Math.floor(duration * 0.24);
  const develop = Math.floor(duration * 0.46);
  const resolve = Math.floor(duration * 0.68);
  return {intro, expand, develop, resolve, duration};
};

export type RichMetric = {label: string; value: string; detail?: string};
export type RichNumericItem = {label: string; value: number; unit: string; display: string};

export const parseRichIntegerUnit = (value: string): {value: number; unit: string} | null => {
  const match = value.trim().match(/^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u);
  if (!match) return null;
  return {value: Number(match[1]), unit: match[2]};
};

export const parseRichNumericItem = (raw: string): RichNumericItem | null => {
  const pieces = raw.split(/[：:]/).map((piece) => piece.trim()).filter(Boolean);
  if (pieces.length !== 2 || !pieces[0]) return null;
  const parsed = parseRichIntegerUnit(pieces[1]);
  if (!parsed) return null;
  return {label: pieces[0], value: parsed.value, unit: parsed.unit, display: pieces[1]};
};

export const richNumericItemsSumToMetric = (items: readonly RichNumericItem[], metric: RichMetric): boolean => {
  const parsed = parseRichIntegerUnit(metric.value);
  if (!parsed || items.length === 0) return false;
  return items.every((item) => item.unit === parsed.unit) &&
    items.reduce((total, item) => total + item.value, 0) === parsed.value;
};

export const richNoMaterialBoxesDoNotOverlap = (): boolean => {
  const boxes = [richNoMaterialGeometry.title, richNoMaterialGeometry.stage,
    richNoMaterialGeometry.emphasis, richNoMaterialGeometry.identity];
  return boxes.every((box, index) => index === 0 || boxes[index - 1].y + boxes[index - 1].height < box.y);
};
