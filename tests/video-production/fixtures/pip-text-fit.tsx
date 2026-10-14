import {Composition, registerRoot} from 'remotion';
import {VideoFromTimeline} from '../../../src/video-production/VideoFromTimeline';
import type {Timeline} from '../../../src/video-production/types';

const Fixture = ({title, source, layered = false}: {title: string; source: string; layered?: boolean}) => {
  const timeline: Timeline = {
    schema_version: '1', job_id: 'pip-text-fit-test', revision: 1,
    width: 1080, height: 1920, fps: 30, duration_in_frames: 180,
    audio_src: null, captions: [],
    shots: [{shot_id: 'pip-test', start_frame: 0, end_frame: 180,
      component_id: 'Talkcraft-split-60-40-story', title, body: '',
      asset_src: null, source_label: source, accent_color: '#38BDF8',
      props: {content_mode: 'list', items: ['自己发消息', '接视频通话', '回关社交账号']},
      ...(layered ? {layers: [{component_id: 'Snapcn-TextReveal', role: 'title' as const,
        start_frame: 0, end_frame: 30, title: '测试标签', body: '',
        accent_color: '#38BDF8', props: {}}]} : {})}],
  };
  return <VideoFromTimeline timeline={timeline} />;
};

registerRoot(() => <Composition id="PipTextFit" component={Fixture}
  width={1080} height={1920} fps={30} durationInFrames={180}
  defaultProps={{title: '真人的活：发消息、视频、回关', source: ''}} />);
