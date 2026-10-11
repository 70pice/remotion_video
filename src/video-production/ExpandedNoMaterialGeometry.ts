export const expandedNoMaterialSetIds = ['B07', 'B08', 'B09', 'B10', 'B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18'] as const;

export const expandedNoMaterialGeometry = Object.freeze({
  title: {x: 64, y: 96, width: 952, height: 280},
  stage: {x: 56, y: 402, width: 968, height: 1068},
  emphasis: {x: 64, y: 1518, width: 952, height: 250},
  identity: {x: 70, y: 1810, width: 940, height: 42},
});

export const expandedStageTimings = (durationInFrames: number) => {
  const duration = Math.max(1, Math.floor(durationInFrames));
  return {intro: 0, expand: Math.floor(duration * 0.24), develop: Math.floor(duration * 0.48), resolve: Math.floor(duration * 0.70), duration};
};

export type ExpandedMetric = {label: string; value: string; detail?: string};
export type ExpandedNumericItem = {label: string; value: number; unit: string; display: string};

export const parseExpandedIntegerUnit = (value: string): {value: number; unit: string} | null => {
  const match = value.trim().match(/^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u);
  if (!match) return null;
  return {value: Number(match[1]), unit: match[2]};
};

export const parseExpandedNumericItem = (raw: string): ExpandedNumericItem | null => {
  const pieces = raw.split(/[：:]/).map((piece) => piece.trim()).filter(Boolean);
  if (pieces.length !== 2 || !pieces[0]) return null;
  const parsed = parseExpandedIntegerUnit(pieces[1]);
  if (!parsed) return null;
  return {label: pieces[0], value: parsed.value, unit: parsed.unit, display: pieces[1]};
};

export const expandedBoxesDoNotOverlap = (): boolean => {
  const boxes = [expandedNoMaterialGeometry.title, expandedNoMaterialGeometry.stage, expandedNoMaterialGeometry.emphasis, expandedNoMaterialGeometry.identity];
  return boxes.every((box, index) => index === 0 || boxes[index - 1].y + boxes[index - 1].height < box.y);
};
