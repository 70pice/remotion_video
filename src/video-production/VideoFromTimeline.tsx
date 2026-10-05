import {useMemo} from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Freeze, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {FittedText, muted, productionFont, useLayout, white} from './adapters/layout';
import {isSemanticComponent, resolveCommunityPreset, semanticProductionRegistry} from './registry';
import type {Timeline, TimelineShot, TimelineVideoProps} from './types';
import {validateTimeline} from './validation.mjs';

const CommunityPresetScene = ({shot}: {shot: TimelineShot}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const preset = resolveCommunityPreset(shot.component_id, vertical);
  const Preset = preset.component;
  const scale = Math.min(width / preset.width, height / preset.height);
  const content = frame < preset.durationInFrames
    ? <Preset />
    : <Freeze frame={Math.max(0, preset.durationInFrames - 1)}><Preset /></Freeze>;
  const titleHeight = (vertical ? 118 : 64) * unit;
  const bodyHeight = shot.body ? (vertical ? 100 : 55) * unit : 0;
  return <AbsoluteFill style={{background: '#050A12', overflow: 'hidden'}}>
    <div style={{position: 'absolute', width: preset.width, height: preset.height, left: '50%', top: '50%',
      transform: `translate(-50%, -50%) scale(${scale})`, transformOrigin: 'center', overflow: 'hidden'}}>
      <Sequence width={preset.width} height={preset.height}>{content}</Sequence>
    </div>
    <div style={{position: 'absolute', left: margin, right: margin, top: (vertical ? 180 : 112) * unit,
      padding: `${18 * unit}px ${24 * unit}px`, borderRadius: 18 * unit, background: '#07101FD9',
      border: '1px solid #FFFFFF2E', boxSizing: 'border-box'}}>
      <FittedText text={shot.title} width={contentWidth - 48 * unit} height={titleHeight}
        fontSize={(vertical ? 52 : 34) * unit} minFontSize={18 * unit} />
      {shot.body ? <FittedText text={shot.body} width={contentWidth - 48 * unit} height={bodyHeight}
        fontSize={(vertical ? 30 : 21) * unit} minFontSize={15 * unit}
        style={{color: '#D6DFEC', fontWeight: 500, marginTop: 8 * unit}} /> : null}
    </div>
  </AbsoluteFill>;
};

const Scene = ({shot}: {shot: TimelineShot}) => {
  const {unit, vertical, margin} = useLayout();
  if (!isSemanticComponent(shot.component_id)) return <CommunityPresetScene shot={shot} />;
  const Adapter = semanticProductionRegistry[shot.component_id];
  return <AbsoluteFill style={{padding: `${(vertical ? 210 : 125) * unit}px ${margin}px ${(vertical ? 500 : 305) * unit}px`,
    background: `radial-gradient(ellipse at 110% 5%, ${shot.accent_color}19, transparent 55%), #111C2E`}}>
    <Adapter shot={shot} durationInFrames={shot.end_frame - shot.start_frame} />
  </AbsoluteFill>;
};

const Captions = ({timeline}: {timeline: Timeline}) => {
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const milliseconds = frame / timeline.fps * 1000;
  const caption = timeline.captions.find((item) => milliseconds >= item.start_ms && milliseconds < item.end_ms);
  if (!caption) return null;
  const height = (vertical ? 200 : 110) * unit;
  return <div style={{position: 'absolute', left: margin, right: margin, bottom: (vertical ? 280 : 150) * unit,
    height, padding: `${16 * unit}px ${24 * unit}px`, boxSizing: 'border-box', background: '#07101FEF',
    borderRadius: 20 * unit, border: '1px solid #41536E', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
    <FittedText text={caption.text} width={contentWidth - 48 * unit} height={height - 32 * unit}
      fontSize={46 * unit} minFontSize={30 * unit} style={{textAlign: 'center'}} />
  </div>;
};

export const VideoFromTimeline = ({timeline: input}: TimelineVideoProps) => {
  const timeline = useMemo(() => validateTimeline(input), [input]);
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const shotIndex = timeline.shots.findIndex((shot) => frame >= shot.start_frame && frame < shot.end_frame);
  const shot = timeline.shots[Math.max(0, shotIndex)];
  return <AbsoluteFill style={{background: '#111C2E', color: white, fontFamily: productionFont}}>
    {timeline.audio_src ? <Audio src={staticFile(timeline.audio_src)} /> : null}
    {timeline.shots.map((item) => <Sequence key={item.shot_id} from={item.start_frame}
      durationInFrames={item.end_frame - item.start_frame} name={`${item.component_id} / ${item.title}`}>
      <Scene shot={item} />
    </Sequence>)}
    <div style={{position: 'absolute', left: margin, right: margin, top: (vertical ? 75 : 42) * unit,
      display: 'flex', justifyContent: 'space-between', color: muted, fontSize: 24 * unit, fontWeight: 700}}>
      <span>VIDEOAGENTS</span><span>{String(Math.max(0, shotIndex) + 1).padStart(2, '0')} / {String(timeline.shots.length).padStart(2, '0')}</span>
    </div>
    <div style={{position: 'absolute', top: (vertical ? 135 : 90) * unit, left: margin, right: margin,
      height: 3 * unit, background: '#334158'}}>
      <div style={{height: '100%', width: `${(frame + 1) / timeline.duration_in_frames * 100}%`, background: shot.accent_color}} />
    </div>
    <Captions timeline={timeline} />
    {shot.source_label ? <div style={{position: 'absolute', bottom: (vertical ? 110 : 52) * unit, left: margin,
      right: margin, height: (vertical ? 120 : 68) * unit, borderTop: '1px solid #3B4A61', paddingTop: 16 * unit, boxSizing: 'border-box'}}>
      <FittedText text={shot.source_label} width={contentWidth} height={(vertical ? 100 : 50) * unit}
        fontSize={24 * unit} minFontSize={18 * unit} style={{color: muted, fontWeight: 500}} />
    </div> : null}
  </AbsoluteFill>;
};
