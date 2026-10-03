import {Composition} from 'remotion';
import {AiScienceVideo} from './templates/AiScienceVideo';
import episode from './episode.generated.json';
import {CommunityRoot} from './components/community/CommunityRoot';
import {TimelineComposition} from './video-production/TimelineComposition';

export const RemotionRoot = () => (
  <>
    <Composition
      id="AiScience"
      component={AiScienceVideo}
      durationInFrames={episode.durationInFrames}
      fps={episode.fps}
      width={episode.width}
      height={episode.height}
      defaultProps={{episode}}
      calculateMetadata={({props}) => ({
        durationInFrames: props.episode.durationInFrames,
        fps: props.episode.fps,
        width: props.episode.width,
        height: props.episode.height,
      })}
    />
    <TimelineComposition />
    <CommunityRoot />
  </>
);
