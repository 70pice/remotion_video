import {componentDemos} from '../demo';

const found = componentDemos.find((item) => item.id === 'Talkcraft-x-follow-card');
if (!found) throw new Error('Missing component entry: Talkcraft-x-follow-card');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
