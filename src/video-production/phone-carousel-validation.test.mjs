import assert from 'node:assert/strict';
import {Buffer} from 'node:buffer';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath, URL} from 'node:url';
import {validateLocalInputs} from '../../scripts/render-timeline.mjs';
import {validateTimeline} from './validation.mjs';

const fixture = (jobId = 'carousel-unit') => {
  const source = (index) => `videoagents/${jobId}/assets/${index}.png`;
  return {schema_version: '1', job_id: jobId, revision: 1, width: 1080, height: 1920, fps: 30,
    duration_in_frames: 120, audio_src: null, captions: [], shots: [{shot_id: 'phone', start_frame: 0, end_frame: 120,
      component_id: 'Snapcn-PhoneFrame', title: '真实图片轮播', body: '', asset_src: source(1), source_label: 'example.com',
      accent_color: '#38BDF8', props: {content_mode: 'media', carousel_transition_frames: 6,
        media_slides: [{asset_src: source(1), start_frame: 0, asset_fit: 'contain'},
          {asset_src: source(2), start_frame: 60, asset_fit: 'cover', asset_crop: {x: 0, y: 0, width: 0.5, height: 1}}]}}]};
};

test('one PhoneFrame timeline accepts timed real image slides without rewriting the shot', () => {
  const timeline = fixture();
  const before = JSON.stringify(timeline);
  assert.equal(validateTimeline(timeline), timeline);
  assert.equal(JSON.stringify(timeline), before);
  assert.equal(timeline.shots.length, 1);
});

test('carousel contract rejects ignored slots, unsafe sources, invalid local frames and image options', () => {
  for (const mutate of [
    (s) => {s.props.media_slides.pop();},
    (s) => {s.props.media_slides = Array.from({length: 9}, (_, index) => ({...s.props.media_slides[0], start_frame: index}));},
    (s) => {s.props.media_slides[0].start_frame = 1;},
    (s) => {s.props.media_slides[1].start_frame = 0;},
    (s) => {s.props.media_slides[1].start_frame = 120;},
    (s) => {s.props.media_slides[1].start_frame = true;},
    (s) => {s.props.media_slides[1].start_frame = 1.5;},
    (s) => {s.props.media_slides[0].asset_src = s.props.media_slides[1].asset_src;},
    (s) => {s.props.media_slides[1].asset_src = 'https://example.com/a.png';},
    (s) => {s.props.media_slides[1].asset_src = 'videoagents/other/assets/2.png';},
    (s) => {s.props.media_slides[1].asset_src = 'videoagents/carousel-unit/../2.png';},
    (s) => {s.props.media_slides[1].asset_src = 'videoagents/carousel-unit/assets/a.mp4';},
    (s) => {s.props.media_slides[1].asset_fit = 'fill';},
    (s) => {delete s.props.media_slides[1].asset_fit;},
    (s) => {s.props.media_slides[1].asset_crop.width = 2;},
    (s) => {s.props.media_slides[1].src = 'ignored.png';},
    (s) => {s.props.carousel_transition_frames = true;},
    (s) => {s.props.carousel_transition_frames = null;},
    (s) => {s.props.carousel_transition_frames = 16;},
    (s) => {delete s.props.media_slides;},
    (s) => {s.component_id = 'Talkcraft-slow-push-in';},
    (s) => {s.props.focus_steps = [];},
    (s) => {s.props.tutorial_steps = [];},
    (s) => {s.props.component_set = 'A08';},
    (s) => {s.set_design = {};},
  ]) {
    const timeline = fixture();
    mutate(timeline.shots[0]);
    assert.throws(() => validateTimeline(timeline));
  }
});

test('renderer validates and stages every distinct carousel file, including later pages', async (t) => {
  const jobId = `carousel-unit-${randomUUID()}`;
  const publicRoot = fileURLToPath(new URL('../../public/', import.meta.url));
  const jobRoot = path.join(publicRoot, 'videoagents', jobId);
  assert.ok(jobRoot.startsWith(path.join(publicRoot, 'videoagents', 'carousel-unit-')));
  await fs.mkdir(path.join(jobRoot, 'assets'), {recursive: true});
  t.after(() => fs.rm(jobRoot, {recursive: true, force: true}));
  const timeline = fixture(jobId);
  const first = path.join(jobRoot, 'assets', '1.png');
  const second = path.join(jobRoot, 'assets', '2.png');
  const image = Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), Buffer.alloc(24)]);
  await fs.writeFile(first, image);
  await assert.rejects(validateLocalInputs(timeline), /ENOENT/);
  await fs.writeFile(second, Buffer.alloc(32));
  await assert.rejects(validateLocalInputs(timeline), /content does not match/);
  await fs.writeFile(second, image);
  const {files} = await validateLocalInputs(timeline);
  assert.deepEqual(files.map(({source}) => source), timeline.shots[0].props.media_slides.map(({asset_src}) => asset_src));
  assert.equal(files.length, 2);
});
