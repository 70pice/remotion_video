import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import {ChatConversation, type ChatMessage} from '../components/component-horizontal/bits/examples/ChatConversation';
import ChartAnimation, {type ChartPoint} from '../components/component-horizontal/rve/chart-animation';
import ComparisonChart from '../components/component-horizontal/rve/comparison-chart';
import ProgressSteps from '../components/component-horizontal/rve/progress-steps';
import QuoteCard from '../components/component-horizontal/rve/quote-card';
import SplitScreen from '../components/component-horizontal/rve/split-screen';
import StatCounter from '../components/component-horizontal/rve/stat-counter';
import {AnswerStream, TextBuild, TextHighlight, TextSwap, WordFlip} from '../components/component-horizontal/snapcn';
import {FittedText, muted, productionFont, white} from './adapters/layout';
import {expandedNoMaterialGeometry, expandedNoMaterialSetIds, expandedStageTimings, parseExpandedIntegerUnit, parseExpandedNumericItem, type ExpandedMetric, type ExpandedNumericItem} from './ExpandedNoMaterialGeometry';
import {LineChartPanel, TalkcraftPanel, type ExpandedTalkcraftComponentId} from './ExpandedSemanticPanels';
import {SnapcnNativeTitle} from './SnapcnNativeTitles';
import {isTalkcraftNativeTitleId, TalkcraftNativeTitle} from './TalkcraftNativeTitles';
import type {TimelineShot} from './types';
type TimelineLayer = NonNullable<TimelineShot['layers']>[number];

export const isExpandedNoMaterialSet = (value: unknown): value is typeof expandedNoMaterialSetIds[number] =>
  typeof value === 'string' && (expandedNoMaterialSetIds as readonly string[]).includes(value);

type ExpandedContent = {takeaway: string; items?: string[]; supporting_items?: string[]; metric?: ExpandedMetric; numeric_items?: string[]};
const accentFallback = '#38BDF8';
const propsOf = (shot: TimelineShot) => shot.props as Record<string, unknown>;
const arrayOfText = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const contentOf = (shot: TimelineShot): ExpandedContent => {
  const raw = propsOf(shot).rich_content;
  const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {};
  const metric = value.metric && typeof value.metric === 'object' && !Array.isArray(value.metric) ? value.metric as Record<string, unknown> : null;
  return {takeaway: typeof value.takeaway === 'string' ? value.takeaway : '', items: arrayOfText(value.items),
    supporting_items: arrayOfText(value.supporting_items), numeric_items: arrayOfText(value.numeric_items),
    ...(metric && typeof metric.label === 'string' && typeof metric.value === 'string' ? {metric: {label: metric.label, value: metric.value,
      ...(typeof metric.detail === 'string' ? {detail: metric.detail} : {})}} : {})};
};
const metricParts = (metric?: ExpandedMetric) => metric ? parseExpandedIntegerUnit(metric.value) : null;
const numericItems = (content: ExpandedContent): ExpandedNumericItem[] => (content.numeric_items ?? []).map(parseExpandedNumericItem).filter((item): item is ExpandedNumericItem => Boolean(item));
const splitItem = (item: string) => { const [title, ...rest] = item.split(/[：:]/); return {title: (title || item).trim(), body: (rest.join(':') || item).trim()}; };
const chartPoints = (items: readonly ExpandedNumericItem[], cumulative = false): ChartPoint[] => { let total = 0; return items.map((item, index) => { total += item.value; return {x: index, y: cumulative ? total : item.value, label: item.label}; }); };
const messagesOf = (content: ExpandedContent): ChatMessage[] => (content.supporting_items ?? []).slice(0, 4).map((item, index) => ({from: /^我[:：]/.test(item) || index % 2 === 1 ? 'me' : 'them', text: item.replace(/^(我|对方)[:：]\s*/, '')}));
const sequenceDuration = (duration: number, from: number) => Math.max(1, duration - Math.max(0, from));
const shortList = (items: string[] | undefined, fallback: string, count = 3) => (items?.length ? items : [fallback]).slice(0, count);

const Shell = ({children}: {children: ReactNode}) => <AbsoluteFill style={{background: 'radial-gradient(ellipse at 20% 5%, #173A55, transparent 52%), #07101F', color: white, overflow: 'hidden', fontFamily: productionFont}}>{children}</AbsoluteFill>;
const Box = ({box, children, style}: {box: {x: number; y: number; width: number; height: number}; children: ReactNode; style?: CSSProperties}) =>
  <div style={{position: 'absolute', left: box.x, top: box.y, width: box.width, height: box.height, ...style}}>{children}</div>;
const Card = ({children, style}: {children: ReactNode; style?: CSSProperties}) => <div style={{position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: 26, border: '1px solid #FFFFFF1A', background: '#0B1729E8', boxSizing: 'border-box', ...style}}>{children}</div>;
const Slot = ({from = 0, duration, children}: {from?: number; duration: number; children: ReactNode}) =>
  <div style={{position: 'relative', width: '100%', height: '100%'}}><Sequence from={from} durationInFrames={sequenceDuration(duration, from)}>{children}</Sequence></div>;
const Grid = ({rows, columns, children}: {rows?: string; columns?: string; children: ReactNode}) =>
  <Box box={expandedNoMaterialGeometry.stage}><div style={{display: 'grid', gridTemplateRows: rows, gridTemplateColumns: columns, gap: 18, width: '100%', height: '100%'}}>{children}</div></Box>;
const InlineNative = ({layer, role, slotWidth, slotHeight}: {layer: TimelineLayer; role: 'title' | 'emphasis'; slotWidth: number; slotHeight: number}) => {
  const layerShot = {shot_id: `expanded-${role}-${layer.component_id}`, start_frame: 0, end_frame: Math.max(1, layer.end_frame - layer.start_frame), component_id: layer.component_id,
    title: layer.title, body: layer.body, source_label: '', asset_src: null, accent_color: layer.accent_color, props: layer.props ?? {}, layers: []} as TimelineShot;
  return isTalkcraftNativeTitleId(layer.component_id)
    ? <TalkcraftNativeTitle shot={layerShot} layerRole={role} componentSample slotWidth={slotWidth} slotHeight={slotHeight} />
    : <SnapcnNativeTitle layer={{...layer, start_frame: 0, end_frame: layerShot.end_frame}} textOnly richTitle />;
};

const Headline = ({shot}: {shot: TimelineShot}) => {
  const layer = shot.layers?.find((item) => item.role === 'title');
  const duration = shot.end_frame - shot.start_frame;
  const opening = layer?.component_id === 'Talkcraft-typewriter-reveal' ? Math.min(150, duration) : Math.min(120, duration);
  const title = <><FittedText text={shot.title} width={expandedNoMaterialGeometry.title.width} height={132} fontSize={84} minFontSize={56} style={{fontWeight: 900, textAlign: 'center'}} />
    <div style={{position: 'absolute', top: 142}}><FittedText text={shot.body} width={expandedNoMaterialGeometry.title.width} height={112} fontSize={42} minFontSize={32} style={{fontWeight: 650, color: '#D9E4F2', textAlign: 'center'}} /></div></>;
  return <Box box={expandedNoMaterialGeometry.title}>{layer ? <><Sequence durationInFrames={opening} width={expandedNoMaterialGeometry.title.width} height={expandedNoMaterialGeometry.title.height}><InlineNative layer={{...layer, title: layer.title || shot.title, body: layer.body || shot.body}} role="title" slotWidth={expandedNoMaterialGeometry.title.width} slotHeight={expandedNoMaterialGeometry.title.height} /></Sequence>{duration > opening ? <Sequence from={opening} durationInFrames={duration - opening}>{title}</Sequence> : null}</> : title}</Box>;
};
const Emphasis = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const layer = shot.layers?.find((item) => item.role === 'emphasis');
  if (layer) return <Sequence from={layer.start_frame} durationInFrames={Math.max(1, layer.end_frame - layer.start_frame)}><Box box={expandedNoMaterialGeometry.emphasis} style={{overflow: 'hidden'}}><InlineNative layer={{...layer, title: layer.title || content.takeaway, body: layer.body || shot.body}} role="emphasis" slotWidth={expandedNoMaterialGeometry.emphasis.width} slotHeight={expandedNoMaterialGeometry.emphasis.height} /></Box></Sequence>;
  return <Sequence from={Math.floor(duration * 0.70)} durationInFrames={Math.max(1, Math.ceil(duration * 0.30))}><Box box={expandedNoMaterialGeometry.emphasis}><Card style={{display: 'grid', placeItems: 'center', background: `${shot.accent_color || accentFallback}1F`}}><FittedText text={content.takeaway} width={840} height={190} fontSize={76} minFontSize={48} style={{fontWeight: 900, textAlign: 'center'}} /></Card></Box></Sequence>;
};
const Identity = () => <Box box={expandedNoMaterialGeometry.identity} style={{color: muted, fontSize: 24, fontWeight: 650}}>演示数字与文案 · 非实际统计 · 无外部素材</Box>;

const Count = ({content, accent, compact = false}: {content: ExpandedContent; accent: string; compact?: boolean}) => { const parsed = metricParts(content.metric); return parsed ? <StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit} label={content.metric?.label} change="" period={compact ? '' : content.metric?.detail ?? ''} productionCompact compactBox fontFamily={productionFont} accentColor={accent} /> : null; };
const Steps = ({content, duration, useItems = false}: {content: ExpandedContent; duration: number; useItems?: boolean}) => <ProgressSteps compactSpacing layout="portrait" steps={shortList(useItems ? content.items : content.supporting_items?.length ? content.supporting_items : content.items, '先分清楚', 4)} title="" secondsPerStep={Math.max(1.1, duration / (30 * 6))} largeCopy productionCompact compactBox fontFamily={productionFont} />;
const Quote = ({text}: {text: string}) => <QuoteCard layout="portrait" quote={text} attribution="" transparentStage quoteFontSize={44} productionCompact instantReveal fontFamily={productionFont} />;
const Formula = ({content, size = 52}: {content: ExpandedContent; size?: number}) => <TextBuild text={`${numericItems(content).map((item) => item.value).join('+')}=${content.metric?.value ?? ''}`} axis="x" fontSize={size} color={white} fontWeight={820} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} />;
const ItemCards = ({items, accent}: {items: string[]; accent: string}) => <div style={{display: 'grid', gap: 10, padding: 18, height: '100%', boxSizing: 'border-box'}}>{items.slice(0, 4).map((item, index) => <div key={item} style={{display: 'flex', alignItems: 'center', gap: 18, padding: '10px 14px', borderRadius: 18, background: '#FFFFFF10', fontSize: 38, fontWeight: 820, lineHeight: 1.14}}><span style={{display: 'grid', placeItems: 'center', width: 44, height: 44, borderRadius: 14, background: index === 0 ? accent : '#FFFFFF18'}}>{index + 1}</span><span>{item}</span></div>)}</div>;
const LineChartMini = ({items, title, maxValue, unit}: {items: readonly ExpandedNumericItem[]; title: string; maxValue: number; unit?: string}) =>
  <LineChartPanel title={title} subtitle="演示走势" data={chartPoints(items, true)} maxValue={maxValue} unit={unit} slotWidth={452} slotHeight={470} />;
const TalkStage = ({componentId, content, title, body, keyword, fromText, toText, items, width = 452, height = 340}: {
  componentId: ExpandedTalkcraftComponentId;
  content: ExpandedContent;
  title: string;
  body?: string;
  keyword?: string;
  fromText?: string;
  toText?: string;
  items?: string[];
  width?: number;
  height?: number;
}) => <TalkcraftPanel componentId={componentId} title={title} body={body || content.takeaway}
  items={shortList(items ?? content.items, content.takeaway, 4)} keyword={keyword ?? content.takeaway}
  fromText={fromText ?? content.items?.[0]} toText={toText ?? content.items?.[1] ?? content.takeaway}
  accentColor={accentFallback} slotWidth={width} slotHeight={height} style={{width: '100%', height: '100%'}} />;

const LayoutDashboard = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const nums = numericItems(content); const accent = shot.accent_color || accentFallback; return <Grid rows="330px 342px 342px"><Card><Quote text={(content.items ?? []).join(' → ')} /></Card><div style={{display: 'grid', gridTemplateColumns: '310px 1fr', gap: 18}}><Card><Slot from={t.expand} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card><Card><Slot from={t.expand} duration={duration}><ChartAnimation unit={nums[0]?.unit} layout="portrait" title="演示拆分" subtitle={content.metric?.detail ?? ''} data={chartPoints(nums)} maxValue={Math.max(...nums.map((i) => i.value), metricParts(content.metric)?.value ?? 1)} compactBox fontFamily={productionFont} /></Slot></Card></div><div style={{display: 'grid', gridTemplateColumns: '1fr 300px', gap: 18}}><Card><Slot from={t.develop} duration={duration}><Steps content={content} duration={duration} /></Slot></Card><Card><Slot from={t.resolve} duration={duration}><WordFlip words={shortList(content.items, content.takeaway, 4)} prefix="" suffix="" fontSize={62} typeStart={0} cps={24} pause={8} cycle={30} loop={false} gradient={[accent, '#F4F7FC']} fontFamily={productionFont} mode="dark" /></Slot></Card></div></Grid>; };
const LayoutCompare = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const items = shortList(content.items, shot.body, 2); const [a, b] = items.map(splitItem); const nums = numericItems(content); const accent = shot.accent_color || accentFallback; return <Grid rows="430px 300px 302px"><Card><SplitScreen layout="portrait" leftTitle={a?.title} leftText={a?.body} rightTitle={b?.title} rightText={b?.body} largeCopy productionCompact compactBox /></Card><div style={{display: 'grid', gridTemplateColumns: '1fr 320px', gap: 18}}><Card><Slot from={t.expand} duration={duration}>{nums.length >= 2 ? <ComparisonChart layout="portrait" title="演示动作数" before={nums[0].value} after={nums[1].value} beforeLabel={nums[0].label} afterLabel={nums[1].label} maxValue={Math.max(...nums.map((i) => i.value), 1)} suffix={nums[0].unit} compactBox fontFamily={productionFont} /> : null}</Slot></Card><Card><Slot from={t.expand} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card></div><div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}><Card style={{display: 'grid', placeItems: 'center'}}><Slot from={t.develop} duration={duration}><TextSwap fromText={a?.title ?? shot.title} toText={b?.title ?? content.takeaway} fontSize={58} color={white} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card><Card><Slot from={t.resolve} duration={duration}><TalkStage componentId="Talkcraft-strike-and-replace" content={content} title="改掉旧判断" body={content.takeaway} width={470} height={302} /></Slot></Card></div></Grid>; };
const LayoutAnswer = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const accent = shot.accent_color || accentFallback; return <Grid rows="300px 430px 302px"><Card><ChatConversation messages={messagesOf(content)} variant="rise" showAvatars={false} stagger={14} compactBox fontSize={42} fontFamily={productionFont} /></Card><Card><Slot from={t.expand} duration={duration}><AnswerStream question={shot.title} answer={shot.body || content.takeaway} headline="" cards={shortList(content.items, content.takeaway, 3).map((item) => ({title: item, body: ""}))} model="机制示意" productionCompact slotWidth={968} slotHeight={430} accentColor={accent} fontFamily={productionFont} mode="dark" /></Slot></Card><div style={{display: 'grid', gridTemplateColumns: '1fr 310px', gap: 18}}><Card><Slot from={t.develop} duration={duration}><TextBuild text={shortList(content.items, content.takeaway, 3).map((item) => splitItem(item).title).join(' ')} axis="y" fontSize={50} color={white} fontWeight={800} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card><Card><Slot from={t.resolve} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card></div></Grid>; };
const LayoutChat = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const accent = shot.accent_color || accentFallback; return <Grid rows="510px 270px 286px"><Card><ChatConversation messages={messagesOf(content)} variant="rise" showAvatars={false} stagger={16} compactBox fontSize={44} fontFamily={productionFont} /></Card><div style={{display: 'grid', gridTemplateColumns: '1fr 320px', gap: 18}}><Card><Slot from={t.expand} duration={duration}><Steps content={content} duration={duration} useItems /></Slot></Card><Card><Slot from={t.expand} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card></div><Card style={{padding: 26}}><Slot from={t.resolve} duration={duration}><TextBuild text={shortList(content.items, content.takeaway, 3).map((item) => splitItem(item).title).join(' ')} axis="y" fontSize={52} color={white} fontWeight={840} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card></Grid>; };
const LayoutLedger = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const nums = numericItems(content); const accent = shot.accent_color || accentFallback; return <Grid rows="250px 420px 362px"><div style={{display: 'grid', gridTemplateColumns: '310px 1fr', gap: 18}}><Card><Count content={content} accent={accent} compact /></Card><Card style={{padding: 26, display: 'grid', placeItems: 'center'}}><Formula content={content} size={44} /></Card></div><Card><Slot from={t.expand} duration={duration}><ChartAnimation unit={nums[0]?.unit} layout="portrait" title="逐项演示" subtitle={content.metric?.detail ?? ''} data={chartPoints(nums)} maxValue={metricParts(content.metric)?.value ?? Math.max(...nums.map((i) => i.value), 1)} compactBox fontFamily={productionFont} /></Slot></Card><div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}><Card><Slot from={t.develop} duration={duration}><WordFlip words={shortList(content.items, content.takeaway, 4)} prefix="" suffix="" fontSize={58} typeStart={0} cps={22} pause={8} cycle={28} loop={false} gradient={[accent, '#F4F7FC']} fontFamily={productionFont} mode="dark" /></Slot></Card><Card><Slot from={t.resolve} duration={duration}><TalkStage componentId="Talkcraft-ink-underline" content={content} title="先看" body="再决定是否付款" keyword="预算去向" toText="再决定是否付款" width={470} height={362} /></Slot></Card></div></Grid>; };
const LayoutSource = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const accent = shot.accent_color || accentFallback; return <Grid rows="330px 360px 340px"><div style={{display: 'grid', gridTemplateColumns: '1fr 310px', gap: 18}}><Card><TalkStage componentId="Talkcraft-source-converge" content={content} title="线索汇总" body={content.takeaway} keyword="链路" width={640} height={330} /></Card><Card><Count content={content} accent={accent} compact /></Card></div><Card><Slot from={t.expand} duration={duration}><Steps content={content} duration={duration} useItems /></Slot></Card><div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}><Card><Slot from={t.develop} duration={duration}><WordFlip words={shortList(content.supporting_items, content.takeaway, 4)} prefix="" suffix="" fontSize={58} typeStart={0} cps={22} pause={8} cycle={28} loop={false} gradient={[accent, '#F4F7FC']} fontFamily={productionFont} mode="dark" /></Slot></Card><Card><Slot from={t.resolve} duration={duration}><Quote text={content.takeaway} /></Slot></Card></div></Grid>; };
const LayoutClassify = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => { const duration = shot.end_frame - shot.start_frame; const t = expandedStageTimings(duration); const accent = shot.accent_color || accentFallback; const nums = numericItems(content); return <Grid rows="330px 400px 302px"><div style={{display: 'grid', gridTemplateColumns: '1fr 310px', gap: 18}}><Card><ProgressSteps compactSpacing layout="portrait" steps={shortList(content.supporting_items, '分类非等级', 4)} title="" secondsPerStep={Math.max(1.1, duration / (30 * 6))} largeCopy productionCompact compactBox fontFamily={productionFont} /></Card><Card><Slot from={t.expand} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card></div><Card><Slot from={t.expand} duration={duration}><ChartAnimation unit={nums[0]?.unit} layout="portrait" title="分类演示" subtitle={content.metric?.detail ?? ''} data={chartPoints(nums)} maxValue={Math.max(...nums.map((item) => item.value), 1)} compactBox fontFamily={productionFont} /></Slot></Card><div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}><Card><Slot from={t.develop} duration={duration}><TextBuild text={shortList(content.supporting_items, content.takeaway, 3).join(' ')} axis="y" fontSize={52} color={white} fontWeight={840} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card><Card><Slot from={t.resolve} duration={duration}><Quote text={content.takeaway} /></Slot></Card></div></Grid>; };
const LayoutAccumulator = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const t = expandedStageTimings(duration);
  const nums = numericItems(content);
  const accent = shot.accent_color || accentFallback;
  const maxValue = metricParts(content.metric)?.value ?? Math.max(...nums.map((item) => item.value), 1);
  return <Grid rows="300px 470px 298px">
    <div style={{display: 'grid', gridTemplateColumns: '1fr 330px', gap: 18}}>
      <Card style={{padding: 28, display: 'grid', placeItems: 'center'}}><Formula content={content} size={48} /></Card>
      <Card><Slot from={t.expand} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card>
    </div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card><Slot from={t.expand} duration={duration}><ChartAnimation unit={nums[0]?.unit} layout="portrait" title="柱状累加" subtitle={content.metric?.detail ?? ''}
        data={chartPoints(nums, true)} maxValue={maxValue} compactBox fontFamily={productionFont} /></Slot></Card>
      <Card><Slot from={t.expand} duration={duration}><LineChartMini items={nums} title="趋势线" maxValue={maxValue} unit={nums[0]?.unit} /></Slot></Card>
    </div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card><Slot from={t.develop} duration={duration}><ItemCards items={shortList(content.items, content.takeaway, 3)} accent={accent} /></Slot></Card>
      <Card><Slot from={t.resolve} duration={duration}><TalkStage componentId="Talkcraft-ink-underline" content={content} title="单笔" body={content.takeaway} keyword={nums[0]?.display ?? content.takeaway} toText={`${content.metric?.label ?? ''} ${content.metric?.value ?? content.takeaway}`} width={470} height={298} /></Slot></Card>
    </div>
  </Grid>;
};
const LayoutRules = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const t = expandedStageTimings(duration);
  const accent = shot.accent_color || accentFallback;
  return <Grid rows="560px 230px 242px">
    <Card><ProgressSteps compactSpacing layout="portrait" steps={shortList(content.supporting_items, content.takeaway, 4)} title="" secondsPerStep={Math.max(1.1, duration / (30 * 6))} largeCopy productionCompact compactBox fontFamily={productionFont} /></Card>
    <div style={{display: 'grid', gridTemplateColumns: '330px 1fr', gap: 18}}>
      <Card><Slot from={t.develop} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card>
      <Card style={{display: 'grid', placeItems: 'center'}}><Slot from={t.develop} duration={duration}><WordFlip words={shortList(content.items, content.takeaway, 4)} prefix="" suffix="" fontSize={68} typeStart={0} cps={20} pause={8} cycle={30} loop={false} gradient={[accent, '#F4F7FC']} fontFamily={productionFont} mode="dark" /></Slot></Card>
    </div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}><Card><Slot from={t.resolve} duration={duration}><Quote text={content.takeaway} /></Slot></Card><Card style={{display: 'grid', placeItems: 'center'}}><Slot from={t.resolve} duration={duration}><TextHighlight before="" highlight={content.takeaway} after="" preset="underline" fontSize={58} fontWeight={860} baseColor={white} accentColor={accent} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card></div>
  </Grid>;
};
const LayoutBeforeAfterSteps = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const t = expandedStageTimings(duration);
  const nums = numericItems(content);
  const items = shortList(content.items, shot.body, 2);
  const [a, b] = items.map(splitItem);
  return <Grid rows="330px 330px 372px">
    <Card><SplitScreen layout="portrait" leftTitle={a?.title} leftText={a?.body} rightTitle={b?.title} rightText={b?.body} largeCopy productionCompact compactBox /></Card>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card>{nums.length >= 2 ? <ComparisonChart layout="portrait" title="前后对比" before={nums[0].value} after={nums[1].value}
        beforeLabel={nums[0].label} afterLabel={nums[1].label} maxValue={Math.max(...nums.map((item) => item.value), 1)} suffix={nums[0].unit} compactBox fontFamily={productionFont} /> : null}</Card>
      <Card style={{display: 'grid', placeItems: 'center'}}><Slot from={t.expand} duration={duration}><TextSwap fromText={a?.title ?? shot.title} toText={b?.title ?? content.takeaway} fontSize={58} color={white} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card>
    </div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card><Slot from={t.develop} duration={duration}><ProgressSteps compactSpacing layout="portrait" steps={shortList(content.supporting_items, content.takeaway, 4)} title="" secondsPerStep={Math.max(1.1, duration / (30 * 6))} largeCopy productionCompact compactBox fontFamily={productionFont} /></Slot></Card>
      <Card><Slot from={t.resolve} duration={duration}><TalkStage componentId="Talkcraft-strike-and-replace" content={content} title="补上步骤" body={content.takeaway} width={470} height={372} /></Slot></Card>
    </div>
  </Grid>;
};
const LayoutCondition = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const t = expandedStageTimings(duration);
  const accent = shot.accent_color || accentFallback;
  const items = shortList(content.items, shot.body, 2);
  const [a, b] = items.map(splitItem);
  return <Grid rows="360px 370px 338px">
    <Card><SplitScreen layout="portrait" leftTitle={a?.title} leftText={a?.body} rightTitle={b?.title} rightText={b?.body} largeCopy productionCompact compactBox /></Card>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 320px', gap: 18}}>
      <Card><Slot from={t.expand} duration={duration}><ProgressSteps compactSpacing layout="portrait" steps={shortList(content.supporting_items, content.takeaway, 4)} title="" secondsPerStep={Math.max(1.1, duration / (30 * 6))} largeCopy productionCompact compactBox fontFamily={productionFont} /></Slot></Card>
      <Card><Slot from={t.expand} duration={duration}><Count content={content} accent={accent} compact /></Slot></Card>
    </div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card style={{display: 'grid', placeItems: 'center'}}><Slot from={t.develop} duration={duration}><TextBuild text={shortList(content.items, content.takeaway, 3).map((item) => splitItem(item).title).join(' ')} axis="y" fontSize={48} color={white} fontWeight={820} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Slot></Card>
      <Card><Slot from={t.resolve} duration={duration}><TalkStage componentId="Talkcraft-word-slot-cycle" content={content} title="如果出现" body={content.takeaway} width={470} height={338} /></Slot></Card>
    </div>
  </Grid>;
};
const LayoutRewrite = ({shot, content}: {shot: TimelineShot; content: ExpandedContent}) => {
  const duration = shot.end_frame - shot.start_frame;
  const t = expandedStageTimings(duration);
  const items = shortList(content.items, shot.body, 2);
  const [a, b] = items.map(splitItem);
  return <Grid rows="320px 360px 352px">
    <div style={{display: 'grid', gridTemplateColumns: '1fr 310px', gap: 18}}><Card style={{display: 'grid', gridTemplateRows: '210px 110px'}}><div style={{position: 'relative'}}><SplitScreen layout="default" leftTitle="原先说法" leftText={a?.body} rightTitle="修正说法" rightText={b?.body} largeCopy productionCompact compactBox /></div><div style={{position: 'relative'}}><TextSwap fromText={content.items?.[0] ?? shot.title} toText={content.items?.[1] ?? content.takeaway} fontSize={46} color={white} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></div></Card><Card><Count content={content} accent={shot.accent_color || accentFallback} compact /></Card></div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card><Slot from={t.expand} duration={duration}><TalkStage componentId="Talkcraft-error-retype" content={content} title="改判断" body={content.takeaway} width={470} height={360} /></Slot></Card>
      <Card><Slot from={t.expand} duration={duration}><Quote text={shot.body || content.takeaway} /></Slot></Card>
    </div>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18}}>
      <Card><Slot from={t.develop} duration={duration}><TalkStage componentId="Talkcraft-strike-and-replace" content={content} title="划掉旧判断" body={content.takeaway} width={470} height={352} /></Slot></Card>
      <Card><Slot from={t.resolve} duration={duration}><ItemCards items={shortList(content.supporting_items, content.takeaway, 3)} accent={shot.accent_color || accentFallback} /></Slot></Card>
    </div>
  </Grid>;
};

const B07 = LayoutDashboard;
const B08 = LayoutLedger;
const B09 = LayoutCompare;
const B10 = LayoutAccumulator;
const B11 = LayoutCondition;
const B12 = LayoutSource;
const B13 = LayoutRewrite;
const B14 = LayoutAnswer;
const B15 = LayoutClassify;
const B16 = LayoutRules;
const B17 = LayoutChat;
const B18 = LayoutBeforeAfterSteps;

const layouts: Record<string, (props: {shot: TimelineShot; content: ExpandedContent}) => ReactNode> = {
  B07, B08, B09, B10, B11, B12, B13, B14, B15, B16, B17, B18,
};

export const ExpandedNoMaterialScene = ({shot}: {shot: TimelineShot}) => {
  const {width, height} = useVideoConfig();
  const setId = String(propsOf(shot).component_set);
  const content = contentOf(shot);
  const Scene = layouts[setId] ?? LayoutDashboard;
  const scale = Math.min(width / 1080, height / 1920);
  return <Shell><div style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${scale})`, transformOrigin: 'top left'}}><Headline shot={shot} /><Scene shot={shot} content={content} /><Emphasis shot={shot} content={content} /><Identity /></div></Shell>;
};
