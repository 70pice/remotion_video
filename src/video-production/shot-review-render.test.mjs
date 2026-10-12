import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import {main, outputScale, parseArgs, renderShotReviewImages, validateShotReviewRequest} from '../../scripts/render-timeline.mjs';

const {structuredClone} = globalThis;

const timeline = () => ({
  schema_version: '1', job_id: 'shot-review-fixture', revision: 1,
  width: 1080, height: 1920, fps: 30, duration_in_frames: 90,
  audio_src: null, captions: [],
  shots: [
    {shot_id: 'first', start_frame: 0, end_frame: 30, component_id: 'title', title: '首镜', body: '',
      asset_src: null, source_label: '', accent_color: '#B7F36B', props: {}},
    {shot_id: 'second', start_frame: 30, end_frame: 90, component_id: 'title', title: '第二镜', body: '',
      asset_src: null, source_label: '', accent_color: '#B7F36B', props: {}},
  ],
});

test('batch renders each specified canonical frame and publishes manifest after all images', async (t) => {
  const root = await fs.mkdtemp(path.join(await fs.realpath(os.tmpdir()), 'videoagents-shot-review-batch-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  const output = path.join(root, 'delivery', 'manifest.json');
  const tempDir = path.join(root, 'staging');
  const frames = [];
  const original = timeline();
  const before = structuredClone(original);
  const images = await renderShotReviewImages({timeline: original, request: request(), output, tempDir,
    progress: () => {}, assertRunning: () => {}, renderFrame: async (frame, file) => {
      frames.push(frame);
      await assert.rejects(fs.stat(output), {code: 'ENOENT'});
      await fs.writeFile(file, `PNG frame ${frame}`);
    }});
  assert.deepEqual(frames, [24, 60]);
  assert.deepEqual(original, before);
  assert.deepEqual(JSON.parse(await fs.readFile(output, 'utf8')), images);
  assert.deepEqual(images.map((image) => [image.width, image.height]), [[1080, 1920], [1080, 1920]]);
  for (const [index, image] of images.entries()) {
    assert.equal(image.path, path.join(path.dirname(output), `shot-${String(index + 1).padStart(3, '0')}.png`));
    assert.equal(await fs.readFile(image.path, 'utf8'), `PNG frame ${frames[index]}`);
  }
});

test('failure of any still leaves no review manifest or partial published batch', async (t) => {
  const root = await fs.mkdtemp(path.join(await fs.realpath(os.tmpdir()), 'videoagents-shot-review-failed-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  const output = path.join(root, 'delivery', 'manifest.json');
  await assert.rejects(renderShotReviewImages({timeline: timeline(), request: request(), output,
    tempDir: path.join(root, 'staging'), progress: () => {}, assertRunning: () => {},
    renderFrame: async (frame, file) => {
      if (frame === 60) throw new Error('second still failed');
      await fs.writeFile(file, 'first still');
    }}), /second still failed/);
  await assert.rejects(fs.stat(output), {code: 'ENOENT'});
  await assert.rejects(fs.stat(path.join(path.dirname(output), 'shot-001.png')), {code: 'ENOENT'});
});

test('atomic manifest publication never replaces a deliverable created during rendering', async (t) => {
  const root = await fs.mkdtemp(path.join(await fs.realpath(os.tmpdir()), 'videoagents-shot-review-race-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  const output = path.join(root, 'manifest.json');
  await assert.rejects(renderShotReviewImages({timeline: timeline(), request: request(), output,
    tempDir: path.join(root, 'staging'), progress: () => {}, assertRunning: () => {},
    renderFrame: async (frame, file) => {
      await fs.writeFile(file, `frame ${frame}`);
      if (frame === 60) await fs.writeFile(output, 'other invocation manifest');
    }}), {code: 'EEXIST'});
  assert.equal(await fs.readFile(output, 'utf8'), 'other invocation manifest');
  assert.deepEqual((await fs.readdir(root)).sort(), ['manifest.json', 'staging']);
});
const request = () => [{shot_id: 'first', frame: 24}, {shot_id: 'second', frame: 60}];

test('shot review CLI requires a separate absolute JSON request and manifest', () => {
  const root = path.join(os.tmpdir(), 'shot review paths');
  const cli = (...extra) => parseArgs(['--timeline', path.join(root, 'timeline.json'),
    '--output', path.join(root, 'manifest.json'), '--mode', 'shot-review', ...extra]);
  const options = cli('--review-frames', path.join(root, 'request.json'));
  assert.equal(options.mode, 'shot-review');
  assert.equal(options['review-frames'], path.join(root, 'request.json'));
  assert.equal(outputScale({...timeline(), presentation: 'component_sample'}, 'shot-review'), 1);
  assert.throws(() => cli(), /review-frames/);
  assert.throws(() => cli('--review-frames', 'relative.json'), /absolute/);
  assert.throws(() => cli('--review-frames', path.join(root, 'request.png')), /JSON/);
  assert.throws(() => cli('--review-frames', path.join(root, 'request.json'), '--cover', path.join(root, 'cover.png')), /cover/);
  assert.throws(() => cli('--review-frames', path.join(root, 'request.json'), '--start-frame', '0', '--end-frame', '30'), /frame/);
  assert.throws(() => parseArgs(['--timeline', path.join(root, 'timeline.json'), '--output', path.join(root, 'preview.mp4'),
    '--mode', 'preview', '--review-frames', path.join(root, 'request.json')]), /shot-review/);
});

test('shot review requests preserve absolute frames and cover every shot once in timeline order', () => {
  const value = request();
  assert.deepEqual(validateShotReviewRequest(timeline(), value), value);
  assert.deepEqual(validateShotReviewRequest(timeline(), [{shot_id: 'first', frame: 0}, {shot_id: 'second', frame: 89}]),
    [{shot_id: 'first', frame: 0}, {shot_id: 'second', frame: 89}]);
  for (const invalid of [null, {}, [], [value[0]], [...value, value[0]], [...value].reverse(),
    [value[0], value[0]], [{shot_id: 'missing', frame: 24}, value[1]],
    [{shot_id: 'first', frame: -1}, value[1]], [{shot_id: 'first', frame: 30}, value[1]],
    [value[0], {shot_id: 'second', frame: 29}], [value[0], {shot_id: 'second', frame: 90}],
    [{shot_id: 'first', frame: 2.5}, value[1]], [{shot_id: 'first', frame: true}, value[1]],
    [{shot_id: 'first', frame: '24'}, value[1]], [{...value[0], path: '../unsafe.png'}, value[1]],
  ]) assert.throws(() => validateShotReviewRequest(timeline(), invalid), /review|shot|frame/i);
  assert.equal(JSON.stringify(timeline().captions), '[]');
});

test('shot review cannot replace an existing manifest or PNG deliverable', async (t) => {
  const root = await fs.mkdtemp(path.join(await fs.realpath(os.tmpdir()), 'videoagents-shot-review-test-'));
  t.after(() => fs.rm(root, {recursive: true, force: true}));
  const input = path.join(root, 'timeline.json');
  const frames = path.join(root, 'request.json');
  const output = path.join(root, 'manifest.json');
  await fs.writeFile(input, JSON.stringify(timeline()));
  await fs.writeFile(frames, JSON.stringify(request()));
  await fs.writeFile(output, 'existing manifest');
  const args = ['--timeline', input, '--output', output, '--mode', 'shot-review', '--review-frames', frames];
  await assert.rejects(main(args), /already exists/);
  assert.equal(await fs.readFile(output, 'utf8'), 'existing manifest');
  await fs.unlink(output);
  const image = path.join(root, 'shot-001.png');
  await fs.writeFile(image, 'existing user PNG');
  await assert.rejects(main(args), /already exists/);
  assert.equal(await fs.readFile(image, 'utf8'), 'existing user PNG');
  await assert.rejects(fs.stat(output), {code: 'ENOENT'});
});
