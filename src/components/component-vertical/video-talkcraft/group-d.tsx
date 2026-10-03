import {useCurrentFrame} from 'remotion';
import {IsolatedCard} from '../../community/IsolatedCard';
import {originalPreviewPropsAtFrame} from '../../component-horizontal/video-talkcraft/preview-props';
import Card0, {meta as meta0} from './whip-pan-transition';
import Card1, {meta as meta1} from './caret-wipe-transition';
import Card2, {meta as meta2} from './chapter-progress-list';
import Card3, {meta as meta3} from './line-carry-transition';
import Card4, {meta as meta4} from './long-take-world';
import Card5, {meta as meta5} from './impact-open-title';
import Card6, {meta as meta6} from './keyword-pop-highlight';
import Card7, {meta as meta7} from './slab-punch-title';
import Card8, {meta as meta8} from './title-demote-to-label';
import Card9, {meta as meta9} from './type-contrast-emphasis';
import Card10, {meta as meta10} from './word-slot-cycle';
import Card11, {meta as meta11} from './alt-block-lines';
import Card12, {meta as meta12} from './count-badge-title';
import Card13, {meta as meta13} from './error-retype';
import Card14, {meta as meta14} from './lead-word-zoom-assemble';
import Card15, {meta as meta15} from './line-by-line-slide';
import Card16, {meta as meta16} from './outline-box-title';
import Card17, {meta as meta17} from './per-character-rise';
import Card18, {meta as meta18} from './quote-bracket-pull';
import Card19, {meta as meta19} from './quote-card';
import Card20, {meta as meta20} from './soft-blur-in';
import Card21, {meta as meta21} from './speed-slab-title';
import Card22, {meta as meta22} from './tracking-in';
import Card23, {meta as meta23} from './typewriter-reveal';
import Card24, {meta as meta24} from './countdown-arc-scatter';
import Card25, {meta as meta25} from './flying-words';
import Card26, {meta as meta26} from './split-text-stagger';

const portraitPropsAtFrame = (slug: string, frame: number) => {
  const {hostSrc: _hostSrc, ...props} = originalPreviewPropsAtFrame(slug, frame);
  void _hostSrc;
  return props;
};

export const nativeDemos = [
  {id: 'Talkcraft-whip-pan-transition', name: "横甩转场", slug: 'whip-pan-transition', width: meta0.width, height: meta0.height, fps: meta0.fps, durationInFrames: meta0.durationInFrames, component: function PortraitDemo0() { const frame = useCurrentFrame(); return <IsolatedCard><Card0 {...portraitPropsAtFrame('whip-pan-transition', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-caret-wipe-transition', name: "光标擦除", slug: 'caret-wipe-transition', width: meta1.width, height: meta1.height, fps: meta1.fps, durationInFrames: meta1.durationInFrames, component: function PortraitDemo1() { const frame = useCurrentFrame(); return <IsolatedCard><Card1 {...portraitPropsAtFrame('caret-wipe-transition', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-chapter-progress-list', name: "章节进度", slug: 'chapter-progress-list', width: meta2.width, height: meta2.height, fps: meta2.fps, durationInFrames: meta2.durationInFrames, component: function PortraitDemo2() { const frame = useCurrentFrame(); return <IsolatedCard><Card2 {...portraitPropsAtFrame('chapter-progress-list', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-line-carry-transition', name: "线条接力", slug: 'line-carry-transition', width: meta3.width, height: meta3.height, fps: meta3.fps, durationInFrames: meta3.durationInFrames, component: function PortraitDemo3() { const frame = useCurrentFrame(); return <IsolatedCard><Card3 {...portraitPropsAtFrame('line-carry-transition', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-long-take-world', name: "长镜头世界", slug: 'long-take-world', width: meta4.width, height: meta4.height, fps: meta4.fps, durationInFrames: meta4.durationInFrames, component: function PortraitDemo4() { const frame = useCurrentFrame(); return <IsolatedCard><Card4 {...portraitPropsAtFrame('long-take-world', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-impact-open-title', name: "冲击开场", slug: 'impact-open-title', width: meta5.width, height: meta5.height, fps: meta5.fps, durationInFrames: meta5.durationInFrames, component: function PortraitDemo5() { const frame = useCurrentFrame(); return <IsolatedCard><Card5 {...portraitPropsAtFrame('impact-open-title', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-keyword-pop-highlight', name: "关键词弹出", slug: 'keyword-pop-highlight', width: meta6.width, height: meta6.height, fps: meta6.fps, durationInFrames: meta6.durationInFrames, component: function PortraitDemo6() { const frame = useCurrentFrame(); return <IsolatedCard><Card6 {...portraitPropsAtFrame('keyword-pop-highlight', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-slab-punch-title', name: "重点放大", slug: 'slab-punch-title', width: meta7.width, height: meta7.height, fps: meta7.fps, durationInFrames: meta7.durationInFrames, component: function PortraitDemo7() { const frame = useCurrentFrame(); return <IsolatedCard><Card7 {...portraitPropsAtFrame('slab-punch-title', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-title-demote-to-label', name: "标题降格成标签", slug: 'title-demote-to-label', width: meta8.width, height: meta8.height, fps: meta8.fps, durationInFrames: meta8.durationInFrames, component: function PortraitDemo8() { const frame = useCurrentFrame(); return <IsolatedCard><Card8 {...portraitPropsAtFrame('title-demote-to-label', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-type-contrast-emphasis', name: "字体对比重音", slug: 'type-contrast-emphasis', width: meta9.width, height: meta9.height, fps: meta9.fps, durationInFrames: meta9.durationInFrames, component: function PortraitDemo9() { const frame = useCurrentFrame(); return <IsolatedCard><Card9 {...portraitPropsAtFrame('type-contrast-emphasis', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-word-slot-cycle', name: "词槽轮换", slug: 'word-slot-cycle', width: meta10.width, height: meta10.height, fps: meta10.fps, durationInFrames: meta10.durationInFrames, component: function PortraitDemo10() { const frame = useCurrentFrame(); return <IsolatedCard><Card10 {...portraitPropsAtFrame('word-slot-cycle', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-alt-block-lines', name: "双色块对句", slug: 'alt-block-lines', width: meta11.width, height: meta11.height, fps: meta11.fps, durationInFrames: meta11.durationInFrames, component: function PortraitDemo11() { const frame = useCurrentFrame(); return <IsolatedCard><Card11 {...portraitPropsAtFrame('alt-block-lines', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-count-badge-title', name: "数字重音标题", slug: 'count-badge-title', width: meta12.width, height: meta12.height, fps: meta12.fps, durationInFrames: meta12.durationInFrames, component: function PortraitDemo12() { const frame = useCurrentFrame(); return <IsolatedCard><Card12 {...portraitPropsAtFrame('count-badge-title', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-error-retype', name: "打字改口", slug: 'error-retype', width: meta13.width, height: meta13.height, fps: meta13.fps, durationInFrames: meta13.durationInFrames, component: function PortraitDemo13() { const frame = useCurrentFrame(); return <IsolatedCard><Card13 {...portraitPropsAtFrame('error-retype', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-lead-word-zoom-assemble', name: "首词占满补句", slug: 'lead-word-zoom-assemble', width: meta14.width, height: meta14.height, fps: meta14.fps, durationInFrames: meta14.durationInFrames, component: function PortraitDemo14() { const frame = useCurrentFrame(); return <IsolatedCard><Card14 {...portraitPropsAtFrame('lead-word-zoom-assemble', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-line-by-line-slide', name: "逐行滑入", slug: 'line-by-line-slide', width: meta15.width, height: meta15.height, fps: meta15.fps, durationInFrames: meta15.durationInFrames, component: function PortraitDemo15() { const frame = useCurrentFrame(); return <IsolatedCard><Card15 {...portraitPropsAtFrame('line-by-line-slide', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-outline-box-title', name: "描边框标题", slug: 'outline-box-title', width: meta16.width, height: meta16.height, fps: meta16.fps, durationInFrames: meta16.durationInFrames, component: function PortraitDemo16() { const frame = useCurrentFrame(); return <IsolatedCard><Card16 {...portraitPropsAtFrame('outline-box-title', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-per-character-rise', name: "逐字升起", slug: 'per-character-rise', width: meta17.width, height: meta17.height, fps: meta17.fps, durationInFrames: meta17.durationInFrames, component: function PortraitDemo17() { const frame = useCurrentFrame(); return <IsolatedCard><Card17 {...portraitPropsAtFrame('per-character-rise', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-quote-bracket-pull', name: "引号夹句", slug: 'quote-bracket-pull', width: meta18.width, height: meta18.height, fps: meta18.fps, durationInFrames: meta18.durationInFrames, component: function PortraitDemo18() { const frame = useCurrentFrame(); return <IsolatedCard><Card18 {...portraitPropsAtFrame('quote-bracket-pull', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-quote-card', name: "金句大字卡", slug: 'quote-card', width: meta19.width, height: meta19.height, fps: meta19.fps, durationInFrames: meta19.durationInFrames, component: function PortraitDemo19() { const frame = useCurrentFrame(); return <IsolatedCard><Card19 {...portraitPropsAtFrame('quote-card', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-soft-blur-in', name: "柔焦淡入", slug: 'soft-blur-in', width: meta20.width, height: meta20.height, fps: meta20.fps, durationInFrames: meta20.durationInFrames, component: function PortraitDemo20() { const frame = useCurrentFrame(); return <IsolatedCard><Card20 {...portraitPropsAtFrame('soft-blur-in', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-speed-slab-title', name: "速度块标题", slug: 'speed-slab-title', width: meta21.width, height: meta21.height, fps: meta21.fps, durationInFrames: meta21.durationInFrames, component: function PortraitDemo21() { const frame = useCurrentFrame(); return <IsolatedCard><Card21 {...portraitPropsAtFrame('speed-slab-title', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-tracking-in', name: "字距收拢", slug: 'tracking-in', width: meta22.width, height: meta22.height, fps: meta22.fps, durationInFrames: meta22.durationInFrames, component: function PortraitDemo22() { const frame = useCurrentFrame(); return <IsolatedCard><Card22 {...portraitPropsAtFrame('tracking-in', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-typewriter-reveal', name: "打字机档案戳", slug: 'typewriter-reveal', width: meta23.width, height: meta23.height, fps: meta23.fps, durationInFrames: meta23.durationInFrames, component: function PortraitDemo23() { const frame = useCurrentFrame(); return <IsolatedCard><Card23 {...portraitPropsAtFrame('typewriter-reveal', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-countdown-arc-scatter', name: "数字弧落标题", slug: 'countdown-arc-scatter', width: meta24.width, height: meta24.height, fps: meta24.fps, durationInFrames: meta24.durationInFrames, component: function PortraitDemo24() { const frame = useCurrentFrame(); return <IsolatedCard><Card24 {...portraitPropsAtFrame('countdown-arc-scatter', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-flying-words', name: "关键词隧道", slug: 'flying-words', width: meta25.width, height: meta25.height, fps: meta25.fps, durationInFrames: meta25.durationInFrames, component: function PortraitDemo25() { const frame = useCurrentFrame(); return <IsolatedCard><Card25 {...portraitPropsAtFrame('flying-words', frame)} /></IsolatedCard>; }},
  {id: 'Talkcraft-split-text-stagger', name: "逐字裂升", slug: 'split-text-stagger', width: meta26.width, height: meta26.height, fps: meta26.fps, durationInFrames: meta26.durationInFrames, component: function PortraitDemo26() { const frame = useCurrentFrame(); return <IsolatedCard><Card26 {...portraitPropsAtFrame('split-text-stagger', frame)} /></IsolatedCard>; }},
];
