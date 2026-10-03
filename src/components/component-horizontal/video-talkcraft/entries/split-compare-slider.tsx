import {componentDemos} from '../demo';

const found = componentDemos.find((item) => item.id === 'Talkcraft-split-compare-slider');
if (!found) throw new Error('Missing component entry: Talkcraft-split-compare-slider');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
