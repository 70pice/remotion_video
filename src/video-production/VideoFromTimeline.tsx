import {useMemo, type CSSProperties} from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Freeze, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {FittedText, muted, productionFont, useLayout, white} from './adapters/layout';
import {buildCaptionPages} from './captionPages';
import {isSemanticComponent, resolveCommunityPreset, semanticProductionRegistry} from './registry';
import type {Timeline, TimelineShot, TimelineVideoProps} from './types';
import {validateTimeline} from './validation.mjs';

type CommunityMetric = {label?: string; value?: string; detail?: string};
type CommunityCrop = {x: number; y: number; width: number; height: number};

const isCommunityMetric = (value: unknown): value is CommunityMetric => Boolean(value && typeof value === 'object');
const isCommunityCrop = (value: unknown): value is CommunityCrop => Boolean(value && typeof value === 'object');

const CommunityMaterial = ({shot, durationInFrames}: {shot: TimelineShot; durationInFrames: number}) => {
  const {fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const props = shot.props as Record<string, unknown>;
  const items = Array.isArray(props.items) ? props.items.filter((item): item is string => typeof item === 'string') : [];
  const metric = isCommunityMetric(props.metric) ? props.metric : null;
  const crop = isCommunityCrop(props.asset_crop) ? props.asset_crop : null;
  const fit = props.asset_fit === 'cover' ? 'cover' : 'contain';
  const mode = props.content_mode === 'list' || props.content_mode === 'metric' || props.content_mode === 'media'
    ? props.content_mode
    : shot.asset_src ? 'media' : metric ? 'metric' : items.length ? 'list' : 'auto';
  const src = shot.asset_src ? staticFile(shot.asset_src) : null;
  const isVideo = Boolean(shot.asset_src && /\.mp4$/i.test(shot.asset_src));
  const start = typeof props.start_seconds === 'number' ? props.start_seconds : 0;
  const end = typeof props.end_seconds === 'number' ? props.end_seconds : undefined;
  const trimBefore = Math.round(start * fps);
  const trimAfter = end === undefined ? undefined : Math.round(end * fps);
  const cropStyle: CSSProperties = crop ? {
    position: 'absolute' as const,
    left: `${-crop.x / crop.width * 100}%`,
    top: `${-crop.y / crop.height * 100}%`,
    width: `${100 / crop.width}%`,
    height: `${100 / crop.height}%`,
    objectFit: 'fill' as const,
  } : {
    width: '100%',
    height: '100%',
    objectFit: fit as CSSProperties['objectFit'],
  };
  const entrance = Math.min(1, Math.max(0, frame / Math.max(1, Math.min(18, durationInFrames * 0.22))));
  const mediaHeight = (vertical ? 720 : 330) * unit;
  const panelTop = (vertical ? 228 : 92) * unit;
  const panelPadding = (vertical ? 28 : 20) * unit;
  const panelWidth = contentWidth;
  const titleHeight = (vertical ? 128 : 66) * unit;
  const bodyHeight = shot.body ? (vertical ? 114 : 56) * unit : 0;
  return <div style={{position: 'absolute', left: margin, right: margin, top: panelTop,
    opacity: entrance, transform: `translateY(${(1 - entrance) * 24 * unit}px)`,
    borderRadius: 24 * unit, overflow: 'hidden', border: `1px solid ${shot.accent_color}66`,
    background: '#07101FE8', boxShadow: `0 ${18 * unit}px ${48 * unit}px #0008`}}>
    {mode === 'media' && src ? <div style={{position: 'relative', height: mediaHeight, background: '#050A12', overflow: 'hidden'}}>
      {isVideo ? <OffthreadVideo src={src} muted trimBefore={trimBefore} trimAfter={trimAfter}
        style={{...cropStyle, display: 'block'}} /> : <Img src={src} style={{...cropStyle, display: 'block'}} />}
      <div style={{position: 'absolute', inset: 0,
        background: `linear-gradient(180deg, #050A1200 42%, #050A12D9 100%), radial-gradient(circle at 18% 16%, ${shot.accent_color}33, transparent 34%)`}} />
    </div> : null}
    <div style={{padding: panelPadding, display: 'grid', gap: 16 * unit}}>
      <div style={{height: 5 * unit, width: 74 * unit, borderRadius: 999, background: shot.accent_color}} />
      <FittedText text={shot.title} width={panelWidth - panelPadding * 2} height={titleHeight}
        fontSize={(vertical ? 54 : 34) * unit} minFontSize={18 * unit} />
      {shot.body ? <FittedText text={shot.body} width={panelWidth - panelPadding * 2} height={bodyHeight}
        fontSize={(vertical ? 28 : 18) * unit} minFontSize={14 * unit}
        style={{color: '#D6DFEC', fontWeight: 500}} /> : null}
      {mode === 'metric' && metric?.label && metric?.value ? <div style={{display: 'grid', gridTemplateColumns: '1fr auto',
        alignItems: 'end', gap: 18 * unit, padding: `${18 * unit}px ${20 * unit}px`, borderRadius: 16 * unit,
        border: `1px solid ${shot.accent_color}4D`, background: `${shot.accent_color}14`}}>
        <FittedText text={metric.label} width={(panelWidth - panelPadding * 2) * 0.46} height={48 * unit}
          fontSize={26 * unit} minFontSize={14 * unit} style={{color: muted, fontWeight: 600}} />
        <FittedText text={metric.value} width={(panelWidth - panelPadding * 2) * 0.42} height={76 * unit}
          fontSize={58 * unit} minFontSize={20 * unit} style={{color: white, textAlign: 'right'}} />
        {metric.detail ? <div style={{gridColumn: '1 / -1', color: '#C2CAD6', fontSize: 20 * unit,
          fontWeight: 500}}>{metric.detail}</div> : null}
      </div> : null}
      {mode === 'list' && items.length ? <div style={{display: 'grid', gap: 10 * unit}}>
        {items.map((item, index) => <div key={index} style={{display: 'grid', gridTemplateColumns: `${28 * unit}px 1fr`,
          alignItems: 'center', gap: 12 * unit, color: '#E9EEF4', fontSize: (vertical ? 25 : 17) * unit,
          fontWeight: 650}}>
          <span style={{width: 24 * unit, height: 24 * unit, borderRadius: 999, background: shot.accent_color,
            color: '#08111F', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14 * unit, fontWeight: 800}}>{index + 1}</span>
          <span>{item}</span>
        </div>)}
      </div> : null}
      {shot.source_label ? <div style={{fontSize: 17 * unit, color: muted, fontWeight: 600}}>{shot.source_label}</div> : null}
    </div>
  </div>;
};

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
      transform: `translate(-50%, -50%) scale(${scale})`, transformOrigin: 'center', overflow: 'hidden',
      filter: shot.asset_src || Object.keys(shot.props).length ? 'saturate(0.8) brightness(0.55)' : undefined}}>
      <Sequence width={preset.width} height={preset.height}>{content}</Sequence>
    </div>
    {shot.asset_src || Object.keys(shot.props).length ? <CommunityMaterial shot={shot}
      durationInFrames={shot.end_frame - shot.start_frame} /> : <div style={{position: 'absolute', left: margin, right: margin, top: (vertical ? 180 : 112) * unit,
      padding: `${18 * unit}px ${24 * unit}px`, borderRadius: 18 * unit, background: '#07101FD9',
      border: '1px solid #FFFFFF2E', boxSizing: 'border-box'}}>
      <FittedText text={shot.title} width={contentWidth - 48 * unit} height={titleHeight}
        fontSize={(vertical ? 52 : 34) * unit} minFontSize={18 * unit} />
      {shot.body ? <FittedText text={shot.body} width={contentWidth - 48 * unit} height={bodyHeight}
        fontSize={(vertical ? 30 : 21) * unit} minFontSize={15 * unit}
        style={{color: '#D6DFEC', fontWeight: 500, marginTop: 8 * unit}} /> : null}
    </div>}
  </AbsoluteFill>;
};

const Scene = ({shot, videoMetadata}: {shot: TimelineShot; videoMetadata?: TimelineVideoProps['videoMetadata']}) => {
  const {unit, vertical, margin} = useLayout();
  if (!isSemanticComponent(shot.component_id)) return <CommunityPresetScene shot={shot} />;
  const Adapter = semanticProductionRegistry[shot.component_id];
  return <AbsoluteFill style={{padding: `${(vertical ? 180 : 125) * unit}px ${margin}px ${(vertical ? 460 : 305) * unit}px`,
    background: `radial-gradient(ellipse at 110% 5%, ${shot.accent_color}19, transparent 55%), #111C2E`}}>
    <Adapter shot={shot} durationInFrames={shot.end_frame - shot.start_frame} videoMetadata={videoMetadata} />
  </AbsoluteFill>;
};

const Captions = ({timeline}: {timeline: Timeline}) => {
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const milliseconds = frame / timeline.fps * 1000;
  const captionPages = useMemo(() => buildCaptionPages(timeline.captions, {
    boundaries: timeline.shots.map((shot) => ({
      start_ms: shot.start_frame / timeline.fps * 1000,
      end_ms: shot.end_frame / timeline.fps * 1000,
    })),
  }), [timeline]);
  const caption = captionPages.find((item) => milliseconds >= item.start_ms && milliseconds < item.end_ms);
  if (!caption) return null;
  const height = (vertical ? 200 : 110) * unit;
  return <div style={{position: 'absolute', left: margin, right: margin, bottom: (vertical ? 280 : 150) * unit,
    height, padding: `${16 * unit}px ${24 * unit}px`, boxSizing: 'border-box', background: '#07101FEF',
    borderRadius: 20 * unit, border: '1px solid #41536E', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
    <FittedText text={caption.text} width={contentWidth - 48 * unit} height={height - 32 * unit}
      fontSize={46 * unit} minFontSize={30 * unit} style={{textAlign: 'center'}} />
  </div>;
};

export const VideoFromTimeline = ({timeline: input, videoMetadata}: TimelineVideoProps) => {
  const timeline = useMemo(() => validateTimeline(input), [input]);
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const shotIndex = timeline.shots.findIndex((shot) => frame >= shot.start_frame && frame < shot.end_frame);
  const shot = timeline.shots[Math.max(0, shotIndex)];
  return <AbsoluteFill style={{background: '#111C2E', color: white, fontFamily: productionFont}}>
    {timeline.audio_src ? <Audio src={staticFile(timeline.audio_src)} /> : null}
    {timeline.shots.map((item) => <Sequence key={item.shot_id} from={item.start_frame}
      durationInFrames={item.end_frame - item.start_frame} name={`${item.component_id} / ${item.title}`}>
      <Scene shot={item} videoMetadata={videoMetadata} />
    </Sequence>)}
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
