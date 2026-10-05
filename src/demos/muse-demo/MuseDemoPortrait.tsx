import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Audio, interpolate, Loop, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {MuseDemoConfig, MusePortraitVisual} from './types';

const font = '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif';
const colors = {paper: '#F7F5F0', ink: '#111920', muted: '#66737A', purple: '#5A4FD6', green: '#1F8A5F', red: '#C74738', gold: '#C77B28'};
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const labelStyle: CSSProperties = {fontSize: 47, lineHeight: 1.26, color: colors.muted, fontWeight: 800};

const FadeIn = ({children, delay = 0, style}: {children: ReactNode; delay?: number; style?: CSSProperties}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const value = spring({frame: frame - delay, fps, config: {damping: 23, stiffness: 120}});
  return <div style={{...style, opacity: value, transform: `translateY(${(1 - value) * 34}px)`}}>{children}</div>;
};

const Badge = ({children, tone = 'dark'}: {children: ReactNode; tone?: 'dark' | 'light'}) => <div style={{
  display: 'inline-flex', alignItems: 'center', borderRadius: 999, padding: '13px 24px',
  background: tone === 'dark' ? '#111920E8' : '#FFFFFFD9', color: tone === 'dark' ? '#FFF' : colors.ink,
  fontSize: 32, fontWeight: 900, boxShadow: '0 18px 50px #00000014',
}}>{children}</div>;

const BigTitle = ({visual}: {visual: MusePortraitVisual}) => <FadeIn style={{position: 'absolute', top: 98, left: 64, right: 64}}>
  <div style={{fontSize: 74, lineHeight: 1.14, fontWeight: 950, color: colors.ink}}>{visual.title}</div>
  <div style={{...labelStyle, marginTop: 22}}>{visual.note}</div>
</FadeIn>;

const OfficialClip = ({visual, config, style}: {visual: MusePortraitVisual; config: MuseDemoConfig; style?: CSSProperties}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const clip = visual.clip ?? 'japan';
  const start = visual.start_seconds ?? 0;
  const end = visual.end_seconds ?? (clip === 'shopping' ? 25.5 : 24.3);
  const duration = Math.max(1, Math.round((end - start) * fps));
  const push = interpolate(frame, [0, duration], [1, 1.035], clamp);
  return <div style={{
    position: 'relative', overflow: 'hidden', borderRadius: 38, background: '#EEF0F3',
    width: 952, height: 1120, boxShadow: '0 30px 110px #14202B2A', ...style,
  }}>
    <Loop durationInFrames={duration}>
      <OffthreadVideo
        src={staticFile(config.clips[clip])}
        muted
        trimBefore={Math.round(start * fps)}
        style={{width: '100%', height: '100%', objectFit: 'contain', transform: `scale(${push})`}}
      />
    </Loop>
    <div style={{position: 'absolute', left: 28, top: 28}}><Badge>Meta 官方演示</Badge></div>
  </div>;
};

const ConceptCard = ({children, style}: {children: ReactNode; style?: CSSProperties}) => <FadeIn style={{
  position: 'absolute', left: 64, right: 64, top: 518, minHeight: 790, borderRadius: 44,
  background: '#FFF', boxShadow: '0 28px 90px #17222A18', padding: 50, ...style,
}}>{children}</FadeIn>;

const PlanVisual = () => {
  const steps = ['目标', '计划', '执行'];
  return <ConceptCard>
    <div style={{fontSize: 48, fontWeight: 950, marginBottom: 50}}>普通人的一句话，会被拆成步骤</div>
    {steps.map((step, index) => <FadeIn key={step} delay={index * 14} style={{
      display: 'flex', alignItems: 'center', gap: 26, padding: '34px 30px', marginBottom: 28,
      borderRadius: 28, background: index === 2 ? '#111920' : '#F2F1F8',
      color: index === 2 ? '#FFF' : colors.ink,
    }}>
      <div style={{width: 76, height: 76, borderRadius: 38, background: index === 2 ? colors.green : colors.purple, color: '#FFF', display: 'grid', placeItems: 'center', fontSize: 35, fontWeight: 950}}>{index + 1}</div>
      <div><div style={{fontSize: 52, fontWeight: 950}}>{step}</div><div style={{fontSize: 31, color: index === 2 ? '#C6D7CF' : colors.muted, marginTop: 8}}>{['你说想完成什么', '它列出行动路径', '再推进具体动作'][index]}</div></div>
    </FadeIn>)}
  </ConceptCard>;
};

const CloudVisual = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const x = interpolate(frame, [fps * 0.4, fps * 2.6], [115, 520], clamp);
  const y = interpolate(frame, [fps * 0.4, fps * 2.6], [250, 445], clamp);
  return <ConceptCard>
    <div style={{height: 70, borderRadius: 26, background: '#E6E9E8', display: 'flex', alignItems: 'center', padding: '0 24px', gap: 12}}>
      {['#E18E82', '#DBBD6D', '#8EBE92'].map(item => <div key={item} style={{width: 18, height: 18, borderRadius: 9, background: item}} />)}
      <div style={{marginLeft: 14, fontSize: 30, color: colors.muted}}>云端浏览器 · 示意</div>
    </div>
    {['打开网页', '填写信息', '等待确认'].map((item, index) => <FadeIn key={item} delay={index * 16 + 8} style={{display: 'flex', alignItems: 'center', gap: 26, marginTop: 42, padding: '36px 32px', borderRadius: 28, background: index === 2 ? '#FFF3DF' : '#F4F6F4'}}>
      <div style={{fontSize: 58, fontWeight: 950, color: index === 2 ? colors.gold : colors.green}}>0{index + 1}</div>
      <div style={{fontSize: 48, fontWeight: 950}}>{item}</div>
    </FadeIn>)}
    <svg width="52" height="68" viewBox="0 0 38 48" style={{position: 'absolute', left: x, top: y, filter: 'drop-shadow(4px 6px 5px #0005)'}}>
      <path d="M3 2v37l10-10 8 16 7-4-8-16 15-1z" fill={colors.ink} stroke="#FFF" strokeWidth="2" />
    </svg>
  </ConceptCard>;
};

const BoundaryVisual = ({config, visual}: {config: MuseDemoConfig; visual: MusePortraitVisual}) => <div>
  <OfficialClip visual={visual} config={config} style={{position: 'absolute', left: 64, top: 474, width: 952, height: 1000}} />
  <FadeIn delay={18} style={{position: 'absolute', left: 102, right: 102, bottom: 248, background: '#111920ED', color: '#FFF', borderRadius: 34, padding: '34px 40px'}}>
    <div style={{fontSize: 58, lineHeight: 1.15, fontWeight: 950}}>购买前，由你确认</div>
    <div style={{fontSize: 34, lineHeight: 1.45, color: '#D8E1E2', marginTop: 20}}>能操作，不等于可以绕过你。</div>
  </FadeIn>
</div>;

const LimitationsVisual = () => <ConceptCard style={{background: '#111920', color: '#FFF'}}>
  <div style={{fontSize: 62, fontWeight: 950, lineHeight: 1.2}}>这不是万能按钮</div>
  <div style={{fontSize: 36, color: '#C9D4D8', lineHeight: 1.55, marginTop: 38}}>官方承认仍会犯错。这里展示的是官方材料和演示画面，不是本片的独立实测。</div>
  <div style={{display: 'grid', gap: 26, marginTop: 60}}>
    {['先限定权限', '关键动作确认', '最后检查结果'].map((item, index) => <FadeIn key={item} delay={index * 12} style={{fontSize: 48, fontWeight: 900, padding: '30px 34px', borderRadius: 28, background: '#FFFFFF14', border: '1px solid #FFFFFF21'}}>{item}</FadeIn>)}
  </div>
</ConceptCard>;

const ClosingVisual = () => <AbsoluteFill style={{background: '#111920', color: '#FFF'}}>
  <FadeIn style={{position: 'absolute', top: 360, left: 70, right: 70}}>
    <div style={{fontSize: 76, lineHeight: 1.16, fontWeight: 950}}>把执行交出去，<br />把判断留下</div>
    <div style={{fontSize: 39, lineHeight: 1.55, color: '#C8D5D3', marginTop: 44}}>对普通人来说，Muse 值得看的不是“会聊天”，而是它能不能可靠地接手一串麻烦事。</div>
  </FadeIn>
  <div style={{position: 'absolute', left: 70, right: 70, bottom: 330, display: 'flex', flexWrap: 'wrap', gap: 22}}>
    {['接手执行', '限定权限', '确认关键动作'].map(item => <Badge key={item} tone="light">{item}</Badge>)}
  </div>
  <div style={{position: 'absolute', left: 70, right: 70, bottom: 240, fontSize: 32, color: '#AEBEC0'}}>使用 Meta 官方素材与概念图解 · 未声称产品实测</div>
</AbsoluteFill>;

const VisualView = ({config, visual}: {config: MuseDemoConfig; visual: MusePortraitVisual}) => {
  if (visual.kind === 'closing') return <ClosingVisual />;
  return <AbsoluteFill style={{background: colors.paper, color: colors.ink}}>
    <BigTitle visual={visual} />
    {visual.kind === 'footage' && <OfficialClip visual={visual} config={config} style={{position: 'absolute', left: 64, top: 474}} />}
    {visual.kind === 'plan' && <PlanVisual />}
    {visual.kind === 'cloud' && <CloudVisual />}
    {visual.kind === 'boundary' && <BoundaryVisual config={config} visual={visual} />}
    {visual.kind === 'limitations' && <LimitationsVisual />}
  </AbsoluteFill>;
};

const fallbackVisual = (index: number, count: number): MusePortraitVisual => index === count - 1
  ? {kind: 'closing', title: '把执行交出去', note: '把判断留下'}
  : {kind: 'footage', title: '官方演示画面', note: '这只是演示，不是实测', clip: 'japan', start_seconds: 0, end_seconds: 8};

export const MuseDemoPortrait = ({config}: {config: MuseDemoConfig}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const nowMs = frame / fps * 1000;
  const caption = config.captions.find(item => nowMs >= item.start_ms && nowMs < item.end_ms);
  const activeIndex = config.segments.reduce((active, item, index) => nowMs >= item.start_ms ? index : active, 0);
  const isClosing = (config.segments[activeIndex]?.visual?.kind ?? '') === 'closing';
  return <AbsoluteFill style={{fontFamily: font, overflow: 'hidden'}}>
    {config.segments.map((segment, index) => {
      const from = index === 0 ? 0 : Math.round(segment.start_ms / 1000 * fps);
      const end = index === config.segments.length - 1 ? durationInFrames : Math.round(config.segments[index + 1].start_ms / 1000 * fps);
      return <Sequence key={segment.id} from={from} durationInFrames={Math.max(1, end - from)}>
        <VisualView config={config} visual={segment.visual ?? fallbackVisual(index, config.segments.length)} />
      </Sequence>;
    })}
    <div style={{position: 'absolute', top: 36, left: 64, right: 64, display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: isClosing ? '#E8F0F0' : colors.ink}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 14, fontSize: 35, fontWeight: 950}}><span style={{width: 14, height: 14, borderRadius: 7, background: colors.purple, display: 'inline-block'}} />MUSE</div>
      <div style={{fontSize: 28, color: isClosing ? '#AEBEC0' : colors.muted, fontWeight: 800}}>竖屏样片</div>
    </div>
    {caption && <div style={{position: 'absolute', left: 54, right: 54, bottom: 82, textAlign: 'center'}}>
      <span style={{display: 'inline-block', maxWidth: '100%', background: '#111920F2', color: '#FFF', borderRadius: 26, padding: '22px 32px', fontSize: 56, lineHeight: 1.28, fontWeight: 900}}>{caption.text}</span>
    </div>}
    <div style={{position: 'absolute', left: 0, bottom: 0, height: 8, width: `${(frame + 1) / durationInFrames * 100}%`, background: colors.purple}} />
    <Audio src={staticFile(config.audio_src)} />
  </AbsoluteFill>;
};
