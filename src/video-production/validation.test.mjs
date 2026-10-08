import assert from 'node:assert/strict';
import {Buffer} from 'node:buffer';
import {execFile} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import test from 'node:test';
import {promisify} from 'node:util';
import {fileURLToPath, pathToFileURL} from 'node:url';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {spring} from 'remotion';
import {main, outputScale, parseArgs, snapshotBuiltInAssets, validateLocalInputs} from '../../scripts/render-timeline.mjs';
import {communityComponentIds, productionComponentIds, validateTimeline} from './validation.mjs';

const {structuredClone} = globalThis;
const execFileAsync = promisify(execFile);

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const importTypeScript = async (t, relativePath) => {
  const sourcePath = path.join(root, relativePath);
  const temp = path.join(await fs.mkdtemp(path.join(await fs.realpath(os.tmpdir()), 'videoagents-ts-test-')), path.basename(relativePath).replace(/\.ts$/, '.mjs'));
  const source = await fs.readFile(sourcePath, 'utf8');
  const output = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022}}).outputText;
  await fs.writeFile(temp, output);
  t.after(async () => {
    assert.ok(path.basename(path.dirname(temp)).startsWith('videoagents-ts-test-'));
    await fs.rm(path.dirname(temp), {recursive: true, force: true});
  });
  return import(pathToFileURL(temp).href);
};
const fixture = () => ({
  schema_version: '1', job_id: 'test-job', revision: 1, width: 1080, height: 1920, fps: 30,
  duration_in_frames: 60, audio_src: null,
  shots: [{shot_id: 'a', start_frame: 0, end_frame: 60, component_id: 'title', title: '测试标题',
    body: '测试内容', asset_src: null, source_label: '明确标记的测试内容', accent_color: '#B7F36B', props: {}}],
  captions: [],
});

test('frozen render assets include fonts and media required by the component registry', async (t) => {
  const canonicalTemp = await fs.realpath(os.tmpdir());
  const snapshot = await fs.mkdtemp(path.join(canonicalTemp, 'videoagents-builtins-test-'));
  t.after(async () => {
    assert.equal(path.dirname(snapshot), canonicalTemp);
    assert.ok(path.basename(snapshot).startsWith('videoagents-builtins-test-'));
    await fs.rm(snapshot, {recursive: true, force: true});
  });
  await snapshotBuiltInAssets(snapshot);
  for (const relative of ['fonts/inter-latin-400-normal.woff2', 'fonts/source-serif-4-latin-600-normal.woff2', 'landscape.svg']) {
    assert.deepEqual(await fs.readFile(path.join(snapshot, 'community', relative)),
      await fs.readFile(path.join(root, 'public', 'community', relative)));
  }
  assert.deepEqual(await fs.readdir(snapshot), ['community']);
});

test('every production adapter accepts supplied content; data is never invented', () => {
  const cases = {
    title: {eyebrow: '测试'}, keyword: {keyword: '来自输入的关键词'},
    evidence: {highlight: {x: 0.2, y: 0.3, width: 0.4, height: 0.5}},
    image_focus: {focal_x: 0.2, focal_y: 0.8, crop: {x: 0.15, y: 0.25, width: 0.5, height: 0.4}},
    comparison: {left_title: '输入 A', left_body: '明确的 A 内容', right_title: '输入 B', right_body: '明确的 B 内容'},
    data: {items: [{label: '用户提供的数据', value: '待核实', detail: '测试字段'}]},
    steps: {items: [{title: '读取输入', body: '来自调用者的步骤'}]}, conclusion: {call_to_action: '测试结束'},
    video: {start_seconds: 1.2, end_seconds: 4.8, fit: 'contain', crop: {x: 0.1, y: 0.2, width: 0.7, height: 0.6}},
  };
  for (const [component, props] of Object.entries(cases)) {
    const timeline = fixture();
    timeline.shots[0].component_id = component;
    timeline.shots[0].props = props;
    if (['evidence', 'image_focus'].includes(component)) timeline.shots[0].asset_src = 'videoagents/test-job/source.png';
    if (component === 'video') timeline.shots[0].asset_src = 'videoagents/test-job/source.mp4';
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before, 'validation must not replace factual input or timestamps');
  }
});

test('semantic cues accept local frames and legacy props without rewriting facts', () => {
  for (const [component, props] of [
    ['data', {items: [{label: '价格', value: '20', reveal_frame: 0}, {label: '结果', value: '待核实', reveal_frame: 45}]}],
    ['steps', {layout: 'flow', items: [{title: '提出任务'}, {title: '检查结果', reveal_frame: 45}]}],
    ['comparison', {left_title: '之前', left_body: '过程', right_title: '之后', right_body: '结果', right_reveal_frame: 45}],
  ]) {
    const timeline = fixture();
    Object.assign(timeline.shots[0], {component_id: component, props});
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before);
  }
});

test('data visualizations validate chart fields without rewriting facts', () => {
  for (const props of [
    {visualization: 'cards', items: [{label: '价格', value: '20'}]},
    {visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 10, reference_value: 5,
      items: [{label: '用量', value: '4 倍', numeric_value: 4, reveal_frame: 0}]},
    {visualization: 'donuts', source_ref: 'https://example.com/report', unit: '%',
      items: [{label: '缓存', value: '86%', numeric_value: 86}, {label: '人工', value: '29%', numeric_value: 29, reveal_frame: 45}]},
  ]) {
    const timeline = fixture();
    Object.assign(timeline.shots[0], {component_id: 'data', props});
    if (props.visualization !== 'cards') timeline.shots[0].source_label = '来源';
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before);
  }
});

test('data visualizations reject unsafe chart field combinations', () => {
  const invalidCases = [
    [{items: [{label: '价格', value: '20', numeric_value: 20}]}, /unsupported/],
    [{visualization: 'cards', source_ref: 'https://example.com/report', items: [{label: '价格', value: '20'}]}, /source_ref/],
    [{visualization: 'cards', unit: '倍', items: [{label: '价格', value: '20'}]}, /unit/],
    [{visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 10,
      items: [{label: '用量', value: '4 倍'}]}, /numeric_value/],
    [{visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 10,
      items: [{label: '用量', value: '4 倍', numeric_value: '4'}]}, /numeric_value/],
    [{visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 10,
      items: [{label: '用量', value: '4 倍', numeric_value: true}]}, /numeric_value/],
    [{visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 3,
      items: [{label: '用量', value: '4 倍', numeric_value: 4}]}, /numeric_value/],
    [{visualization: 'bars', source_ref: 'https://example.com/report', unit: 'x'.repeat(25), scale_max: 10,
      items: [{label: '用量', value: '4 倍', numeric_value: 4}]}, /unit/],
    [{visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 10, reference_value: 11,
      items: [{label: '用量', value: '4 倍', numeric_value: 4}]}, /reference_value/],
    [{visualization: 'donuts', source_ref: 'https://example.com/report', unit: '倍',
      items: [{label: '缓存', value: '86%', numeric_value: 86}]}, /unit/],
    [{visualization: 'donuts', source_ref: 'https://example.com/report', unit: '%', scale_max: 100,
      items: [{label: '缓存', value: '86%', numeric_value: 86}]}, /scale_max/],
    [{visualization: 'donuts', source_ref: 'https://example.com/report', unit: '%',
      items: [{label: '缓存', value: '101%', numeric_value: 101}]}, /numeric_value/],
    [{visualization: 'donuts', source_ref: 'https://example.com/report', unit: '%',
      items: [{label: '一', value: '1%', numeric_value: 1}, {label: '二', value: '2%', numeric_value: 2}, {label: '三', value: '3%', numeric_value: 3}]}, /donuts/],
    [{visualization: 'bars', source_ref: 'not-a-url', unit: '倍', scale_max: 10,
      items: [{label: '用量', value: '4 倍', numeric_value: 4}]}, /HTTP\/HTTPS/],
  ];
  for (const [props, message] of invalidCases) {
    const timeline = fixture();
    Object.assign(timeline.shots[0], {component_id: 'data', source_label: '来源', props});
    assert.throws(() => validateTimeline(timeline), message);
  }
  const missingLabel = fixture();
  Object.assign(missingLabel.shots[0], {
    component_id: 'data',
    source_label: '',
    props: {visualization: 'bars', source_ref: 'https://example.com/report', unit: '倍', scale_max: 10,
      items: [{label: '用量', value: '4 倍', numeric_value: 4}]},
  });
  assert.throws(() => validateTimeline(missingLabel), /source label/);
});

test('image focus cues accept overview-focus-overview sequences without rewriting facts', () => {
  for (const component of ['evidence', 'image_focus']) {
    const timeline = fixture();
    Object.assign(timeline.shots[0], {
      component_id: component,
      asset_src: 'videoagents/test-job/source.png',
      source_label: '来源',
      props: {focus_cues: [
        {frame: 0, label: '总览'},
        {frame: 20, region: {x: 0.1, y: 0.2, width: 0.45, height: 0.35}, label: '重点'},
        {frame: 40},
      ]},
    });
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before);
  }
});

test('image focus cues reject invalid shape, timing, conflicts and labels', () => {
  const invalidCases = [
    ['evidence', {focus_cues: [{frame: 46}]}, /integer/],
    ['evidence', {focus_cues: [{frame: true}]}, /integer/],
    ['evidence', {focus_cues: [{frame: Number.NaN}]}, /integer/],
    ['image_focus', {focus_cues: [{frame: 0}, {frame: 0}]}, /strictly increasing/],
    ['image_focus', {focus_cues: [{frame: 0}, {frame: 10}, {frame: 5}]}, /strictly increasing/],
    ['evidence', {focus_cues: [{frame: 10}]}, /must be 0/],
    ['evidence', {focus_cues: [{frame: 0, extra: 'bad'}]}, /unsupported/],
    ['evidence', {focus_cues: [{frame: 0}], highlight: {x: 0, y: 0, width: 1, height: 1}}, /cannot be mixed/],
    ['image_focus', {focus_cues: [{frame: 0}], crop: {x: 0, y: 0, width: 1, height: 1}}, /cannot be mixed/],
    ['image_focus', {focus_cues: [{frame: 0}], focal_x: 0.5}, /cannot be mixed/],
    ['evidence', {focus_cues: [{frame: 0, label: '字'.repeat(25)}]}, /at most 24/],
    ['evidence', {focus_cues: {frame: 0}}, /1 to 8/],
    ['evidence', {focus_cues: []}, /1 to 8/],
    ['evidence', {focus_cues: [{frame: 0, region: {x: 0.8, y: 0, width: 0.3, height: 1}}]}, /inside the image/],
  ];
  for (const [component, props, message] of invalidCases) {
    const timeline = fixture();
    Object.assign(timeline.shots[0], {
      component_id: component,
      asset_src: 'videoagents/test-job/source.png',
      source_label: '来源',
      props,
    });
    assert.throws(() => validateTimeline(timeline), message);
  }
});

test('semantic cues reject invalid frame types, late cues and unordered item reveals', () => {
  for (const cue of [-1, 46, 1.5, true, '10', null]) {
    for (const component of ['data', 'steps', 'comparison']) {
      const timeline = fixture();
      timeline.shots[0].component_id = component;
      timeline.shots[0].props = component === 'comparison'
        ? {left_title: '之前', left_body: '过程', right_title: '之后', right_body: '结果', right_reveal_frame: cue}
        : {items: [component === 'data' ? {label: '价格', value: '20', reveal_frame: cue} : {title: '检查', reveal_frame: cue}]};
      assert.throws(() => validateTimeline(timeline), /integer/);
    }
  }
  for (const lastCue of [undefined, 5]) {
    const timeline = fixture();
    timeline.shots[0].component_id = 'steps';
    timeline.shots[0].props = {items: [{title: '第一步', reveal_frame: 10}, {title: '第二步', ...(lastCue === undefined ? {} : {reveal_frame: lastCue})}]};
    assert.throws(() => validateTimeline(timeline), /nondecreasing/);
  }
  const timeline = fixture();
  timeline.shots[0].component_id = 'steps';
  timeline.shots[0].props = {items: [{title: '检查'}], layout: 'horizontal'};
  assert.throws(() => validateTimeline(timeline), /cards or flow/);
});

test('explicit reveals stay hidden before the measured cue and finish within 15 frames', async () => {
  const source = await fs.readFile(path.join(root, 'src/video-production/adapters/layout.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  let frame = 0;
  const nodeRequire = createRequire(import.meta.url);
  const imports = (name) => name === 'remotion' ? {
    spring,
    useCurrentFrame: () => frame,
    useVideoConfig: () => ({fps: 30, width: 1080, height: 1920, durationInFrames: 300}),
  } : nodeRequire(name);
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  const {CuedMotion, Motion} = module.exports;
  const markup = (component, props = {}) => renderToStaticMarkup(createElement(component, props, 'supplied result'));
  frame = 0;
  const opening = markup(CuedMotion, {revealFrame: 120});
  assert.match(opening, /visibility:hidden;opacity:0/);
  frame = 119;
  assert.equal(markup(CuedMotion, {revealFrame: 120}), opening, 'the cue must not be clamped to an opening delay');
  frame = 121;
  const firstVisible = markup(CuedMotion, {revealFrame: 120});
  assert.match(firstVisible, /visibility:visible;/);
  const opacity = Number(firstVisible.match(/opacity:([\d.]+)/)[1]);
  assert.ok(opacity > 0 && opacity < 1);
  frame = 134;
  assert.match(markup(CuedMotion, {revealFrame: 120}), /visibility:visible;opacity:1;/);
  assert.equal(markup(CuedMotion, {delay: 8}), markup(Motion, {delay: 8}), 'omitted cues preserve the old animation exactly');
});

test('ASCII identifiers can request a fitted single line instead of orphan wrapping', async () => {
  const source = await fs.readFile(path.join(root, 'src/video-production/adapters/layout.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const nodeRequire = createRequire(import.meta.url);
  const imports = (name) => name === 'remotion' ? {
    spring,
    useCurrentFrame: () => 0,
    useVideoConfig: () => ({fps: 30, width: 1080, height: 1920, durationInFrames: 115}),
  } : nodeRequire(name);
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  const {FittedText} = module.exports;
  const markup = renderToStaticMarkup(createElement(FittedText, {
    text: 'DeepPlanning', width: 880, height: 800, fontSize: 128, minFontSize: 40,
    lineHeight: 1.18, preferSingleLine: true,
  }));
  assert.match(markup, /white-space:nowrap/);
  assert.match(markup, /overflow-wrap:normal/);
  const size = Number(markup.match(/font-size:([\d.]+)px/)[1]);
  assert.ok(size < 128 && size >= 40, `single-line identifier font size was ${size}`);
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
  assert.equal(productionComponentIds.length, 161);
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

test('video shots require local MP4 footage and valid trim, fit and crop props', () => {
  const timeline = fixture();
  Object.assign(timeline.shots[0], {
    component_id: 'video',
    asset_src: 'videoagents/test-job/clip.mp4',
    props: {start_seconds: 0, end_seconds: 2, fit: 'cover', crop: {x: 0.2, y: 0.1, width: 0.7, height: 0.8}},
  });
  assert.equal(validateTimeline(timeline), timeline);
  for (const [props, message] of [
    [{start_seconds: -0.1}, /start_seconds/],
    [{start_seconds: 3, end_seconds: 2}, /end_seconds/],
    [{fit: 'stretch'}, /fit/],
    [{crop: {x: 0.9, y: 0.1, width: 0.2, height: 0.5}}, /inside the video/],
  ]) {
    const bad = structuredClone(timeline);
    bad.shots[0].props = props;
    assert.throws(() => validateTimeline(bad), message);
  }
  const missingAsset = structuredClone(timeline);
  missingAsset.shots[0].asset_src = null;
  assert.throws(() => validateTimeline(missingAsset), /requires an MP4 video/);
  const imageAsset = structuredClone(timeline);
  imageAsset.shots[0].asset_src = 'videoagents/test-job/clip.png';
  assert.throws(() => validateTimeline(imageAsset), /requires an MP4 video/);
});

test('image_focus accepts optional crop while preserving focal-only behavior', () => {
  const timeline = fixture();
  Object.assign(timeline.shots[0], {
    component_id: 'image_focus',
    asset_src: 'videoagents/test-job/source.png',
    props: {focal_x: 0.2, focal_y: 0.8},
  });
  const before = structuredClone(timeline);
  assert.equal(validateTimeline(timeline), timeline);
  assert.deepEqual(timeline, before);

  timeline.shots[0].props = {crop: {x: 0.25, y: 0.1, width: 0.5, height: 0.8}};
  assert.equal(validateTimeline(timeline), timeline);

  for (const props of [
    {crop: {x: 0.8, y: 0.1, width: 0.3, height: 0.5}},
    {crop: {x: 0, y: 0, width: 0, height: 1}},
    {crop: {x: 0, y: 0, width: 1}},
  ]) {
    const bad = structuredClone(timeline);
    bad.shots[0].props = props;
    assert.throws(() => validateTimeline(bad), /inside the image|unsupported|number between 0 and 1/);
  }
});

test('video crop geometry preserves the real source aspect ratio for contain and cover', async (t) => {
  const {resolveVideoCropGeometry} = await importTypeScript(t, 'src/video-production/adapters/videoGeometry.ts');
  const close = (actual, expected) => assert.ok(Math.abs(actual - expected) < 0.001, `${actual} ≈ ${expected}`);
  const source = {width: 960, height: 836};
  const phoneCrop = {x: 295 / 960, y: 22 / 836, width: 370 / 960, height: 792 / 836};
  const phone = resolveVideoCropGeometry({viewportWidth: 936, viewportHeight: 950, metadata: source, crop: phoneCrop, fit: 'contain'});
  close(phone.window.width / phone.window.height, 370 / 792);
  close(phone.media.width / phone.media.height, 960 / 836);
  close(-phone.media.left / phone.media.width, phoneCrop.x);
  close(-phone.media.top / phone.media.height, phoneCrop.y);
  assert.equal(phone.window.height, 950);
  assert.ok(phone.window.left > 240 && phone.window.left < 250);

  const wideContain = resolveVideoCropGeometry({viewportWidth: 936, viewportHeight: 950, metadata: {width: 1920, height: 1080, duration: 8}, fit: 'contain'});
  close(wideContain.window.width, 936);
  close(wideContain.window.height, 526.5);
  assert.ok(wideContain.window.top > 211 && wideContain.window.top < 212);
  close(wideContain.media.width / wideContain.media.height, 1920 / 1080);

  const wideCover = resolveVideoCropGeometry({viewportWidth: 936, viewportHeight: 950, metadata: {width: 1920, height: 1080, duration: 8}, fit: 'cover'});
  close(wideCover.window.height, 950);
  assert.ok(wideCover.window.width > 1688 && wideCover.window.left < 0);
  close(wideCover.media.width / wideCover.media.height, 1920 / 1080);
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

test('dense word-level captions are grouped into stable readable display pages without mutating input', async (t) => {
  const {buildCaptionPages} = await importTypeScript(t, 'src/video-production/captionPages.ts');
  const captions = [
    {text: 'M', start_ms: 0, end_ms: 80}, {text: 'u', start_ms: 80, end_ms: 150},
    {text: 's', start_ms: 150, end_ms: 220}, {text: 'e', start_ms: 220, end_ms: 300},
    {text: '是', start_ms: 340, end_ms: 430}, {text: '什', start_ms: 430, end_ms: 520},
    {text: '么', start_ms: 520, end_ms: 610}, {text: '？', start_ms: 610, end_ms: 700},
    {text: '它', start_ms: 820, end_ms: 930}, {text: '能', start_ms: 930, end_ms: 1040},
    {text: '帮', start_ms: 1040, end_ms: 1150}, {text: '你', start_ms: 1150, end_ms: 1260},
    {text: '做', start_ms: 1260, end_ms: 1370}, {text: '事', start_ms: 1370, end_ms: 1480},
    {text: '。', start_ms: 1480, end_ms: 1560},
  ];
  const before = structuredClone(captions);
  const pages = buildCaptionPages(captions, {maxChars: 20});
  assert.deepEqual(captions, before);
  assert.deepEqual(pages, [{text: 'Muse是什么？', start_ms: 0, end_ms: 700}, {text: '它能帮你做事。', start_ms: 820, end_ms: 1560}]);
});

test('caption grouping does not cross long gaps or shot boundaries', async (t) => {
  const {buildCaptionPages} = await importTypeScript(t, 'src/video-production/captionPages.ts');
  const captions = [
    {text: '第', start_ms: 0, end_ms: 100}, {text: '一', start_ms: 100, end_ms: 200},
    {text: '段', start_ms: 200, end_ms: 300}, {text: '第', start_ms: 900, end_ms: 1000},
    {text: '二', start_ms: 1000, end_ms: 1100}, {text: '段', start_ms: 1100, end_ms: 1200},
    {text: '切', start_ms: 1880, end_ms: 1960}, {text: '镜', start_ms: 2060, end_ms: 2140},
  ];
  const pages = buildCaptionPages(captions, {
    boundaries: [{start_ms: 0, end_ms: 2000}, {start_ms: 2000, end_ms: 4000}],
  });
  assert.deepEqual(pages.map((item) => item.text), ['第一段', '第二段', '切', '镜']);
  assert.ok(pages[1].end_ms <= 2000);
  assert.ok(pages[2].start_ms < 2000 && pages[2].end_ms <= 2000);
  assert.ok(pages[3].start_ms >= 2000);
});

test('complete sentence captions keep their original text and timing instead of fabricated splits', async (t) => {
  const {buildCaptionPages} = await importTypeScript(t, 'src/video-production/captionPages.ts');
  const captions = [
    {text: 'Muse 是一个面向普通人的 AI 个人助手，它不是聊天框那么简单。', start_ms: 120, end_ms: 4120},
    {text: '下一句继续解释它为什么有用。', start_ms: 4300, end_ms: 6900},
  ];
  const pages = buildCaptionPages(captions, {maxChars: 10});
  assert.deepEqual(pages, captions);
});

test('caption grouping preserves source text order and avoids standalone flashing punctuation', async (t) => {
  const {buildCaptionPages} = await importTypeScript(t, 'src/video-production/captionPages.ts');
  const captions = [
    {text: '这', start_ms: 0, end_ms: 80}, {text: '不', start_ms: 80, end_ms: 160},
    {text: '是', start_ms: 160, end_ms: 240}, {text: '科', start_ms: 240, end_ms: 320},
    {text: '幻', start_ms: 320, end_ms: 400}, {text: '，', start_ms: 400, end_ms: 470},
    {text: '而', start_ms: 500, end_ms: 590}, {text: '是', start_ms: 590, end_ms: 680},
    {text: '现', start_ms: 680, end_ms: 770}, {text: '实', start_ms: 770, end_ms: 860},
    {text: '。', start_ms: 860, end_ms: 930},
  ];
  const pages = buildCaptionPages(captions);
  assert.equal(pages.map((item) => item.text).join(''), captions.map((item) => item.text).join(''));
  assert.ok(pages.every((item) => item.text !== '，' && item.text !== '。'));
  assert.ok(pages.some((item) => item.text.includes('，')));
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

test('video preflight rejects M4A-in-MP4 spoofing and clips shorter than their shot', async (t) => {
  const jobId = 'render-video-validation-' + randomUUID();
  const jobRoot = path.join(root, 'public', 'videoagents', jobId);
  await fs.mkdir(jobRoot, {recursive: true});
  t.after(async () => {
    assert.equal(path.basename(jobRoot), jobId);
    assert.equal(path.dirname(jobRoot), path.join(root, 'public', 'videoagents'));
    await fs.rm(jobRoot, {recursive: true, force: true});
  });
  const timeline = fixture();
  Object.assign(timeline, {job_id: jobId, fps: 30, duration_in_frames: 90});
  Object.assign(timeline.shots[0], {
    start_frame: 0, end_frame: 90, component_id: 'video',
    asset_src: `videoagents/${jobId}/audio-only.mp4`, props: {start_seconds: 0},
  });
  const audioOnly = Buffer.from('00000018667479704d344120000002004d3441206d7034320000000c6d6461746100000000', 'hex');
  await fs.writeFile(path.join(jobRoot, 'audio-only.mp4'), audioOnly);
  await assert.rejects(validateLocalInputs(timeline), /does not match its allowed format|audio-only MP4/);
  await execFileAsync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=18x12:d=4',
    '-an', '-pix_fmt', 'yuv420p', path.join(jobRoot, 'valid.mp4')]);
  timeline.shots[0].asset_src = `videoagents/${jobId}/valid.mp4`;
  timeline.shots[0].props = {start_seconds: 0.5, end_seconds: 3.6};
  const preflight = await validateLocalInputs(timeline);
  assert.deepEqual(preflight.videoMetadata[timeline.shots[0].asset_src], {width: 18, height: 12, duration: 4});
  await execFileAsync('ffmpeg', ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=16x16:d=1',
    '-an', '-pix_fmt', 'yuv420p', path.join(jobRoot, 'tiny.mp4')]);
  timeline.shots[0].asset_src = `videoagents/${jobId}/tiny.mp4`;
  timeline.shots[0].props = {start_seconds: 0, end_seconds: 1};
  await assert.rejects(validateLocalInputs(timeline), /too short/);
});
