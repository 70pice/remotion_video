import {createElement, type CSSProperties, type ReactNode} from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import componentSetCapabilities from '../../videoagents/component-set-capabilities.json';
import {ChatConversation, type ChatMessage} from '../components/component-horizontal/bits/examples/ChatConversation';
import {Component as KenBurns} from '../components/component-horizontal/bits/examples/KenBurns';
import ChartAnimation, {type ChartPoint} from '../components/component-horizontal/rve/chart-animation';
import ComparisonChart from '../components/component-horizontal/rve/comparison-chart';
import ProgressSteps from '../components/component-horizontal/rve/progress-steps';
import QuoteCard from '../components/component-horizontal/rve/quote-card';
import SplitScreen from '../components/component-horizontal/rve/split-screen';
import StatCounter from '../components/component-horizontal/rve/stat-counter';
import {AnswerStream, TextBuild, TextHighlight, TextReveal, TextSwap, WordFlip} from '../components/component-horizontal/snapcn';
import {PhoneFrame} from '../components/component-horizontal/snapcn/phone-frame';
import {muted, productionFont, white} from './adapters/layout';
import {talkcraftNativeMediaBindings, TALKCRAFT_PRODUCTION_MEDIA_CSS} from './TalkcraftNativeMedia';
import {LineChartPanel, TalkcraftPanel, type ExpandedTalkcraftComponentId} from './ExpandedSemanticPanels';
import {IsolatedCard} from '../components/community/IsolatedCard';
import {resolveTalkcraftTitleCopy} from '../components/component-horizontal/video-talkcraft/production-props';
import {tutorialRingPath, tutorialTargetRect, tutorialStepAt, type TutorialSourceSize, type TutorialStep} from './phoneTutorial';
import type {TimelineShot} from './types';

type Box = {x: number; y: number; width: number; height: number};
type Metric = {label: string; value: string; detail?: string};
type NumericDatum = {label: string; value: number; unit: string; display: string};
type SetContent = {
  takeaway: string;
  items?: string[];
  supporting_items?: string[];
  metric?: Metric;
  numeric_items?: string[];
  source_refs?: string[];
};
type SetDesignPart = {part_id: string; start_frame: number; end_frame: number; box: Box};
type SetDesign = {
  set_id: string;
  content: SetContent;
  parts?: SetDesignPart[];
  focus_steps?: TutorialStep[];
  source_size?: TutorialSourceSize;
};
type MetadataPart = {
  part_id: string;
  component_id: string;
  role: 'main' | 'title' | 'emphasis' | 'support';
  binding: string;
  box: Box;
  start_ratio: number;
  end_ratio: number;
};
type MetadataSet = {
  set_id: string;
  main_component_id: string;
  material_kind: 'none' | 'image' | 'image_or_video' | 'video';
  focus_supported?: boolean;
  parts: MetadataPart[];
};

type ResolvedPart = MetadataPart & {box: Box; start_frame: number; end_frame: number};

const metadata = componentSetCapabilities as {version: 1; safe_area: Box; sets: MetadataSet[]};
const metadataBySet = new Map(metadata.sets.map((entry) => [entry.set_id, entry]));
const talkcraftPanelIds = new Set(['Talkcraft-ink-underline', 'Talkcraft-strike-and-replace', 'Talkcraft-word-slot-cycle', 'Talkcraft-source-converge', 'Talkcraft-error-retype']);
const talkcraftMediaIds = new Set(['Talkcraft-slow-push-in', 'Talkcraft-slow-pull-reveal', 'Talkcraft-tilt-3d-page', 'Talkcraft-scanline-annotate']);

export const productionComponentSetIds = Object.freeze(metadata.sets.map((entry) => entry.set_id));
export const isProductionComponentSetDesign = (value: unknown): value is SetDesign => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const design = value as Record<string, unknown>;
  return typeof design.set_id === 'string' && metadataBySet.has(design.set_id) && Boolean(design.content) &&
    typeof design.content === 'object' && !Array.isArray(design.content);
};

const arrayOfText = (value: unknown): string[] => Array.isArray(value)
  ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0).map((item) => item.trim())
  : [];
const splitItem = (item: string) => {
  const [title, ...rest] = item.split(/[：:]/);
  return {title: (title || item).trim(), body: (rest.join(':') || item).trim()};
};
const integerMetric = (value: string | undefined): {value: number; unit: string} | null => {
  const match = value?.trim().match(/^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u);
  return match ? {value: Number(match[1]), unit: match[2]} : null;
};
const numericItems = (items: string[] | undefined): NumericDatum[] => arrayOfText(items).map((item) => {
  const [label, rawValue] = item.split(/[：:]/).map((piece) => piece.trim());
  const parsed = integerMetric(rawValue);
  return label && parsed ? {label, display: rawValue, ...parsed} : null;
}).filter((item): item is NumericDatum => Boolean(item));
const chartPoints = (items: readonly NumericDatum[], cumulative = false): ChartPoint[] => {
  let total = 0;
  return items.map((item, index) => {
    total += item.value;
    return {x: index, y: cumulative ? total : item.value, label: item.label};
  });
};
const boundedItems = (content: SetContent, preferred: 'items' | 'supporting_items' = 'items', count = 4) => {
  const first = arrayOfText(content[preferred]);
  const second = arrayOfText(preferred === 'items' ? content.supporting_items : content.items);
  const values = [...first, ...second, content.takeaway].filter(Boolean);
  return values.slice(0, count);
};
const valuesForBinding = (content: SetContent, binding: string): string[] => {
  if (binding.startsWith('items.')) {
    const index = Number(binding.split('.')[1]);
    const value = arrayOfText(content.items)[index];
    return value ? [value] : [];
  }
  if (binding.startsWith('supporting_items.')) {
    const index = Number(binding.split('.')[1]);
    const value = arrayOfText(content.supporting_items)[index];
    return value ? [value] : [];
  }
  if (binding === 'items') return arrayOfText(content.items);
  if (binding === 'supporting_items') return arrayOfText(content.supporting_items);
  if (binding === 'numeric_items') return arrayOfText(content.numeric_items);
  if (binding === 'metric') return content.metric ? [content.metric.label, content.metric.value, content.metric.detail ?? ''].filter(Boolean) : [];
  if (binding === 'takeaway') return [content.takeaway].filter(Boolean);
  if (binding === 'title') return [];
  if (binding === 'body') return [];
  return boundedItems(content);
};
const metricOf = (content: SetContent): {label: string; value: number; unit: string; detail?: string} => {
  const realCount = arrayOfText(content.items).length || arrayOfText(content.supporting_items).length || arrayOfText(content.numeric_items).length;
  const parsed = integerMetric(content.metric?.value) ?? {value: realCount, unit: '项'};
  return {label: content.metric?.label ?? '要点', detail: content.metric?.detail, ...parsed};
};
const maxValue = (items: readonly NumericDatum[], fallback = 1) => Math.max(fallback, ...items.map((item) => item.value));
const toCanvasBox = (box: Box): Box => ({
  x: metadata.safe_area.x + box.x * metadata.safe_area.width,
  y: metadata.safe_area.y + box.y * metadata.safe_area.height,
  width: box.width * metadata.safe_area.width,
  height: box.height * metadata.safe_area.height,
});
const safeBox = (box: Box) => ({position: 'absolute' as const, left: box.x, top: box.y, width: box.width, height: box.height});
const cloneShot = (shot: TimelineShot, componentId: string, start: number, end: number, content: SetContent): TimelineShot => ({
  ...shot,
  component_id: componentId,
  start_frame: 0,
  end_frame: Math.max(1, end - start),
  title: shot.title,
  body: shot.body || content.takeaway,
  props: {...shot.props, items: boundedItems(content), metric: content.metric},
  layers: [],
});

const resolvedParts = (setMeta: MetadataSet, design: SetDesign, duration: number): ResolvedPart[] => {
  const overrides = new Map((design.parts ?? []).map((part) => [part.part_id, part]));
  return setMeta.parts.map((part) => {
    const override = overrides.get(part.part_id);
    const start = override?.start_frame ?? Math.floor(duration * part.start_ratio);
    const end = override?.end_frame ?? Math.max(start + 1, Math.ceil(duration * part.end_ratio));
    return {...part, box: override?.box ?? part.box, start_frame: start, end_frame: Math.min(duration, Math.max(start + 1, end))};
  });
};

const Shell = ({children, accent}: {children: ReactNode; accent: string}) => {
  const {width, height} = useVideoConfig();
  const scale = Math.min(width / 1080, height / 1920);
  return <AbsoluteFill style={{background: `radial-gradient(ellipse at 24% 4%, ${accent}24, transparent 52%), #07101F`, color: white, overflow: 'hidden', fontFamily: productionFont}}>
    <div style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${scale})`, transformOrigin: 'top left'}}>{children}</div>
  </AbsoluteFill>;
};

const Card = ({children, accent, style}: {children: ReactNode; accent: string; style?: CSSProperties}) =>
  <div style={{position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: 26,
    border: `1px solid ${accent}55`, background: '#0B1729E8', boxSizing: 'border-box', boxShadow: '0 22px 58px #0008', ...style}}>{children}</div>;

const fitHeadlineFont = (text: string, box: Box, max = 68, ratio = 0.42) =>
  Math.max(30, Math.min(max, box.height * ratio, box.width / Math.max(8, [...text].length) * 1.1));

const fitBodyFont = (text: string, box: Box, max = 30) =>
  Math.max(20, Math.min(max, box.height * 0.2, box.width / Math.max(14, [...text].length) * 1.35));

const activeFocusRect = (design: SetDesign | undefined, frame: number, width: number, height: number): Box | null => {
  const source = design?.source_size;
  const steps = design?.focus_steps ?? [];
  const active = steps.length && source ? tutorialStepAt(steps, frame) : undefined;
  if (!active || !source) return null;
  const scale = Math.min(width / source.width, height / source.height);
  const left = (width - source.width * scale) / 2;
  const top = (height - source.height * scale) / 2;
  const raw = tutorialTargetRect(active.target, source);
  return {x: left + raw.x * scale, y: top + raw.y * scale, width: raw.width * scale, height: raw.height * scale};
};

const FocusRing = ({rect, width, height, label}: {rect: Box | null; width: number; height: number; label?: string}) => rect ? <svg data-focus-ring={label} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"
  style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}>
  <path d={tutorialRingPath(rect)} fill="none" stroke="#FB923C" strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
</svg> : null;

const MediaElement = ({shot, part, design}: {shot: TimelineShot; part: ResolvedPart; design?: SetDesign}) => {
  const {fps} = useVideoConfig();
  const localFrame = useCurrentFrame();
  const canvasBox = toCanvasBox(part.box);
  if (!shot.asset_src) return <div style={{display: 'grid', placeItems: 'center', width: '100%', height: '100%', color: muted}}>media</div>;
  const src = staticFile(shot.asset_src);
  const props = shot.props as Record<string, unknown>;
  const crop = props.asset_crop && typeof props.asset_crop === 'object' ? props.asset_crop as Partial<Box> : null;
  const fit = props.asset_fit === 'cover' || props.fit === 'cover' ? 'cover' : 'contain';
  const style: CSSProperties = crop && typeof crop.x === 'number' && typeof crop.y === 'number' && typeof crop.width === 'number' && typeof crop.height === 'number'
    ? {position: 'absolute', left: `${-crop.x / crop.width * 100}%`, top: `${-crop.y / crop.height * 100}%`, width: `${100 / crop.width}%`, height: `${100 / crop.height}%`, objectFit: 'fill'}
    : {width: '100%', height: '100%', objectFit: fit};
  const trimBefore = Math.round((typeof props.start_seconds === 'number' ? props.start_seconds : 0) * fps) + part.start_frame;
  const trimAfter = typeof props.end_seconds === 'number' ? Math.round(props.end_seconds * fps) : undefined;
  const video = /\.(mp4|webm|mov|m4v)$/i.test(shot.asset_src);
  const focusRect = activeFocusRect(design, part.start_frame + localFrame, canvasBox.width, canvasBox.height);
  const active = focusRect ? tutorialStepAt(design?.focus_steps ?? [], part.start_frame + localFrame) : undefined;
  return <div data-media-trim-before={video ? trimBefore : undefined} style={{position: 'absolute', inset: 0, background: '#020617', overflow: 'hidden'}}>
    {video ? <OffthreadVideo muted src={src} trimBefore={trimBefore} trimAfter={trimAfter} style={{...style, display: 'block'}} /> : <Img src={src} style={{...style, display: 'block'}} />}
    <FocusRing rect={focusRect} width={canvasBox.width} height={canvasBox.height} label={active?.instruction} />
  </div>;
};


const PhoneMedia = ({shot, content, design, part}: {shot: TimelineShot; content: SetContent; design: SetDesign; part: ResolvedPart}) => {
  const source = design.source_size;
  const steps = design.focus_steps ?? [];
  const canvasBox = toCanvasBox(part.box);
  const phoneScale = Math.min(1.2, Math.max(0.5, Math.min(canvasBox.width / 380, canvasBox.height / 760)));
  const localFrame = useCurrentFrame();
  const active = steps.length && source ? tutorialStepAt(steps, part.start_frame + localFrame) : undefined;
  const contained = active && source ? (() => {
    const scale = Math.min(300 / source.width, 640 / source.height);
    const left = (300 - source.width * scale) / 2;
    const top = (640 - source.height * scale) / 2;
    const raw = tutorialTargetRect(active.target, source);
    return {x: left + raw.x * scale, y: top + raw.y * scale, width: raw.width * scale, height: raw.height * scale};
  })() : null;
  return <div data-phone-scale={phoneScale.toFixed(3)} style={{position: 'absolute', inset: 0, display: 'grid', placeItems: 'center'}}>
    <PhoneFrame variant="flat" entrance="rise" scale={phoneScale} showDynamicIsland={false}
      bezelColor="#0B1220" screenColor="#050A12">
      <div style={{position: 'relative', width: 300, height: 640, overflow: 'hidden', background: '#050A12'}}>
        <MediaElement shot={shot} part={part} />
        <FocusRing rect={contained} width={300} height={640} label={active?.instruction} />
      </div>
    </PhoneFrame>
    {steps.length ? <div style={{position: 'absolute', left: 24, right: 24, bottom: 18, borderRadius: 18, background: '#020617D9', border: '1px solid #FFFFFF24', padding: 14, textAlign: 'center', fontSize: 26, fontWeight: 800}}>{active?.instruction ?? content.takeaway}</div> : null}
  </div>;
};

const talkcraftNativeMediaClassName = (componentId: string): string =>
  `native-media-${componentId.replace(/^Talkcraft-/, '').replace(/[^a-z0-9-]/gi, '-').toLowerCase()}`;

const TalkcraftMediaSlot = ({shot, part, componentId, items}: {shot: TimelineShot; part: ResolvedPart; componentId: string; items: string[]}) => {
  const binding = talkcraftNativeMediaBindings.find((entry) => entry.id === componentId);
  if (!binding || !shot.asset_src) return null;
  const canvasBox = toCanvasBox(part.box);
  const scale = Math.min(canvasBox.width / 960, canvasBox.height / 540);
  const mediaShot = cloneShot(shot, componentId, part.start_frame, part.end_frame, {takeaway: items[0] ?? shot.body});
  mediaShot.title = items[0] ?? shot.title;
  mediaShot.body = items.slice(1).join(' / ') || shot.body;
  mediaShot.props = {...mediaShot.props, asset_fit: 'contain', items};
  const props = binding.props(staticFile(shot.asset_src), resolveTalkcraftTitleCopy(mediaShot), mediaShot);
  const safeProps = componentId === 'Talkcraft-scanline-annotate' ? {...props, targets: [], labels: []} : props;
  return <div data-native-id={componentId} style={{position: 'absolute', left: (canvasBox.width - 960 * scale) / 2, top: (canvasBox.height - 540 * scale) / 2,
    width: 960, height: 540, transform: `scale(${scale})`, transformOrigin: 'top left', overflow: 'hidden'}}>
    <IsolatedCard>
      <style>{TALKCRAFT_PRODUCTION_MEDIA_CSS}</style>
      <div className={`talkcraft-production-media ${talkcraftNativeMediaClassName(componentId)}`}>
        {createElement(binding.Component, safeProps)}
      </div>
    </IsolatedCard>
  </div>;
};

const RenderPart = ({shot, content, design, part}: {shot: TimelineShot; content: SetContent; design: SetDesign; part: ResolvedPart}) => {
  const accent = shot.accent_color || '#38BDF8';
  const canvasBox = toCanvasBox(part.box);
  const boundValues = valuesForBinding(content, part.binding);
  const items = boundValues;
  const nums = numericItems(content.numeric_items);
  const metric = metricOf(content);
  const [left, right] = (items.length >= 2 ? items : [shot.title, content.takeaway]).map(splitItem);
  const textTheme = {background: 'transparent', foreground: white};
  if (part.component_id === 'Snapcn-TextReveal') return <Card accent={accent} style={{display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: Math.max(6, canvasBox.height * 0.06), padding: '8px 28px', background: 'transparent', boxShadow: 'none', border: 0}}>
    <div data-title-flow="headline" style={{position: 'relative', height: shot.body ? '58%' : '100%', minHeight: Math.max(56, canvasBox.height * 0.5), overflow: 'hidden'}}>
      <TextReveal text={shot.title} fontSize={fitHeadlineFont(shot.title, canvasBox, canvasBox.height > 170 ? 70 : 52, shot.body ? 0.38 : 0.5)} color={white} initialScale={1.04} fontWeight={880} fontFamily={productionFont} mode="dark" theme={textTheme} />
    </div>
    {shot.body ? <div data-title-flow="body" style={{position: 'relative', color: '#D9E4F2', fontSize: fitBodyFont(shot.body, canvasBox), lineHeight: 1.18, fontWeight: 650, textAlign: 'center', overflow: 'hidden'}}>{shot.body}</div> : null}
  </Card>;
  if (part.component_id === 'Snapcn-TextHighlight') return <Card accent={accent} style={{display: 'grid', placeItems: 'center'}}><TextHighlight before="" highlight={items[0] ?? content.takeaway ?? shot.title} after="" preset="underline" fontSize={Math.min(58, canvasBox.height * 0.42)} fontWeight={880} baseColor={white} accentColor={accent} fontFamily={productionFont} mode="dark" theme={textTheme} /></Card>;
  if (part.component_id === 'Snapcn-TextBuild') return <Card accent={accent} style={{display: 'grid', placeItems: 'center', padding: 24}}><TextBuild text={items.join(' ')} axis="y" fontSize={Math.min(48, canvasBox.height * 0.18)} color={white} fontWeight={820} fontFamily={productionFont} mode="dark" theme={textTheme} /></Card>;
  if (part.component_id === 'Snapcn-TextSwap') return <Card accent={accent} style={{display: 'grid', placeItems: 'center'}}><TextSwap fromText={left?.title ?? shot.title} toText={right?.title ?? content.takeaway} fontSize={Math.min(54, canvasBox.height * 0.25)} color={white} fontFamily={productionFont} mode="dark" theme={textTheme} /></Card>;
  if (part.component_id === 'Snapcn-WordFlip') {
    const cycle = Math.max(12, Math.floor((part.end_frame - part.start_frame) / Math.max(1, items.length)));
    const pause = Math.max(2, Math.min(8, Math.floor(cycle * 0.2)));
    return <Card accent={accent} style={{display: 'grid', placeItems: 'center'}}><WordFlip prefix="" suffix="" words={items} fontSize={Math.max(34, Math.min(62, canvasBox.height * 0.34, canvasBox.width * 0.16))} typeStart={0} cps={32} pause={pause} cycle={cycle} exitDuration={Math.max(4, Math.floor(cycle * 0.28))} enterDuration={Math.max(4, Math.floor(cycle * 0.28))} loop={false} gradient={[accent, '#F4F7FC']} fontFamily={productionFont} mode="dark" /></Card>;
  }
  if (part.component_id === 'Snapcn-AnswerStream') return <Card accent={accent}><AnswerStream question={shot.title} answer={shot.body || content.takeaway} headline="" cards={items.slice(0, 3).map((item) => ({title: item, body: ''}))} model="本期回答" productionCompact slotWidth={canvasBox.width} slotHeight={canvasBox.height} accentColor={accent} fontFamily={productionFont} mode="dark" /></Card>;
  if (part.component_id === 'Rve-QuoteCard') return <Card accent={accent}><QuoteCard layout="portrait" quote={items.join(' / ')} attribution="" fontFamily={productionFont} transparentStage quoteFontSize={Math.max(24, Math.min(46, canvasBox.height * 0.24, canvasBox.width * 0.09))} productionCompact instantReveal slotWidth={canvasBox.width} slotHeight={canvasBox.height} /></Card>;
  if (part.component_id === 'Rve-ProgressSteps') return <Card accent={accent}><ProgressSteps compactSpacing layout="portrait" steps={items.slice(0, 4)} title="" secondsPerStep={Math.max(0.5, ((part.end_frame - part.start_frame) / 30 - 0.5) / Math.max(1, items.length))} largeCopy productionCompact compactBox fontFamily={productionFont} /></Card>;
  if (part.component_id === 'Rve-SplitScreen') return <Card accent={accent}><SplitScreen layout="portrait" leftTitle={left?.title} leftText={left?.body} rightTitle={right?.title} rightText={right?.body} largeCopy productionCompact compactBox /></Card>;
  if (part.component_id === 'Rve-StatCounter') return <Card accent={accent}><StatCounter layout="portrait" value={metric.value} suffix={metric.unit} label={metric.label} change="" period={metric.detail ?? ''} productionCompact compactBox fontFamily={productionFont} slotWidth={canvasBox.width} slotHeight={canvasBox.height} /></Card>;
  if (part.component_id === 'Rve-ChartAnimation') {
    return <Card accent={accent}><ChartAnimation unit={nums[0]?.unit} layout="portrait" title={content.metric?.label ?? shot.title} subtitle={content.metric?.detail} data={chartPoints(nums)} maxValue={maxValue(nums, metric.value)} compactBox fontFamily={productionFont} /></Card>;
  }
  if (part.component_id === 'Rve-LineChart') return <Card accent={accent}><LineChartPanel title={content.metric?.label ?? shot.title} data={chartPoints(nums, true)} unit={nums[0]?.unit} subtitle={content.metric?.detail} maxValue={metric.value} accentColor={accent} slotWidth={canvasBox.width} slotHeight={canvasBox.height} /></Card>;
  if (part.component_id === 'Rve-ComparisonChart') {
    return <Card accent={accent}><ComparisonChart layout="portrait" title={shot.title} before={nums[0]?.value ?? 0} after={nums[1]?.value ?? 0} beforeLabel={nums[0]?.label ?? ''} afterLabel={nums[1]?.label ?? ''} maxValue={maxValue(nums)} suffix={nums[0]?.unit ?? ''} compactBox fontFamily={productionFont} /></Card>;
  }
  if (part.component_id === 'Bits-ChatConversation') {
    const messages: ChatMessage[] = items.slice(0, 4).map((item, index) => ({from: /^我[:：]/.test(item) || index % 2 === 1 ? 'me' : 'them', text: item.replace(/^(我|对方)[:：]\s*/, '')}));
    return <Card accent={accent}><ChatConversation messages={messages} variant="rise" showAvatars={false} stagger={16} compactBox fontSize={Math.min(42, canvasBox.height * 0.12)} fontFamily={productionFont} /></Card>;
  }
  if (part.component_id === 'Bits-KenBurns') return <Card accent={accent} style={{background: '#020617'}}><KenBurns images={shot.asset_src ? [staticFile(shot.asset_src)] : []} layout="default" stepDuration={part.end_frame - part.start_frame} transitionDuration={0} fit="contain" /></Card>;
  if (part.component_id === 'Snapcn-PhoneFrame') return <Card accent={accent} style={{background: '#020617'}}><PhoneMedia shot={shot} content={content} design={design} part={part} /></Card>;
  if (['video', 'evidence', 'image_focus'].includes(part.component_id)) return <Card accent={accent} style={{background: '#020617'}}><MediaElement shot={shot} part={part} design={design} /></Card>;
  if (talkcraftMediaIds.has(part.component_id)) return <Card accent={accent} style={{background: '#020617'}}><TalkcraftMediaSlot shot={shot} part={part} componentId={part.component_id} items={items} /></Card>;
  if (talkcraftPanelIds.has(part.component_id)) return <TalkcraftPanel componentId={part.component_id as ExpandedTalkcraftComponentId} title={items[0] ?? shot.title} body={items.join(' / ')} items={items} keyword={items[0] ?? content.takeaway} fromText={items[0]} toText={items[1] ?? content.takeaway} accentColor={accent} slotWidth={canvasBox.width} slotHeight={canvasBox.height} productionCompact partDurationFrames={part.end_frame - part.start_frame} />;
  throw new Error(`Production component set part ${part.part_id} uses unsupported component ${part.component_id}`);
};

export const ProductionComponentSetScene = ({shot}: {shot: TimelineShot}) => {
  const design = (shot as TimelineShot & {set_design?: SetDesign}).set_design;
  if (!isProductionComponentSetDesign(design)) return null;
  const setMeta = metadataBySet.get(design.set_id);
  if (!setMeta) return null;
  const duration = shot.end_frame - shot.start_frame;
  const content = design.content;
  const parts = resolvedParts(setMeta, design, duration);
  return <Shell accent={shot.accent_color || '#38BDF8'}>
    <div data-component-set-production={design.set_id} data-main-component-id={setMeta.main_component_id}>
      {parts.map((part) => <Sequence key={part.part_id} from={part.start_frame} durationInFrames={part.end_frame - part.start_frame} layout="none">
        {(() => {
          const canvasBox = toCanvasBox(part.box);
          return (
        <div data-set-part={part.part_id} data-native-id={part.component_id} data-local-start={part.start_frame}
          style={safeBox(canvasBox)}>
          <RenderPart shot={shot} content={content} design={design} part={part} />
        </div>
          );
        })()}
      </Sequence>)}
    </div>
  </Shell>;
};
