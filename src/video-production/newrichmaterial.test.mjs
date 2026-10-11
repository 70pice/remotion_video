import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {materialRichNativeIdsForSet, materialRichSetComponents, validateTimeline} from './validation.mjs';

const {structuredClone} = globalThis;
const require = createRequire(import.meta.url);
const fixture = JSON.parse(await readFile(new URL('../../tests/fixtures/component-set-material-rich-content.json', import.meta.url), 'utf8'));

const mainBySet = Object.fromEntries(Object.entries(materialRichSetComponents).map(([setId, ids]) => [setId, ids[0]]));
const layerProps = (componentId, content) => {
  if (componentId === 'Talkcraft-ink-underline') return {highlight: content.takeaway, from_text: '只看单笔', to_text: content.takeaway};
  if (componentId === 'Snapcn-TextHighlight') return {highlight: content.takeaway};
  return {};
};
const focusSteps = [
  {instruction: '输入事项', start_frame: 0, end_frame: 115, target: {x: 0.108333, y: 0.275825, width: 0.783333, height: 0.061111}},
  {instruction: '点保存', start_frame: 115, end_frame: 179, target: {x: 0.108333, y: 0.353602, width: 0.277778, height: 0.054167}},
  {instruction: '查看列表', start_frame: 179, end_frame: 371, target: {x: 0.063889, y: 0.513889, width: 0.872222, height: 0.115278}},
];

const sample = (setId) => {
  const content = structuredClone(fixture[setId]);
  const duration = setId === 'A09' ? 371 : 540;
  const [main, titleComponent, emphasisComponent] = materialRichSetComponents[setId];
  return {
    schema_version: '1',
    job_id: 'material-rich-test',
    revision: 1,
    width: 1080,
    height: 1920,
    fps: 30,
    presentation: 'component_sample',
    duration_in_frames: duration,
    audio_src: null,
    captions: [],
    shots: [{
      shot_id: setId,
      start_frame: 0,
      end_frame: duration,
      component_id: main,
      title: content.title,
      body: content.body,
      source_label: `素材来源 · ${setId}`,
      asset_src: `videoagents/material-rich-test/${setId}.${setId === 'A09' ? 'mp4' : 'png'}`,
      accent_color: '#38BDF8',
      props: {
        component_set: setId,
        composition: 'rich',
        rich_content: content,
        ...(setId === 'A09' ? {focus_source_size: {width: 720, height: 1440}, focus_steps: structuredClone(focusSteps)} : {}),
      },
      layers: [
        {component_id: titleComponent, role: 'title', start_frame: 0, end_frame: duration,
          title: content.title, body: content.body, accent_color: '#38BDF8', props: {}},
        {component_id: emphasisComponent, role: 'emphasis', start_frame: Math.floor(duration * 0.62), end_frame: duration,
          title: content.takeaway, body: '', accent_color: '#38BDF8', props: layerProps(emphasisComponent, content)},
      ],
    }],
  };
};

test('A07-A12 material rich sets validate supplied content and expose seven actual native IDs', () => {
  for (const setId of Object.keys(materialRichSetComponents)) {
    const timeline = sample(setId);
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before);
    assert.equal(new Set(materialRichNativeIdsForSet(setId)).size, 7);
    assert.equal(materialRichNativeIdsForSet(setId)[0], mainBySet[setId]);
  }
});

test('material rich validation rejects invalid media, isolation extras, focus cues and numeric totals', () => {
  const videoInImageSet = sample('A07');
  videoInImageSet.shots[0].asset_src = 'videoagents/material-rich-test/A07.mp4';
  assert.throws(() => validateTimeline(videoInImageSet), /requires an image material/);

  const defaultPresetLeak = sample('A08');
  defaultPresetLeak.shots[0].props.content_mode = 'media';
  assert.throws(() => validateTimeline(defaultPresetLeak), /unsupported/);

  const badCue = sample('A09');
  badCue.shots[0].props.focus_steps[1].start_frame = 116;
  assert.throws(() => validateTimeline(badCue), /contiguous/);

  const badInstruction = sample('A09');
  badInstruction.shots[0].props.focus_steps[2].instruction = '默认文案';
  assert.throws(() => validateTimeline(badInstruction), /instruction must match/);

  const nonDefaultSourceSize = sample('A09');
  nonDefaultSourceSize.shots[0].props.focus_source_size = {width: 1080, height: 2160};
  assert.equal(validateTimeline(nonDefaultSourceSize), nonDefaultSourceSize);

  const badSum = sample('A10');
  badSum.shots[0].props.rich_content.numeric_items[2] = '第3笔:134元';
  assert.throws(() => validateTimeline(badSum), /sum to metric/);
});

test('material rich geometry keeps upper material, lower white title and support bands separated', () => {
  const source = require('node:fs').readFileSync(new URL('./RichMaterialGeometry.ts', import.meta.url), 'utf8');
  const module = {exports: {}};
  new Function('require', 'module', 'exports', ts.transpileModule(source,
    {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText)(require, module, module.exports);
  const {richMaterialGeometry: boxes, richMaterialBoxesDoNotOverlap} = module.exports;
  assert.equal(richMaterialBoxesDoNotOverlap(), true);
  assert.deepEqual(boxes.material, {x: 56, y: 64, width: 968, height: 900});
  assert.equal(boxes.title.y, 1000);
  assert.equal(boxes.title.height, 190);
  assert.ok(boxes.support.y >= 1210 && boxes.support.y + boxes.support.height <= 1640);
  assert.equal(boxes.emphasis.y, 1700);
  assert.equal(boxes.identity.y, 1840);
});

const loadRichMaterialScene = async ({currentFrame = 160} = {}) => {
  const cache = new Map();
  const loadLocal = (relative) => {
    const url = new URL(relative.endsWith('.ts') || relative.endsWith('.tsx') ? relative : `${relative}.ts`, import.meta.url);
    const key = url.href;
    if (cache.has(key)) return cache.get(key).exports;
    const module = {exports: {}};
    cache.set(key, module);
    const source = require('node:fs').readFileSync(url, 'utf8');
    new Function('require', 'module', 'exports', ts.transpileModule(source, {compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
    }}).outputText)(mockRequire, module, module.exports);
    return module.exports;
  };
  const passthrough = (name) => (props) => createElement('div', {'data-native-id': name}, props.children);
  const mockRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime' || name.startsWith('node:')) return require(name);
    if (name === 'remotion') return {
      AbsoluteFill: ({children, style}) => createElement('div', {style}, children),
      Freeze: ({children}) => createElement('div', {'data-freeze': 'true'}, children),
      Img: (props) => createElement('img', props),
      OffthreadVideo: ({trimBefore, trimAfter, ...props}) => createElement('video', {'data-trim-before': trimBefore, 'data-trim-after': trimAfter, ...props}),
      Sequence: ({children}) => createElement('div', null, children),
      staticFile: (src) => `static:${src}`,
      useCurrentFrame: () => currentFrame,
      useVideoConfig: () => ({width: 1080, height: 1920, fps: 30, durationInFrames: 371}),
    };
    if (name === './RichMaterialGeometry' || name === './RichMaterialContract' ||
        name === './phoneTutorial' || name === './adapters/videoGeometry') return loadLocal(name);
    if (name === './MaterialFocus') return {FocusInk: ({steps}) => createElement('svg', {'data-focus-steps': steps.length})};
    if (name === './adapters/layout') return {
      FittedText: ({text}) => createElement('span', null, text),
      muted: '#94a3b8',
      productionFont: 'Inter',
      white: '#ffffff',
    };
    if (name.includes('/snapcn/phone-frame')) return {PhoneFrame: ({children}) => createElement('section', {'data-native-id': 'Snapcn-PhoneFrame'}, children)};
    if (name.includes('/snapcn')) return {
      TextBuild: passthrough('Snapcn-TextBuild'),
      TextHighlight: ({highlight}) => createElement('strong', {'data-native-id': 'Snapcn-TextHighlight'}, highlight),
      TextReveal: ({text}) => createElement('h1', {'data-native-id': 'Snapcn-TextReveal'}, text),
      TextSwap: passthrough('Snapcn-TextSwap'),
      WordFlip: passthrough('Snapcn-WordFlip'),
    };
    if (name.includes('/rve/chart-animation')) return {__esModule: true, default: passthrough('Rve-ChartAnimation')};
    if (name.includes('/rve/line-chart')) return {__esModule: true, default: passthrough('Rve-LineChart')};
    if (name.includes('/rve/progress-steps')) return {__esModule: true, default: passthrough('Rve-ProgressSteps')};
    if (name.includes('/rve/quote-card')) return {__esModule: true, default: passthrough('Rve-QuoteCard')};
    if (name.includes('/rve/split-screen')) return {__esModule: true, default: passthrough('Rve-SplitScreen')};
    if (name.includes('/rve/stat-counter')) return {__esModule: true, default: passthrough('Rve-StatCounter')};
    if (name.includes('/community/IsolatedCard')) return {IsolatedCard: ({children}) => createElement('div', {'data-isolated-card': 'true'}, children)};
    if (name.includes('/video-talkcraft/cards/ink-underline')) return {__esModule: true, default: passthrough('Talkcraft-ink-underline')};
    if (name.includes('/video-talkcraft/cards/source-converge')) return {__esModule: true, default: passthrough('Talkcraft-source-converge')};
    if (name.includes('/video-talkcraft/cards/scanline-annotate')) return {__esModule: true, default: passthrough('Talkcraft-scanline-annotate')};
    if (name.includes('/video-talkcraft/cards/slow-pull-reveal')) return {__esModule: true, default: passthrough('Talkcraft-slow-pull-reveal')};
    if (name.includes('/video-talkcraft/cards/slow-push-in')) return {__esModule: true, default: passthrough('Talkcraft-slow-push-in')};
    if (name.includes('/video-talkcraft/cards/tilt-3d-page')) return {__esModule: true, default: passthrough('Talkcraft-tilt-3d-page')};
    throw new Error(`Unexpected import in RichMaterialScene test: ${name}`);
  };
  return loadLocal('./RichMaterialScene.tsx');
};

test('SSR renders A09 real media once without default copy or outer demo labels', async () => {
  const {RichMaterialScene} = await loadRichMaterialScene();
  const shot = validateTimeline(sample('A09')).shots[0];
  const markup = renderToStaticMarkup(createElement(RichMaterialScene, {shot}));
  assert.equal((markup.match(/<video/g) ?? []).length, 1);
  assert.match(markup, /static:videoagents\/material-rich-test\/A09\.mp4/);
  assert.doesNotMatch(markup, /演示文案|无外部素材|模拟界面 · 操作演示|默认文案/);
  assert.match(markup, /本地模拟App操作录屏/);
});

test('SSR renders image material through isolated native media without default copy', async () => {
  const {RichMaterialScene} = await loadRichMaterialScene();
  const shot = validateTimeline(sample('A07')).shots[0];
  const markup = renderToStaticMarkup(createElement(RichMaterialScene, {shot}));
  assert.match(markup, /data-isolated-card/);
  assert.match(markup, /data-native-id="Talkcraft-slow-push-in"/);
  assert.doesNotMatch(markup, /演示文案|无外部素材|默认文案/);
});

test('SSR mounts declared A10 and A11 support natives instead of generic placeholders', async () => {
  const {RichMaterialScene} = await loadRichMaterialScene();
  const a10 = renderToStaticMarkup(createElement(RichMaterialScene, {shot: validateTimeline(sample('A10')).shots[0]}));
  for (const id of ['Talkcraft-scanline-annotate', 'Talkcraft-ink-underline', 'Rve-ChartAnimation', 'Rve-StatCounter', 'Snapcn-TextBuild', 'Rve-LineChart']) {
    assert.match(a10, new RegExp(`data-native-id="${id}"|${id}`));
  }
  assert.match(a10, /data-freeze="true"/);

  const a11 = renderToStaticMarkup(createElement(RichMaterialScene, {shot: validateTimeline(sample('A11')).shots[0]}));
  assert.match(a11, /data-native-id="Talkcraft-ink-underline"/);
  assert.doesNotMatch(a11, /data-native-id="Rve-ProgressSteps"/);
});

test('A10 scanline keeps live playback before the hold frame and uses pixel fit math', async () => {
  const source = require('node:fs').readFileSync(new URL('./RichMaterialScene.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(source, /100cqw|100cqh|scale\(min\(/);

  const {RichMaterialScene} = await loadRichMaterialScene({currentFrame: 120});
  const markup = renderToStaticMarkup(createElement(RichMaterialScene, {shot: validateTimeline(sample('A10')).shots[0]}));
  assert.doesNotMatch(markup, /data-freeze="true"/);
});
