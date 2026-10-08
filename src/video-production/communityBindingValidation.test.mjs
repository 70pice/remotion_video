import assert from 'node:assert/strict';
import test from 'node:test';
import {createCommunityBindingSpec, validateCommunityBindingProps} from './communityBindingValidation.mjs';
import {validateTimeline} from './validation.mjs';

const {structuredClone} = globalThis;

const fixture = (componentId, props = {}) => ({
  schema_version: '1',
  job_id: 'test-job',
  revision: 1,
  width: 1080,
  height: 1920,
  fps: 30,
  duration_in_frames: 120,
  audio_src: null,
  shots: [{
    shot_id: 'a',
    start_frame: 0,
    end_frame: 120,
    component_id: componentId,
    title: '生产绑定测试',
    body: '',
    asset_src: null,
    source_label: '来源：测试报告',
    accent_color: '#E85332',
    props,
  }],
  captions: [],
});

const validCases = [
  ['Rve-StatCounter', {
    value: 4700,
    label: 'AI身份',
    change: '',
    period: '2026年4月两周',
    suffix: '+',
    source_ref: 'https://example.com/report',
    reveal_frame: 24,
  }],
  ['Rve-PieChart', {
    title: '聊天分工',
    source_ref: 'https://example.com/report',
    segments: [
      {label: 'AI聊天', value: 75, color: '#E85332'},
      {label: '真人节点', value: 25, color: '#111111'},
    ],
  }],
  ['Rve-SplitScreen', {
    leftTitle: 'AI',
    leftText: '负责大规模文字聊天和人设维持',
    rightTitle: '真人',
    rightText: '负责视频聊天等机器不擅长的节点',
  }],
  ['Talkcraft-unit-grid-proportion', {
    target: 75,
    unit: '%',
    label: ['由AI完成', '不是全真人'],
    legend: ['AI文字聊天', '真人接管节点', '每格=1%'],
    source_ref: 'https://example.com/report',
  }],
  ['Talkcraft-source-converge', {
    title: '系统把信任感拼起来',
    sources: ['文字', '头像', '视频', '付费'],
    hub: '交友局',
    caption: 'AI和真人分段协作',
  }],
  ['Bits-ChatConversation', {
    messages: [
      {from: 'them', text: '先用AI连续聊天'},
      {from: 'me', text: '关键时刻真人接视频'},
    ],
    variant: 'pop',
    showAvatars: true,
    stagger: 12,
    semantics: 'illustration',
  }],
];

test('bound community components accept real production values and keep them in the render spec', () => {
  for (const [componentId, props] of validCases) {
    const timeline = fixture(componentId, props);
    const before = structuredClone(timeline);
    assert.equal(validateTimeline(timeline), timeline);
    assert.deepEqual(timeline, before);
    const spec = createCommunityBindingSpec(timeline.shots[0]);
    assert.equal(spec.component, componentId);
    if (componentId === 'Rve-StatCounter') {
      assert.equal(spec.props.value, 4700);
      assert.equal(spec.props.label, 'AI身份');
      assert.equal(spec.props.period, '2026年4月两周');
      assert.equal(spec.revealFrame, 24);
    }
    if (componentId === 'Rve-PieChart') {
      assert.deepEqual(spec.props.segments.map((segment) => segment.label), ['AI聊天', '真人节点']);
      assert.equal(spec.props.title, '聊天分工');
    }
    if (componentId === 'Talkcraft-unit-grid-proportion') {
      assert.equal(spec.props.target, 75);
      assert.deepEqual(spec.props.legend, ['AI文字聊天', '真人接管节点', '每格=1%']);
      assert.equal(spec.props.productionHold, true);
      assert.equal(spec.holdFrame, 200);
    }
    if (componentId === 'Talkcraft-source-converge') {
      assert.deepEqual(spec.props.sources, ['文字', '头像', '视频', '付费']);
      assert.equal(spec.props.productionHold, true);
      assert.equal(spec.holdFrame, 200);
    }
    if (componentId === 'Bits-ChatConversation') {
      assert.equal(spec.badge, '机制示意｜非真实对话');
      assert.equal(spec.props.messages[0].text, '先用AI连续聊天');
    }
  }
});

test('empty props preserve the existing fixed-demo preset behavior', () => {
  for (const componentId of validCases.map(([id]) => id)) {
    const timeline = fixture(componentId, {});
    timeline.shots[0].source_label = '';
    assert.equal(validateTimeline(timeline), timeline);
    assert.equal(createCommunityBindingSpec(timeline.shots[0]), null);
  }
});

test('bound community validation rejects unsafe sources, mixed media and fabricated chart semantics', () => {
  const invalid = [
    ['Rve-StatCounter', {...validCases[0][1], source_ref: 'ftp://example.com/report'}, /HTTP\/HTTPS/],
    ['Rve-StatCounter', {...validCases[0][1], asset_src: 'videoagents/test-job/a.png'}, /unsupported/],
    ['Rve-PieChart', {...validCases[1][1], segments: [
      {label: 'AI聊天', value: 74, color: '#E85332'},
      {label: '真人节点', value: 25, color: '#111111'},
    ]}, /sum to 100/],
    ['Rve-PieChart', {...validCases[1][1], segments: [
      {label: 'AI聊天', value: 75, color: 'red'},
      {label: '真人节点', value: 25, color: '#111111'},
    ]}, /pattern/],
    ['Bits-ChatConversation', {...validCases[5][1], semantics: 'quotation'}, /source_ref/],
    ['Bits-ChatConversation', {...validCases[5][1], source_ref: 'file:///tmp/source'}, /HTTP\/HTTPS/],
    ['Talkcraft-unit-grid-proportion', {...validCases[3][1], target: 101}, /at most 100/],
  ];
  for (const [componentId, props, message] of invalid) {
    const timeline = fixture(componentId, props);
    assert.throws(() => validateTimeline(timeline), message);
  }
  const asset = fixture('Talkcraft-unit-grid-proportion', validCases[3][1]);
  asset.shots[0].asset_src = 'videoagents/test-job/a.png';
  assert.throws(() => validateTimeline(asset), /do not accept asset_src/);
  const missingLabel = fixture('Rve-StatCounter', validCases[0][1]);
  missingLabel.shots[0].source_label = '';
  assert.throws(() => validateTimeline(missingLabel), /source label/);
  const lateReveal = fixture('Rve-StatCounter', {...validCases[0][1], reveal_frame: 106});
  assert.throws(() => validateTimeline(lateReveal), /reveal_frame/);
});

test('quotation chats require a real source while illustration chats get a mechanism badge', () => {
  const quotation = fixture('Bits-ChatConversation', {
    ...validCases[5][1],
    semantics: 'quotation',
    source_ref: 'https://example.com/transcript',
  });
  assert.equal(validateTimeline(quotation), quotation);
  const spec = createCommunityBindingSpec(quotation.shots[0]);
  assert.equal(spec.badge, '来源摘录');
  validateCommunityBindingProps(quotation.shots[0], 'shots[0]');
});
