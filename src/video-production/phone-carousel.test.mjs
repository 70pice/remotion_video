import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import test from 'node:test';
import {URL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ts from 'typescript';

const nodeRequire = createRequire(import.meta.url);
const load = async (name, resolve = nodeRequire) => {
  const source = await readFile(new URL(name, import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText;
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(resolve, module, module.exports);
  return module.exports;
};
const {phoneCarouselAt} = await load('./phoneCarousel.ts');
const slides = [
  {asset_src: 'app-a.png', start_frame: 0, asset_fit: 'cover'},
  {asset_src: 'app-b.png', start_frame: 90, asset_fit: 'contain'},
  {asset_src: 'app-c.png', start_frame: 180, asset_fit: 'contain'},
];

test('carousel selects images on local boundaries and keeps last page to shot end', () => {
  for (const [frame, index] of [[0,0],[89,0],[90,1],[179,1],[180,2],[299,2]]) {
    assert.equal(phoneCarouselAt(slides, frame, 300).currentIndex, index);
  }
  assert.deepEqual(phoneCarouselAt(slides, 0, 300), {currentIndex: 0, previousIndex: null, opacity: 1});
});

test('only image opacity changes during transition and hard cuts remain supported', () => {
  assert.deepEqual(phoneCarouselAt(slides, 92, 300), {currentIndex: 1, previousIndex: 0, opacity: 0.5});
  assert.deepEqual(phoneCarouselAt(slides, 95, 300), {currentIndex: 1, previousIndex: null, opacity: 1});
  assert.deepEqual(phoneCarouselAt(slides, 90, 300, 0), {currentIndex: 1, previousIndex: null, opacity: 1});
  const shortSlides = [{...slides[0], start_frame: 0}, {...slides[1], start_frame: 2}, {...slides[2], start_frame: 4}];
  assert.equal(phoneCarouselAt(shortSlides, 3, 6, 15).opacity, 1);
  assert.equal(phoneCarouselAt(shortSlides, 5, 6, 15).opacity, 1);
});

let frame = 0;
const material = await load('./PhoneFrameMaterial.tsx', name => {
  if (name === 'remotion') return {Img: props => createElement('img', props),
    OffthreadVideo: ({src, muted, style}) => createElement('video', {src, muted, style}), staticFile: src => src,
    useCurrentFrame: () => frame, useVideoConfig: () => ({fps: 30})};
  if (name === './phoneCarousel') return {phoneCarouselAt};
  if (name.endsWith('/snapcn/phone-frame')) return {PhoneFrame: ({children}) =>
    createElement('section', {'data-single-phone-frame': true}, children)};
  if (name === './adapters/layout') return {useLayout: () => ({unit:1, vertical:true, margin:72,
    contentWidth:936, componentSample:false}), FittedText: ({text}) => createElement('span', {}, text),
    productionFont:'Arial', muted:'#aaa', white:'#fff'};
  if (name === './phoneTutorial' || name === './focusGeometry') return {};
  return nodeRequire(name);
});
const shot = {shot_id:'one-shot', start_frame:330, end_frame:630, component_id:'Snapcn-PhoneFrame',
  title:'固定标题25000人', body:'', asset_src:'app-a.png', source_label:'测试来源', accent_color:'#5B8CFF',
  props:{media_slides:slides, carousel_transition_frames:6}};

test('one persistent phone shell contains all registered images without restarting title layout', () => {
  for (const value of [0, 89, 90, 92, 95, 180, 299]) {
    frame = value;
    const html = renderToStaticMarkup(createElement(material.PhoneFrameMaterial, {shot}));
    assert.equal((html.match(/<section /g) ?? []).length, 1);
    assert.equal((html.match(/固定标题25000人/g) ?? []).length, 1);
    assert.equal((html.match(/data-phone-carousel-index=/g) ?? []).length, 3);
    for (const slide of slides) assert.ok(html.includes(`src="${slide.asset_src}"`));
    assert.ok(html.includes('object-fit:contain'));
  }
});

test('single-image and video inputs retain their existing renderer path', () => {
  for (const [asset, element] of [['legacy.png','img'], ['legacy.mp4','video']]) {
    const html = renderToStaticMarkup(createElement(material.PhoneFrameMaterial,
      {shot:{...shot, asset_src:asset, props:{asset_fit:'contain'}}}));
    assert.ok(html.includes(`<${element} `));
    assert.ok(html.includes(`src="${asset}"`));
    assert.ok(!html.includes('data-phone-carousel-index'));
    assert.equal((html.match(/<section /g) ?? []).length, 1);
  }
});
