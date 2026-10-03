import type {ComponentType, CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {
  CursorTrack,
  KaraokeCaptions,
  LaptopFrame,
  PhoneFrame,
  ScreenRecording,
  SearchTyping,
  TextBuild,
  TextHighlight,
  TextReveal,
  TextSwap,
  WordCaptions,
} from '../../component-horizontal/snapcn';
import {AgentSteps} from './agent-steps';
import {AnswerHighlight} from './answer-highlight';
import {AnswerStream} from './answer-stream';
import {ChannelThread} from './channel-thread';
import {MoodboardReveal} from './moodboard-reveal';
import {PromptSend} from './prompt-send';
import {PromptZoom} from './prompt-zoom';
import {TerminalSimulator} from './terminal-simulator';
import {TextRewrite} from './text-rewrite';
import {
  charStartFrame,
  DEFAULT_MOTION,
  easeInBack,
  easeInBackSpeed,
  typingEndFrame,
  wordAt,
} from '../../component-horizontal/snapcn/word-flip';
import {LOCAL_FONT_FAMILY} from '../../component-horizontal/snapcn/ui/local-font';
import {componentDemos, type SnapcnDemo} from '../../component-horizontal/snapcn/demo';

const portraitFormat = {width: 1080, height: 1920, fps: 30} as const;
const ink = '#111827';
const muted = '#657083';
const blue = '#2563eb';
const dark = '#101421';
const bg = '#faf9f6';
const CLAMP = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const uiImage = () => staticFile('community/ai-ui.svg');
const portraitUiImage = () => staticFile('community/ai-ui-portrait.svg');
const photo = () => staticFile('community/landscape.svg');

const base = {
  fontFamily: LOCAL_FONT_FAMILY,
  letterSpacing: 0,
} as const;

const phoneCanvas = (children: ReactNode, background = bg) => (
  <AbsoluteFill
    style={{
      ...base,
      background,
      color: ink,
      overflow: 'hidden',
    }}
  >
    {children}
  </AbsoluteFill>
);

const SoftPhoto = () => (
  <AbsoluteFill>
    <Img src={photo()} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    <AbsoluteFill style={{background: 'linear-gradient(180deg, #0007 0%, #0002 42%, #0009 100%)'}} />
  </AbsoluteFill>
);

const SceneLabel = ({children, darkMode = false}: {children: ReactNode; darkMode?: boolean}) => (
  <div
    style={{
      position: 'absolute',
      left: 80,
      top: 108,
      color: darkMode ? '#9bdcff' : blue,
      fontSize: 30,
      fontWeight: 700,
      lineHeight: 1,
    }}
  >
    {children}
  </div>
);

const BigTitle = ({children, color = ink}: {children: ReactNode; color?: string}) => (
  <div
    style={{
      position: 'absolute',
      left: 80,
      right: 80,
      top: 190,
      color,
      fontSize: 82,
      fontWeight: 800,
      lineHeight: 1.16,
    }}
  >
    {children}
  </div>
);

const TextRevealPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>TEXT REVEAL</SceneLabel>
      <TextReveal text="认识 AI 智能体" fontSize={122} fontWeight={800} fontFamily={LOCAL_FONT_FAMILY} />
    </>,
  );

const TextBuildPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>TEXT BUILD</SceneLabel>
      <TextBuild
        text="让 知识 变成 视频"
        axis="y"
        gap={36}
        entryOffset={58}
        fontSize={112}
        fontWeight={800}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
  );

const TextHighlightPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>HIGHLIGHT</SceneLabel>
      <div style={{position: 'absolute', left: 78, right: 78, top: 660}}>
        <TextHighlight
          before="AI 的关键是"
          highlight="上下文"
          after=""
          preset="marker"
          fontSize={106}
          fontFamily={LOCAL_FONT_FAMILY}
          accentColor="#ffce2e"
          baseColor={ink}
        />
      </div>
    </>,
  );

const TextRewritePortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>REWRITE</SceneLabel>
      <TextRewrite
        headline="普通 脚本"
        keep={1}
        append="AI 科普"
        fontSize={104}
        zoom={1.05}
        fontWeight={700}
        centerY={0.48}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
  );

const TextSwapPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>TEXT SWAP</SceneLabel>
      <TextSwap
        fromText="手动 操作"
        toText="自动 执行"
        unit="word"
        fontSize={112}
        fontWeight={800}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
  );

const WordFlipPortrait = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const words = ['搜索', '推理', '执行'];
  const prefix = 'AI 可以';
  const suffix = '任务';
  const fontSize = 190;
  const cps = 9;
  const typeStart = 4;
  const charFade = 6;
  const jitter = 0.18;
  const pause = 6;
  const cycle = 35;
  const exitDuration = 9;
  const enterDuration = 9;
  const overlap = 3;
  const motion = DEFAULT_MOTION;
  const chars = [...prefix, ...suffix];
  const clock = {typeStart, cps, fps, jitter};
  const typingEnd = typingEndFrame({charCount: chars.length, charFade, ...clock});
  const {index: entering, local} = wordAt(frame, {
    typingEnd,
    pause,
    cycle,
    wordCount: words.length,
    loop: true,
  });
  const outgoing = entering - 1 < 0 ? words.length - 1 : entering - 1;
  const enterStart = Math.max(0, exitDuration - overlap);
  const em = fontSize;

  const exitAt = (localFrame: number) => {
    const t = interpolate(localFrame, [0, exitDuration], [0, 1], CLAMP);
    const progress = easeInBack(t);
    return {
      y: progress * motion.exitY * em,
      rotate: progress * motion.rotate,
      scale: 1 + progress * (motion.scale - 1),
      blur: easeInBackSpeed(t) * motion.blur * em,
      opacity: interpolate(t, [0.65, 1], [1, 0], CLAMP),
    };
  };

  const enterAt = (localFrame: number) => {
    const progress = interpolate(localFrame, [enterStart, enterStart + enterDuration], [0, 1], {
      ...CLAMP,
      easing: Easing.bezier(0.2, 0.6, 0.35, 1),
    });
    return {
      y: (1 - progress) * motion.enterY * em,
      rotate: -(1 - progress) * motion.rotate,
      scale: motion.scale + progress * (1 - motion.scale),
      blur: (1 - progress) * motion.blur * em,
      opacity: interpolate(progress, [0, 0.45], [0, 1], CLAMP),
    };
  };

  const stateFor = (i: number) => {
    if (i === entering && local >= enterStart) return enterAt(local);
    if (i === outgoing && local >= 0 && local <= exitDuration) return exitAt(local);
    if (i === entering && local > exitDuration) return enterAt(local);
    if (i === 0 && local < 0) return {y: 0, rotate: 0, scale: 1, blur: 0, opacity: 1};
    return null;
  };

  const typed = (text: string, offset: number, style: CSSProperties) => (
    <div style={style}>
      {[...text].map((ch, index) => {
        const start = charStartFrame(offset + index, clock);
        return (
          <span
            key={`${text}-${index}`}
            style={{opacity: interpolate(frame, [start, start + charFade], [0, 1], CLAMP)}}
          >
            {ch}
          </span>
        );
      })}
      {frame >= typeStart && frame <= typingEnd + pause ? (
        <span
          style={{
            display: 'inline-block',
            width: 5,
            height: '0.78em',
            marginLeft: 10,
            borderRadius: 2,
            background: muted,
            opacity: Math.floor((frame / fps) * 2) % 2 === 0 ? 1 : 0.12,
            verticalAlign: '-0.08em',
          }}
        />
      ) : null}
    </div>
  );

  return phoneCanvas(
    <>
      <SceneLabel>WORD FLIP</SceneLabel>
      <div style={{position: 'absolute', left: 80, right: 80, top: 520, height: 760, textAlign: 'center'}}>
        {typed(prefix, 0, {fontSize: 76, fontWeight: 700, color: muted, lineHeight: 1.1})}
        <div
          style={{
            position: 'relative',
            height: 260,
            marginTop: 64,
            marginBottom: 64,
            perspective: 6.5 * em,
          }}
        >
          {words.map((word, index) => {
            const state = stateFor(index);
            if (!state || state.opacity <= 0) return null;
            return (
              <div
                key={word}
                style={{
                  position: 'absolute',
                  inset: 0,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize,
                  lineHeight: 1,
                  fontWeight: 900,
                  letterSpacing: '-0.05em',
                  textRendering: 'geometricPrecision',
                  background: 'linear-gradient(90deg,#2563eb,#d946ef)',
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  color: 'transparent',
                  WebkitTextFillColor: 'transparent',
                  transformOrigin: 'center 70%',
                  transform: `translateY(${state.y}px) rotateX(${state.rotate}deg) scale(${state.scale})`,
                  opacity: state.opacity,
                  filter: state.blur > 0.01 ? `blur(${state.blur}px)` : undefined,
                }}
              >
                {word}
              </div>
            );
          })}
        </div>
        {typed(suffix, prefix.length, {fontSize: 76, fontWeight: 700, color: muted, lineHeight: 1.1})}
      </div>
    </>,
  );
};

const WordCaptionsPortrait = () =>
  phoneCanvas(
    <>
      <SoftPhoto />
      <WordCaptions
        words="人工智能 可以 帮你 理解 知识 自动 制作 视频"
        framesPerWord={18}
        aspect="9:16"
        maxWidth={900}
        fontSize={82}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
    dark,
  );

const KaraokeCaptionsPortrait = () =>
  phoneCanvas(
    <>
      <SoftPhoto />
      <KaraokeCaptions
        text="我们 把 复杂 的 AI 知识 讲 清楚"
        emphasize="讲 清楚"
        aspect="portrait"
        fontSize={78}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
    dark,
  );

const SearchTypingPortrait = () => {
  const frame = useCurrentFrame();
  const reveal = interpolate(frame, [58, 88], [0, 1], CLAMP);
  return phoneCanvas(<>
    <SceneLabel>SEARCH</SceneLabel>
    <BigTitle>AI 智能体如何工作？</BigTitle>
    <SearchTyping text="智能体如何工作" fieldHeight={0.115}
      frontVisible={0.85} dolly={1.1} edgeInset={70}
      charsPerSecond={9} fontFamily={LOCAL_FONT_FAMILY} />
    <div style={{position: 'absolute', left: 80, right: 80, top: 1220,
      opacity: reveal, display: 'grid', gap: 26}}>
      {['理解目标', '调用工具', '根据反馈继续'].map((step,i) =>
        <div key={step} style={{padding: '34px 40px', borderRadius: 28,
          background: i === 0 ? '#dbeafe' : '#fff', fontSize: 54,
          fontWeight: 700, color: i === 0 ? blue : ink}}>{step}</div>)}
    </div>
  </>);
};

const PromptSendPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>PROMPT</SceneLabel>
      <BigTitle>从一句话开始生成科普脚本</BigTitle>
        <PromptSend
          text="解释 RAG 并举例"
          chips={['解释概念', '举例说明', '整理步骤']}
          width={680}
          fieldHeight={450}
          fontSize={52}
          chipFontSize={38}
          radius={36}
          sendSize={90}
          zoomIn={1.35}
          zoomOut={1}
          focusX={0.62}
          focusY={0.5}
          outX={0.8}
          outY={0.6}
          fontFamily={LOCAL_FONT_FAMILY}
        />
    </>,
  );

const PromptZoomPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>PROMPT ZOOM</SceneLabel>
      <BigTitle>输入一个问题，镜头推到关键字</BigTitle>
        <PromptZoom
          greeting="想了解 AI？"
          placeholder="输入你的问题"
          text="解释智能体的工作原理"
          model="Auto"
          effort="Medium"
          typeStart={0.35}
          cutAt={1}
          zoom={1.32}
          charsPerSecond={18}
          focusX={0.35}
          focusY={0.5}
          accentColor="#266DF0"
          mode="light"
        />
    </>,
  );

const AnswerStreamPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>ANSWER</SceneLabel>
        <AnswerStream
          question="什么是 AI 智能体？"
          answer="智能体 接收 目标，制订 计划，调用 工具，再 根据 结果 调整 下一步。"
          headline="三个关键能力"
          cards={[
            {title: '理解', body: '把目标转成可执行步骤'},
            {title: '工具', body: '搜索、读取和操作软件'},
            {title: '反馈', body: '检查结果并继续行动'},
          ]}
          fontFamily={LOCAL_FONT_FAMILY}
          focusY={0.05}
        />
    </>,
  );

const AnswerHighlightPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>HIGHLIGHT ANSWER</SceneLabel>
        <AnswerHighlight
          question="AI 为什么需要上下文？"
          answer="上下文 提供 当前 任务 的 背景 和 约束。清晰的 目标 和 充分的 信息 能 帮助 模型 给出 更 相关 的 回答。"
          statement="清晰的 目标"
          word="目标"
          fontFamily={LOCAL_FONT_FAMILY}
        />
    </>,
  );

const AgentStepsPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>AGENT STEPS</SceneLabel>
      <AgentSteps
        query="把一段文章做成 AI 科普视频"
        steps={[
          {running: '正在理解文本…', done: '提取 3 个重点', icon: 'check'},
          {running: '正在检索资料…', done: '找到可靠来源', icon: 'globe'},
          {running: '正在生成脚本…', done: '完成分镜', icon: 'check'},
          {running: '正在渲染视频…', done: '完成视频', icon: 'check'},
        ]}
        result="视频已生成"
        centerY={0.48}
        glowRadius={0.72}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
  );

const TerminalSimulatorPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel darkMode>TERMINAL</SceneLabel>
      <TerminalSimulator
        intro="用 *代码* 制作视频"
        command={{text: 'npx remotion render'}}
        lines={[
          {text: '准备脚本和素材', type: 'command', delay: 0, pause: 0},
          {text: '渲染帧 1 / 300', type: 'log', delay: 8, pause: 0},
          {text: '渲染完成', type: 'success', delay: 8, pause: 0},
        ]}
        fontSize={22}
        zoom={{enabled: true, scale: 1.1}}
        speed={1.2}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
    dark,
  );

const ChannelThreadPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel darkMode>THREAD</SceneLabel>
      <ChannelThread
        messages={[
          {author: '策划 Agent', time: '09:41', text: '先理解文章，再确定重点。', avatar: uiImage(), at: 0},
          {author: '策划 Agent', time: '09:41', text: '脚本已经准备好了。', avatar: uiImage(), at: 30},
          {author: '制作 Agent', time: '09:42', text: '我来匹配组件和素材。', avatar: uiImage(), at: 72},
          {author: '制作 Agent', time: '09:42', text: '开始生成视频。', avatar: uiImage(), at: 110},
        ]}
        fontFamily={LOCAL_FONT_FAMILY}
      />
    </>,
    dark,
  );

const PhoneFramePortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>PHONE FRAME</SceneLabel>
      <BigTitle>手机界面作为短视频主画面</BigTitle>
      <div style={{position: 'absolute', left: 0, right: 0, top: 570, height: 1180}}>
        <PhoneFrame screenSrc={portraitUiImage()} scale={2.1} fontFamily={LOCAL_FONT_FAMILY} />
      </div>
    </>,
  );

const LaptopFramePortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>LAPTOP</SceneLabel>
      <BigTitle>桌面操作聚焦到关键区域</BigTitle>
      <div style={{position: 'absolute', left: -150, right: -150, top: 660, height: 760}}>
        <LaptopFrame
          screenSrc={uiImage()}
          entrance="open"
          finale="zoom-to-screen"
          notchLabel="AI 正在运行"
          scale={1.15}
          fontFamily={LOCAL_FONT_FAMILY}
        />
      </div>
    </>,
  );

const ScreenRecordingPortrait = () =>
  phoneCanvas(
    <>
      <SceneLabel>SCREEN</SceneLabel>
      <ScreenRecording
        src={portraitUiImage()}
        sourceAspect={9 / 16}
        camera={[
          {at: 30, duration: 25, zoom: 1.1, x: 0.5, y: 0.52},
          {at: 100, duration: 25, zoom: 1},
        ]}
      />
    </>,
  );

const CursorTrackPortrait = () =>
  phoneCanvas(
    <CursorTrack variant="dot" size={58}>
      <AbsoluteFill style={{background: '#f8fafc', padding: '190px 76px'}}>
        <div style={{fontSize: 48, fontWeight: 800, marginBottom: 38}}>AI 视频工作台</div>
        {['导入文本', '生成脚本', '匹配组件', '渲染短视频'].map((step, i) => (
          <div
            key={step}
            style={{
              height: 180,
              borderRadius: 28,
              background: i === 2 ? '#dbeafe' : '#fff',
              border: `2px solid ${i === 2 ? '#3b82f6' : '#e5e7eb'}`,
              marginBottom: 28,
              padding: 38,
              fontSize: 42,
              fontWeight: 700,
              color: i === 2 ? '#1d4ed8' : ink,
            }}
          >
            {step}
          </div>
        ))}
      </AbsoluteFill>
    </CursorTrack>,
  );

const MoodboardRevealPortrait = () =>
  phoneCanvas(
    <MoodboardReveal
      leadIn="让"
      emphasis="知识"
      tailIn="可视化"
      images={[photo(), uiImage(), photo(), uiImage()]}
      heroImage={portraitUiImage()}
      fontFamily={LOCAL_FONT_FAMILY}
    />,
  );

const portraitComponents: Record<string, ComponentType> = {
  'Snapcn-TextReveal': TextRevealPortrait,
  'Snapcn-TextBuild': TextBuildPortrait,
  'Snapcn-TextHighlight': TextHighlightPortrait,
  'Snapcn-TextRewrite': TextRewritePortrait,
  'Snapcn-TextSwap': TextSwapPortrait,
  'Snapcn-WordFlip': WordFlipPortrait,
  'Snapcn-WordCaptions': WordCaptionsPortrait,
  'Snapcn-KaraokeCaptions': KaraokeCaptionsPortrait,
  'Snapcn-SearchTyping': SearchTypingPortrait,
  'Snapcn-PromptSend': PromptSendPortrait,
  'Snapcn-PromptZoom': PromptZoomPortrait,
  'Snapcn-AnswerStream': AnswerStreamPortrait,
  'Snapcn-AnswerHighlight': AnswerHighlightPortrait,
  'Snapcn-AgentSteps': AgentStepsPortrait,
  'Snapcn-TerminalSimulator': TerminalSimulatorPortrait,
  'Snapcn-ChannelThread': ChannelThreadPortrait,
  'Snapcn-PhoneFrame': PhoneFramePortrait,
  'Snapcn-LaptopFrame': LaptopFramePortrait,
  'Snapcn-ScreenRecording': ScreenRecordingPortrait,
  'Snapcn-CursorTrack': CursorTrackPortrait,
  'Snapcn-MoodboardReveal': MoodboardRevealPortrait,
};

export const nativeDemos: SnapcnDemo[] = componentDemos.map((demo) => {
  const component = portraitComponents[demo.id];
  if (!component) throw new Error(`Missing Snapcn portrait component for ${demo.id}`);
  return {
    ...demo,
    id: demo.id,
    component,
    ...portraitFormat,
  };
});


export const nativeLayoutNotes: Record<string, string> = {
  'Snapcn-TextReveal': 'Full-height portrait headline reveal with large centered type and safe margins.',
  'Snapcn-TextBuild': 'Stacked vertical phrase build with expanded line spacing for phone reading.',
  'Snapcn-TextHighlight': 'Portrait text block with marker emphasis centered in the upper-middle viewport.',
  'Snapcn-TextRewrite': 'Large portrait rewrite headline preserving source word replacement timing.',
  'Snapcn-TextSwap': 'Phone-scale word swap with the source token transition emphasized at center.',
  'Snapcn-WordFlip': 'Three-line portrait layout: typed prefix, baseline flip slot, typed suffix, preserving source flip timing curves.',
  'Snapcn-WordCaptions': '9:16 caption layer over full-bleed media with larger word captions.',
  'Snapcn-KaraokeCaptions': 'Portrait karaoke captions over full-bleed media with emphasized phrase timing.',
  'Snapcn-SearchTyping': 'Tall search answer card with typed query and vertically stacked result cards.',
  'Snapcn-PromptSend': 'Portrait prompt composer card with chips arranged for thumb-readable phone layout.',
  'Snapcn-PromptZoom': 'Prompt zoom scene framed as a tall phone-safe interaction area.',
  'Snapcn-AnswerStream': 'Tall answer panel with question, streaming answer, and stacked explanation cards.',
  'Snapcn-AnswerHighlight': 'Portrait answer reading panel with highlight focus retained in a taller text column.',
  'Snapcn-AgentSteps': 'Vertical agent progress sequence centered for short-video narration.',
  'Snapcn-TerminalSimulator': 'Dark portrait terminal scene with larger command/log lines.',
  'Snapcn-ChannelThread': 'Chat thread arranged as a vertical conversation surface.',
  'Snapcn-PhoneFrame': 'Phone device showcase scaled as the primary vertical object.',
  'Snapcn-LaptopFrame': 'Landscape desktop material reframed as a focused vertical cutaway.',
  'Snapcn-ScreenRecording': 'Portrait screen recording camera path using a 9:16 source aspect.',
  'Snapcn-CursorTrack': 'Vertical checklist workspace with cursor highlight over stacked steps.',
  'Snapcn-MoodboardReveal': 'Portrait moodboard reveal using full-height image rhythm and centered title copy.',
};

