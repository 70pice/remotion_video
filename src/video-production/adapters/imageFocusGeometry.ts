import {fullCrop, resolveVideoCropGeometry} from './videoGeometry';
import type {NormalizedCrop, VideoMetadata} from './videoGeometry';

export type ImageFocusCue = {frame: number; region?: NormalizedCrop; label?: string};
export const focusEntranceFrames = 18;

// Keep one real image mounted while the camera moves between measured regions.
// Both camera and spotlight use source coordinates, so they stay aligned even
// when a landscape figure is letterboxed inside the portrait reading area.
export const resolveImageFocusGeometry = ({
  frame, cues, viewportWidth, viewportHeight, metadata,
}: {
  frame: number; cues: ImageFocusCue[];
  viewportWidth: number; viewportHeight: number; metadata: VideoMetadata;
}) => {
  const overview: ImageFocusCue = {frame: 0};
  const currentIndex = cues.reduce((selected, cue, index) => cue.frame <= frame ? index : selected, -1);
  const current = currentIndex < 0 ? overview : cues[currentIndex];
  const previous = currentIndex > 0 ? cues[currentIndex - 1] : overview;
  const elapsed = Math.max(0, Math.min(1, (frame - current.frame) / focusEntranceFrames));
  const progress = elapsed * elapsed * (3 - 2 * elapsed);
  const mix = (from: number, to: number) => from + (to - from) * progress;
  const camera = (region: NormalizedCrop) => {
    const geometry = resolveVideoCropGeometry({viewportWidth, viewportHeight, metadata, crop: region, fit: 'contain'});
    return {
      left: geometry.window.left + geometry.media.left,
      top: geometry.window.top + geometry.media.top,
      width: geometry.media.width, height: geometry.media.height,
    };
  };
  const fromRegion = previous.region ?? fullCrop;
  const toRegion = current.region ?? fullCrop;
  const from = camera(fromRegion);
  const to = camera(toRegion);
  const image = {
    left: mix(from.left, to.left), top: mix(from.top, to.top),
    width: mix(from.width, to.width), height: mix(from.height, to.height),
  };
  const region = Object.fromEntries(
    (['x', 'y', 'width', 'height'] as const).map((key) => [key, mix(fromRegion[key], toRegion[key])]),
  ) as NormalizedCrop;
  const spotlight = {
    left: image.left + region.x * image.width,
    top: image.top + region.y * image.height,
    width: region.width * image.width, height: region.height * image.height,
  };
  const emphasis = mix(previous.region ? 1 : 0, current.region ? 1 : 0);
  return {image, spotlight, emphasis, label: current.label};
};
