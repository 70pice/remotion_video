import assert from 'node:assert/strict';
import test from 'node:test';
import {validateConfig} from './render-muse-demo.mjs';

const baseConfig = () => ({
  job_id: 'demo_job',
  title: 'Muse 是什么',
  width: 1920,
  height: 1080,
  fps: 30,
  duration_seconds: 10,
  audio_src: 'videoagents/demo_job/demo/voice.mp3',
  clips: {
    japan: 'videoagents/demo_job/demo/official-japan.mp4',
    shopping: 'videoagents/demo_job/demo/official-shopping.mp4',
  },
  segments: [{id: 's1', text: '测试', start_ms: 0, end_ms: 10000}],
  captions: [{text: '测试', start_ms: 0, end_ms: 9000}],
});

test('validateConfig keeps the existing horizontal demo size valid', () => {
  const config = baseConfig();
  assert.equal(validateConfig(config), config);
});

test('validateConfig accepts portrait visual metadata', () => {
  const config = baseConfig();
  config.width = 1080;
  config.height = 1920;
  config.segments[0].visual = {
    kind: 'footage',
    title: '官方演示',
    note: '真实视频素材',
    clip: 'japan',
    start_seconds: 1,
    end_seconds: 5,
  };
  assert.equal(validateConfig(config), config);
});

test('validateConfig rejects unsupported demo sizes', () => {
  const config = baseConfig();
  config.width = 1280;
  config.height = 720;
  assert.throws(() => validateConfig(config), /1920×1080 or 1080×1920/);
});

test('validateConfig rejects backwards portrait clip ranges', () => {
  const config = baseConfig();
  config.width = 1080;
  config.height = 1920;
  config.segments[0].visual = {
    kind: 'footage',
    title: '官方演示',
    note: '真实视频素材',
    clip: 'japan',
    start_seconds: 6,
    end_seconds: 2,
  };
  assert.throws(() => validateConfig(config), /clip range/);
});
