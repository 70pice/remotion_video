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
import {ffmpegExecutable, main, outputScale, parseArgs, resolvePreviewFrameRange, selectCoverFrame, snapshotBuiltInAssets, validateLocalInputs} from '../../scripts/render-timeline.mjs';
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

const focusFixture = (component = 'evidence') => {
  const timeline = fixture();
  const instruction = '圈出关键原文';
  Object.assign(timeline, {duration_in_frames: 120, presentation: 'component_sample'});
  Object.assign(timeline.shots[0], {component_id: component, end_frame: 120, source_label: '',
    asset_src: `videoagents/test-job/source.${component === 'video' ? 'mp4' : 'png'}`,
    props: {focus_source_size: {width: 1600, height: 1600}, focus_steps: [
      {start_frame: 0, end_frame: 60, instruction, target: {x: 0.1, y: 0.2, width: 0.6, height: 0.1}},
      {start_frame: 60, end_frame: 120, instruction: '放大查看', target: {x: 0.3, y: 0.5, width: 0.5, height: 0.2}},
    ]}, layers: [{component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 120,
      title: instruction, body: '', accent_color: '#FB923C', props: {}}]});
  return timeline;
};

test('material focus keeps supplied title and targets synchronized on supported media', () => {
  for (const component of ['video', 'evidence', 'image_focus', 'Talkcraft-tilt-3d-page']) {
    const value = focusFixture(component);
    assert.equal(validateTimeline(value), value);
  }
  for (const mutate of [
    (s) => {s.props.focus_steps[1].start_frame = 59;},
    (s) => {s.props.focus_steps[1].end_frame = 119;},
    (s) => {s.props.focus_steps[0].target.x = 0.9;},
    (s) => {s.layers[0].title = '不匹配';},
    (s) => {s.layers[0].end_frame = 119;},
    (s) => {s.props.focus_source_size.width = 0;},
    (s) => {s.props.crop = {x: 0, y: 0, width: 1, height: 1};},
    (s) => {s.props.asset_fit = 'cover';},
    (s) => {s.component_id = 'Bits-KenBurns';},
    (s) => {s.props.tutorial_steps = s.props.focus_steps;},
  ]) {
    const value = focusFixture();
    mutate(value.shots[0]);
    assert.throws(() => validateTimeline(value));
  }
});

test('focus layout fits both portrait recordings and wide figures, and crops stay within source', async (t) => {
  const {focusMediaBox, focusDetailCrop} = await importTypeScript(t, 'src/video-production/focusGeometry.ts');
  const {tutorialTargetRect, tutorialStepAt} = await importTypeScript(t, 'src/video-production/phoneTutorial.ts');
  assert.deepEqual(focusMediaBox({width: 720, height: 1440}), {width: 952, height: 1450});
  assert.deepEqual(focusMediaBox({width: 1600, height: 1600}), {width: 952, height: 952});
  const target = {x: 0.1, y: 0.2, width: 0.4, height: 0.1};
  const rect = tutorialTargetRect(target, {width: 720, height: 1440}, {width: 952, height: 1450});
  assert.deepEqual(rect, {x: 186, y: 290, width: 290, height: 145});
  for (const corner of [{x: 0, y: 0, width: 0.03, height: 0.03}, {x: 0.97, y: 0.97, width: 0.03, height: 0.03}, target]) {
    const crop = focusDetailCrop(corner);
    assert.ok(crop.x >= 0 && crop.y >= 0 && crop.x + crop.width <= 1 && crop.y + crop.height <= 1);
    assert.ok(crop.x <= corner.x && crop.y <= corner.y && crop.x + crop.width >= corner.x + corner.width && crop.y + crop.height >= corner.y + corner.height);
  }
  const steps = focusFixture().shots[0].props.focus_steps;
  assert.equal(tutorialStepAt(steps, 59).instruction, '圈出关键原文');
  assert.equal(tutorialStepAt(steps, 60).instruction, '放大查看');
  assert.equal(tutorialStepAt(steps, 120), undefined);
});

test('guided copy follows material and detail without overlap or a top title block', async (t) => {
  const {focusCompositionLayout, guidedMaterialTop, guidedTitleHeight, guidedPhoneHeight, guidedPhoneTitleTop} =
    await importTypeScript(t, 'src/video-production/focusGeometry.ts');
  const detailTarget = {x: 0.1, y: 0.2, width: 0.4, height: 0.1};
  for (const [source, video] of [[{width: 720, height: 1440}, true],
    [{width: 1600, height: 1600}, false], [{width: 1448, height: 1086}, false]]) {
    for (const target of [detailTarget, {x: 0, y: 0, width: 1, height: 1}]) {
      const layout = focusCompositionLayout(source, target, video);
      const materialBottom = guidedMaterialTop + layout.media.height;
      const finalMaterialBottom = layout.detail ? layout.detail.top + layout.detail.labelHeight + layout.detail.height : materialBottom;
      assert.ok(layout.titleTop >= finalMaterialBottom + 28);
      assert.ok(layout.titleTop + guidedTitleHeight <= 1824);
      if (video || target.width * target.height > 0.7) assert.equal(layout.detail, null);
      if (layout.detail) assert.ok(layout.detail.top >= materialBottom + 28);
    }
  }
  assert.equal(guidedPhoneTitleTop, guidedMaterialTop + guidedPhoneHeight + 28);
  assert.ok(guidedPhoneTitleTop + guidedTitleHeight <= 1824);
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




test('component_sample presentation is silent while legacy production defaults stay unchanged', () => {
  const production = fixture();
  production.audio_src = 'videoagents/test-job/narration.mp3';
  production.captions = [{text: '默认生产仍允许字幕', start_ms: 0, end_ms: 1000}];
  assert.equal(validateTimeline(production), production);

  const sample = fixture();
  sample.presentation = 'component_sample';
  assert.equal(validateTimeline(sample), sample);

  const withAudio = structuredClone(sample);
  withAudio.audio_src = 'videoagents/test-job/narration.mp3';
  assert.throws(() => validateTimeline(withAudio), /component_sample presentation must be silent/);

  const withCaptions = structuredClone(sample);
  withCaptions.captions = [{text: '不应有字幕', start_ms: 0, end_ms: 1000}];
  assert.throws(() => validateTimeline(withCaptions), /component_sample presentation must not include captions/);

  const invalid = fixture();
  invalid.presentation = 'storyboard';
  assert.throws(() => validateTimeline(invalid), /presentation must be production or component_sample/);
});

test('native title layers must finish their reveal before the shot ends', () => {
  for (const [componentId, minimum] of [
    ['Talkcraft-typewriter-reveal', 150], ['Talkcraft-scribble-annotation', 120],
    ['Talkcraft-keyword-pop-highlight', 60], ['Talkcraft-title-demote-to-label', 105],
    ['Talkcraft-chip-grid-single-select', 150],
  ]) {
    const timeline = fixture();
    timeline.duration_in_frames = 180;
    timeline.shots[0].end_frame = 180;
    const role = ['Talkcraft-typewriter-reveal', 'Talkcraft-title-demote-to-label'].includes(componentId) ? 'title' : 'emphasis';
    timeline.shots[0].layers = [{component_id: componentId, role, start_frame: 0,
      end_frame: minimum - 1, title: '核实身份', body: '原有联系方式', accent_color: '#B7F36B', props: {items: ['继续充值', '核实身份']}}];
    assert.throws(() => validateTimeline(timeline), new RegExp(`at least ${minimum} frames`));
    timeline.shots[0].layers[0].end_frame = minimum;
    assert.doesNotThrow(() => validateTimeline(timeline));
  }
});

test('chip selection must identify one supplied option and cannot guess by substring', () => {
  const timeline = fixture();
  timeline.duration_in_frames = 180;
  timeline.shots[0].end_frame = 180;
  timeline.shots[0].layers = [{component_id: 'Talkcraft-chip-grid-single-select', role: 'emphasis',
    start_frame: 0, end_frame: 150, title: '先停下来', body: '', accent_color: '#B7F36B',
    props: {items: ['继续充值', '先停下来']}}];
  assert.doesNotThrow(() => validateTimeline(timeline));
  timeline.shots[0].layers[0].title = '充值';
  assert.throws(() => validateTimeline(timeline), /exactly match one unique option/);
  timeline.shots[0].layers[0].props.highlight = '先停下来';
  assert.doesNotThrow(() => validateTimeline(timeline));
  timeline.shots[0].layers[0].props.items = ['先停下来', '先停下来！'];
  assert.throws(() => validateTimeline(timeline), /exactly match one unique option/);
});

test('title layers use the semantic header slot without shrinking the whole scene', async () => {
  const source = await fs.readFile(path.join(root, 'src/video-production/adapters/layout.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  let width = 1080;
  let frame = 0;
  const nodeRequire = createRequire(import.meta.url);
  const imports = (name) => name === 'remotion' ? {
    useVideoConfig: () => ({width, height: width * 16 / 9, fps: 30, durationInFrames: 900}),
    useCurrentFrame: () => frame,
    spring,
  } : nodeRequire(name);
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  const {LayoutComponentSample, LayoutHeaderHeight, useLayout, SceneHeader} = module.exports;
  const Probe = () => {
    const layout = useLayout();
    return createElement('span', null, `${layout.contentHeight}/${layout.headerHeight}`);
  };
  const available = (inset) => renderToStaticMarkup(createElement(LayoutHeaderHeight.Provider,
    {value: inset}, createElement(Probe)));
  assert.equal(available(0), '<span>1260/260</span>');
  assert.equal(available(400), '<span>1260/400</span>');
  const sampleAvailable = (inset) => renderToStaticMarkup(createElement(LayoutComponentSample.Provider,
    {value: true}, createElement(LayoutHeaderHeight.Provider, {value: inset}, createElement(Probe))));
  assert.equal(sampleAvailable(0), '<span>1450/260</span>');
  assert.equal(sampleAvailable(400), '<span>1450/400</span>');
  width = 540;
  assert.equal(available(400), '<span>630/200</span>');
  const shot = {...fixture().shots[0], layers: [{role: 'title', start_frame: 15, end_frame: 90}]};
  const header = () => renderToStaticMarkup(createElement(LayoutHeaderHeight.Provider,
    {value: 400}, createElement(SceneHeader, {shot})));
  assert.match(header(), /visibility:visible/);
  frame = 15;
  assert.match(header(), /visibility:hidden/);
  frame = 90;
  assert.match(header(), /visibility:visible/);
});

test('shot layers validate safe local title and emphasis overlays without mutating legacy shots', () => {
  const timeline = fixture();
  timeline.shots[0].component_id = 'conclusion';
  timeline.shots[0].layers = [
    {
      component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 30,
      title: 'AI 在聊天', body: '主画面仍是真实素材', accent_color: '#38BDF8', props: {items: ['30秒Demo先看方向']},
    },
    {
      component_id: 'Snapcn-TextHighlight', role: 'emphasis', start_frame: 30, end_frame: 60,
      title: '真人接管', body: '', accent_color: '#B7F36B', props: {highlight: '视频聊天节点'},
    },
  ];
  const before = structuredClone(timeline);
  assert.equal(validateTimeline(timeline), timeline);
  assert.deepEqual(timeline, before);

  const legacy = fixture();
  const legacyBefore = structuredClone(legacy);
  assert.equal(validateTimeline(legacy), legacy);
  assert.deepEqual(legacy, legacyBefore, 'missing layers stays omitted for old timeline hashes');
});

test('shot layers reject unsafe props, generic components, short ranges and conflicting roles', () => {
  const withLayer = (layer) => {
    const timeline = fixture();
    timeline.shots[0].component_id = 'conclusion';
    timeline.shots[0].layers = [layer];
    return timeline;
  };
  assert.throws(() => validateTimeline(withLayer({
    component_id: 'title', role: 'title', start_frame: 0, end_frame: 30,
    title: '语义适配器层', body: '', accent_color: '#38BDF8', props: {},
  })), /native layer component/);
  assert.throws(() => validateTimeline(withLayer({
    component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 30,
    title: '危险参数', body: '', accent_color: '#38BDF8', props: {style: 'background:url(https://example.com/a.svg)'},
  })), /unsupported/);
  assert.throws(() => validateTimeline(withLayer({
    component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 29,
    title: '太短', body: '', accent_color: '#38BDF8', props: {},
  })), /at least 30 frames/);

  assert.throws(() => validateTimeline(withLayer({
    component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 30,
    title: 'This native title is far too long to remain readable', body: '', accent_color: '#38BDF8', props: {},
  })), /at most 32 characters/);
  assert.throws(() => validateTimeline(withLayer({
    component_id: 'Snapcn-TextRewrite', role: 'title', start_frame: 0, end_frame: 30,
    title: '改口', body: '', accent_color: '#38BDF8', props: {from_text: 'This previous wording is far too long to read'},
  })), /at most 32 characters/);
  const overlap = fixture();
  overlap.shots[0].component_id = 'conclusion';
  overlap.shots[0].layers = [
    {component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 45, title: '第一层', body: '', accent_color: '#38BDF8', props: {}},
    {component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 30, end_frame: 60, title: '第二层', body: '', accent_color: '#38BDF8', props: {}},
  ];
  assert.throws(() => validateTimeline(overlap), /duplicated|overlaps/);
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

test('all curated community presets are registered and accept safe material slots', () => {
  assert.equal(productionComponentIds.length, 196);
  assert.equal(communityComponentIds.length, 187);
  assert.ok(communityComponentIds.includes('RemotionUI-SocialClip'));
  assert.ok(communityComponentIds.includes('Rve-GalleryGrid'));
  assert.ok(communityComponentIds.includes('RenderComp-SocialReel'));
  const preset = fixture();
  preset.shots[0].component_id = 'Snapcn-TextReveal';
  preset.shots[0].asset_src = 'videoagents/test-job/assets/source.png';
  preset.shots[0].source_label = 'example.test';
  preset.shots[0].props = {
    content_mode: 'media',
    asset_fit: 'cover',
    asset_crop: {x: 0.1, y: 0.2, width: 0.7, height: 0.6},
    items: ['来自任务素材的一项', '来自当前旁白的一项'],
    metric: {label: '节省时间', value: '42%', detail: '测试来源'},
  };
  assert.equal(validateTimeline(preset), preset);
  const presetProps = structuredClone(preset);
  presetProps.shots[0].props = {src: 'https://example.com/payload.svg'};
  assert.throws(() => validateTimeline(presetProps), /unsupported/);
  const presetAsset = structuredClone(preset);
  presetAsset.shots[0].asset_src = 'videoagents/test-job/assets/source.svg';
  assert.throws(() => validateTimeline(presetAsset), /image or MP4 video/);
  const presetVideo = structuredClone(preset);
  presetVideo.shots[0].asset_src = 'videoagents/test-job/assets/source.mp4';
  presetVideo.shots[0].props = {content_mode: 'media', start_seconds: 1.2, end_seconds: 4.8, asset_fit: 'contain'};
  assert.equal(validateTimeline(presetVideo), presetVideo);
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

test('materialized curated presets map normalized shot materials into native scene props', async (t) => {
  const {
    materializedCommunityComponentIds,
    curatedScenePropsForShot,
  } = await importTypeScript(t, 'src/video-production/curatedMaterial.ts');
  assert.equal(materializedCommunityComponentIds.length, 35);
  assert.ok(materializedCommunityComponentIds.includes('RenderComp-ProductSpotlight'));
  assert.ok(materializedCommunityComponentIds.includes('RemotionUI-SocialClip'));
  assert.ok(!materializedCommunityComponentIds.includes('Snapcn-TextReveal'));

  const shot = {
    ...fixture().shots[0],
    component_id: 'RenderComp-ProductSpotlight',
    title: '把素材放进产品聚焦组件',
    body: '视频限制时长，图片限制大小，然后让组件自己展示。',
    asset_src: 'videoagents/test-job/assets/demo.mp4',
    accent_color: '#38BDF8',
    source_label: 'demo source',
    props: {
      asset_fit: 'cover',
      asset_crop: {x: 0.1, y: 0.2, width: 0.7, height: 0.6},
      start_seconds: 2,
      end_seconds: 7,
    },
  };
  const props = curatedScenePropsForShot(shot, true);
  assert.equal(props.layout, 'portrait');
  assert.equal(props.variant, 'product-spotlight');
  assert.equal(props.title, shot.title);
  assert.equal(props.secondary, shot.body);
  assert.equal(props.accent, '#38BDF8');
  assert.deepEqual(props.material, {
    src: shot.asset_src,
    kind: 'video',
    fit: 'cover',
    crop: shot.props.asset_crop,
    startSeconds: 2,
    endSeconds: 7,
  });

  const listShot = {
    ...fixture().shots[0],
    component_id: 'Rve-AnimatedList',
    title: '这个团伙分三层',
    body: '',
    asset_src: null,
    source_label: '浦东警方',
    props: {items: ['技术开发', '运营策划', '聊天推广：俗称“聊手”']},
  };
  assert.deepEqual(curatedScenePropsForShot(listShot, false).items, ['技术开发', '运营策划', '聊天推广：俗称“聊手”']);

  const noItemsShot = {...listShot, props: {}};
  assert.deepEqual(curatedScenePropsForShot(noItemsShot, true).items, []);
});

test('context examples keep their visible source and do not mutate legacy shots', () => {
  const legacy = fixture();
  const before = JSON.stringify(legacy);
  validateTimeline(legacy);
  assert.equal(JSON.stringify(legacy), before);
  const current = fixture();
  Object.assign(current.shots[0], {component_id: 'Snapcn-PhoneFrame', asset_src: 'videoagents/test-job/assets/profile.png',
    media_usage: 'context_example', source_label: '另案示例｜thepaper.cn｜警方供图', props: {content_mode: 'media'}});
  validateTimeline(current);
  assert.equal(current.shots[0].media_usage, 'context_example');
  for (const change of [{source_label: 'thepaper.cn'}, {source_label: '另案示例'}, {component_id: 'evidence'},
    {asset_src: null}, {media_usage: 'unrestricted'}]) {
    const invalid = structuredClone(current);
    Object.assign(invalid.shots[0], change);
    assert.throws(() => validateTimeline(invalid));
  }
});


test('Snapcn phone frame renders real screen media through native phone body', async (t) => {
  const tutorial = await importTypeScript(t, 'src/video-production/phoneTutorial.ts');
  const focus = await importTypeScript(t, 'src/video-production/focusGeometry.ts');
  const source = await fs.readFile(path.join(root, 'src/video-production/PhoneFrameMaterial.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const nodeRequire = createRequire(import.meta.url);
  const imports = (name) => {
    if (name === 'remotion') return {
      Img: (props) => createElement('img', props),
      OffthreadVideo: ({trimBefore, trimAfter, ...props}) => createElement('video', {'data-trim-before': trimBefore, 'data-trim-after': trimAfter, ...props}),
      staticFile: (src) => `/static/${src}`,
      useVideoConfig: () => ({fps: 30, width: 1080, height: 1920, durationInFrames: 120}),
      useCurrentFrame: () => 45,
    };
    if (name === '../components/component-horizontal/snapcn/phone-frame') return {
      PhoneFrame: ({children, scale, screenSrc}) => createElement('section', {'data-phone-frame': 'true', 'data-scale': scale, 'data-screen-src': screenSrc ?? ''}, children),
    };
    if (name === './adapters/layout') return {
      FittedText: ({text}) => createElement('span', null, text),
      muted: '#A8B6CB',
      productionFont: 'TestFont',
      useLayout: () => ({unit: 1, vertical: true, margin: 72, contentWidth: 936}),
      white: '#fff',
    };
    if (name === './phoneTutorial') return tutorial;
    if (name === './focusGeometry') return focus;
    return nodeRequire(name);
  };
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  const {PhoneFrameMaterial} = module.exports;
  const shot = {
    shot_id: 'phone', start_frame: 0, end_frame: 90, component_id: 'Snapcn-PhoneFrame',
    title: '充值界面先出现', body: '', asset_src: 'videoagents/test-job/assets/chat.mp4',
    source_label: '另案示例｜thepaper.cn｜浦东警方供图', accent_color: '#B7F36B',
    props: {asset_fit: 'cover', asset_crop: {x: 0.1, y: 0.2, width: 0.5, height: 0.6}, start_seconds: 1.2, end_seconds: 4.4},
  };

  const markup = renderToStaticMarkup(createElement(PhoneFrameMaterial, {shot}));

  assert.match(markup, /data-phone-frame="true"/);
  assert.match(markup, /data-scale="1.55"/);
  assert.match(markup, /<video/);
  assert.match(markup, /src="\/static\/videoagents\/test-job\/assets\/chat.mp4"/);
  assert.match(markup, /data-trim-before="36"/);
  assert.match(markup, /data-trim-after="132"/);
  assert.match(markup, /left:-20%/);
  assert.match(markup, /top:-33.333333333333336%/);
  assert.match(markup, /width:200%/);
  assert.match(markup, /height:166.66666666666669%/);
  assert.ok(markup.includes('充值界面先出现'));
  assert.ok(markup.includes('另案示例｜thepaper.cn｜浦东警方供图'));
  assert.equal(markup.includes('live material'), false);
  assert.equal(markup.includes('PHONE FRAME'), false);
  const guided = {...shot, props: {content_mode: 'media', asset_fit: 'contain',
    tutorial_source_size: {width: 720, height: 1440}, tutorial_steps: [
      {start_frame: 0, end_frame: 30, instruction: '输入事项', target: {x: 0.1, y: 0.2, width: 0.8, height: 0.08}},
      {start_frame: 30, end_frame: 90, instruction: '点保存', target: {x: 0.1, y: 0.35, width: 0.3, height: 0.06}},
    ]}};
  const guidedMarkup = renderToStaticMarkup(createElement(PhoneFrameMaterial, {shot: guided}));
  assert.match(guidedMarkup, /data-scale="2.05"/);
  assert.match(guidedMarkup, /top:96px;height:1350px/);
  assert.match(guidedMarkup, /data-tutorial-target="点保存"/);
  assert.doesNotMatch(guidedMarkup, /data-tutorial-target="输入事项"/);
  assert.match(guidedMarkup, /viewBox="0 0 296 632"/);
  assert.match(guidedMarkup, /fill="none" stroke="#FB923C"/);
});

test('tutorial targeting accounts for contain letterboxing and half-open action boundaries', async (t) => {
  const {tutorialTargetRect, tutorialStepAt} = await importTypeScript(t, 'src/video-production/phoneTutorial.ts');
  const target = tutorialTargetRect({x: 0.25, y: 0.25, width: 0.5, height: 0.5}, {width: 720, height: 1440});
  assert.deepEqual(target, {x: 74, y: 168, width: 148, height: 296});
  const steps = [{start_frame: 0, end_frame: 60, instruction: '输入'}, {start_frame: 60, end_frame: 120, instruction: '保存'}];
  assert.equal(tutorialStepAt(steps, 59).instruction, '输入');
  assert.equal(tutorialStepAt(steps, 60).instruction, '保存');
  assert.equal(tutorialStepAt(steps, 120), undefined);
});

test('guided phone tutorials reject mismatched source, timings and targets', () => {
  const timeline = fixture();
  timeline.duration_in_frames = 120;
  Object.assign(timeline.shots[0], {end_frame: 120, component_id: 'Snapcn-PhoneFrame', asset_src: 'videoagents/test-job/assets/tutorial.mp4',
    props: {content_mode: 'media', asset_fit: 'contain', tutorial_source_size: {width: 720, height: 1440}, tutorial_steps: [
      {start_frame: 0, end_frame: 60, instruction: '输入事项', target: {x: 0.1, y: 0.2, width: 0.8, height: 0.08}},
      {start_frame: 60, end_frame: 120, instruction: '点保存', target: {x: 0.1, y: 0.4, width: 0.3, height: 0.06}},
    ]}, layers: [{component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 120,
      title: '输入事项', body: '', accent_color: '#FB923C', props: {}}]});
  assert.doesNotThrow(() => validateTimeline(timeline));
  for (const mutate of [
    (item) => { item.shots[0].props.tutorial_steps[1].start_frame = 59; },
    (item) => { item.shots[0].props.tutorial_steps[1].start_frame = 61; },
    (item) => { item.shots[0].props.tutorial_steps[1].end_frame = 119; },
    (item) => { item.shots[0].props.tutorial_steps[0].target.width = 0.95; },
    (item) => { item.shots[0].props.tutorial_steps[0].target.x = NaN; },
    (item) => { item.shots[0].props.asset_fit = 'cover'; },
    (item) => { item.shots[0].asset_src = 'videoagents/test-job/assets/still.png'; },
    (item) => { item.shots[0].component_id = 'Bits-KenBurns'; },
    (item) => { item.shots[0].layers[0].title = '保存'; },
    (item) => { item.width = 1920; item.height = 1080; },
  ]) {
    const invalid = structuredClone(timeline);
    mutate(invalid);
    assert.throws(() => validateTimeline(invalid));
  }
});


test('production community materials do not expose implementation labels or demo presets behind real assets', async () => {
  const source = await fs.readFile(path.join(root, 'src/video-production/VideoFromTimeline.tsx'), 'utf8');

  for (const forbidden of ['live material', 'workspace material', 'DEVICE FRAME', 'MATERIAL CARD', 'PHONE FRAME']) {
    assert.equal(source.includes(forbidden), false, `${forbidden} must not be production copy`);
  }
  assert.equal(source.includes('resolveCommunityPreset'), false);
  assert.equal(source.includes('<Freeze'), false);
  assert.match(source, /<CommunityNativeMaterial shot=\{shot\} durationInFrames=\{shot\.end_frame - shot\.start_frame\} \/>/);
});


test('curated social reel material shows one clear screenshot without demo caption or ambient duplicate', async () => {
  const source = await fs.readFile(path.join(root, 'src/components/component-horizontal/curated/CuratedScene.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const nodeRequire = createRequire(import.meta.url);
  const imports = (name) => name === 'remotion' ? {
    AbsoluteFill: (props) => createElement('div', props, props?.children),
    Img: (props) => createElement('img', props),
    OffthreadVideo: (props) => createElement('video', props),
    staticFile: (src) => `/static/${src}`,
    useCurrentFrame: () => 45,
    useVideoConfig: () => ({fps: 30, width: 1080, height: 1920, durationInFrames: 120}),
  } : nodeRequire(name);
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  const {CuratedScene} = module.exports;
  const material = {src: 'videoagents/test-job/assets/app.png', kind: 'image', fit: 'cover'};

  const production = renderToStaticMarkup(createElement(CuratedScene, {
    variant: 'social-reel', layout: 'portrait', title: '先看充值界面', kicker: '另案示例', accent: '#FACC15', material,
  }));
  const demo = renderToStaticMarkup(createElement(CuratedScene, {
    variant: 'social-reel', layout: 'portrait', title: 'Demo title', kicker: 'Demo', accent: '#FACC15',
  }));

  assert.equal((production.match(/<img/g) ?? []).length, 1);
  assert.match(production, /right:104px;top:500px/);
  assert.match(production, /width:872px;height:850px/);
  assert.match(production, /src="\/static\/videoagents\/test-job\/assets\/app.png"/);
  assert.equal(production.includes('Caption synced from material'), false);
  assert.equal(production.includes('repeating-linear-gradient'), false);
  assert.equal(demo.includes('Caption synced from material'), true);
  assert.equal(demo.includes('repeating-linear-gradient'), true);
});

test('curated animated lists render production supplied labels in both layouts', async () => {
  const source = await fs.readFile(path.join(root, 'src/components/component-horizontal/curated/CuratedScene.tsx'), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const nodeRequire = createRequire(import.meta.url);
  let config = {fps: 30, width: 1280, height: 720, durationInFrames: 120};
  const passthrough = (name) => (props) => createElement(name, props, props?.children);
  const imports = (name) => name === 'remotion' ? {
    AbsoluteFill: passthrough('div'),
    Img: passthrough('img'),
    OffthreadVideo: passthrough('video'),
    staticFile: (src) => src,
    useCurrentFrame: () => 45,
    useVideoConfig: () => config,
  } : nodeRequire(name);
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  const {CuratedScene} = module.exports;
  const labels = ['技术开发', '运营策划', '聊天推广：俗称“聊手”'];
  const props = {
    variant: 'animated-list',
    title: '这个团伙分三层',
    kicker: '浦东警方',
    accent: '#FACC15',
    items: labels,
  };

  for (const [layout, size] of [
    ['landscape', {width: 1280, height: 720}],
    ['portrait', {width: 1080, height: 1920}],
  ]) {
    config = {fps: 30, durationInFrames: 120, ...size};
    const markup = renderToStaticMarkup(createElement(CuratedScene, {...props, layout}));
    for (const label of labels) assert.ok(markup.includes(label), `${layout} markup missed ${label}`);
    for (const demoLabel of ['hook', 'evidence', 'edit', 'publish']) {
      assert.ok(!markup.includes(`>${demoLabel}</span>`), `${layout} markup kept demo label ${demoLabel}`);
    }
  }
});

test('all community presets route to a native material surface instead of generic overlay', async (t) => {
  const {
    communityMaterialSurfaceForComponentId,
  } = await importTypeScript(t, 'src/video-production/communityMaterial.ts');
  const surfaces = communityComponentIds.map((componentId) => communityMaterialSurfaceForComponentId(componentId));
  assert.equal(communityComponentIds.length, 187);
  assert.equal(surfaces.length, communityComponentIds.length);
  assert.ok(surfaces.every((surface) => typeof surface === 'string' && surface.length > 0));
  assert.ok(new Set(surfaces).size >= 7);
  assert.equal(communityMaterialSurfaceForComponentId('Snapcn-TextReveal'), 'text');
  assert.equal(communityMaterialSurfaceForComponentId('Rve-GalleryGrid'), 'gallery');
  assert.equal(communityMaterialSurfaceForComponentId('Rve-PictureInPicture'), 'pip');
  assert.equal(communityMaterialSurfaceForComponentId('RemotionUI-DeviceMockup3D'), 'device');
  assert.equal(communityMaterialSurfaceForComponentId('Snapcn-PromptSend'), 'workspace');
  assert.equal(communityMaterialSurfaceForComponentId('Talkcraft-terminal-typing-log'), 'workspace');
  assert.equal(communityMaterialSurfaceForComponentId('Talkcraft-reticle-lock-on'), 'reveal');
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

test('preview render frame ranges stay half-open and capped at thirty seconds', () => {
  const location = path.join(os.tmpdir(), 'video agents test');
  const cli = (...extra) => parseArgs(['--timeline', path.join(location, 'timeline.json'),
    '--output', path.join(location, 'clip.mp4'), '--mode', 'preview', ...extra]);
  const longTimeline = {...fixture(), duration_in_frames: 1800};
  assert.deepEqual(resolvePreviewFrameRange(longTimeline, cli()), {
    startFrame: 0,
    endFrame: 900,
    remotionFrameRange: [0, 899],
  });
  const shortTimeline = {...fixture(), duration_in_frames: 120};
  assert.deepEqual(resolvePreviewFrameRange(shortTimeline, cli()), {
    startFrame: 0,
    endFrame: 120,
    remotionFrameRange: [0, 119],
  });
  assert.deepEqual(resolvePreviewFrameRange(longTimeline, cli('--start-frame', '120', '--end-frame', '180')), {
    startFrame: 120,
    endFrame: 180,
    remotionFrameRange: [120, 179],
  });
  assert.equal(selectCoverFrame(longTimeline, {startFrame: 120, endFrame: 180}), 120);
  assert.equal(selectCoverFrame(longTimeline, {startFrame: 0, endFrame: 10}), 9);

  assert.throws(() => parseArgs(['--timeline', path.join(location, 'timeline.json'), '--output', path.join(location, 'clip.mp4'),
    '--mode', 'preview', '--start-frame', '0']), /provided together/);
  assert.throws(() => parseArgs(['--timeline', path.join(location, 'timeline.json'), '--output', path.join(location, 'clip.mp4'),
    '--mode', 'preview', '--end-frame', '30']), /provided together/);
  for (const value of ['1.5', '-1', 'abc']) {
    assert.throws(() => cli('--start-frame', value, '--end-frame', '30'), /nonnegative integer/);
  }
  assert.throws(() => cli('--start-frame', '30', '--end-frame', '30'), /greater than/);
  assert.throws(() => cli('--start-frame', '10', '--start-frame', '20', '--end-frame', '30'), /Usage/);
  assert.throws(() => resolvePreviewFrameRange(longTimeline, cli('--start-frame', '0', '--end-frame', '901')), /30 seconds/);
  assert.throws(() => resolvePreviewFrameRange(longTimeline, cli('--start-frame', '1799', '--end-frame', '1801')), /outside/);
  assert.throws(() => parseArgs(['--timeline', path.join(location, 'timeline.json'), '--output', path.join(location, 'clip.mp4'),
    '--mode', 'final', '--start-frame', '0', '--end-frame', '30']), /final render does not accept/);
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
  await execFileAsync(await ffmpegExecutable(), ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=18x12:d=4',
    '-an', '-pix_fmt', 'yuv420p', path.join(jobRoot, 'valid.mp4')]);
  timeline.shots[0].asset_src = `videoagents/${jobId}/valid.mp4`;
  timeline.shots[0].props = {start_seconds: 0.5, end_seconds: 3.6};
  const preflight = await validateLocalInputs(timeline);
  assert.deepEqual(preflight.videoMetadata[timeline.shots[0].asset_src], {width: 18, height: 12, duration: 4});
  await execFileAsync(await ffmpegExecutable(), ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=16x16:d=1',
    '-an', '-pix_fmt', 'yuv420p', path.join(jobRoot, 'tiny.mp4')]);
  timeline.shots[0].asset_src = `videoagents/${jobId}/tiny.mp4`;
  timeline.shots[0].props = {start_seconds: 0, end_seconds: 1};
  await assert.rejects(validateLocalInputs(timeline), /too short/);
  await execFileAsync(await ffmpegExecutable(), ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=12x24:d=4',
    '-an', '-pix_fmt', 'yuv420p', path.join(jobRoot, 'phone.mp4')]);
  Object.assign(timeline.shots[0], {component_id: 'Snapcn-PhoneFrame', asset_src: `videoagents/${jobId}/phone.mp4`,
    props: {content_mode: 'media', asset_fit: 'contain', start_seconds: 0, end_seconds: 3,
      tutorial_source_size: {width: 12, height: 24}, tutorial_steps: [
        {start_frame: 0, end_frame: 90, instruction: '点保存', target: {x: 0.1, y: 0.3, width: 0.3, height: 0.1}},
      ]}, layers: [{component_id: 'Snapcn-TextReveal', role: 'title', start_frame: 0, end_frame: 90,
      title: '点保存', body: '', accent_color: '#FB923C', props: {}}]});
  const phone = await validateLocalInputs(timeline);
  assert.deepEqual(phone.videoMetadata[timeline.shots[0].asset_src], {width: 12, height: 24, duration: 4});
  timeline.shots[0].props.tutorial_source_size.width = 10;
  await assert.rejects(validateLocalInputs(timeline), /dimensions must match/);
  timeline.shots[0].props.tutorial_source_size.width = 12;
  timeline.shots[0].props.start_seconds = 2;
  await assert.rejects(validateLocalInputs(timeline), /too short/);
});

test('focus preflight measures source dimensions instead of trusting image or video coordinates', async (t) => {
  const jobId = 'focus-preflight-' + randomUUID();
  const jobRoot = path.join(root, 'public', 'videoagents', jobId);
  await fs.mkdir(jobRoot, {recursive: true});
  t.after(async () => {
    assert.equal(path.dirname(jobRoot), path.join(root, 'public', 'videoagents'));
    assert.equal(path.basename(jobRoot), jobId);
    await fs.rm(jobRoot, {recursive: true, force: true});
  });
  const timeline = focusFixture();
  timeline.job_id = jobId;
  timeline.shots[0].asset_src = `videoagents/${jobId}/source.png`;
  await fs.writeFile(path.join(jobRoot, 'source.png'), Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=', 'base64'));
  await assert.rejects(validateLocalInputs(timeline), /dimensions must match measured media/);
  timeline.shots[0].props.focus_source_size = {width: 1, height: 1};
  await validateLocalInputs(timeline);
  await execFileAsync(await ffmpegExecutable(), ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=12x24:d=4',
    '-an', '-pix_fmt', 'yuv420p', path.join(jobRoot, 'source.mp4')]);
  Object.assign(timeline.shots[0], {component_id: 'video', asset_src: `videoagents/${jobId}/source.mp4`});
  await assert.rejects(validateLocalInputs(timeline), /dimensions must match measured media/);
  timeline.shots[0].props.focus_source_size = {width: 12, height: 24};
  await validateLocalInputs(timeline);
});
