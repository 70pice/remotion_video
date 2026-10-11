export const richMaterialSetIds = ['A07', 'A08', 'A09', 'A10', 'A11', 'A12'] as const;
export type RichMaterialSetId = typeof richMaterialSetIds[number];

export const richMaterialSetComponents: Record<RichMaterialSetId, readonly string[]> = {
  A07: ['Talkcraft-slow-push-in', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-QuoteCard', 'Rve-ProgressSteps', 'Snapcn-WordFlip', 'Talkcraft-source-converge'],
  A08: ['Snapcn-PhoneFrame', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-ProgressSteps', 'Rve-SplitScreen', 'Snapcn-WordFlip', 'Talkcraft-source-converge'],
  A09: ['Snapcn-PhoneFrame', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-ProgressSteps', 'Rve-StatCounter', 'Snapcn-TextBuild', 'Snapcn-TextSwap'],
  A10: ['Talkcraft-scanline-annotate', 'Snapcn-TextReveal', 'Talkcraft-ink-underline', 'Rve-ChartAnimation', 'Rve-StatCounter', 'Snapcn-TextBuild', 'Rve-LineChart'],
  A11: ['Talkcraft-tilt-3d-page', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-QuoteCard', 'Snapcn-WordFlip', 'Talkcraft-source-converge', 'Talkcraft-ink-underline'],
  A12: ['Talkcraft-slow-pull-reveal', 'Snapcn-TextReveal', 'Snapcn-TextHighlight', 'Rve-SplitScreen', 'Rve-ProgressSteps', 'Talkcraft-source-converge', 'Snapcn-WordFlip'],
};

export const richMaterialMainComponents = Object.fromEntries(
  richMaterialSetIds.map((id) => [id, richMaterialSetComponents[id][0]]),
) as Record<RichMaterialSetId, string>;

export const isRichMaterialSet = (value: unknown): value is RichMaterialSetId =>
  typeof value === 'string' && (richMaterialSetIds as readonly string[]).includes(value);

export const richMaterialNativeIdsForSet = (setId: RichMaterialSetId): readonly string[] =>
  richMaterialSetComponents[setId];

export const richMaterialA09FocusSourceSize = Object.freeze({width: 720, height: 1440});
export const richMaterialA09FocusSteps = Object.freeze([
  {instruction: '输入事项', start_frame: 0, end_frame: 115, target: {x: 0.108333, y: 0.275825, width: 0.783333, height: 0.061111}},
  {instruction: '点保存', start_frame: 115, end_frame: 179, target: {x: 0.108333, y: 0.353602, width: 0.277778, height: 0.054167}},
  {instruction: '查看列表', start_frame: 179, end_frame: 371, target: {x: 0.063889, y: 0.513889, width: 0.872222, height: 0.115278}},
] as const);
