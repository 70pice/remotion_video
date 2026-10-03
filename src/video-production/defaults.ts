import type {Timeline} from './types';

// Studio's initial view is clearly a test composition, not a generated job.
export const defaultTimeline: Timeline = {
  schema_version: '1',
  job_id: 'studio-test',
  revision: 1,
  width: 1080,
  height: 1920,
  fps: 30,
  duration_in_frames: 150,
  audio_src: null,
  shots: [{
    shot_id: 'test-title',
    start_frame: 0,
    end_frame: 150,
    component_id: 'title',
    title: '把声音变成画面',
    body: '制作流程测试片\n从真实素材、文案与音频开始。',
    asset_src: null,
    source_label: '测试内容 · 尚未接入任务音频',
    accent_color: '#B7F36B',
    props: {eyebrow: 'VIDEOAGENTS / 测试预览'},
  }],
  captions: [],
};
