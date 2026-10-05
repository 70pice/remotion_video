import {registerRoot} from 'remotion';
import {TimelineComposition} from './TimelineComposition';

// The production entry registers one timeline composition. Its registry
// resolves either a typed adapter or one of the 152 reviewed community presets.
registerRoot(TimelineComposition);
