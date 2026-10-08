import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import {fileURLToPath} from 'node:url';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {interpolate, spring} from 'remotion';

const nodeRequire = createRequire(import.meta.url);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../..');

let frame = 0;
let videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};

const loadAdapterModules = async () => {
  const cache = new Map();
  const resolveLocal = (fromPath, request) => {
    const base = path.posix.normalize(path.posix.join(path.posix.dirname(fromPath), request));
    const candidates = request.endsWith('.tsx') || request.endsWith('.ts') ? [base] : [
      `${base}.tsx`,
      `${base}.ts`,
      path.posix.join(base, 'index.tsx'),
      path.posix.join(base, 'index.ts'),
    ];
    return candidates.find((candidate) => fs.existsSync(path.join(root, candidate)));
  };
  const load = (relativePath) => {
    const normalized = relativePath.replaceAll('\\', '/');
    if (cache.has(normalized)) return cache.get(normalized).exports;
    const source = fs.readFileSync(path.join(root, normalized), 'utf8');
    const compiled = ts.transpileModule(source, {compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    }}).outputText;
    const module = {exports: {}};
    cache.set(normalized, module);
    const requireFrom = (name) => {
      if (name === 'remotion') return {
        Easing: {
          bezier: () => (input) => input,
          cubic: (input) => input ** 3,
          in: (fn) => fn,
        },
        interpolate,
        spring,
        useCurrentFrame: () => frame,
        useVideoConfig: () => videoConfig,
      };
      if (name === './layout') return cache.get('src/video-production/adapters/layout.tsx')?.exports ??
        (() => { throw new Error('layout.tsx must be loaded before data.tsx'); })();
      if (name.startsWith('.')) {
        const resolved = resolveLocal(normalized, name);
        if (resolved) return load(resolved);
      }
      return nodeRequire(name);
    };
    new Function('require', 'module', 'exports', compiled)(requireFrom, module, module.exports);
    return module.exports;
  };
  await load('src/video-production/adapters/layout.tsx');
  return {...load('src/video-production/adapters/data.tsx'), load};
};

const shot = (items, props = {}, overrides = {}) => ({
  shot_id: 'data-shot',
  start_frame: 0,
  end_frame: 120,
  component_id: 'data',
  title: 'Token 价格和算力需求',
  body: overrides.body ?? '同一张数据卡要先给上下文，再揭示结论。',
  asset_src: null,
  source_label: '测试数据',
  accent_color: '#B7F36B',
  props: {items, ...props},
});

const renderData = async (items, props = {}, overrides = {}) => {
  const {DataAdapter} = await loadAdapterModules();
  return renderToStaticMarkup(createElement(DataAdapter, {shot: shot(items, props, overrides), durationInFrames: 120}));
};

const embeddedDonutLegendStyle = (markup) => {
  const match = markup.match(/data-donut-legend="embedded" style="([^"]+)"/);
  assert.ok(match, 'embedded donut legend container should render with inspectable styles');
  return match[1];
};

test('data cards keep labels and details visible on the first frame while cued values wait', async () => {
  frame = 0;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {label: '单位智能价格', value: '4×', detail: '先看到比较对象和单位说明', reveal_frame: 30},
    {label: 'H100 算力价格', value: '15×', detail: '等待旁白讲到再出数字', reveal_frame: 45},
  ]);
  assert.match(markup, /单位智能价格/);
  assert.match(markup, /H100 算力价格/);
  assert.match(markup, /先看到比较对象和单位说明/);
  assert.match(markup, /等待旁白讲到再出数字/);
  assert.doesNotMatch(markup, /4×/);
  assert.doesNotMatch(markup, /15×/);
  assert.doesNotMatch(markup, /即将揭示/);
  assert.doesNotMatch(markup, /单位：/);
});

test('cued data values are hidden before the cue and rendered after the cue', async () => {
  const items = [
    {label: '单位智能价格', value: '4×', detail: '下降幅度', reveal_frame: 30},
    {label: 'H100 算力价格', value: '15×', detail: '反向走高', reveal_frame: 45},
  ];
  frame = 29;
  assert.doesNotMatch(await renderData(items), /4×/);
  frame = 44;
  const firstOnly = await renderData(items);
  assert.match(firstOnly, /4×/);
  assert.doesNotMatch(firstOnly, /15×/);
  frame = 60;
  const both = await renderData(items);
  assert.match(both, /4×/);
  assert.match(both, /15×/);
  assert.doesNotMatch(both, /即将揭示/);
});

test('two-item portrait data shots prefer a vertical stack', async () => {
  frame = 0;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {label: '左图', value: '更便宜'},
    {label: '右图', value: '更贵'},
  ]);
  assert.match(markup, /data-data-grid="true"/);
  assert.match(markup, /data-columns="1"/);
  assert.match(markup, /data-rows="2"/);
});

test('data items without reveal cues still show their supplied values immediately', async () => {
  frame = 0;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {label: '无需等待', value: '直接显示', detail: '保持无 cue 行为'},
  ]);
  assert.match(markup, /无需等待/);
  assert.match(markup, /直接显示/);
  assert.match(markup, /保持无 cue 行为/);
  assert.doesNotMatch(markup, /即将揭示/);
});

test('bar data uses one zero-based scale and preserves exact width ratios', async () => {
  frame = 70;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {label: '普通聊天', value: '1×', detail: '基准', reveal_frame: 10, numeric_value: 1},
    {label: '单 Agent', value: '约4×', detail: '一次工具循环', reveal_frame: 20, numeric_value: 4},
    {label: '多 Agent', value: '约15×', detail: '并行任务', reveal_frame: 30, numeric_value: 15},
  ], {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(markup, /data-data-bars="true"/);
  assert.match(markup, /width:936px/);
  assert.match(markup, /data-bar-ratio="0.0667"/);
  assert.match(markup, /width:6\.666666666666667%/);
  assert.match(markup, /data-bar-ratio="0.2667"/);
  assert.match(markup, /width:26\.666666666666668%/);
  assert.match(markup, /data-bar-ratio="1"/);
  assert.match(markup, /width:100%/);
});

test('bar labels stay visible while cued values avoid leaking future final text', async () => {
  const items = [
    {label: '普通聊天', value: '1×', detail: '基准', reveal_frame: 10, numeric_value: 1},
    {label: '单 Agent', value: '约4×', detail: '一次工具循环', reveal_frame: 30, numeric_value: 4},
    {label: '多个Agent并行', value: '约15倍', detail: '并行任务', reveal_frame: 50, numeric_value: 15},
  ];
  frame = 0;
  const before = await renderData(items, {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(before, /普通聊天/);
  assert.doesNotMatch(before, /基准/);
  assert.doesNotMatch(before, /一次工具循环/);
  assert.doesNotMatch(before, /并行任务/);
  assert.doesNotMatch(before, /1×/);
  assert.doesNotMatch(before, /约4×/);
  assert.match(before, /多个Agent并行/);
  assert.doesNotMatch(before, /多个Agent\.\.\./);
  assert.doesNotMatch(before, /约15倍/);
  frame = 17;
  const during = await renderData(items, {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(during, /1×/);
  assert.match(during, /基准/);
  assert.doesNotMatch(during, /约4×/);
  assert.doesNotMatch(during, /一次工具循环/);
  assert.doesNotMatch(during, /约15倍/);
  frame = 70;
  const settled = await renderData(items, {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(settled, /1×/);
  assert.match(settled, /约4×/);
  assert.match(settled, /约15倍/);
});

test('donut data keeps labels visible, uses 100-percent complements, and reveals center text on cue', async () => {
  const items = [
    {label: 'Agents', value: '最高86%', detail: '缓存命中', reveal_frame: 20, numeric_value: 86},
    {label: 'Humans', value: '29%', detail: '人工命中', reveal_frame: 40, numeric_value: 29},
  ];
  frame = 0;
  const before = await renderData(items, {visualization: 'donuts', unit: '%'});
  assert.match(before, /data-data-donuts="true"/);
  assert.match(before, /data-donut-count="2"/);
  assert.match(before, /Agents/);
  assert.doesNotMatch(before, /缓存命中/);
  assert.doesNotMatch(before, /人工命中/);
  assert.doesNotMatch(before, /Completion Rate/);
  assert.doesNotMatch(before, />0%<\/text>/);
  assert.doesNotMatch(before, /最高86%/);
  assert.doesNotMatch(before, /data-donut-segment=/);
  frame = 28;
  const during = await renderData(items, {visualization: 'donuts', unit: '%'});
  assert.match(during, /最高86%/);
  assert.match(during, /缓存命中/);
  assert.doesNotMatch(during, /人工命中/);
  frame = 60;
  const settled = await renderData(items, {visualization: 'donuts', unit: '%'});
  assert.match(settled, /最高86%/);
  assert.match(settled, /29%/);
  assert.match(settled, /人工命中/);
  assert.match(settled, /data-donut-ratio="0.86"/);
  assert.match(settled, /data-donut-ratio="0.14"/);
  assert.match(settled, /data-donut-ratio="0.29"/);
  assert.match(settled, /data-donut-ratio="0.71"/);
});

test('embedded bars keep exact scale_max, preserve zero values, and avoid fake minimum bar width', async () => {
  frame = 40;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {label: '零值', value: '0×', detail: '真实为零', reveal_frame: 10, numeric_value: 0},
    {label: '上限', value: '120 指数', detail: 'scale max', reveal_frame: 10, numeric_value: 120},
  ], {visualization: 'bars', scale_max: 120, unit: '指数'});
  assert.match(markup, /data-bar-ratio="0"/);
  assert.match(markup, /data-bar-fill="零值"[^>]*style="width:0%/);
  assert.match(markup, /data-bar-ratio="1"/);
  assert.match(markup, /data-bar-fill="上限"[^>]*style="width:100%/);
});

test('non-embedded animated bar chart keeps the original portrait demo sizing defaults', async () => {
  frame = 90;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const {load} = await loadAdapterModules();
  const {AnimatedBarChart} = load('src/components/component-horizontal/remotion-ui/scenes/animated-bar-chart/index.tsx');
  const markup = renderToStaticMarkup(createElement(AnimatedBarChart, {
    data: [{label: 'Alpha', value: 10}],
  }));
  assert.match(markup, /font-size:46px/);
  assert.match(markup, /font-size:52px/);
  assert.match(markup, /height:92px/);
  assert.match(markup, /grid-template-columns:159px 1fr 150px/);
});

test('donut layout remains bounded on small horizontal cards without default English or token-specific remainder labels', async () => {
  frame = 60;
  videoConfig = {fps: 30, width: 1080, height: 720, durationInFrames: 120};
  const markup = await renderData([
    {label: 'Agents', value: '最高86%', reveal_frame: 10, numeric_value: 86},
    {label: 'Humans', value: '29%', reveal_frame: 10, numeric_value: 29},
  ], {visualization: 'donuts'}, {body: ''});
  assert.match(markup, /data-donut-count="2"/);
  assert.doesNotMatch(markup, /Completion Rate/);
  assert.doesNotMatch(markup, /其他 Token/);
  assert.match(markup, /其他部分/);
  assert.doesNotMatch(markup, /height:300px/);
});

test('single Chinese donut uses the 936 by 816 main area without clipped wrapped legend rows', async () => {
  frame = 60;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {
      label: 'Agent Token中的缓存占比',
      value: '最高86%',
      detail: 'OpenRouter平台；余下部分为其他Token',
      reveal_frame: 10,
      numeric_value: 86,
    },
  ], {visualization: 'donuts'});
  assert.match(markup, /Agent Token中的缓存占比/);
  assert.match(markup, /OpenRouter平台；余下部分为其他Token/);
  assert.match(markup, /最高86%/);
  assert.match(markup, /其他部分/);
  const legendStyle = embeddedDonutLegendStyle(markup);
  assert.match(legendStyle, /height:110px/);
  assert.match(legendStyle, /left:0/);
  assert.match(legendStyle, /right:0/);
  assert.match(legendStyle, /width:100%/);
  assert.match(legendStyle, /display:grid/);
  assert.match(legendStyle, /grid-template-rows:repeat\(2,\s*minmax\(0,\s*1fr\)\)/);
  assert.match(legendStyle, /padding:0 12px/);
  assert.doesNotMatch(legendStyle, /translateX/);
  assert.doesNotMatch(legendStyle, /flex-wrap/);
  assert.match(markup, /data-donut-legend-item="Agent Token中的缓存占比"/);
  assert.match(markup, /data-donut-legend-item="其他部分"/);
  assert.match(markup, /white-space:nowrap/);
  assert.match(markup, /text-overflow:clip/);
  assert.doesNotMatch(markup, /Completion Rate/);
  assert.doesNotMatch(markup, /其他 Token/);
});

test('single Chinese donut before cue has no colored cap endpoint', async () => {
  frame = 0;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const markup = await renderData([
    {
      label: 'Agent Token中的缓存占比',
      value: '最高86%',
      detail: 'OpenRouter平台；余下部分为其他Token',
      reveal_frame: 10,
      numeric_value: 86,
    },
  ], {visualization: 'donuts'});
  assert.match(markup, /Agent Token中的缓存占比/);
  assert.doesNotMatch(markup, /data-donut-segment=/);
  assert.doesNotMatch(markup, /最高86%/);
  assert.doesNotMatch(markup, /OpenRouter平台；余下部分为其他Token/);
});

test('cued chart details with numeric facts do not render before their reveal cue', async () => {
  frame = 0;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const barsBefore = await renderData([
    {label: '多 Agent', value: '约15倍', detail: '约15倍是同源观测，不是受控测试', reveal_frame: 20, numeric_value: 15},
  ], {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(barsBefore, /多 Agent/);
  assert.doesNotMatch(barsBefore, /约15倍/);
  assert.doesNotMatch(barsBefore, /同源观测/);
  const donutBefore = await renderData([
    {label: '缓存占比', value: '最高86%', detail: '其余14%是其他Token，不代表重算量', reveal_frame: 20, numeric_value: 86},
  ], {visualization: 'donuts'});
  assert.match(donutBefore, /缓存占比/);
  assert.doesNotMatch(donutBefore, /最高86%/);
  assert.doesNotMatch(donutBefore, /其余14%/);
});

test('cued chart details reveal completely after their cue', async () => {
  frame = 40;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const barsAfter = await renderData([
    {label: '多 Agent', value: '约15倍', detail: '约15倍是同源观测，不是受控测试', reveal_frame: 20, numeric_value: 15},
  ], {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(barsAfter, /约15倍/);
  assert.match(barsAfter, /同源观测/);
  const donutAfter = await renderData([
    {label: '缓存占比', value: '最高86%', detail: '其余14%是其他Token，不代表重算量', reveal_frame: 20, numeric_value: 86},
  ], {visualization: 'donuts'});
  assert.match(donutAfter, /最高86%/);
  assert.match(donutAfter, /其余14%是其他Token，不代表重算量/);
});

test('chart details without reveal cues render immediately', async () => {
  frame = 0;
  videoConfig = {fps: 30, width: 1080, height: 1920, durationInFrames: 120};
  const bars = await renderData([
    {label: '即时条图', value: '约15倍', detail: '无 cue 立即显示 detail', numeric_value: 15},
  ], {visualization: 'bars', scale_max: 15, unit: '倍'});
  assert.match(bars, /约15倍/);
  assert.match(bars, /无 cue 立即显示 detail/);
  const donuts = await renderData([
    {label: '即时圆环', value: '最高86%', detail: '无 cue 立即显示圆环 detail', numeric_value: 86},
  ], {visualization: 'donuts'});
  assert.match(donuts, /最高86%/);
  assert.match(donuts, /无 cue 立即显示圆环 detail/);
});

test('chart data rejects missing numeric values instead of silently dropping facts', async () => {
  frame = 0;
  await assert.rejects(
    () => renderData([{label: '缺数字', value: '约4×'}], {visualization: 'bars'}),
    /requires numeric_value/,
  );
});

test('donut data rejects more than two items instead of slicing away facts', async () => {
  frame = 0;
  await assert.rejects(
    () => renderData([
      {label: 'A', value: '10%', numeric_value: 10},
      {label: 'B', value: '20%', numeric_value: 20},
      {label: 'C', value: '30%', numeric_value: 30},
    ], {visualization: 'donuts'}),
    /at most 2 items/,
  );
});
