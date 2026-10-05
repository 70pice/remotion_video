export type VideoFit = 'contain' | 'cover';
export type NormalizedCrop = {x: number; y: number; width: number; height: number};
export type VideoMetadata = {width: number; height: number};

export type VideoCropGeometry = {
  window: {left: number; top: number; width: number; height: number};
  media: {left: number; top: number; width: number; height: number};
};

const assertPositive = (value: number, name: string) => {
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${name} must be a positive finite number`);
};

export const fullCrop: NormalizedCrop = {x: 0, y: 0, width: 1, height: 1};

export const resolveVideoCropGeometry = ({
  viewportWidth, viewportHeight, metadata, crop = fullCrop, fit = 'contain',
}: {
  viewportWidth: number;
  viewportHeight: number;
  metadata: VideoMetadata;
  crop?: NormalizedCrop;
  fit?: VideoFit;
}): VideoCropGeometry => {
  assertPositive(viewportWidth, 'viewportWidth');
  assertPositive(viewportHeight, 'viewportHeight');
  assertPositive(metadata.width, 'metadata.width');
  assertPositive(metadata.height, 'metadata.height');
  for (const field of ['x', 'y', 'width', 'height'] as const) {
    if (!Number.isFinite(crop[field])) throw new Error(`crop.${field} must be finite`);
  }
  if (crop.x < 0 || crop.y < 0 || crop.width <= 0 || crop.height <= 0 || crop.x + crop.width > 1 || crop.y + crop.height > 1) {
    throw new Error('crop must be a nonempty normalized rectangle inside the video');
  }
  const cropAspect = metadata.width * crop.width / (metadata.height * crop.height);
  const viewportAspect = viewportWidth / viewportHeight;
  const widthConstrained = fit === 'contain' ? cropAspect >= viewportAspect : cropAspect < viewportAspect;
  const windowWidth = widthConstrained ? viewportWidth : viewportHeight * cropAspect;
  const windowHeight = widthConstrained ? viewportWidth / cropAspect : viewportHeight;
  const mediaWidth = windowWidth / crop.width;
  const mediaHeight = windowHeight / crop.height;
  return {
    window: {
      left: (viewportWidth - windowWidth) / 2,
      top: (viewportHeight - windowHeight) / 2,
      width: windowWidth,
      height: windowHeight,
    },
    media: {
      left: -crop.x * mediaWidth,
      top: -crop.y * mediaHeight,
      width: mediaWidth,
      height: mediaHeight,
    },
  };
};
