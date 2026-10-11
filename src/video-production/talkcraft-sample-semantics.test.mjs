import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import React, {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const require = createRequire(import.meta.url);
let currentFrame = 0;

const remotionStub = {
  AbsoluteFill: ({children, style}) => createElement('div', {style: {position: 'absolute', inset: 0, ...style}}, children),
  Loop: ({children}) => createElement(React.Fragment, null, children),
  OffthreadVideo: (props) => createElement('video', props),
  continueRender: () => undefined,
  delayRender: () => 1,
  random: (seed) => {
    let hash = 0;
    for (const ch of String(seed)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    return (hash % 1000) / 1000;
  },
  useCurrentFrame: () => currentFrame,
};

const loadCard = async (relativePath) => {
  const source = await readFile(new URL(relativePath, import.meta.url), 'utf8');
  const module = {exports: {}};
  const compiled = ts.transpileModule(source, {
    compilerOptions: {
      esModuleInterop: true,
      jsx: ts.JsxEmit.React,
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

const renderCard = (Component, props, frame) => {
  currentFrame = frame;
  return renderToStaticMarkup(createElement(Component, props));
};

const pathStarts = (markup) => [...markup.matchAll(/<path[^>]* d="M ([\d.-]+) ([\d.-]+)/g)]
  .map((match) => ({x: Number(match[1]), y: Number(match[2])}));

test('typewriter reveal completes long supplied copy and does not leak the demo preset', async () => {
  const TypewriterReveal = await loadCard('../components/component-horizontal/video-talkcraft/cards/typewriter-reveal.tsx');
  const line1 = '这是一行比默认更长的自定义档案标题';
  const line2 = '这里继续补充更长的说明文字，必须完整打出来';
  const markup = renderCard(TypewriterReveal, {line1, line2}, 420);

  assert.match(markup, new RegExp(line1));
  assert.match(markup, new RegExp(line2));
  assert.doesNotMatch(markup, /北京 · 2008年8月8日/);
  assert.doesNotMatch(markup, /奥运会开幕当晚/);
});

test('strike and replace renders the supplied prefix, values and suffix instead of the demo sentence', async () => {
  const StrikeAndReplace = await loadCard('../components/component-horizontal/video-talkcraft/cards/strike-and-replace.tsx');
  const markup = renderCard(StrikeAndReplace, {
    prefix: '先纠正一个判断：',
    from: '能视频',
    to: '能核实',
    suffix: '，才进入下一步',
  }, 40);

  for (const text of ['先纠正一个判断：', '能视频', '能核实', '，才进入下一步']) {
    assert.match(markup, new RegExp(text));
  }
  assert.doesNotMatch(markup, /上下文窗口是/);
  assert.doesNotMatch(markup, /一年翻了八倍/);
});

test('ink underline keeps the legacy default boxes and moves custom underlines with the supplied text', async () => {
  const InkUnderline = await loadCard('../components/component-horizontal/video-talkcraft/cards/ink-underline.tsx');
  const legacy = renderCard(InkUnderline, {}, 80);
  const legacyStarts = pathStarts(legacy);
  assert.equal(legacyStarts.length, 2);
  assert.ok(Math.abs(legacyStarts[0].x - 772) < 8);
  assert.match(legacy, /成本上涨/);
  assert.match(legacy, /渠道结构/);

  const short = renderCard(InkUnderline, {title: '先看', wrong: '付款', right: '来源'}, 80);
  const long = renderCard(InkUnderline, {title: '先看付款动作再判断', wrong: '付款', right: '来源'}, 80);
  const shortStarts = pathStarts(short);
  const longStarts = pathStarts(long);

  assert.equal(shortStarts.length, 2);
  assert.equal(longStarts.length, 2);
  assert.match(long, /先看付款动作再判断/);
  assert.match(long, /付款/);
  assert.match(long, /来源/);
  assert.doesNotMatch(long, /成本上涨/);
  assert.ok(longStarts[0].x > shortStarts[0].x + 120);
});
