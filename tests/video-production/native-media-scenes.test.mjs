import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {URL} from 'node:url';

const sourcePath = new URL('../../src/video-production/NativeMediaScenes.tsx', import.meta.url);
const kenBurnsPath = new URL('../../src/components/component-horizontal/bits/examples/KenBurns.tsx', import.meta.url);
const cursorFlyoverPath = new URL('../../src/components/component-horizontal/bits/examples/CursorFlyover.tsx', import.meta.url);
const source = await readFile(sourcePath, 'utf8');
const kenBurnsSource = await readFile(kenBurnsPath, 'utf8');
const cursorFlyoverSource = await readFile(cursorFlyoverPath, 'utf8');

const supportIds = [...source.matchAll(/\{component_id: '([^']+)', library: '([^']+)', origin: '([^']+)', media: (true|false), source: '([^']+)'\}/g)]
  .map((match) => ({id: match[1], library: match[2], origin: match[3], media: match[4] === 'true', source: match[5]}));
const bindingRecords = [...source.matchAll(/\{component_id: '([^']+)', library: '([^']+)', origin: '([^']+)', source: '([^']+)', content_constraints: \{([^}]*)\}, requires:/g)]
  .map((match) => ({id: match[1], library: match[2], origin: match[3], source: match[4], constraints: match[5]}));
const bindingIds = bindingRecords.map((record) => record.id);

const byId = (id) => bindingRecords.find((record) => record.id === id);

test('native media scene lane exposes bounded RVE/Bits/Remocn native-source bindings with manifest fields', () => {
  assert.equal(supportIds.length, 11);
  assert.equal(bindingRecords.length, 11);
  assert.equal(new Set(supportIds.map((item) => item.id)).size, supportIds.length);
  assert.deepEqual(bindingIds, supportIds.map((item) => item.id));
  assert.ok(supportIds.every((item) => ['RVE', 'Bits', 'Remocn'].includes(item.library)));
  assert.ok(bindingRecords.every((item) => item.origin === 'native-source'));
  assert.ok(bindingRecords.every((item) => item.source.startsWith('src/components/component-horizontal/')));
  assert.equal(supportIds.filter((item) => item.media).length, 2);
  assert.deepEqual(bindingIds, [
    'Bits-CursorFlyover',
    'Bits-KenBurns',
    'Rve-QuoteCard',
    'Rve-ProgressSteps',
    'Rve-SplitScreen',
    'Bits-ChatConversation',
    'Remocn-AnimatedLineChart',
    'Rve-LineChart',
    'Rve-ChartAnimation',
    'Rve-ComparisonChart',
    'Rve-StatCounter',
  ]);
});

test('binding constraints are explicit enough for AST manifest extraction', () => {
  assert.match(byId('Bits-CursorFlyover').constraints, /media_required: true/);
  assert.match(byId('Bits-CursorFlyover').constraints, /image_only: true/);
  assert.match(byId('Bits-KenBurns').constraints, /media_required: true/);
  assert.match(byId('Bits-KenBurns').constraints, /image_only: true/);
  for (const id of ['Rve-ProgressSteps', 'Rve-SplitScreen', 'Bits-ChatConversation']) {
    assert.match(byId(id).constraints, /items_min: 2/, `${id} must declare item minimum`);
  }
  for (const id of ['Remocn-AnimatedLineChart', 'Rve-LineChart', 'Rve-ChartAnimation', 'Rve-ComparisonChart']) {
    assert.match(byId(id).constraints, /items_min: 2/, `${id} must declare item minimum`);
    assert.match(byId(id).constraints, /numeric_first_item: true/, `${id} must declare strict numeric items`);
  }
  assert.match(byId('Rve-QuoteCard').constraints, /body_required: false/);
  assert.match(byId('Rve-StatCounter').constraints, /metric_required: true/);
});

test('native media scene lane excludes forbidden developer-flow and misleading before-after components', () => {
  for (const forbidden of ['CodeMorph', 'AgentRun', 'ChatGpt', 'SearchReveal', 'Terminal', 'ClaudeCode', 'Talkcraft-', 'Snapcn-', 'ImageComparisonSlider']) {
    assert.equal(source.includes(forbidden), false, `${forbidden} must not be included`);
  }
  assert.equal(source.includes('Caption synced from material'), false);
  assert.equal(source.includes('scene {index + 1}'), false);
  assert.equal(source.includes('Monthly Performance'), false);
  assert.equal(source.includes('Total Users'), false);
});

test('native media scene lane enforces current production prop contract and numeric safety', () => {
  assert.match(source, /props\.items\[\$\{index\}\] must be a string; object items are outside the current contract/);
  assert.match(source, /rejects ratios and denominatorless percentages/);
  assert.match(source, /约\|近\|超\|超过\|高达\|至少\|最多/);
  assert.match(source, /metric\.display !== counted/);
  assert.match(source, /numeric props\.items must use one shared unit; mixed units are rejected/);
  assert.doesNotMatch(source, /Math\.min\(100/);
  assert.doesNotMatch(source, /Math\.max\(0, Math\.min/);
});

test('native media scene lane constrains original components to production safe viewport slots', () => {
  assert.match(source, /title: \{x: 70, y: 180, width: 940, height: 270\}/);
  assert.match(source, /mainDefault: \{x: 70, y: 500, width: 940, height: 840\}/);
  assert.match(source, /mainWithLayers: \{x: 70, y: 500, width: 940, height: 600\}/);
  assert.match(source, /const mainBox = textOnly \? noMaterialSetGeometry\.main : componentSample/);
  assert.match(source, /: hasEmphasisLayer \? NATIVE_MEDIA_SCENE_SAFE_BOX\.mainWithLayers : NATIVE_MEDIA_SCENE_SAFE_BOX\.mainDefault/);
  assert.match(source, /<Sequence width=\{mainBox\.width\} height=\{mainBox\.height\}/);
  assert.match(source, /showTitle && !hasTitleLayer/);
  assert.match(source, /!hasEmphasisLayer && sourceOf\(shot\)/);
  assert.doesNotMatch(source, /width=\{1080\} height=\{1920\}/);
});

test('real media bindings pass fit and crop into original library components', () => {
  assert.match(source, /<CursorFlyover src=\{requireImageMedia\(shot, 'Bits-CursorFlyover'\)\} layout=\{context\?\.componentSample \? 'portrait' : 'default'\} fit=\{assetFitOf\(shot\)\} crop=\{assetCropOf\(shot\)\}/);
  assert.match(source, /<KenBurns images=\{\[src\]\} layout=\{context\?\.componentSample \? 'portrait' : 'default'\} stepDuration=\{90\} transitionDuration=\{0\} fit=\{assetFitOf\(shot\)\} crop=\{assetCropOf\(shot\)\}/);
  assert.match(cursorFlyoverSource, /fit\?: "contain" \| "cover"/);
  assert.match(cursorFlyoverSource, /crop\?: Crop \| null/);
  assert.match(cursorFlyoverSource, /objectFit: fit/);
  assert.match(kenBurnsSource, /fit\?: "contain" \| "cover"/);
  assert.match(kenBurnsSource, /crop\?: Crop \| null/);
  assert.match(kenBurnsSource, /objectFit: fit/);
});

test('native media scene lane documents the remaining RVE/Bits/Remocn media ceiling', () => {
  const mediaIds = supportIds.filter((item) => item.media).map((item) => item.id);
  assert.deepEqual(mediaIds, ['Bits-CursorFlyover', 'Bits-KenBurns']);
  assert.ok(mediaIds.length < 13, 'RVE/Bits/Remocn alone cannot prove a 70% real-media quota across 18 bindings');
});

test('single-image KenBurns keeps one real image in continuous motion instead of re-entering duplicates', () => {
  assert.match(kenBurnsSource, /uniqueImages\.length === 1/);
  assert.match(kenBurnsSource, /src=\{singleImage\}/);
  assert.doesNotMatch(source, /\[src, src, src\]/);
  assert.doesNotMatch(source, /images=\{\[src, src, src\]\}/);
});
