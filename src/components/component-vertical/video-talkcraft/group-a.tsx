import {useCurrentFrame} from 'remotion';
import {IsolatedCard} from '../../community/IsolatedCard';
import {componentDemos} from '../../component-horizontal/video-talkcraft/demo';
import {originalPreviewPropsAtFrame} from '../../component-horizontal/video-talkcraft/preview-props';
import Card0, {meta as Meta0} from './focus-dim-spotlight';
import Card1, {meta as Meta1} from './hand-drawn-ellipse';
import Card2, {meta as Meta2} from './highlighter-sweep';
import Card3, {meta as Meta3} from './scribble-annotation';
import Card4, {meta as Meta4} from './callout-line-label';
import Card5, {meta as Meta5} from './converging-arrows';
import Card6, {meta as Meta6} from './corner-bracket-frame';
import Card7, {meta as Meta7} from './crash-zoom-punch';
import Card8, {meta as Meta8} from './ink-underline';
import Card9, {meta as Meta9} from './magnifier-detail';
import Card10, {meta as Meta10} from './quote-hold-arrow';
import Card11, {meta as Meta11} from './scanline-annotate';
import Card12, {meta as Meta12} from './strike-and-replace';
import Card13, {meta as Meta13} from './reticle-lock-on';
import Card14, {meta as Meta14} from './lower-third-nameplate';
import Card15, {meta as Meta15} from './parallel-items-with-host';
import Card16, {meta as Meta16} from './behind-text-title';
import Card17, {meta as Meta17} from './chevron-lower-third';
import Card18, {meta as Meta18} from './danmu-bubble-praise';
import Card19, {meta as Meta19} from './douyin-follow-card';
import Card20, {meta as Meta20} from './host-card-glass-board';
import Card21, {meta as Meta21} from './host-shrink-to-chip';
import Card22, {meta as Meta22} from './subscribe-cta';
import Card23, {meta as Meta23} from './x-follow-card';
import Card24, {meta as Meta24} from './bar-chart-growth';
import Card25, {meta as Meta25} from './chart-grow';
import Card26, {meta as Meta26} from './line-chart-story-draw';

const ownedSlugs = ['focus-dim-spotlight', 'hand-drawn-ellipse', 'highlighter-sweep', 'scribble-annotation', 'callout-line-label', 'converging-arrows', 'corner-bracket-frame', 'crash-zoom-punch', 'ink-underline', 'magnifier-detail', 'quote-hold-arrow', 'scanline-annotate', 'strike-and-replace', 'reticle-lock-on', 'lower-third-nameplate', 'parallel-items-with-host', 'behind-text-title', 'chevron-lower-third', 'danmu-bubble-praise', 'douyin-follow-card', 'host-card-glass-board', 'host-shrink-to-chip', 'subscribe-cta', 'x-follow-card', 'bar-chart-growth', 'chart-grow', 'line-chart-story-draw'] as const;
const cards = {
  'focus-dim-spotlight': {component: Card0, meta: Meta0},
  'hand-drawn-ellipse': {component: Card1, meta: Meta1},
  'highlighter-sweep': {component: Card2, meta: Meta2},
  'scribble-annotation': {component: Card3, meta: Meta3},
  'callout-line-label': {component: Card4, meta: Meta4},
  'converging-arrows': {component: Card5, meta: Meta5},
  'corner-bracket-frame': {component: Card6, meta: Meta6},
  'crash-zoom-punch': {component: Card7, meta: Meta7},
  'ink-underline': {component: Card8, meta: Meta8},
  'magnifier-detail': {component: Card9, meta: Meta9},
  'quote-hold-arrow': {component: Card10, meta: Meta10},
  'scanline-annotate': {component: Card11, meta: Meta11},
  'strike-and-replace': {component: Card12, meta: Meta12},
  'reticle-lock-on': {component: Card13, meta: Meta13},
  'lower-third-nameplate': {component: Card14, meta: Meta14},
  'parallel-items-with-host': {component: Card15, meta: Meta15},
  'behind-text-title': {component: Card16, meta: Meta16},
  'chevron-lower-third': {component: Card17, meta: Meta17},
  'danmu-bubble-praise': {component: Card18, meta: Meta18},
  'douyin-follow-card': {component: Card19, meta: Meta19},
  'host-card-glass-board': {component: Card20, meta: Meta20},
  'host-shrink-to-chip': {component: Card21, meta: Meta21},
  'subscribe-cta': {component: Card22, meta: Meta22},
  'x-follow-card': {component: Card23, meta: Meta23},
  'bar-chart-growth': {component: Card24, meta: Meta24},
  'chart-grow': {component: Card25, meta: Meta25},
  'line-chart-story-draw': {component: Card26, meta: Meta26},
} as const;

export const nativeDemos = ownedSlugs.map((slug) => {
  const source = componentDemos.find((demo) => demo.slug === slug);
  if (!source) throw new Error('Missing Talkcraft source demo for ' + slug);
  const card = cards[slug];
  const Component = () => {
    const frame = useCurrentFrame();
    const Card = card.component;
    return <IsolatedCard><Card {...originalPreviewPropsAtFrame(slug, frame)} /></IsolatedCard>;
  };
  return {...source, id: source.id, component: Component, width: card.meta.width, height: card.meta.height, fps: card.meta.fps, durationInFrames: card.meta.durationInFrames, portraitSource: 'src/components/component-vertical/video-talkcraft/' + slug + '.tsx'};
});
