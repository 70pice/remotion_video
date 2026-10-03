import React from 'react';
import {useCurrentFrame} from 'remotion';
import {IsolatedCard} from '../../community/IsolatedCard';
import {originalPreviewPropsAtFrame} from '../../component-horizontal/video-talkcraft/preview-props';
import MetricWithSparkline, {meta as MetricMeta} from './metric-with-sparkline';
import NumberCounter, {meta as CounterMeta} from './number-counter';
import NumberSlabPop, {meta as SlabMeta} from './number-slab-pop';
import UnitGridProportion, {meta as GridMeta} from './unit-grid-proportion';
import ChipGridSingleSelect, {meta as ChipMeta} from './chip-grid-single-select';
import InfoTermCard, {meta as TermMeta} from './info-term-card';
import MapRoutePin, {meta as MapMeta} from './map-route-pin';
import NumberedStepStack, {meta as StepsMeta} from './numbered-step-stack';
import StepTimelineVertical, {meta as TimelineMeta} from './step-timeline-vertical';
import UiPropTheater, {meta as PropMeta} from './ui-prop-theater';
import SourceConverge, {meta as SourceMeta} from './source-converge';
import BedEchoBlur, {meta as BedMeta} from './bed-echo-blur';
import ChatMessageFlow, {meta as ChatFlowMeta} from './chat-message-flow';
import CursorActorDemo, {meta as CursorMeta} from './cursor-actor-demo';
import EvidenceScrollTour, {meta as EvidenceMeta} from './evidence-scroll-tour';
import MediaPopIn, {meta as MediaMeta} from './media-pop-in';
import NewsCardDesk, {meta as NewsMeta} from './news-card-desk';
import SplitCompareSlider, {meta as CompareMeta} from './split-compare-slider';
import StillLayoutRelay, {meta as StillMeta} from './still-layout-relay';
import UiFlowTheater, {meta as FlowMeta} from './ui-flow-theater';
import ChatGpt, {meta as GptMeta} from './chat-gpt';
import ClaudeCode, {meta as ClaudeMeta} from './claude-code';
import DocParkLeftPillDeal, {meta as DocMeta} from './doc-park-left-pill-deal';
import FilmstripConveyor, {meta as FilmMeta} from './filmstrip-conveyor';
import GalleryWallDolly, {meta as GalleryMeta} from './gallery-wall-dolly';
import GlassCodeWalk, {meta as GlassMeta} from './glass-code-walk';
import GooeyMorph, {meta as GooeyMeta} from './gooey-morph';

type NativeProps = Record<string, unknown>;
type NativeComponent = React.ComponentType<NativeProps>;
type NativeMeta = {
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};

const withoutHost = (props: NativeProps): NativeProps => {
  const rest = {...props};
  delete rest.hostSrc;
  return rest;
};

const demos: Array<{
  slug: string;
  name: string;
  component: NativeComponent;
  meta: NativeMeta;
  note: string;
}> = [
  {slug: 'metric-with-sparkline', name: '数字带趋势', component: MetricWithSparkline, meta: MetricMeta, note: '原组件源码派生；保留计数、折线、数据点节奏，释放主持人栏位并扩为竖屏指标区'},
  {slug: 'number-counter', name: '数字滚动计数', component: NumberCounter, meta: CounterMeta, note: '原组件源码派生；保留 tween 计数和 odometer 逐位滚轮，数据面板改为竖屏主卡'},
  {slug: 'number-slab-pop', name: '数字弹出', component: NumberSlabPop, meta: SlabMeta, note: '原组件源码派生；保留色块先落、数字后弹、小数延迟的时间表'},
  {slug: 'unit-grid-proportion', name: '点阵比例图', component: UnitGridProportion, meta: GridMeta, note: '原组件源码派生；保留点阵比例动画，竖屏扩展可视区域'},
  {slug: 'chip-grid-single-select', name: '五选一反黑', component: ChipGridSingleSelect, meta: ChipMeta, note: '原组件源码派生；保留 options/selected/equation props 和单选节奏，选项纵向铺开'},
  {slug: 'info-term-card', name: '名词解释悬浮卡', component: InfoTermCard, meta: TermMeta, note: '原组件源码派生；保留名词卡入场和说明结构，取消主持人占位'},
  {slug: 'map-route-pin', name: '地图路线图钉', component: MapRoutePin, meta: MapMeta, note: '原组件源码派生；保留路径和图钉节奏，舞台改为竖屏'},
  {slug: 'numbered-step-stack', name: '编号步骤堆入', component: NumberedStepStack, meta: StepsMeta, note: '原组件源码派生；保留步骤堆入时序，竖向空间用于清单'},
  {slug: 'step-timeline-vertical', name: '竖向步骤线', component: StepTimelineVertical, meta: TimelineMeta, note: '原组件源码派生；保留竖线步骤时序，扩展为手机画布'},
  {slug: 'ui-prop-theater', name: '界面道具剧场', component: UiPropTheater, meta: PropMeta, note: '原组件源码派生；保留界面道具的进度和状态动画'},
  {slug: 'source-converge', name: '多源汇聚', component: SourceConverge, meta: SourceMeta, note: '原组件源码派生；保留贝塞尔曲线取点、packet 循环、吞并缩放、擦线和 hub 居中'},
  {slug: 'bed-echo-blur', name: '同源模糊底床', component: BedEchoBlur, meta: BedMeta, note: '原组件源码派生；保留视频 src/title/note props 和模糊底床结构'},
  {slug: 'chat-message-flow', name: '聊天记录自演', component: ChatMessageFlow, meta: ChatFlowMeta, note: '原组件源码派生；保留消息 schedule，取消主持人视频'},
  {slug: 'cursor-actor-demo', name: '光标演员演示', component: CursorActorDemo, meta: CursorMeta, note: '原组件源码派生；保留光标路径和点击节奏'},
  {slug: 'evidence-scroll-tour', name: '证据长页慢滚', component: EvidenceScrollTour, meta: EvidenceMeta, note: '原组件源码派生；保留长页滚动巡游时间轴'},
  {slug: 'media-pop-in', name: '素材弹入堆叠', component: MediaPopIn, meta: MediaMeta, note: '原组件源码派生；保留素材弹入错峰节奏'},
  {slug: 'news-card-desk', name: '新闻卡片划重点', component: NewsCardDesk, meta: NewsMeta, note: '原组件源码派生；保留新闻卡走读和高亮节奏'},
  {slug: 'split-compare-slider', name: '对比双分屏（滑动揭示）', component: SplitCompareSlider, meta: CompareMeta, note: '原组件源码派生；保留 srcBefore/srcAfter 和滑杆揭示'},
  {slug: 'still-layout-relay', name: '多图排版 + 焦点接力', component: StillLayoutRelay, meta: StillMeta, note: '原组件源码派生；保留 srcs/layout/captions props 和焦点接力时序'},
  {slug: 'ui-flow-theater', name: '界面流程剧场', component: UiFlowTheater, meta: FlowMeta, note: '原组件源码派生；保留流程舞台推进节奏'},
  {slug: 'chat-gpt', name: 'ChatGPT 对话框', component: ChatGpt, meta: GptMeta, note: '原组件源码派生；保留 ChatGPT schedule，取消主持人视频'},
  {slug: 'claude-code', name: '编码智能体终端', component: ClaudeCode, meta: ClaudeMeta, note: '原组件源码派生；保留终端 schedule，取消主持人视频'},
  {slug: 'doc-park-left-pill-deal', name: '文档驻留发牌', component: DocParkLeftPillDeal, meta: DocMeta, note: '原组件源码派生；保留文档驻留和 pill 发牌节奏'},
  {slug: 'filmstrip-conveyor', name: '传送带列举 + 减速停靠', component: FilmstripConveyor, meta: FilmMeta, note: '原组件源码派生；保留 srcs/labels/title/note props 和传送带速度曲线'},
  {slug: 'gallery-wall-dolly', name: '照片墙推轨', component: GalleryWallDolly, meta: GalleryMeta, note: '原组件源码派生；保留 srcs/labels 和 dolly 时间轴'},
  {slug: 'glass-code-walk', name: '玻璃代码走读', component: GlassCodeWalk, meta: GlassMeta, note: '原组件源码派生；保留行高亮、相机推进和回拉时间轴'},
  {slug: 'gooey-morph', name: '图块拼入', component: GooeyMorph, meta: GooeyMeta, note: '原组件源码派生；保留 L 形入场、错峰和 cubic-bezier 速度曲线'},
];

export const nativeDemos = demos.map(({slug, name, component: Component, meta, note}) => ({
  id: `Talkcraft-${slug}`,
  name: `竖屏 · ${name}`,
  slug,
  sourceId: `Talkcraft-${slug}`,
  width: meta.width,
  height: meta.height,
  fps: meta.fps,
  durationInFrames: meta.durationInFrames,
  adaptationNotes: note,
  component: function TalkcraftPortraitDemo() {
    const frame = useCurrentFrame();
    const props = withoutHost(originalPreviewPropsAtFrame(slug, frame));
    return (
      <IsolatedCard>
        <Component {...props} />
      </IsolatedCard>
    );
  },
}));
