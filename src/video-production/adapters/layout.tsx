import {useMemo} from 'react';
import type {CSSProperties, ReactNode} from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {TimelineShot, VideoMetadata} from '../types';

export const productionFont = '"Microsoft YaHei", "Noto Sans SC", sans-serif';
export const muted = '#A8B6CB';
export const panel = '#1B2940';
export const white = '#F4F7FC';
export const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

export type AdapterProps = {shot: TimelineShot; durationInFrames: number; videoMetadata?: Record<string, VideoMetadata>};

export const useLayout = () => {
  const {width, height, fps, durationInFrames} = useVideoConfig();
  const vertical = height > width;
  const unit = Math.min(width, height) / 1080;
  const margin = 72 * unit;
  const contentWidth = width - margin * 2;
  // Reserve the subtitle and source regions even for a shot with no captions.
  const contentHeight = height - (vertical ? 640 : 430) * unit;
  const headerHeight = (vertical ? 260 : 170) * unit;
  const bodyHeight = (vertical ? 180 : 120) * unit;
  return {width, height, fps, durationInFrames, unit, vertical, margin, contentWidth, contentHeight, headerHeight, bodyHeight};
};

const fittedSize = (text: string, width: number, height: number, max: number, min: number, lineHeight: number,
  preferSingleLine: boolean) => {
  // Measure actual installed Chinese glyphs and keep space for browser wrapping
  // around punctuation. Text is never silently clipped.
  const canvas = typeof document === 'undefined' ? null : document.createElement('canvas');
  const context = canvas?.getContext('2d');
  const glyphWidth = (character: string, size: number) => {
    if (context) context.font = `700 ${size}px ${productionFont}`;
    return context?.measureText(character).width ?? size * (/^[\x20-\x7E]$/.test(character) ? 0.65 : 1);
  };
  const countLines = (size: number) => {
    if (context) context.font = `700 ${size}px ${productionFont}`;
    let lines = 1;
    let used = 0;
    for (const character of text) {
      if (character === '\n') { lines += 1; used = 0; continue; }
      const glyph = glyphWidth(character, size);
      if (used + glyph > width) { lines += 1; used = glyph; } else used += glyph;
    }
    return lines;
  };
  for (let size = max; size >= min; size -= Math.max(1, max / 80)) {
    if (preferSingleLine) {
      const measured = [...text].reduce((total, character) => total + glyphWidth(character, size), 0);
      if (measured <= width * 0.96 && size * lineHeight <= height * 0.92) return size;
      continue;
    }
    if (countLines(size) * size * lineHeight <= height * 0.92) return size;
  }
  throw new Error('Text exceeds the safe area. Shorten this field or split it into more shots.');
};

export const FittedText = ({text, width, height, fontSize, minFontSize = 22, lineHeight = 1.36,
  preferSingleLine = false, style}: {
  text: string;
  width: number;
  height: number;
  fontSize: number;
  minFontSize?: number;
  lineHeight?: number;
  preferSingleLine?: boolean;
  style?: CSSProperties;
}) => {
  const size = useMemo(() => fittedSize(text, width, height, fontSize, minFontSize, lineHeight, preferSingleLine),
    [text, width, height, fontSize, minFontSize, lineHeight, preferSingleLine]);
  return <div style={{width, maxWidth: '100%', fontSize: size, lineHeight,
    whiteSpace: preferSingleLine ? 'nowrap' : 'pre-wrap', overflowWrap: preferSingleLine ? 'normal' : 'anywhere',
    fontWeight: 700, ...style}}>{text}</div>;
};

export const Motion = ({children, delay = 0, style}: {children: ReactNode; delay?: number; style?: CSSProperties}) => {
  const frame = useCurrentFrame();
  const {fps, unit, durationInFrames} = useLayout();
  const entranceFrames = Math.max(1, Math.min(Math.round(fps * 0.42), Math.floor(durationInFrames * 0.28)));
  const adjustedDelay = Math.min(delay, Math.floor(durationInFrames / 10));
  const entrance = durationInFrames < Math.max(4, Math.round(fps * 0.25)) ? 1 :
    spring({frame: frame - adjustedDelay, fps, durationInFrames: entranceFrames, config: {damping: 200, stiffness: 140}});
  return <div style={{opacity: entrance, transform: `translateY(${(1 - entrance) * 26 * unit}px)`, ...style}}>{children}</div>;
};

export const CuedMotion = ({children, revealFrame, delay = 0, style}: {
  children: ReactNode; revealFrame?: number; delay?: number; style?: CSSProperties;
}) => {
  const frame = useCurrentFrame();
  const {fps, unit} = useLayout();
  // Legacy content keeps its original entrance. Explicit cues are measured local
  // frames: do not clamp them to the opening animation's short delay window.
  if (revealFrame === undefined) return <Motion delay={delay} style={style}>{children}</Motion>;
  const elapsed = frame - revealFrame;
  const entrance = elapsed < 0 ? 0 : elapsed >= 14 ? 1 : spring({frame: elapsed, fps, durationInFrames: 15,
    config: {damping: 200, stiffness: 140}});
  return <div style={{...style, visibility: elapsed < 0 ? 'hidden' : 'visible', opacity: entrance,
    transform: `translateY(${(1 - entrance) * 26 * unit}px)`}}>{children}</div>;
};

export const SceneHeader = ({shot}: {shot: TimelineShot}) => {
  const {contentWidth, unit, vertical, headerHeight} = useLayout();
  return <Motion style={{height: headerHeight, flexShrink: 0}}>
    <div style={{height: 6 * unit, width: 72 * unit, background: shot.accent_color, marginBottom: 22 * unit}} />
    <FittedText text={shot.title} width={contentWidth} height={headerHeight - 58 * unit}
      fontSize={(vertical ? 80 : 70) * unit} minFontSize={32 * unit} />
  </Motion>;
};

export const Body = ({text, width, height, style}: {text: string; width?: number; height?: number; style?: CSSProperties}) => {
  const {contentWidth, unit, vertical} = useLayout();
  if (!text) return null;
  return <FittedText text={text} width={width ?? contentWidth} height={height ?? (vertical ? 280 : 150) * unit}
    fontSize={40 * unit} minFontSize={22 * unit} style={{color: muted, fontWeight: 500, ...style}} />;
};

export const Card = ({children, accent, style}: {children: ReactNode; accent?: string; style?: CSSProperties}) => {
  const {unit} = useLayout();
  return <div style={{background: panel, border: `1px solid ${accent ? accent + '65' : '#3A4860'}`,
    borderRadius: 28 * unit, padding: 34 * unit, boxSizing: 'border-box', ...style}}>{children}</div>;
};

export const gentleZoom = (frame: number, duration: number) => interpolate(frame, [0, Math.max(1, duration - 1)], [1, 1.04], clamp);

export const contrastingInk = (hex: string) => {
  const parts = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
  const [r, g, b] = parts.map((part) => part <= 0.04045 ? part / 12.92 : ((part + 0.055) / 1.055) ** 2.4);
  return r * 0.2126 + g * 0.7152 + b * 0.0722 > 0.179 ? '#111B2A' : white;
};
