import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Freeze, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import ChartAnimation, {type ChartPoint} from '../components/component-horizontal/rve/chart-animation';
import LineChart from '../components/component-horizontal/rve/line-chart';
import ProgressSteps from '../components/component-horizontal/rve/progress-steps';
import QuoteCard from '../components/component-horizontal/rve/quote-card';
import SplitScreen from '../components/component-horizontal/rve/split-screen';
import StatCounter from '../components/component-horizontal/rve/stat-counter';
import {PhoneFrame} from '../components/component-horizontal/snapcn/phone-frame';
import {TextBuild, TextHighlight, TextReveal, TextSwap, WordFlip} from '../components/component-horizontal/snapcn';
import InkUnderline from '../components/component-horizontal/video-talkcraft/cards/ink-underline';
import SourceConverge from '../components/component-horizontal/video-talkcraft/cards/source-converge';
import ScanlineAnnotate from '../components/component-horizontal/video-talkcraft/cards/scanline-annotate';
import SlowPullReveal from '../components/component-horizontal/video-talkcraft/cards/slow-pull-reveal';
import SlowPushIn from '../components/component-horizontal/video-talkcraft/cards/slow-push-in';
import Tilt3dPage from '../components/component-horizontal/video-talkcraft/cards/tilt-3d-page';
import {IsolatedCard} from '../components/community/IsolatedCard';
import {FittedText, muted, productionFont, white} from './adapters/layout';
import {fullCrop, resolveVideoCropGeometry} from './adapters/videoGeometry';
import {richMaterialNativeIdsForSet, type RichMaterialSetId} from './RichMaterialContract';
import {richMaterialGeometry} from './RichMaterialGeometry';
import {tutorialStepAt, type TutorialStep} from './phoneTutorial';
import type {TimelineShot} from './types';

type RichMetric = {label: string; value: string; detail?: string};
type RichContent = {takeaway: string; items?: string[]; supporting_items?: string[]; metric?: RichMetric; numeric_items?: string[]};
type NumericItem = {label: string; value: number; unit: string; display: string};

const propsOf = (shot: TimelineShot) => shot.props as Record<string, unknown>;
const textArray = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const isVideo = (src: string | null | undefined) => Boolean(src && /\.mp4$/i.test(src));
const contentOf = (shot: TimelineShot): RichContent => {
  const raw = propsOf(shot).rich_content;
  const value = raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : {};
  const metric = value.metric && typeof value.metric === 'object' && !Array.isArray(value.metric) ? value.metric as Record<string, unknown> : null;
  return {
    takeaway: typeof value.takeaway === 'string' ? value.takeaway : '',
    items: textArray(value.items),
    supporting_items: textArray(value.supporting_items),
    numeric_items: textArray(value.numeric_items),
    ...(metric && typeof metric.label === 'string' && typeof metric.value === 'string'
      ? {metric: {label: metric.label, value: metric.value, ...(typeof metric.detail === 'string' ? {detail: metric.detail} : {})}}
      : {}),
  };
};

const metricParts = (metric?: RichMetric) => {
  const match = metric?.value.match(/^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u);
  return match ? {value: Number(match[1]), unit: match[2]} : null;
};
const numericItems = (content: RichContent): NumericItem[] => (content.numeric_items ?? []).map((item) => {
  const [label, value] = item.split(/[：:]/).map((piece) => piece.trim());
  const parsed = value?.match(/^([0-9]{1,5})([\u4e00-\u9fff]{1,2})$/u);
  return label && parsed ? {label, value: Number(parsed[1]), unit: parsed[2], display: value} : null;
}).filter((item): item is NumericItem => Boolean(item));
const chartPoints = (items: readonly NumericItem[], cumulative = false): ChartPoint[] => {
  let total = 0;
  return items.map((item, index) => {
    total += item.value;
    return {x: index, y: cumulative ? total : item.value, label: item.label};
  });
};
const splitItem = (item: string) => {
  const [title, ...rest] = item.split(/[：:]/);
  return {title: (title || item).trim(), body: (rest.join('：') || item).trim()};
};
const shortLabel = (item: string) => splitItem(item).title.slice(0, 8);
const focusSourceSizeOf = (shot: TimelineShot) => {
  const value = propsOf(shot).focus_source_size;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {width: 720, height: 1440};
  const size = value as Record<string, unknown>;
  return {
    width: typeof size.width === 'number' ? size.width : 720,
    height: typeof size.height === 'number' ? size.height : 1440,
  };
};

const Box = ({box, children, style}: {box: {x: number; y: number; width: number; height: number}; children: ReactNode; style?: CSSProperties}) =>
  <div style={{position: 'absolute', left: box.x, top: box.y, width: box.width, height: box.height, ...style}}>{children}</div>;
const Card = ({children, style}: {children: ReactNode; style?: CSSProperties}) =>
  <div style={{position: 'relative', width: '100%', height: '100%', overflow: 'hidden', borderRadius: 22,
    border: '1px solid rgba(148,163,184,0.24)', background: '#071426E6', boxSizing: 'border-box', ...style}}>{children}</div>;
const RevealAt = ({frame, children}: {frame: number; children: ReactNode}) =>
  <Sequence from={frame} layout="none">{children}</Sequence>;
const NativeStage = ({children, className = '', css = ''}: {children: ReactNode; className?: string; css?: string}) =>
  <IsolatedCard><style>{nativeCss}{css}</style><div className={`rich-material-native ${className}`}>{children}</div></IsolatedCard>;

const ScaledNativeStage = ({children, slotWidth, slotHeight, sourceWidth = 960, sourceHeight = 540, css = ''}: {
  children: ReactNode; slotWidth: number; slotHeight: number; sourceWidth?: number; sourceHeight?: number; css?: string;
}) => <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
  <div style={{position: 'absolute', left: (slotWidth - sourceWidth * Math.min(slotWidth / sourceWidth, slotHeight / sourceHeight)) / 2,
    top: (slotHeight - sourceHeight * Math.min(slotWidth / sourceWidth, slotHeight / sourceHeight)) / 2,
    width: sourceWidth, height: sourceHeight,
    transform: `scale(${Math.min(slotWidth / sourceWidth, slotHeight / sourceHeight)})`, transformOrigin: 'top left'}}>
    <NativeStage css={css}>{children}</NativeStage>
  </div>
</div>;

const WidthCroppedNativeStage = ({children, slotWidth, slotHeight, sourceWidth = 960, sourceHeight = 540, css = ''}: {
  children: ReactNode; slotWidth: number; slotHeight: number; sourceWidth?: number; sourceHeight?: number; css?: string;
}) => {
  const scale = slotWidth / sourceWidth;
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden'}}>
    <div style={{position: 'absolute', left: 0, top: (slotHeight - sourceHeight * scale) / 2,
      width: sourceWidth, height: sourceHeight, transform: `scale(${scale})`, transformOrigin: 'top left'}}>
      <NativeStage css={css}>{children}</NativeStage>
    </div>
  </div>;
};

const nativeCss = `
* { box-sizing: border-box; }
.rich-material-native { position: relative; width: 100%; height: 100%; overflow: hidden; background: transparent; }
.rich-material-native > div { background: transparent !important; }
.rich-material-native > div { background: transparent !important; }
.rich-material-native .host-wrap, .rich-material-native .host-badge, .rich-material-native .host { display: none !important; }
.rich-material-native .camera, .rich-material-native .world { position: absolute; inset: 0; }
.rich-material-native .page, .rich-material-native .shot { background: transparent !important; border-color: rgba(226,232,240,0.28) !important; }
.rich-material-native .sla-shot, .rich-material-native .sla-shot .sla-bar { background: #f8fafc !important; }
.rich-material-native .sla-status { color: #93c5fd !important; }
.rich-material-native .sla-lab, .rich-material-native .czp-lab { color: #f8fafc !important; font-size: 28px !important; }
.rich-material-native .sla-lab small { color: #CBD5E1 !important; font-size: 22px !important; }
.rich-material-native .scv-ttl { color: #f8fafc !important; font-size: 46px !important; }
.rich-material-native .scv-node rect { x: -96px; width: 192px; fill: #11283f !important; stroke: #7dd3fc !important; }
.rich-material-native .scv-node text { font-size: 26px !important; font-weight: 800 !important; }
.rich-material-native .scv-hub rect { x: -116px; width: 232px; }
.rich-material-native .scv-node text, .rich-material-native .scv-cap { fill: #f8fafc !important; }
.rich-material-native .say-line, .rich-material-native .wsc-sent { color: #f8fafc !important; }
`;

const MaterialImage = ({children}: {children: ReactNode}) =>
  <Box box={richMaterialGeometry.material}>
    <Card style={{background: '#020817'}}>
      {children}
      <div style={{position: 'absolute', inset: 0, boxShadow: 'inset 0 0 0 1px rgba(255,255,255,0.08)', pointerEvents: 'none'}} />
    </Card>
  </Box>;

const TextTitle = ({shot, content}: {shot: TimelineShot; content: RichContent}) =>
  <Box box={richMaterialGeometry.title} style={{overflow: 'hidden'}}>
    <div style={{position: 'absolute', left: 0, right: 0, top: 0, height: 122, overflow: 'hidden'}}>
      <TextReveal text={shot.title} fontSize={62} color={white} initialScale={1.04}
        fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} />
    </div>
    <div style={{position: 'absolute', left: 0, right: 0, bottom: 0, color: '#D6DFEC', fontSize: 30, lineHeight: 1.25,
      fontWeight: 650, textAlign: 'center'}}>{shot.body || content.takeaway}</div>
  </Box>;

const inkCompactCss = `
.rich-material-native .host-wrap { display: none !important; }
.rich-material-native .say { left: 44px !important; right: 44px !important; top: 50% !important; color: #f8fafc !important; }
.rich-material-native .say-line { font-size: 38px !important; line-height: 1.1 !important; white-space: nowrap !important; }
.rich-material-native #inkLayer { width: 100% !important; height: 100% !important; }
`;

const Emphasis = ({shot, content, setId}: {shot: TimelineShot; content: RichContent; setId: RichMaterialSetId}) =>
  <Box box={richMaterialGeometry.emphasis} style={{display: 'grid', placeItems: 'center', overflow: 'hidden'}}>
    {setId === 'A10'
      ? <WidthCroppedNativeStage slotWidth={richMaterialGeometry.emphasis.width} slotHeight={richMaterialGeometry.emphasis.height}
        css={inkCompactCss}>
        <InkUnderline title="核算后" wrong="只看单笔" right={content.takeaway} />
      </WidthCroppedNativeStage>
      : <TextHighlight before="" highlight={content.takeaway} after="" preset="underline" fontSize={54}
        fontWeight={860} baseColor={white} accentColor={shot.accent_color} fontFamily={productionFont}
        mode="dark" theme={{background: 'transparent', foreground: white}} />}
  </Box>;

const Identity = ({setId}: {setId: RichMaterialSetId}) =>
  <Box box={richMaterialGeometry.identity} style={{color: muted, fontSize: 24, fontWeight: 650}}>
    {setId === 'A09' ? '本地模拟App操作录屏 · 非实际产品'
      : setId === 'A10' ? '模拟账单 · 非真实消费记录'
        : 'AI生成/本地示意素材 · 非真实事件'}
  </Box>;

const SourceConvergePanel = ({content}: {content: RichContent}) =>
  <ScaledNativeStage slotWidth={467} slotHeight={206}><SourceConverge holdResult title="线索合并"
    sources={(content.items ?? content.supporting_items ?? []).slice(0, 3).map(shortLabel)}
    hub={content.takeaway} caption="" /></ScaledNativeStage>;

const InkUnderlinePanel = ({content}: {content: RichContent}) => {
  const wrong = shortLabel(content.items?.[0] ?? '表面');
  const longestLine = Math.max(`核对重点${wrong}，`.length, `真正要看的，是${content.takeaway}。`.length);
  const fontSize = Math.min(60, Math.floor(840 / longestLine));
  return <WidthCroppedNativeStage slotWidth={467} slotHeight={205}
    css={`${inkCompactCss}.rich-material-native .say-line { font-size: ${fontSize}px !important; line-height: 1.25 !important; }`}>
    <InkUnderline title="核对重点" wrong={wrong} right={content.takeaway} />
  </WidthCroppedNativeStage>;
};

const SupportBase = ({shot, content, setId}: {shot: TimelineShot; content: RichContent; setId: RichMaterialSetId}) => {
  const frame = useCurrentFrame();
  const phase = (referenceFrame: number) => Math.floor(referenceFrame * (shot.end_frame - shot.start_frame) / 540);
  const parsed = metricParts(content.metric);
  const nums = numericItems(content);
  const support = content.supporting_items ?? [];
  const items = content.items ?? [];
  if (setId === 'A10') {
    const maxValue = Math.max(parsed?.value ?? 1, ...nums.map((item) => item.value));
    return <Box box={richMaterialGeometry.support}>
      <div style={{display: 'grid', gridTemplateColumns: '300px 1fr', gridTemplateRows: '205px 205px', gap: 18, height: '100%'}}>
        <Card><RevealAt frame={phase(30)}><ScaledNativeStage slotWidth={300} slotHeight={205} sourceWidth={520} sourceHeight={300}>
          {parsed ? <StatCounter layout="portrait" value={parsed.value} suffix={parsed.unit} label={content.metric?.label}
            change="" period="" compactBox productionCompact fontFamily={productionFont} /> : null}
        </ScaledNativeStage></RevealAt></Card>
        <Card><RevealAt frame={phase(120)}><ChartAnimation layout="portrait" title="三笔累加" data={chartPoints(nums, true)}
          subtitle={content.metric?.detail ?? ''} maxValue={maxValue} unit={parsed?.unit ?? ''} compactBox fontFamily={productionFont} /></RevealAt></Card>
        <Card style={{display: 'grid', placeItems: 'center'}}><RevealAt frame={phase(210)}><TextBuild
          text={`${nums.map((item, index) => `${index ? '+' : ''}${item.display}`).join(' ')} =${content.metric?.value ?? ''}`}
          axis="y" gap={6} fontSize={32} color={white} fontWeight={820} fontFamily={productionFont}
          mode="dark" theme={{background: 'transparent', foreground: white}} /></RevealAt></Card>
        <Card><RevealAt frame={phase(300)}><ScaledNativeStage slotWidth={634} slotHeight={205} sourceWidth={760} sourceHeight={420}
          css=".rich-material-native svg text[text-anchor='end'] { font-size: 18px !important; }">
          <LineChart layout="portrait" title="逐笔金额" data={chartPoints(nums)} maxValue={maxValue} unit={parsed?.unit ?? ''} compactBox />
        </ScaledNativeStage></RevealAt></Card>
      </div>
    </Box>;
  }
  if (setId === 'A09') {
    const steps = shot.props.focus_steps as TutorialStep[];
    const activeIndex = Math.max(0, steps.findIndex((item) => frame >= item.start_frame && frame < item.end_frame));
    const activeCount = Math.max(1, activeIndex + 1);
    return <Box box={richMaterialGeometry.support}>
      <div style={{display: 'grid', gridTemplateColumns: '410px 250px 256px', gridTemplateRows: '205px 205px', gap: 18, height: '100%'}}>
        <Card style={{gridRow: '1 / span 2'}}><Freeze frame={activeIndex * 60 + 15}>
          <ProgressSteps compactSpacing layout="portrait" steps={items} title={`当前第 ${activeCount} 步`}
            secondsPerStep={2} largeCopy productionCompact compactBox fontFamily={productionFont} />
        </Freeze></Card>
        <Card><StatCounter layout="portrait" value={activeCount} suffix="步" label={content.metric?.label}
          change="" period={steps[activeIndex]?.instruction ?? content.metric?.detail ?? ''} productionCompact compactBox fontFamily={productionFont} /></Card>
        <Card style={{gridColumn: 2, gridRow: 2, display: 'grid', placeItems: 'center'}}><TextBuild text={support[activeIndex] ?? support.join(' ')} axis="y" fontSize={30}
          color={white} fontWeight={800} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Card>
        <Card style={{gridColumn: 3, gridRow: '1 / span 2', display: 'grid', placeItems: 'center'}}><TextSwap fromText={items[Math.max(0, activeIndex - 1)] ?? shot.title} toText={items[activeIndex] ?? content.takeaway}
          fontSize={42} color={white} fontFamily={productionFont} mode="dark" theme={{background: 'transparent', foreground: white}} /></Card>
      </div>
    </Box>;
  }
  const [left, right] = items.map((item, index) => ({title: splitItem(item).title, body: support[index] ?? splitItem(item).body}));
  const progressPanel = <ScaledNativeStage slotWidth={467} slotHeight={205} sourceWidth={700} sourceHeight={320}>
    <ProgressSteps compactSpacing layout="portrait" steps={support.length ? support : items} title="" secondsPerStep={1.25}
      largeCopy productionCompact compactBox fontFamily={productionFont} />
  </ScaledNativeStage>;
  const splitPanel = <ScaledNativeStage slotWidth={467} slotHeight={205} sourceWidth={700} sourceHeight={320}>
    <SplitScreen layout="portrait" leftTitle={left?.title} leftText={left?.body} rightTitle={right?.title}
      rightText={right?.body} largeCopy productionCompact compactBox />
  </ScaledNativeStage>;
  const quotePanel = <ScaledNativeStage slotWidth={467} slotHeight={205} sourceWidth={700} sourceHeight={320}>
    <QuoteCard layout="portrait" quote={content.takeaway} attribution="" transparentStage quoteFontSize={54}
      productionCompact instantReveal fontFamily={productionFont} />
  </ScaledNativeStage>;
  return <Box box={richMaterialGeometry.support}>
    <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gridTemplateRows: '205px 205px', gap: 18, height: '100%'}}>
      <Card>{setId === 'A11' ? quotePanel : setId === 'A08' || setId === 'A12' ? progressPanel : quotePanel}</Card>
      <Card><RevealAt frame={phase(90)}>{setId === 'A07' ? progressPanel : setId === 'A11' ? <InkUnderlinePanel content={content} /> : splitPanel}</RevealAt></Card>
      <Card style={{display: 'grid', placeItems: 'center'}}><RevealAt frame={phase(210)}><WordFlip prefix="" suffix="" words={items}
        fontSize={46} typeStart={0} cps={24} pause={8} cycle={28} loop={false}
        gradient={[shot.accent_color, white]} fontFamily={productionFont} mode="dark" /></RevealAt></Card>
      <Card><RevealAt frame={phase(330)}><SourceConvergePanel content={content} /></RevealAt></Card>
    </div>
  </Box>;
};

const FramedMedia = ({shot, setId}: {shot: TimelineShot; setId: RichMaterialSetId}) => {
  const frame = useCurrentFrame();
  const src = shot.asset_src ? staticFile(shot.asset_src) : '';
  const content = contentOf(shot);
  const nums = numericItems(content);
  const parsed = metricParts(content.metric);
  if (setId === 'A07') {
    return <MaterialImage><NativeStage className="slow-push"><SlowPushIn mediaSrc={src} mediaFit="cover" /></NativeStage></MaterialImage>;
  }
  if (setId === 'A10') {
    const rowYs = [116, 176, 236];
    const targets = [
      ...nums.slice(0, 3).map((_item, index) => ({x: 90, y: rowYs[index] ?? 116 + index * 60, w: 520, h: 44})),
      {x: 90, y: 318, w: 520, h: 56},
    ];
    const labels = [
      ...nums.slice(0, 3).map((item) => ({text: item.label, sub: item.display})),
      {text: content.metric?.label ?? '合计', sub: content.metric?.value ?? (parsed ? `${parsed.value}${parsed.unit}` : '')},
    ];
    const scan = <ScanlineAnnotate src={src} targets={targets} labels={labels}
      mediaStyle={{objectFit: 'cover', objectPosition: 'center center'}} />;
    return <MaterialImage>
      <div style={{position: 'absolute', left: 36, top: 86, width: 896, height: 610, borderRadius: 26,
        background: 'linear-gradient(180deg, rgba(15,23,42,0.95), rgba(2,6,23,0.98))', overflow: 'hidden',
        border: '1px solid rgba(147,197,253,0.22)'}}>
        <ScaledNativeStage slotWidth={896} slotHeight={610}>
          {frame > 150 ? <Freeze frame={150}>{scan}</Freeze> : scan}
        </ScaledNativeStage>
      </div>
      <div style={{position: 'absolute', left: 72, right: 72, bottom: 76, display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)', gap: 14}}>
        {labels.map((label) => <div key={label.text} style={{minHeight: 86, borderRadius: 18, padding: '14px 16px',
          background: 'rgba(15,23,42,0.82)', border: '1px solid rgba(148,163,184,0.25)', color: white}}>
          <div style={{fontSize: 24, fontWeight: 850}}>{label.text}</div>
          <div style={{fontSize: 28, fontWeight: 900, color: '#93C5FD', marginTop: 4}}>{label.sub}</div>
        </div>)}
      </div>
    </MaterialImage>;
  }
  if (setId === 'A11') {
    return <MaterialImage><NativeStage className="tilt-page" css={`
      .tilt-page .world { perspective: 1000px; perspective-origin: 50% 46%; }
      .tilt-page .camera { inset: auto; left: 50%; top: 50%; width: 792px; height: 594px;
        margin: -297px 0 0 -396px; transform-style: preserve-3d; }
      .tilt-page .page, .tilt-page .shadow { position: absolute; inset: 0; border-radius: 20px; overflow: hidden; }
      .tilt-page .shadow { background: #000; filter: blur(26px); }
    `}><Tilt3dPage mediaSrc={src} mediaFit="contain" /></NativeStage></MaterialImage>;
  }
  if (setId === 'A12') {
    return <MaterialImage><NativeStage><SlowPullReveal mediaSrc={src} mediaFit="contain" /></NativeStage></MaterialImage>;
  }
  return <MaterialImage>
    <div style={{position: 'absolute', left: 300, top: 42, width: 390, height: 810}}>
      <PhoneFrame variant="flat" entrance="rise" scale={1.25} showDynamicIsland={false}
        bezelColor="#0B1220" screenColor="#050A12">
        <Img src={src} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
      </PhoneFrame>
    </div>
  </MaterialImage>;
};

const A09Material = ({shot, content}: {shot: TimelineShot; content: RichContent}) => {
  const {fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const src = staticFile(shot.asset_src!);
  const steps = shot.props.focus_steps as TutorialStep[];
  const step = tutorialStepAt(steps, frame);
  const viewport = {width: 296, height: 632};
  const geometry = resolveVideoCropGeometry({viewportWidth: viewport.width, viewportHeight: viewport.height,
    metadata: focusSourceSizeOf(shot), crop: fullCrop, fit: 'contain'});
  const activeIndex = Math.max(0, steps.findIndex((item) => item === step));
  const ring = step ? {
    x: geometry.window.left + geometry.media.left + step.target.x * geometry.media.width,
    y: geometry.window.top + geometry.media.top + step.target.y * geometry.media.height,
    width: step.target.width * geometry.media.width,
    height: step.target.height * geometry.media.height,
  } : null;
  return <MaterialImage>
    <div style={{position: 'absolute', left: 248, top: 34, width: 472, height: 820}}>
      <PhoneFrame variant="flat" entrance="float" scale={1.18} showDynamicIsland={false}
        bezelColor="#0B1220" screenColor="#050A12">
        <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: '#020817'}}>
          <OffthreadVideo src={src} muted trimBefore={Math.round(Number(shot.props.start_seconds ?? 0) * fps)}
            trimAfter={shot.props.end_seconds === undefined ? undefined : Math.round(Number(shot.props.end_seconds) * fps)}
            style={{position: 'absolute', left: geometry.window.left + geometry.media.left, top: geometry.window.top + geometry.media.top,
              width: geometry.media.width, height: geometry.media.height, objectFit: 'fill'}} />
          {ring ? <svg aria-label={`重点：${step?.instruction}`} viewBox={`0 0 ${viewport.width} ${viewport.height}`}
            style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}>
            <rect x={Math.max(4, ring.x)} y={Math.max(4, ring.y)}
              width={Math.max(24, Math.min(viewport.width - 8 - Math.max(4, ring.x), ring.width))}
              height={Math.max(18, Math.min(viewport.height - 8 - Math.max(4, ring.y), ring.height))}
              rx={10} fill="rgba(251,146,60,0.08)" stroke="#FB923C" strokeWidth={4} />
          </svg> : null}
        </div>
      </PhoneFrame>
    </div>
    <div style={{position: 'absolute', left: 66, top: 86, width: 210, display: 'grid', gap: 14}}>
      <div style={{color: '#FB923C', fontSize: 22, fontWeight: 900}}>操作录屏</div>
      <FittedText text={step?.instruction ?? shot.title} width={210} height={84} fontSize={42} minFontSize={24} />
      <div style={{color: '#CBD5E1', fontSize: 24, lineHeight: 1.35, fontWeight: 700}}>{content.supporting_items?.[activeIndex]}</div>
    </div>
    <div style={{position: 'absolute', left: 720, right: 36, bottom: 72, display: 'grid', gap: 12}}>
      <div style={{position: 'relative', height: 64}}>
        <TextHighlight before="" highlight={step?.instruction ?? content.takeaway} after="" preset="marker"
          fontSize={38} baseColor={white} accentColor="#FB923C" fontFamily={productionFont}
          mode="dark" theme={{background: 'transparent', foreground: white}} />
      </div>
      <div style={{display: 'grid', gap: 10}}>
        {(content.items ?? []).map((item, index) => <div key={item} style={{height: 42, borderRadius: 999,
          display: 'grid', placeItems: 'center', color: index === activeIndex ? '#08111F' : '#D9E4F2',
          background: index === activeIndex ? '#FB923C' : '#172033', fontSize: 20, fontWeight: 800}}>{item}</div>)}
      </div>
    </div>
  </MaterialImage>;
};

export const RichMaterialScene = ({shot}: {shot: TimelineShot}) => {
  const {width, height} = useVideoConfig();
  const setId = String(propsOf(shot).component_set) as RichMaterialSetId;
  const content = contentOf(shot);
  const scale = Math.min(width / 1080, height / 1920);
  richMaterialNativeIdsForSet(setId);
  return <AbsoluteFill style={{background: 'radial-gradient(ellipse at 18% 4%, #15324A, transparent 46%), #050A12',
    color: white, overflow: 'hidden', fontFamily: productionFont}}>
    <div style={{position: 'absolute', width: 1080, height: 1920, transform: `scale(${scale})`, transformOrigin: 'top left'}}>
      {setId === 'A09' && isVideo(shot.asset_src) ? <A09Material shot={shot} content={content} /> : <FramedMedia shot={shot} setId={setId} />}
      <TextTitle shot={shot} content={content} />
      <SupportBase shot={shot} content={content} setId={setId} />
      <RevealAt frame={shot.layers?.find((layer) => layer.role === 'emphasis')?.start_frame ?? Math.floor((shot.end_frame - shot.start_frame) * 0.62)}>
        <Emphasis shot={shot} content={content} setId={setId} />
      </RevealAt>
      <Identity setId={setId} />
    </div>
  </AbsoluteFill>;
};
