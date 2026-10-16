import React, {type CSSProperties} from 'react';
import {AbsoluteFill, useVideoConfig} from 'remotion';
import {IsolatedCard} from '../components/community/IsolatedCard';
import HighlighterSweep from '../components/component-horizontal/video-talkcraft/cards/highlighter-sweep';
import OutlineBoxTitle from '../components/component-horizontal/video-talkcraft/cards/outline-box-title';
import NewsCardDesk from '../components/component-horizontal/video-talkcraft/cards/news-card-desk';
import QuoteCard from '../components/component-horizontal/video-talkcraft/cards/quote-card';
import QuoteBracketPull from '../components/component-horizontal/video-talkcraft/cards/quote-bracket-pull';
import QuoteHoldArrow from '../components/component-horizontal/video-talkcraft/cards/quote-hold-arrow';
import KeywordPopHighlight from '../components/component-horizontal/video-talkcraft/cards/keyword-pop-highlight';
import HandDrawnEllipse from '../components/component-horizontal/video-talkcraft/cards/hand-drawn-ellipse';
import ScribbleAnnotation from '../components/component-horizontal/video-talkcraft/cards/scribble-annotation';
import CornerBracketFrame from '../components/component-horizontal/video-talkcraft/cards/corner-bracket-frame';
import InkUnderline from '../components/component-horizontal/video-talkcraft/cards/ink-underline';
import StrikeAndReplace from '../components/component-horizontal/video-talkcraft/cards/strike-and-replace';
import ReticleLockOn from '../components/component-horizontal/video-talkcraft/cards/reticle-lock-on';
import ImpactOpenTitle from '../components/component-horizontal/video-talkcraft/cards/impact-open-title';
import SlabPunchTitle from '../components/component-horizontal/video-talkcraft/cards/slab-punch-title';
import SpeedSlabTitle from '../components/component-horizontal/video-talkcraft/cards/speed-slab-title';
import CountBadgeTitle from '../components/component-horizontal/video-talkcraft/cards/count-badge-title';
import LeadWordZoomAssemble from '../components/component-horizontal/video-talkcraft/cards/lead-word-zoom-assemble';
import LineByLineSlide from '../components/component-horizontal/video-talkcraft/cards/line-by-line-slide';
import PerCharacterRise from '../components/component-horizontal/video-talkcraft/cards/per-character-rise';
import TrackingIn from '../components/component-horizontal/video-talkcraft/cards/tracking-in';
import TypewriterReveal from '../components/component-horizontal/video-talkcraft/cards/typewriter-reveal';
import AltBlockLines from '../components/component-horizontal/video-talkcraft/cards/alt-block-lines';
import TypeContrastEmphasis from '../components/component-horizontal/video-talkcraft/cards/type-contrast-emphasis';
import WordSlotCycle from '../components/component-horizontal/video-talkcraft/cards/word-slot-cycle';
import SoftBlurIn from '../components/component-horizontal/video-talkcraft/cards/soft-blur-in';
import ChipGridSingleSelect from '../components/component-horizontal/video-talkcraft/cards/chip-grid-single-select';
import ErrorRetype from '../components/component-horizontal/video-talkcraft/cards/error-retype';
import SourceConverge from '../components/component-horizontal/video-talkcraft/cards/source-converge';
import SplitTextStagger from '../components/component-horizontal/video-talkcraft/cards/split-text-stagger';
import TitleDemoteToLabel from '../components/component-horizontal/video-talkcraft/cards/title-demote-to-label';
import {resolveTalkcraftTitleCopy, takeTalkcraftLines, type TalkcraftTitleCopy} from '../components/component-horizontal/video-talkcraft/production-props';
import type {TimelineShot} from './types';

type NativeComponent = React.ComponentType<Record<string, unknown>>;

type Binding = {
  id: string;
  source: string;
  role: 'title' | 'emphasis';
  motion: string;
  content_constraints: string[];
  Component: NativeComponent;
  props: (copy: TalkcraftTitleCopy, shot: TimelineShot) => Record<string, unknown> | null;
};

const asNative = (Component: unknown): NativeComponent => Component as NativeComponent;
const words = (copy: TalkcraftTitleCopy, count = 4) => copy.items.slice(0, count);
const titleWords = (copy: TalkcraftTitleCopy) => {
  const split = copy.title.split(/\s+/).filter(Boolean);
  return split.length >= 2 ? split.slice(0, 4) : takeTalkcraftLines(copy, 4);
};
const hasCopy = (copy: TalkcraftTitleCopy) => Boolean(copy.title || copy.body || copy.lines.length || copy.items.length);
const requireLines = (copy: TalkcraftTitleCopy, count: number) => {
  const lines = takeTalkcraftLines(copy, count);
  return lines.length >= count ? lines : null;
};
const explicitText = (shot: TimelineShot, key: string): string | null => {
  const props = shot.props as Record<string, unknown>;
  const value = props[key];
  return typeof value === 'string' && value.trim() && value.length <= 64 ? value.trim() : null;
};
const normalizeChoiceText = (value: string): string => value.replace(/[^\p{L}\p{N}]+/gu, '').toLowerCase();
const selectedOptionIndex = (copy: TalkcraftTitleCopy, shot: TimelineShot): number | null => {
  const explicitSelection = explicitText(shot, 'keyword') ?? explicitText(shot, 'highlight');
  const target = normalizeChoiceText(explicitSelection || copy.title);
  if (!target) return null;
  const matches = copy.items
    .map((item, index) => ({index, value: normalizeChoiceText(item)}))
    .filter((item) => item.value === target);
  return matches.length === 1 ? matches[0].index : null;
};
const chipGridEquation = (copy: TalkcraftTitleCopy, selected: number) => {
  const selectedText = copy.items[selected];
  if (!selectedText) return null;
  const equation: Array<{text: string; accent?: boolean}> = [{text: selectedText, accent: true}];
  if (copy.body) equation.push({text: copy.body});
  return equation;
};
const metricValue = (shot: TimelineShot): string | null => {
  const props = shot.props as Record<string, unknown>;
  const metric = props.metric;
  if (!metric || typeof metric !== 'object') return null;
  const value = (metric as Record<string, unknown>).value;
  return typeof value === 'string' && /[0-9０-９一二三四五六七八九十百千万亿]+/.test(value) ? value : null;
};

export const TALKCRAFT_TITLE_SAFE_BOX = {x: 64, y: 180, width: 952, height: 400, sourceWidth: 960, sourceHeight: 540} as const;

export const talkcraftNativeTitleBindings: Binding[] = [
  {id: 'Talkcraft-highlighter-sweep', source: 'cards/highlighter-sweep.tsx', role: 'emphasis', motion: 'highlight block sweep + dimmed surrounding lines + lifted key sentence', content_constraints: ['title_or_body_required'], Component: asNative(HighlighterSweep), props: (copy) => hasCopy(copy) ? ({title: copy.keyword || copy.title, body: takeTalkcraftLines(copy, 4).join('｜'), source: copy.source}) : null},
  {id: 'Talkcraft-outline-box-title', source: 'cards/outline-box-title.tsx', role: 'title', motion: 'single-stroke rounded rectangle + delayed chip + chevrons', content_constraints: ['title_required'], Component: asNative(OutlineBoxTitle), props: (copy) => copy.title ? ({title: copy.title, label: copy.keyword || copy.title}) : null},
  {id: 'Talkcraft-news-card-desk', source: 'cards/news-card-desk.tsx', role: 'emphasis', motion: 'newspaper cards slide onto desk + Ken Burns + redline sweep', content_constraints: ['title_required'], Component: asNative(NewsCardDesk), props: (copy) => copy.title ? ({title: copy.title, body: copy.body, source: copy.source, date: copy.source, highlight: copy.keyword || copy.title}) : null},
  {id: 'Talkcraft-quote-card', source: 'cards/quote-card.tsx', role: 'title', motion: 'dark panel cover + staggered quote line punches', content_constraints: ['lines_min_2_or_title_body_required'], Component: asNative(QuoteCard), props: (copy) => { const lines = requireLines(copy, 2); return lines ? {lines, source: copy.source, highlight: copy.keyword} : null; }},
  {id: 'Talkcraft-quote-bracket-pull', source: 'cards/quote-bracket-pull.tsx', role: 'emphasis', motion: 'paired quote marks pull inward + final phrase marker sweep', content_constraints: ['lines_min_3_or_title_body_item_required'], Component: asNative(QuoteBracketPull), props: (copy) => { const lines = requireLines(copy, 3); return lines ? {lines, highlight: copy.keyword || lines[2]} : null; }},
  {id: 'Talkcraft-quote-hold-arrow', source: 'cards/quote-hold-arrow.tsx', role: 'emphasis', motion: 'staggered quote lines + centered highlighter box punch', content_constraints: ['lines_min_3_or_title_body_item_required'], Component: asNative(QuoteHoldArrow), props: (copy) => { const lines = requireLines(copy, 3); return lines ? {lines} : null; }},
  {id: 'Talkcraft-keyword-pop-highlight', source: 'cards/keyword-pop-highlight.tsx', role: 'emphasis', motion: 'keyword scale pop + shake impact + skew color slab', content_constraints: ['title_required', 'keyword_required', 'min_visible_frames_60'], Component: asNative(KeywordPopHighlight), props: (copy) => copy.title && copy.keyword ? ({prefix: copy.title === copy.keyword ? '' : copy.title, keyword: copy.keyword, suffix: copy.body}) : null},
  {id: 'Talkcraft-hand-drawn-ellipse', source: 'cards/hand-drawn-ellipse.tsx', role: 'emphasis', motion: 'hand-drawn ellipse path + circled phrase punch', content_constraints: ['title_required', 'keyword_required'], Component: asNative(HandDrawnEllipse), props: (copy) => copy.title && copy.keyword ? ({lead: copy.title, emphasis: copy.keyword}) : null},
  {id: 'Talkcraft-scribble-annotation', source: 'cards/scribble-annotation.tsx', role: 'emphasis', motion: 'three hand-drawn annotation strokes over product-like panel', content_constraints: ['title_required', 'keyword_required', 'min_visible_frames_120'], Component: asNative(ScribbleAnnotation), props: (copy) => copy.title && copy.keyword ? ({title: copy.title, price: copy.keyword, original: copy.items[1] ?? '', spec: copy.body, fine: copy.source, button: copy.items[2] ?? ''}) : null},
  {id: 'Talkcraft-corner-bracket-frame', source: 'cards/corner-bracket-frame.tsx', role: 'title', motion: 'opposite corner brackets enter + two-line reveal', content_constraints: ['title_required', 'body_required'], Component: asNative(CornerBracketFrame), props: (copy) => copy.title && copy.body ? ({line1: copy.title, line2: copy.body}) : null},
  {id: 'Talkcraft-ink-underline', source: 'cards/ink-underline.tsx', role: 'emphasis', motion: 'grainy ink ribbons underline two emphasized phrases', content_constraints: ['title_required', 'keyword_required', 'body_or_items_1_required'], Component: asNative(InkUnderline), props: (copy) => { const right = copy.items[1] ?? copy.body; return copy.title && copy.keyword && right ? {title: copy.title, wrong: copy.keyword, right} : null; }},
  {id: 'Talkcraft-strike-and-replace', source: 'cards/strike-and-replace.tsx', role: 'emphasis', motion: 'fast strike-through + same-slot replacement text', content_constraints: ['title_required', 'from_text_or_items_0_required', 'to_text_or_items_1_or_keyword_required'], Component: asNative(StrikeAndReplace), props: (copy, shot) => { const from = explicitText(shot, 'from_text') ?? copy.items[0]; const to = explicitText(shot, 'to_text') ?? copy.items[1] ?? copy.keyword; return copy.title && from && to ? {prefix: copy.title, from, to, suffix: copy.body} : null; }},
  {id: 'Talkcraft-reticle-lock-on', source: 'cards/reticle-lock-on.tsx', role: 'emphasis', motion: 'reticle locks onto target button area', content_constraints: ['title_required', 'keyword_required'], Component: asNative(ReticleLockOn), props: (copy) => copy.title && copy.keyword ? ({label: copy.title, buttonText: copy.keyword}) : null},
  {id: 'Talkcraft-impact-open-title', source: 'cards/impact-open-title.tsx', role: 'title', motion: 'headline slam + delayed keyword recolor + corner frame', content_constraints: ['title_required', 'keyword_required'], Component: asNative(ImpactOpenTitle), props: (copy) => copy.title && copy.keyword ? ({prefix: copy.title, keyword: copy.keyword, subtitle: copy.body}) : null},
  {id: 'Talkcraft-slab-punch-title', source: 'cards/slab-punch-title.tsx', role: 'title', motion: 'first line snap + centered slab expands + white word punch', content_constraints: ['title_required', 'keyword_required'], Component: asNative(SlabPunchTitle), props: (copy) => copy.title && copy.keyword ? ({title: copy.title, emphasis: copy.keyword}) : null},
  {id: 'Talkcraft-speed-slab-title', source: 'cards/speed-slab-title.tsx', role: 'title', motion: 'speed lines + slab rush-in + lagging text catch-up', content_constraints: ['title_required', 'keyword_required'], Component: asNative(SpeedSlabTitle), props: (copy) => copy.title && copy.keyword ? ({title: copy.title, emphasis: copy.keyword}) : null},
  {id: 'Talkcraft-count-badge-title', source: 'cards/count-badge-title.tsx', role: 'title', motion: 'large count lands, hue shifts, rest of phrase is pushed out', content_constraints: ['title_required', 'keyword_required', 'numeric_first_item_or_metric_value_required'], Component: asNative(CountBadgeTitle), props: (copy, shot) => { const count = copy.items[0] ?? metricValue(shot); return count && /[0-9０-９一二三四五六七八九十百千万亿]+/.test(count) && copy.keyword && copy.title ? {count, unit: copy.keyword, title: copy.title} : null; }},
  {id: 'Talkcraft-lead-word-zoom-assemble', source: 'cards/lead-word-zoom-assemble.tsx', role: 'title', motion: 'lead word zoom assemble with one accent word', content_constraints: ['title_or_lines_required'], Component: asNative(LeadWordZoomAssemble), props: (copy) => { const ws = titleWords(copy); return ws.length ? {words: ws, subline: copy.body, accent: copy.accent} : null; }},
  {id: 'Talkcraft-line-by-line-slide', source: 'cards/line-by-line-slide.tsx', role: 'title', motion: 'each line slides in and exits as a continuous phrase block', content_constraints: ['lines_min_2_or_title_body_required'], Component: asNative(LineByLineSlide), props: (copy) => { const lines = requireLines(copy, 2); return lines ? {lines} : null; }},
  {id: 'Talkcraft-per-character-rise', source: 'cards/per-character-rise.tsx', role: 'title', motion: 'characters rise individually with staggered opacity', content_constraints: ['title_required'], Component: asNative(PerCharacterRise), props: (copy) => copy.title ? ({text: copy.title}) : null},
  {id: 'Talkcraft-tracking-in', source: 'cards/tracking-in.tsx', role: 'title', motion: 'letter spacing and blur spring into a locked title', content_constraints: ['title_required'], Component: asNative(TrackingIn), props: (copy) => copy.title ? ({title: copy.title}) : null},
  {id: 'Talkcraft-typewriter-reveal', source: 'cards/typewriter-reveal.tsx', role: 'title', motion: 'two-line typewriter with blinking cursor handoff', content_constraints: ['title_required', 'body_required', 'min_visible_frames_150'], Component: asNative(TypewriterReveal), props: (copy) => copy.title && copy.body ? ({line1: copy.title, line2: copy.body}) : null},
  {id: 'Talkcraft-alt-block-lines', source: 'cards/alt-block-lines.tsx', role: 'title', motion: 'two colored blocks brush text into view', content_constraints: ['lines_min_2_or_title_body_required'], Component: asNative(AltBlockLines), props: (copy) => { const rows = requireLines(copy, 2); return rows ? {rows} : null; }},
  {id: 'Talkcraft-type-contrast-emphasis', source: 'cards/type-contrast-emphasis.tsx', role: 'emphasis', motion: 'word-by-word baseline pop with serif/color emphasis channels', content_constraints: ['lines_min_2_or_title_body_required'], Component: asNative(TypeContrastEmphasis), props: (copy) => { const lines = requireLines(copy, 2); return lines ? {words: lines.slice(0, 5).map((line, index) => ({w: line, beat: index * 0.34, emph: index === 1 ? 'serif' : index === 3 ? 'color' : undefined}))} : null; }},
  {id: 'Talkcraft-word-slot-cycle', source: 'cards/word-slot-cycle.tsx', role: 'emphasis', motion: 'fixed stem with rolling pill slot and final overshoot', content_constraints: ['title_required', 'body_required', 'items_min_1'], Component: asNative(WordSlotCycle), props: (copy) => { const ws = words(copy, 4); return copy.title && ws.length && copy.body ? {stem: copy.title, words: ws, final: copy.body, accent: copy.accent} : null; }},
  {id: 'Talkcraft-soft-blur-in', source: 'cards/soft-blur-in.tsx', role: 'title', motion: 'per-character soft blur resolves into a full sentence', content_constraints: ['title_required'], Component: asNative(SoftBlurIn), props: (copy) => copy.title ? ({text: copy.title}) : null},
  {id: 'Talkcraft-chip-grid-single-select', source: 'cards/chip-grid-single-select.tsx', role: 'emphasis', motion: 'option grid flips one selected answer into equation result', content_constraints: ['title_required', 'items_min_2', 'selected_option_must_match_title_or_keyword', 'min_visible_frames_150'], Component: asNative(ChipGridSingleSelect), props: (copy, shot) => { const options = words(copy, 5); const selected = selectedOptionIndex(copy, shot); const equation = selected == null ? null : chipGridEquation(copy, selected); return copy.title && options.length >= 2 && selected != null && equation ? {question: copy.title, options, selected, equation} : null; }},
  {id: 'Talkcraft-error-retype', source: 'cards/error-retype.tsx', role: 'emphasis', motion: 'wrong phrase retyped into corrected phrase', content_constraints: ['title_required', 'from_text_or_items_0_required', 'to_text_or_items_1_or_keyword_required'], Component: asNative(ErrorRetype), props: (copy, shot) => { const first = explicitText(shot, 'from_text') ?? copy.items[0]; const second = explicitText(shot, 'to_text') ?? copy.items[1] ?? copy.keyword; return copy.title && first && second ? {prefix: copy.title, first, second, accent: copy.accent} : null; }},
  {id: 'Talkcraft-source-converge', source: 'cards/source-converge.tsx', role: 'emphasis', motion: 'multiple sources converge into one central hub', content_constraints: ['title_required', 'keyword_required', 'items_min_2'], Component: asNative(SourceConverge), props: (copy) => { const sources = words(copy, 4); return copy.title && sources.length >= 2 && copy.keyword ? {title: copy.title, sources, hub: copy.keyword, caption: copy.source} : null; }},
  {id: 'Talkcraft-split-text-stagger', source: 'cards/split-text-stagger.tsx', role: 'title', motion: 'split text stagger reveal with subtitle', content_constraints: ['title_required'], Component: asNative(SplitTextStagger), props: (copy) => copy.title ? ({text: copy.title, sub: copy.body}) : null},
  {id: 'Talkcraft-title-demote-to-label', source: 'cards/title-demote-to-label.tsx', role: 'title', motion: 'title demotes into a label while item cards appear', content_constraints: ['title_required', 'items_min_1', 'min_visible_frames_105'], Component: asNative(TitleDemoteToLabel), props: (copy) => { const items = words(copy, 4); return copy.title && items.length ? {title: copy.title, items, accent: copy.accent} : null; }},
];

export const supportedTalkcraftNativeTitleIds = talkcraftNativeTitleBindings.map((binding) => binding.id);
const bindingsById = new Map(talkcraftNativeTitleBindings.map((binding) => [binding.id, binding]));

export const isTalkcraftNativeTitleId = (componentId: string): boolean => bindingsById.has(componentId);

export const talkcraftNativeTitlePropsForShot = (shot: TimelineShot): Record<string, unknown> | null => {
  const binding = bindingsById.get(shot.component_id);
  if (!binding) return null;
  const props = binding.props(resolveTalkcraftTitleCopy(shot), shot);
  return props;
};

export const talkcraftNativeTitleBindingSummary = talkcraftNativeTitleBindings.map(({id, source, role, motion, content_constraints}) => ({id, source, role, motion, content_constraints}));

export const TALKCRAFT_PRODUCTION_TITLE_CSS = `
* { box-sizing: border-box; }
div { background: transparent !important; }
style + div { overflow: visible !important; }
.talkcraft-native-title, .talkcraft-native-title * { color: #f8fafc !important; }
.talkcraft-native-title .host-wrap, .talkcraft-native-title [class$='-host'], .talkcraft-native-title .host { display: none !important; }
.talkcraft-native-title .caption-zone { bottom: auto !important; top: 96px !important; align-items: center !important; }
.talkcraft-native-title .caption { color: #f8fafc !important; font-size: 62px !important; line-height: 1.12 !important; white-space: normal !important; max-width: 820px !important; text-align: center !important; }
.talkcraft-native-title .caption .kw { color: #ffffff !important; padding: 0 .12em !important; }
.talkcraft-native-title .caption .kw::before { background: rgba(56,189,248,0.24) !important; border: 2px solid rgba(125,211,252,0.64) !important; }
.talkcraft-native-title .wsc-pill { background: rgba(56,189,248,0.18) !important; border: 2px solid rgba(125,211,252,0.7) !important; color: #f8fafc !important; }
.talkcraft-native-title .wsc-final { color: #7dd3fc !important; }
.talkcraft-native-title .sr-line, .talkcraft-native-title .ert-tw, .talkcraft-native-title .say, .talkcraft-native-title .scv-ttl { color: #f8fafc !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-typewriter-reveal'] .stamp { left: 40px !important; right: 40px !important; bottom: auto !important; top: 32px !important; color: #f8fafc !important; white-space: normal !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-typewriter-reveal'] .stamp .line1 { font-size: 52px !important; line-height: 1.12 !important; white-space: normal !important; letter-spacing: 0 !important; color: #f8fafc !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-typewriter-reveal'] .stamp .line2 { font-size: 32px !important; line-height: 1.2 !important; white-space: normal !important; margin-top: 18px !important; letter-spacing: 0 !important; color: rgba(226,232,240,0.92) !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-typewriter-reveal'] .cursor { background: #7dd3fc !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-title-demote-to-label'] .tdl-ttl { color: #f8fafc !important; font-size: 54px !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-title-demote-to-label'] .tdl-content { top: 130px !important; left: 80px !important; right: 80px !important; width: auto !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-title-demote-to-label'] .tdl-blk { height: 50px !important; margin-bottom: 12px !important; font-size: 38px !important; color: #f8fafc !important; gap: 14px !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-title-demote-to-label'] .tdl-blk i { height: 36px !important; background: #38bdf8 !important; }
.talkcraft-native-title[data-compact-slot='true'][data-component-id='Talkcraft-title-demote-to-label'] .tdl-blk span { background: transparent !important; height: 50px !important; line-height: 50px !important; padding: 0 !important; color: #f8fafc !important; white-space: normal !important; }
.talkcraft-native-title[data-component-id='Talkcraft-keyword-pop-highlight'] div[style*='radial-gradient'] { display: none !important; }
.talkcraft-native-title[data-component-sample='true'][data-layer-role='emphasis'][data-component-id='Talkcraft-keyword-pop-highlight'] .caption-zone { bottom: auto !important; top: 112px !important; align-items: center !important; }
.talkcraft-native-title[data-component-sample='true'][data-layer-role='emphasis'][data-component-id='Talkcraft-keyword-pop-highlight'] .caption { font-size: 64px !important; line-height: 1.08 !important; }
.host-wrap, [class$='-host'], .host { display: none !important; }
.io-line { max-width: 820px !important; white-space: normal !important; font-size: 58px !important; line-height: 1.1 !important; }
.io-sub { max-width: 820px !important; white-space: normal !important; }
.quote-line { font-size: 38px !important; line-height: 1.35 !important; }
.quote-line.key { font-size: 54px !important; line-height: 1.16 !important; }
.doc-head { font-size: 20px !important; }
.title, .headline, h1, h2 { font-size: 54px !important; line-height: 1.08 !important; }
.body, .subtitle, .subline, p { font-size: 38px !important; line-height: 1.22 !important; }
`;

export const TalkcraftNativeTitle = ({shot, layerRole = 'title', componentSample = false, style, slotWidth, slotHeight}: {
  shot: TimelineShot;
  layerRole?: 'title' | 'emphasis';
  componentSample?: boolean;
  style?: CSSProperties;
  slotWidth?: number;
  slotHeight?: number;
}) => {
  const {width, height} = useVideoConfig();
  const binding = bindingsById.get(shot.component_id);
  if (!binding) return null;
  const props = binding.props(resolveTalkcraftTitleCopy(shot), shot);
  if (!props) {
    throw new Error(`Talkcraft native title ${shot.component_id} is missing production content (${binding.content_constraints.join(', ')})`);
  }
  const sampleEmphasis = componentSample && layerRole === 'emphasis';
  const sourceHeight = sampleEmphasis ? 300 : slotHeight !== undefined
    ? shot.component_id === 'Talkcraft-typewriter-reveal' ? 300 : 380
    : TALKCRAFT_TITLE_SAFE_BOX.sourceHeight;
  const safeHeight = slotHeight ?? (sampleEmphasis ? 300 : TALKCRAFT_TITLE_SAFE_BOX.height);
  const safeWidth = slotWidth ?? TALKCRAFT_TITLE_SAFE_BOX.width;
  const scale = Math.min(safeWidth / TALKCRAFT_TITLE_SAFE_BOX.sourceWidth, safeHeight / sourceHeight);
  const renderedWidth = TALKCRAFT_TITLE_SAFE_BOX.sourceWidth * scale;
  const renderedHeight = sourceHeight * scale;
  const left = slotWidth !== undefined ? (slotWidth - renderedWidth) / 2 : (width - renderedWidth) / 2;
  const top = slotHeight !== undefined ? (slotHeight - renderedHeight) / 2 : sampleEmphasis ? 0 : Math.min(TALKCRAFT_TITLE_SAFE_BOX.y, Math.max(0, height * 0.09));
  return (
    <AbsoluteFill style={{background: 'transparent', pointerEvents: 'none', ...style}}>
      <div style={{position: 'absolute', left, top, width: TALKCRAFT_TITLE_SAFE_BOX.sourceWidth,
        height: sourceHeight, transform: `scale(${scale})`, transformOrigin: 'top left',
        overflow: 'visible'}}>
        <IsolatedCard>
          <style>{TALKCRAFT_PRODUCTION_TITLE_CSS}</style>
          <div className="talkcraft-native-title" data-component-id={binding.id} data-layer-role={layerRole} data-component-sample={componentSample ? 'true' : 'false'} data-compact-slot={slotWidth !== undefined ? 'true' : 'false'}>
            {React.createElement(binding.Component, props)}
          </div>
        </IsolatedCard>
      </div>
    </AbsoluteFill>
  );
};
