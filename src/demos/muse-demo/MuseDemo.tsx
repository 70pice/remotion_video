import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Audio, Freeze, interpolate, Loop, OffthreadVideo, Sequence, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {MuseDemoConfig} from './types';

const colors = {paper: '#F4F3EF', ink: '#17222A', subtle: '#66737A', purple: '#6857DB', mint: '#B2F4CC', orange: '#F3AD74'};
const font = '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif';
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

type Scene = 'hook' | 'travel' | 'contrast' | 'plan' | 'cloud' | 'shopping' | 'control' | 'closing';

// 选择画面只看实际文案；段落时间始终使用配音返回的时间。
export const sceneFor = (text: string, index: number, count: number): Scene => {
  if (index === 0) return 'hook';
  if (index === count - 1) return 'closing';
  if (/确认|敏感|权限|发邮件|发送邮件|购买前|付款前/.test(text)) return 'control';
  if (/云端|虚拟机|浏览器|电脑/.test(text)) return 'cloud';
  if (/购物|商品|挑选|比较价格|婴儿车/.test(text)) return 'shopping';
  if (/拆|计划|分成|步骤|目标/.test(text)) return 'plan';
  if (/旅行|日本|订餐|行程|机票|餐厅/.test(text)) return 'travel';
  if (/回答|执行|聊天|办事|助手/.test(text)) return 'contrast';
  return (['travel', 'contrast', 'plan', 'cloud', 'shopping', 'control'] as const)[(index - 1) % 6];
};

const Pill = ({children, dark = false}: {children: ReactNode; dark?: boolean}) => <div style={{display: 'inline-flex', alignItems: 'center', gap: 12, fontSize: 22, fontWeight: 700, border: `1px solid ${dark ? '#5A6571' : '#C9CFCC'}`, borderRadius: 40, padding: '12px 23px', color: dark ? '#D4DEE5' : colors.subtle}}>{children}</div>;

const FadeIn = ({children, delay = 0, style}: {children: ReactNode; delay?: number; style?: CSSProperties}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = spring({frame: frame - delay, fps, config: {damping: 20, stiffness: 100}});
  return <div style={{...style, opacity: reveal, transform: `translateY(${(1 - reveal) * 35}px)`}}>{children}</div>;
};

const Icon = ({kind, color = colors.ink, size = 62}: {kind: 'arrow' | 'check' | 'browser' | 'person' | 'plane' | 'lock'; color?: string; size?: number}) => <svg width={size} height={size} viewBox="0 0 64 64" fill="none" stroke={color} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round">
  {kind === 'arrow' && <><path d="M10 32h40M37 19l13 13-13 13" /></>}
  {kind === 'check' && <><circle cx="32" cy="32" r="24" /><path d="m20 32 8 9 17-20" /></>}
  {kind === 'browser' && <><rect x="8" y="12" width="48" height="40" rx="6" /><path d="M8 24h48M17 18h1M24 18h1M31 18h1M20 36l-6 5 6 5M44 36l6 5-6 5M35 32l-6 17" /></>}
  {kind === 'person' && <><circle cx="32" cy="19" r="10" /><path d="M12 55v-7c0-10 8-16 20-16s20 6 20 16v7" /></>}
  {kind === 'plane' && <path d="m8 35 20-7V13c0-7 8-7 8 0v15l20 7v8l-20-3v10l8 5H20l8-5V40L8 43z" />}
  {kind === 'lock' && <><rect x="13" y="28" width="38" height="28" rx="6" /><path d="M21 28V19a11 11 0 0 1 22 0v9M32 40v7" /></>}
</svg>;

const Heading = ({kicker, children, detail, light = false}: {kicker: string; children: ReactNode; detail?: string; light?: boolean}) => <FadeIn>
  <div style={{color: light ? colors.mint : colors.purple, fontSize: 24, fontWeight: 800, letterSpacing: 2, marginBottom: 24}}>{kicker}</div>
  <div style={{fontSize: 78, fontWeight: 900, letterSpacing: -3, lineHeight: 1.22, color: light ? '#F9F9F5' : colors.ink}}>{children}</div>
  {detail && <div style={{marginTop: 30, fontSize: 29, lineHeight: 1.6, color: light ? '#B6C6D0' : colors.subtle}}>{detail}</div>}
</FadeIn>;

const OfficialVideo = ({src, offset = 0, freezeAt, style}: {src: string; offset?: number; freezeAt?: number; style?: CSSProperties}) => {
  const {fps} = useVideoConfig();
  const sourceDuration = src.toLowerCase().includes('shopping') ? 25.73 : 24.57;
  const video = <OffthreadVideo src={staticFile(src)} muted trimBefore={Math.round(offset * fps)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />;
  return <div style={{position: 'relative', overflow: 'hidden', borderRadius: 32, background: '#F0F1F6', boxShadow: '0 24px 80px #11213718', ...style}}>
    {freezeAt === undefined ? <Loop durationInFrames={Math.floor((sourceDuration - offset) * fps)}>{video}</Loop> : <Freeze frame={Math.round((freezeAt - offset) * fps)}>{video}</Freeze>}
    <div style={{position: 'absolute', top: 22, left: 24, borderRadius: 30, padding: '10px 17px', background: '#17222AEA', color: '#FFF', fontSize: 19, fontWeight: 700}}>Meta 官方演示{freezeAt === undefined ? '' : ' · 实帧'}</div>
  </div>;
};

const Hook = ({config}: {config: MuseDemoConfig}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const push = interpolate(frame, [0, fps * 8], [1, 1.035], clamp);
  return <>
    <div style={{position: 'absolute', left: 108, top: 225, width: 870}}><Heading kicker="一个普通人的问题" detail="把目标交给 AI，事情会怎么往前走？">AI 能替你<br /><span style={{color: colors.purple}}>把事办完吗？</span></Heading>
      <FadeIn delay={18} style={{marginTop: 54, display: 'flex', gap: 15}}><Pill>计划旅行</Pill><Pill>比较商品</Pill><Pill>你来确认</Pill></FadeIn>
    </div>
    <FadeIn delay={9} style={{position: 'absolute', right: 100, top: 150, width: 805, height: 736}}>
      <Sequence durationInFrames={Math.round(fps * 4.1)}><OfficialVideo src={config.clips.japan} offset={6} style={{width: '100%', height: '100%', transform: `scale(${push})`}} /></Sequence>
      <Sequence from={Math.round(fps * 4.1)}><OfficialVideo src={config.clips.shopping} offset={3} style={{width: '100%', height: '100%', transform: `scale(${push})`}} /></Sequence>
    </FadeIn>
    <div style={{position: 'absolute', bottom: 185, left: 112, color: colors.subtle, fontSize: 22}}>MUSE / AI 助手科普样片</div>
  </>;
};

const Travel = ({config}: {config: MuseDemoConfig}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const items = [{title: '安排旅行', note: '行程与目的地', icon: 'plane' as const}, {title: '接着办事', note: '预订与后续事项', icon: 'check' as const}];
  return <>
    <OfficialVideo src={config.clips.japan} offset={7} style={{position: 'absolute', left: 95, top: 147, width: 825, height: 750}} />
    <div style={{position: 'absolute', left: 1000, top: 190, width: 815}}><Heading kicker="先看真实画面" detail="官网演示把多步事项接在同一次对话里。">从一句话<br />到一串事情</Heading>
      {items.map((item, index) => <FadeIn key={item.title} delay={index * 14 + 12} style={{marginTop: 28, display: 'flex', alignItems: 'center', gap: 25, borderTop: '1px solid #D2D9D4', paddingTop: 24}}><Icon kind={item.icon} color={colors.purple} /><div><div style={{fontSize: 34, fontWeight: 800}}>{item.title}</div><div style={{fontSize: 23, marginTop: 9, color: colors.subtle}}>{item.note}</div></div></FadeIn>)}
    </div>
    <div style={{position: 'absolute', right: 111, top: 837, display: 'flex', alignItems: 'center', gap: 13, opacity: interpolate(frame, [fps, fps + 12], [0, 1], clamp)}}><div style={{width: 10, height: 10, borderRadius: '50%', background: colors.purple}} /><span style={{fontSize: 21, color: colors.subtle}}>官方演示 ≠ 本片实测</span></div>
  </>;
};

const Contrast = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = interpolate(frame, [fps * .65, fps * 1.3], [0, 1], clamp);
  return <>
    <div style={{position: 'absolute', left: 112, top: 160}}><Heading kicker="理解它的关键">回答问题，和执行任务</Heading></div>
    <FadeIn style={{position: 'absolute', top: 390, left: 110, width: 740, padding: 40, background: '#FFFFFF', borderRadius: 35}}>
      <Pill>聊天式回答</Pill><div style={{marginTop: 33, fontSize: 40, fontWeight: 800}}>给你一份建议</div>
      <div style={{display: 'flex', flexDirection: 'column', gap: 16, marginTop: 36}}>{[93, 72, 83, 58].map((width, index) => <div key={index} style={{height: 15, width: `${width}%`, borderRadius: 9, background: index === 0 ? '#CFC7EF' : '#E2E6E4'}} />)}</div>
      <div style={{fontSize: 23, color: colors.subtle, marginTop: 42}}>你继续打开网站、逐项处理</div>
    </FadeIn>
    <div style={{position: 'absolute', left: 878, top: 555, transform: `translateX(${(1 - reveal) * -20}px)`, opacity: reveal}}><Icon kind="arrow" color={colors.purple} size={110} /></div>
    <FadeIn delay={18} style={{position: 'absolute', top: 390, left: 1040, width: 770, padding: 40, background: colors.ink, color: '#FFF', borderRadius: 35}}>
      <Pill dark>执行型助手 · 概念图解</Pill><div style={{marginTop: 33, fontSize: 40, fontWeight: 800}}>推动事情往前走</div>
      <div style={{display: 'flex', alignItems: 'center', gap: 24, marginTop: 43}}><Icon kind="browser" color={colors.mint} /><Icon kind="arrow" color="#83968C" size={38} /><Icon kind="check" color={colors.mint} /><Icon kind="arrow" color="#83968C" size={38} /><Icon kind="person" color={colors.orange} /></div>
      <div style={{fontSize: 23, color: '#BED0CB', marginTop: 43}}>访问网页 → 执行步骤 → 请你确认</div>
    </FadeIn>
  </>;
};

const Plan = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const steps = ['理解目标', '列出计划', '逐项执行'];
  return <>
    <div style={{position: 'absolute', left: 112, top: 160}}><Heading kicker="概念图解 / 把大目标拆开" detail="先理解你要什么，再把任务分成能执行的步骤。">一句目标，怎样往前走？</Heading></div>
    <div style={{position: 'absolute', left: 120, right: 120, top: 476, height: 300}}>
      <svg width="1680" height="290" style={{position: 'absolute', top: 0, left: 0}}><path d="M240 132H1450" fill="none" stroke="#D8DEDA" strokeWidth="4" /><path d="M240 132H1450" fill="none" stroke={colors.purple} strokeWidth="5" strokeDasharray="1210" strokeDashoffset={1210 * (1 - interpolate(frame, [fps * .35, fps * 2.4], [0, 1], clamp))} /></svg>
      {steps.map((step, index) => <FadeIn key={step} delay={index * 18} style={{position: 'absolute', left: index * 565, width: 530, padding: '39px 33px', background: index === 2 ? colors.ink : '#FFF', borderRadius: 30, boxShadow: '0 17px 40px #17222A0A', color: index === 2 ? '#FFF' : colors.ink}}>
        <div style={{fontSize: 20, color: index === 2 ? colors.mint : colors.purple, fontWeight: 800}}>0{index + 1}</div><div style={{fontSize: 46, fontWeight: 900, marginTop: 22}}>{step}</div><div style={{marginTop: 27, fontSize: 23, color: index === 2 ? '#BDCEC6' : colors.subtle}}>{['想达成什么结果', '需要哪些信息与行动', '随结果继续下一步'][index]}</div>
      </FadeIn>)}
    </div>
    <div style={{position: 'absolute', left: 115, top: 845, display: 'flex', alignItems: 'center', gap: 16}}><Icon kind="person" color={colors.purple} size={35} /><span style={{fontSize: 25, color: colors.subtle}}>人的目标和限制，一直留在流程里</span></div>
  </>;
};

const Cloud = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const cursor = interpolate(frame, [fps * .5, fps * 2.5], [0, 1], clamp);
  return <>
    <div style={{position: 'absolute', left: 105, top: 185, width: 665}}><Heading kicker="概念图解 / 执行发生在哪里" detail="助手通过云端电脑和浏览器处理任务。">它有一台<br /><span style={{color: colors.purple}}>云端电脑</span></Heading>
      <FadeIn delay={22} style={{marginTop: 45, display: 'flex', alignItems: 'center', gap: 18}}><Icon kind="browser" color={colors.purple} /><div style={{fontSize: 27, fontWeight: 700}}>打开网页<br /><span style={{fontSize: 23, fontWeight: 400, color: colors.subtle}}>把步骤实际执行下去</span></div></FadeIn>
    </div>
    <FadeIn style={{position: 'absolute', left: 835, top: 187, width: 970, height: 640, border: '1px solid #C9D0CD', borderRadius: 28, background: '#FFF', boxShadow: '0 32px 80px #17222A18', overflow: 'hidden'}}>
      <div style={{height: 68, background: '#E7EBE7', borderBottom: '1px solid #D4DCD5', display: 'flex', alignItems: 'center', padding: '0 28px', gap: 10}}>{['#E7A295', '#DFC58B', '#A8C7AC'].map(color => <div key={color} style={{width: 13, height: 13, borderRadius: '50%', background: color}} />)}<div style={{marginLeft: 27, background: '#FFF', borderRadius: 10, fontSize: 20, color: colors.subtle, padding: '8px 28px', flex: 1}}>云端浏览器 · 示意界面</div></div>
      <div style={{padding: 36}}><div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 33}}><div style={{fontSize: 29, fontWeight: 900}}>任务工作区</div><Pill>依据目标执行</Pill></div>
        {['读取相关页面', '整理符合条件的选项', '准备需要确认的操作'].map((label, index) => <FadeIn key={label} delay={index * 17 + 9} style={{padding: '25px 22px', marginBottom: 14, borderRadius: 18, background: index === 2 ? '#F0EDF9' : '#F1F4EF', display: 'flex', alignItems: 'center', gap: 21}}><Icon kind={index === 2 ? 'lock' : 'check'} size={40} color={colors.purple} /><span style={{fontSize: 28, fontWeight: 700}}>{label}</span></FadeIn>)}
      </div>
      <svg width="38" height="48" viewBox="0 0 38 48" style={{position: 'absolute', left: 130 + cursor * 490, top: 215 + cursor * 253, filter: 'drop-shadow(2px 3px 3px #0004)'}}><path d="M3 2v37l10-10 8 16 7-4-8-16 15-1z" fill={colors.ink} stroke="#FFF" strokeWidth="2" /></svg>
    </FadeIn>
  </>;
};

const Shopping = ({config}: {config: MuseDemoConfig}) => <>
  <div style={{position: 'absolute', left: 110, top: 190, width: 780}}><Heading kicker="回到官方演示" detail="这里展示了按需求寻找和比较商品的过程。">有了需求，<br />再去找选项</Heading>
    <FadeIn delay={18} style={{marginTop: 52}}><Pill>真实素材：官网购物演示</Pill><div style={{fontSize: 29, color: colors.subtle, marginTop: 31, lineHeight: 1.7}}>看它如何推进任务，<br />也看哪些地方需要人把关。</div></FadeIn>
  </div>
  <OfficialVideo src={config.clips.shopping} offset={1} style={{position: 'absolute', right: 96, top: 148, width: 890, height: 745}} />
</>;

const Control = ({config}: {config: MuseDemoConfig}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const pulse = Math.sin(frame / fps * 3) * .045 + 1;
  return <>
    <OfficialVideo src={config.clips.japan} freezeAt={9.5} style={{position: 'absolute', left: 100, top: 150, width: 820, height: 738}} />
    <div style={{position: 'absolute', left: 1000, top: 183, width: 800}}><Heading kicker="关键一步 / 人工确认">执行到这里，<br /><span style={{color: colors.purple}}>决定权在你</span></Heading>
      <FadeIn delay={15} style={{marginTop: 42, display: 'flex', gap: 24, alignItems: 'center', padding: '28px 30px', background: '#FFF', borderRadius: 24}}><Icon kind="lock" color={colors.purple} /><div><div style={{fontSize: 32, fontWeight: 900}}>发邮件 · 购买等操作</div><div style={{fontSize: 23, marginTop: 13, color: colors.subtle}}>官方要求在敏感操作前请求确认</div></div></FadeIn>
      <FadeIn delay={33} style={{marginTop: 32, display: 'flex', alignItems: 'center', gap: 26}}><div style={{display: 'flex', alignItems: 'center', gap: 14, padding: '21px 34px', background: colors.purple, borderRadius: 19, color: '#FFF', fontSize: 29, fontWeight: 800, transform: `scale(${pulse})`}}><Icon kind="person" color="#FFF" size={35} />你来确认</div><div style={{fontSize: 24, color: colors.subtle}}>允许 / 调整 / 停止</div></FadeIn>
      <div style={{fontSize: 21, color: colors.subtle, marginTop: 32, lineHeight: 1.6}}>左侧实帧：发送预订详情前征询用户意见<br />右侧：官方能力说明的概念图解</div>
    </div>
  </>;
};

const Closing = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const reveal = spring({frame, fps, config: {damping: 26}});
  return <AbsoluteFill style={{background: colors.ink}}>
    <div style={{position: 'absolute', width: 750, height: 750, border: '1px solid #FFFFFF12', borderRadius: '50%', right: -80, top: 130, transform: `scale(${.85 + reveal * .15})`}}><div style={{position: 'absolute', inset: 105, border: '1px solid #FFFFFF17', borderRadius: '50%'}} /><div style={{position: 'absolute', inset: 212, border: '1px solid #FFFFFF1C', borderRadius: '50%'}} /></div>
    <div style={{position: 'absolute', top: 255, left: 110, width: 1380}}><Heading light kicker="看懂 MUSE / 接下来值得追问">能办事，<br />也要知道<span style={{color: colors.mint}}>哪里由人把关。</span></Heading><FadeIn delay={20} style={{marginTop: 55, display: 'flex', gap: 28}}><Pill dark>任务执行</Pill><Pill dark>权限边界</Pill><Pill dark>实际效果</Pill></FadeIn></div>
    <div style={{position: 'absolute', left: 113, bottom: 184, fontSize: 22, color: '#B3C0C5'}}>样片使用 Meta 官方素材与概念图解 · 未声称产品实测</div>
  </AbsoluteFill>;
};

const SceneView = ({scene, config}: {scene: Scene; config: MuseDemoConfig}) => {
  const frame = useCurrentFrame();
  const fade = interpolate(frame, [0, 8], [0, 1], clamp);
  return <AbsoluteFill style={{opacity: fade}}>{scene === 'hook' ? <Hook config={config} /> : scene === 'travel' ? <Travel config={config} /> : scene === 'contrast' ? <Contrast /> : scene === 'plan' ? <Plan /> : scene === 'cloud' ? <Cloud /> : scene === 'shopping' ? <Shopping config={config} /> : scene === 'control' ? <Control config={config} /> : <Closing />}</AbsoluteFill>;
};

export const MuseDemo = ({config}: {config: MuseDemoConfig}) => {
  const frame = useCurrentFrame();
  const {fps, durationInFrames} = useVideoConfig();
  const nowMs = frame / fps * 1000;
  const caption = config.captions.find(item => nowMs >= item.start_ms && nowMs < item.end_ms);
  const segmentIndex = config.segments.reduce((active, item, index) => nowMs >= item.start_ms ? index : active, 0);
  const closing = sceneFor(config.segments[segmentIndex]?.text ?? '', segmentIndex, config.segments.length) === 'closing';
  return <AbsoluteFill style={{background: colors.paper, color: colors.ink, fontFamily: font, overflow: 'hidden'}}>
    <div style={{position: 'absolute', right: -60, top: -320, width: 1000, height: 1000, borderRadius: '50%', border: '1px solid #C4CFC533'}} />
    {config.segments.map((segment, index) => {
      const from = index === 0 ? 0 : Math.round(segment.start_ms / 1000 * fps);
      const end = index === config.segments.length - 1 ? durationInFrames : Math.round(config.segments[index + 1].start_ms / 1000 * fps);
      return <Sequence key={segment.id} from={from} durationInFrames={Math.max(1, end - from)}><SceneView scene={sceneFor(segment.text, index, config.segments.length)} config={config} /></Sequence>;
    })}
    <div style={{position: 'absolute', top: 52, left: 107, right: 107, display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: closing ? '#E3EAE3' : colors.ink}}><div style={{display: 'flex', alignItems: 'center', gap: 13}}><div style={{width: 12, height: 12, borderRadius: '50%', background: closing ? colors.mint : colors.purple}} /><span style={{fontSize: 27, fontWeight: 900, letterSpacing: 4}}>MUSE</span><span style={{fontSize: 18, opacity: .65, marginLeft: 8}}>是什么</span></div><span style={{fontSize: 20, letterSpacing: 1, opacity: .65}}>AI 科普 · 01 / DEMO</span></div>
    {caption && <div style={{position: 'absolute', left: 135, right: 135, bottom: 69, textAlign: 'center'}}><span style={{display: 'inline-block', fontSize: 35, lineHeight: 1.45, fontWeight: 700, color: '#FFF', background: '#17222AEF', borderRadius: 15, padding: '14px 29px', maxWidth: '100%'}}>{caption.text}</span></div>}
    <div style={{position: 'absolute', left: 0, bottom: 0, height: 5, width: `${(frame + 1) / durationInFrames * 100}%`, background: closing ? colors.mint : colors.purple}} />
    <Audio src={staticFile(config.audio_src)} />
  </AbsoluteFill>;
};
