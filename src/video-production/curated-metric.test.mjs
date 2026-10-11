import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const load = async (url, remotion = {}) => {
  const source = await readFile(url, 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const nodeRequire = createRequire(import.meta.url);
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(
    name => name === 'remotion' ? remotion : nodeRequire(name), module, module.exports,
  );
  return module.exports;
};

test('production KPI components display supplied amount and unit without demo numbers or percentages', async () => {
  const {curatedScenePropsForShot} = await load(new URL('./curatedMaterial.ts', import.meta.url));
  let config = {width: 1080, height: 1920, fps: 30};
  const passthrough = name => props => createElement(name, props, props.children);
  const {CuratedScene} = await load(new URL('../components/component-horizontal/curated/CuratedScene.tsx', import.meta.url), {
    AbsoluteFill: passthrough('div'), Img: passthrough('img'), OffthreadVideo: passthrough('video'),
    staticFile: src => src, useCurrentFrame: () => 45, useVideoConfig: () => config,
  });
  const metric = {label: '项目累计金额', value: '近13万元', detail: '含采购和服务费用'};
  for (const portrait of [true, false]) {
    config = {width: portrait ? 1080 : 1280, height: portrait ? 1920 : 720, fps: 30};
    const props = curatedScenePropsForShot({component_id: 'RenderComp-KpiCounter', title: '示例项目：费用累计',
      body: '', source_label: '测试来源', accent_color: '#FF6B6B', asset_src: null,
      props: {content_mode: 'metric', metric}}, portrait);
    assert.deepEqual(props.metric, metric);
    const markup = renderToStaticMarkup(createElement(CuratedScene, props));
    for (const value of Object.values(metric)) assert.ok(markup.includes(value));
    for (const invented of ['860', '86%', '+72%', 'verified input']) assert.equal(markup.includes(invented), false);
  }
});
