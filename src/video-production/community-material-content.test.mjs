import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import {createContext, createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';
import {validateTimeline} from './validation.mjs';

const require = createRequire(import.meta.url);
const load = async (file, imports) => {
  const source = await readFile(new URL(file, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText;
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(imports, module, module.exports);
  return module.exports;
};
const passthrough = ({children}) => createElement('div', null, children);
const communityMaterial = await load('./communityMaterial.ts', require);
const {VideoFromTimeline} = await load('./VideoFromTimeline.tsx', (name) => {
  if (name === 'react' || name === 'react/jsx-runtime') return require(name);
  if (name === 'remotion') return {
    AbsoluteFill: passthrough, Sequence: passthrough,
    Img: ({src}) => createElement('img', {src}), OffthreadVideo: () => null,
    staticFile: (src) => src, useCurrentFrame: () => 45,
    useVideoConfig: () => ({width: 1080, height: 1920, fps: 30, durationInFrames: 180}),
  };
  if (name === '@remotion/media') return {Audio: () => null};
  if (name === './adapters/layout') return {
    FittedText: ({text}) => createElement('span', null, text),
    LayoutComponentSample: createContext(false), LayoutHeaderHeight: createContext(0),
    muted: '#94A3B8', white: '#FFFFFF', productionFont: 'Inter',
    useLayout: () => ({unit: 1, vertical: true, margin: 72, contentWidth: 936, componentSample: false}),
  };
  if (name === './captionPages') return {buildCaptionPages: () => []};
  if (name === './communityMaterial') return communityMaterial;
  if (name === './curatedMaterial') return {materializedCommunityComponentIdSet: new Set()};
  if (name === './noMaterialSetGeometry') return {isNoMaterialSet: () => false};
  if (name === './RichMaterialContract') return {isRichMaterialSet: () => false};
  if (name === './ProductionComponentSetScene') return {isProductionComponentSetDesign: () => false};
  if (name === './NativeMediaScenes') return {hasNativeMediaScene: () => false};
  if (name === './SnapcnNativeTitles') return {snapcnNativeTitleIds: []};
  if (name === './TalkcraftNativeTitles') return {
    isTalkcraftNativeTitleId: () => true,
    TalkcraftNativeTitle: ({shot}) => createElement('aside', null, shot.title),
  };
  if (name === './TalkcraftNativeMedia') return {isTalkcraftNativeMediaId: () => false};
  if (name === './registry') return {isSemanticComponent: () => false};
  if (name === './validation.mjs') return {validateTimeline};
  if (['../components/component-horizontal/curated/CuratedScene', './PhoneFrameMaterial',
    './MaterialFocus', './RichMaterialScene', './RichNoMaterialScene', './focusGeometry',
    './phoneTutorial'].includes(name)) return {};
  throw new Error(`Unexpected VideoFromTimeline test import: ${name}`);
});

const timeline = (props, {layered, asset}) => ({
  schema_version: '1', job_id: 'community-content-test', revision: 1,
  width: 1080, height: 1920, fps: 30, duration_in_frames: 180,
  audio_src: null, captions: [], shots: [{
    shot_id: 'community-content', start_frame: 0, end_frame: 180,
    component_id: 'Snapcn-WordFlip', title: '三种用途', body: '同一段说明',
    asset_src: asset ? 'videoagents/community-content-test/image.png' : null,
    source_label: '', accent_color: '#38BDF8', props,
    layers: layered ? [{component_id: 'Talkcraft-keyword-pop-highlight', role: 'emphasis',
      start_frame: 0, end_frame: 180, title: '关键结论', body: '',
      accent_color: '#38BDF8', props: {highlight: '关键结论'}}] : [],
  }],
});

for (const [mode, props, labels] of [
  ['list', {content_mode: 'list', items: ['写代码做应用', '创建服务角色', '自主应答']},
    ['写代码做应用', '创建服务角色', '自主应答']],
  ['metric', {content_mode: 'metric', metric: {label: '项目收入', value: '123元', detail: '三笔合计'}},
    ['项目收入', '123元', '三笔合计']],
]) {
  test(`portrait community ${mode} content appears once with and without layers or media`, () => {
    for (const layered of [false, true]) {
      for (const asset of [false, true]) {
        const input = timeline(props, {layered, asset});
        const markup = renderToStaticMarkup(createElement(VideoFromTimeline, {timeline: input}));
        for (const label of labels) {
          assert.equal(markup.split(label).length - 1, 1,
            `${mode} ${label}, layered=${layered}, asset=${asset}`);
        }
        assert.equal(markup.split('三种用途').length - 1, layered && asset ? 0 : 1);
        assert.equal(markup.split('关键结论').length - 1, layered ? 1 : 0);
      }
    }
  });
}
