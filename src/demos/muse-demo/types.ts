// 样片独立输入：字幕和段落时间来自实际配音，不用字数推算时间。
export type MuseTimedText = {text: string; start_ms: number; end_ms: number};
export type MuseDemoConfig = {
  job_id: string;
  title: string;
  width: number;
  height: number;
  fps: number;
  duration_seconds: number;
  audio_src: string;
  clips: {japan: string; shopping: string};
  segments: (MuseTimedText & {id: string})[];
  captions: MuseTimedText[];
};
