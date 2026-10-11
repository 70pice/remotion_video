import React, {type CSSProperties} from 'react';
import {AbsoluteFill, staticFile, useVideoConfig} from 'remotion';
import {useLayout} from './adapters/layout';
import {IsolatedCard} from '../components/community/IsolatedCard';
import SlowPushIn from '../components/component-horizontal/video-talkcraft/cards/slow-push-in';
import SlowPullReveal from '../components/component-horizontal/video-talkcraft/cards/slow-pull-reveal';
import SwayParallax from '../components/component-horizontal/video-talkcraft/cards/sway-parallax';
import OrbitDrift from '../components/component-horizontal/video-talkcraft/cards/orbit-drift';
import CrashZoomPunch from '../components/component-horizontal/video-talkcraft/cards/crash-zoom-punch';
import MagnifierDetail from '../components/component-horizontal/video-talkcraft/cards/magnifier-detail';
import MediaPopIn from '../components/component-horizontal/video-talkcraft/cards/media-pop-in';
import EvidenceScrollTour from '../components/component-horizontal/video-talkcraft/cards/evidence-scroll-tour';
import Tilt3dPage from '../components/component-horizontal/video-talkcraft/cards/tilt-3d-page';
import ScanlineAnnotate from '../components/component-horizontal/video-talkcraft/cards/scanline-annotate';
import CursorLockedZoom from '../components/component-horizontal/video-talkcraft/cards/cursor-locked-zoom';
import PipZoomBox from '../components/component-horizontal/video-talkcraft/cards/pip-zoom-box';
import FocusDimSpotlight from '../components/component-horizontal/video-talkcraft/cards/focus-dim-spotlight';
import {resolveTalkcraftTitleCopy, type TalkcraftTitleCopy} from '../components/component-horizontal/video-talkcraft/production-props';
import type {TimelineShot} from './types';
import {FocusDetail, FocusInk} from './MaterialFocus';
import {focusMediaBox, guidedMaterialTop} from './focusGeometry';
import type {TutorialSourceSize, TutorialStep} from './phoneTutorial';

type NativeComponent = React.ComponentType<Record<string, unknown>>;

type MediaBinding = {
  id: string;
  source: string;
  motion: string;
  content_constraints: string[];
  image_only: true;
  Component: NativeComponent;
  props: (mediaSrc: string, copy: TalkcraftTitleCopy, shot: TimelineShot) => Record<string, unknown>;
};

const asNative = (Component: unknown): NativeComponent => Component as NativeComponent;
const fitFor = (shot: TimelineShot): 'cover' | 'contain' => {
  const props = shot.props as Record<string, unknown>;
  return props.asset_fit === 'contain' ? 'contain' : 'cover';
};
const labelFor = (copy: TalkcraftTitleCopy): string | null => copy.title || copy.keyword || copy.body || copy.source || null;
const requireLabel = (copy: TalkcraftTitleCopy, componentId: string): string => {
  const label = labelFor(copy);
  if (!label) throw new Error(`Talkcraft native media ${componentId} is missing production label (title_or_keyword_required)`);
  return label;
};
const subFor = (copy: TalkcraftTitleCopy): string | undefined => copy.body || copy.source || undefined;
const isImageAsset = (assetSrc: string): boolean => /\.(png|jpe?g|webp|gif|avif)$/i.test(assetSrc);
const cropStyleFor = (shot: TimelineShot): CSSProperties => {
  const props = shot.props as Record<string, unknown>;
  const crop = props.asset_crop as Record<string, unknown> | undefined;
  if (!crop || typeof crop.x !== 'number' || typeof crop.y !== 'number' ||
      typeof crop.width !== 'number' || typeof crop.height !== 'number') return {};
  return {
    left: `${-crop.x / crop.width * 100}%`,
    top: `${-crop.y / crop.height * 100}%`,
    width: `${100 / crop.width}%`,
    height: `${100 / crop.height}%`,
  };
};

const centerTarget = {x: 140, y: 84, w: 420, h: 252};
const scanTarget = {x: 160, y: 95, w: 380, h: 220};

export const TALKCRAFT_MEDIA_SAFE_BOX = {x: 54, y: 250, width: 972, height: 730, sourceWidth: 960, sourceHeight: 540} as const;

export const talkcraftNativeMediaBindings: MediaBinding[] = [
  {id: 'Talkcraft-slow-push-in', source: 'cards/slow-push-in.tsx', motion: 'continuous slow push into a real screenshot focal area', content_constraints: ['media_required'], image_only: true, Component: asNative(SlowPushIn), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-slow-pull-reveal', source: 'cards/slow-pull-reveal.tsx', motion: 'slow pull from detail back to full real screenshot', content_constraints: ['media_required'], image_only: true, Component: asNative(SlowPullReveal), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-sway-parallax', source: 'cards/sway-parallax.tsx', motion: 'subtle 3D side sway across a real screenshot plane', content_constraints: ['media_required'], image_only: true, Component: asNative(SwayParallax), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-orbit-drift', source: 'cards/orbit-drift.tsx', motion: 'slow 3D orbit drift with page shadow around a real screenshot', content_constraints: ['media_required'], image_only: true, Component: asNative(OrbitDrift), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-crash-zoom-punch', source: 'cards/crash-zoom-punch.tsx', motion: 'fast camera punch into the central area of a real screenshot', content_constraints: ['media_required', 'title_or_keyword_required'], image_only: true, Component: asNative(CrashZoomPunch), props: (mediaSrc, copy, shot) => ({src: mediaSrc, target: centerTarget, label: requireLabel(copy, 'Talkcraft-crash-zoom-punch'), sub: subFor(copy), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-magnifier-detail', source: 'cards/magnifier-detail.tsx', motion: 'moving magnifier over a real screenshot detail', content_constraints: ['media_required'], image_only: true, Component: asNative(MagnifierDetail), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-media-pop-in', source: 'cards/media-pop-in.tsx', motion: 'single evidence screenshot pops in with the original card tilt timing', content_constraints: ['media_required', 'title_or_keyword_required'], image_only: true, Component: asNative(MediaPopIn), props: (mediaSrc, copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot), label: requireLabel(copy, 'Talkcraft-media-pop-in')})},
  {id: 'Talkcraft-evidence-scroll-tour', source: 'cards/evidence-scroll-tour.tsx', motion: 'vertical evidence tour scrolling a real long screenshot', content_constraints: ['media_required', 'title_or_keyword_required'], image_only: true, Component: asNative(EvidenceScrollTour), props: (mediaSrc, copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot), label: requireLabel(copy, 'Talkcraft-evidence-scroll-tour')})},
  {id: 'Talkcraft-tilt-3d-page', source: 'cards/tilt-3d-page.tsx', motion: 'real screenshot tilts into a 3D page with shadow drift', content_constraints: ['media_required'], image_only: true, Component: asNative(Tilt3dPage), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-scanline-annotate', source: 'cards/scanline-annotate.tsx', motion: 'scanline pass reveals a central callout on a real screenshot', content_constraints: ['media_required', 'title_or_keyword_required'], image_only: true, Component: asNative(ScanlineAnnotate), props: (mediaSrc, copy, shot) => ({src: mediaSrc, targets: [scanTarget], labels: [{text: requireLabel(copy, 'Talkcraft-scanline-annotate'), sub: subFor(copy)}], mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-cursor-locked-zoom', source: 'cards/cursor-locked-zoom.tsx', motion: 'camera follows the command-cursor path across a real screenshot', content_constraints: ['media_required'], image_only: true, Component: asNative(CursorLockedZoom), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-pip-zoom-box', source: 'cards/pip-zoom-box.tsx', motion: 'picture-in-picture zoom duplicates a real screenshot only as a magnified detail view', content_constraints: ['media_required'], image_only: true, Component: asNative(PipZoomBox), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
  {id: 'Talkcraft-focus-dim-spotlight', source: 'cards/focus-dim-spotlight.tsx', motion: 'spotlight mask and glow travel across a real screenshot', content_constraints: ['media_required'], image_only: true, Component: asNative(FocusDimSpotlight), props: (mediaSrc, _copy, shot) => ({mediaSrc, mediaFit: fitFor(shot), mediaStyle: cropStyleFor(shot)})},
];

export const supportedTalkcraftNativeMediaIds = talkcraftNativeMediaBindings.map((binding) => binding.id);
const bindingsById = new Map(talkcraftNativeMediaBindings.map((binding) => [binding.id, binding]));
const talkcraftNativeMediaClassName = (componentId: string): string =>
  `native-media-${componentId.replace(/^Talkcraft-/, '').replace(/[^a-z0-9-]/gi, '-').toLowerCase()}`;

export const isTalkcraftNativeMediaId = (componentId: string): boolean => bindingsById.has(componentId);

export const talkcraftNativeMediaPropsForShot = (shot: TimelineShot): Record<string, unknown> | null => {
  const binding = bindingsById.get(shot.component_id);
  if (!binding || !shot.asset_src || !isImageAsset(shot.asset_src)) return null;
  return binding.props(staticFile(shot.asset_src), resolveTalkcraftTitleCopy(shot), shot);
};

export const talkcraftNativeMediaBindingSummary = talkcraftNativeMediaBindings.map(({id, source, motion, content_constraints, image_only}) => ({
  id, source, motion, content_constraints, image_only,
}));

export const TALKCRAFT_PRODUCTION_MEDIA_CSS = `
* { box-sizing: border-box; }
.host-wrap, .host-badge, [class$='-host'], .host { display: none !important; }
.shot span, .sla-lab, .czp-lab { font-size: 28px !important; }
.talkcraft-production-media { position: relative; width: 100%; height: 100%; overflow: hidden; }
.native-media-slow-push-in .camera,
.native-media-slow-pull-reveal .camera,
.native-media-cursor-locked-zoom .camera { position: absolute; inset: 0; will-change: transform; }
.native-media-sway-parallax .world { position: absolute; inset: 0; perspective: 1200px; perspective-origin: 50% 50%; overflow: hidden; }
.native-media-sway-parallax .camera { position: absolute; left: 0; top: 50%; width: 1880px; height: 430px; margin-top: -215px; transform-style: preserve-3d; will-change: transform; }
.native-media-orbit-drift .world { position: absolute; inset: 0; perspective: 900px; perspective-origin: 50% 48%; }
.native-media-orbit-drift .camera { position: absolute; left: 50%; top: 50%; width: 700px; height: 436px; margin: -218px 0 0 -350px; transform-style: preserve-3d; will-change: transform; }
.native-media-tilt-3d-page .world { position: absolute; inset: 0; perspective: 1000px; perspective-origin: 50% 46%; }
.native-media-tilt-3d-page .camera { position: absolute; left: 50%; top: 50%; width: 792px; height: 452px; margin: -226px 0 0 -396px; transform-style: preserve-3d; will-change: transform; }
.native-media-sway-parallax .shadow,
.native-media-orbit-drift .shadow,
.native-media-tilt-3d-page .shadow { position: absolute; inset: 0; background: #000; filter: blur(24px); }
.native-media-sway-parallax .shadow { border-radius: 10px; opacity: 0.14; transform: translateZ(-30px); }
.native-media-orbit-drift .shadow { border-radius: 14px; }
.native-media-tilt-3d-page .shadow { border-radius: 12px; filter: blur(26px); }
.native-media-sway-parallax .page,
.native-media-orbit-drift .page,
.native-media-tilt-3d-page .page { position: absolute; inset: 0; background: #ffffff; border: 1px solid #e0e0e0; overflow: hidden; color: #1d1d1f; backface-visibility: hidden; }
.native-media-sway-parallax .page { border-radius: 10px; display: flex; }
.native-media-orbit-drift .page { border-radius: 14px; display: flex; }
.native-media-tilt-3d-page .page { border-radius: 12px; }
.native-media-magnifier-detail .shot { position: absolute; left: 56px; top: 116px; width: 540px; height: 308px; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; overflow: hidden; color: #1d1d1f; }
.native-media-magnifier-detail #magnifier { position: absolute; left: 0; top: 0; width: 210px; height: 210px; border-radius: 50%; border: 2px solid #1d1d1f; overflow: hidden; background: #ffffff; }
.native-media-magnifier-detail #magnifier .mag-inner { position: absolute; left: 0; top: 0; transform-origin: 0 0; }
.native-media-magnifier-detail .mag-inner .shot { left: 0; top: 0; border: 0; border-radius: 0; }
`;

export const TalkcraftNativeMedia = ({shot, style}: {shot: TimelineShot; style?: CSSProperties}) => {
  const {width} = useVideoConfig();
  const {componentSample} = useLayout();
  const binding = bindingsById.get(shot.component_id);
  if (!binding) return null;
  if (!shot.asset_src) {
    throw new Error(`Talkcraft native media ${shot.component_id} is missing production media (media_required)`);
  }
  if (!isImageAsset(shot.asset_src)) {
    throw new Error(`Talkcraft native media ${shot.component_id} only supports image assets (image_only)`);
  }
  const mediaSrc = staticFile(shot.asset_src);
  const props = binding.props(mediaSrc, resolveTalkcraftTitleCopy(shot), shot);
  if (shot.props.focus_steps && binding.id === 'Talkcraft-tilt-3d-page') {
    const source = shot.props.focus_source_size as TutorialSourceSize;
    const viewport = focusMediaBox(source);
    const guidedProps = {...props, transparentStage: true,
      mediaOverlay: <FocusInk steps={shot.props.focus_steps as TutorialStep[]} source={source} viewport={viewport} />};
    return <AbsoluteFill style={{background: 'transparent', pointerEvents: 'none', ...style}}>
      <div style={{position: 'absolute', left: 64, top: guidedMaterialTop, ...viewport}}>
        <IsolatedCard>
          <style>{TALKCRAFT_PRODUCTION_MEDIA_CSS}{`
            .native-media-tilt-3d-page .camera {left: 0; top: 0; width: ${viewport.width}px; height: ${viewport.height}px; margin: 0;}
            .native-media-tilt-3d-page .page {background: transparent; border: 0; border-radius: 18px;}
          `}</style>
          <div className="talkcraft-production-media native-media-tilt-3d-page">
            {React.createElement(binding.Component, guidedProps)}
          </div>
        </IsolatedCard>
      </div>
      <FocusDetail shot={shot} source={source} mediaHeight={viewport.height} />
    </AbsoluteFill>;
  }
  const hasOverlayLayers = Array.isArray(shot.layers) && shot.layers.length > 0;
  const safeBox = componentSample
    ? {...TALKCRAFT_MEDIA_SAFE_BOX, y: 600, height: 850}
    : TALKCRAFT_MEDIA_SAFE_BOX;
  const top = componentSample ? safeBox.y : hasOverlayLayers ? 520 : safeBox.y;
  const scale = Math.min(safeBox.width / safeBox.sourceWidth,
    safeBox.height / safeBox.sourceHeight);
  const renderedWidth = TALKCRAFT_MEDIA_SAFE_BOX.sourceWidth * scale;
  const left = (width - renderedWidth) / 2;
  return (
    <AbsoluteFill style={{background: 'transparent', pointerEvents: 'none', ...style}}>
      <div style={{position: 'absolute', left, top, width: TALKCRAFT_MEDIA_SAFE_BOX.sourceWidth,
        height: TALKCRAFT_MEDIA_SAFE_BOX.sourceHeight, transform: `scale(${scale})`, transformOrigin: 'top left', overflow: 'hidden'}}>
        <IsolatedCard>
          <style>{TALKCRAFT_PRODUCTION_MEDIA_CSS}</style>
          <div className={`talkcraft-production-media ${talkcraftNativeMediaClassName(binding.id)}`}>
            {React.createElement(binding.Component, props)}
          </div>
        </IsolatedCard>
      </div>
    </AbsoluteFill>
  );
};
