import {componentDemos} from '../demo';

const found = componentDemos.find((item) => item.id === 'Talkcraft-magnifier-detail');
if (!found) throw new Error('Missing component entry: Talkcraft-magnifier-detail');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
