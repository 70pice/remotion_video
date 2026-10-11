export type TutorialRect = {x: number; y: number; width: number; height: number};
export type TutorialStep = {
  start_frame: number;
  end_frame: number;
  instruction: string;
  target: TutorialRect;
};
export type TutorialSourceSize = {width: number; height: number};

// The guided adapter fixes the native phone body to border-box sizing.
export const phoneScreenSize = {width: 296, height: 632};

export const tutorialStepAt = (steps: TutorialStep[], frame: number) =>
  steps.find((step) => frame >= step.start_frame && frame < step.end_frame);

export const containedSourceRect = (source: TutorialSourceSize, viewport = phoneScreenSize): TutorialRect => {
  const scale = Math.min(viewport.width / source.width, viewport.height / source.height);
  const width = source.width * scale;
  const height = source.height * scale;
  return {x: (viewport.width - width) / 2, y: (viewport.height - height) / 2, width, height};
};

// Targets refer to source pixels, so contain-fit letterboxing must also apply to ink.
export const tutorialTargetRect = (target: TutorialRect, source: TutorialSourceSize, viewport = phoneScreenSize): TutorialRect => {
  const media = containedSourceRect(source, viewport);
  return {x: media.x + target.x * media.width, y: media.y + target.y * media.height,
    width: target.width * media.width, height: target.height * media.height};
};

// A loose, hand-drawn loop follows the outside of the control; no fill covers its text.
export const tutorialRingPath = (rect: TutorialRect, viewport = phoneScreenSize): string => {
  const left = Math.max(2, rect.x - 5);
  const top = Math.max(2, rect.y - 5);
  const right = Math.min(viewport.width - 2, rect.x + rect.width + 5);
  const bottom = Math.min(viewport.height - 2, rect.y + rect.height + 5);
  const middle = (left + right) / 2;
  const corner = Math.min(12, (bottom - top) / 4);
  return `M ${middle} ${top} C ${right - corner} ${top - 1}, ${right + 1} ${top}, ${right} ${top + corner}
    L ${right - 1} ${bottom - corner} Q ${right + 1} ${bottom + 1}, ${right - corner} ${bottom}
    C ${middle} ${bottom + 1}, ${left - 1} ${bottom}, ${left} ${bottom - corner}
    L ${left + 1} ${top + corner} Q ${left - 1} ${top - 1}, ${left + corner} ${top + 1}
    L ${middle + 6} ${top + 1}`;
};
