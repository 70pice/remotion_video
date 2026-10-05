import assert from 'node:assert/strict';
import {Buffer} from 'node:buffer';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import {main, outputScale, parseArgs, validateLocalInputs} from '../../scripts/render-timeline.mjs';
import {communityComponentIds, productionComponentIds, validateTimeline} from './validation.mjs';

const {structuredClone} = globalThis;

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const fixture = () => ({
  schema_version: '1', job_id: 'test-job', revision: 1, width: 1080, height: 1920, fps: 30,
  duration_in_frames: 60, audio_src: null,
  shots: [{shot_id: 'a', start_frame: 0, end_frame: 60, component_id: 'title', title: '测试标题',
    body: '测试内容', asset_src: null, source_label: '明确标记的测试内容', accent_color: '#B7F36B', props: {}}],
  captions: [],
});

test('every production adapter accepts supplied content; data is never invented', () => {
  const cases = {
    title: {eyebrow: '测试'}, keyword: {keyword: '来自输入的关键词'},
    evidence: {highlight: {x: 0.2, y: 0.3, width: 0.4, height: 0.5}},
    image_focus: {focal_x: 0.2, focal_y: 0.8},
    comparison: {left_title: '输入 A', left_body: '明确的 A 内容', right_title: '输入 B', right_body: '明确的 B 内容'},
    data: {items: [{label: '用户提供的数据', value: '待核实', detail: '测试字段'}]},
    steps: {items: [{title: '读取输入', body: '来自调用者的步骤'}]}, conclusion: {call_to_action: '测试结束'},
  };
  for (const [component, props] of Object.entries(cases)) {
    const timeline = fixture();
    timeline.shots[0].component_id = component;
    timeline.shots[0].props = props;
    if (['evidence', 'image_focus'].includes(component)) timeline.shots[0].asset_src = 'videoagents/test-job/source.png';
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before, 'validation must not replace factual input or timestamps');
  }
});

test('shots form a complete half-open partition: reject gaps, overlaps, duplicate IDs and missing ending', () => {
  for (const secondStart of [29, 31]) {
    const timeline = fixture();
    timeline.shots[0].end_frame = 30;
    timeline.shots.push({...timeline.shots[0], shot_id: 'b', start_frame: secondStart, end_frame: 60});
    assert.throws(() => validateTimeline(timeline), /contiguously/);
  }
  const duplicate = fixture();
  duplicate.shots[0].end_frame = 30;
  duplicate.shots.push({...duplicate.shots[0], start_frame: 30, end_frame: 60});
  assert.throws(() => validateTimeline(duplicate), /duplicated/);
  const unfinished = fixture();
  unfinished.shots[0].end_frame = 59;
  assert.throws(() => validateTimeline(unfinished), /must end/);
});

test('remote, absolute, encoded and other-job media references cannot reach a renderer', () => {
  const bad = ['https://example.com/a.png', 'file:///C:/private.png', 'C:\\private.png',
    '/api/artifacts/123', 'videoagents/other-job/a.png', 'videoagents/test-job/../a.png',
    'videoagents/test-job/%2e%2e/a.png', 'videoagents/test-job/a.png?fetch=https://example.com'];
  for (const source of bad) {
    const timeline = fixture();
    timeline.shots[0].asset_src = source;
    assert.throws(() => validateTimeline(timeline), /without URLs/);
  }
});

test('all 152 presets are registered while unknown IDs and preset injections are rejected', () => {
  assert.equal(productionComponentIds.length, 160);
  assert.equal(communityComponentIds.length, 152);
  const preset = fixture();
  preset.shots[0].component_id = 'Snapcn-TextReveal';
  assert.equal(validateTimeline(preset), preset);
  const presetProps = structuredClone(preset);
  presetProps.shots[0].props = {src: 'https://example.com/payload.svg'};
  assert.throws(() => validateTimeline(presetProps), /unsupported/);
  const presetAsset = structuredClone(preset);
  presetAsset.shots[0].asset_src = 'videoagents/test-job/a.png';
  assert.throws(() => validateTimeline(presetAsset), /do not accept asset_src/);
  const injection = fixture();
  injection.shots[0].props = {src: 'https://example.com/payload.svg'};
  assert.throws(() => validateTimeline(injection), /unsupported/);
  const demo = fixture();
  demo.shots[0].component_id = 'crash-zoom-punch';
  assert.throws(() => validateTimeline(demo), /not supported/);
  const css = fixture();
  css.shots[0].accent_color = 'url(https://example.com/payload)';
  assert.throws(() => validateTimeline(css), /hex color/);
  const evidence = fixture();
  Object.assign(evidence.shots[0], {component_id: 'evidence', source_label: '', asset_src: 'videoagents/test-job/a.png'});
  assert.throws(() => validateTimeline(evidence), /requires an image and a source label/);
  evidence.shots[0].source_label = '来源';
  evidence.shots[0].props = {highlight: {x: 0.8, y: 0.1, width: 0.5, height: 0.2}};
  assert.throws(() => validateTimeline(evidence), /inside the image/);
});

test('props length limits and optional-field emptiness have explicit boundaries', () => {
  const cases = [
    ['title', {eyebrow: 'a'.repeat(49)}], ['keyword', {keyword: 'a'.repeat(41)}],
    ['conclusion', {call_to_action: 'a'.repeat(73)}], ['title', {eyebrow: '   '}],
    ['comparison', {left_title: 'a'.repeat(49), left_body: 'a', right_title: 'a', right_body: 'a'}],
    ['data', {items: [{label: 'a', value: 'a'.repeat(41)}]}],
    ['data', {items: [{label: 'a', value: 'a', detail: 'a'.repeat(65)}]}],
    ['steps', {items: [{title: 'a'.repeat(49)}]}],
    ['steps', {items: [{title: 'a', body: 'a'.repeat(97)}]}],
  ];
  for (const [component, props] of cases) {
    const timeline = fixture();
    Object.assign(timeline.shots[0], {component_id: component, props});
    assert.throws(() => validateTimeline(timeline), /text of at most/);
  }
});

test('captions preserve fractional measured milliseconds and cannot overlap or exceed the timeline', () => {
  const timeline = fixture();
  timeline.audio_src = 'videoagents/test-job/voice.wav';
  timeline.captions = [{text: '测试甲', start_ms: 125.5, end_ms: 940.25}, {text: '测试乙', start_ms: 1000.75, end_ms: 1900.5}];
  assert.equal(validateTimeline(timeline).captions[0].end_ms, 940.25);
  const overlap = structuredClone(timeline);
  overlap.captions[1].start_ms = 940;
  assert.throws(() => validateTimeline(overlap), /nonoverlapping/);
  const pastEnd = structuredClone(timeline);
  pastEnd.captions[1].end_ms = 2001;
  assert.throws(() => validateTimeline(pastEnd), /inside the audio timeline/);
  timeline.audio_src = null;
  assert.throws(() => validateTimeline(timeline), /aligned source audio/);
});

test('CLI accepts absolute paths with spaces and rejects ambiguous repeated flags', () => {
  const location = path.join(os.tmpdir(), 'video agents test');
  const options = parseArgs(['--timeline', path.join(location, 'timeline.json'), '--output', path.join(location, 'clip.mp4'),
    '--mode', 'preview', '--cover', path.join(location, 'cover.png')]);
  assert.equal(options.mode, 'preview');
  assert.throws(() => parseArgs(['--timeline', 'relative.json', '--output', path.join(location, 'clip.mp4'), '--mode', 'preview']), /absolute path/);
  assert.throws(() => parseArgs(['--timeline', path.join(location, 'timeline.json'), '--timeline', path.join(location, 'second.json')]), /Usage/);
});

test('preview scaling cannot turn valid even H.264 dimensions into odd pixels', () => {
  for (const dimensions of [{width: 1080, height: 1920}, {width: 242, height: 640}, {width: 360, height: 642}]) {
    const scale = outputScale(dimensions, 'preview');
    assert.equal(dimensions.width * scale % 2, 0);
    assert.equal(dimensions.height * scale % 2, 0);
    assert.equal(outputScale(dimensions, 'final'), 1);
  }
});

test('a new render invocation cannot overwrite an existing deliverable', async (t) => {
  const canonicalTemp = await fs.realpath(os.tmpdir());
  const temp = await fs.mkdtemp(path.join(canonicalTemp, 'videoagents-command-test-'));
  t.after(async () => {
    assert.equal(path.dirname(temp), canonicalTemp);
    assert.ok(path.basename(temp).startsWith('videoagents-command-test-'));
    await fs.rm(temp, {recursive: true, force: true});
  });
  const input = path.join(temp, 'input.json');
  const output = path.join(temp, 'existing.mp4');
  await fs.writeFile(input, JSON.stringify(fixture()));
  await fs.writeFile(output, 'existing-user-deliverable');
  await assert.rejects(main(['--timeline', input, '--output', output, '--mode', 'final']), /already exists/);
  assert.equal(await fs.readFile(output, 'utf8'), 'existing-user-deliverable');
});

test('local media rejects extension spoofing and directory junctions escaping a task', async (t) => {
  const jobId = 'render-validation-' + randomUUID();
  const jobRoot = path.join(root, 'public', 'videoagents', jobId);
  const canonicalTemp = await fs.realpath(os.tmpdir());
  const externalRoot = await fs.mkdtemp(path.join(canonicalTemp, 'videoagents-media-test-'));
  await fs.mkdir(jobRoot, {recursive: true});
  t.after(async () => {
    // Remove the test junction directly, never recurse through its target.
    await fs.unlink(path.join(jobRoot, 'escape')).catch((error) => { if (error.code !== 'ENOENT') throw error; });
    assert.equal(path.basename(jobRoot), jobId);
    assert.equal(path.dirname(jobRoot), path.join(root, 'public', 'videoagents'));
    await fs.rm(jobRoot, {recursive: true, force: true});
    assert.equal(path.dirname(externalRoot), canonicalTemp);
    assert.ok(path.basename(externalRoot).startsWith('videoagents-media-test-'));
    await fs.rm(externalRoot, {recursive: true, force: true});
  });
  const timeline = fixture();
  timeline.job_id = jobId;
  timeline.shots[0].asset_src = `videoagents/${jobId}/spoof.png`;
  await fs.writeFile(path.join(jobRoot, 'spoof.png'), '<svg xmlns="http://www.w3.org/2000/svg"><image href="https://example.com/a"/></svg>');
  await assert.rejects(validateLocalInputs(timeline), /does not match/);
  await fs.writeFile(path.join(externalRoot, 'source.png'), Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'));
  await fs.symlink(externalRoot, path.join(jobRoot, 'escape'), process.platform === 'win32' ? 'junction' : 'dir');
  timeline.shots[0].asset_src = `videoagents/${jobId}/escape/source.png`;
  await assert.rejects(validateLocalInputs(timeline), /escape its own job directory/);
});
