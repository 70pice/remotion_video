import type {TutorialRect, TutorialSourceSize} from './phoneTutorial';

export const focusMediaBox = (source: TutorialSourceSize) => ({
  width: 952,
  height: Math.min(1450, 952 * source.height / source.width),
});

export const guidedMaterialTop = 96;
export const guidedTitleHeight = 156;
export const guidedPhoneHeight = 1350;
export const guidedPhoneScale = 2.05;
export const guidedPhoneTitleTop = guidedMaterialTop + guidedPhoneHeight + 28;

// Copy follows the last visible material, with the same gap for an overview,
// a live recording or an enlarged detail. No title plate occupies the stage.
export const focusCompositionLayout = (source: TutorialSourceSize, target: TutorialRect, video: boolean) => {
  const media = focusMediaBox(source);
  const mediaBottom = guidedMaterialTop + media.height;
  const detailTop = mediaBottom + 28;
  const detailLabelHeight = 52;
  const available = 1824 - guidedTitleHeight - 28 - detailTop - detailLabelHeight;
  const detail = !video && target.width * target.height <= 0.7 && available >= 180
    ? {top: detailTop, height: Math.min(600, available), labelHeight: detailLabelHeight} : null;
  return {media, detail, titleTop: detail ? detail.top + detail.labelHeight + detail.height + 28 : mediaBottom + 28};
};

// A detail is a crop of the same continuous source, never a replacement screenshot.
export const focusDetailCrop = (target: TutorialRect): TutorialRect => {
  const width = Math.min(1, Math.max(0.24, target.width + 0.08));
  const height = Math.min(1, Math.max(0.15, target.height + 0.08));
  return {x: Math.max(0, Math.min(1 - width, target.x + target.width / 2 - width / 2)),
    y: Math.max(0, Math.min(1 - height, target.y + target.height / 2 - height / 2)), width, height};
};
