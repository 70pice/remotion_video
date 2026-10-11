import type {CSSProperties} from 'react';
import {Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {PhoneFrame} from '../components/component-horizontal/snapcn/phone-frame';
import {FittedText, muted, productionFont, useLayout, white} from './adapters/layout';
import type {TimelineShot} from './types';
import {phoneScreenSize, tutorialRingPath, tutorialStepAt, tutorialTargetRect, type TutorialSourceSize, type TutorialStep} from './phoneTutorial';
import {guidedMaterialTop, guidedPhoneHeight, guidedPhoneScale} from './focusGeometry';

type Crop = {x: number; y: number; width: number; height: number};

const isCrop = (value: unknown): value is Crop => Boolean(value && typeof value === 'object'
  && typeof (value as Crop).x === 'number'
  && typeof (value as Crop).y === 'number'
  && typeof (value as Crop).width === 'number'
  && typeof (value as Crop).height === 'number');

const isVideoSrc = (src: string) => /\.(mp4|webm|mov|m4v)$/i.test(src);

const cropStyleFor = (crop: Crop | null, fit: 'contain' | 'cover'): CSSProperties => {
  if (!crop) {
    return {width: '100%', height: '100%', objectFit: fit};
  }
  return {
    position: 'absolute',
    left: `${-crop.x / crop.width * 100}%`,
    top: `${-crop.y / crop.height * 100}%`,
    width: `${100 / crop.width}%`,
    height: `${100 / crop.height}%`,
    objectFit: 'fill',
  };
};

const PhoneScreenFallback = ({shot}: {shot: TimelineShot}) => {
  const {unit} = useLayout();
  return <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
    justifyContent: 'center', gap: 18 * unit, padding: 28 * unit, boxSizing: 'border-box',
    color: white, background: `linear-gradient(160deg, ${shot.accent_color}30, #07101F 42%, #02050A)`}}>
    <div style={{width: 52 * unit, height: 6 * unit, borderRadius: 999, background: shot.accent_color}} />
    <FittedText text={shot.title} width={250 * unit} height={170 * unit}
      fontSize={32 * unit} minFontSize={16 * unit} />
    {shot.body ? <FittedText text={shot.body} width={250 * unit} height={220 * unit}
      fontSize={18 * unit} minFontSize={12 * unit} style={{color: '#D6DFEC', fontWeight: 500}} /> : null}
  </div>;
};

const PhoneScreenMedia = ({shot}: {shot: TimelineShot}) => {
  const {fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const props = shot.props as Record<string, unknown>;
  const src = shot.asset_src ? staticFile(shot.asset_src) : null;
  if (!src) return <PhoneScreenFallback shot={shot} />;
  const crop = isCrop(props.asset_crop) ? props.asset_crop : null;
  const fit = props.asset_fit === 'contain' ? 'contain' : 'cover';
  const start = typeof props.start_seconds === 'number' ? props.start_seconds : 0;
  const end = typeof props.end_seconds === 'number' ? props.end_seconds : undefined;
  const trimBefore = Math.round(start * fps);
  const trimAfter = end === undefined ? undefined : Math.round(end * fps);
  const style = cropStyleFor(crop, fit);
  const steps = props.tutorial_steps as TutorialStep[] | undefined;
  const step = steps ? tutorialStepAt(steps, frame) : undefined;
  const sourceSize = props.tutorial_source_size as TutorialSourceSize | undefined;
  const ring = step && sourceSize ? tutorialTargetRect(step.target, sourceSize) : null;
  const drawn = step ? Math.min(1, (frame - step.start_frame + 1) / 12) : 0;
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: '#050A12'}}>
    {isVideoSrc(shot.asset_src ?? '')
      ? <OffthreadVideo src={src} muted trimBefore={trimBefore} trimAfter={trimAfter} style={{...style, display: 'block'}} />
      : <Img src={src} style={{...style, display: 'block'}} />}
    {ring ? <svg data-tutorial-target={step?.instruction} viewBox={`0 0 ${phoneScreenSize.width} ${phoneScreenSize.height}`}
      preserveAspectRatio="none" style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}>
      <path d={tutorialRingPath(ring)} fill="none" stroke="#FB923C" strokeWidth={2.4}
        strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - drawn} />
    </svg> : null}
  </div>;
};

export const PhoneFrameMaterial = ({shot}: {shot: TimelineShot}) => {
  const {unit, vertical, margin, contentWidth, componentSample} = useLayout();
  const titleHeight = (vertical ? 148 : 76) * unit;
  const sourceHeight = (vertical ? 54 : 34) * unit;
  const frameTop = (vertical ? 410 : 126) * unit;
  const layered = Boolean(shot.layers?.length);
  const hasEmphasis = shot.layers?.some((layer) => layer.role === 'emphasis');
  const guided = vertical && Array.isArray(shot.props.tutorial_steps);
  const sampleTitleOnly = componentSample && vertical && layered && !hasEmphasis;
  const frameHeight = (guided ? guidedPhoneHeight : vertical ? sampleTitleOnly ? 1050 : hasEmphasis ? 620 : layered ? 820 : 1030 : 390) * unit;
  const phoneScale = guided ? guidedPhoneScale * unit : vertical ? sampleTitleOnly ? 1.7 : hasEmphasis ? 0.95 : layered ? 1.25 : 1.55 : 0.58;
  return <div style={{position: 'absolute', inset: 0, overflow: 'hidden', background: guided ? 'transparent' : `radial-gradient(circle at 50% 18%, ${shot.accent_color}2E, transparent 42%), #050A12`,
    color: white, fontFamily: productionFont}}>
    {!layered ? <div style={{position: 'absolute', left: margin, right: margin, top: (vertical ? 150 : 72) * unit}}>
      <div style={{width: 70 * unit, height: 6 * unit, borderRadius: 999, background: shot.accent_color, marginBottom: 20 * unit}} />
      <FittedText text={shot.title} width={contentWidth} height={titleHeight}
        fontSize={(vertical ? 58 : 34) * unit} minFontSize={(vertical ? 28 : 18) * unit} />
      {shot.source_label ? <div style={{marginTop: 10 * unit, display: 'inline-flex', maxWidth: contentWidth,
        border: '1px solid #FFFFFF29', borderRadius: 999, padding: `${7 * unit}px ${14 * unit}px`,
        background: '#07101FCC', color: muted, fontWeight: 700}}>
        <FittedText text={shot.source_label} width={contentWidth - 28 * unit} height={sourceHeight}
          fontSize={(vertical ? 22 : 14) * unit} minFontSize={(vertical ? 15 : 11) * unit} preferSingleLine />
      </div> : null}
    </div> : null}
    {guided ? <style>{'.guided-phone-frame div { box-sizing: border-box; }'}</style> : null}
    <div className={guided ? 'guided-phone-frame' : undefined} style={{position: 'absolute', left: 0, right: 0,
      top: guided ? guidedMaterialTop * unit : sampleTitleOnly ? 550 * unit : layered && vertical ? 520 * unit : frameTop, height: frameHeight}}>
      <PhoneFrame variant="flat" entrance={guided ? 'float' : 'rise'} scale={phoneScale} showDynamicIsland={false}
        floatLoop={!guided} floatAmplitude={6} bezelColor="#0B1220" screenColor="#050A12" shadow={`0 ${26 * unit}px ${70 * unit}px #000A`}>
        <PhoneScreenMedia shot={shot} />
      </PhoneFrame>
    </div>
  </div>;
};
