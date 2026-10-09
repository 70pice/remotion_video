import {nativeDemos} from '../demo';

const found = nativeDemos.find((item) => item.id === 'RenderComp-NewsTicker');
if (!found) throw new Error('Missing component entry: RenderComp-NewsTicker');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
