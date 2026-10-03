import type {CSSProperties, ReactNode} from 'react';
import {AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {Audio} from '@remotion/media';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {Arrow, Circle} from '@remotion/shapes';
import type initialEpisode from '../episode.generated.json';
import {TextBuild} from '../components/vendor/TextBuild';
import {TimedCaptions} from '../components/TimedCaptions';

type Episode = typeof initialEpisode;
type Shot = Episode['shots'][number];
const ink = '#162b23';
const green = '#176c52';
const orange = '#ed6946';
const paper = '#f4f3ed';
const font = '"Microsoft YaHei", "Noto Sans SC", sans-serif';
const clamped = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const Card = ({children, style}: {children: ReactNode; style?: CSSProperties}) => (
  <div style={{background: '#fff', border: '2px solid #dddcd2', borderRadius: 28, padding: 34,
    boxShadow: '0 12px 0 #e6e5dc', ...style}}>{children}</div>
);

const Tag = ({children, color = green}: {children: ReactNode; color?: string}) => (
  <span style={{display: 'inline-block', color, background: color + '15', borderRadius: 12,
    padding: '12px 22px', fontSize: 26, fontWeight: 700}}>{children}</span>
);

const Reveal = ({children, delay = 0, style}: {children: ReactNode; delay?: number; style?: CSSProperties}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = spring({frame: frame - delay, fps, config: {damping: 200}});
  return <div style={{opacity: progress, transform: `translateY(${(1 - progress) * 30}px)`, ...style}}>{children}</div>;
};

const DownArrow = () => <div style={{display: 'flex', justifyContent: 'center', margin: '16px 0'}}>
  <Arrow length={48} headWidth={32} headLength={20} shaftWidth={8} direction="down" fill={green} />
</div>;

const SceneTitle = ({shot, big = false}: {shot: Shot; big?: boolean}) => (
  <>
    <div style={{fontSize: 31, color: green, letterSpacing: 2, fontWeight: 700, marginBottom: 28}}>{shot.eyebrow}</div>
    <div style={{height: big ? 320 : 240, position: 'relative', marginBottom: big ? 45 : 28}}>
      <TextBuild text={shot.title.split('\n').map(line => line.replaceAll(' ', '\u00a0')).join(' ')} axis="y" fontSize={big ? 96 : 78}
        fontWeight={800} fontFamily={font} color={ink} gap={22} firstDuration={14} pushDuration={22} />
    </div>
  </>
);

const Hook = () => {
  const frame = useCurrentFrame();
  return <Reveal delay={30}>
    <Card style={{marginTop: 40, padding: 48}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 20, marginBottom: 32}}>
        <Circle radius={15} fill={green} /><span style={{fontSize: 30, color: '#69776f'}}>AI 生成结果</span>
      </div>
      <div style={{fontFamily: 'Consolas, monospace', fontSize: 37, lineHeight: 1.85, color: green}}>
        <div>function login() {'{'}</div><div style={{paddingLeft: 48}}>return success;</div><div>{'}'}</div>
      </div>
      <div style={{marginTop: 34, display: 'flex', gap: 18, flexWrap: 'wrap'}}>
        <Tag>代码已生成</Tag><div style={{opacity: interpolate(frame, [70, 85], [0, 1], clamped)}}><Tag color={orange}>需求待验收</Tag></div>
      </div>
    </Card>
    <div style={{fontSize: 43, textAlign: 'center', marginTop: 65, color: orange, fontWeight: 800}}>还有一条交付链。</div>
  </Reveal>;
};

const Workflow = () => {
  const labels = ['明确需求', '拆分任务', '编写代码', '测试 · 人工验收'];
  return <div>{labels.map((label, index) => <Reveal delay={22 + index * 24} key={label}>
    <Card style={{padding: '23px 35px', display: 'flex', alignItems: 'center', gap: 30,
      background: index === 2 ? '#e3f0e7' : '#fff'}}>
      <span style={{fontSize: 30, color: green, fontFamily: 'Consolas, monospace'}}>0{index + 1}</span>
      <span style={{fontSize: 47, fontWeight: 700}}>{label}</span>
      {index === 2 ? <span style={{marginLeft: 'auto', color: green, fontSize: 25}}>只是一步</span> : null}
    </Card>{index < labels.length - 1 ? <DownArrow /> : null}
  </Reveal>)}</div>;
};

const Graph = () => <>
  <Reveal delay={20}><Card style={{textAlign: 'center'}}><Tag>起点</Tag><div style={{fontSize: 55, fontWeight: 800, marginTop: 18}}>一个真实需求</div></Card></Reveal>
  <Reveal delay={45}><DownArrow /><div style={{display: 'flex', gap: 18}}>{['拆需求', '实现', '审查'].map((item, i) =>
    <Card key={item} style={{flex: 1, textAlign: 'center', padding: '40px 10px', background: i === 1 ? '#e3f0e7' : '#fff'}}>
      <div style={{fontSize: 25, color: green}}>角色 {i + 1}</div><div style={{fontSize: 38, fontWeight: 800, marginTop: 22}}>{item}</div>
    </Card>)}</div></Reveal>
  <Reveal delay={75}><DownArrow /><Card style={{textAlign: 'center', background: ink, color: paper}}>
    <div style={{fontSize: 29, color: '#add3bc'}}>任务有依赖 · 产物可交接</div>
    <div style={{fontSize: 51, fontWeight: 800, marginTop: 18}}>可验证的结果</div>
  </Card></Reveal>
  <div style={{fontSize: 25, color: '#758078', textAlign: 'center', marginTop: 35}}>概念示意 · 原文按作者理解讨论此方向</div>
</>;

const Roles = () => <>
  <Reveal delay={20}><Card style={{padding: 15, overflow: 'hidden'}}>
    <Img src={staticFile('episodes/001-ai-coding/source-team.png')} style={{width: '100%', height: 430, objectFit: 'cover', objectPosition: '75% 10%'}} />
  </Card><div style={{fontSize: 23, color: '#758078', margin: '22px 0 30px'}}>素材：用户原文中的 Multica 小队截图</div></Reveal>
  <Reveal delay={40}><Card style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
    <div><Tag>人负责</Tag><div style={{fontSize: 47, marginTop: 22, fontWeight: 800}}>最终验收</div></div>
    <div style={{fontSize: 68, color: green}}>✓</div>
  </Card></Reveal>
  <Reveal delay={95}><div style={{fontSize: 39, textAlign: 'center', marginTop: 38, color: green, fontWeight: 800}}>交接任务状态 + 产物</div></Reveal>
</>;

const Board = () => {
  const frame = useCurrentFrame();
  const zoom = interpolate(frame, [30, 170], [1, 1.14], clamped);
  return <>
    <Card style={{padding: 10, overflow: 'hidden'}}><div style={{height: 525, overflow: 'hidden', borderRadius: 18}}>
      <Img src={staticFile('episodes/001-ai-coding/source-board.png')} style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${zoom})`}} />
    </div></Card>
    <div style={{fontSize: 23, color: '#758078', margin: '23px 0 30px'}}>原文截图 · 示例工具，不代表特定大厂内部系统</div>
    <Reveal delay={30}><div style={{display: 'flex', gap: 12, justifyContent: 'space-between'}}>{['待办', '进行中', '审查', '完成'].map((label, index) =>
      <div key={label} style={{background: index === Math.min(3, Math.floor(frame / 45)) ? green : '#e3e5dc',
        color: index === Math.min(3, Math.floor(frame / 45)) ? '#fff' : ink,
        padding: '22px 24px', borderRadius: 14, fontSize: 32, fontWeight: 700}}>{label}</div>)}</div></Reveal>
    <Reveal delay={140}><div style={{marginTop: 35, fontSize: 36, color: orange, fontWeight: 700, textAlign: 'center'}}>遇到阻塞 → 人来判断</div></Reveal>
  </>;
};

const Cloud = () => <>
  <Reveal delay={20}><Card style={{display: 'flex', alignItems: 'center', gap: 45}}>
    <div style={{width: 110, height: 174, border: `8px solid ${ink}`, borderRadius: 24, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 38}}>任务</div>
    <div><Tag>手机</Tag><div style={{fontSize: 44, fontWeight: 800, marginTop: 20}}>发起 · 查看进度</div></div>
  </Card></Reveal>
  <Reveal delay={50}><DownArrow /><Card style={{background: ink, color: '#fff', textAlign: 'center', padding: 48}}>
    <div style={{fontSize: 28, color: '#a9d2b7'}}>远程运行环境</div><div style={{fontSize: 52, fontWeight: 800, marginTop: 24}}>Agent 继续执行</div>
  </Card></Reveal>
  <Reveal delay={80}><DownArrow /><Card style={{textAlign: 'center', fontSize: 43, fontWeight: 800}}>产物回传 → 人工验收</Card></Reveal>
  <div style={{marginTop: 35, color: '#758078', textAlign: 'center', fontSize: 25}}>概念示意 · 人仍负责关键判断与验收</div>
</>;

const Evaluation = () => <>
  <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 25}}>{[
    ['01', '记录过程', '留下执行轨迹'], ['02', '整理案例', '形成评测集'],
    ['03', '优化工作流', '改知识库与 Skill'], ['04', '再次评测', '验证是否变好'],
  ].map(([number, title, desc], index) => <Reveal key={number} delay={20 + index * 40}>
    <Card style={{height: 225, padding: 30, background: index === 3 ? '#e3f0e7' : '#fff'}}>
      <div style={{color: green, fontSize: 29, fontFamily: 'Consolas, monospace'}}>{number}</div>
      <div style={{fontSize: 40, fontWeight: 800, marginTop: 23}}>{title}</div>
      <div style={{fontSize: 27, color: '#768078', marginTop: 22}}>{desc}</div>
    </Card>
  </Reveal>)}</div>
  <Reveal delay={215}><div style={{marginTop: 45, padding: 30, border: `2px solid ${orange}`, borderRadius: 20}}>
    <Tag color={orange}>原文进展：早期验证 / MVP</Tag>
    <div style={{fontSize: 30, lineHeight: 1.6, marginTop: 22}}>数据清洗、评估器仍需改进。<br />还需验证，是否真正提效。</div>
  </div></Reveal>
</>;

const Ending = () => <Reveal delay={20}>
  <Card style={{background: ink, color: paper, padding: 55, textAlign: 'center'}}>
    <div style={{fontSize: 33, color: '#b7d4c0'}}>从写代码</div><div style={{fontSize: 55, margin: '22px 0'}}>↓</div>
    <div style={{fontSize: 60, fontWeight: 800, marginBottom: 35}}>到交付需求</div><Tag color="#a1d8b3">目标清楚 · 过程可追踪 · 结果可验收</Tag>
  </Card>
  <div style={{fontSize: 31, color: '#6b776f', marginTop: 55, lineHeight: 1.85, textAlign: 'center'}}>
    参考文章<br />《AI Coding 大厂中的发展历程（三）》<br />画面含原文截图与概念示意
  </div>
</Reveal>;

const Scene = ({shot}: {shot: Shot}) => {
  const visuals: Record<string, ReactNode> = {hook: <Hook />, workflow: <Workflow />, graph: <Graph />,
    roles: <Roles />, board: <Board />, cloud: <Cloud />, evaluation: <Evaluation />, ending: <Ending />};
  return <AbsoluteFill style={{background: paper, color: ink, padding: '285px 80px 440px', fontFamily: font}}>
    <SceneTitle shot={shot} big={shot.type === 'hook' || shot.type === 'ending'} />
    {visuals[shot.type]}
    <Audio src={staticFile(shot.audio)} />
  </AbsoluteFill>;
};

export const AiScienceVideo = ({episode}: {episode: Episode}) => {
  const frame = useCurrentFrame();
  const current = episode.shots.reduce((result, shot, index) => frame >= shot.from ? index : result, 0);
  return <AbsoluteFill style={{background: paper, fontFamily: font, color: ink}}>
    <TransitionSeries>{episode.shots.map((shot, index) => [
      <TransitionSeries.Sequence key={shot.id} durationInFrames={shot.sequenceDurationInFrames}><Scene shot={shot} /></TransitionSeries.Sequence>,
      index < episode.shots.length - 1 ? <TransitionSeries.Transition key={shot.id + '-transition'} presentation={fade()}
        timing={linearTiming({durationInFrames: episode.transitionFrames})} /> : null,
    ])}</TransitionSeries>
    <div style={{position: 'absolute', top: 110, left: 80, right: 80, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
      <div style={{fontSize: 33, fontWeight: 800}}>AI 知识科普 <span style={{color: green}}> / 001</span></div>
      <div style={{fontSize: 27, color: green, fontFamily: 'Consolas, monospace'}}>{String(current + 1).padStart(2, '0')} / 08</div>
    </div>
    <div style={{position: 'absolute', left: 80, right: 80, top: 185, height: 5, background: '#dedfd4'}}>
      <div style={{height: '100%', width: `${100 * frame / (episode.durationInFrames - 1)}%`, background: green}} />
    </div>
    <TimedCaptions captions={episode.captions} />
    <div style={{position: 'absolute', top: 1735, left: 80, right: 80, borderTop: '2px solid #deded4', paddingTop: 25,
      display: 'flex', justifyContent: 'space-between', fontSize: 23, color: '#6c776e'}}>
      <span>从写代码到交付需求</span><span>AI 配音 · 第一版</span>
    </div>
  </AbsoluteFill>;
};
