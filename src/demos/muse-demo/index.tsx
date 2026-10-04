import {Composition, registerRoot} from 'remotion';
import {MuseDemo} from './MuseDemo';
import type {MuseDemoConfig} from './types';

const demoJob = '7dc715a4328f4d8a8297ff0dafcf0c8d';
const defaults: MuseDemoConfig = {
  job_id: demoJob, title: 'Muse 是什么', width: 1920, height: 1080, fps: 30, duration_seconds: 55,
  audio_src: `videoagents/${demoJob}/demo/voice.mp3`,
  clips: {japan: `videoagents/${demoJob}/demo/official-japan.mp4`, shopping: `videoagents/${demoJob}/demo/official-shopping.mp4`},
  segments: [{id: 'preview', text: 'Muse 是什么', start_ms: 0, end_ms: 55000}], captions: [],
};

const MuseDemoRoot = () => <Composition id="MuseDemo" component={MuseDemo} width={1920} height={1080} fps={30} durationInFrames={1650} defaultProps={{config: defaults}} calculateMetadata={({props}) => ({width: props.config.width, height: props.config.height, fps: props.config.fps, durationInFrames: Math.ceil(props.config.duration_seconds * props.config.fps)})} />;

registerRoot(MuseDemoRoot);
