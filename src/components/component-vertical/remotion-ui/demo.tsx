import type {FC} from 'react';
import {DataFlowPipes} from '../../component-horizontal/remotion-ui/scenes/data-flow-pipes';
import {CodeReveal} from '../../component-horizontal/remotion-ui/scenes/code-reveal';
import {AnimatedBarChart} from '../../component-horizontal/remotion-ui/scenes/animated-bar-chart';

type Demo = {id: string; name: string; slug: string; component: FC; width: 1080; height: 1920; durationInFrames: number; fps: 30};

export const DataFlowPipesPortrait: FC = () => <DataFlowPipes stages={[
  {label: '提问', detail: '输入问题'},
  {label: '检索', detail: '寻找资料'},
  {label: '上下文', detail: '组织片段'},
  {label: '生成', detail: '输出答案'},
]} packets={3} unit="示例片段" />;

export const CodeRevealPortrait: FC = () => <CodeReveal layout="portrait" title="rag.ts" language="TypeScript" code={
  'const question = "What is RAG?";\nconst context = await retrieve(question);\nconst answer = await generate({\n  question,\n  context,\n});'
} highlightedLines={[2, 4, 5]} />;

export const AnimatedBarChartPortrait: FC = () => <AnimatedBarChart title="示例指标对比" subtitle="演示数据，不代表真实模型评测" data={[
  {label: '任务 A', value: 56},
  {label: '任务 B', value: 72},
  {label: '任务 C', value: 38},
]} maxValue={100} highlightLabel="任务 B" holdSeconds={4.5} />;

export const nativeDemos: Demo[] = [
  {id: 'RemotionUI-DataFlowPipes', name: 'Data Flow Pipes', slug: 'remotion-ui-data-flow-pipes', component: DataFlowPipesPortrait, width: 1080, height: 1920, durationInFrames: 240, fps: 30},
  {id: 'RemotionUI-CodeReveal', name: 'Code Reveal', slug: 'remotion-ui-code-reveal', component: CodeRevealPortrait, width: 1080, height: 1920, durationInFrames: 210, fps: 30},
  {id: 'RemotionUI-AnimatedBarChart', name: 'Animated Bar Chart', slug: 'remotion-ui-animated-bar-chart', component: AnimatedBarChartPortrait, width: 1080, height: 1920, durationInFrames: 210, fps: 30},
];

export const nativeLayoutNotes: Record<string, string> = {
  'RemotionUI-DataFlowPipes': 'Original DataFlowPipes portrait branch from video config.',
  'RemotionUI-CodeReveal': 'Original CodeReveal write plan, tokenizer, caret, scroll, and highlight engine with portrait scale basis.',
  'RemotionUI-AnimatedBarChart': 'Original AnimatedBarChart portrait branch from video config.',
};
