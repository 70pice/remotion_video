import type {FC, PropsWithChildren} from 'react';
import {AbsoluteFill} from 'remotion';
import {AnimatedLineChart} from './animated-line-chart';
import {CodeMorph} from './code-morph';
import {ChatGpt} from './chat-gpt';
import {AgentRun, getAgentRunDuration, type AgentRunScript} from './agent-run';
import {SearchReveal} from './search-reveal';

const Stage: FC<PropsWithChildren<{background?: string}>> = ({children, background = '#0b1020'}) => (
  <AbsoluteFill style={{background, alignItems: 'center', justifyContent: 'center', fontFamily: '"Microsoft YaHei UI", "Microsoft YaHei", Arial, sans-serif'}}>
    {children}
  </AbsoluteFill>
);

export const AnimatedLineChartDemo: FC = () => (
  <Stage>
    <div style={{position: 'absolute', top: 42, left: 72, color: '#fff', fontSize: 32}}>示例趋势 · 演示数据</div>
    <AnimatedLineChart data={[18, 24, 21, 38, 45, 42, 62, 74, 82]} strokeColor="#818cf8" />
  </Stage>
);

export const CodeMorphDemo: FC = () => (
  <Stage background="#f1eee7">
    <CodeMorph filename="prompt.ts" steps={[
      {at: 0, code: 'const prompt = "Explain AI";\nconst answer = await askModel(prompt);\nconsole.log(answer);'},
      {at: 60, code: 'const context = await retrieve(question);\nconst prompt = context + question;\nconst answer = await askModel(prompt);\nconsole.log(answer);'},
    ]} />
  </Stage>
);

export const ChatGptDemo: FC = () => (
  <Stage background="#ffffff">
    <ChatGpt greeting="你想了解什么？" placeholder="输入一个问题" prompt="用简单的例子解释什么是 RAG。" />
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

export const AgentRunDemo: FC = () => (
  <Stage background="#ececea"><AgentRun run={agentRun} {...agentOptions} speed={agentSpeed} /></Stage>
);

export const SearchRevealDemo: FC = () => <Stage background="#f3f0f5"><SearchReveal text="什么是 Agent？" /></Stage>;

type Demo = {id: string; name: string; slug: string; component: FC; width: number; height: number; durationInFrames: number; fps: 30; defaultProps?: Record<string, unknown>};
export const componentDemos: Demo[] = [
  {id: 'Remocn-AnimatedLineChart', name: 'Animated Line Chart', slug: 'remocn-animated-line-chart', component: AnimatedLineChartDemo, width: 1280, height: 720, durationInFrames: 120, fps: 30},
  {id: 'Remocn-CodeMorph', name: 'Code Morph', slug: 'remocn-code-morph', component: CodeMorphDemo, width: 1280, height: 720, durationInFrames: 180, fps: 30},
  {id: 'Remocn-ChatGpt', name: 'ChatGPT', slug: 'remocn-chat-gpt', component: ChatGptDemo, width: 1280, height: 720, durationInFrames: 150, fps: 30},
  {id: 'Remocn-AgentRun', name: 'Agent Run', slug: 'remocn-agent-run', component: AgentRunDemo, width: 1280, height: 720, durationInFrames: agentDuration, fps: 30},
  {id: 'Remocn-SearchReveal', name: 'Search Reveal', slug: 'remocn-search-reveal', component: SearchRevealDemo, width: 1280, height: 720, durationInFrames: 180, fps: 30},
];
