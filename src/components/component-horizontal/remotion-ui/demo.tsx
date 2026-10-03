import type {FC} from 'react';
import {DataFlowPipes} from './scenes/data-flow-pipes';
import {CodeReveal} from './scenes/code-reveal';
import {AnimatedBarChart} from './scenes/animated-bar-chart';

export const DataFlowPipesDemo: FC = () => <DataFlowPipes stages={[
  {label: '提问', detail: '输入问题'},
  {label: '检索', detail: '寻找资料'},
  {label: '上下文', detail: '组织片段'},
  {label: '生成', detail: '输出答案'},
]} packets={3} unit="示例片段" />;

export const CodeRevealDemo: FC = () => <CodeReveal title="rag.ts" language="TypeScript" code={
  'const question = "What is RAG?";\nconst context = await retrieve(question);\nconst answer = await generate({\n  question,\n  context,\n});'
} highlightedLines={[2, 4, 5]} />;

export const AnimatedBarChartDemo: FC = () => <AnimatedBarChart title="示例指标对比" subtitle="演示数据，不代表真实模型评测" data={[
  {label: '示例任务 A', value: 56},
  {label: '示例任务 B', value: 72},
  {label: '示例任务 C', value: 38},
]} maxValue={100} highlightLabel="示例任务 B" holdSeconds={4.5} />;

type Demo = {id: string; name: string; slug: string; component: FC; width: number; height: number; durationInFrames: number; fps: 30; defaultProps?: Record<string, unknown>};
export const componentDemos: Demo[] = [
  {id: 'RemotionUI-DataFlowPipes', name: 'Data Flow Pipes', slug: 'remotion-ui-data-flow-pipes', component: DataFlowPipesDemo, width: 1280, height: 720, durationInFrames: 240, fps: 30},
  {id: 'RemotionUI-CodeReveal', name: 'Code Reveal', slug: 'remotion-ui-code-reveal', component: CodeRevealDemo, width: 1280, height: 720, durationInFrames: 210, fps: 30},
  {id: 'RemotionUI-AnimatedBarChart', name: 'Animated Bar Chart', slug: 'remotion-ui-animated-bar-chart', component: AnimatedBarChartDemo, width: 1280, height: 720, durationInFrames: 210, fps: 30},
];
