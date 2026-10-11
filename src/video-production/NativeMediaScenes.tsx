import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Sequence, staticFile} from 'remotion';
import {ChatConversation, type ChatMessage} from '../components/component-horizontal/bits/examples/ChatConversation';
import {CursorFlyover} from '../components/component-horizontal/bits/examples/CursorFlyover';
import {KenBurns} from '../components/component-horizontal/bits/examples/KenBurns';
import {AnimatedLineChart} from '../components/component-horizontal/remocn/animated-line-chart';
import ChartAnimation, {type ChartPoint} from '../components/component-horizontal/rve/chart-animation';
import ComparisonChart from '../components/component-horizontal/rve/comparison-chart';
import LineChart from '../components/component-horizontal/rve/line-chart';
import ProgressSteps from '../components/component-horizontal/rve/progress-steps';
import QuoteCard from '../components/component-horizontal/rve/quote-card';
import SplitScreen from '../components/component-horizontal/rve/split-screen';
import StatCounter from '../components/component-horizontal/rve/stat-counter';
import {FittedText, muted, productionFont, white} from './adapters/layout';
import type {TimelineShot} from './types';
import {isNoMaterialSet, noMaterialSetGeometry} from './noMaterialSetGeometry';

export type NativeMediaSceneContext = {layout?: 'portrait' | 'landscape'; componentSample?: boolean};
type Requirement = 'image_media' | 'items' | 'metric' | 'text' | 'strict_numeric_items';
type NativeLibrary = 'RVE' | 'Remocn' | 'Bits';
type Crop = {x: number; y: number; width: number; height: number};
type ContentConstraints = {
  items_min?: number;
  numeric_first_item?: boolean;
  body_required?: boolean;
  media_required?: boolean;
  image_only?: boolean;
  metric_required?: boolean;
};

export type NativeMediaSceneBinding = {
  component_id: string;
  library: NativeLibrary;
  origin: 'native-source';
  source: string;
  content_constraints: ContentConstraints;
  requires: readonly Requirement[];
  render: (shot: TimelineShot, context?: NativeMediaSceneContext) => ReactNode;
};

export const NATIVE_MEDIA_SCENE_SAFE_BOX = Object.freeze({
  title: {x: 70, y: 180, width: 940, height: 270},
  mainDefault: {x: 70, y: 500, width: 940, height: 840},
  mainWithLayers: {x: 70, y: 500, width: 940, height: 600},
  sourceY: 1384,
});

export const nativeMediaSceneSupport = Object.freeze([
  {component_id: 'Bits-CursorFlyover', library: 'Bits', origin: 'native-source', media: true, source: 'src/components/component-horizontal/bits/examples/CursorFlyover.tsx'},
  {component_id: 'Bits-KenBurns', library: 'Bits', origin: 'native-source', media: true, source: 'src/components/component-horizontal/bits/examples/KenBurns.tsx'},
  {component_id: 'Rve-QuoteCard', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/quote-card.tsx'},
  {component_id: 'Rve-ProgressSteps', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/progress-steps.tsx'},
  {component_id: 'Rve-SplitScreen', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/split-screen.tsx'},
  {component_id: 'Bits-ChatConversation', library: 'Bits', origin: 'native-source', media: false, source: 'src/components/component-horizontal/bits/examples/ChatConversation.tsx'},
  {component_id: 'Remocn-AnimatedLineChart', library: 'Remocn', origin: 'native-source', media: false, source: 'src/components/component-horizontal/remocn/animated-line-chart/index.tsx'},
  {component_id: 'Rve-LineChart', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/line-chart.tsx'},
  {component_id: 'Rve-ChartAnimation', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/chart-animation.tsx'},
  {component_id: 'Rve-ComparisonChart', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/comparison-chart.tsx'},
  {component_id: 'Rve-StatCounter', library: 'RVE', origin: 'native-source', media: false, source: 'src/components/component-horizontal/rve/stat-counter.tsx'},
] as const);

type NumericDatum = {label: string; value: number; unit: string; display: string};
type MetricDatum = {label: string; value: number; unit: string; display: string; prefix: string; detail?: string};

const chartPalette = ['#38BDF8', '#A3E635', '#F97316', '#F43F5E', '#FACC15', '#2DD4BF'];
const imagePattern = /\.(png|jpe?g|webp|gif)$/i;
const propsOf = (shot: TimelineShot) => shot.props as Record<string, unknown>;
const present = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
const titleOf = (shot: TimelineShot) => (shot.title || '').trim();
const bodyOf = (shot: TimelineShot) => (shot.body || '').trim();
const sourceOf = (shot: TimelineShot) => (shot.source_label || '').trim();
const fail = (componentId: string, message: string): never => { throw new Error(`${componentId}: ${message}`); };
const isCrop = (value: unknown): value is Crop => Boolean(value && typeof value === 'object'
  && typeof (value as Crop).x === 'number'
  && typeof (value as Crop).y === 'number'
  && typeof (value as Crop).width === 'number'
  && typeof (value as Crop).height === 'number');

const requireImageMedia = (shot: TimelineShot, componentId: string) => {
  const src = typeof shot.asset_src === 'string' ? shot.asset_src.trim() : '';
  if (!present(src)) fail(componentId, 'requires shot.asset_src from the current job');
  if (!imagePattern.test(src)) fail(componentId, 'requires image media because the source component renders with <Img>');
  return staticFile(src);
};
const assetFitOf = (shot: TimelineShot) => propsOf(shot).asset_fit === 'contain' ? 'contain' : 'cover';
const assetCropOf = (shot: TimelineShot) => {
  const crop = propsOf(shot).asset_crop;
  return isCrop(crop) ? crop : null;
};

const textItemsOf = (shot: TimelineShot, componentId: string, minimum = 1): string[] => {
  const raw = propsOf(shot).items;
  if (!Array.isArray(raw)) fail(componentId, `requires props.items with at least ${minimum} string entr${minimum === 1 ? 'y' : 'ies'}`);
  const rawItems = raw as unknown[];
  const items: string[] = [];
  rawItems.forEach((rawItem, index) => {
    if (typeof rawItem !== 'string') fail(componentId, `props.items[${index}] must be a string; object items are outside the current contract`);
    const item = String(rawItem).trim();
    if (item.length > 0) items.push(item);
  });
  if (items.length < minimum) fail(componentId, `requires at least ${minimum} nonempty props.items strings`);
  return items;
};

const parseNumberWithUnit = (input: string, componentId: string, field: string, allowQualifier = false): {value: number; unit: string; display: string; prefix: string} => {
  const value = input.trim();
  if (!value) fail(componentId, `${field} is empty`);
  if (/[/%％]/.test(value)) fail(componentId, `${field} rejects ratios and denominatorless percentages; provide a sourced count with unit instead`);
  const normalized = value.replace(/,/g, '');
  const match = normalized.match(/^(?:(约|近|超|超过|高达|至少|最多)\s*)?([+-]?\d+(?:\.\d+)?)(\s*[\p{Script=Han}A-Za-z$¥￥元万亿人次单份条个笔件分钟小时天]+)?$/u);
  const numericText = match?.[2];
  if (!numericText) fail(componentId, `${field} must be a standalone number plus optional explicit unit; mixed text is rejected`);
  if (match?.[1] && !allowQualifier) fail(componentId, `${field} approximate or bounded chart values are rejected`);
  const unitText = match?.[3];
  const number = Number(numericText);
  if (!Number.isFinite(number)) fail(componentId, `${field} is not finite`);
  return {value: number, unit: (unitText ?? '').trim(), display: value, prefix: match?.[1] ?? ''};
};

const metricOf = (shot: TimelineShot, componentId: string): MetricDatum => {
  const raw = propsOf(shot).metric;
  if (!raw || typeof raw !== 'object') fail(componentId, 'requires props.metric with real label/value');
  const metric = raw as Record<string, unknown>;
  const label = metric.label;
  const value = metric.value;
  const detail = metric.detail;
  if (!present(label) || !present(value)) fail(componentId, 'requires props.metric.label and props.metric.value');
  const metricLabel = String(label).trim();
  const metricValue = String(value).trim();
  const parsed = parseNumberWithUnit(metricValue, componentId, 'props.metric.value', componentId === 'Rve-StatCounter');
  return {label: metricLabel, value: parsed.value, unit: parsed.unit, display: parsed.display, prefix: parsed.prefix, ...(present(detail) ? {detail: detail.trim()} : {})};
};

const numericItemsOf = (shot: TimelineShot, componentId: string, minimum = 2): NumericDatum[] => {
  const items = textItemsOf(shot, componentId, minimum);
  const parsed = items.map((item, index) => {
    const pieces = item.split(/[：:|，,]/).map((piece) => piece.trim()).filter(Boolean);
    if (pieces.length !== 2) fail(componentId, `props.items[${index}] must be "label: value+unit" with no extra fields`);
    const [label, rawValue] = pieces as [string, string];
    const number = parseNumberWithUnit(rawValue, componentId, `props.items[${index}]`);
    return {label, value: number.value, unit: number.unit, display: rawValue};
  });
  const units = new Set(parsed.map((item) => item.unit));
  if (units.size !== 1) fail(componentId, 'numeric props.items must use one shared unit; mixed units are rejected');
  return parsed;
};

const chartPointsOf = (shot: TimelineShot, componentId: string): ChartPoint[] =>
  numericItemsOf(shot, componentId, 2).map((item, index) => ({x: index, y: item.value, label: item.label}));
const maxValueOf = (items: readonly {value: number}[]) => Math.max(1, ...items.map((item) => item.value));
const splitLabel = (item: string) => { const [head, ...rest] = item.split(/[：:]/); return {title: (head || item).trim(), body: (rest.join('：') || item).trim()}; };

const NativeTitle = ({shot, componentSample = false}: {shot: TimelineShot; componentSample?: boolean}) => {
  const title = titleOf(shot);
  if (!title) return null;
  const box = componentSample ? {x: 70, y: 120, width: 940, height: 380} : NATIVE_MEDIA_SCENE_SAFE_BOX.title;
  return <div style={{position: 'absolute', left: box.x, top: box.y, width: box.width, height: box.height}}>
    <div style={{width: 70, height: 6, borderRadius: 999, background: shot.accent_color, marginBottom: 20}} />
    <FittedText text={title} width={box.width} height={box.height - 26}
      fontSize={58} minFontSize={28} style={{color: white}} />
  </div>;
};

const NativeShell = ({shot, showTitle = false, componentSample = false, children}: {shot: TimelineShot; showTitle?: boolean; componentSample?: boolean; children: ReactNode}) => {
  const hasTitleLayer = shot.layers?.some((layer) => layer.role === 'title') ?? false;
  const hasEmphasisLayer = shot.layers?.some((layer) => layer.role === 'emphasis') ?? false;
  const textOnly = componentSample && isNoMaterialSet(shot.props.component_set);
  const mainBox = textOnly ? noMaterialSetGeometry.main : componentSample
    ? {x: 70, y: 600, width: 940, height: 850}
    : hasEmphasisLayer ? NATIVE_MEDIA_SCENE_SAFE_BOX.mainWithLayers : NATIVE_MEDIA_SCENE_SAFE_BOX.mainDefault;
  const shellStyle: CSSProperties = {
    position: 'absolute',
    left: mainBox.x,
    top: mainBox.y,
    width: mainBox.width,
    height: mainBox.height,
    overflow: 'hidden',
    borderRadius: 28,
    border: `1px solid ${shot.accent_color}66`,
    background: textOnly ? 'transparent' : '#050A12',
    boxShadow: textOnly ? undefined : '0 24px 64px #0009',
  };
  return <AbsoluteFill style={{background: textOnly ? 'transparent' : `radial-gradient(circle at 50% 18%, ${shot.accent_color}2E, transparent 42%), #08111F`, color: white,
    overflow: 'hidden', fontFamily: productionFont}}>
    {showTitle && !hasTitleLayer ? <NativeTitle shot={shot} componentSample={componentSample} /> : null}
    <div style={shellStyle}>
      <Sequence width={mainBox.width} height={mainBox.height} durationInFrames={Math.max(1, shot.end_frame - shot.start_frame)}>
        <div style={{position: 'absolute', inset: 0, width: mainBox.width, height: mainBox.height, overflow: 'hidden'}}>
          {children}
        </div>
      </Sequence>
    </div>
    {!hasEmphasisLayer && sourceOf(shot) ? <div style={{position: 'absolute', left: 70, right: 70, top: componentSample ? 1810 : NATIVE_MEDIA_SCENE_SAFE_BOX.sourceY,
      height: 42, color: muted, fontSize: 22, fontWeight: 650, borderTop: '1px solid #334155', paddingTop: 10}}>
      {sourceOf(shot)}
    </div> : null}
  </AbsoluteFill>;
};

const bindings: NativeMediaSceneBinding[] = [
  {component_id: 'Bits-CursorFlyover', library: 'Bits', origin: 'native-source', source: 'src/components/component-horizontal/bits/examples/CursorFlyover.tsx', content_constraints: {media_required: true, image_only: true}, requires: ['image_media'], render: (shot, context) => <NativeShell shot={shot} showTitle componentSample={Boolean(context?.componentSample)}><CursorFlyover src={requireImageMedia(shot, 'Bits-CursorFlyover')} layout={context?.componentSample ? 'portrait' : 'default'} fit={assetFitOf(shot)} crop={assetCropOf(shot)} /></NativeShell>},
  {component_id: 'Bits-KenBurns', library: 'Bits', origin: 'native-source', source: 'src/components/component-horizontal/bits/examples/KenBurns.tsx', content_constraints: {media_required: true, image_only: true}, requires: ['image_media'], render: (shot, context) => { const src = requireImageMedia(shot, 'Bits-KenBurns'); return <NativeShell shot={shot} showTitle componentSample={Boolean(context?.componentSample)}><KenBurns images={[src]} layout={context?.componentSample ? 'portrait' : 'default'} stepDuration={90} transitionDuration={0} fit={assetFitOf(shot)} crop={assetCropOf(shot)} /></NativeShell>; }},
  {component_id: 'Rve-QuoteCard', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/quote-card.tsx', content_constraints: {body_required: false}, requires: ['text'], render: (shot, context) => <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><QuoteCard layout="portrait" quote={bodyOf(shot) || titleOf(shot)} attribution={shot.props.component_set === 'B01' ? '' : sourceOf(shot) || titleOf(shot)} fontFamily={shot.props.component_set === 'B01' ? productionFont : undefined} transparentStage={shot.props.component_set === 'B01'} quoteFontSize={shot.props.component_set === 'B01' ? Math.min(76, Math.floor(Math.sqrt(780 * 460 / Math.max(1, [...bodyOf(shot)].length)))) : undefined} productionCompact /></NativeShell>},
  {component_id: 'Rve-ProgressSteps', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/progress-steps.tsx', content_constraints: {items_min: 2}, requires: ['items'], render: (shot, context) => <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><ProgressSteps layout="portrait" steps={textItemsOf(shot, 'Rve-ProgressSteps', 2).slice(0, 4)} title={shot.props.component_set === 'B05' ? '' : titleOf(shot)} secondsPerStep={shot.props.component_set === 'B05' ? (shot.end_frame - shot.start_frame) / (30 * 3) : 0.72} largeCopy={shot.props.component_set === 'B05'} productionCompact /></NativeShell>},
  {component_id: 'Rve-SplitScreen', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/split-screen.tsx', content_constraints: {items_min: 2}, requires: ['items'], render: (shot, context) => { const [left, right] = textItemsOf(shot, 'Rve-SplitScreen', 2).map(splitLabel); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><SplitScreen layout="portrait" leftTitle={left.title} leftText={left.body} rightTitle={right.title} rightText={right.body} largeCopy={shot.props.component_set === 'B03'} productionCompact /></NativeShell>; }},
  {component_id: 'Bits-ChatConversation', library: 'Bits', origin: 'native-source', source: 'src/components/component-horizontal/bits/examples/ChatConversation.tsx', content_constraints: {items_min: 2}, requires: ['items'], render: (shot, context) => { const messages: ChatMessage[] = textItemsOf(shot, 'Bits-ChatConversation', 2).slice(0, 6).map((item, index) => ({from: /^\s*(我|me)[:：]/i.test(item) || index % 2 === 1 ? 'me' : 'them', text: item.replace(/^\s*(我|对方|me|them)[:：]\s*/i, '')})); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><ChatConversation messages={messages} variant="rise" showAvatars /></NativeShell>; }},
  {component_id: 'Remocn-AnimatedLineChart', library: 'Remocn', origin: 'native-source', source: 'src/components/component-horizontal/remocn/animated-line-chart/index.tsx', content_constraints: {items_min: 2, numeric_first_item: true}, requires: ['strict_numeric_items'], render: (shot, context) => { const data = numericItemsOf(shot, 'Remocn-AnimatedLineChart', 2); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><AnimatedLineChart data={data.map((item) => item.value)} strokeColor={shot.accent_color || chartPalette[0]} width={840} height={520} /></NativeShell>; }},
  {component_id: 'Rve-LineChart', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/line-chart.tsx', content_constraints: {items_min: 2, numeric_first_item: true}, requires: ['strict_numeric_items'], render: (shot, context) => { const data = chartPointsOf(shot, 'Rve-LineChart'); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><LineChart layout="portrait" data={data} title={titleOf(shot)} maxValue={Math.max(1, ...data.map((item) => item.y))} /></NativeShell>; }},
  {component_id: 'Rve-ChartAnimation', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/chart-animation.tsx', content_constraints: {items_min: 2, numeric_first_item: true}, requires: ['strict_numeric_items'], render: (shot, context) => { const data = chartPointsOf(shot, 'Rve-ChartAnimation'); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><ChartAnimation layout="portrait" data={data} title={titleOf(shot)} subtitle={sourceOf(shot)} maxValue={Math.max(1, ...data.map((item) => item.y))} /></NativeShell>; }},
  {component_id: 'Rve-ComparisonChart', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/comparison-chart.tsx', content_constraints: {items_min: 2, numeric_first_item: true}, requires: ['strict_numeric_items'], render: (shot, context) => { const [before, after] = numericItemsOf(shot, 'Rve-ComparisonChart', 2); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><ComparisonChart layout="portrait" title={titleOf(shot)} before={before.value} after={after.value} beforeLabel={before.label} afterLabel={after.label} maxValue={maxValueOf([before, after])} suffix={before.unit} /></NativeShell>; }},
  {component_id: 'Rve-StatCounter', library: 'RVE', origin: 'native-source', source: 'src/components/component-horizontal/rve/stat-counter.tsx', content_constraints: {metric_required: true}, requires: ['metric'], render: (shot, context) => { const metric = metricOf(shot, 'Rve-StatCounter'); const counted = `${metric.prefix}${metric.value}${metric.unit}`; const change = [metric.display !== counted ? metric.display : '', metric.detail ?? ''].filter(Boolean).join('｜'); return <NativeShell shot={shot} componentSample={Boolean(context?.componentSample)}><StatCounter layout="portrait" value={metric.value} prefix={metric.prefix} suffix={metric.unit} label={metric.label} change={change} period={sourceOf(shot)} productionCompact /></NativeShell>; }},
];

export const nativeMediaSceneBindings = Object.freeze(bindings);
export const nativeMediaSceneIds = Object.freeze(bindings.map((binding) => binding.component_id));
const bindingById = new Map(nativeMediaSceneBindings.map((binding) => [binding.component_id, binding]));
export const hasNativeMediaScene = (componentId: string) => bindingById.has(componentId);
export const renderNativeMediaScene = (shot: TimelineShot, context?: NativeMediaSceneContext) => {
  const binding = bindingById.get(shot.component_id);
  if (!binding) fail(shot.component_id, 'has no native media scene binding');
  return binding!.render(shot, context);
};
