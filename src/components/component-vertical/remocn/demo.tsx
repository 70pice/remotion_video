import type {FC, PropsWithChildren} from 'react';
import {AbsoluteFill} from 'remotion';
import {AnimatedLineChart} from '../../component-horizontal/remocn/animated-line-chart';
import {CodeMorph} from '../../component-horizontal/remocn/code-morph';
import {ChatGpt} from '../../component-horizontal/remocn/chat-gpt';
import {AgentRun, getAgentRunDuration, type AgentRunScript} from '../../component-horizontal/remocn/agent-run';
import {SearchReveal} from '../../component-horizontal/remocn/search-reveal';

type Demo = {id: string; name: string; slug: string; component: FC; width: 1080; height: 1920; durationInFrames: number; fps: 30};

const fontFamily = '"Microsoft YaHei UI", "Microsoft YaHei", Arial, sans-serif';

const Stage: FC<PropsWithChildren<{background?: string}>> = ({children, background = '#0b1020'}) => (
  <AbsoluteFill style={{background, alignItems: 'center', justifyContent: 'center', fontFamily}}>
    {children}
  </AbsoluteFill>
);

export const AnimatedLineChartPortrait: FC = () => (
  <Stage>
    <AnimatedLineChart data={[18, 24, 21, 38, 45, 42, 62, 74, 82]} width={840} height={980} strokeColor="#818cf8" strokeWidth={9} />
  </Stage>
);

export const CodeMorphPortrait: FC = () => (
  <Stage background="#f1eee7">
    <CodeMorph layout="portrait" filename="rag.ts" fontSize={76} steps={[
      {at: 0, code: 'const q = "RAG?";\nconst answer = await ask(q);\nshow(answer);'},
      {at: 60, code: 'const q = "RAG?";\nconst docs = await search(q);\nconst answer = await explain(docs);\nshow(answer);'},
    ]} />
  </Stage>
);

export const ChatGptPortrait: FC = () => (
  <Stage background="#ffffff">
    <ChatGpt layout="portrait" greeting="你想了解什么？" placeholder="输入一个问题" prompt="用简单的例子解释什么是 RAG。" />
  </Stage>
);

const agentRun: AgentRunScript = {
  title: 'Agent 模拟执行示意',
  prompt: 'RAG 如何回答问题？',
  plan: ['检索示例资料', '结合资料解释概念'],
  steps: [
    {name: '检索资料', detail: '示例知识库', duration: 3, icon: 'search', sources: ['示例资料 [1]']},
    {name: '整理上下文', detail: '选择相关片段', duration: 2, icon: 'book'},
  ],
  answer: '## RAG 的流程\n- 先找到相关资料。\n- 再把资料交给模型组织答案。[1]\n\n这是动画示意，没有实际执行检索。',
};
const agentOptions = {compression: 4, seed: 2};
const agentSpeed = Math.max(1, getAgentRunDuration(agentRun, agentOptions) / 270);
const agentDuration = getAgentRunDuration(agentRun, {...agentOptions, speed: agentSpeed});

export const AgentRunPortrait: FC = () => (
  <Stage background="#ececea"><AgentRun run={agentRun} {...agentOptions} speed={agentSpeed} /></Stage>
);

export const SearchRevealPortrait: FC = () => (
  <Stage background="#f3f0f5">
    <SearchReveal layout="portrait" text="什么是 Agent？" fieldWidth={900} fontSize={76} />
  </Stage>
);

export const nativeDemos: Demo[] = [
  {id: 'Remocn-AnimatedLineChart', name: 'Animated Line Chart', slug: 'remocn-animated-line-chart', component: AnimatedLineChartPortrait, width: 1080, height: 1920, durationInFrames: 120, fps: 30},
  {id: 'Remocn-CodeMorph', name: 'Code Morph', slug: 'remocn-code-morph', component: CodeMorphPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Remocn-ChatGpt', name: 'ChatGPT', slug: 'remocn-chat-gpt', component: ChatGptPortrait, width: 1080, height: 1920, durationInFrames: 150, fps: 30},
  {id: 'Remocn-AgentRun', name: 'Agent Run', slug: 'remocn-agent-run', component: AgentRunPortrait, width: 1080, height: 1920, durationInFrames: agentDuration, fps: 30},
  {id: 'Remocn-SearchReveal', name: 'Search Reveal', slug: 'remocn-search-reveal', component: SearchRevealPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
];

export const nativeLayoutNotes: Record<string, string> = {
  'Remocn-AnimatedLineChart': 'Original AnimatedLineChart engine with explicit portrait width, height, and stroke.',
  'Remocn-CodeMorph': 'Original CodeMorph token diff, movement, highlight, and layout engine with larger portrait font.',
  'Remocn-ChatGpt': 'Original ChatGpt typewriter and morph engine with portrait reference geometry.',
  'Remocn-AgentRun': 'Original AgentRun rendered directly in 1080x1920 so its model reads portrait config.',
  'Remocn-SearchReveal': 'Original SearchReveal state machine and construction SVG with portrait reference geometry.',
};
