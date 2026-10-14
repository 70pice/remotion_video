import {useMemo, type CSSProperties} from 'react';
import {Audio} from '@remotion/media';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {CuratedScene} from '../components/component-horizontal/curated/CuratedScene';
import {FittedText, LayoutComponentSample, LayoutHeaderHeight, muted, productionFont, useLayout, white} from './adapters/layout';
import {buildCaptionPages} from './captionPages';
import {communityMaterialSurfaceForComponentId} from './communityMaterial';
import {curatedScenePropsForShot, materializedCommunityComponentIdSet} from './curatedMaterial';
import {PhoneFrameMaterial} from './PhoneFrameMaterial';
import {MaterialFocus} from './MaterialFocus';
import {isNoMaterialSet, noMaterialSetGeometry} from './noMaterialSetGeometry';
import {isRichMaterialSet} from './RichMaterialContract';
import {RichMaterialScene} from './RichMaterialScene';
import {RichNoMaterialScene} from './RichNoMaterialScene';
import {isProductionComponentSetDesign, ProductionComponentSetScene} from './ProductionComponentSetScene';
import {focusCompositionLayout, guidedPhoneTitleTop, guidedTitleHeight} from './focusGeometry';
import {tutorialStepAt, type TutorialStep, type TutorialSourceSize} from './phoneTutorial';
import {hasNativeMediaScene, renderNativeMediaScene} from './NativeMediaScenes';
import {SnapcnNativeTitle, snapcnNativeTitleIds} from './SnapcnNativeTitles';
import {isTalkcraftNativeTitleId, TalkcraftNativeTitle} from './TalkcraftNativeTitles';
import {isTalkcraftNativeMediaId, TalkcraftNativeMedia} from './TalkcraftNativeMedia';
import {isSemanticComponent, semanticProductionRegistry} from './registry';
import type {Timeline, TimelineShot, TimelineVideoProps} from './types';
import {validateTimeline} from './validation.mjs';

type CommunityMetric = {label?: string; value?: string; detail?: string};
type CommunityCrop = {x: number; y: number; width: number; height: number};

const isCommunityMetric = (value: unknown): value is CommunityMetric => Boolean(value && typeof value === 'object');
const isCommunityCrop = (value: unknown): value is CommunityCrop => Boolean(value && typeof value === 'object');

const CommunityNativeMaterial = ({shot, durationInFrames}: {shot: TimelineShot; durationInFrames: number}) => {
  const {fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth} = useLayout();
  const props = shot.props as Record<string, unknown>;
  const surface = communityMaterialSurfaceForComponentId(shot.component_id);
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
  const mediaHeight = (vertical ? 660 : 300) * unit;
  const panelTop = (vertical ? 214 : 82) * unit;
  const panelPadding = (vertical ? 28 : 20) * unit;
  const panelInset = surface === 'pip' && vertical && !shot.layers?.length ? 84 * unit : 0;
  const panelWidth = contentWidth - panelInset * 2;
  const titleHeight = (vertical ? 128 : 66) * unit;
  const bodyHeight = shot.body ? (vertical ? 114 : 56) * unit : 0;
  const media = (style: CSSProperties = {}) => mode === 'media' && src ? <div style={{position: 'relative',
    height: mediaHeight, background: '#050A12', overflow: 'hidden', ...style}}>
    {isVideo ? <OffthreadVideo src={src} muted trimBefore={trimBefore} trimAfter={trimAfter}
      style={{...cropStyle, display: 'block'}} /> : <Img src={src} style={{...cropStyle, display: 'block'}} />}
  </div> : null;
  const metricBlock = mode === 'metric' && metric?.label && metric?.value ? <div style={{display: 'grid', gridTemplateColumns: '1fr auto',
    alignItems: 'end', gap: 18 * unit, padding: `${18 * unit}px ${20 * unit}px`, borderRadius: 16 * unit,
    border: `1px solid ${shot.accent_color}4D`, background: `${shot.accent_color}14`}}>
    <FittedText text={metric.label} width={(panelWidth - panelPadding * 2) * 0.46} height={48 * unit}
      fontSize={26 * unit} minFontSize={14 * unit} style={{color: muted, fontWeight: 600}} />
    <FittedText text={metric.value} width={(panelWidth - panelPadding * 2) * 0.42} height={76 * unit}
      fontSize={58 * unit} minFontSize={20 * unit} style={{color: white, textAlign: 'right'}} />
    {metric.detail ? <div style={{gridColumn: '1 / -1', color: '#C2CAD6', fontSize: 20 * unit,
      fontWeight: 500}}>{metric.detail}</div> : null}
  </div> : null;
  const listBlock = mode === 'list' && items.length ? <div style={{display: 'grid', gap: 10 * unit}}>
    {items.map((item, index) => <div key={index} style={{display: 'grid', gridTemplateColumns: `${28 * unit}px 1fr`,
      alignItems: 'center', gap: 12 * unit, color: '#E9EEF4', fontSize: (vertical ? 25 : 17) * unit,
      fontWeight: 650}}>
      <span style={{width: 24 * unit, height: 24 * unit, borderRadius: 999, background: shot.accent_color,
        color: '#08111F', display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 14 * unit, fontWeight: 800}}>{index + 1}</span>
      <span>{item}</span>
    </div>)}
  </div> : null;
  const primaryCopy = <div style={{padding: panelPadding, display: 'grid', gap: 16 * unit}}>
    <div style={{height: 5 * unit, width: 74 * unit, borderRadius: 999, background: shot.accent_color}} />
    <FittedText text={shot.title} width={panelWidth - panelPadding * 2} height={titleHeight}
      fontSize={(vertical ? 54 : 34) * unit} minFontSize={18 * unit} />
    {shot.body ? <FittedText text={shot.body} width={panelWidth - panelPadding * 2} height={bodyHeight}
      fontSize={(vertical ? 28 : 18) * unit} minFontSize={14 * unit}
      style={{color: '#D6DFEC', fontWeight: 500}} /> : null}
    {metricBlock}
    {listBlock}
    {shot.source_label ? <div style={{fontSize: 17 * unit, color: muted, fontWeight: 600}}>{shot.source_label}</div> : null}
  </div>;
  const thumbnailRail = surface === 'gallery' && src ? <div style={{display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 * unit, padding: `${0}px ${panelPadding}px ${panelPadding}px`}}>
    {[0, 1, 2].map((index) => <div key={index} style={{height: (vertical ? 92 : 54) * unit,
      borderRadius: 12 * unit, background: `${shot.accent_color}${index === 1 ? '33' : '1F'}`,
      border: `1px solid ${shot.accent_color}${index === 1 ? '99' : '44'}`}} />)}
  </div> : null;
  const shellStyle: CSSProperties = {position: 'absolute', left: margin + panelInset, right: margin + panelInset, top: panelTop,
    opacity: entrance, transform: `translateY(${(1 - entrance) * 24 * unit}px)`,
    borderRadius: surface === 'pip' ? 34 * unit : 24 * unit, overflow: 'hidden',
    border: `1px solid ${shot.accent_color}66`, background: '#07101FE8',
    boxShadow: `0 ${18 * unit}px ${48 * unit}px #0008`};
  if (vertical && shot.layers?.length) {
    const hasEmphasis = shot.layers.some((layer) => layer.role === 'emphasis');
    return <div style={{...shellStyle, top: 520 * unit}}>
      {media({height: (hasEmphasis ? 570 : 790) * unit})}
      {!src ? primaryCopy : null}
      {metricBlock}
      {listBlock}
    </div>;
  }
  if (surface === 'reveal') {
    shellStyle.clipPath = vertical ? 'polygon(0 8%, 92% 0, 100% 90%, 8% 100%)' : 'polygon(0 0, 94% 8%, 100% 100%, 6% 92%)';
  }
  if (surface === 'workspace' || surface === 'device') {
    return <div style={shellStyle}>
      {media({height: (vertical ? 520 : 246) * unit, borderBottom: '1px solid #FFFFFF14'})}
      {primaryCopy}
    </div>;
  }
  if (surface === 'gallery') {
    return <div style={shellStyle}>
      {media({height: (vertical ? 590 : 270) * unit})}
      {thumbnailRail}
      {primaryCopy}
    </div>;
  }
  if (surface === 'pip') {
    return <div style={shellStyle}>
      {media({height: (vertical ? 720 : 310) * unit, borderRadius: `${28 * unit}px ${28 * unit}px 0 0`})}
      {primaryCopy}
    </div>;
  }
  if (surface === 'data') {
    return <div style={shellStyle}>
      {src && vertical ? media({height: 360 * unit, borderBottom: '1px solid #FFFFFF14'}) : null}
      <div style={{display: 'grid', gridTemplateColumns: src && !vertical ? '0.9fr 1.1fr' : '1fr', gap: 0}}>
        {src && !vertical ? media({height: (vertical ? 520 : 330) * unit}) : null}
        <div>{primaryCopy}</div>
      </div>
    </div>;
  }
  if (surface === 'text') {
    return <div style={{...shellStyle, background: `linear-gradient(135deg, ${shot.accent_color}2B, #07101FF2 42%, #050A12F5)`}}>
      {src ? media({height: (vertical ? (shot.body ? 740 : 880) : 158) * unit}) : null}
      {primaryCopy}
    </div>;
  }
  if (surface === 'reveal' || surface === 'motion') {
    return <div style={shellStyle}>
      {media({height: (vertical ? 630 : 286) * unit})}
      <div style={{position: 'absolute', inset: 0, border: `${2 * unit}px solid ${shot.accent_color}`,
        pointerEvents: 'none'}} />
      {primaryCopy}
    </div>;
  }
  return <div style={shellStyle}>
    {media()}
    {primaryCopy}
  </div>;
};

const CommunityPresetScene = ({shot}: {shot: TimelineShot}) => {
  const {vertical, unit, componentSample} = useLayout();
  if (shot.component_id === 'Snapcn-PhoneFrame') {
    return <PhoneFrameMaterial shot={shot} />;
  }
  if (isTalkcraftNativeMediaId(shot.component_id)) {
    return <div style={{position: 'absolute', width: 1080, height: 1920,
      transform: `scale(${unit})`, transformOrigin: 'top left'}}>
      <Sequence width={1080} height={1920} durationInFrames={shot.end_frame - shot.start_frame}>
        <TalkcraftNativeMedia shot={shot} />
      </Sequence>
    </div>;
  }
  if (hasNativeMediaScene(shot.component_id)) {
    return <div style={{position: 'absolute', width: 1080, height: 1920,
      transform: `scale(${unit})`, transformOrigin: 'top left'}}>
      <Sequence width={1080} height={1920} durationInFrames={shot.end_frame - shot.start_frame}>
        {renderNativeMediaScene(shot, {layout: vertical ? 'portrait' : 'landscape', componentSample})}
      </Sequence>
    </div>;
  }
  if (materializedCommunityComponentIdSet.has(shot.component_id)) {
    return <CuratedScene {...curatedScenePropsForShot(shot, vertical)} />;
  }
  return <AbsoluteFill style={{background: '#050A12', overflow: 'hidden'}}>
    <CommunityNativeMaterial shot={shot} durationInFrames={shot.end_frame - shot.start_frame} />
  </AbsoluteFill>;
};

export const VideoFromTimeline = ({timeline: input, videoMetadata}: TimelineVideoProps) => {
  const timeline = useMemo(() => validateTimeline(input), [input]);
  const presentation = (timeline as Timeline & {presentation?: 'production' | 'component_sample'}).presentation ?? 'production';
  return <LayoutComponentSample.Provider value={presentation === 'component_sample'}>
    <TimelineRender timeline={timeline} videoMetadata={videoMetadata} />
  </LayoutComponentSample.Provider>;
};

const guidedCopyTop = (shot: TimelineShot, step: TutorialStep) => shot.props.tutorial_steps ? guidedPhoneTitleTop :
  focusCompositionLayout(shot.props.focus_source_size as TutorialSourceSize, step.target, /\.mp4$/i.test(shot.asset_src ?? '')).titleTop;

const ComponentLayers = ({shot}: {shot: TimelineShot}) => {
  const {unit, vertical, componentSample} = useLayout();
  const frame = useCurrentFrame();
  const steps = (shot.props.tutorial_steps ?? shot.props.focus_steps) as TutorialStep[] | undefined;
  const activeStep = steps ? tutorialStepAt(steps, frame) : undefined;
  return <>{shot.layers?.map((layer, index) => {
    if (activeStep && layer.component_id === 'Snapcn-TextReveal' && layer.role === 'title') {
      const top = guidedCopyTop(shot, activeStep);
      return <Sequence key={`${index}-${activeStep.start_frame}`} from={activeStep.start_frame}
        durationInFrames={activeStep.end_frame - activeStep.start_frame} name={activeStep.instruction}>
        <div style={{position: 'absolute', left: 64 * unit, top: top * unit, width: 952, height: guidedTitleHeight,
          transform: `scale(${unit})`, transformOrigin: 'top left'}}>
          <Sequence width={952} height={guidedTitleHeight}>
            <SnapcnNativeTitle tutorial layer={{...layer, title: activeStep.instruction}} />
          </Sequence>
        </div>
      </Sequence>;
    }
    const layerShot: TimelineShot = {...shot, component_id: layer.component_id, title: layer.title,
      body: layer.body, accent_color: layer.accent_color, props: layer.props,
      asset_src: null, source_label: '', layers: [], start_frame: 0,
      end_frame: layer.end_frame - layer.start_frame};
    const textOnly = componentSample && isNoMaterialSet(shot.props.component_set);
    const box = textOnly ? noMaterialSetGeometry[layer.role] : undefined;
    const top = box ? box.y * unit : (vertical ? componentSample ? layer.role === 'title' ? 120 : 1480 : layer.role === 'title' ? 170 : 1030 : layer.role === 'title' ? 80 : 550) * unit;
    if (snapcnNativeTitleIds.some((id) => id === layer.component_id)) {
      const sourceHeight = box?.height ?? (componentSample && layer.role === 'emphasis' ? 300 : 360);
      return <Sequence key={index} from={layer.start_frame} durationInFrames={layer.end_frame - layer.start_frame}
        name={`${layer.role} / ${layer.component_id}`}>
        <div style={{position: 'absolute', left: 64 * unit, top, width: 960, height: sourceHeight,
          overflow: componentSample ? 'hidden' : undefined, transform: `scale(${unit * 0.99})`, transformOrigin: 'top left'}}>
          <Sequence width={960} height={sourceHeight}><SnapcnNativeTitle layer={layer} textOnly={textOnly} /></Sequence>
        </div>
      </Sequence>;
    }
    if (isTalkcraftNativeTitleId(layer.component_id)) {
      const sampleEmphasis = componentSample && layer.role === 'emphasis';
      const translateY = sampleEmphasis ? top : top - 180 * unit;
      return <Sequence key={index} from={layer.start_frame} durationInFrames={layer.end_frame - layer.start_frame}
        name={`${layer.role} / ${layer.component_id}`}>
        <div style={{position: 'absolute', width: 1080, height: 1920,
          transform: `translateY(${translateY}px) scale(${unit})`, transformOrigin: 'top left'}}>
          <Sequence width={1080} height={1920}>
            <TalkcraftNativeTitle shot={layerShot} layerRole={layer.role} componentSample={componentSample} />
          </Sequence>
        </div>
      </Sequence>;
    }
    throw new Error(`No native component layer binding: ${layer.component_id}`);
  })}</>;
};

const Scene = ({shot, videoMetadata}: {shot: TimelineShot; videoMetadata?: TimelineVideoProps['videoMetadata']}) => {
  const {unit, vertical, margin, componentSample} = useLayout();
  if (componentSample && isRichMaterialSet(shot.props.component_set) && shot.props.composition === 'rich') {
    return <RichMaterialScene shot={shot} />;
  }
  if (componentSample && isNoMaterialSet(shot.props.component_set) && shot.props.composition === 'rich') {
    return <RichNoMaterialScene shot={shot} />;
  }
  if (!componentSample && isProductionComponentSetDesign((shot as TimelineShot & {set_design?: unknown}).set_design)) {
    return <ProductionComponentSetScene shot={shot} />;
  }
  if (!isSemanticComponent(shot.component_id)) return <CommunityPresetScene shot={shot} />;
  if (shot.props.focus_steps) return <MaterialFocus shot={shot} />;
  const Adapter = semanticProductionRegistry[shot.component_id];
  if (componentSample && isNoMaterialSet(shot.props.component_set)) {
    const box = noMaterialSetGeometry.main;
    return <div style={{position: 'absolute', left: box.x * unit, top: box.y * unit,
      width: box.width * unit, height: box.height * unit}}>
      <Adapter shot={shot} durationInFrames={shot.end_frame - shot.start_frame} videoMetadata={videoMetadata} />
    </div>;
  }
  const titleHeight = vertical && shot.layers?.some((layer) => layer.role === 'title') ? 400 : 0;
  const paddingTop = (vertical && componentSample ? 600 : vertical ? 180 : 125) * unit;
  const paddingBottom = (vertical && componentSample ? 470 : vertical ? 460 : 305) * unit;
  return <AbsoluteFill style={{padding: `${paddingTop}px ${margin}px ${paddingBottom}px`,
    background: `radial-gradient(ellipse at 110% 5%, ${shot.accent_color}19, transparent 55%), #111C2E`}}>
    <LayoutHeaderHeight.Provider value={titleHeight}>
      <Adapter shot={shot} durationInFrames={shot.end_frame - shot.start_frame} videoMetadata={videoMetadata} />
    </LayoutHeaderHeight.Provider>
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

const TimelineRender = ({timeline, videoMetadata}: TimelineVideoProps) => {
  const frame = useCurrentFrame();
  const {unit, vertical, margin, contentWidth, componentSample} = useLayout();
  const shotIndex = timeline.shots.findIndex((shot) => frame >= shot.start_frame && frame < shot.end_frame);
  const shot = timeline.shots[Math.max(0, shotIndex)];
  const sourceFooterStyle: CSSProperties = componentSample && vertical
    ? {top: 1810 * unit, height: 72 * unit}
    : {bottom: (vertical ? 110 : 52) * unit, height: (vertical ? 120 : 68) * unit};
  const guided = Array.isArray(shot.props.focus_steps) || Array.isArray(shot.props.tutorial_steps);
  const textOnly = componentSample && isNoMaterialSet(shot.props.component_set);
  const richMaterial = componentSample && isRichMaterialSet(shot.props.component_set) && shot.props.composition === 'rich';
  const richTextOnly = textOnly && shot.props.composition === 'rich';
  const focusStep = Array.isArray(shot.props.focus_steps) ? tutorialStepAt(shot.props.focus_steps as TutorialStep[], frame - shot.start_frame) : undefined;
  return <AbsoluteFill style={{background: guided || textOnly || richMaterial ? 'radial-gradient(ellipse at 30% 5%, #12324A, transparent 55%), #07101F' : '#111C2E', color: white, fontFamily: productionFont}}>
    {!componentSample && timeline.audio_src ? <Audio src={staticFile(timeline.audio_src)} /> : null}
    {timeline.shots.map((item) => <Sequence key={item.shot_id} from={item.start_frame}
      durationInFrames={item.end_frame - item.start_frame} name={`${item.component_id} / ${item.title}`}>
      <Scene shot={item} videoMetadata={videoMetadata} />
      {item.props.composition === 'rich' ? null : <ComponentLayers shot={item} />}
    </Sequence>)}
    {focusStep && !richMaterial ? <div style={{position: 'absolute', left: 64 * unit, top: (guidedCopyTop(shot, focusStep) + guidedTitleHeight + 12) * unit,
      fontSize: 26 * unit, color: '#9CAEC5', lineHeight: 1.3}}>
      {shot.component_id === 'video' ? '模拟界面 · 操作演示' : shot.component_id === 'evidence' ? '模拟资料 · 非真实证据'
        : shot.component_id === 'image_focus' ? '关系示意 · 非实际运行记录' : 'AI 生成插画 · 作品演示'}
    </div> : null}
    {textOnly && !richTextOnly && !['B01', 'B02'].includes(String(shot.props.component_set)) && shot.body ? <div style={{position: 'absolute', left: noMaterialSetGeometry.body.x * unit,
      top: noMaterialSetGeometry.body.y * unit, width: noMaterialSetGeometry.body.width * unit}}>
      <FittedText text={shot.body} width={noMaterialSetGeometry.body.width * unit} height={noMaterialSetGeometry.body.height * unit}
        fontSize={42 * unit} minFontSize={28 * unit} style={{fontWeight: 500, color: white}} />
    </div> : null}
    {textOnly && !richTextOnly ? <div style={{position: 'absolute', left: noMaterialSetGeometry.identity.x * unit,
      top: noMaterialSetGeometry.identity.y * unit, color: muted, fontSize: 24 * unit}}>
      {shot.props.component_set === 'B04' ? '演示数字 · 非实际统计' : '演示文案 · 无外部素材'}
    </div> : null}
    {!textOnly && !richMaterial && !Array.isArray(shot.props.tutorial_steps) && !Array.isArray(shot.props.focus_steps) ? <div style={{position: 'absolute', top: (vertical ? 135 : 90) * unit, left: margin, right: margin,
      height: 3 * unit, background: '#334158'}}>
      <div style={{height: '100%', width: `${(frame + 1) / timeline.duration_in_frames * 100}%`, background: shot.accent_color}} />
    </div> : null}
    {!componentSample ? <Captions timeline={timeline} /> : null}
    {shot.source_label && !richMaterial ? <div style={{position: 'absolute', ...sourceFooterStyle, left: margin,
      right: margin, borderTop: '1px solid #3B4A61', paddingTop: 16 * unit, boxSizing: 'border-box'}}>
      <FittedText text={shot.source_label} width={contentWidth} height={(vertical ? 100 : 50) * unit}
        fontSize={24 * unit} minFontSize={18 * unit} style={{color: muted, fontWeight: 500}} />
    </div> : null}
  </AbsoluteFill>;
};
