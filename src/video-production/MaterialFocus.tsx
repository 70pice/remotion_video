import {Img, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {useLayout} from './adapters/layout';
import {resolveVideoCropGeometry} from './adapters/videoGeometry';
import {focusCompositionLayout, focusDetailCrop, focusMediaBox, guidedMaterialTop} from './focusGeometry';
import {tutorialRingPath, tutorialStepAt, tutorialTargetRect, type TutorialStep, type TutorialSourceSize} from './phoneTutorial';
import type {TimelineShot} from './types';

export const FocusInk = ({steps, source, viewport}: {
  steps: TutorialStep[]; source: TutorialSourceSize; viewport: TutorialSourceSize;
}) => {
  const frame = useCurrentFrame();
  const step = tutorialStepAt(steps, frame);
  if (!step) return null;
  const rect = tutorialTargetRect(step.target, source, viewport);
  const draw = Math.min(1, (frame - step.start_frame + 1) / 12);
  return <svg aria-label={`重点：${step.instruction}`} viewBox={`0 0 ${viewport.width} ${viewport.height}`}
    style={{position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none'}}>
    <path d={tutorialRingPath(rect, viewport)} fill="none" stroke="#FB923C" strokeWidth={4}
      strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray={1} strokeDashoffset={1 - draw}
      style={{filter: 'drop-shadow(0 0 2px #08101F)'}} />
  </svg>;
};

export const FocusDetail = ({shot, source, mediaHeight}: {
  shot: TimelineShot; source: TutorialSourceSize; mediaHeight: number;
}) => {
  const frame = useCurrentFrame();
  const step = tutorialStepAt(shot.props.focus_steps as TutorialStep[], frame);
  if (!step || !shot.asset_src) return null;
  const detail = focusCompositionLayout(source, step.target, /\.mp4$/i.test(shot.asset_src)).detail;
  if (!detail) return null;
  const height = detail.height;
  const geometry = resolveVideoCropGeometry({viewportWidth: 952, viewportHeight: height,
    metadata: source, crop: focusDetailCrop(step.target), fit: 'contain'});
  return <div style={{position: 'absolute', left: 64, top: guidedMaterialTop + mediaHeight + 28, width: 952}}>
    <div style={{fontSize: 28, lineHeight: '40px', color: '#F4F7FC', marginBottom: 12}}>局部放大</div>
    <div style={{position: 'relative', height, overflow: 'hidden', borderRadius: 18, background: '#091324',
      boxShadow: '0 0 0 2px #FB923C55 inset'}}>
      <div style={{position: 'absolute', left: geometry.window.left, top: geometry.window.top,
        width: geometry.window.width, height: geometry.window.height, overflow: 'hidden'}}>
        <Img src={staticFile(shot.asset_src)} style={{position: 'absolute', left: geometry.media.left, top: geometry.media.top,
          width: geometry.media.width, height: geometry.media.height, objectFit: 'fill'}} />
      </div>
    </div>
  </div>;
};

export const MaterialFocus = ({shot}: {shot: TimelineShot}) => {
  const {unit} = useLayout();
  const {fps} = useVideoConfig();
  const source = shot.props.focus_source_size as TutorialSourceSize;
  const steps = shot.props.focus_steps as TutorialStep[];
  const viewport = focusMediaBox(source);
  const src = staticFile(shot.asset_src!);
  const video = /\.mp4$/i.test(shot.asset_src!);
  return <div style={{position: 'absolute', width: 1080, height: 1920,
    transform: `scale(${unit})`, transformOrigin: 'top left'}}>
    <div style={{position: 'absolute', left: 64, top: guidedMaterialTop, ...viewport, overflow: 'hidden', borderRadius: 18}}>
      {video ? <OffthreadVideo src={src} muted trimBefore={Math.round(Number(shot.props.start_seconds ?? 0) * fps)}
        trimAfter={shot.props.end_seconds === undefined ? undefined : Math.round(Number(shot.props.end_seconds) * fps)} style={{width: '100%', height: '100%', objectFit: 'contain'}} />
        : <Img src={src} style={{width: '100%', height: '100%', objectFit: 'contain'}} />}
      <FocusInk steps={steps} source={source} viewport={viewport} />
    </div>
    <FocusDetail shot={shot} source={source} mediaHeight={viewport.height} />
  </div>;
};
