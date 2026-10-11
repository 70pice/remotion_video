import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {validateTimeline} from './validation.mjs';

const {structuredClone} = globalThis;

const require = createRequire(import.meta.url);
const geometrySource = await readFile(new URL('./noMaterialSetGeometry.ts', import.meta.url), 'utf8');
const module = {exports: {}};
new Function('require', 'module', 'exports', ts.transpileModule(geometrySource,
  {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText)(require, module, module.exports);
const {noMaterialSetMainComponents: mains, noMaterialSetGeometry: boxes} = module.exports;
const richGeometrySource = await readFile(new URL('./RichNoMaterialGeometry.ts', import.meta.url), 'utf8');
const richModule = {exports: {}};
new Function('require', 'module', 'exports', ts.transpileModule(richGeometrySource,
  {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText)(require, richModule, richModule.exports);
const {richNoMaterialGeometry: richBoxes, richNoMaterialMinimumFont, richStageTimings,
  richNoMaterialBoxesDoNotOverlap, parseRichNumericItem, richNumericItemsSumToMetric} = richModule.exports;
const expandedGeometrySource = await readFile(new URL('./ExpandedNoMaterialGeometry.ts', import.meta.url), 'utf8');
const expandedModule = {exports: {}};
new Function('require', 'module', 'exports', ts.transpileModule(expandedGeometrySource,
  {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText)(require, expandedModule, expandedModule.exports);
const {expandedNoMaterialSetIds, expandedNoMaterialGeometry: expandedBoxes, expandedStageTimings, expandedBoxesDoNotOverlap} = expandedModule.exports;
const legacySetIds = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06'];
const expandedSetIds = [...expandedNoMaterialSetIds];

const props = {B01: {}, B02: {keyword: '先核对'}, B03: {items: ['陌生消息：直接照做', '熟悉号码：先回拨']},
  B04: {metric: {label: '演示账本', value: '399元'}}, B05: {items: ['停一下', '回拨核对', '保留记录']},
  B06: {call_to_action: '先核对再行动'}};
const sample = (id) => ({schema_version: '1', job_id: 'text-set-test', revision: 1,
  width: 1080, height: 1920, fps: 30, presentation: 'component_sample', duration_in_frames: 240,
  audio_src: null, captions: [], shots: [{shot_id: id, start_frame: 0, end_frame: 240,
    component_id: mains[id], title: '演示标题', body: '演示说明', source_label: '', asset_src: null,
    accent_color: '#38BDF8', props: {...props[id], component_set: id}, layers: []}]});
const richContent = {
  B01: {takeaway: '先核实身份', items: ['消息称呼', '来电身份', '付款理由'], metric: {label: '核对线索', value: '3项'}},
  B02: {takeaway: '聊天能力不等于身份', items: ['能接话', '能视频', '身份可信'], metric: {label: '分开判断', value: '3项'}},
  B03: {takeaway: '先核对再行动', items: ['只看消息', '回拨核实'], numeric_items: ['只看消息:1步', '回拨核实:2步']},
  B04: {takeaway: '小额也看总账', metric: {label: '三次合计', value: '399元', detail: '133元×3次'}, numeric_items: ['第1次:133元', '第2次:133元', '第3次:133元']},
  B05: {takeaway: '核对清楚再决定', items: ['先停一下', '回拨号码', '家人核对'],
    supporting_items: ['先不急着付钱', '只拨已存号码', '让家人一起看'], metric: {label: '核对顺序', value: '3步'}},
  B06: {takeaway: '先停再核实', items: ['停下来', '回拨核对', '家人一起看'],
    supporting_items: ['对方：先转点钱再聊吧', '我：我先核对一下'], metric: {label: '一起练习', value: '3步'}},
};
const richProps = (id) => ({
  B01: {component_set: 'B01', composition: 'rich', rich_content: richContent.B01},
  B02: {component_set: 'B02', keyword: richContent.B02.takeaway, composition: 'rich', rich_content: richContent.B02},
  B03: {component_set: 'B03', items: richContent.B03.items, composition: 'rich', rich_content: richContent.B03},
  B04: {component_set: 'B04', metric: richContent.B04.metric, composition: 'rich', rich_content: richContent.B04},
  B05: {component_set: 'B05', items: richContent.B05.items, composition: 'rich', rich_content: richContent.B05},
  B06: {component_set: 'B06', call_to_action: richContent.B06.takeaway, composition: 'rich', rich_content: richContent.B06},
}[id]);
const richSample = (id) => {
  const input = sample(id);
  const title = '先核实身份';
  const body = '把聊天视频和付款理由分开看。';
  const content = richContent[id];
  const [titleComponent, emphasisComponent] = {
    B01: ['Snapcn-SearchTyping', 'Snapcn-TextHighlight'],
    B02: ['Snapcn-TextRewrite', 'Snapcn-AnswerHighlight'],
    B03: ['Snapcn-TextSwap', 'Snapcn-TextHighlight'],
    B04: ['Snapcn-TextRewrite', 'Snapcn-TextHighlight'],
    B05: ['Snapcn-TextBuild', 'Snapcn-TextHighlight'],
    B06: ['Snapcn-TextReveal', 'Snapcn-AnswerHighlight'],
  }[id];
  const titleProps = id === 'B02' ? {from_text: title, to_text: content.takeaway}
    : id === 'B03' ? {from_text: content.items[0], to_text: content.items[1]}
      : id === 'B04' ? {from_text: title, to_text: content.metric.value} : {};
  const answer = emphasisComponent === 'Snapcn-AnswerHighlight';
  input.duration_in_frames = 450;
  Object.assign(input.shots[0], {end_frame: 450, title, body, props: richProps(id), layers: [
    {component_id: titleComponent, role: 'title', start_frame: 0, end_frame: 450,
      title, body, props: titleProps, accent_color: '#38BDF8'},
    {component_id: emphasisComponent, role: 'emphasis', start_frame: 261, end_frame: 450,
      title: answer ? content.takeaway : '记住', body: answer ? (content.supporting_items?.join(' / ') ?? body) : '',
      props: answer ? {} : {highlight: content.takeaway}, accent_color: '#38BDF8'},
  ]});
  return input;
};
const expandedRequests = JSON.parse(await readFile(new URL('../../tests/fixtures/component-set-expanded-content.json', import.meta.url), 'utf8'));
const expandedLayers = {
  B07: ['Talkcraft-typewriter-reveal', 'Snapcn-TextHighlight'],
  B08: ['Snapcn-TextBuild', 'Snapcn-TextHighlight'],
  B09: ['Snapcn-TextSwap', 'Snapcn-TextHighlight'],
  B10: ['Snapcn-TextBuild', 'Snapcn-TextHighlight'],
  B11: ['Snapcn-TextBuild', 'Snapcn-AnswerHighlight'],
  B12: ['Snapcn-WordFlip', 'Snapcn-TextHighlight'],
  B13: ['Snapcn-TextRewrite', 'Snapcn-TextHighlight'],
  B14: ['Snapcn-SearchTyping', 'Snapcn-AnswerHighlight'],
  B15: ['Talkcraft-title-demote-to-label', 'Snapcn-TextHighlight'],
  B16: ['Talkcraft-title-demote-to-label', 'Talkcraft-keyword-pop-highlight'],
  B17: ['Talkcraft-line-by-line-slide', 'Snapcn-AnswerHighlight'],
  B18: ['Snapcn-TextSwap', 'Snapcn-TextHighlight'],
};
const expandedLayerProps = (componentId, content) => {
  if (componentId === 'Snapcn-TextSwap') return {from_text: content.items[0], to_text: content.items[1]};
  if (componentId === 'Snapcn-TextRewrite') return {from_text: content.items[0], to_text: content.takeaway};
  if (componentId.startsWith('Talkcraft-')) return {items: content.items, highlight: content.takeaway,
    from_text: content.items[0], to_text: content.items[1]};
  return componentId === 'Snapcn-TextHighlight' ? {highlight: content.takeaway} : {};
};
const expandedSample = (id) => {
  const {title, body, ...content} = structuredClone(expandedRequests[id]);
  const [titleComponent, emphasisComponent] = expandedLayers[id];
  return {schema_version: '1', job_id: 'expanded-set-test', revision: 1,
    width: 1080, height: 1920, fps: 30, presentation: 'component_sample', duration_in_frames: 540,
    audio_src: null, captions: [], shots: [{shot_id: id, start_frame: 0, end_frame: 540,
      component_id: mains[id], title, body, source_label: '', asset_src: null,
      accent_color: '#38BDF8', props: {component_set: id, composition: 'rich', rich_content: content}, layers: [
        {component_id: titleComponent, role: 'title', start_frame: 0, end_frame: titleComponent === 'Talkcraft-typewriter-reveal' ? 180 : 540,
          title, body, props: expandedLayerProps(titleComponent, content), accent_color: '#38BDF8'},
        {component_id: emphasisComponent, role: 'emphasis', start_frame: 330, end_frame: 540,
          title: content.takeaway, body: '先停一下｜回拨号码｜保留记录', props: expandedLayerProps(emphasisComponent, content), accent_color: '#38BDF8'},
      ]}]};
};

test('all six registered text-only sets validate without any media, preserving the supplied content', () => {
  for (const id of legacySetIds) {
    const input = sample(id);
    const before = structuredClone(input);
    assert.equal(validateTimeline(input), input);
    assert.deepEqual(input, before);
  }
});

test('text-only marker cannot select a different native component, media slot, or production mode', () => {
  for (const mutate of [
    (v) => {v.presentation = 'production';},
    (v) => {v.shots[0].component_id = 'Rve-StatCounter';},
    (v) => {v.shots[0].props.component_set = 'B19';},
    (v) => {v.shots[0].asset_src = 'videoagents/text-set-test/assets/photo.png';},
    (v) => {v.shots[0].props.content_mode = 'media';},
    (v) => {v.shots[0].props.focus_steps = [];},
    (v) => {v.width = 1920; v.height = 1080;},
  ]) {
    const input = sample('B01'); mutate(input);
    assert.throws(() => validateTimeline(input));
  }
  const legacy = sample('B02');
  delete legacy.shots[0].props.component_set;
  legacy.presentation = 'production';
  assert.doesNotThrow(() => validateTimeline(legacy));
  for (const [id, replacement] of [
    ['B03', {items: ['只有一项']}], ['B05', {items: ['第一步', '第二步']}],
    ['B04', {metric: {label: '演示指标', value: '12.5元'}}],
    ['B04', {metric: {label: '演示指标', value: '30%'}}],
    ['B04', {metric: {label: '演示指标', value: '３９９元'}}],
  ]) {
    const input = sample(id);
    Object.assign(input.shots[0].props, replacement);
    assert.throws(() => validateTimeline(input));
  }
});

test('text-only copy areas stay separate, in the portrait safe area, including three action rows', () => {
  const ordered = ['title', 'main', 'body', 'emphasis', 'identity'].map((key) => boxes[key]);
  for (const [index, box] of ordered.entries()) {
    assert.ok(box.x >= 64 && box.x + box.width <= 1016);
    assert.ok(box.y >= 96 && box.y + box.height <= 1852);
    if (index) assert.ok(ordered[index - 1].y + ordered[index - 1].height < box.y);
  }
  assert.ok(boxes.emphasis.height >= 3 * 76 + 2 * 12);
});

test('rich no-material sets validate richer text, number and core-prop contracts without mutating basic mode', () => {
  for (const id of legacySetIds) {
    const input = richSample(id);
    const before = structuredClone(input);
    assert.equal(validateTimeline(input), input);
    assert.deepEqual(input, before);
  }
  assert.equal(validateTimeline(sample('B04')).shots[0].props.composition, undefined);
});

test('answer highlight supports an emphasis layer while title-only interaction components do not', () => {
  for (const id of ['B02', 'B06']) assert.doesNotThrow(() => validateTimeline(richSample(id)));
  for (const componentId of ['Snapcn-SearchTyping', 'Snapcn-PromptSend', 'Snapcn-AnswerStream']) {
    const input = richSample('B02');
    input.shots[0].layers[1].component_id = componentId;
    assert.throws(() => validateTimeline(input), /does not support emphasis layers/);
  }
});

test('rich no-material sets reject bad totals, inconsistent core props, short duration and non-B rich flags', () => {
  const badTotal = richSample('B04');
  badTotal.shots[0].props.rich_content.numeric_items[2] = '第3次:134元';
  assert.throws(() => validateTimeline(badTotal), /sum to metric/);

  const mismatchKeyword = richSample('B02');
  mismatchKeyword.shots[0].props.keyword = '不一致';
  assert.throws(() => validateTimeline(mismatchKeyword), /keyword must match/);

  const mismatchItems = richSample('B05');
  mismatchItems.shots[0].props.items = ['先停一下', '回拨号码', '换一项'];
  assert.throws(() => validateTimeline(mismatchItems), /props.items must match/);

  const short = richSample('B01');
  short.duration_in_frames = 300;
  short.shots[0].end_frame = 300;
  assert.throws(() => validateTimeline(short), /12 to 20 seconds/);

  const richA = sample('B01');
  richA.shots[0].props.component_set = 'A01';
  richA.shots[0].props.composition = 'rich';
  assert.throws(() => validateTimeline(richA), /component_set must match/);
});

test('rich text-only safe geometry preserves large readable slots and staged timing', () => {
  assert.equal(richNoMaterialBoxesDoNotOverlap(), true);
  assert.ok(richNoMaterialMinimumFont.compact >= 40);
  assert.ok(richBoxes.title.height >= 280);
  assert.ok(richBoxes.stage.width >= 960);
  assert.ok(richBoxes.stage.height >= 1060);
  assert.ok(richBoxes.emphasis.y >= richBoxes.stage.y + richBoxes.stage.height + 40);
  for (const key of ['title', 'stage', 'emphasis', 'identity']) {
    const box = richBoxes[key];
    assert.ok(box.x >= 56 && box.x + box.width <= 1024);
    assert.ok(box.y >= 96 && box.y + box.height <= 1852);
  }
  const timing = richStageTimings(450);
  assert.deepEqual(Object.keys(timing), ['intro', 'expand', 'develop', 'resolve', 'duration']);
  assert.ok(timing.expand >= 90);
  assert.ok(timing.develop - timing.expand >= 90);
  assert.ok(timing.resolve - timing.develop >= 90);
  const items = ['第1次:133元', '第2次:133元', '第3次:133元'].map(parseRichNumericItem);
  assert.equal(richNumericItemsSumToMetric(items, {label: '合计', value: '399元'}), true);
  assert.equal(richNumericItemsSumToMetric(items, {label: '合计', value: '400元'}), false);
});

test('expanded rich no-material sets validate the B07-B18 component contract and layer IDs', () => {
  for (const id of expandedSetIds) {
    const input = expandedSample(id);
    const before = structuredClone(input);
    assert.equal(validateTimeline(input), input);
    assert.deepEqual(input, before);
  }
});

test('expanded no-material sets require rich content and reject incomplete numeric contracts', () => {
  const basic = expandedSample('B07');
  delete basic.shots[0].props.composition;
  delete basic.shots[0].props.rich_content;
  assert.throws(() => validateTimeline(basic), /expanded no-material sets require rich composition/);

  const badNumeric = expandedSample('B10');
  badNumeric.shots[0].props.rich_content.numeric_items[0] = '消息:12.5项';
  assert.throws(() => validateTimeline(badNumeric), /ASCII integer/);

  const badCount = expandedSample('B13');
  badCount.shots[0].props.rich_content.metric.value = '2项';
  assert.throws(() => validateTimeline(badCount), /metric value must equal supporting item count/);
});

test('expanded sets preserve their distinct optional fields and arithmetic relationships', () => {
  for (const id of ['B07', 'B08', 'B09', 'B10']) {
    const input = expandedSample(id);
    assert.equal(input.shots[0].props.rich_content.supporting_items, undefined);
    assert.doesNotThrow(() => validateTimeline(input));
    input.shots[0].props.rich_content.metric.value = '999元';
    assert.throws(() => validateTimeline(input), /units must match|sum to metric|numeric difference/);
  }
  const chat = expandedSample('B17');
  assert.equal(chat.shots[0].props.rich_content.supporting_items.length, 2);
  assert.equal(chat.shots[0].props.rich_content.metric.value, '3问');
  assert.doesNotThrow(() => validateTimeline(chat));
  const missing = expandedSample('B12');
  delete missing.shots[0].props.rich_content.supporting_items;
  assert.throws(() => validateTimeline(missing), /supporting_items/);
  const unused = expandedSample('B11');
  unused.shots[0].props.rich_content.numeric_items = ['一:1项', '二:1项', '三:1项'];
  assert.throws(() => validateTimeline(unused), /numeric_items is unsupported/);
  const steps = expandedSample('B18');
  steps.shots[0].props.rich_content.numeric_items[1] = '现在:4步';
  assert.throws(() => validateTimeline(steps), /maximum numeric step count/);
});

test('expanded safe geometry keeps title, stage, emphasis and identity separated', () => {
  assert.equal(expandedBoxesDoNotOverlap(), true);
  for (const key of ['title', 'stage', 'emphasis', 'identity']) {
    const box = expandedBoxes[key];
    assert.ok(box.x >= 56 && box.x + box.width <= 1024);
    assert.ok(box.y >= 96 && box.y + box.height <= 1852);
  }
  const timing = expandedStageTimings(540);
  assert.ok(timing.expand >= 120);
  assert.ok(timing.develop - timing.expand >= 120);
  assert.ok(timing.resolve - timing.develop >= 110);
});

test('compact cumulative chart keeps the first and final bars inside its SVG, with supplied values and labels', async () => {
  const source = await readFile(new URL('../components/component-horizontal/rve/chart-animation.tsx', import.meta.url), 'utf8');
  const chartModule = {exports: {}};
  new Function('require', 'module', 'exports', ts.transpileModule(source,
    {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText)(
    (name) => name === 'remotion' ? {useCurrentFrame: () => 120, interpolate: () => 1} : require(name),
    chartModule, chartModule.exports);
  const data = [133, 266, 399].map((y, x) => ({x, y, label: `第${x + 1}次`}));
  const markup = renderToStaticMarkup(createElement(chartModule.exports.default, {
    compactBox: true, layout: 'portrait', data, maxValue: 399, title: '逐笔累加', subtitle: '133元×3次＝399元',
  }));
  const svgMatch = markup.match(/<svg[^>]*viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  assert.ok(svgMatch, 'chart SVG must expose a viewBox for responsive bounds');
  const width = Number(svgMatch[1]);
  const bars = [...markup.matchAll(/<rect ([^>]+)>/g)].map((match) =>
    Object.fromEntries([...match[1].matchAll(/(\w+)="([^"]+)"/g)].map((attr) => [attr[1], attr[2]])));
  assert.equal(bars.length, 3);
  for (const bar of bars) {
    assert.ok(Number(bar.x) >= 30);
    assert.ok(Number(bar.x) + Number(bar.width) <= width - 30);
  }
  for (const point of data) {
    assert.ok(markup.includes(`>${point.label}</text>`));
    assert.ok(markup.includes(`>${point.y}</text>`));
  }
});
