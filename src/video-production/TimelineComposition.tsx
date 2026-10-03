import {Composition} from 'remotion';
import {VideoFromTimeline} from './VideoFromTimeline';
import {defaultTimeline} from './defaults';
import {validateTimeline} from './validation.mjs';

export const TimelineComposition = () => <Composition
  id="VideoFromTimeline"
  component={VideoFromTimeline}
  durationInFrames={defaultTimeline.duration_in_frames}
  fps={defaultTimeline.fps}
  width={defaultTimeline.width}
  height={defaultTimeline.height}
  defaultProps={{timeline: defaultTimeline}}
  calculateMetadata={({props}) => {
    const timeline = validateTimeline(props.timeline);
    return {
      durationInFrames: timeline.duration_in_frames,
      fps: timeline.fps,
      width: timeline.width,
      height: timeline.height,
    };
  }}
/>;
