import {registerRoot} from 'remotion';
import {TimelineComposition} from './TimelineComposition';

// Production rendering loads only the reviewed adapters. Importing community
// demos here would start their font/media loaders even when not selected.
registerRoot(TimelineComposition);
