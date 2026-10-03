import {useCurrentFrame} from 'remotion';
import {IsolatedCard} from '../../community/IsolatedCard';
import {originalPreviewPropsAtFrame} from './preview-props';
import * as Card0 from './cards/focus-dim-spotlight';
import * as Card1 from './cards/hand-drawn-ellipse';
import * as Card2 from './cards/highlighter-sweep';
import * as Card3 from './cards/scribble-annotation';
import * as Card4 from './cards/callout-line-label';
import * as Card5 from './cards/converging-arrows';
import * as Card6 from './cards/corner-bracket-frame';
import * as Card7 from './cards/crash-zoom-punch';
import * as Card8 from './cards/ink-underline';
import * as Card9 from './cards/magnifier-detail';
import * as Card10 from './cards/quote-hold-arrow';
import * as Card11 from './cards/scanline-annotate';
import * as Card12 from './cards/strike-and-replace';
import * as Card13 from './cards/reticle-lock-on';
import * as Card14 from './cards/lower-third-nameplate';
import * as Card15 from './cards/parallel-items-with-host';
import * as Card16 from './cards/behind-text-title';
import * as Card17 from './cards/chevron-lower-third';
import * as Card18 from './cards/danmu-bubble-praise';
import * as Card19 from './cards/douyin-follow-card';
import * as Card20 from './cards/host-card-glass-board';
import * as Card21 from './cards/host-shrink-to-chip';
import * as Card22 from './cards/subscribe-cta';
import * as Card23 from './cards/x-follow-card';
import * as Card24 from './cards/bar-chart-growth';
import * as Card25 from './cards/chart-grow';
import * as Card26 from './cards/line-chart-story-draw';
import * as Card27 from './cards/metric-with-sparkline';
import * as Card28 from './cards/number-counter';
import * as Card29 from './cards/number-slab-pop';
import * as Card30 from './cards/unit-grid-proportion';
import * as Card31 from './cards/chip-grid-single-select';
import * as Card32 from './cards/info-term-card';
import * as Card33 from './cards/map-route-pin';
import * as Card34 from './cards/numbered-step-stack';
import * as Card35 from './cards/step-timeline-vertical';
import * as Card36 from './cards/ui-prop-theater';
import * as Card37 from './cards/source-converge';
import * as Card38 from './cards/bed-echo-blur';
import * as Card39 from './cards/chat-message-flow';
import * as Card40 from './cards/cursor-actor-demo';
import * as Card41 from './cards/evidence-scroll-tour';
import * as Card42 from './cards/media-pop-in';
import * as Card43 from './cards/news-card-desk';
import * as Card44 from './cards/split-compare-slider';
import * as Card45 from './cards/still-layout-relay';
import * as Card46 from './cards/ui-flow-theater';
import * as Card47 from './cards/chat-gpt';
import * as Card48 from './cards/claude-code';
import * as Card49 from './cards/doc-park-left-pill-deal';
import * as Card50 from './cards/filmstrip-conveyor';
import * as Card51 from './cards/gallery-wall-dolly';
import * as Card52 from './cards/glass-code-walk';
import * as Card53 from './cards/gooey-morph';
import * as Card54 from './cards/grid-to-hero';
import * as Card55 from './cards/info-card-assemble';
import * as Card56 from './cards/logo-enter';
import * as Card57 from './cards/motion-blur-slam-in';
import * as Card58 from './cards/pencil-sketch-draw';
import * as Card59 from './cards/rack-focus-pair';
import * as Card60 from './cards/split-60-40-story';
import * as Card61 from './cards/stack-fan-out';
import * as Card62 from './cards/terminal-typing-log';
import * as Card63 from './cards/timeline-photo-strip';
import * as Card64 from './cards/word-relay-filmstrip';
import * as Card65 from './cards/slow-pull-reveal';
import * as Card66 from './cards/slow-push-in';
import * as Card67 from './cards/cursor-locked-zoom';
import * as Card68 from './cards/orbit-drift';
import * as Card69 from './cards/pip-zoom-box';
import * as Card70 from './cards/stage-keyframe-tour';
import * as Card71 from './cards/sway-parallax';
import * as Card72 from './cards/tilt-3d-page';
import * as Card73 from './cards/black-slam-transition';
import * as Card74 from './cards/chapter-title-card';
import * as Card75 from './cards/color-slam-beat-card';
import * as Card76 from './cards/overexpose-flip-transition';
import * as Card77 from './cards/particle-weld-transition';
import * as Card78 from './cards/pullback-cool-transition';
import * as Card79 from './cards/push-through-transition';
import * as Card80 from './cards/shape-wipe-transition';
import * as Card81 from './cards/whip-pan-transition';
import * as Card82 from './cards/caret-wipe-transition';
import * as Card83 from './cards/chapter-progress-list';
import * as Card84 from './cards/line-carry-transition';
import * as Card85 from './cards/long-take-world';
import * as Card86 from './cards/impact-open-title';
import * as Card87 from './cards/keyword-pop-highlight';
import * as Card88 from './cards/slab-punch-title';
import * as Card89 from './cards/title-demote-to-label';
import * as Card90 from './cards/type-contrast-emphasis';
import * as Card91 from './cards/word-slot-cycle';
import * as Card92 from './cards/alt-block-lines';
import * as Card93 from './cards/count-badge-title';
import * as Card94 from './cards/error-retype';
import * as Card95 from './cards/lead-word-zoom-assemble';
import * as Card96 from './cards/line-by-line-slide';
import * as Card97 from './cards/outline-box-title';
import * as Card98 from './cards/per-character-rise';
import * as Card99 from './cards/quote-bracket-pull';
import * as Card100 from './cards/quote-card';
import * as Card101 from './cards/soft-blur-in';
import * as Card102 from './cards/speed-slab-title';
import * as Card103 from './cards/tracking-in';
import * as Card104 from './cards/typewriter-reveal';
import * as Card105 from './cards/countdown-arc-scatter';
import * as Card106 from './cards/flying-words';
import * as Card107 from './cards/split-text-stagger';

// Original meta is evaluated by Remotion; no guessed dimensions or durations.
export const componentDemos = [
  {id: 'Talkcraft-focus-dim-spotlight', name: "聚焦压暗切换", slug: 'focus-dim-spotlight', component: function CardDemo0() {return <IsolatedCard><Card0.default {...originalPreviewPropsAtFrame('focus-dim-spotlight', useCurrentFrame())} /></IsolatedCard>;}, ...Card0.meta},
  {id: 'Talkcraft-hand-drawn-ellipse', name: "手绘圈重点", slug: 'hand-drawn-ellipse', component: function CardDemo1() {return <IsolatedCard><Card1.default {...originalPreviewPropsAtFrame('hand-drawn-ellipse', useCurrentFrame())} /></IsolatedCard>;}, ...Card1.meta},
  {id: 'Talkcraft-highlighter-sweep', name: "荧光笔高亮扫过", slug: 'highlighter-sweep', component: function CardDemo2() {return <IsolatedCard><Card2.default {...originalPreviewPropsAtFrame('highlighter-sweep', useCurrentFrame())} /></IsolatedCard>;}, ...Card2.meta},
  {id: 'Talkcraft-scribble-annotation', name: "手绘圈注箭头", slug: 'scribble-annotation', component: function CardDemo3() {return <IsolatedCard><Card3.default {...originalPreviewPropsAtFrame('scribble-annotation', useCurrentFrame())} /></IsolatedCard>;}, ...Card3.meta},
  {id: 'Talkcraft-callout-line-label', name: "标注引出线", slug: 'callout-line-label', component: function CardDemo4() {return <IsolatedCard><Card4.default {...originalPreviewPropsAtFrame('callout-line-label', useCurrentFrame())} /></IsolatedCard>;}, ...Card4.meta},
  {id: 'Talkcraft-converging-arrows', name: "双箭头聚焦", slug: 'converging-arrows', component: function CardDemo5() {return <IsolatedCard><Card5.default {...originalPreviewPropsAtFrame('converging-arrows', useCurrentFrame())} /></IsolatedCard>;}, ...Card5.meta},
  {id: 'Talkcraft-corner-bracket-frame', name: "对角角框", slug: 'corner-bracket-frame', component: function CardDemo6() {return <IsolatedCard><Card6.default {...originalPreviewPropsAtFrame('corner-bracket-frame', useCurrentFrame())} /></IsolatedCard>;}, ...Card6.meta},
  {id: 'Talkcraft-crash-zoom-punch', name: "急推特写", slug: 'crash-zoom-punch', component: function CardDemo7() {return <IsolatedCard><Card7.default {...originalPreviewPropsAtFrame('crash-zoom-punch', useCurrentFrame())} /></IsolatedCard>;}, ...Card7.meta},
  {id: 'Talkcraft-ink-underline', name: "墨迹下划线", slug: 'ink-underline', component: function CardDemo8() {return <IsolatedCard><Card8.default {...originalPreviewPropsAtFrame('ink-underline', useCurrentFrame())} /></IsolatedCard>;}, ...Card8.meta},
  {id: 'Talkcraft-magnifier-detail', name: "局部放大镜", slug: 'magnifier-detail', component: function CardDemo9() {return <IsolatedCard><Card9.default {...originalPreviewPropsAtFrame('magnifier-detail', useCurrentFrame())} /></IsolatedCard>;}, ...Card9.meta},
  {id: 'Talkcraft-quote-hold-arrow', name: "金句停留", slug: 'quote-hold-arrow', component: function CardDemo10() {return <IsolatedCard><Card10.default {...originalPreviewPropsAtFrame('quote-hold-arrow', useCurrentFrame())} /></IsolatedCard>;}, ...Card10.meta},
  {id: 'Talkcraft-scanline-annotate', name: "扫描线逐处点名", slug: 'scanline-annotate', component: function CardDemo11() {return <IsolatedCard><Card11.default {...originalPreviewPropsAtFrame('scanline-annotate', useCurrentFrame())} /></IsolatedCard>;}, ...Card11.meta},
  {id: 'Talkcraft-strike-and-replace', name: "划线纠错替换", slug: 'strike-and-replace', component: function CardDemo12() {return <IsolatedCard><Card12.default {...originalPreviewPropsAtFrame('strike-and-replace', useCurrentFrame())} /></IsolatedCard>;}, ...Card12.meta},
  {id: 'Talkcraft-reticle-lock-on', name: "准星咬合", slug: 'reticle-lock-on', component: function CardDemo13() {return <IsolatedCard><Card13.default {...originalPreviewPropsAtFrame('reticle-lock-on', useCurrentFrame())} /></IsolatedCard>;}, ...Card13.meta},
  {id: 'Talkcraft-lower-third-nameplate', name: "人名条展示牌", slug: 'lower-third-nameplate', component: function CardDemo14() {return <IsolatedCard><Card14.default {...originalPreviewPropsAtFrame('lower-third-nameplate', useCurrentFrame())} /></IsolatedCard>;}, ...Card14.meta},
  {id: 'Talkcraft-parallel-items-with-host', name: "并列句排版（人物在场）", slug: 'parallel-items-with-host', component: function CardDemo15() {return <IsolatedCard><Card15.default {...originalPreviewPropsAtFrame('parallel-items-with-host', useCurrentFrame())} /></IsolatedCard>;}, ...Card15.meta},
  {id: 'Talkcraft-behind-text-title', name: "人后大字视差", slug: 'behind-text-title', component: function CardDemo16() {return <IsolatedCard><Card16.default {...originalPreviewPropsAtFrame('behind-text-title', useCurrentFrame())} /></IsolatedCard>;}, ...Card16.meta},
  {id: 'Talkcraft-chevron-lower-third', name: "动态人名条", slug: 'chevron-lower-third', component: function CardDemo17() {return <IsolatedCard><Card17.default {...originalPreviewPropsAtFrame('chevron-lower-third', useCurrentFrame())} /></IsolatedCard>;}, ...Card17.meta},
  {id: 'Talkcraft-danmu-bubble-praise', name: "弹幕气泡", slug: 'danmu-bubble-praise', component: function CardDemo18() {return <IsolatedCard><Card18.default {...originalPreviewPropsAtFrame('danmu-bubble-praise', useCurrentFrame())} /></IsolatedCard>;}, ...Card18.meta},
  {id: 'Talkcraft-douyin-follow-card', name: "抖音主页关注卡", slug: 'douyin-follow-card', component: function CardDemo19() {return <IsolatedCard><Card19.default {...originalPreviewPropsAtFrame('douyin-follow-card', useCurrentFrame())} /></IsolatedCard>;}, ...Card19.meta},
  {id: 'Talkcraft-host-card-glass-board', name: "人物竖卡玻璃台", slug: 'host-card-glass-board', component: function CardDemo20() {return <IsolatedCard><Card20.default {...originalPreviewPropsAtFrame('host-card-glass-board', useCurrentFrame())} /></IsolatedCard>;}, ...Card20.meta},
  {id: 'Talkcraft-host-shrink-to-chip', name: "人物缩位让台", slug: 'host-shrink-to-chip', component: function CardDemo21() {return <IsolatedCard><Card21.default {...originalPreviewPropsAtFrame('host-shrink-to-chip', useCurrentFrame())} /></IsolatedCard>;}, ...Card21.meta},
  {id: 'Talkcraft-subscribe-cta', name: "多平台关注 CTA", slug: 'subscribe-cta', component: function CardDemo22() {return <IsolatedCard><Card22.default {...originalPreviewPropsAtFrame('subscribe-cta', useCurrentFrame())} /></IsolatedCard>;}, ...Card22.meta},
  {id: 'Talkcraft-x-follow-card', name: "关注卡弹出", slug: 'x-follow-card', component: function CardDemo23() {return <IsolatedCard><Card23.default {...originalPreviewPropsAtFrame('x-follow-card', useCurrentFrame())} /></IsolatedCard>;}, ...Card23.meta},
  {id: 'Talkcraft-bar-chart-growth', name: "柱状增长", slug: 'bar-chart-growth', component: function CardDemo24() {return <IsolatedCard><Card24.default {...originalPreviewPropsAtFrame('bar-chart-growth', useCurrentFrame())} /></IsolatedCard>;}, ...Card24.meta},
  {id: 'Talkcraft-chart-grow', name: "图表生长", slug: 'chart-grow', component: function CardDemo25() {return <IsolatedCard><Card25.default {...originalPreviewPropsAtFrame('chart-grow', useCurrentFrame())} /></IsolatedCard>;}, ...Card25.meta},
  {id: 'Talkcraft-line-chart-story-draw', name: "折线分段推演", slug: 'line-chart-story-draw', component: function CardDemo26() {return <IsolatedCard><Card26.default {...originalPreviewPropsAtFrame('line-chart-story-draw', useCurrentFrame())} /></IsolatedCard>;}, ...Card26.meta},
  {id: 'Talkcraft-metric-with-sparkline', name: "数字带趋势", slug: 'metric-with-sparkline', component: function CardDemo27() {return <IsolatedCard><Card27.default {...originalPreviewPropsAtFrame('metric-with-sparkline', useCurrentFrame())} /></IsolatedCard>;}, ...Card27.meta},
  {id: 'Talkcraft-number-counter', name: "数字滚动计数", slug: 'number-counter', component: function CardDemo28() {return <IsolatedCard><Card28.default {...originalPreviewPropsAtFrame('number-counter', useCurrentFrame())} /></IsolatedCard>;}, ...Card28.meta},
  {id: 'Talkcraft-number-slab-pop', name: "数字弹出", slug: 'number-slab-pop', component: function CardDemo29() {return <IsolatedCard><Card29.default {...originalPreviewPropsAtFrame('number-slab-pop', useCurrentFrame())} /></IsolatedCard>;}, ...Card29.meta},
  {id: 'Talkcraft-unit-grid-proportion', name: "点阵比例图", slug: 'unit-grid-proportion', component: function CardDemo30() {return <IsolatedCard><Card30.default {...originalPreviewPropsAtFrame('unit-grid-proportion', useCurrentFrame())} /></IsolatedCard>;}, ...Card30.meta},
  {id: 'Talkcraft-chip-grid-single-select', name: "五选一反黑", slug: 'chip-grid-single-select', component: function CardDemo31() {return <IsolatedCard><Card31.default {...originalPreviewPropsAtFrame('chip-grid-single-select', useCurrentFrame())} /></IsolatedCard>;}, ...Card31.meta},
  {id: 'Talkcraft-info-term-card', name: "名词解释悬浮卡", slug: 'info-term-card', component: function CardDemo32() {return <IsolatedCard><Card32.default {...originalPreviewPropsAtFrame('info-term-card', useCurrentFrame())} /></IsolatedCard>;}, ...Card32.meta},
  {id: 'Talkcraft-map-route-pin', name: "地图路线图钉", slug: 'map-route-pin', component: function CardDemo33() {return <IsolatedCard><Card33.default {...originalPreviewPropsAtFrame('map-route-pin', useCurrentFrame())} /></IsolatedCard>;}, ...Card33.meta},
  {id: 'Talkcraft-numbered-step-stack', name: "编号步骤堆入", slug: 'numbered-step-stack', component: function CardDemo34() {return <IsolatedCard><Card34.default {...originalPreviewPropsAtFrame('numbered-step-stack', useCurrentFrame())} /></IsolatedCard>;}, ...Card34.meta},
  {id: 'Talkcraft-step-timeline-vertical', name: "竖向步骤线", slug: 'step-timeline-vertical', component: function CardDemo35() {return <IsolatedCard><Card35.default {...originalPreviewPropsAtFrame('step-timeline-vertical', useCurrentFrame())} /></IsolatedCard>;}, ...Card35.meta},
  {id: 'Talkcraft-ui-prop-theater', name: "界面道具剧场", slug: 'ui-prop-theater', component: function CardDemo36() {return <IsolatedCard><Card36.default {...originalPreviewPropsAtFrame('ui-prop-theater', useCurrentFrame())} /></IsolatedCard>;}, ...Card36.meta},
  {id: 'Talkcraft-source-converge', name: "多源汇聚", slug: 'source-converge', component: function CardDemo37() {return <IsolatedCard><Card37.default {...originalPreviewPropsAtFrame('source-converge', useCurrentFrame())} /></IsolatedCard>;}, ...Card37.meta},
  {id: 'Talkcraft-bed-echo-blur', name: "同源模糊底床", slug: 'bed-echo-blur', component: function CardDemo38() {return <IsolatedCard><Card38.default {...originalPreviewPropsAtFrame('bed-echo-blur', useCurrentFrame())} /></IsolatedCard>;}, ...Card38.meta},
  {id: 'Talkcraft-chat-message-flow', name: "聊天记录自演", slug: 'chat-message-flow', component: function CardDemo39() {return <IsolatedCard><Card39.default {...originalPreviewPropsAtFrame('chat-message-flow', useCurrentFrame())} /></IsolatedCard>;}, ...Card39.meta},
  {id: 'Talkcraft-cursor-actor-demo', name: "光标演员演示", slug: 'cursor-actor-demo', component: function CardDemo40() {return <IsolatedCard><Card40.default {...originalPreviewPropsAtFrame('cursor-actor-demo', useCurrentFrame())} /></IsolatedCard>;}, ...Card40.meta},
  {id: 'Talkcraft-evidence-scroll-tour', name: "证据长页慢滚", slug: 'evidence-scroll-tour', component: function CardDemo41() {return <IsolatedCard><Card41.default {...originalPreviewPropsAtFrame('evidence-scroll-tour', useCurrentFrame())} /></IsolatedCard>;}, ...Card41.meta},
  {id: 'Talkcraft-media-pop-in', name: "素材弹入堆叠", slug: 'media-pop-in', component: function CardDemo42() {return <IsolatedCard><Card42.default {...originalPreviewPropsAtFrame('media-pop-in', useCurrentFrame())} /></IsolatedCard>;}, ...Card42.meta},
  {id: 'Talkcraft-news-card-desk', name: "新闻卡片划重点", slug: 'news-card-desk', component: function CardDemo43() {return <IsolatedCard><Card43.default {...originalPreviewPropsAtFrame('news-card-desk', useCurrentFrame())} /></IsolatedCard>;}, ...Card43.meta},
  {id: 'Talkcraft-split-compare-slider', name: "对比双分屏（滑动揭示）", slug: 'split-compare-slider', component: function CardDemo44() {return <IsolatedCard><Card44.default {...originalPreviewPropsAtFrame('split-compare-slider', useCurrentFrame())} /></IsolatedCard>;}, ...Card44.meta},
  {id: 'Talkcraft-still-layout-relay', name: "多图排版 + 焦点接力", slug: 'still-layout-relay', component: function CardDemo45() {return <IsolatedCard><Card45.default {...originalPreviewPropsAtFrame('still-layout-relay', useCurrentFrame())} /></IsolatedCard>;}, ...Card45.meta},
  {id: 'Talkcraft-ui-flow-theater', name: "界面流程剧场", slug: 'ui-flow-theater', component: function CardDemo46() {return <IsolatedCard><Card46.default {...originalPreviewPropsAtFrame('ui-flow-theater', useCurrentFrame())} /></IsolatedCard>;}, ...Card46.meta},
  {id: 'Talkcraft-chat-gpt', name: "ChatGPT 对话框", slug: 'chat-gpt', component: function CardDemo47() {return <IsolatedCard><Card47.default {...originalPreviewPropsAtFrame('chat-gpt', useCurrentFrame())} /></IsolatedCard>;}, ...Card47.meta},
  {id: 'Talkcraft-claude-code', name: "编码智能体终端", slug: 'claude-code', component: function CardDemo48() {return <IsolatedCard><Card48.default {...originalPreviewPropsAtFrame('claude-code', useCurrentFrame())} /></IsolatedCard>;}, ...Card48.meta},
  {id: 'Talkcraft-doc-park-left-pill-deal', name: "文档驻留发牌", slug: 'doc-park-left-pill-deal', component: function CardDemo49() {return <IsolatedCard><Card49.default {...originalPreviewPropsAtFrame('doc-park-left-pill-deal', useCurrentFrame())} /></IsolatedCard>;}, ...Card49.meta},
  {id: 'Talkcraft-filmstrip-conveyor', name: "传送带列举 + 减速停靠", slug: 'filmstrip-conveyor', component: function CardDemo50() {return <IsolatedCard><Card50.default {...originalPreviewPropsAtFrame('filmstrip-conveyor', useCurrentFrame())} /></IsolatedCard>;}, ...Card50.meta},
  {id: 'Talkcraft-gallery-wall-dolly', name: "照片墙推轨", slug: 'gallery-wall-dolly', component: function CardDemo51() {return <IsolatedCard><Card51.default {...originalPreviewPropsAtFrame('gallery-wall-dolly', useCurrentFrame())} /></IsolatedCard>;}, ...Card51.meta},
  {id: 'Talkcraft-glass-code-walk', name: "玻璃代码走读", slug: 'glass-code-walk', component: function CardDemo52() {return <IsolatedCard><Card52.default {...originalPreviewPropsAtFrame('glass-code-walk', useCurrentFrame())} /></IsolatedCard>;}, ...Card52.meta},
  {id: 'Talkcraft-gooey-morph', name: "图块拼入", slug: 'gooey-morph', component: function CardDemo53() {return <IsolatedCard><Card53.default {...originalPreviewPropsAtFrame('gooey-morph', useCurrentFrame())} /></IsolatedCard>;}, ...Card53.meta},
  {id: 'Talkcraft-grid-to-hero', name: "网格收成主角", slug: 'grid-to-hero', component: function CardDemo54() {return <IsolatedCard><Card54.default {...originalPreviewPropsAtFrame('grid-to-hero', useCurrentFrame())} /></IsolatedCard>;}, ...Card54.meta},
  {id: 'Talkcraft-info-card-assemble', name: "信息卡逐字段自建", slug: 'info-card-assemble', component: function CardDemo55() {return <IsolatedCard><Card55.default {...originalPreviewPropsAtFrame('info-card-assemble', useCurrentFrame())} /></IsolatedCard>;}, ...Card55.meta},
  {id: 'Talkcraft-logo-enter', name: "Logo 登场", slug: 'logo-enter', component: function CardDemo56() {return <IsolatedCard><Card56.default {...originalPreviewPropsAtFrame('logo-enter', useCurrentFrame())} /></IsolatedCard>;}, ...Card56.meta},
  {id: 'Talkcraft-motion-blur-slam-in', name: "模糊甩入急停", slug: 'motion-blur-slam-in', component: function CardDemo57() {return <IsolatedCard><Card57.default {...originalPreviewPropsAtFrame('motion-blur-slam-in', useCurrentFrame())} /></IsolatedCard>;}, ...Card57.meta},
  {id: 'Talkcraft-pencil-sketch-draw', name: "铅笔手绘揭示", slug: 'pencil-sketch-draw', component: function CardDemo58() {return <IsolatedCard><Card58.default {...originalPreviewPropsAtFrame('pencil-sketch-draw', useCurrentFrame())} /></IsolatedCard>;}, ...Card58.meta},
  {id: 'Talkcraft-rack-focus-pair', name: "焦点接力", slug: 'rack-focus-pair', component: function CardDemo59() {return <IsolatedCard><Card59.default {...originalPreviewPropsAtFrame('rack-focus-pair', useCurrentFrame())} /></IsolatedCard>;}, ...Card59.meta},
  {id: 'Talkcraft-split-60-40-story', name: "60/40 主从分屏", slug: 'split-60-40-story', component: function CardDemo60() {return <IsolatedCard><Card60.default {...originalPreviewPropsAtFrame('split-60-40-story', useCurrentFrame())} /></IsolatedCard>;}, ...Card60.meta},
  {id: 'Talkcraft-stack-fan-out', name: "卡堆扇形展开", slug: 'stack-fan-out', component: function CardDemo61() {return <IsolatedCard><Card61.default {...originalPreviewPropsAtFrame('stack-fan-out', useCurrentFrame())} /></IsolatedCard>;}, ...Card61.meta},
  {id: 'Talkcraft-terminal-typing-log', name: "终端逐行推进", slug: 'terminal-typing-log', component: function CardDemo62() {return <IsolatedCard><Card62.default {...originalPreviewPropsAtFrame('terminal-typing-log', useCurrentFrame())} /></IsolatedCard>;}, ...Card62.meta},
  {id: 'Talkcraft-timeline-photo-strip', name: "时间线照片带", slug: 'timeline-photo-strip', component: function CardDemo63() {return <IsolatedCard><Card63.default {...originalPreviewPropsAtFrame('timeline-photo-strip', useCurrentFrame())} /></IsolatedCard>;}, ...Card63.meta},
  {id: 'Talkcraft-word-relay-filmstrip', name: "动词接力胶片", slug: 'word-relay-filmstrip', component: function CardDemo64() {return <IsolatedCard><Card64.default {...originalPreviewPropsAtFrame('word-relay-filmstrip', useCurrentFrame())} /></IsolatedCard>;}, ...Card64.meta},
  {id: 'Talkcraft-slow-pull-reveal', name: "缓拉全貌", slug: 'slow-pull-reveal', component: function CardDemo65() {return <IsolatedCard><Card65.default {...originalPreviewPropsAtFrame('slow-pull-reveal', useCurrentFrame())} /></IsolatedCard>;}, ...Card65.meta},
  {id: 'Talkcraft-slow-push-in', name: "缓推特写", slug: 'slow-push-in', component: function CardDemo66() {return <IsolatedCard><Card66.default {...originalPreviewPropsAtFrame('slow-push-in', useCurrentFrame())} /></IsolatedCard>;}, ...Card66.meta},
  {id: 'Talkcraft-cursor-locked-zoom', name: "光标锁定跟拍", slug: 'cursor-locked-zoom', component: function CardDemo67() {return <IsolatedCard><Card67.default {...originalPreviewPropsAtFrame('cursor-locked-zoom', useCurrentFrame())} /></IsolatedCard>;}, ...Card67.meta},
  {id: 'Talkcraft-orbit-drift', name: "环绕微漂", slug: 'orbit-drift', component: function CardDemo68() {return <IsolatedCard><Card68.default {...originalPreviewPropsAtFrame('orbit-drift', useCurrentFrame())} /></IsolatedCard>;}, ...Card68.meta},
  {id: 'Talkcraft-pip-zoom-box', name: "画中画放大", slug: 'pip-zoom-box', component: function CardDemo69() {return <IsolatedCard><Card69.default {...originalPreviewPropsAtFrame('pip-zoom-box', useCurrentFrame())} /></IsolatedCard>;}, ...Card69.meta},
  {id: 'Talkcraft-stage-keyframe-tour', name: "长页兴趣点巡游", slug: 'stage-keyframe-tour', component: function CardDemo70() {return <IsolatedCard><Card70.default {...originalPreviewPropsAtFrame('stage-keyframe-tour', useCurrentFrame())} /></IsolatedCard>;}, ...Card70.meta},
  {id: 'Talkcraft-sway-parallax', name: "左右摇移", slug: 'sway-parallax', component: function CardDemo71() {return <IsolatedCard><Card71.default {...originalPreviewPropsAtFrame('sway-parallax', useCurrentFrame())} /></IsolatedCard>;}, ...Card71.meta},
  {id: 'Talkcraft-tilt-3d-page', name: "3D 立面展示", slug: 'tilt-3d-page', component: function CardDemo72() {return <IsolatedCard><Card72.default {...originalPreviewPropsAtFrame('tilt-3d-page', useCurrentFrame())} /></IsolatedCard>;}, ...Card72.meta},
  {id: 'Talkcraft-black-slam-transition', name: "黑震切转场", slug: 'black-slam-transition', component: function CardDemo73() {return <IsolatedCard><Card73.default {...originalPreviewPropsAtFrame('black-slam-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card73.meta},
  {id: 'Talkcraft-chapter-title-card', name: "章节标题卡", slug: 'chapter-title-card', component: function CardDemo74() {return <IsolatedCard><Card74.default {...originalPreviewPropsAtFrame('chapter-title-card', useCurrentFrame())} /></IsolatedCard>;}, ...Card74.meta},
  {id: 'Talkcraft-color-slam-beat-card', name: "纯色硬切节拍卡", slug: 'color-slam-beat-card', component: function CardDemo75() {return <IsolatedCard><Card75.default {...originalPreviewPropsAtFrame('color-slam-beat-card', useCurrentFrame())} /></IsolatedCard>;}, ...Card75.meta},
  {id: 'Talkcraft-overexpose-flip-transition', name: "过曝翻页转场", slug: 'overexpose-flip-transition', component: function CardDemo76() {return <IsolatedCard><Card76.default {...originalPreviewPropsAtFrame('overexpose-flip-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card76.meta},
  {id: 'Talkcraft-particle-weld-transition', name: "粒子溶接转场", slug: 'particle-weld-transition', component: function CardDemo77() {return <IsolatedCard><Card77.default {...originalPreviewPropsAtFrame('particle-weld-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card77.meta},
  {id: 'Talkcraft-pullback-cool-transition', name: "后拉冷却转场", slug: 'pullback-cool-transition', component: function CardDemo78() {return <IsolatedCard><Card78.default {...originalPreviewPropsAtFrame('pullback-cool-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card78.meta},
  {id: 'Talkcraft-push-through-transition', name: "推穿转场", slug: 'push-through-transition', component: function CardDemo79() {return <IsolatedCard><Card79.default {...originalPreviewPropsAtFrame('push-through-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card79.meta},
  {id: 'Talkcraft-shape-wipe-transition', name: "色块扫屏转场", slug: 'shape-wipe-transition', component: function CardDemo80() {return <IsolatedCard><Card80.default {...originalPreviewPropsAtFrame('shape-wipe-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card80.meta},
  {id: 'Talkcraft-whip-pan-transition', name: "横甩转场", slug: 'whip-pan-transition', component: function CardDemo81() {return <IsolatedCard><Card81.default {...originalPreviewPropsAtFrame('whip-pan-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card81.meta},
  {id: 'Talkcraft-caret-wipe-transition', name: "光标擦除转场", slug: 'caret-wipe-transition', component: function CardDemo82() {return <IsolatedCard><Card82.default {...originalPreviewPropsAtFrame('caret-wipe-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card82.meta},
  {id: 'Talkcraft-chapter-progress-list', name: "章节进度", slug: 'chapter-progress-list', component: function CardDemo83() {return <IsolatedCard><Card83.default {...originalPreviewPropsAtFrame('chapter-progress-list', useCurrentFrame())} /></IsolatedCard>;}, ...Card83.meta},
  {id: 'Talkcraft-line-carry-transition', name: "线条接力转场", slug: 'line-carry-transition', component: function CardDemo84() {return <IsolatedCard><Card84.default {...originalPreviewPropsAtFrame('line-carry-transition', useCurrentFrame())} /></IsolatedCard>;}, ...Card84.meta},
  {id: 'Talkcraft-long-take-world', name: "长镜头世界画布", slug: 'long-take-world', component: function CardDemo85() {return <IsolatedCard><Card85.default {...originalPreviewPropsAtFrame('long-take-world', useCurrentFrame())} /></IsolatedCard>;}, ...Card85.meta},
  {id: 'Talkcraft-impact-open-title', name: "冲击开场", slug: 'impact-open-title', component: function CardDemo86() {return <IsolatedCard><Card86.default {...originalPreviewPropsAtFrame('impact-open-title', useCurrentFrame())} /></IsolatedCard>;}, ...Card86.meta},
  {id: 'Talkcraft-keyword-pop-highlight', name: "关键词弹出强调", slug: 'keyword-pop-highlight', component: function CardDemo87() {return <IsolatedCard><Card87.default {...originalPreviewPropsAtFrame('keyword-pop-highlight', useCurrentFrame())} /></IsolatedCard>;}, ...Card87.meta},
  {id: 'Talkcraft-slab-punch-title', name: "重点放大", slug: 'slab-punch-title', component: function CardDemo88() {return <IsolatedCard><Card88.default {...originalPreviewPropsAtFrame('slab-punch-title', useCurrentFrame())} /></IsolatedCard>;}, ...Card88.meta},
  {id: 'Talkcraft-title-demote-to-label', name: "标题降格成标签", slug: 'title-demote-to-label', component: function CardDemo89() {return <IsolatedCard><Card89.default {...originalPreviewPropsAtFrame('title-demote-to-label', useCurrentFrame())} /></IsolatedCard>;}, ...Card89.meta},
  {id: 'Talkcraft-type-contrast-emphasis', name: "字体对比重音", slug: 'type-contrast-emphasis', component: function CardDemo90() {return <IsolatedCard><Card90.default {...originalPreviewPropsAtFrame('type-contrast-emphasis', useCurrentFrame())} /></IsolatedCard>;}, ...Card90.meta},
  {id: 'Talkcraft-word-slot-cycle', name: "词槽轮换", slug: 'word-slot-cycle', component: function CardDemo91() {return <IsolatedCard><Card91.default {...originalPreviewPropsAtFrame('word-slot-cycle', useCurrentFrame())} /></IsolatedCard>;}, ...Card91.meta},
  {id: 'Talkcraft-alt-block-lines', name: "双色块对句", slug: 'alt-block-lines', component: function CardDemo92() {return <IsolatedCard><Card92.default {...originalPreviewPropsAtFrame('alt-block-lines', useCurrentFrame())} /></IsolatedCard>;}, ...Card92.meta},
  {id: 'Talkcraft-count-badge-title', name: "数字重音标题", slug: 'count-badge-title', component: function CardDemo93() {return <IsolatedCard><Card93.default {...originalPreviewPropsAtFrame('count-badge-title', useCurrentFrame())} /></IsolatedCard>;}, ...Card93.meta},
  {id: 'Talkcraft-error-retype', name: "打字改口", slug: 'error-retype', component: function CardDemo94() {return <IsolatedCard><Card94.default {...originalPreviewPropsAtFrame('error-retype', useCurrentFrame())} /></IsolatedCard>;}, ...Card94.meta},
  {id: 'Talkcraft-lead-word-zoom-assemble', name: "首词占满补句", slug: 'lead-word-zoom-assemble', component: function CardDemo95() {return <IsolatedCard><Card95.default {...originalPreviewPropsAtFrame('lead-word-zoom-assemble', useCurrentFrame())} /></IsolatedCard>;}, ...Card95.meta},
  {id: 'Talkcraft-line-by-line-slide', name: "逐行滑入", slug: 'line-by-line-slide', component: function CardDemo96() {return <IsolatedCard><Card96.default {...originalPreviewPropsAtFrame('line-by-line-slide', useCurrentFrame())} /></IsolatedCard>;}, ...Card96.meta},
  {id: 'Talkcraft-outline-box-title', name: "描边框标题", slug: 'outline-box-title', component: function CardDemo97() {return <IsolatedCard><Card97.default {...originalPreviewPropsAtFrame('outline-box-title', useCurrentFrame())} /></IsolatedCard>;}, ...Card97.meta},
  {id: 'Talkcraft-per-character-rise', name: "逐字升起", slug: 'per-character-rise', component: function CardDemo98() {return <IsolatedCard><Card98.default {...originalPreviewPropsAtFrame('per-character-rise', useCurrentFrame())} /></IsolatedCard>;}, ...Card98.meta},
  {id: 'Talkcraft-quote-bracket-pull', name: "引号夹句", slug: 'quote-bracket-pull', component: function CardDemo99() {return <IsolatedCard><Card99.default {...originalPreviewPropsAtFrame('quote-bracket-pull', useCurrentFrame())} /></IsolatedCard>;}, ...Card99.meta},
  {id: 'Talkcraft-quote-card', name: "金句大字卡", slug: 'quote-card', component: function CardDemo100() {return <IsolatedCard><Card100.default {...originalPreviewPropsAtFrame('quote-card', useCurrentFrame())} /></IsolatedCard>;}, ...Card100.meta},
  {id: 'Talkcraft-soft-blur-in', name: "柔焦淡入", slug: 'soft-blur-in', component: function CardDemo101() {return <IsolatedCard><Card101.default {...originalPreviewPropsAtFrame('soft-blur-in', useCurrentFrame())} /></IsolatedCard>;}, ...Card101.meta},
  {id: 'Talkcraft-speed-slab-title', name: "速度块标题", slug: 'speed-slab-title', component: function CardDemo102() {return <IsolatedCard><Card102.default {...originalPreviewPropsAtFrame('speed-slab-title', useCurrentFrame())} /></IsolatedCard>;}, ...Card102.meta},
  {id: 'Talkcraft-tracking-in', name: "字距收拢", slug: 'tracking-in', component: function CardDemo103() {return <IsolatedCard><Card103.default {...originalPreviewPropsAtFrame('tracking-in', useCurrentFrame())} /></IsolatedCard>;}, ...Card103.meta},
  {id: 'Talkcraft-typewriter-reveal', name: "打字机档案戳", slug: 'typewriter-reveal', component: function CardDemo104() {return <IsolatedCard><Card104.default {...originalPreviewPropsAtFrame('typewriter-reveal', useCurrentFrame())} /></IsolatedCard>;}, ...Card104.meta},
  {id: 'Talkcraft-countdown-arc-scatter', name: "数字弧落标题", slug: 'countdown-arc-scatter', component: function CardDemo105() {return <IsolatedCard><Card105.default {...originalPreviewPropsAtFrame('countdown-arc-scatter', useCurrentFrame())} /></IsolatedCard>;}, ...Card105.meta},
  {id: 'Talkcraft-flying-words', name: "关键词隧道", slug: 'flying-words', component: function CardDemo106() {return <IsolatedCard><Card106.default {...originalPreviewPropsAtFrame('flying-words', useCurrentFrame())} /></IsolatedCard>;}, ...Card106.meta},
  {id: 'Talkcraft-split-text-stagger', name: "逐字裂升", slug: 'split-text-stagger', component: function CardDemo107() {return <IsolatedCard><Card107.default {...originalPreviewPropsAtFrame('split-text-stagger', useCurrentFrame())} /></IsolatedCard>;}, ...Card107.meta},
];
