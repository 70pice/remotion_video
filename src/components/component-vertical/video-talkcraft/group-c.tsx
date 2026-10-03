import {useCurrentFrame} from 'remotion';
import {IsolatedCard} from '../../community/IsolatedCard';
import {originalPreviewPropsAtFrame} from '../../component-horizontal/video-talkcraft/preview-props';
import * as Card0 from './grid-to-hero';
import * as Card1 from './info-card-assemble';
import * as Card2 from './logo-enter';
import * as Card3 from './motion-blur-slam-in';
import * as Card4 from './pencil-sketch-draw';
import * as Card5 from './rack-focus-pair';
import * as Card6 from './split-60-40-story';
import * as Card7 from './stack-fan-out';
import * as Card8 from './terminal-typing-log';
import * as Card9 from './timeline-photo-strip';
import * as Card10 from './word-relay-filmstrip';
import * as Card11 from './slow-pull-reveal';
import * as Card12 from './slow-push-in';
import * as Card13 from './cursor-locked-zoom';
import * as Card14 from './orbit-drift';
import * as Card15 from './pip-zoom-box';
import * as Card16 from './stage-keyframe-tour';
import * as Card17 from './sway-parallax';
import * as Card18 from './tilt-3d-page';
import * as Card19 from './black-slam-transition';
import * as Card20 from './chapter-title-card';
import * as Card21 from './color-slam-beat-card';
import * as Card22 from './overexpose-flip-transition';
import * as Card23 from './particle-weld-transition';
import * as Card24 from './pullback-cool-transition';
import * as Card25 from './push-through-transition';
import * as Card26 from './shape-wipe-transition';

const RenderCard = ({
	Card,
	slug,
}: {
	Card: {default: React.ComponentType<Record<string, unknown>>};
	slug: string,
}) => {
	const {hostSrc: _hostSrc, ...props} = originalPreviewPropsAtFrame(
		slug,
		useCurrentFrame(),
	);
	void _hostSrc;
	return (
		<IsolatedCard>
			<Card.default {...props} />
		</IsolatedCard>
	);
};

export const nativeDemos = [
	{id: 'Talkcraft-grid-to-hero', name: '网格收成主角', slug: 'grid-to-hero', component: function PortraitCard0() { return <RenderCard Card={Card0} slug="grid-to-hero" />; }, ...Card0.meta},
	{id: 'Talkcraft-info-card-assemble', name: '信息卡逐字段自建', slug: 'info-card-assemble', component: function PortraitCard1() { return <RenderCard Card={Card1} slug="info-card-assemble" />; }, ...Card1.meta},
	{id: 'Talkcraft-logo-enter', name: 'Logo 登场', slug: 'logo-enter', component: function PortraitCard2() { return <RenderCard Card={Card2} slug="logo-enter" />; }, ...Card2.meta},
	{id: 'Talkcraft-motion-blur-slam-in', name: '模糊甩入急停', slug: 'motion-blur-slam-in', component: function PortraitCard3() { return <RenderCard Card={Card3} slug="motion-blur-slam-in" />; }, ...Card3.meta},
	{id: 'Talkcraft-pencil-sketch-draw', name: '铅笔手绘揭示', slug: 'pencil-sketch-draw', component: function PortraitCard4() { return <RenderCard Card={Card4} slug="pencil-sketch-draw" />; }, ...Card4.meta},
	{id: 'Talkcraft-rack-focus-pair', name: '焦点接力', slug: 'rack-focus-pair', component: function PortraitCard5() { return <RenderCard Card={Card5} slug="rack-focus-pair" />; }, ...Card5.meta},
	{id: 'Talkcraft-split-60-40-story', name: '60/40 主从分屏', slug: 'split-60-40-story', component: function PortraitCard6() { return <RenderCard Card={Card6} slug="split-60-40-story" />; }, ...Card6.meta},
	{id: 'Talkcraft-stack-fan-out', name: '卡堆扇形展开', slug: 'stack-fan-out', component: function PortraitCard7() { return <RenderCard Card={Card7} slug="stack-fan-out" />; }, ...Card7.meta},
	{id: 'Talkcraft-terminal-typing-log', name: '终端逐行推进', slug: 'terminal-typing-log', component: function PortraitCard8() { return <RenderCard Card={Card8} slug="terminal-typing-log" />; }, ...Card8.meta},
	{id: 'Talkcraft-timeline-photo-strip', name: '时间线照片带', slug: 'timeline-photo-strip', component: function PortraitCard9() { return <RenderCard Card={Card9} slug="timeline-photo-strip" />; }, ...Card9.meta},
	{id: 'Talkcraft-word-relay-filmstrip', name: '动词接力胶片', slug: 'word-relay-filmstrip', component: function PortraitCard10() { return <RenderCard Card={Card10} slug="word-relay-filmstrip" />; }, ...Card10.meta},
	{id: 'Talkcraft-slow-pull-reveal', name: '缓拉全貌', slug: 'slow-pull-reveal', component: function PortraitCard11() { return <RenderCard Card={Card11} slug="slow-pull-reveal" />; }, ...Card11.meta},
	{id: 'Talkcraft-slow-push-in', name: '缓推特写', slug: 'slow-push-in', component: function PortraitCard12() { return <RenderCard Card={Card12} slug="slow-push-in" />; }, ...Card12.meta},
	{id: 'Talkcraft-cursor-locked-zoom', name: '光标锁定跟拍', slug: 'cursor-locked-zoom', component: function PortraitCard13() { return <RenderCard Card={Card13} slug="cursor-locked-zoom" />; }, ...Card13.meta},
	{id: 'Talkcraft-orbit-drift', name: '环绕微漂', slug: 'orbit-drift', component: function PortraitCard14() { return <RenderCard Card={Card14} slug="orbit-drift" />; }, ...Card14.meta},
	{id: 'Talkcraft-pip-zoom-box', name: '画中画放大', slug: 'pip-zoom-box', component: function PortraitCard15() { return <RenderCard Card={Card15} slug="pip-zoom-box" />; }, ...Card15.meta},
	{id: 'Talkcraft-stage-keyframe-tour', name: '长页兴趣点巡游', slug: 'stage-keyframe-tour', component: function PortraitCard16() { return <RenderCard Card={Card16} slug="stage-keyframe-tour" />; }, ...Card16.meta},
	{id: 'Talkcraft-sway-parallax', name: '左右摇移', slug: 'sway-parallax', component: function PortraitCard17() { return <RenderCard Card={Card17} slug="sway-parallax" />; }, ...Card17.meta},
	{id: 'Talkcraft-tilt-3d-page', name: '3D 立面展示', slug: 'tilt-3d-page', component: function PortraitCard18() { return <RenderCard Card={Card18} slug="tilt-3d-page" />; }, ...Card18.meta},
	{id: 'Talkcraft-black-slam-transition', name: '黑震切转场', slug: 'black-slam-transition', component: function PortraitCard19() { return <RenderCard Card={Card19} slug="black-slam-transition" />; }, ...Card19.meta},
	{id: 'Talkcraft-chapter-title-card', name: '章节标题卡', slug: 'chapter-title-card', component: function PortraitCard20() { return <RenderCard Card={Card20} slug="chapter-title-card" />; }, ...Card20.meta},
	{id: 'Talkcraft-color-slam-beat-card', name: '纯色硬切节拍卡', slug: 'color-slam-beat-card', component: function PortraitCard21() { return <RenderCard Card={Card21} slug="color-slam-beat-card" />; }, ...Card21.meta},
	{id: 'Talkcraft-overexpose-flip-transition', name: '过曝翻页转场', slug: 'overexpose-flip-transition', component: function PortraitCard22() { return <RenderCard Card={Card22} slug="overexpose-flip-transition" />; }, ...Card22.meta},
	{id: 'Talkcraft-particle-weld-transition', name: '粒子溶接转场', slug: 'particle-weld-transition', component: function PortraitCard23() { return <RenderCard Card={Card23} slug="particle-weld-transition" />; }, ...Card23.meta},
	{id: 'Talkcraft-pullback-cool-transition', name: '后拉冷却转场', slug: 'pullback-cool-transition', component: function PortraitCard24() { return <RenderCard Card={Card24} slug="pullback-cool-transition" />; }, ...Card24.meta},
	{id: 'Talkcraft-push-through-transition', name: '推穿转场', slug: 'push-through-transition', component: function PortraitCard25() { return <RenderCard Card={Card25} slug="push-through-transition" />; }, ...Card25.meta},
	{id: 'Talkcraft-shape-wipe-transition', name: '色块扫屏转场', slug: 'shape-wipe-transition', component: function PortraitCard26() { return <RenderCard Card={Card26} slug="shape-wipe-transition" />; }, ...Card26.meta},
];
