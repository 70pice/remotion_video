// The no-material sets share separated copy, demonstration and action areas.
// They use real native bindings; this marker never selects a demo entrypoint.
export const noMaterialSetMainComponents = {
  B01: 'Rve-QuoteCard', B02: 'keyword', B03: 'Rve-SplitScreen',
  B04: 'Rve-StatCounter', B05: 'Rve-ProgressSteps', B06: 'conclusion',
  B07: 'Rve-ChartAnimation', B08: 'Rve-StatCounter', B09: 'Rve-ComparisonChart',
  B10: 'Rve-ChartAnimation', B11: 'Rve-ProgressSteps', B12: 'Rve-QuoteCard',
  B13: 'Rve-SplitScreen', B14: 'Snapcn-AnswerStream', B15: 'Rve-QuoteCard',
  B16: 'Rve-ProgressSteps', B17: 'Bits-ChatConversation', B18: 'Rve-ComparisonChart',
} as const;

export const isNoMaterialSet = (value: unknown): value is keyof typeof noMaterialSetMainComponents =>
  typeof value === 'string' && Object.hasOwn(noMaterialSetMainComponents, value);

export const noMaterialSetGeometry = Object.freeze({
  title: {x: 64, y: 96, width: 952, height: 270},
  main: {x: 70, y: 430, width: 940, height: 800},
  body: {x: 70, y: 1260, width: 940, height: 180},
  emphasis: {x: 64, y: 1480, width: 952, height: 290},
  identity: {x: 70, y: 1810, width: 940, height: 42},
});
