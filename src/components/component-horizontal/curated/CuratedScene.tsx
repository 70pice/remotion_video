import type {CSSProperties, FC, ReactNode} from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';

export type CuratedVariant =
  | 'social-clip'
  | 'social-reel'
  | 'bar-chart-race'
  | 'kanban-move'
  | 'device-mockup-3d'
  | 'split-text-chars'
  | 'aurora-bg'
  | 'audio-wave-captions'
  | 'end-card'
  | 'glass-panel'
  | 'path-draw'
  | 'area-chart'
  | 'circular-progress'
  | 'animated-list'
  | 'notification-pop'
  | 'sound-wave'
  | 'text-highlight'
  | 'gallery-grid'
  | 'image-carousel'
  | 'image-zoom-reveal'
  | 'masonry-gallery'
  | 'photo-stack'
  | 'picture-in-picture'
  | 'polaroid-frame'
  | 'clock-wipe'
  | 'iris-transition'
  | 'pixel-candlestick-ohlc'
  | 'racing-chart'
  | 'kpi-counter'
  | 'glass-lower-third'
  | 'pixel-waterfall-cycle'
  | 'pencil-draw'
  | 'eye-reveal'
  | 'news-ticker'
  | 'product-spotlight';

export type CuratedSceneProps = {
  variant: CuratedVariant;
  layout?: 'landscape' | 'portrait';
  title: string;
  kicker: string;
  accent: string;
  secondary?: string;
};

export type CuratedDemoDefinition = Omit<CuratedSceneProps, 'layout'> & {
  id: string;
  name: string;
  slug: string;
  durationInFrames: number;
};

export type CuratedDemo = {
  id: string;
  name: string;
  slug: string;
  component: FC;
  width: number;
  height: number;
  durationInFrames: number;
  fps: 30;
};

const font = '"Inter", "Microsoft YaHei UI", Arial, sans-serif';
const ink = '#F7FBFF';
const muted = '#94A3B8';
const slate = '#0F172A';

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));
const mix = (frame: number, start: number, length: number) => clamp01((frame - start) / length);
const wave = (frame: number, index: number, amplitude = 1) =>
  (0.5 + Math.sin(frame * 0.13 + index * 0.72) * 0.5) * amplitude;

const makeBars = (count: number, frame: number) =>
  Array.from({length: count}, (_, index) => 0.24 + wave(frame, index, 0.68));

const TitleBlock: FC<{title: string; kicker: string; accent: string; unit: number; compact?: boolean}> = ({
  title,
  kicker,
  accent,
  unit,
  compact = false,
}) => <div style={{display: 'grid', gap: compact ? 8 * unit : 13 * unit}}>
  <div style={{display: 'flex', alignItems: 'center', gap: 12 * unit, color: muted,
    fontSize: (compact ? 17 : 21) * unit, fontWeight: 700, letterSpacing: 0}}>
    <span style={{width: 44 * unit, height: 4 * unit, borderRadius: 999, background: accent}} />
    {kicker}
  </div>
  <div style={{fontSize: (compact ? 43 : 62) * unit, lineHeight: 1.02, fontWeight: 850,
    color: ink, letterSpacing: 0, maxWidth: 760 * unit}}>
    {title}
  </div>
</div>;

const Shell: FC<{children: ReactNode; accent: string; unit: number; portrait: boolean}> = ({
  children,
  accent,
  unit,
  portrait,
}) => <AbsoluteFill style={{background: slate, color: ink, fontFamily: font, overflow: 'hidden'}}>
  <div style={{position: 'absolute', inset: 0,
    background: `radial-gradient(circle at 18% 14%, ${accent}42, transparent 30%),
      radial-gradient(circle at 88% 72%, #2DD4BF33, transparent 32%),
      linear-gradient(135deg, #08111F 0%, #172033 55%, #070B12 100%)`}} />
  <div style={{position: 'absolute', inset: portrait ? `${72 * unit}px ${58 * unit}px` : `${44 * unit}px ${58 * unit}px`,
    border: `1px solid ${accent}3D`, borderRadius: 28 * unit, boxShadow: 'inset 0 0 0 1px #FFFFFF0F'}} />
  {children}
</AbsoluteFill>;

const FlowDots: FC<{count: number; frame: number; accent: string; unit: number; style?: CSSProperties}> = ({
  count,
  frame,
  accent,
  unit,
  style,
}) => <div style={{display: 'flex', gap: 9 * unit, ...style}}>
  {Array.from({length: count}, (_, index) => {
    const active = wave(frame, index, 1);
    return <span key={index} style={{
      width: (10 + active * 22) * unit,
      height: 9 * unit,
      borderRadius: 999,
      background: active > 0.58 ? accent : '#CBD5E166',
      opacity: 0.45 + active * 0.55,
    }} />;
  })}
</div>;

const chartColors = ['#38BDF8', '#A3E635', '#F97316', '#F43F5E', '#FACC15'];

const ChartPanel: FC<{frame: number; accent: string; unit: number; mode?: 'area' | 'bars' | 'candles' | 'race'}> = ({
  frame,
  accent,
  unit,
  mode = 'bars',
}) => {
  const values = makeBars(mode === 'candles' ? 9 : 5, frame);
  if (mode === 'area') {
    const points = values.map((value, index) => `${index * 25},${100 - value * 78}`).join(' ');
    return <svg viewBox="0 0 100 100" style={{width: '100%', height: '100%', overflow: 'visible'}}>
      <defs>
        <linearGradient id="curated-area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.75" />
          <stop offset="100%" stopColor={accent} stopOpacity="0.04" />
        </linearGradient>
      </defs>
      <polygon points={`0,100 ${points} 100,100`} fill="url(#curated-area)" />
      <polyline points={points} fill="none" stroke={accent} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {values.map((value, index) => <circle key={index} cx={index * 25} cy={100 - value * 78} r="2.6" fill="#F8FAFC" />)}
    </svg>;
  }
  if (mode === 'candles') {
    return <div style={{height: '100%', display: 'grid', gridTemplateColumns: `repeat(${values.length}, 1fr)`, gap: 15 * unit,
      alignItems: 'center'}}>
      {values.map((value, index) => {
        const up = index % 3 !== 1;
        const body = (28 + value * 66) * unit;
        return <div key={index} style={{height: 230 * unit, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{position: 'relative', width: 18 * unit, height: '100%'}}>
            <span style={{position: 'absolute', left: '50%', top: (14 + index * 3) * unit,
              bottom: (24 + (8 - index) * 3) * unit, width: 2 * unit, background: up ? '#22C55E' : '#F43F5E'}} />
            <span style={{position: 'absolute', left: 0, top: (92 - value * 28) * unit,
              width: 18 * unit, height: body, borderRadius: 3 * unit,
              background: up ? '#22C55E' : '#F43F5E', boxShadow: `0 0 ${16 * unit}px ${up ? '#22C55E55' : '#F43F5E55'}`}} />
          </div>
        </div>;
      })}
    </div>;
  }
  const sorted = values.map((value, index) => ({label: ['A', 'B', 'C', 'D', 'E'][index], value}))
    .sort((a, b) => mode === 'race' ? b.value - a.value : 0);
  return <div style={{display: 'grid', gap: 16 * unit}}>
    {sorted.map((item, index) => <div key={item.label} style={{display: 'grid', gridTemplateColumns: `${64 * unit}px 1fr ${70 * unit}px`,
      alignItems: 'center', gap: 14 * unit, color: '#E5EEF8', fontSize: 22 * unit, fontWeight: 800}}>
      <span>{item.label}</span>
      <span style={{height: 24 * unit, borderRadius: 999, background: '#1F2A3B', overflow: 'hidden'}}>
        <span style={{display: 'block', height: '100%', width: `${Math.round(item.value * 100)}%`,
          borderRadius: 999, background: chartColors[index % chartColors.length]}} />
      </span>
      <span style={{textAlign: 'right'}}>{Math.round(item.value * 100)}</span>
    </div>)}
  </div>;
};

const PhoneCard: FC<{frame: number; accent: string; unit: number; portrait: boolean; title: string}> = ({
  frame,
  accent,
  unit,
  portrait,
  title,
}) => <div style={{position: 'relative', width: portrait ? 500 * unit : 300 * unit, height: portrait ? 850 * unit : 560 * unit,
  borderRadius: 42 * unit, padding: 12 * unit, background: '#020617', border: '1px solid #FFFFFF33',
  boxShadow: `0 ${30 * unit}px ${90 * unit}px #000A`, transform: portrait ? undefined : 'rotate(-4deg)'}}>
  <div style={{height: '100%', borderRadius: 32 * unit, overflow: 'hidden', position: 'relative',
    background: `linear-gradient(160deg, ${accent} 0%, #0F172A 42%, #101827 100%)`}}>
    <div style={{position: 'absolute', inset: 0, opacity: 0.22,
      background: 'repeating-linear-gradient(0deg, #fff 0 1px, transparent 1px 28px)'}} />
    <div style={{position: 'absolute', left: 22 * unit, right: 22 * unit, bottom: 34 * unit,
      display: 'grid', gap: 12 * unit}}>
      <FlowDots count={9} frame={frame} accent="#F8FAFC" unit={unit} />
      <div style={{fontSize: (portrait ? 36 : 24) * unit, lineHeight: 1.05, fontWeight: 860}}>{title}</div>
      <div style={{height: 42 * unit, borderRadius: 999, background: '#FFFFFFE8', color: '#0F172A',
        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 15 * unit, fontWeight: 850}}>
        Caption synced from material
      </div>
    </div>
  </div>
</div>;

const Gallery: FC<{frame: number; accent: string; unit: number; portrait: boolean; mode: 'grid' | 'carousel' | 'masonry' | 'stack' | 'polaroid' | 'zoom'}> = ({
  frame,
  accent,
  unit,
  portrait,
  mode,
}) => {
  const count = mode === 'masonry' ? 8 : mode === 'stack' || mode === 'polaroid' ? 5 : 6;
  return <div style={{position: 'relative', width: portrait ? 760 * unit : 690 * unit,
    height: portrait ? 930 * unit : 410 * unit}}>
    {Array.from({length: count}, (_, index) => {
      const revealed = mix(frame, index * 5, 18);
      const column = index % (portrait ? 2 : 3);
      const row = Math.floor(index / (portrait ? 2 : 3));
      const stacked = mode === 'stack' || mode === 'polaroid';
      const zoom = mode === 'zoom' ? 1 + mix(frame, 18, 70) * 0.14 : 1;
      const baseWidth = stacked ? 310 : portrait ? 330 : 210;
      const baseHeight = mode === 'masonry' ? [250, 350, 290, 400][index % 4] : stacked ? 220 : portrait ? 265 : 170;
      const left = stacked ? 190 + index * 36 : column * (portrait ? 380 : 238);
      const top = stacked ? 260 - index * 22 : row * (portrait ? 310 : 205);
      return <div key={index} style={{position: 'absolute', left: left * unit, top: top * unit,
        width: baseWidth * unit, height: baseHeight * unit, borderRadius: (mode === 'polaroid' ? 8 : 22) * unit,
        padding: mode === 'polaroid' ? 14 * unit : 0, background: mode === 'polaroid' ? '#F8FAFC' : undefined,
        transform: `translateY(${(1 - revealed) * 28 * unit}px) rotate(${stacked ? -9 + index * 5 : 0}deg) scale(${zoom})`,
        opacity: revealed, boxShadow: `0 ${20 * unit}px ${54 * unit}px #0008`, overflow: 'hidden'}}>
        <div style={{height: mode === 'polaroid' ? '82%' : '100%', borderRadius: (mode === 'polaroid' ? 5 : 22) * unit,
          background: `linear-gradient(135deg, ${chartColors[index % chartColors.length]} 0%, ${accent} 52%, #111827 100%)`}} />
        {mode === 'polaroid' ? <div style={{height: '18%', color: '#1E293B', fontSize: 16 * unit,
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800}}>scene {index + 1}</div> : null}
      </div>;
    })}
  </div>;
};

const ListPanel: FC<{frame: number; accent: string; unit: number; portrait: boolean; notification?: boolean}> = ({
  frame,
  accent,
  unit,
  portrait,
  notification = false,
}) => <div style={{display: 'grid', gap: 18 * unit, width: portrait ? 760 * unit : 590 * unit}}>
  {['hook', 'evidence', 'edit', 'publish'].map((item, index) => {
    const reveal = mix(frame, index * 10, 18);
    return <div key={item} style={{display: 'grid', gridTemplateColumns: `${(notification ? 58 : 44) * unit}px 1fr`,
      alignItems: 'center', gap: 18 * unit, padding: `${18 * unit}px ${22 * unit}px`, borderRadius: 22 * unit,
      background: notification ? '#F8FAFCEB' : '#101B2FDD', color: notification ? '#0F172A' : '#E5EEF8',
      opacity: reveal, transform: `translateX(${(1 - reveal) * (notification ? 60 : -44) * unit}px)`,
      boxShadow: `0 ${18 * unit}px ${50 * unit}px #0006`}}>
      <span style={{width: 44 * unit, height: 44 * unit, borderRadius: 999, background: accent,
        color: '#08111F', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 900}}>
        {index + 1}
      </span>
      <span style={{fontSize: (portrait ? 30 : 23) * unit, fontWeight: 820}}>{item}</span>
    </div>;
  })}
</div>;

const CircularProgress: FC<{frame: number; accent: string; unit: number; value?: number}> = ({
  frame,
  accent,
  unit,
  value = 0.78,
}) => {
  const progress = mix(frame, 10, 58) * value;
  const radius = 118;
  const circumference = Math.PI * 2 * radius;
  return <svg viewBox="0 0 300 300" style={{width: 300 * unit, height: 300 * unit}}>
    <circle cx="150" cy="150" r={radius} fill="none" stroke="#334155" strokeWidth="24" />
    <circle cx="150" cy="150" r={radius} fill="none" stroke={accent} strokeWidth="24" strokeLinecap="round"
      strokeDasharray={circumference} strokeDashoffset={circumference * (1 - progress)}
      transform="rotate(-90 150 150)" />
    <text x="150" y="166" textAnchor="middle" fill="#F8FAFC" fontFamily={font} fontSize="52" fontWeight="850">
      {Math.round(progress * 100)}%
    </text>
  </svg>;
};

const RevealMask: FC<{frame: number; unit: number; mode: 'clock' | 'iris' | 'eye'; accent: string}> = ({
  frame,
  unit,
  mode,
  accent,
}) => {
  const progress = mix(frame, 12, 60);
  if (mode === 'iris' || mode === 'eye') {
    return <div style={{position: 'relative', width: 600 * unit, height: 390 * unit, borderRadius: mode === 'eye' ? '50%' : 30 * unit,
      overflow: 'hidden', border: `2px solid ${accent}`, background: '#07101F'}}>
      <div style={{position: 'absolute', inset: `${(1 - progress) * 46}%`, borderRadius: mode === 'eye' ? '50%' : 24 * unit,
        background: `linear-gradient(135deg, ${accent}, #38BDF8 56%, #111827)`, boxShadow: `0 0 ${90 * unit}px ${accent}`}} />
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 36 * unit, fontWeight: 860}}>reveal</div>
    </div>;
  }
  return <div style={{position: 'relative', width: 600 * unit, height: 390 * unit, borderRadius: 30 * unit,
    overflow: 'hidden', background: '#07101F', border: `1px solid ${accent}88`}}>
    <div style={{position: 'absolute', inset: 0,
      background: `conic-gradient(from -90deg, ${accent} ${progress * 360}deg, #101827 ${progress * 360}deg)`}} />
    <div style={{position: 'absolute', inset: 30 * unit, borderRadius: 24 * unit, background: '#07101FE8',
      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 34 * unit, fontWeight: 850}}>
      clock wipe
    </div>
  </div>;
};

export const CuratedScene: FC<CuratedSceneProps> = ({variant, layout = 'landscape', title, kicker, accent, secondary}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const portrait = layout === 'portrait';
  const unit = Math.min(width / (portrait ? 1080 : 1280), height / (portrait ? 1920 : 720));
  const left = portrait ? 104 * unit : 92 * unit;
  const top = portrait ? 150 * unit : 86 * unit;
  const heroTop = portrait ? 590 * unit : 210 * unit;
  const panelStyle: CSSProperties = {position: 'absolute', left, top, right: left};
  const commonTitle = <div style={panelStyle}><TitleBlock title={title} kicker={kicker} accent={accent} unit={unit} compact={portrait} /></div>;

  if (variant === 'social-clip' || variant === 'social-reel') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', right: portrait ? 285 * unit : 150 * unit, top: heroTop}}>
        <PhoneCard frame={frame} accent={accent} unit={unit} portrait={portrait} title={secondary || title} />
      </div>
    </Shell>;
  }

  if (variant === 'bar-chart-race' || variant === 'racing-chart') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop,
        padding: 30 * unit, borderRadius: 28 * unit, background: '#07101FDD', border: '1px solid #FFFFFF1F'}}>
        <ChartPanel frame={frame} accent={accent} unit={unit} mode="race" />
      </div>
    </Shell>;
  }

  if (variant === 'area-chart' || variant === 'pixel-candlestick-ohlc') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop,
        height: portrait ? 690 * unit : 360 * unit, padding: 34 * unit, borderRadius: 28 * unit,
        background: '#07101FDD', border: '1px solid #FFFFFF1F'}}>
        <ChartPanel frame={frame} accent={accent} unit={unit} mode={variant === 'area-chart' ? 'area' : 'candles'} />
      </div>
    </Shell>;
  }

  if (variant === 'circular-progress' || variant === 'kpi-counter') {
    const progress = Math.round(mix(frame, 5, 62) * 860);
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop, display: 'flex',
        alignItems: 'center', justifyContent: 'space-around', gap: 36 * unit}}>
        <CircularProgress frame={frame} accent={accent} unit={unit} value={variant === 'kpi-counter' ? 0.86 : 0.72} />
        <div style={{fontSize: (portrait ? 78 : 68) * unit, fontWeight: 900, color: ink}}>
          {variant === 'kpi-counter' ? progress.toLocaleString('en-US') : '+72%'}
          <div style={{fontSize: 22 * unit, color: muted, fontWeight: 700, marginTop: 8 * unit}}>
            {secondary || 'verified input'}
          </div>
        </div>
      </div>
    </Shell>;
  }

  if (variant === 'kanban-move') {
    const columns = ['Todo', 'Doing', 'Done'];
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop, display: 'grid',
        gridTemplateColumns: portrait ? '1fr' : 'repeat(3, 1fr)', gap: 18 * unit}}>
        {columns.map((column, columnIndex) => <div key={column} style={{minHeight: portrait ? 205 * unit : 280 * unit,
          borderRadius: 24 * unit, background: '#F8FAFC14', border: '1px solid #FFFFFF20', padding: 18 * unit}}>
          <div style={{fontSize: 20 * unit, fontWeight: 850, color: muted, marginBottom: 16 * unit}}>{column}</div>
          {[0, 1, 2].map((card) => {
            const moving = columnIndex === 1 && card === 1;
            return <div key={card} style={{height: 58 * unit, borderRadius: 16 * unit, background: moving ? accent : '#E5EEF8',
              marginBottom: 12 * unit, opacity: mix(frame, card * 6, 18),
              transform: moving ? `translateX(${Math.sin(frame / 22) * 42 * unit}px)` : undefined}} />;
          })}
        </div>)}
      </div>
    </Shell>;
  }

  if (variant === 'device-mockup-3d' || variant === 'product-spotlight') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left: portrait ? 160 * unit : 520 * unit, top: heroTop,
        width: portrait ? 760 * unit : 560 * unit, height: portrait ? 680 * unit : 330 * unit,
        borderRadius: 34 * unit, background: '#E5EEF8', padding: 18 * unit,
        transform: `perspective(${900 * unit}px) rotateY(${-16 + Math.sin(frame / 38) * 5}deg) rotateX(6deg)`,
        boxShadow: `0 ${34 * unit}px ${90 * unit}px #000A`}}>
        <div style={{height: '100%', borderRadius: 22 * unit, background: '#0F172A', padding: 22 * unit,
          display: 'grid', gridTemplateRows: `${42 * unit}px 1fr`, gap: 18 * unit}}>
          <div style={{display: 'flex', gap: 9 * unit}}>{['#F87171', '#FACC15', '#34D399'].map((color) =>
            <span key={color} style={{width: 13 * unit, height: 13 * unit, borderRadius: 999, background: color}} />)}</div>
          <div style={{display: 'grid', gridTemplateColumns: '0.8fr 1.2fr', gap: 18 * unit}}>
            <div style={{borderRadius: 18 * unit, background: `linear-gradient(135deg, ${accent}, #38BDF8)`}} />
            <div style={{display: 'grid', gap: 14 * unit, alignContent: 'center'}}>
              {[0.85, 0.64, 0.92, 0.48].map((value, index) =>
                <span key={index} style={{height: 16 * unit, width: `${value * 100}%`, borderRadius: 999, background: '#CBD5E1'}} />)}
            </div>
          </div>
        </div>
      </div>
    </Shell>;
  }

  if (variant === 'split-text-chars' || variant === 'text-highlight') {
    const words = title.split('');
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      <div style={{position: 'absolute', left, right: left, top: portrait ? 450 * unit : 230 * unit,
        display: 'flex', flexWrap: 'wrap', gap: 5 * unit, alignItems: 'center', justifyContent: 'center'}}>
        {words.map((character, index) => {
          const reveal = mix(frame, index * 2, 16);
          return <span key={`${character}-${index}`} style={{display: 'inline-block',
            fontSize: (portrait ? 78 : 74) * unit, lineHeight: 1, fontWeight: 900, letterSpacing: 0,
            color: index % 4 === 1 ? accent : ink, transform: `translateY(${(1 - reveal) * 48 * unit}px)`,
            opacity: reveal, textShadow: index % 4 === 1 ? `0 0 ${30 * unit}px ${accent}` : undefined}}>
            {character === ' ' ? '\u00A0' : character}
          </span>;
        })}
      </div>
      <div style={{position: 'absolute', left, right: left, bottom: portrait ? 430 * unit : 120 * unit,
        height: 5 * unit, background: `linear-gradient(90deg, transparent, ${accent}, transparent)`}} />
    </Shell>;
  }

  if (variant === 'aurora-bg') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      <div style={{position: 'absolute', inset: 0, filter: `blur(${36 * unit}px)`, opacity: 0.78}}>
        {[accent, '#22C55E', '#F97316', '#38BDF8'].map((color, index) =>
          <div key={color} style={{position: 'absolute', left: `${18 + index * 19 + Math.sin(frame / 45 + index) * 7}%`,
            top: `${22 + Math.cos(frame / 50 + index) * 18}%`, width: portrait ? 390 * unit : 330 * unit,
            height: portrait ? 560 * unit : 260 * unit, borderRadius: '48%', background: color, opacity: 0.42}} />)}
      </div>
      <div style={{position: 'absolute', left, right: left, top: portrait ? 650 * unit : 250 * unit,
        textAlign: 'center'}}><TitleBlock title={title} kicker={kicker} accent={accent} unit={unit} /></div>
    </Shell>;
  }

  if (variant === 'audio-wave-captions' || variant === 'sound-wave') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop + (portrait ? 70 * unit : 20 * unit),
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 * unit}}>
        {makeBars(44, frame).map((value, index) => <span key={index} style={{width: 8 * unit,
          height: (28 + value * (portrait ? 220 : 150)) * unit, borderRadius: 999,
          background: index % 5 === 0 ? accent : '#E2E8F0'}} />)}
      </div>
      <div style={{position: 'absolute', left: left + 60 * unit, right: left + 60 * unit,
        bottom: portrait ? 390 * unit : 88 * unit, padding: `${18 * unit}px ${26 * unit}px`, borderRadius: 18 * unit,
        background: '#F8FAFCEB', color: '#0F172A', fontSize: (portrait ? 34 : 28) * unit, fontWeight: 850,
        textAlign: 'center'}}>{secondary || 'captions follow the voice'}</div>
    </Shell>;
  }

  if (variant === 'end-card' || variant === 'glass-panel' || variant === 'glass-lower-third') {
    const reveal = mix(frame, 8, 52);
    const sweep = ((frame * 3) % 160) / 160;
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      <div style={{position: 'absolute', left, right: left, top: variant === 'glass-lower-third'
        ? (portrait ? 1180 : 455) * unit : heroTop, padding: 34 * unit, borderRadius: 30 * unit,
        background: '#FFFFFF18', border: '1px solid #FFFFFF3D', backdropFilter: 'blur(18px)',
        boxShadow: `0 ${24 * unit}px ${80 * unit}px #0008`,
        opacity: 0.7 + reveal * 0.3, transform: `translateY(${(1 - reveal) * 30 * unit}px)`}}>
        <div style={{position: 'absolute', inset: 0, pointerEvents: 'none',
          background: `linear-gradient(105deg, transparent ${Math.max(0, sweep * 100 - 26)}%, #FFFFFF24 ${sweep * 100}%, transparent ${Math.min(100, sweep * 100 + 26)}%)`,
          opacity: 0.72}} />
        <TitleBlock title={title} kicker={kicker} accent={accent} unit={unit} compact={variant === 'glass-lower-third'} />
        <div style={{marginTop: 26 * unit, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 18 * unit}}>
          {[secondary || 'source', 'next action'].map((item) =>
            <div key={item} style={{padding: 20 * unit, borderRadius: 18 * unit, background: '#07101FA8',
              fontSize: 22 * unit, color: '#DCE7F3', fontWeight: 750}}>{item}</div>)}
        </div>
        <div style={{height: 5 * unit, borderRadius: 999, marginTop: 24 * unit,
          background: `linear-gradient(90deg, ${accent} ${Math.round((0.2 + reveal * 0.8) * 100)}%, #FFFFFF24 0)`}} />
      </div>
    </Shell>;
  }

  if (variant === 'path-draw' || variant === 'pencil-draw') {
    const dash = 610 * (1 - mix(frame, 8, 76));
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <svg viewBox="0 0 680 360" style={{position: 'absolute', left, top: heroTop,
        width: portrait ? 840 * unit : 700 * unit, height: portrait ? 500 * unit : 360 * unit}}>
        <path d="M42 280 C140 96 216 315 336 158 C438 23 500 255 628 82" fill="none"
          stroke={accent} strokeWidth="14" strokeLinecap="round" strokeDasharray="610" strokeDashoffset={dash} />
        <path d="M56 286 C156 120 214 306 330 170 C426 54 514 246 614 102" fill="none"
          stroke="#F8FAFC" strokeWidth="3" strokeLinecap="round" strokeDasharray="610" strokeDashoffset={dash} opacity="0.72" />
      </svg>
    </Shell>;
  }

  if (variant === 'animated-list' || variant === 'notification-pop') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left: portrait ? 160 * unit : 590 * unit, top: heroTop}}>
        <ListPanel frame={frame} accent={accent} unit={unit} portrait={portrait} notification={variant === 'notification-pop'} />
      </div>
    </Shell>;
  }

  if (variant === 'gallery-grid' || variant === 'image-carousel' || variant === 'image-zoom-reveal' ||
    variant === 'masonry-gallery' || variant === 'photo-stack' || variant === 'polaroid-frame') {
    const mode = variant === 'gallery-grid' ? 'grid' : variant === 'image-carousel' ? 'carousel' :
      variant === 'image-zoom-reveal' ? 'zoom' : variant === 'masonry-gallery' ? 'masonry' :
        variant === 'photo-stack' ? 'stack' : 'polaroid';
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left: portrait ? 130 * unit : 520 * unit, top: heroTop - (portrait ? 30 * unit : 35 * unit)}}>
        <Gallery frame={frame} accent={accent} unit={unit} portrait={portrait} mode={mode} />
      </div>
    </Shell>;
  }

  if (variant === 'picture-in-picture') {
    const pan = Math.sin(frame / 28);
    const pulse = mix(frame, 10, 90);
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop, height: portrait ? 720 * unit : 370 * unit,
        borderRadius: 30 * unit, overflow: 'hidden', background: `linear-gradient(135deg, ${accent}, #0F172A 68%)`,
        border: '1px solid #FFFFFF22'}}>
        <div style={{position: 'absolute', inset: 0,
          background: `radial-gradient(circle at ${46 + pan * 14}% ${38 + Math.cos(frame / 34) * 10}%, #FFFFFF55, transparent 34%),
            linear-gradient(120deg, transparent, #FFFFFF1C ${42 + pulse * 32}%, transparent ${58 + pulse * 22}%)`,
          transform: `scale(${1.02 + pulse * 0.04})`, opacity: 0.75}} />
        <div style={{position: 'absolute', left: 38 * unit, bottom: 42 * unit, right: portrait ? 410 * unit : 370 * unit}}>
          {[0.95, 0.72, 0.58].map((value, index) => <span key={index} style={{display: 'block',
            height: 16 * unit, width: `${(value * (0.7 + mix(frame, index * 12, 70) * 0.3)) * 100}%`,
            borderRadius: 999, background: index === 0 ? '#F8FAFC' : '#DCE7F3A8',
            marginBottom: 13 * unit}} />)}
        </div>
        <div style={{position: 'absolute', right: 34 * unit, bottom: 34 * unit, width: portrait ? 330 * unit : 280 * unit,
          height: portrait ? 220 * unit : 158 * unit, borderRadius: 22 * unit, background: '#F8FAFC',
          boxShadow: `0 ${18 * unit}px ${50 * unit}px #0008`, display: 'grid', placeItems: 'center',
          color: '#0F172A', fontSize: 24 * unit, fontWeight: 850,
          transform: `translateY(${(1 - pulse) * 34 * unit}px) scale(${0.96 + pulse * 0.04})`}}>
          <span style={{width: 74 * unit, height: 74 * unit, borderRadius: 999, background: accent,
            boxShadow: `0 0 0 ${8 * unit}px #0F172A14`, display: 'grid', placeItems: 'center', color: '#0F172A'}}>
            {Math.round(76 + pulse * 18)}%
          </span>
        </div>
      </div>
    </Shell>;
  }

  if (variant === 'clock-wipe' || variant === 'iris-transition' || variant === 'eye-reveal') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left: portrait ? 230 * unit : 520 * unit, top: heroTop}}>
        <RevealMask frame={frame} unit={unit} accent={accent}
          mode={variant === 'clock-wipe' ? 'clock' : variant === 'iris-transition' ? 'iris' : 'eye'} />
      </div>
    </Shell>;
  }

  if (variant === 'pixel-waterfall-cycle') {
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left, right: left, top: heroTop, display: 'grid',
        gridTemplateColumns: 'repeat(18, 1fr)', gap: 5 * unit}}>
        {Array.from({length: 162}, (_, index) => <span key={index} style={{height: (portrait ? 46 : 24) * unit,
          borderRadius: 4 * unit, background: chartColors[index % chartColors.length],
          opacity: 0.2 + wave(frame, index, 0.8),
          transform: `translateY(${Math.sin(frame / 10 + index) * 12 * unit}px)`}} />)}
      </div>
    </Shell>;
  }

  if (variant === 'news-ticker') {
    const offset = -((frame * 6) % 520) * unit;
    return <Shell accent={accent} unit={unit} portrait={portrait}>
      {commonTitle}
      <div style={{position: 'absolute', left: 0, right: 0, bottom: portrait ? 420 * unit : 92 * unit,
        height: 86 * unit, background: '#F8FAFC', color: '#0F172A', overflow: 'hidden',
        display: 'flex', alignItems: 'center', borderTop: `${8 * unit}px solid ${accent}`}}>
        <div style={{whiteSpace: 'nowrap', transform: `translateX(${offset}px)`, fontSize: 31 * unit, fontWeight: 900}}>
          {title} · {secondary || 'verified updates'} · timeline ready · material slots · {title} ·
        </div>
      </div>
    </Shell>;
  }

  return <Shell accent={accent} unit={unit} portrait={portrait}>
    {commonTitle}
    <div style={{position: 'absolute', left, right: left, top: heroTop,
      padding: 34 * unit, borderRadius: 28 * unit, background: '#07101FDD'}}>
      <ChartPanel frame={frame} accent={accent} unit={unit} />
    </div>
  </Shell>;
};

export const makeCuratedDemos = (
  definitions: CuratedDemoDefinition[],
  layout: 'landscape' | 'portrait',
  size: {width: number; height: number},
): CuratedDemo[] => definitions.map((definition) => {
  const Component: FC = () => <CuratedScene {...definition} layout={layout} />;
  return {
    id: definition.id,
    name: definition.name,
    slug: definition.slug,
    component: Component,
    width: size.width,
    height: size.height,
    durationInFrames: definition.durationInFrames,
    fps: 30,
  };
});
