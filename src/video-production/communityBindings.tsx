import type {ComponentType, ReactNode} from 'react';
import {AbsoluteFill, Freeze, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {ChatConversation} from '../components/component-horizontal/bits/examples/ChatConversation';
import PieChart from '../components/component-horizontal/rve/pie-chart';
import SplitScreen from '../components/component-horizontal/rve/split-screen';
import StatCounter from '../components/component-horizontal/rve/stat-counter';
import UnitGridProportionHorizontal from '../components/component-horizontal/video-talkcraft/cards/unit-grid-proportion';
import SourceConvergeHorizontal from '../components/component-horizontal/video-talkcraft/cards/source-converge';
import UnitGridProportionPortrait from '../components/component-vertical/video-talkcraft/unit-grid-proportion';
import SourceConvergePortrait from '../components/component-vertical/video-talkcraft/source-converge';
import {FittedText, useLayout} from './adapters/layout';
import {createCommunityBindingSpec, hasProductionCommunityProps} from './communityBindingValidation.mjs';
import type {TimelineShot} from './types';

type BoundComponent = ComponentType<Record<string, unknown>>;

const componentMap = {
  'Rve-StatCounter': {portrait: StatCounter, landscape: StatCounter, width: 1080, height: 1920},
  'Rve-PieChart': {portrait: PieChart, landscape: PieChart, width: 1080, height: 1920},
  'Rve-SplitScreen': {portrait: SplitScreen, landscape: SplitScreen, width: 1080, height: 1920},
  'Talkcraft-unit-grid-proportion': {portrait: UnitGridProportionPortrait, landscape: UnitGridProportionHorizontal, width: 1080, height: 1920},
  'Talkcraft-source-converge': {portrait: SourceConvergePortrait, landscape: SourceConvergeHorizontal, width: 1080, height: 1920},
  'Bits-ChatConversation': {portrait: ChatConversation, landscape: ChatConversation, width: 1080, height: 1920},
} satisfies Record<string, {portrait: BoundComponent; landscape: BoundComponent; width: number; height: number}>;

export const hasProductionCommunityBinding = hasProductionCommunityProps;

const FrameMapped = ({frame, children}: {frame: number; children: ReactNode}) => (
  <Freeze frame={Math.max(0, Math.floor(frame))}>{children}</Freeze>
);

export const ProductionCommunityScene = ({shot}: {shot: TimelineShot}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const {contentWidth, margin, unit} = useLayout();
  const vertical = height >= width;
  const durationInFrames = shot.end_frame - shot.start_frame;
  const spec = createCommunityBindingSpec(shot);
  if (!spec) return null;
  const entry = componentMap[spec.component as keyof typeof componentMap];
  const Component = (vertical ? entry.portrait : entry.landscape) as BoundComponent;
  const componentProps = spec.component.startsWith('Rve-')
    ? {...spec.props, layout: vertical ? 'portrait' : 'default'}
    : (!vertical && spec.component.startsWith('Talkcraft-')
      ? Object.fromEntries(Object.entries(spec.props).filter(([key]) => key !== 'productionHold'))
      : spec.props);
  const stageWidth = vertical ? entry.width : 1280;
  const stageHeight = vertical ? entry.height : 720;
  const topClearance = vertical ? 340 : 145;
  const bottomClearance = vertical ? 420 : 210;
  const sideClearance = vertical ? 48 : 56;
  const availableWidth = width - sideClearance * 2;
  const availableHeight = height - topClearance - bottomClearance;
  const scale = Math.min(availableWidth / stageWidth, availableHeight / stageHeight);
  const stage = <Component {...componentProps} />;
  let content = stage;
  if ('holdFrame' in spec && typeof spec.holdFrame === 'number') {
    const holdFrame = vertical ? spec.holdFrame : Math.min(spec.holdFrame, 169);
    if (frame > holdFrame) content = <FrameMapped frame={holdFrame}>{stage}</FrameMapped>;
  }
  if ('revealFrame' in spec && typeof spec.revealFrame === 'number') {
    const remaining = Math.max(1, durationInFrames - spec.revealFrame - 1);
    const acceleration = Math.max(1, 75 / remaining);
    const mappedFrame = frame < spec.revealFrame ? 0 : (frame - spec.revealFrame) * acceleration;
    content = <FrameMapped frame={mappedFrame}>{stage}</FrameMapped>;
  }
  return <AbsoluteFill style={{background: `radial-gradient(circle at 50% 18%, ${shot.accent_color}24, transparent 42%), #070B12`,
    overflow: 'hidden'}}>
    <div style={{position: 'absolute', left: '50%', top: topClearance + availableHeight / 2,
      width: stageWidth, height: stageHeight, transform: `translate(-50%, -50%) scale(${scale})`,
      transformOrigin: 'center', overflow: 'hidden', borderRadius: vertical ? 28 : 18,
      boxShadow: `0 28px 90px ${shot.accent_color}22`}}>
      <Sequence width={stageWidth} height={stageHeight}>{content}</Sequence>
    </div>
    {'badge' in spec && spec.badge ? <div style={{position: 'absolute', left: sideClearance + 18, top: topClearance + 8,
      padding: '12px 18px', borderRadius: 999, background: '#F8FAFC', color: '#0F172A',
      fontSize: vertical ? 28 : 18, fontWeight: 900, letterSpacing: 0}}>
      {spec.badge}
    </div> : null}
    <div style={{position: 'absolute', left: margin, right: margin, top: vertical ? 175 * unit : 82 * unit,
      height: vertical ? 115 * unit : 58 * unit}}>
      <FittedText text={shot.title} width={contentWidth} height={vertical ? 70 * unit : 34 * unit}
        fontSize={vertical ? 48 * unit : 29 * unit} minFontSize={vertical ? 28 * unit : 18 * unit}
        style={{textAlign: 'center', fontWeight: 900}} />
      {shot.body ? <FittedText text={shot.body} width={contentWidth} height={vertical ? 34 * unit : 20 * unit}
        fontSize={vertical ? 24 * unit : 15 * unit} minFontSize={vertical ? 18 * unit : 12 * unit}
        preferSingleLine style={{textAlign: 'center', color: '#D9E4F2', fontWeight: 650, marginTop: 8 * unit}} /> : null}
    </div>
  </AbsoluteFill>;
};
