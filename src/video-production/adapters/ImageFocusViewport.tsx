import {Img, useCurrentFrame} from 'remotion';
import {resolveImageFocusGeometry} from './imageFocusGeometry';
import type {ImageFocusCue} from './imageFocusGeometry';
import type {VideoMetadata} from './videoGeometry';

export const ImageFocusViewport = ({src, cues, metadata, width, height, accent, unit}: {
  src: string; cues: ImageFocusCue[]; metadata: VideoMetadata;
  width: number; height: number; accent: string; unit: number;
}) => {
  const geometry = resolveImageFocusGeometry({
    frame: useCurrentFrame(), cues, viewportWidth: width, viewportHeight: height, metadata,
  });
  const {image, spotlight, emphasis} = geometry;
  const right = spotlight.left + spotlight.width;
  const bottom = spotlight.top + spotlight.height;
  const mask = `M0 0H${width}V${height}H0Z M${spotlight.left} ${spotlight.top}V${bottom}H${right}V${spotlight.top}Z`;
  return <div style={{position: 'relative', width, height, overflow: 'hidden'}}>
    <Img src={src} style={{position: 'absolute', ...image, maxWidth: 'none', display: 'block'}} />
    <svg aria-hidden width={width} height={height} viewBox={`0 0 ${width} ${height}`}
      style={{position: 'absolute', inset: 0, pointerEvents: 'none'}}>
      <path d={mask} fill="#081324" fillRule="evenodd" opacity={emphasis * 0.62} />
      <rect x={spotlight.left} y={spotlight.top} width={spotlight.width} height={spotlight.height}
        fill="none" stroke={accent} strokeWidth={4 * unit} opacity={emphasis} />
    </svg>
  </div>;
};
