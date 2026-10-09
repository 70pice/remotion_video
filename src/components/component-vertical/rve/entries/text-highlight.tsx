import {nativeDemos} from '../demo';

const found = nativeDemos.find((item) => item.id === 'Rve-TextHighlight');
if (!found) throw new Error('Missing component entry: Rve-TextHighlight');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
