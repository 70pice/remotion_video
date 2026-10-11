import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import capabilities from '../../videoagents/component-set-capabilities.json' with {type: 'json'};
import {validateTimeline} from './validation.mjs';

const require = createRequire(import.meta.url);
const safe = capabilities.safe_area;
const allowedBindings = new Set(['media', 'title', 'body', 'takeaway', 'items', 'supporting_items', 'numeric_items', 'metric']);
const bySet = new Map(capabilities.sets.map((entry) => [entry.set_id, entry]));
const clone = (value) => JSON.parse(JSON.stringify(value));

const loadSourceConverge = (frame) => {
  const url = new URL('../components/component-horizontal/video-talkcraft/cards/source-converge.tsx', import.meta.url);
  const source = readFileSync(url, 'utf8');
  const module = {exports: {}};
  const mockRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime') return require(name);
    if (name === 'remotion') return {
      AbsoluteFill: ({children, style}) => createElement('div', {style}, children),
      useCurrentFrame: () => frame,
    };
    throw new Error(`Unexpected import in SourceConverge test: ${name}`);
  };
  new Function('require', 'module', 'exports', ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText)(mockRequire, module, module.exports);
  return module.exports.default;
};

const defaultContent = {
  takeaway: '先看真实变化',
  items: ['输入问题', '核对来源', '再做决定'],
  supporting_items: ['来源A', '来源B', '人工核对'],
  metric: {label: '合计', value: '3项', detail: '本期统计'},
  numeric_items: ['第一项:1项', '第二项:2项', '第三项:3项'],
  source_refs: ['https://example.com/a', 'https://example.com/b'],
};

const contentFor = (setId) => {
  const base = {takeaway: defaultContent.takeaway, source_refs: defaultContent.source_refs};
  if (['A07', 'A08', 'A11', 'A12'].includes(setId)) return {...base, items: defaultContent.items, supporting_items: defaultContent.supporting_items};
  if (setId === 'A09') return {...base, items: defaultContent.items, supporting_items: defaultContent.supporting_items, metric: {label: '步骤', value: '3步', detail: '连续操作'}};
  if (setId === 'A10') return {...base, items: defaultContent.items, numeric_items: defaultContent.numeric_items, metric: {label: '合计', value: '6项', detail: '三项相加'}};
  if (['B01', 'B02'].includes(setId)) return {...base, items: defaultContent.items, metric: {label: '条目', value: '3项', detail: '三项内容'}};
  if (setId === 'B03') return {...base, items: ['旧做法', '新做法'], numeric_items: ['旧做法:1项', '新做法:2项']};
  if (setId === 'B04') return {...base, numeric_items: defaultContent.numeric_items, metric: {label: '合计', value: '6项', detail: '三项相加'}};
  if (setId === 'B05') return {...base, items: defaultContent.items, supporting_items: defaultContent.supporting_items, metric: {label: '步骤', value: '3项', detail: '三项内容'}};
  if (setId === 'B06') return {...base, items: defaultContent.items, supporting_items: ['先截图', '再核对'], metric: {label: '提醒', value: '3项', detail: '三项内容'}};
  if (setId === 'B09') return {...base, items: ['自述金额', '核实金额'], numeric_items: ['自述:5项', '核实:2项'], metric: {label: '差异', value: '3项', detail: '两项差值'}};
  if (['B07', 'B08', 'B10'].includes(setId)) return {...base, items: defaultContent.items, numeric_items: defaultContent.numeric_items, metric: {label: '合计', value: '6项', detail: '三项相加'}};
  if (setId === 'B11') return {...base, items: defaultContent.items, supporting_items: defaultContent.supporting_items, metric: {label: '支撑', value: '3项', detail: '三条依据'}};
  if (setId === 'B12') return {...base, items: defaultContent.items, supporting_items: defaultContent.supporting_items, metric: {label: '支撑', value: '3项', detail: '三条依据'}};
  if (setId === 'B13') return {...base, items: ['旧说法', '新说法'], supporting_items: defaultContent.supporting_items, metric: {label: '支撑', value: '3项', detail: '三条依据'}};
  if (setId === 'B14') return {...base, items: defaultContent.items, supporting_items: ['先看来源', '再看动作'], metric: {label: '问题', value: '3项', detail: '三项内容'}};
  if (setId === 'B15') return {...base, items: defaultContent.items, supporting_items: defaultContent.supporting_items, numeric_items: defaultContent.numeric_items, metric: {label: '合计', value: '6项', detail: '三项相加'}};
  if (setId === 'B16') return {...base, items: defaultContent.items, supporting_items: ['第一步', '第二步', '第三步'], metric: {label: '步骤', value: '3项', detail: '三项内容'}};
  if (setId === 'B17') return {...base, items: defaultContent.items, supporting_items: ['人工核对', '保留证据'], metric: {label: '步骤', value: '3项', detail: '三项内容'}};
  if (setId === 'B18') return {...base, items: ['前后差异', '继续核实'], supporting_items: defaultContent.supporting_items, numeric_items: ['最小:1项', '最大:3项'], metric: {label: '最大', value: '3项', detail: '两项最大值'}};
  return clone(defaultContent);
};

const defaultPartsFor = (meta, duration) => meta.parts.map((part) => ({
  part_id: part.part_id,
  start_frame: Math.floor(duration * part.start_ratio),
  end_frame: Math.ceil(duration * part.end_ratio),
  box: clone(part.box),
}));


const propsFor = (componentId, hasAsset, video) => {
  if (!hasAsset) return {};
  if (video && (componentId === 'video' || componentId === 'Snapcn-PhoneFrame')) return {asset_fit: 'contain', start_seconds: 2};
  if (componentId === 'evidence' || componentId === 'image_focus') return {};
  return {asset_fit: 'contain'};
};

const timelineFor = (setId, overrides = {}) => {
  const meta = bySet.get(setId);
  const material = meta.material_kind;
  const video = material === 'video' || (material === 'image_or_video' && setId === 'A02');
  const asset = material === 'none' ? null : `videoagents/prod-set/${setId}.${video ? 'mp4' : 'png'}`;
  return {
    schema_version: '1',
    job_id: 'prod-set',
    revision: 1,
    width: 1080,
    height: 1920,
    fps: 30,
    duration_in_frames: 360,
    audio_src: 'videoagents/prod-set/audio.wav',
    captions: [{text: '这里是生产字幕', start_ms: 0, end_ms: 1000}],
    shots: [{
      shot_id: setId,
      start_frame: 0,
      end_frame: 360,
      component_id: meta.main_component_id,
      title: `${setId}生产标题`,
      body: '本期真实素材和口播内容',
      source_label: setId === 'A05' ? '资料来源 example.com' : '素材来源 example.com',
      asset_src: asset,
      accent_color: '#38BDF8',
      props: propsFor(meta.main_component_id, Boolean(asset), video),
      layers: [],
      set_design: {set_id: setId, content: contentFor(setId), parts: defaultPartsFor(meta, 360), ...(setId === 'A09' ? {focus_steps: [
        {instruction: '输入问题', start_frame: 0, end_frame: 120, target: {x: 0.1, y: 0.2, width: 0.3, height: 0.1}},
        {instruction: '核对来源', start_frame: 120, end_frame: 240, target: {x: 0.2, y: 0.4, width: 0.3, height: 0.1}},
        {instruction: '再做决定', start_frame: 240, end_frame: 360, target: {x: 0.3, y: 0.6, width: 0.3, height: 0.1}},
      ], source_size: {width: 720, height: 1440}} : {})},
      ...overrides,
    }],
  };
};

test('component-set capabilities cover exact 30 production sets with safe native parts', () => {
  assert.equal(capabilities.version, 1);
  assert.deepEqual(safe, {x: 64, y: 96, width: 952, height: 1304});
  const ids = capabilities.sets.map((entry) => entry.set_id);
  assert.equal(ids.length, 30);
  assert.equal(new Set(ids).size, 30);
  assert.deepEqual(ids.slice(0, 12), ['A01', 'A02', 'A03', 'A04', 'A05', 'A06', 'A07', 'A08', 'A09', 'A10', 'A11', 'A12']);
  assert.deepEqual(ids.slice(12), ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B09', 'B10', 'B11', 'B12', 'B13', 'B14', 'B15', 'B16', 'B17', 'B18']);
  for (const set of capabilities.sets) {
    assert.ok(set.parts.length >= 5, `${set.set_id} should expose multiple native parts`);
    assert.ok(set.parts.find((part) => part.part_id === 'main')?.component_id, `${set.set_id} should expose a main native part`);
    for (const part of set.parts) {
      assert.match(part.component_id, /^[A-Za-z0-9_-]+$/);
      assert.ok(allowedBindings.has(part.binding) || /^(items|supporting_items)\.\d+$/.test(part.binding), `${set.set_id}.${part.part_id} binding`);
      assert.ok(part.box.x >= 0 && part.box.y >= 0, `${set.set_id}.${part.part_id} starts inside normalized safe area`);
      assert.ok(part.box.x + part.box.width <= 1, `${set.set_id}.${part.part_id} width inside safe area`);
      assert.ok(part.box.y + part.box.height <= 1, `${set.set_id}.${part.part_id} height inside safe area`);
      assert.ok(part.start_ratio >= 0 && part.start_ratio < part.end_ratio && part.end_ratio <= 1);
    }
  }

  const expectedExistingBindings = new Map([
    ['B02', new Set(['title', 'takeaway', 'items', 'metric'])],
    ['B04', new Set(['title', 'takeaway', 'metric', 'numeric_items'])],
    ['B09', new Set(['title', 'takeaway', 'items', 'metric', 'numeric_items'])],
  ]);
  for (const [setId, allowed] of expectedExistingBindings) {
    for (const part of bySet.get(setId).parts) {
      const root = part.binding.split('.')[0];
      assert.ok(allowed.has(root), `${setId}.${part.part_id} should bind to content available for that set`);
    }
  }
  for (const set of capabilities.sets) {
    assert.equal(typeof set.focus_supported, 'boolean', `${set.set_id} declares focus support`);
    for (const part of set.parts) {
      if (['Rve-ChartAnimation', 'Rve-ComparisonChart', 'Rve-LineChart'].includes(part.component_id)) {
        assert.equal(part.binding, 'numeric_items', `${set.set_id}.${part.part_id} chart parts require numeric_items`);
      }
    }
  }
});

test('production set_design validates all 30 sets while keeping audio and captions enabled', () => {
  for (const setId of bySet.keys()) {
    const input = timelineFor(setId);
    const before = clone(input);
    assert.equal(validateTimeline(input), input);
    assert.deepEqual(input, before);
    assert.equal(input.audio_src, 'videoagents/prod-set/audio.wav');
    assert.equal(input.captions.length, 1);
    assert.equal(input.shots[0].props.component_set, undefined);
    assert.equal(input.shots[0].props.composition, undefined);
    assert.equal(input.shots[0].props.rich_content, undefined);
  }
});

test('production set_design rejects wrong main component, unsafe part boxes, sample content duplication and media mismatch', () => {
  const wrongMain = timelineFor('B07', {component_id: 'Rve-QuoteCard'});
  assert.throws(() => validateTimeline(wrongMain), /main component/);

  const unsafe = timelineFor('A07');
  unsafe.shots[0].set_design.parts = defaultPartsFor(bySet.get('A07'), 360);
  unsafe.shots[0].set_design.parts[0] = {part_id: 'main', start_frame: 0, end_frame: 180, box: {x: 0, y: 0.99, width: 1, height: 0.05}};
  assert.throws(() => validateTimeline(unsafe), /safe area/);

  const duplicateCopy = timelineFor('B01');
  duplicateCopy.shots[0].set_design.content.title = '不允许';
  assert.throws(() => validateTimeline(duplicateCopy), /must not duplicate/);

  const imageAsVideo = timelineFor('A09');
  imageAsVideo.shots[0].asset_src = 'videoagents/prod-set/A09.png';
  assert.throws(() => validateTimeline(imageAsVideo), /requires video media/);
});

const loadProductionScene = (capabilityPayload = capabilities) => {
  const cache = new Map();
  const loadLocal = (relative) => {
    const url = new URL(relative.endsWith('.ts') || relative.endsWith('.tsx') ? relative : `${relative}.ts`, import.meta.url);
    const key = url.href;
    if (cache.has(key)) return cache.get(key).exports;
    const module = {exports: {}};
    cache.set(key, module);
    const source = readFileSync(url, 'utf8');
    new Function('require', 'module', 'exports', ts.transpileModule(source, {compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, resolveJsonModule: true,
    }}).outputText)(mockRequire, module, module.exports);
    return module.exports;
  };
  const passthrough = (name) => (props) => createElement('div', {'data-native-prop': name}, props.children ?? props.text ?? props.highlight ?? props.title);
  const mockRequire = (name) => {
    if (name === 'react' || name === 'react/jsx-runtime' || name.startsWith('node:')) return require(name);
    if (name.endsWith('component-set-capabilities.json')) return {default: capabilityPayload, ...capabilityPayload};
    if (name === 'remotion') return {
      AbsoluteFill: ({children, style}) => createElement('div', {style}, children),
      Img: (props) => createElement('img', props),
      OffthreadVideo: ({trimBefore, trimAfter, ...props}) => createElement('video', {'data-trim-before': trimBefore, 'data-trim-after': trimAfter, ...props}),
      Sequence: ({children, from, durationInFrames}) => createElement('div', {'data-sequence-from': from, 'data-sequence-duration': durationInFrames}, children),
      staticFile: (src) => `static:${src}`,
      useCurrentFrame: () => 0,
      useVideoConfig: () => ({width: 1080, height: 1920, fps: 30, durationInFrames: 360}),
    };
    if (name.includes('/bits/examples/ChatConversation')) return {ChatConversation: ({messages}) => createElement('div', {'data-native-prop': 'Bits-ChatConversation', 'data-chat-messages': messages.map((message) => message.text).join('|')})};
    if (name.includes('/bits/examples/KenBurns')) return {Component: passthrough('Bits-KenBurns')};
    if (name.includes('/rve/chart-animation')) return {__esModule: true, default: passthrough('Rve-ChartAnimation')};
    if (name.includes('/rve/comparison-chart')) return {__esModule: true, default: passthrough('Rve-ComparisonChart')};
    if (name.includes('/rve/line-chart')) return {__esModule: true, default: passthrough('Rve-LineChart')};
    if (name.includes('/rve/progress-steps')) return {__esModule: true, default: passthrough('Rve-ProgressSteps')};
    if (name.includes('/rve/quote-card')) return {__esModule: true, default: ({quote, quoteFontSize, slotWidth, slotHeight}) => createElement('div', {'data-native-prop': 'Rve-QuoteCard', 'data-quote-font-size': quoteFontSize, 'data-slot-width': slotWidth, 'data-slot-height': slotHeight}, quote)};
    if (name.includes('/rve/split-screen')) return {__esModule: true, default: passthrough('Rve-SplitScreen')};
    if (name.includes('/rve/stat-counter')) return {__esModule: true, default: ({label, period, suffix, slotWidth, slotHeight}) => createElement('div', {'data-native-prop': 'Rve-StatCounter', 'data-label': label, 'data-period': period, 'data-suffix': suffix, 'data-slot-width': slotWidth, 'data-slot-height': slotHeight})};
    if (name.includes('/snapcn/phone-frame')) return {PhoneFrame: ({children, scale}) => createElement('section', {'data-native-prop': 'Snapcn-PhoneFrame', 'data-phone-frame-scale': scale}, children)};
    if (name.includes('/snapcn')) return {
      AnswerStream: passthrough('Snapcn-AnswerStream'),
      TextBuild: passthrough('Snapcn-TextBuild'),
      TextHighlight: passthrough('Snapcn-TextHighlight'),
      TextReveal: ({text, fontSize}) => createElement('div', {'data-native-prop': 'Snapcn-TextReveal', 'data-font-size': fontSize}, text),
      TextSwap: passthrough('Snapcn-TextSwap'),
      WordFlip: ({words, fontSize}) => createElement('div', {'data-native-prop': 'Snapcn-WordFlip', 'data-font-size': fontSize, 'data-words': (words ?? []).join('|')}),
    };
    if (name === './adapters/layout') return {muted: '#94a3b8', productionFont: 'Inter', white: '#fff'};
    if (name === './TalkcraftNativeMedia') return {talkcraftNativeMediaBindings: [], TALKCRAFT_PRODUCTION_MEDIA_CSS: ''};
    if (name.includes('/community/IsolatedCard')) return {IsolatedCard: ({children}) => createElement('div', {'data-isolated-card': true}, children)};
    if (name.includes('/video-talkcraft/production-props')) return {resolveTalkcraftTitleCopy: (shot) => ({title: shot.title ?? '', body: shot.body ?? '', source: shot.source_label ?? '', accent: shot.accent_color ?? '', keyword: shot.title ?? '', lines: [], items: shot.props?.items ?? []})};
    if (name === './ExpandedSemanticPanels') return {TalkcraftPanel: ({componentId, productionCompact, slotWidth, slotHeight}) => createElement('div', {'data-native-prop': componentId, 'data-production-compact': productionCompact ? 'true' : 'false', 'data-slot-width': slotWidth, 'data-slot-height': slotHeight}), LineChartPanel: passthrough('Rve-LineChart')};
    if (name === './phoneTutorial') return {tutorialRingPath: () => 'M0 0', tutorialTargetRect: () => ({x: 0, y: 0, width: 10, height: 10}), tutorialStepAt: (steps) => steps[0]};
    throw new Error(`Unexpected import in production set scene test: ${name}`);
  };
  return loadLocal('./ProductionComponentSetScene.tsx');
};



test('production set_design mirrors strict content, layout, focus and props rejection rules', () => {
  const validRefs = timelineFor('B01');
  validRefs.shots[0].set_design.content.source_refs = Array.from({length: 30}, (_, index) => `https://example.com/source-${index}`);
  assert.equal(validateTimeline(validRefs), validRefs);

  const tooManyRefs = timelineFor('B01');
  tooManyRefs.shots[0].set_design.content.source_refs = Array.from({length: 31}, (_, index) => `https://example.com/source-${index}`);
  assert.throws(() => validateTimeline(tooManyRefs), /at most 30 source refs/);

  const missingPart = timelineFor('B01');
  missingPart.shots[0].set_design.parts.pop();
  assert.throws(() => validateTimeline(missingPart), /include every template part/);

  const overlap = timelineFor('B01');
  overlap.shots[0].set_design.parts[1] = {...overlap.shots[0].set_design.parts[1], start_frame: overlap.shots[0].set_design.parts[0].start_frame, end_frame: overlap.shots[0].set_design.parts[0].end_frame, box: clone(overlap.shots[0].set_design.parts[0].box)};
  assert.throws(() => validateTimeline(overlap), /must not overlap/);

  const short = timelineFor('B01');
  short.shots[0].set_design.parts[1].end_frame = short.shots[0].set_design.parts[1].start_frame + 20;
  assert.throws(() => validateTimeline(short), /display interval is too short/);

  const extraProps = timelineFor('B01', {props: {asset_fit: 'contain'}});
  assert.throws(() => validateTimeline(extraProps), /does not accept media/);

  const unsupportedFocus = timelineFor('A07');
  unsupportedFocus.shots[0].set_design.focus_steps = [{instruction: '输入问题', start_frame: 0, end_frame: 360, target: {x: 0.1, y: 0.2, width: 0.3, height: 0.1}}];
  unsupportedFocus.shots[0].set_design.source_size = {width: 720, height: 1440};
  assert.throws(() => validateTimeline(unsupportedFocus), /does not support focus_steps/);

  const coverFocus = timelineFor('A09');
  coverFocus.shots[0].props.asset_fit = 'cover';
  assert.throws(() => validateTimeline(coverFocus), /require contain fit/);

  const brokenFocus = timelineFor('A09');
  brokenFocus.shots[0].set_design.focus_steps[1].start_frame += 5;
  assert.throws(() => validateTimeline(brokenFocus), /must be contiguous/);

  const blankSource = timelineFor('A07');
  blankSource.shots[0].source_label = '';
  assert.throws(() => validateTimeline(blankSource), /source_label/);
});


test('SSR chat conversation uses the part binding without appending fallback items or takeaway', () => {
  const capabilityPayload = clone(capabilities);
  const b11 = capabilityPayload.sets.find((entry) => entry.set_id === 'B11');
  const main = b11.parts.find((part) => part.part_id === 'main');
  main.component_id = 'Bits-ChatConversation';
  main.binding = 'supporting_items';
  const {ProductionComponentSetScene} = loadProductionScene(capabilityPayload);
  const shot = validateTimeline(timelineFor('B11')).shots[0];
  const markup = renderToStaticMarkup(createElement(ProductionComponentSetScene, {shot}));
  assert.match(markup, /data-chat-messages="来源A\|来源B\|人工核对"/);
  assert.doesNotMatch(markup, /data-chat-messages="[^"]*输入问题/);
  assert.doesNotMatch(markup, /data-chat-messages="[^"]*核对来源/);
  assert.doesNotMatch(markup, /data-chat-messages="[^"]*再做决定/);
  assert.doesNotMatch(markup, /data-chat-messages="[^"]*先看真实变化/);
});

test('SSR production compact slots keep title flow and readable support sizing', () => {
  const {ProductionComponentSetScene} = loadProductionScene();
  const a05 = renderToStaticMarkup(createElement(ProductionComponentSetScene, {shot: validateTimeline(timelineFor('A05')).shots[0]}));
  assert.match(a05, /data-title-flow="headline"/);
  assert.match(a05, /data-title-flow="body" style="position:relative/);
  assert.doesNotMatch(a05, /data-title-flow="body" style="position:absolute/);
  assert.match(a05, /data-native-prop="Rve-QuoteCard"[^>]*data-quote-font-size="(?:4[0-9]|3[0-9]|2[4-9])/);
  assert.match(a05, /data-native-prop="Rve-QuoteCard"[^>]*data-slot-height="(?:20[0-9]|21[0-9])/);
  assert.match(a05, /data-native-prop="Talkcraft-source-converge"[^>]*data-production-compact="true"/);

  const b11 = renderToStaticMarkup(createElement(ProductionComponentSetScene, {shot: validateTimeline(timelineFor('B11')).shots[0]}));
  assert.match(b11, /data-native-prop="Rve-StatCounter"[^>]*data-slot-height="(?:21[0-9]|22[0-9])/);
  assert.match(b11, /data-native-prop="Rve-StatCounter"[^>]*data-label="支撑"[^>]*data-period="三条依据"/);
  assert.match(b11, /data-native-prop="Talkcraft-word-slot-cycle"[^>]*data-production-compact="true"/);
});

test('native source converge compact timing preserves motion and exact source count in short support slots', () => {
  const expandedSource = readFileSync(new URL('./ExpandedSemanticPanels.tsx', import.meta.url), 'utf8');
  assert.doesNotMatch(expandedSource, /CompactTalkcraftContent/);
  assert.doesNotMatch(expandedSource, /opacity:\s*0\.18/);
  const speed = 132 / (79 - 30);
  const early = renderToStaticMarkup(createElement(loadSourceConverge(5), {holdResult: true, title: '', sources: ['来源A'], hub: '来源A', caption: '', speed}));
  const middle = renderToStaticMarkup(createElement(loadSourceConverge(35), {holdResult: true, title: '', sources: ['来源A'], hub: '来源A', caption: '', speed}));
  const final = renderToStaticMarkup(createElement(loadSourceConverge(60), {holdResult: true, title: '', sources: ['来源A'], hub: '来源A', caption: '', speed}));
  assert.notEqual(early, middle);
  assert.equal((final.match(/class="scv-node"/g) ?? []).length, 1);
  assert.doesNotMatch(final, /旧判断|新判断/);
  assert.match(final, /transform="translate\(480 290\) scale/);
  assert.match(final, />来源A</);

  const currentLabels = renderToStaticMarkup(createElement(loadSourceConverge(60), {
    holdResult: true,
    title: '',
    sources: ['山东法院网', '转载人民法院报'],
    hub: '山东法院网',
    caption: '',
    speed,
    compactFit: true,
  }));
  assert.match(currentLabels, /width="386"/);
  assert.match(currentLabels, /width="502"/);
  assert.match(currentLabels, /font-size:60\.\d+px/);
  assert.match(currentLabels, /font-size:57\.\d+px/);
  assert.doesNotMatch(currentLabels, /font-size:7[04]px/);
});

test('SSR renders production set parts with local sequence clocks and shot-clock video trim', () => {
  const {ProductionComponentSetScene} = loadProductionScene();
  const timeline = timelineFor('A09');
  timeline.shots[0].set_design.parts = defaultPartsFor(bySet.get('A09'), 360);
  timeline.shots[0].set_design.parts[0] = {part_id: 'main', start_frame: 60, end_frame: 180, box: {x: 0.016807, y: 0.018405, width: 0.945378, height: 0.383436}};
  timeline.shots[0].set_design.focus_steps = [{instruction: '输入问题', start_frame: 0, end_frame: 360, target: {x: 0.1, y: 0.2, width: 0.3, height: 0.1}}];
  timeline.shots[0].set_design.source_size = {width: 720, height: 1440};
  const shot = validateTimeline(timeline).shots[0];
  const markup = renderToStaticMarkup(createElement(ProductionComponentSetScene, {shot}));
  assert.match(markup, /data-component-set-production="A09"/);
  assert.match(markup, /data-set-part="main"/);
  assert.match(markup, /data-local-start="60"/);
  assert.match(markup, /data-sequence-from="60"/);
  assert.match(markup, /data-media-trim-before="120"/);
  assert.match(markup, /data-phone-scale="0\.658"/);
  assert.match(markup, /left:80(?:\.\d+)?px/);
  assert.match(markup, /top:120(?:\.\d+)?px/);

  timeline.shots[0].set_design.parts[0].box = {x: 0.05, y: 0.05, width: 0.25, height: 0.2};
  timeline.shots[0].set_design.parts[0].end_frame = 240;
  const smallMarkup = renderToStaticMarkup(createElement(ProductionComponentSetScene, {shot: validateTimeline(timeline).shots[0]}));
  assert.doesNotMatch(smallMarkup, /data-phone-scale="0\.658"/);
});
