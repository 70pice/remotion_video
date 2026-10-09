import type {FC} from 'react';
import QuoteCard from '../../component-horizontal/rve/quote-card';
import ChartAnimation from '../../component-horizontal/rve/chart-animation';
import LineChart from '../../component-horizontal/rve/line-chart';
import PieChart from '../../component-horizontal/rve/pie-chart';
import DonutChart from '../../component-horizontal/rve/donut-chart';
import StatCounter from '../../component-horizontal/rve/stat-counter';
import ProgressBars from '../../component-horizontal/rve/progress-bars';
import ProgressSteps from '../../component-horizontal/rve/progress-steps';
import ComparisonChart from '../../component-horizontal/rve/comparison-chart';
import SplitScreen from '../../component-horizontal/rve/split-screen';
import ImageComparisonSlider from '../../component-horizontal/rve/image-comparison-slider';
import {makeCuratedDemos} from '../../component-horizontal/curated/CuratedScene';
import {rveAdditions} from '../../component-horizontal/rve/additions';

type Demo = {id: string; name: string; slug: string; component: FC; width: number; height: number; durationInFrames: number; fps: 30};

const data = [
  {x: 0, y: 54, label: '脚本'},
  {x: 1, y: 72, label: '素材'},
  {x: 2, y: 43, label: '配音'},
  {x: 3, y: 88, label: '剪辑'},
  {x: 4, y: 64, label: '发布'},
];

const segments = [
  {label: '检索资料', value: 38, color: '#60a5fa'},
  {label: '脚本整理', value: 27, color: '#a78bfa'},
  {label: '画面生成', value: 22, color: '#f472b6'},
  {label: '发布优化', value: 13, color: '#2dd4bf'},
];

const skills = [
  {label: '脚本', value: 90, color: '#4361ee'},
  {label: '素材', value: 85, color: '#7209b7'},
  {label: '配音', value: 75, color: '#f72585'},
  {label: '剪辑', value: 60, color: '#4cc9f0'},
  {label: '发布', value: 45, color: '#a855f7'},
];

export const QuoteCardPortrait: FC = () => <QuoteCard layout="portrait" quote="把一个复杂概念，拆成用户看得懂的三步。" attribution="AI 科普短视频结构" />;
export const ChartAnimationPortrait: FC = () => <ChartAnimation layout="portrait" data={data} title="制作流程占比" subtitle="AI 科普视频示例" />;
export const LineChartPortrait: FC = () => <LineChart layout="portrait" data={data} title="兴趣曲线" />;
export const PieChartPortrait: FC = () => <PieChart layout="portrait" segments={segments} title="内容结构" />;
export const DonutChartPortrait: FC = () => <DonutChart layout="portrait" segments={segments} title="完成率" centerLabel="完成度" />;
export const StatCounterPortrait: FC = () => <StatCounter layout="portrait" value={1247} label="AI 科普选题库" change="↑ 12.5%" period="本月新增" />;
export const ProgressBarsPortrait: FC = () => <ProgressBars layout="portrait" skills={skills} title="技能进度" />;
export const ProgressStepsPortrait: FC = () => <ProgressSteps layout="portrait" steps={['选题', '查证', '脚本', '生成', '发布']} title="短视频生产线" />;
export const ComparisonPortrait: FC = () => <ComparisonChart layout="portrait" title="效率对比" before={34} after={89} beforeLabel="手动剪辑" afterLabel="自动模板" />;
export const SplitScreenPortrait: FC = () => <SplitScreen layout="portrait" leftTitle="概念" leftText="先把一个词讲清楚" rightTitle="例子" rightText="再放进一个真实场景" />;
export const ImageComparePortrait: FC = () => <ImageComparisonSlider layout="portrait" beforeLabel="Before" afterLabel="After" />;

export const nativeDemos: Demo[] = [
  {id: 'Rve-QuoteCard', name: 'Quote Card', slug: 'quote-card', component: QuoteCardPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-ChartAnimation', name: 'Bar Chart', slug: 'chart-animation', component: ChartAnimationPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-LineChart', name: 'Line Chart', slug: 'line-chart', component: LineChartPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-PieChart', name: 'Pie Chart', slug: 'pie-chart', component: PieChartPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-DonutChart', name: 'Donut Chart', slug: 'donut-chart', component: DonutChartPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-StatCounter', name: 'Stat Counter', slug: 'stat-counter', component: StatCounterPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-ProgressBars', name: 'Progress Bars', slug: 'progress-bars', component: ProgressBarsPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-ProgressSteps', name: 'Progress Steps', slug: 'progress-steps', component: ProgressStepsPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-ComparisonChart', name: 'Comparison Chart', slug: 'comparison-chart', component: ComparisonPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-SplitScreen', name: 'Split Screen', slug: 'split-screen', component: SplitScreenPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Rve-ImageComparisonSlider', name: 'Image Comparison Slider', slug: 'image-comparison-slider', component: ImageComparePortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  ...makeCuratedDemos(rveAdditions, 'portrait', {width: 1080, height: 1920}),
];

export const nativeLayoutNotes: Record<string, string> = {
  'Rve-QuoteCard': 'Original QuoteCard interpolate timings with portrait typography.',
  'Rve-ChartAnimation': 'Original bar growth logic with portrait chart dimensions and label sizes.',
  'Rve-LineChart': 'Original line draw and point reveal logic with portrait chart dimensions.',
  'Rve-PieChart': 'Original segment stroke animation with portrait circle and legend dimensions.',
  'Rve-DonutChart': 'Original donut stroke and center counter animation with portrait dimensions.',
  'Rve-StatCounter': 'Original spring counter card with portrait typography.',
  'Rve-ProgressBars': 'Original progress interpolation with wider portrait bars and labels.',
  'Rve-ProgressSteps': 'Original step timing and spring pulse with portrait vertical timeline.',
  'Rve-ComparisonChart': 'Original before/after value interpolation with portrait stacked comparison.',
  'Rve-SplitScreen': 'Original panel spring entrance with portrait top-bottom split.',
  'Rve-ImageComparisonSlider': 'Original slider interpolation with taller portrait media frame.',
  ...Object.fromEntries(rveAdditions.map((item) => [item.id, 'Curated RVE portrait version with safe material-slot overlay support.'])),
};
