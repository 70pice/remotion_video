import {nativeDemos as groupA} from '../group-a';
import {nativeDemos as groupB} from '../group-b';
import {nativeDemos as groupC} from '../group-c';
import {nativeDemos as groupD} from '../group-d';
const nativeDemos = [...groupA, ...groupB, ...groupC, ...groupD];

const found = nativeDemos.find((item) => item.id === 'Talkcraft-focus-dim-spotlight');
if (!found) throw new Error('Missing component entry: Talkcraft-focus-dim-spotlight');

// Ready-to-preview component using the library's existing example props.
export const demo = found;
export const Component = found.component;
export const meta = {
  width: found.width, height: found.height,
  fps: found.fps, durationInFrames: found.durationInFrames,
};
export default Component;
