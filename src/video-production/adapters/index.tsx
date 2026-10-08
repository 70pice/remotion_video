import {getImageDimensions} from '@remotion/media-utils';
import {useEffect, useState} from 'react';
import {cancelRender, continueRender, delayRender, Img, interpolate, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {Highlight, StepItem} from '../types';
import {Body, Card, CuedMotion, FittedText, Motion, SceneHeader, clamp, contrastingInk, gentleZoom, muted, useLayout, white} from './layout';
import type {AdapterProps} from './layout';
import {resolveVideoCropGeometry} from './videoGeometry';
import type {NormalizedCrop} from './videoGeometry';
import {ImageFocusViewport} from './ImageFocusViewport';
import type {ImageFocusCue} from './imageFocusGeometry';
export {DataAdapter} from './data';

export const TitleAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight} = useLayout();
  const eyebrow = shot.props.eyebrow as string | undefined;
  const textBudget = contentHeight - (eyebrow ? 100 : 0) * unit - 93 * unit;
  const titleHeight = textBudget * (shot.body ? 0.59 : 0.98);
  const bodyHeight = textBudget * 0.41;
  return <div style={{height: contentHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    {eyebrow ? <Motion><div style={{fontSize: 28 * unit, color: muted, marginBottom: 50 * unit, letterSpacing: 2 * unit}}>{eyebrow}</div></Motion> : null}
    <Motion><FittedText text={shot.title} width={contentWidth} height={titleHeight}
      fontSize={126 * unit} minFontSize={42 * unit} lineHeight={1.22}
      preferSingleLine={/^[A-Za-z0-9][A-Za-z0-9._+:/-]*$/.test(shot.title)} /></Motion>
    <Motion delay={5}><div style={{height: 9 * unit, width: 136 * unit, background: shot.accent_color, margin: `${42 * unit}px 0`}} />
      <Body text={shot.body} height={bodyHeight} />
    </Motion>
  </div>;
};

export const KeywordAdapter = ({shot}: AdapterProps) => {
  const frame = useCurrentFrame();
  const {unit, contentWidth, contentHeight, vertical, durationInFrames} = useLayout();
  const keyword = (shot.props.keyword as string | undefined) ?? shot.title;
  const reveal = interpolate(frame, [0, Math.max(1, Math.min(14, durationInFrames * 0.25))], [0, 1], clamp);
  const contextHeight = (vertical ? 80 : 60) * unit;
  const textBudget = contentHeight - contextHeight - 156 * unit;
  return <div style={{height: contentHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    <Motion style={{marginBottom: 40 * unit}}><FittedText text={keyword === shot.title ? '核心观点' : shot.title}
      width={contentWidth} height={contextHeight} fontSize={30 * unit} minFontSize={18 * unit} style={{color: muted}} /></Motion>
    <Motion delay={3}><div style={{position: 'relative', padding: `${32 * unit}px ${28 * unit}px`, marginLeft: -28 * unit}}>
      <div style={{position: 'absolute', inset: 0, background: shot.accent_color, transform: `scaleX(${reveal})`, transformOrigin: 'left', borderRadius: 12 * unit}} />
      <FittedText text={keyword} width={contentWidth - 56 * unit} height={textBudget * (shot.body ? 0.58 : 0.98)}
        fontSize={128 * unit} minFontSize={40 * unit} lineHeight={1.18}
        preferSingleLine={/^[A-Za-z0-9][A-Za-z0-9._+:/-]*$/.test(keyword)}
        style={{position: 'relative', color: contrastingInk(shot.accent_color)}} />
    </div></Motion>
    <Motion delay={8} style={{marginTop: 52 * unit}}><Body text={shot.body} height={textBudget * 0.42} /></Motion>
  </div>;
};

type ImageDimensions = {width: number; height: number};

const useImageDimensions = (src: string | null, enabled: boolean): ImageDimensions | null => {
  const [dimensions, setDimensions] = useState<ImageDimensions | null>(null);
  useEffect(() => {
    if (!enabled || !src) {
      setDimensions(null);
      return;
    }
    setDimensions(null);
    const handle = delayRender(`Loading image dimensions: ${src}`);
    let active = true;
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      continueRender(handle);
    };
    getImageDimensions(src)
      .then((loaded) => {
        if (active) setDimensions({width: loaded.width, height: loaded.height});
        finish();
      })
      .catch((error) => {
        if (settled) return;
        settled = true;
        if (active) cancelRender(error);
        else continueRender(handle);
      });
    return () => {
      active = false;
      finish();
    };
  }, [enabled, src]);
  return dimensions;
};

const ImageCard = ({shot, focus, durationInFrames}: AdapterProps & {focus: boolean}) => {
  const frame = useCurrentFrame();
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight} = useLayout();
  const cues = shot.props.focus_cues as ImageFocusCue[] | undefined;
  const cueLabel = cues?.filter((cue) => cue.frame <= frame).at(-1)?.label;
  const labelHeight = cues?.some((cue) => cue.label) ? 58 * unit : 0;
  const mediaHeight = contentHeight - headerHeight - bodyHeight - 58 * unit - labelHeight;
  const highlight = shot.props.highlight as Highlight | undefined;
  const focalX = (shot.props.focal_x as number | undefined) ?? 0.5;
  const focalY = (shot.props.focal_y as number | undefined) ?? 0.5;
  const crop = focus ? shot.props.crop as NormalizedCrop | undefined : undefined;
  const imageSrc = shot.asset_src ? staticFile(shot.asset_src) : null;
  const dimensions = useImageDimensions(imageSrc, Boolean(crop || cues));
  const cropGeometry = crop && dimensions ? resolveVideoCropGeometry({
    viewportWidth: contentWidth - 30 * unit,
    viewportHeight: mediaHeight,
    metadata: dimensions,
    crop,
    fit: 'contain',
  }) : null;
  return <>
    <SceneHeader shot={shot} />
    <Motion delay={4}>
      <Card accent={shot.accent_color} style={{padding: 14 * unit, overflow: 'hidden'}}>
        {labelHeight ? <div style={{height: labelHeight, display: 'flex', alignItems: 'center',
          paddingLeft: 12 * unit, fontSize: 27 * unit, fontWeight: 700, color: white}}>{cueLabel}</div> : null}
        <div style={{position: 'relative', height: mediaHeight, overflow: 'hidden', borderRadius: 16 * unit,
          display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#F1F3F7'}}>
          {cues && dimensions ? <ImageFocusViewport src={imageSrc!} cues={cues} metadata={dimensions}
            width={contentWidth - 30 * unit} height={mediaHeight} accent={shot.accent_color} unit={unit} />
            : focus && cropGeometry ? <div style={{position: 'absolute', left: cropGeometry.window.left, top: cropGeometry.window.top,
            width: cropGeometry.window.width, height: cropGeometry.window.height, overflow: 'hidden'}}>
            <Img src={imageSrc!} style={{position: 'absolute', left: cropGeometry.media.left, top: cropGeometry.media.top,
              width: cropGeometry.media.width, height: cropGeometry.media.height, objectFit: 'fill', display: 'block'}} />
          </div> : focus ? <Img src={imageSrc!} style={{width: '100%', height: '100%', objectFit: 'cover',
            objectPosition: `${focalX * 100}% ${focalY * 100}%`,
            transform: `scale(${gentleZoom(frame, durationInFrames)})`,
            transformOrigin: `${focalX * 100}% ${focalY * 100}%`}} /> :
            <div style={{position: 'relative', display: 'inline-flex'}}>
              <Img src={imageSrc!} style={{display: 'block', width: 'auto', height: 'auto',
                maxWidth: contentWidth - 30 * unit, maxHeight: mediaHeight}} />
              {highlight ? <div style={{position: 'absolute', left: `${highlight.x * 100}%`, top: `${highlight.y * 100}%`,
                width: `${highlight.width * 100}%`, height: `${highlight.height * 100}%`, boxSizing: 'border-box',
                border: `${4 * unit}px solid ${shot.accent_color}`, background: shot.accent_color + '18',
                opacity: interpolate(frame, [0, Math.max(1, Math.min(20, durationInFrames * 0.3))], [0, 1], clamp)}} /> : null}
            </div>}
        </div>
      </Card>
    </Motion>
    <Motion delay={7} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion>
  </>;
};

export const EvidenceAdapter = (props: AdapterProps) => <ImageCard {...props} focus={false} />;
export const ImageFocusAdapter = (props: AdapterProps) => <ImageCard {...props} focus />;

type VideoCrop = {x: number; y: number; width: number; height: number};

export const VideoAdapter = ({shot, videoMetadata}: AdapterProps) => {
  const {fps} = useVideoConfig();
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight, vertical} = useLayout();
  const metadata = shot.asset_src ? videoMetadata?.[shot.asset_src] : undefined;
  if (!metadata) throw new Error(`Missing video metadata for ${shot.asset_src ?? 'video asset'}`);
  const fit = (shot.props.fit as 'contain' | 'cover' | undefined) ?? 'contain';
  const crop = shot.props.crop as VideoCrop | undefined;
  const start = (shot.props.start_seconds as number | undefined) ?? 0;
  const end = shot.props.end_seconds as number | undefined;
  const titleHeight = vertical ? Math.min(headerHeight, 200 * unit) : headerHeight;
  const textHeight = shot.body ? Math.min(bodyHeight, (vertical ? 130 : 95) * unit) : 0;
  const mediaHeight = contentHeight - titleHeight - textHeight - (shot.body ? 42 : 30) * unit;
  const frameWidth = contentWidth - 28 * unit;
  const frameHeight = mediaHeight;
  const geometry = resolveVideoCropGeometry({
    viewportWidth: frameWidth,
    viewportHeight: frameHeight,
    metadata,
    crop,
    fit,
  });
  const trimBefore = Math.round(start * fps);
  const trimAfter = end === undefined ? undefined : Math.round(end * fps);
  return <>
    <Motion style={{height: titleHeight, flexShrink: 0}}>
      <div style={{height: 6 * unit, width: 72 * unit, background: shot.accent_color, marginBottom: 18 * unit}} />
      <FittedText text={shot.title} width={contentWidth} height={titleHeight - 46 * unit}
        fontSize={(vertical ? 74 : 70) * unit} minFontSize={32 * unit} />
    </Motion>
    <Motion delay={4}>
      <Card accent={shot.accent_color} style={{padding: 14 * unit, overflow: 'hidden'}}>
        <div style={{position: 'relative', height: mediaHeight, overflow: 'hidden', borderRadius: 16 * unit,
          background: '#050A12', boxShadow: `0 0 0 ${1 * unit}px #FFFFFF12 inset`,
          display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{position: 'absolute', left: geometry.window.left, top: geometry.window.top,
            width: geometry.window.width, height: geometry.window.height, overflow: 'hidden'}}>
            <OffthreadVideo
              src={staticFile(shot.asset_src!)}
              muted
              trimBefore={trimBefore}
              trimAfter={trimAfter}
              style={{position: 'absolute', left: geometry.media.left, top: geometry.media.top,
                width: geometry.media.width, height: geometry.media.height, objectFit: 'fill', display: 'block'}}
            />
          </div>
        </div>
      </Card>
    </Motion>
    {shot.body ? <Motion delay={7} style={{marginTop: 18 * unit}}><Body text={shot.body} height={textHeight} /></Motion> : null}
  </>;
};

export const ComparisonAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, vertical, headerHeight, bodyHeight} = useLayout();
  const cardWidth = vertical ? contentWidth : (contentWidth - 24 * unit) / 2;
  const availableHeight = contentHeight - headerHeight - (shot.body ? bodyHeight + 24 * unit : 0);
  const cardHeight = (availableHeight - (vertical ? 24 * unit : 0)) / (vertical ? 2 : 1);
  const sides = [
    {title: shot.props.left_title as string, body: shot.props.left_body as string},
    {title: shot.props.right_title as string, body: shot.props.right_body as string},
  ];
  return <>
    <SceneHeader shot={shot} />
    <div style={{display: 'flex', flexDirection: vertical ? 'column' : 'row', gap: 24 * unit}}>
      {sides.map((side, index) => <CuedMotion key={index} delay={index * 5} style={{width: cardWidth}}
        revealFrame={index === 1 ? shot.props.right_reveal_frame as number | undefined : undefined}>
        <Card accent={index === 1 ? shot.accent_color : undefined} style={{height: cardHeight}}>
          <div style={{fontSize: 24 * unit, color: muted, marginBottom: 20 * unit}}>{index === 0 ? 'A' : 'B'}</div>
          <FittedText text={side.title} width={cardWidth - 68 * unit} height={(cardHeight - 146 * unit) * 0.4}
            fontSize={58 * unit} minFontSize={26 * unit} />
          <Body text={side.body} width={cardWidth - 68 * unit} height={(cardHeight - 146 * unit) * 0.6} style={{marginTop: 24 * unit}} />
        </Card>
      </CuedMotion>)}
    </div>
    {shot.body ? <Motion delay={10} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion> : null}
  </>;
};

export const StepsAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, headerHeight, bodyHeight, vertical} = useLayout();
  const items = shot.props.items as StepItem[];
  const flow = shot.props.layout === 'flow';
  const columns = !flow && !vertical && items.length > 2 ? 2 : 1;
  const rows = Math.ceil(items.length / columns);
  const cardWidth = (contentWidth - (columns - 1) * 18 * unit) / columns;
  const availableHeight = contentHeight - headerHeight - (shot.body ? bodyHeight + 24 * unit : 0);
  const gap = (flow ? 48 : 18) * unit;
  const cardHeight = (availableHeight - (rows - 1) * gap) / rows;
  return <>
    <SceneHeader shot={shot} />
    <div style={{display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap}}>
      {items.map((item, index) => <CuedMotion key={index} delay={index * 4} revealFrame={item.reveal_frame}
        style={flow ? {position: 'relative'} : undefined}>
        {flow && index > 0 ? <svg aria-hidden width={24 * unit} height={gap}
          viewBox="0 0 24 48" style={{position: 'absolute', left: 47 * unit, top: -gap, overflow: 'visible'}}>
          <path d="M12 2V37M5 30L12 37L19 30" fill="none" stroke={shot.accent_color}
            strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />
        </svg> : null}
        <Card style={{height: cardHeight, display: 'flex', alignItems: 'center', gap: 30 * unit, padding: 26 * unit}}>
          <div style={{alignSelf: 'center', flexShrink: 0, width: 66 * unit, height: 66 * unit, borderRadius: 18 * unit,
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 30 * unit,
            background: shot.accent_color, color: contrastingInk(shot.accent_color), fontWeight: 800}}>{index + 1}</div>
          <div style={{flex: 1, minWidth: 0}}>
            <FittedText text={item.title} width={cardWidth - 154 * unit} height={(cardHeight - 66 * unit) * (item.body ? 0.5 : 0.9)}
              fontSize={45 * unit} minFontSize={24 * unit} />
            {item.body ? <Body text={item.body} width={cardWidth - 154 * unit} height={(cardHeight - 66 * unit) * 0.5} style={{marginTop: 14 * unit}} /> : null}
          </div>
        </Card>
      </CuedMotion>)}
    </div>
    <Motion delay={8} style={{marginTop: 24 * unit}}><Body text={shot.body} height={bodyHeight} /></Motion>
  </>;
};

export const ConclusionAdapter = ({shot}: AdapterProps) => {
  const {unit, contentWidth, contentHeight, vertical} = useLayout();
  const callToAction = shot.props.call_to_action as string | undefined;
  const actionHeight = (vertical ? 150 : 80) * unit;
  const cardHeight = contentHeight - 70 * unit - (callToAction ? actionHeight + 40 * unit : 0);
  const textHeight = cardHeight - 161 * unit;
  return <div style={{height: contentHeight, display: 'flex', flexDirection: 'column', justifyContent: 'center'}}>
    <Motion><div style={{fontSize: 28 * unit, color: muted, marginBottom: 32 * unit}}>最后记住</div></Motion>
    <Motion delay={3}><Card accent={shot.accent_color} style={{padding: 48 * unit}}>
      <FittedText text={shot.title} width={contentWidth - 96 * unit} height={textHeight * (shot.body ? 0.55 : 0.98)}
        fontSize={94 * unit} minFontSize={34 * unit} lineHeight={1.24} />
      <div style={{height: 5 * unit, width: 90 * unit, background: shot.accent_color, margin: `${30 * unit}px 0`}} />
      <Body text={shot.body} width={contentWidth - 96 * unit} height={textHeight * 0.45} />
    </Card></Motion>
    {callToAction ? <Motion delay={10} style={{marginTop: 40 * unit}}><FittedText text={callToAction}
      width={contentWidth} height={actionHeight} fontSize={36 * unit} style={{textAlign: 'center', color: muted}} /></Motion> : null}
  </div>;
};
