import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
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

const loadTalkcraftNativeTitles = async () => {
  const cache = new Map();
  const loadSyncModule = (url) => {
    const key = url.href;
    if (cache.has(key)) return cache.get(key).exports;
    const source = readFileSync(url, 'utf8');
    const compiled = ts.transpileModule(source, {compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
    }}).outputText;
    const module = {exports: {}};
    cache.set(key, module);
    new Function('require', 'module', 'exports', compiled)(
      name => name === 'remotion' ? remotionStub : nodeRequire(name),
      module,
      module.exports,
    );
    return module.exports;
  };
  const loadModule = async (url) => {
    const key = url.href;
    if (cache.has(key)) return cache.get(key).exports;
    const source = await readFile(url, 'utf8');
    const compiled = ts.transpileModule(source, {compilerOptions: {
      module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
    }}).outputText;
    const module = {exports: {}};
    cache.set(key, module);
    new Function('require', 'module', 'exports', compiled)(
      name => {
        if (name === 'remotion') return {...remotionStub, useVideoConfig: () => ({width: 1080, height: 1920})};
        if (name === 'react' || name === 'react/jsx-runtime') return nodeRequire(name);
        if (name.includes('production-props')) return loadSyncModule(new URL('../components/component-horizontal/video-talkcraft/production-props.ts', import.meta.url));
        if (name.includes('IsolatedCard')) return {IsolatedCard: props => createElement('div', props, props.children)};
        if (name.startsWith('../components/component-horizontal/video-talkcraft/cards/')) return {default: () => null};
        return nodeRequire(name);
      },
      module,
      module.exports,
    );
    return module.exports;
  };
  return loadModule(new URL('./TalkcraftNativeTitles.tsx', import.meta.url));
};

const remotionStub = {
  AbsoluteFill: props => createElement('div', props, props.children),
  Loop: props => createElement('div', props, props.children),
  OffthreadVideo: props => createElement('video', props),
  Img: props => createElement('img', props),
  useCurrentFrame: () => 90,
  delayRender: () => 1,
  continueRender: () => undefined,
};

test('Talkcraft native title renderer exposes at least 25 real component bindings in the title safe area', async () => {
  const source = await readFile(new URL('./TalkcraftNativeTitles.tsx', import.meta.url), 'utf8');
  const ids = [...source.matchAll(/id: 'Talkcraft-[^']+'/g)].map(match => match[0].slice(5, -1));
  assert.ok(ids.length >= 25, `expected at least 25 bindings, got ${ids.length}`);
  assert.equal(new Set(ids).size, ids.length, 'bindings must be distinct component ids');
  for (const id of ['Talkcraft-highlighter-sweep', 'Talkcraft-outline-box-title', 'Talkcraft-news-card-desk',
    'Talkcraft-quote-card', 'Talkcraft-keyword-pop-highlight', 'Talkcraft-word-slot-cycle']) {
    assert.ok(ids.includes(id), `${id} should be bound`);
  }
  assert.match(source, /TALKCRAFT_TITLE_SAFE_BOX = \{x: 64, y: 180, width: 952, height: 400/);
  assert.match(source, /IsolatedCard/, 'original Talkcraft cards need ShadowRoot style isolation in production layers');
  assert.match(source, /content_constraints:/, 'binding summaries must expose validation constraints for backend quota checks');
  assert.match(source, /throw new Error\(`Talkcraft native title/, 'renderer must fail loudly when required production content is missing');
  assert.doesNotMatch(source, /component_id.*switch|CommunityNativeMaterial/, 'native title bindings must not route through generic community surfaces');
});


test('Talkcraft sample emphasis removes keyword host and stays inside the 300px safe band', async () => {
  const source = await readFile(new URL('./TalkcraftNativeTitles.tsx', import.meta.url), 'utf8');
  assert.match(source, /data-component-id=\{binding\.id\}/);
  assert.match(source, /data-component-sample=\{componentSample \? 'true' : 'false'\}/);
  assert.match(source, /data-component-id='Talkcraft-keyword-pop-highlight'\] div\[style\*='radial-gradient'\]/);
  assert.match(source, /data-component-sample='true'\]\[data-layer-role='emphasis'\]\[data-component-id='Talkcraft-keyword-pop-highlight'\] \.caption-zone/);
  assert.match(source, /componentSample && layerRole === 'emphasis'/);
  assert.match(source, /sourceHeight = sampleEmphasis \? 300 : slotHeight !== undefined/);
  assert.match(source, /shot\.component_id === 'Talkcraft-typewriter-reveal' \? 300 : 380\s*: TALKCRAFT_TITLE_SAFE_BOX\.sourceHeight/);
  assert.match(source, /slotWidth\?: number/);
  assert.match(source, /slotHeight\?: number/);
  assert.match(source, /safeHeight = slotHeight \?\? \(sampleEmphasis \? 300 : TALKCRAFT_TITLE_SAFE_BOX\.height\)/);
  const timelineSource = await readFile(new URL('./VideoFromTimeline.tsx', import.meta.url), 'utf8');
  assert.match(timelineSource, /layerRole=\{layer\.role\} componentSample=\{componentSample\}/);
  assert.match(timelineSource, /sourceHeight = box\?\.height \?\? \(componentSample && layer\.role === 'emphasis' \? 300 : 360\)/);
  assert.match(timelineSource, /const translateY = sampleEmphasis \? top : top - 180 \* unit/);
});

test('production prop helper derives supplied copy without demo fallback leakage', async () => {
  const {resolveTalkcraftTitleCopy, takeTalkcraftLines} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/production-props.ts', import.meta.url));
  const copy = resolveTalkcraftTitleCopy({title: 'AI 先聊天，真人接视频', body: '充值之前先核实身份｜别给陌生人转账', source_label: '另案示例｜thepaper.cn', accent_color: '#F43F5E', props: {items: ['AI 聊天', '真人视频', '充值诱导'], keyword: '真人视频'}});
  assert.equal(copy.title, 'AI 先聊天，真人接视频');
  assert.equal(copy.keyword, '真人视频');
  assert.deepEqual(takeTalkcraftLines(copy, 3), ['AI 先聊天，真人接视频', '充值之前先核实身份', '别给陌生人转账']);
  assert.equal(copy.source, '另案示例｜thepaper.cn');
});



test('Talkcraft native title binding summaries include backend-readable content constraints', async () => {
  const source = await readFile(new URL('./TalkcraftNativeTitles.tsx', import.meta.url), 'utf8');
  assert.match(source, /talkcraftNativeTitleBindingSummary = talkcraftNativeTitleBindings\.map\(\(\{id, source, role, motion, content_constraints\}\)/);
  assert.match(source, /numeric_first_item_or_metric_value_required/);
  assert.match(source, /from_text_or_items_0_required/);
  assert.match(source, /items_min_2/);
  assert.match(source, /body_or_items_1_required/);
  assert.match(source, /selected_option_must_match_title_or_keyword/);
  assert.match(source, /min_visible_frames_150/);
});

test('Talkcraft native title props fail closed instead of inventing numbers or before/after text', async () => {
  const source = await readFile(new URL('./TalkcraftNativeTitles.tsx', import.meta.url), 'utf8');
  const unsafeFallbacks = ["?? '3'", "?? '真人'", "?? '查看细节'", "Array(count).fill", "DEFAULT_SOURCE", 'Math.min(1, options.length - 1)', '省 6 小时'];
  for (const token of unsafeFallbacks) assert.equal(source.includes(token), false, `${token} must not appear in production mapping`);
  assert.match(source, /metricValue\(shot\)/, 'count badge must read supplied metric value when item count is absent');
  assert.match(source, /from_text/, 'replacement components must require explicit before text');
  assert.match(source, /to_text/, 'replacement components must require explicit after text');
});

test('Talkcraft chip grid selects only an explicitly matching production option and supplies a real equation', async () => {
  const {talkcraftNativeTitlePropsForShot} = await loadTalkcraftNativeTitles();
  const props = talkcraftNativeTitlePropsForShot({
    component_id: 'Talkcraft-chip-grid-single-select',
    title: '先停下来',
    body: '回到原有联系方式核实',
    source_label: '',
    accent_color: '#FFC24B',
    props: {items: ['持续充值', '送礼刷亲密度', '先停下来']},
  });
  assert.deepEqual(props.options, ['持续充值', '送礼刷亲密度', '先停下来']);
  assert.equal(props.selected, 2);
  assert.deepEqual(props.equation, [
    {text: '先停下来', accent: true},
    {text: '回到原有联系方式核实'},
  ]);

  const serialized = JSON.stringify(props);
  assert.equal(serialized.includes('先看见'), false);
  assert.equal(serialized.includes('再决定'), false);
  assert.equal(serialized.includes('省 6 小时'), false);
  assert.equal(serialized.includes('每月 72 小时'), false);

  const missing = talkcraftNativeTitlePropsForShot({
    component_id: 'Talkcraft-chip-grid-single-select',
    title: '先停下来',
    body: '',
    source_label: '',
    accent_color: '#FFC24B',
    props: {items: ['持续充值', '送礼刷亲密度']},
  });
  assert.equal(missing, null);

  const prefix = talkcraftNativeTitlePropsForShot({
    component_id: 'Talkcraft-chip-grid-single-select',
    title: '充值',
    body: '',
    source_label: '',
    accent_color: '#FFC24B',
    props: {items: ['持续充值', '充值前核实', '先停下来']},
  });
  assert.equal(prefix, null, 'prefix substrings must not guess a selected option');

  const duplicate = talkcraftNativeTitlePropsForShot({
    component_id: 'Talkcraft-chip-grid-single-select',
    title: '先停下来',
    body: '',
    source_label: '',
    accent_color: '#FFC24B',
    props: {items: ['先停下来', '送礼刷亲密度', '先停下来']},
  });
  assert.equal(duplicate, null, 'duplicate normalized matches must be rejected as ambiguous');

  const explicitHighlight = talkcraftNativeTitlePropsForShot({
    component_id: 'Talkcraft-chip-grid-single-select',
    title: '先判断动作',
    body: '',
    source_label: '',
    accent_color: '#FFC24B',
    props: {highlight: '先停下来', items: ['持续充值', '送礼刷亲密度', '先停下来']},
  });
  assert.deepEqual(explicitHighlight.equation, [{text: '先停下来', accent: true}]);
});

test('patched Talkcraft title cards render supplied production copy instead of fixed demo copy', async () => {
  const {default: HighlighterSweep} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/highlighter-sweep.tsx', import.meta.url), remotionStub);
  const highlighter = renderToStaticMarkup(createElement(HighlighterSweep, {
    title: '可能不是丈夫，而是 AI', body: '交友软件先建立信任｜再诱导充值｜最后要求视频', source: '警方通报',
  }));
  const highlighterVisible = highlighter.split('</style>').at(-1);
  assert.ok(highlighterVisible.includes('可能不是丈夫，而是 AI'));
  assert.ok(highlighterVisible.includes('警方通报'));
  assert.equal(highlighterVisible.includes('真正拖住消费'), false);

  const {default: QuoteCard} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/quote-card.tsx', import.meta.url), remotionStub);
  const quote = renderToStaticMarkup(createElement(QuoteCard, {
    lines: ['先暂停转账', '再核实身份', '最后保留证据'], source: '防骗提醒', highlight: '核实身份',
  }));
  const quoteVisible = quote.split('</style>').at(-1);
  assert.ok(quoteVisible.includes('先暂停转账'));
  assert.ok(quoteVisible.includes('核实身份'));
  assert.ok(quoteVisible.includes('防骗提醒'));
  assert.equal(quoteVisible.includes('赚钱这件事'), false);

  const {default: InkUnderline} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/ink-underline.tsx', import.meta.url), remotionStub);
  const ink = renderToStaticMarkup(createElement(InkUnderline, {title: '别只看', wrong: 'AI 陪聊', right: '真人接视频'}));
  const inkVisible = ink.split('</style>').at(-1);
  assert.ok(inkVisible.includes('AI 陪聊'));
  assert.ok(inkVisible.includes('真人接视频'));
  assert.equal(inkVisible.includes('成本上涨'), false);

  const {default: SoftBlurIn} = await loadTsx(new URL('../components/component-horizontal/video-talkcraft/cards/soft-blur-in.tsx', import.meta.url), remotionStub);
  const soft = renderToStaticMarkup(createElement(SoftBlurIn, {text: '让家里老人少被骗'}));
  const softVisible = soft.split('</style>').at(-1);
  assert.ok(softVisible.includes('让'));
  assert.equal(softVisible.includes('答案往往没那么复杂'), false);
});
