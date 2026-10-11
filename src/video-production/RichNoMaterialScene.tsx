import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, interpolate, Sequence, useCurrentFrame, useVideoConfig} from 'remotion';
import {ChatConversation, type ChatMessage} from '../components/component-horizontal/bits/examples/ChatConversation';
import ChartAnimation, {type ChartPoint} from '../components/component-horizontal/rve/chart-animation';
import ComparisonChart from '../components/component-horizontal/rve/comparison-chart';
import ProgressSteps from '../components/component-horizontal/rve/progress-steps';
import QuoteCard from '../components/component-horizontal/rve/quote-card';
import SplitScreen from '../components/component-horizontal/rve/split-screen';
import StatCounter from '../components/component-horizontal/rve/stat-counter';
import {TextBuild, WordFlip} from '../components/component-horizontal/snapcn';
import {FittedText, muted, productionFont, white} from './adapters/layout';
import {ExpandedNoMaterialScene, isExpandedNoMaterialSet} from './ExpandedNoMaterialScene';
import {parseRichIntegerUnit, parseRichNumericItem, richNoMaterialGeometry, richStageTimings, type RichMetric, type RichNumericItem} from './RichNoMaterialGeometry';
import {SnapcnNativeTitle} from './SnapcnNativeTitles';
import type {TimelineShot} from './types';

type RichContent = {
  takeaway: string;
  items?: string[];
  metric?: RichMetric;
  numeric_items?: string[];
  supporting_items?: string[];
};

const accentFallback = '#38BDF8';
const propsOf = (shot: TimelineShot) => shot.props as Record<string, unknown>;
const textArray = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const richContentOf = (shot: TimelineShot): RichContent => {
  const raw = propsOf(shot).rich_content;
  const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {};
  const metric = value.metric && typeof value.metric === 'object' && !Array.isArray(value.metric) ? value.metric as Record<string, unknown> : null;
  return {
    takeaway: typeof value.takeaway === 'string' ? value.takeaway : '',
    items: textArray(value.items),
    numeric_items: textArray(value.numeric_items),
    supporting_items: textArray(value.supporting_items),
    ...(metric && typeof metric.label === 'string' && typeof metric.value === 'string'
      ? {metric: {label: metric.label, value: metric.value, ...(typeof metric.detail === 'string' ? {detail: metric.detail} : {})}}
      : {}),
  };
};

const metricParts = (metric?: RichMetric) => metric ? parseRichIntegerUnit(metric.value) : null;
const numericItems = (content: RichContent): RichNumericItem[] => (content.numeric_items ?? [])
  .map(parseRichNumericItem).filter((item): item is RichNumericItem => Boolean(item));
const splitItem = (item: string) => {
  const [title, ...rest] = item.split(/[：:]/);
  return {title: (title || item).trim(), body: (rest.join(':') || item).trim()};
};
const chartPoints = (items: readonly RichNumericItem[], cumulative = false): ChartPoint[] => {
  let total = 0;
  return items.map((item, index) => {
    total += item.value;
    return {x: index, y: cumulative ? total : item.value, label: item.label};
  });
};

const Shell = ({children}: {children: ReactNode}) =>
  <AbsoluteFill style={{background: 'radial-gradient(ellipse at 18% 4%, #163A54, transparent 50%), #07101F',
    color: white, overflow: 'hidden', fontFamily: productionFont}}>{children}</AbsoluteFill>;

const Box = ({box, children, style}: {box: {x: number; y: number; width: number; height: number}; children: ReactNode; style?: CSSProperties}) =>
  <div style={{position: 'absolute', left: box.x, top: box.y, width: box.width, height: box.height, ...style}}>{children}</div>;

const Panel = ({children, style}: {children: ReactNode; style?: CSSProperties}) =>
  <div style={{position: 'relative', width: '100%', height: '100%', borderRadius: 30,
    border: '1px solid #FFFFFF1F', background: '#071426D9', overflow: 'hidden',
    boxShadow: '0 28px 80px #0009', boxSizing: 'border-box', ...style}}>{children}</div>;

const StageCard = ({children, style, revealAt = 0}: {children: ReactNode; style?: CSSProperties; revealAt?: number}) => {
  const frame = useCurrentFrame();
  const opacity = revealAt ? interpolate(frame, [revealAt, revealAt + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}) : 1;
  return <div style={{borderRadius: 24, border: '1px solid #FFFFFF1A', background: '#0B1729E6',
    overflow: 'hidden', position: 'relative', boxSizing: 'border-box', opacity, ...style}}>{children}</div>;
};

const Headline = ({shot}: {shot: TimelineShot; content: RichContent}) => {
  const titleLayer = shot.layers?.find((layer) => layer.role === 'title');
  const duration = shot.end_frame - shot.start_frame;
  const opening = Math.min(90, Math.max(1, duration));
  const showBody = ['B03', 'B04', 'B05'].includes(String(propsOf(shot).component_set));
  const plainTitle = <>
    <FittedText text={shot.title} width={richNoMaterialGeometry.title.width}
      height={showBody ? 130 : richNoMaterialGeometry.title.height}
      fontSize={showBody ? 82 : 92} minFontSize={54} style={{fontWeight: 900, textAlign: 'center'}} />
    {showBody ? <div style={{position: 'absolute', top: 146}}>
      <FittedText text={shot.body} width={richNoMaterialGeometry.title.width} height={134}
        fontSize={44} minFontSize={34} style={{fontWeight: 650, color: '#D9E4F2', textAlign: 'center'}} />
    </div> : null}
  </>;
  return <Box box={richNoMaterialGeometry.title}>
    {titleLayer ? <>
      <Sequence durationInFrames={opening} width={richNoMaterialGeometry.title.width} height={richNoMaterialGeometry.title.height}>
        <SnapcnNativeTitle layer={{...titleLayer, title: titleLayer.title || shot.title}} textOnly richTitle />
      </Sequence>
      {duration > opening ? <Sequence from={opening} durationInFrames={duration - opening}>{plainTitle}</Sequence> : null}
    </> : plainTitle}
  </Box>;
};

const Emphasis = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const layer = shot.layers?.find((item) => item.role === 'emphasis');
  if (layer) {
    return <Sequence from={layer.start_frame} durationInFrames={layer.end_frame - layer.start_frame}>
      <Box box={richNoMaterialGeometry.emphasis} style={{overflow: 'hidden'}}>
        <Sequence width={richNoMaterialGeometry.emphasis.width} height={richNoMaterialGeometry.emphasis.height}>
          <SnapcnNativeTitle layer={{...layer, start_frame: 0, end_frame: layer.end_frame - layer.start_frame}} textOnly richTitle />
        </Sequence>
      </Box>
    </Sequence>;
  }
  return <Sequence from={Math.floor(duration * 0.55)} durationInFrames={Math.ceil(duration * 0.45)}>
    <Box box={richNoMaterialGeometry.emphasis}>
      <Panel style={{background: `${shot.accent_color || accentFallback}18`, borderColor: `${shot.accent_color || accentFallback}66`,
        display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 40px'}}>
        <FittedText text={content.takeaway} width={840} height={180} fontSize={72} minFontSize={46}
          style={{textAlign: 'center', fontWeight: 850}} />
      </Panel>
    </Box>
  </Sequence>;
};

const Identity = ({setId}: {setId: string}) => <Box box={richNoMaterialGeometry.identity}
  style={{color: muted, fontSize: 24, fontWeight: 650}}>
  {setId === 'B06' ? '机制示意 · 模拟聊天 · 非真实对话' : '演示数字与文案 · 非实际统计'}
</Box>;

const B01 = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const parsed = metricParts(content.metric);
  const timing = richStageTimings(duration);
  return <Box box={richNoMaterialGeometry.stage}>
    <div style={{display: 'grid', gridTemplateRows: '410px 640px', gap: 18}}>
      <StageCard><QuoteCard layout="portrait" quote={shot.body}
        attribution="" fontFamily={productionFont} transparentStage quoteFontSize={58} productionCompact /></StageCard>
      <StageCard revealAt={timing.expand} style={{padding: 18, display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16}}>
        <div style={{position: 'relative', minWidth: 0}}>{parsed ? <Sequence from={timing.expand} durationInFrames={duration - timing.expand}><StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit}
          label={content.metric?.label} change="" period={content.metric?.detail ?? ''} productionCompact compactBox fontFamily={productionFont} /></Sequence> : null}</div>
        <div style={{position: 'relative', minWidth: 0}}><Sequence from={timing.develop} durationInFrames={duration - timing.develop}><ProgressSteps layout="portrait" steps={(content.items ?? []).slice(0, 3)}
          title="" secondsPerStep={Math.max(1.2, (duration - timing.develop) / (30 * 3))} largeCopy productionCompact compactBox fontFamily={productionFont} /></Sequence></div>
      </StageCard>
    </div>
  </Box>;
};

const B02 = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const parsed = metricParts(content.metric);
  const timing = richStageTimings(duration);
  return <Box box={richNoMaterialGeometry.stage}>
    <div style={{display: 'grid', gridTemplateRows: '320px 350px 362px', gap: 18}}>
      <StageCard style={{display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', alignItems: 'center', padding: 34, gap: 18}}>
        {(content.items ?? []).map((item) => <FittedText key={item} text={item} width={286} height={240}
          fontSize={64} minFontSize={40} style={{fontWeight: 900, textAlign: 'center', textWrap: 'balance'}} />)}
      </StageCard>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
        <StageCard revealAt={timing.expand}>{parsed ? <Sequence from={timing.expand} durationInFrames={duration - timing.expand}><StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit}
          label={content.metric?.label} change="" period="" productionCompact compactBox fontFamily={productionFont} /></Sequence> : null}</StageCard>
        <StageCard revealAt={timing.expand}><Sequence from={timing.expand} durationInFrames={duration - timing.expand}><WordFlip prefix="" suffix="" words={(content.items ?? []).slice(0, 3)} fontSize={70}
          typeStart={0} cps={24} pause={8} cycle={28} loop={false}
          gradient={[shot.accent_color || accentFallback, '#F4F7FC']} fontFamily={productionFont} mode="dark" /></Sequence></StageCard>
      </div>
      <StageCard revealAt={timing.develop} style={{padding: 34}}>
        <Sequence from={timing.develop} durationInFrames={duration - timing.develop}><FittedText text={shot.body} width={860} height={190} fontSize={56} minFontSize={42}
          style={{fontWeight: 760, textAlign: 'center', textWrap: 'balance'}} /></Sequence>
      </StageCard>
    </div>
  </Box>;
};

const B03 = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const timing = richStageTimings(duration);
  const items = content.items ?? [];
  const [left, right] = items.map(splitItem);
  const nums = numericItems(content);
  return <Box box={richNoMaterialGeometry.stage}>
    <div style={{display: 'grid', gridTemplateRows: '560px 330px 142px', gap: 18}}>
      <StageCard><SplitScreen layout="portrait" leftTitle={left?.title} leftText={left?.body}
        rightTitle={right?.title} rightText={right?.body} largeCopy productionCompact /></StageCard>
      <StageCard revealAt={timing.develop}>{nums.length >= 2 ? <Sequence from={timing.develop} durationInFrames={duration - timing.develop}><ComparisonChart layout="portrait" title="演示动作数"
          before={nums[0].value} after={nums[1].value} beforeLabel={nums[0].label} afterLabel={nums[1].label}
          maxValue={Math.max(...nums.map((item) => item.value), 1)} suffix={nums[0].unit} compactBox fontFamily={productionFont} /></Sequence> : null}</StageCard>
      <StageCard style={{padding: 26, display: 'flex', alignItems: 'center'}}>
          <TextBuild text={(content.items ?? []).map((item) => splitItem(item).title).join(' ')} axis="x" fontSize={60} color={white} fontWeight={850}
            fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} />
      </StageCard>
    </div>
  </Box>;
};

const B04 = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const timing = richStageTimings(duration);
  const nums = numericItems(content);
  const parsed = metricParts(content.metric);
  const formula = nums.length >= 3 && parsed ? `${nums.map((item, index) => `${index ? '+' : ''}${item.display}`).join(' ')} =${parsed.value}${parsed.unit}` : content.metric?.detail ?? '';
  return <Box box={richNoMaterialGeometry.stage}>
    <div style={{display: 'grid', gridTemplateRows: '240px 320px 472px', gap: 18}}>
      <StageCard>{parsed ? <StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit}
        label={content.metric?.label} change="" period={content.metric?.detail ?? ''} productionCompact compactBox fontFamily={productionFont} /> : null}</StageCard>
      <StageCard style={{padding: 30, display: 'flex', alignItems: 'center'}}>
        <TextBuild text={formula} axis="y" fontSize={46} color={white} fontWeight={850}
          fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} />
      </StageCard>
      <StageCard revealAt={timing.develop}>{nums.length >= 3 ? <Sequence from={timing.develop} durationInFrames={duration - timing.develop}><ChartAnimation layout="portrait" title="逐笔累加"
        subtitle={content.metric?.detail ?? ''} data={chartPoints(nums, true)}
        maxValue={parsed?.value ?? Math.max(...nums.map((item) => item.value), 1)} compactBox fontFamily={productionFont} /></Sequence> : null}</StageCard>
    </div>
  </Box>;
};

const B05 = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const timing = richStageTimings(duration);
  const parsed = metricParts(content.metric);
  const support = content.supporting_items ?? [];
  const phase = Math.max(60, Math.floor(duration / Math.max(1, support.length)));
  return <Box box={richNoMaterialGeometry.stage}>
    <div style={{display: 'grid', gridTemplateRows: '760px 290px', gap: 18}}>
      <StageCard style={{padding: 18, display: 'grid', gridTemplateColumns: '300px 1fr', gap: 16}}>
        <div style={{position: 'relative', minWidth: 0}}>{parsed ? <Sequence from={timing.expand} durationInFrames={duration - timing.expand}><StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit}
          label={content.metric?.label} change="" period={content.metric?.detail ?? ''} productionCompact compactBox fontFamily={productionFont} /></Sequence> : null}</div>
        <div style={{position: 'relative', minWidth: 0}}><ProgressSteps layout="portrait" steps={(content.items ?? []).slice(0, 3)}
          title="" secondsPerStep={Math.max(1.2, duration / (30 * 3))} largeCopy productionCompact compactBox fontFamily={productionFont} /></div>
      </StageCard>
      <StageCard>{support.map((item, index) => {
        const from = Math.min(duration - 30, index * phase);
        const next = index === support.length - 1 ? duration : Math.min(duration, (index + 1) * phase);
        return <Sequence key={item} from={from} durationInFrames={Math.max(30, next - from)}>
          <QuoteCard layout="portrait" quote={item} attribution="" fontFamily={productionFont}
            transparentStage quoteFontSize={54} productionCompact instantReveal />
        </Sequence>;
      })}</StageCard>
    </div>
  </Box>;
};

const B06 = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const timing = richStageTimings(duration);
  const parsed = metricParts(content.metric);
  const messages: ChatMessage[] = (content.supporting_items ?? []).slice(0, 4)
    .map((item, index) => ({from: /^我[:：]/.test(item) || index % 2 === 1 ? 'me' : 'them',
      text: item.replace(/^(我|对方)[:：]\s*/, '')}));
  return <Box box={richNoMaterialGeometry.stage}>
    <div style={{display: 'grid', gridTemplateRows: '250px 470px 312px', gap: 18}}>
      <StageCard style={{padding: 34}}>
        <FittedText text={shot.body || (content.items ?? []).join(' ')} width={860} height={172} fontSize={76} minFontSize={52}
          style={{fontWeight: 900}} />
      </StageCard>
      <StageCard revealAt={timing.expand}><Sequence from={timing.expand} durationInFrames={duration - timing.expand}><ChatConversation messages={messages} variant="rise"
        showAvatars={false} stagger={16} compactBox fontSize={44} fontFamily={productionFont} /></Sequence></StageCard>
      <StageCard style={{padding: 30, display: 'grid', gridTemplateColumns: '1fr 360px', gap: 24, alignItems: 'center'}}>
        <div style={{position: 'relative', minWidth: 0, width: '100%', height: '100%'}}>
          <TextBuild text={(content.items ?? []).join(' ')} axis="y" fontSize={48} color={white}
            fontWeight={780} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} />
        </div>
        {parsed ? <div style={{position: 'relative', width: '100%', height: '100%'}}><Sequence from={timing.develop} durationInFrames={duration - timing.develop}><StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit}
          label={content.metric?.label} change="" period="" productionCompact compactBox fontFamily={productionFont} /></Sequence></div> : null}
      </StageCard>
    </div>
  </Box>;
};

const scenes: Record<string, (props: {shot: TimelineShot; content: RichContent}) => ReactNode> =
  {B01, B02, B03, B04, B05, B06};

export const RichNoMaterialScene = ({shot}: {shot: TimelineShot}) => {
  const {width, height} = useVideoConfig();
  const setId = String(propsOf(shot).component_set);
  if (isExpandedNoMaterialSet(setId)) return <ExpandedNoMaterialScene shot={shot} />;
  const content = richContentOf(shot);
  const Scene = scenes[setId] ?? B01;
  const scale = Math.min(width / 1080, height / 1920);
  return <Shell>
    <div style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${scale})`, transformOrigin: 'top left'}}>
      <Headline shot={shot} content={content} />
      <Scene shot={shot} content={content} />
      <Emphasis shot={shot} content={content} />
      <Identity setId={setId} />
    </div>
  </Shell>;
};
