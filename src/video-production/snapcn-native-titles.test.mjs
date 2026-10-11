import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {URL} from 'node:url';
import test from 'node:test';
import ts from 'typescript';

const require = createRequire(import.meta.url);
const source = await readFile(new URL('./SnapcnNativeTitles.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS,
  target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText;
const module = {exports: {}};
new Function('require', 'module', 'exports', compiled)((name) => {
  if (name === 'remotion') return {AbsoluteFill: 'div'};
  if (name.includes('/snapcn')) return new Proxy({}, {get: (_target, key) => `native-${String(key)}`});
  if (name === './adapters/layout') return {productionFont: 'Microsoft YaHei'};
  return require(name);
}, module, module.exports);
const {SnapcnNativeTitle, snapcnNativeTitleIds} = module.exports;
const layer = (component_id, values = {}) => ({component_id, role: 'title', start_frame: 15,
  end_frame: 135, title: '先核实身份', body: 'AI 聊天，真人接视频', props: {}, accent_color: '#38BDF8', ...values});
const native = (input) => SnapcnNativeTitle({layer: input}).props.children[0];

test('Snapcn production bindings call 12 actual prop-driven components, without demo entries', () => {
  assert.equal(snapcnNativeTitleIds.length, 12);
  assert.equal(new Set(snapcnNativeTitleIds).size, 12);
  assert.doesNotMatch(source, /snapcn\/entries|CommunityNativeMaterial|DEFAULT_/);
  for (const id of snapcnNativeTitleIds) assert.equal(native(layer(id)).type, `native-${id.slice(7)}`);
  assert.throws(() => native(layer('Snapcn-TerminalSimulator')), /No native/);
});

test('Snapcn replacements and word callouts preserve explicit content and local layer clock', () => {
  const rewrite = native(layer('Snapcn-TextRewrite', {props: {from_text: '真人视频就可信', to_text: '仍要核实身份'}}));
  assert.equal(rewrite.props.headline, '真人视频就可信');
  assert.equal(rewrite.props.append, '仍要核实身份');
  assert.equal(rewrite.props.keep, 0);
  const caption = native(layer('Snapcn-WordCaptions'));
  assert.deepEqual(caption.props.words, [{text: '先核实身份', startFrame: 0, endFrame: 120}]);
  const build = native(layer('Snapcn-TextBuild', {props: {items: ['先暂停转账', '再核实身份', '保留证据']}}));
  assert.equal(build.props.axis, 'y');
  assert.equal(build.props.text, '先暂停转账 再核实身份 保留证据');
});

test('Snapcn short-title fit respects long Chinese text and compact answer slots use real copy', () => {
  const title = '核'.repeat(32);
  const reveal = native(layer('Snapcn-TextReveal', {title}));
  assert.ok(reveal.props.fontSize * 32 <= 850);
  const stream = native(layer('Snapcn-AnswerStream'));
  assert.equal(stream.props.productionCompact, true);
  assert.deepEqual(stream.props.cards, []);
  assert.equal(stream.props.headline, '');
  assert.equal(stream.props.model, '机制示意');
  const highlight = native(layer('Snapcn-AnswerHighlight'));
  assert.equal(highlight.props.statement, 'AI 聊天，真人接视频');
  assert.equal(highlight.props.productionCompact, true);
});

test('guided instructions use compact white native text without a title plate', () => {
  const input = layer('Snapcn-TextReveal', {title: '点保存', accent_color: '#FB923C'});
  const result = SnapcnNativeTitle({layer: input, tutorial: true});
  const reveal = result.props.children[0];
  assert.equal(result.props.style.background, 'transparent');
  assert.equal(reveal.type, 'native-TextReveal');
  assert.equal(reveal.props.text, '点保存');
  assert.equal(reveal.props.color, '#F4F7FC');
  assert.equal(reveal.props.fontSize, 72);
  assert.equal(reveal.props.initialScale, 1);
  assert.equal(reveal.props.wordDelay, 0);
  assert.equal(reveal.props.wordStagger, 0);
  const long = SnapcnNativeTitle({layer: {...input, title: '核'.repeat(24)}, tutorial: true}).props.children[0];
  assert.ok(long.props.fontSize * 24 <= 860);
  assert.equal(native(input).props.color, '#F4F7FC');
});

test('text-only sets retain white ink and underline emphasis instead of a solid text plate', () => {
  const input = layer('Snapcn-TextHighlight', {props: {highlight: '先核实身份'}});
  const element = SnapcnNativeTitle({layer: input, textOnly: true});
  const result = element.props.children[0];
  assert.equal(result.props.preset, 'underline');
  assert.equal(result.props.baseColor, '#F4F7FC');
  assert.equal(result.props.fontSize, 76);
  assert.equal(element.props.style.background, 'transparent');
  assert.equal(result.props.theme.background, 'transparent');
});

test('rich answer emphasis presents the supplied takeaway without a second question or clipped paragraph', () => {
  const input = layer('Snapcn-AnswerHighlight', {role: 'emphasis', title: '聊天能力≠身份凭证', body: '把能接话、能视频、身份可信分开看。'});
  const element = SnapcnNativeTitle({layer: input, textOnly: true, richTitle: true});
  const result = element.props.children[0];
  assert.equal(result.props.answer, input.title);
  assert.equal(result.props.statement, input.title);
  assert.equal(result.props.question, '');
  assert.equal(result.props.word, '');
  assert.equal(result.props.compactCallout, true);
  assert.equal(element.props.children[1], null);
  assert.equal(native(input).props.answer, input.body);
});

test('rich underlined takeaway fits the native component eighty-percent text measure', () => {
  const title = '核对清楚，再做决定';
  const input = layer('Snapcn-TextHighlight', {role: 'emphasis', props: {highlight: title}});
  const result = SnapcnNativeTitle({layer: input, textOnly: true, richTitle: true}).props.children[0];
  assert.ok(result.props.fontSize * [...title].length <= 952 * 0.8);
});
