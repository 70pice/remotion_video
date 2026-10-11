import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';

const nodeRequire = createRequire(import.meta.url);

const loadTsx = async (url, remotion = {}) => {
  const source = await readFile(url, 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const module = {exports: {}};
  new Function('require', 'module', 'exports', compiled)(
    name => name === 'remotion' ? remotion : nodeRequire(name), module, module.exports,
  );
  return module.exports;
};

const remotionStub = {
  AbsoluteFill: props => createElement('div', props, props.children),
  Loop: props => createElement('div', props, props.children),
  OffthreadVideo: props => createElement('video', props),
  Img: props => createElement('img', props),
  useCurrentFrame: () => 90,
};

test('Talkcraft native media renderer exposes at least 13 distinct media-required bindings without reticle double counting', async () => {
  const source = await readFile(new URL('./TalkcraftNativeMedia.tsx', import.meta.url), 'utf8');
  const ids = [...source.matchAll(/id: 'Talkcraft-[^']+'/g)].map(match => match[0].slice(5, -1));
  assert.ok(ids.length >= 13, `expected at least 13 bindings, got ${ids.length}`);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(ids.includes('Talkcraft-reticle-lock-on'), false);
  for (const id of ['Talkcraft-slow-push-in', 'Talkcraft-slow-pull-reveal', 'Talkcraft-sway-parallax',
    'Talkcraft-orbit-drift', 'Talkcraft-crash-zoom-punch', 'Talkcraft-magnifier-detail', 'Talkcraft-media-pop-in',
    'Talkcraft-evidence-scroll-tour', 'Talkcraft-tilt-3d-page', 'Talkcraft-scanline-annotate',
    'Talkcraft-cursor-locked-zoom', 'Talkcraft-pip-zoom-box', 'Talkcraft-focus-dim-spotlight']) {
    assert.ok(ids.includes(id), `${id} should be bound`);
  }
  assert.match(source, /content_constraints: \['media_required'\]/);
  assert.match(source, /image_only: true/);
  assert.match(source, /isImageAsset/);
  assert.match(source, /cropStyleFor/);
  assert.match(source, /componentSample \? safeBox\.y : hasOverlayLayers \? 520 : safeBox\.y/);
  assert.match(source, /\.\.\.TALKCRAFT_MEDIA_SAFE_BOX, y: 600, height: 850/);
  assert.doesNotMatch(source, /labelFor\(copy, '重点区域'\)|labelFor\(copy, '素材截图'\)|labelFor\(copy, '证据截图'\)/);
  assert.match(source, /IsolatedCard/);
  assert.match(source, /throw new Error\(`Talkcraft native media/);
});


test('Talkcraft native media adapter restores layout CSS for media-only component branches', async () => {
  const source = await readFile(new URL('./TalkcraftNativeMedia.tsx', import.meta.url), 'utf8');
  assert.match(source, /talkcraftNativeMediaClassName/);
  assert.match(source, /talkcraft-production-media \$\{talkcraftNativeMediaClassName\(binding\.id\)\}/);

  for (const selector of [
    '.native-media-slow-push-in .camera',
    '.native-media-slow-pull-reveal .camera',
    '.native-media-tilt-3d-page .world',
    '.native-media-tilt-3d-page .camera',
    '.native-media-tilt-3d-page .page',
    '.native-media-sway-parallax .camera',
    '.native-media-orbit-drift .camera',
    '.native-media-magnifier-detail .shot',
    '.native-media-cursor-locked-zoom .camera',
  ]) {
    assert.ok(source.includes(selector), `${selector} should be present in production media CSS`);
  }

  assert.match(source, /native-media-tilt-3d-page \.camera \{[^}]*width: 792px; height: 452px/s);
  assert.match(source, /native-media-slow-push-in \.camera,[\s\S]*position: absolute; inset: 0; will-change: transform/);
  assert.match(source, /native-media-magnifier-detail \.shot \{[^}]*height: 308px/s);
});

test('Talkcraft media card production branches render supplied image without demo page copy', async () => {
  const {default: SlowPushIn} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/slow-push-in.tsx', import.meta.url), remotionStub);
  const push = renderToStaticMarkup(createElement(SlowPushIn, {mediaSrc: '/assets/chat.png', mediaFit: 'contain', mediaStyle: {left: '-20%', width: '200%'}}));
  assert.ok(push.includes('/assets/chat.png'));
  assert.ok(push.includes('left:-20%'));
  assert.ok(push.includes('width:200%'));
  assert.equal(push.includes('推理时算力'), false);

  const {default: MediaPopIn} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/media-pop-in.tsx', import.meta.url), remotionStub);
  const pop = renderToStaticMarkup(createElement(MediaPopIn, {mediaSrc: '/assets/app.png', label: '真实交友界面'}));
  assert.ok(pop.includes('/assets/app.png'));
  assert.ok(pop.includes('真实交友界面'));
  assert.equal(pop.includes('充值记录'), false);

  const {default: CursorLockedZoom} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/cursor-locked-zoom.tsx', import.meta.url), remotionStub);
  const cursor = renderToStaticMarkup(createElement(CursorLockedZoom, {mediaSrc: '/assets/terminal.png'}));
  assert.ok(cursor.includes('/assets/terminal.png'));
  assert.equal(cursor.includes('ffmpeg -i raw.mov'), false);

  const {default: EvidenceScrollTour} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/evidence-scroll-tour.tsx', import.meta.url), remotionStub);
  const evidence = renderToStaticMarkup(createElement(EvidenceScrollTour, {mediaSrc: '/assets/report.png', label: '警方通报截图'}));
  assert.ok(evidence.includes('/assets/report.png'));
  assert.ok(evidence.includes('警方通报截图'));
  assert.equal(evidence.includes('个人借款服务协议'), false);
});

test('work detail annotation shares the native tilted page transform without changing legacy white stage', async () => {
  const {default: Tilt3dPage} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/tilt-3d-page.tsx', import.meta.url), remotionStub);
  const guided = renderToStaticMarkup(createElement(Tilt3dPage, {mediaSrc: '/assets/work.png', mediaFit: 'contain',
    transparentStage: true, mediaOverlay: createElement('svg', {'data-focus': 'phone-detail'})}));
  assert.match(guided, /class="camera" style="transform:rotateY\(/);
  assert.match(guided, /class="page"><img[^>]+\/assets\/work.png[^>]*\/><svg data-focus="phone-detail"><\/svg><\/div>/);
  assert.match(guided, /background:transparent/);
  const legacy = renderToStaticMarkup(createElement(Tilt3dPage, {mediaSrc: '/assets/work.png'}));
  assert.match(legacy, /background:#ffffff/);
  assert.doesNotMatch(legacy, /data-focus/);
});
