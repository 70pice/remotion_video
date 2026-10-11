import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import test from 'node:test';
import {URL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';

const nodeRequire = createRequire(import.meta.url);
const container = ({children}) => createElement('div', {}, children);
const remotion = {AbsoluteFill: container, Sequence: container, staticFile: src => src,
  useCurrentFrame: () => 90, useVideoConfig: () => ({fps: 30, width: 1080, height: 1920}),
  interpolate: (_frame, _input, output) => output.at(-1), spring: () => 1};
const load = async (url, resolve) => {
  const source = await readFile(url, 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText;
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(resolve, module, module.exports);
  return module.exports;
};
const native = await load(new URL('../components/component-horizontal/rve/stat-counter.tsx', import.meta.url),
  name => name === 'remotion' ? remotion : nodeRequire(name));
const scenes = await load(new URL('./NativeMediaScenes.tsx', import.meta.url), name => {
  if (name === 'remotion') return remotion;
  if (name.endsWith('/rve/stat-counter')) return native;
  if (name === './adapters/layout') return {FittedText: container, productionFont: 'Microsoft YaHei', white: '#fff', muted: '#aaa'};
  if (name === './noMaterialSetGeometry') return {isNoMaterialSet: () => false};
  if (name.includes('../components/')) return {__esModule: true, default: container};
  return nodeRequire(name);
});
const shot = value => ({shot_id: 'counter', start_frame: 0, end_frame: 90,
  component_id: 'Rve-StatCounter', title: '示例项目累计金额', body: '', asset_src: null,
  source_label: '测试来源', accent_color: '#5B8CFF', layers: [],
  props: {content_mode: 'metric', metric: {label: '项目金额累计', value, detail: '含采购和服务费用'}}});

test('real native counter preserves approximate Chinese amounts and exact units', () => {
  for (const value of ['近13万元', '约13万元', '13万元', '至少13万元']) {
    const markup = renderToStaticMarkup(scenes.renderNativeMediaScene(shot(value)));
    assert.ok(markup.includes(value), value);
    assert.ok(markup.includes('含采购和服务费用'));
    assert.ok(markup.includes('测试来源'));
    assert.ok(!markup.includes('1,247'));
  }
});

test('native counter still rejects mixed claims, ranges and percentages', () => {
  for (const value of ['损失13万元', '近13-14万元', '约40%']) {
    assert.throws(() => scenes.renderNativeMediaScene(shot(value)), /rejected|rejects/);
  }
});

test('charts cannot silently turn approximate or bounded values into exact values', () => {
  const input = {...shot('13万元'), component_id: 'Rve-ComparisonChart', props: {items: ['甲:近13万元', '乙:14万元']}};
  assert.throws(() => scenes.renderNativeMediaScene(input), /approximate or bounded chart values are rejected/);
});

test('native legacy default keeps its original unqualified number', () => {
  const markup = renderToStaticMarkup(createElement(native.default));
  assert.ok(markup.includes('1,247'));
  assert.ok(!markup.includes('近1,247') && !markup.includes('约1,247'));
});
