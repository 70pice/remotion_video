import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require = createRequire(import.meta.url);
let currentFrame = 120;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const remotionStub = {
  AbsoluteFill: ({children, style}) => createElement('div', {style}, children),
  delayRender: () => 1,
  continueRender: () => {},
  interpolate: (value, input, output) => {
    const progress = clamp((value - input[0]) / Math.max(1e-6, input[input.length - 1] - input[0]), 0, 1);
    return output[0] + (output[output.length - 1] - output[0]) * progress;
  },
  spring: () => 1,
  useCurrentFrame: () => currentFrame,
  useVideoConfig: () => ({fps: 30, width: 1080, height: 1920}),
};

const loadComponent = async (relativePath) => {
  const source = await readFile(new URL(relativePath, import.meta.url), 'utf8');
  const module = {exports: {}};
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      jsx: ts.JsxEmit.ReactJSX,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText;
  new Function('require', 'module', 'exports', compiled)(
    (name) => name === 'remotion' ? remotionStub : require(name),
    module,
    module.exports,
  );
  return module.exports.default;
};

test('ChartAnimation compactBox scales to its slot and keeps real labels, values and units', async () => {
  const ChartAnimation = await loadComponent('../components/component-horizontal/rve/chart-animation.tsx');
  const markup = renderToStaticMarkup(createElement(ChartAnimation, {
    compactBox: true,
    title: '100元预算拆分',
    subtitle: '演示预算，不代表真实收费',
    unit: '元',
    maxValue: 100,
    data: [
      {x: 0, y: 30, label: '沟通'},
      {x: 1, y: 20, label: '核实'},
      {x: 2, y: 50, label: '预留'},
    ],
  }));

  assert.match(markup, /width="100%"/);
  assert.match(markup, /height="100%"/);
  assert.match(markup, /viewBox="0 0 640 360"/);
  assert.doesNotMatch(markup, /860px/);
  assert.doesNotMatch(markup, /Jan|Feb|Monthly Performance/);
  const maxTick = markup.match(/<text x="([\d.]+)"[^>]*text-anchor="end"[^>]*>100元<\/text>/);
  assert.ok(maxTick, 'maximum axis tick must show its complete amount and unit');
  assert.ok(Number(maxTick[1]) >= 3 * 12 + 19, 'reserve horizontal space for the full tick');
  for (const text of ['100元预算拆分', '演示预算，不代表真实收费', '沟通', '核实', '预留', '30元', '20元', '50元']) {
    assert.match(markup, new RegExp(text));
  }

  const rects = [...markup.matchAll(/<rect ([^>]+)>/g)].map((match) =>
    Object.fromEntries([...match[1].matchAll(/(\w+)="([^"]+)"/g)].map((attr) => [attr[1], attr[2]])));
  assert.equal(rects.length, 3);
  for (const rect of rects) {
    const x = Number(rect.x);
    const width = Number(rect.width);
    const y = Number(rect.y);
    assert.ok(x >= 54);
    assert.ok(x + width <= 640 - 54);
    assert.ok(y >= 104);
    assert.ok(y <= 360 - 58);
  }
});

test('SplitScreen compactBox keeps 24 Chinese characters readable inside short portrait slots', async () => {
  const SplitScreen = await loadComponent('../components/component-horizontal/rve/split-screen.tsx');
  const leftText = '先看付款动作再核实身份来源';
  const rightText = '能聊天不等于真实可信身份';
  const markup = renderToStaticMarkup(createElement(SplitScreen, {
    layout: 'portrait',
    productionCompact: true,
    largeCopy: true,
    compactBox: true,
    leftTitle: '以前一步',
    leftText,
    rightTitle: '现在三步',
    rightText,
  }));

  for (const text of ['以前一步', leftText, '现在三步', rightText]) {
    assert.match(markup, new RegExp(text));
  }
  assert.match(markup, /font-size:48px/);
  assert.match(markup, /font-size:34px/);
  assert.match(markup, /padding:18px 22px/);
  assert.doesNotMatch(markup, /font-size:4rem|font-size:3\.2rem|padding:3\.2rem/);
});

test('three compact action rows fit a 270px slot without cutting off the final step', async () => {
  const ProgressSteps = await loadComponent('../components/component-horizontal/rve/progress-steps.tsx');
  const markup = renderToStaticMarkup(createElement(ProgressSteps, {
    layout: 'portrait', compactBox: true, compactSpacing: true, title: '',
    steps: ['先停一下', '回拨核实', '记录结果'], secondsPerStep: 2,
  }));
  assert.match(markup, /height:60px/);
  assert.match(markup, /height:22px/);
  assert.ok(3 * 60 + 2 * 22 + 14 + 12 <= 270);
  for (const text of ['先停一下', '回拨核实', '记录结果']) assert.match(markup, new RegExp(text));
});

test('optional result hold retains final supplied copy while standalone Talkcraft exits remain unchanged', async () => {
  currentFrame = 510;
  try {
    const SourceConverge = await loadComponent('../components/component-horizontal/video-talkcraft/cards/source-converge.tsx');
    const ErrorRetype = await loadComponent('../components/component-horizontal/video-talkcraft/cards/error-retype.tsx');
    for (const [Component, props] of [
      [SourceConverge, {title: '角色链路', sources: ['AI文字', '真人视频', '付款入口'], hub: '链路', caption: '分清角色'}],
      [ErrorRetype, {prefix: '改判断', first: '会聊天＝真人', second: '会聊天≠可信'}],
    ]) {
      const standalone = renderToStaticMarkup(createElement(Component, props));
      const held = renderToStaticMarkup(createElement(Component, {...props, holdResult: true}));
      if (props.title) {
        assert.match(standalone, /class="scv-ttl" style="opacity:0/);
        assert.match(held, /class="scv-ttl" style="opacity:1/);
        assert.ok(held.includes(props.caption));
      } else {
        assert.match(standalone, /<span style="opacity:0">改判断<\/span>/);
        assert.match(held, /<span style="opacity:1">改判断<\/span>/);
        for (const char of props.second) assert.ok(held.includes(`>${char}</span>`));
      }
    }
  } finally {
    currentFrame = 120;
  }
});
