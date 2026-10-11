import React, {type CSSProperties, type ReactNode} from 'react';
import {AbsoluteFill} from 'remotion';
import {IsolatedCard} from '../components/community/IsolatedCard';
import InkUnderline from '../components/component-horizontal/video-talkcraft/cards/ink-underline';
import StrikeAndReplace from '../components/component-horizontal/video-talkcraft/cards/strike-and-replace';
import WordSlotCycle from '../components/component-horizontal/video-talkcraft/cards/word-slot-cycle';
import SourceConverge from '../components/component-horizontal/video-talkcraft/cards/source-converge';
import ErrorRetype from '../components/component-horizontal/video-talkcraft/cards/error-retype';
import LineChart, {type ChartPoint} from '../components/component-horizontal/rve/line-chart';

export type ExpandedTalkcraftComponentId =
  | 'Talkcraft-ink-underline'
  | 'Talkcraft-strike-and-replace'
  | 'Talkcraft-word-slot-cycle'
  | 'Talkcraft-source-converge'
  | 'Talkcraft-error-retype';

export type TalkcraftPanelProps = {
  componentId: ExpandedTalkcraftComponentId;
  title?: string;
  body?: string;
  items?: string[];
  keyword?: string;
  fromText?: string;
  toText?: string;
  accentColor?: string;
  slotWidth?: number;
  slotHeight?: number;
  scale?: number;
  style?: CSSProperties;
  productionCompact?: boolean;
  partDurationFrames?: number;
};

export type LineChartPanelProps = {
  title: string;
  data: ChartPoint[];
  unit?: string;
  subtitle?: string;
  maxValue?: number;
  accentColor?: string;
  slotWidth?: number;
  slotHeight?: number;
  scale?: number;
  style?: CSSProperties;
};

const SOURCE_WIDTH = 960;
const SOURCE_HEIGHT = 540;

const clean = (value: string | undefined, fallback = '') => {
  const text = value?.trim();
  return text ? text : fallback;
};

const cleanItems = (items: string[] | undefined) => (items ?? [])
  .map((item) => item.trim())
  .filter(Boolean)
  .slice(0, 4);

const panelScale = (slotWidth: number, slotHeight: number, scale?: number) =>
  scale ?? Math.min(slotWidth / SOURCE_WIDTH, slotHeight / SOURCE_HEIGHT);

const StageShell = ({
  children,
  slotWidth = 760,
  slotHeight = 420,
  scale,
  style,
  compactBox = false,
}: {
  children: ReactNode;
  slotWidth?: number;
  slotHeight?: number;
  scale?: number;
  style?: CSSProperties;
  compactBox?: boolean;
}) => {
  const fit = panelScale(slotWidth, slotHeight, scale);
  return (
    <div
      style={{
        position: 'relative',
        width: slotWidth,
        height: slotHeight,
        overflow: 'hidden',
        borderRadius: 28,
        background: 'linear-gradient(145deg, rgba(15,23,42,0.94), rgba(2,6,23,0.98))',
        border: '1px solid rgba(148,163,184,0.18)',
        boxShadow: '0 18px 48px rgba(0,0,0,0.24)',
        ...style,
      }}
    >
      <div
        style={{
          position: 'absolute',
          left: compactBox ? 0 : '50%',
          top: compactBox ? 0 : '50%',
          width: compactBox ? slotWidth : SOURCE_WIDTH,
          height: compactBox ? slotHeight : SOURCE_HEIGHT,
          transform: compactBox ? undefined : `translate(-50%, -50%) scale(${fit})`,
          transformOrigin: compactBox ? undefined : 'center center',
          overflow: 'hidden',
        }}
      >
        <IsolatedCard>
          <style>{TALKCRAFT_DARK_PANEL_CSS}</style>
          {!compactBox ? <style>{TALKCRAFT_LEGACY_SOURCE_LAYOUT_CSS}</style> : null}
          {children}
          {compactBox ? <style>{TALKCRAFT_COMPACT_PANEL_CSS}</style> : null}
        </IsolatedCard>
      </div>
    </div>
  );
};

const TALKCRAFT_DARK_PANEL_CSS = `
* { box-sizing: border-box; }
div { background: transparent !important; }
.host-wrap { display: none !important; }
.say, .sr-line, .ert-tw, .wsc-sent, .scv-ttl { color: #f8fafc !important; }
.say { left: 72px !important; right: 72px !important; top: 150px !important; }
.say-line { font-size: 64px !important; line-height: 1.35 !important; white-space: normal !important; font-weight: 700 !important; }
.say-line b { font-weight: 900 !important; color: #ffffff !important; }
#inkLayer path { fill: #38bdf8 !important; opacity: 0.92 !important; }
.sr-line { left: 72px !important; right: 72px !important; top: 180px !important; font-size: 72px !important; line-height: 1.28 !important; white-space: normal !important; }
.strike { background: #fb7185 !important; height: 5px !important; }
.word.from, .word.to { color: #f8fafc !important; }
.ert-tw { left: 72px !important; right: 72px !important; top: 236px !important; height: auto !important; font-size: 64px !important; line-height: 1.2 !important; white-space: normal !important; }
.ert-slot span { width: 66px !important; }
.ert-cur { background: #38bdf8 !important; }
.wsc-sent { left: 72px !important; right: 72px !important; top: 230px !important; font-size: 48px !important; height: 74px !important; }
.wsc-pill { background: rgba(56,189,248,0.18) !important; border: 2px solid rgba(125,211,252,0.7) !important; color: #f8fafc !important; font-size: 40px !important; }
.wsc-reel span { font-size: 40px !important; }
.wsc-final { color: #7dd3fc !important; font-size: 48px !important; }
.wsc-ghost { color: rgba(226,232,240,0.76) !important; font-size: 40px !important; }
.scv-ttl { left: 72px !important; right: 72px !important; top: 48px !important; font-size: 46px !important; line-height: 1.12 !important; font-weight: 900 !important; }
.scv-path { stroke: rgba(148,163,184,0.5) !important; stroke-width: 4 !important; }
.scv-node rect { fill: rgba(15,23,42,0.88) !important; stroke: rgba(125,211,252,0.7) !important; stroke-width: 3 !important; }
.scv-node text { fill: #f8fafc !important; font-weight: 900 !important; }
.scv-pk { fill: #38bdf8 !important; }
.scv-hub rect { fill: #0ea5e9 !important; }
.scv-hub text { fill: #ffffff !important; font-weight: 950 !important; }
.scv-cap { fill: rgba(226,232,240,0.9) !important; font-size: 40px !important; font-weight: 850 !important; }
`;

const TALKCRAFT_LEGACY_SOURCE_LAYOUT_CSS = `
.scv-node rect { x: -96px; y: -30px; width: 192px; height: 60px; }
.scv-node text { font-size: 40px !important; }
.scv-hub text { font-size: 42px !important; }
`;

const TALKCRAFT_COMPACT_PANEL_CSS = `
.host-wrap { display: none !important; }
.say { left: 24px !important; right: 24px !important; top: 50% !important; transform: translateY(-50%) !important; }
.say-line { font-size: 28px !important; line-height: 1.28 !important; white-space: normal !important; }
#inkLayer { width: 100% !important; height: 100% !important; }
.sr-line { left: 24px !important; right: 24px !important; top: 50% !important; transform: translateY(-50%) !important; font-size: 30px !important; line-height: 1.18 !important; white-space: normal !important; }
.strike { height: 4px !important; background: #fb7185 !important; }
.ert-tw { left: 24px !important; right: 24px !important; top: 50% !important; transform: translateY(-50%) !important; height: auto !important; font-size: 28px !important; line-height: 1.16 !important; white-space: normal !important; }
.ert-slot span { width: 32px !important; }
.ert-cur { width: 5px !important; height: 34px !important; }
.wsc-sent { left: 24px !important; right: 24px !important; top: 50% !important; transform: translateY(-50%) !important; height: 46px !important; font-size: 28px !important; line-height: 1.1 !important; }
.wsc-slot { height: 42px !important; }
.wsc-pill { height: 42px !important; font-size: 24px !important; }
.wsc-reel span { height: 42px !important; line-height: 42px !important; padding: 0 18px !important; font-size: 24px !important; }
.wsc-ghost { left: 18px !important; font-size: 24px !important; line-height: 42px !important; color: rgba(226,232,240,0.72) !important; }
.wsc-gu { top: -38px !important; }
.wsc-gd { top: 46px !important; }
.wsc-final { height: 42px !important; line-height: 42px !important; font-size: 28px !important; color: #7dd3fc !important; }
.wsc-meas span { font-size: 28px !important; }
.scv-ttl { left: 24px !important; right: 24px !important; top: 16px !important; font-size: 24px !important; line-height: 1.05 !important; text-align: center !important; }
.scv-svg { left: 0 !important; top: 0 !important; width: 100% !important; height: 100% !important; }
.scv-path { stroke: rgba(148,163,184,0.62) !important; stroke-width: 7 !important; }
.scv-node rect { fill: rgba(15,23,42,0.92) !important; stroke: rgba(125,211,252,0.82) !important; stroke-width: 5 !important; }
.scv-node text { fill: #f8fafc !important; font-weight: 900 !important; }
.scv-pk { fill: #38bdf8 !important; }
.scv-hub rect { fill: #38bdf8 !important; }
.scv-hub text { fill: #06111f !important; font-weight: 950 !important; }
.scv-cap { fill: rgba(226,232,240,0.92) !important; font-size: 58px !important; font-weight: 850 !important; }
`;

const talkcraftElement = ({
  componentId,
  title,
  body,
  items,
  keyword,
  fromText,
  toText,
  accentColor = '#38bdf8',
  productionCompact = false,
  partDurationFrames,
}: TalkcraftPanelProps) => {
  const list = cleanItems(items);
  const fallbackFrom = clean(fromText, clean(list[0], clean(keyword, '旧判断')));
  const fallbackTo = clean(toText, clean(list[1], clean(body, clean(keyword, '新判断'))));
  const sourceSpeed = productionCompact && partDurationFrames
    ? Math.max(1, Math.min(3.5, 132 / Math.max(30, partDurationFrames - 30)))
    : 1;
  switch (componentId) {
    case 'Talkcraft-ink-underline':
      return <InkUnderline title={clean(title, '先看这一点')} wrong={clean(keyword, fallbackFrom)} right={fallbackTo} />;
    case 'Talkcraft-strike-and-replace':
      return <StrikeAndReplace prefix={clean(title, '先纠正：')} from={fallbackFrom} to={fallbackTo} suffix={clean(body)} />;
    case 'Talkcraft-word-slot-cycle':
      return <WordSlotCycle stem={clean(title, '先检查')} words={list.length ? list : [fallbackFrom, fallbackTo]} final={clean(body, clean(keyword, '再决定'))} accent={accentColor} />;
    case 'Talkcraft-source-converge':
      return <SourceConverge holdResult title={productionCompact ? '' : clean(title, '把来源合到一起看')} sources={productionCompact ? (list.length ? list : [fallbackFrom].filter(Boolean)) : list.length >= 2 ? list : [fallbackFrom, fallbackTo]} hub={clean(keyword, fallbackTo)} caption={productionCompact ? '' : clean(body)} speed={sourceSpeed} compactFit={productionCompact} />;
    case 'Talkcraft-error-retype':
      return <ErrorRetype holdResult prefix={clean(title, '把判断改成')} first={fallbackFrom} second={fallbackTo} accent={accentColor} />;
    default:
      return null;
  }
};

export const TalkcraftPanel = (props: TalkcraftPanelProps) => (
  <StageShell slotWidth={props.slotWidth} slotHeight={props.slotHeight} scale={props.scale} style={props.style} compactBox={props.productionCompact}>
    {talkcraftElement(props)}
  </StageShell>
);

export const LineChartPanel = ({
  title,
  data,
  unit,
  subtitle,
  maxValue,
  accentColor = '#38bdf8',
  slotWidth = 760,
  slotHeight = 420,
  scale,
  style,
}: LineChartPanelProps) => (
  <StageShell slotWidth={slotWidth} slotHeight={slotHeight} scale={scale} style={style}>
    <AbsoluteFill style={{background: 'transparent'}}>
      <LineChart
        compactBox
        data={data}
        title={title}
        unit={unit}
        subtitle={subtitle}
        maxValue={maxValue}
        accentColor={accentColor}
      />
    </AbsoluteFill>
  </StageShell>
);

export const expandedSemanticPanelIds: ExpandedTalkcraftComponentId[] = [
  'Talkcraft-ink-underline',
  'Talkcraft-strike-and-replace',
  'Talkcraft-word-slot-cycle',
  'Talkcraft-source-converge',
  'Talkcraft-error-retype',
];
