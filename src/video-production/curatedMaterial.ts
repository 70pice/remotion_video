import type {TimelineShot} from './types';

type CuratedVariant =
  | 'social-clip'
  | 'social-reel'
  | 'bar-chart-race'
  | 'kanban-move'
  | 'device-mockup-3d'
  | 'split-text-chars'
  | 'aurora-bg'
  | 'audio-wave-captions'
  | 'end-card'
  | 'glass-panel'
  | 'path-draw'
  | 'area-chart'
  | 'circular-progress'
  | 'animated-list'
  | 'notification-pop'
  | 'sound-wave'
  | 'text-highlight'
  | 'gallery-grid'
  | 'image-carousel'
  | 'image-zoom-reveal'
  | 'masonry-gallery'
  | 'photo-stack'
  | 'picture-in-picture'
  | 'polaroid-frame'
  | 'clock-wipe'
  | 'iris-transition'
  | 'pixel-candlestick-ohlc'
  | 'racing-chart'
  | 'kpi-counter'
  | 'glass-lower-third'
  | 'pixel-waterfall-cycle'
  | 'pencil-draw'
  | 'eye-reveal'
  | 'news-ticker'
  | 'product-spotlight';

type CuratedDefinition = {
  id: string;
  variant: CuratedVariant;
  title: string;
  kicker: string;
  accent: string;
  secondary?: string;
};

export type NativeMaterialCrop = {x: number; y: number; width: number; height: number};

export type NativeCuratedMaterial = {
  src: string;
  kind: 'image' | 'video';
  fit: 'contain' | 'cover';
  crop?: NativeMaterialCrop;
  startSeconds?: number;
  endSeconds?: number;
};

export type MaterializedCuratedSceneProps = {
  variant: CuratedVariant;
  layout: 'landscape' | 'portrait';
  title: string;
  kicker: string;
  accent: string;
  secondary?: string;
  material?: NativeCuratedMaterial;
};

export const curatedMaterialDefinitions: readonly CuratedDefinition[] = Object.freeze([
  {id: 'RemotionUI-SocialClip', variant: 'social-clip', title: '素材变成短视频钩子', kicker: 'social clip', accent: '#2DD4BF', secondary: 'Hook / caption / end card'},
  {id: 'RemotionUI-BarChartRace', variant: 'bar-chart-race', title: '排行随时间变化', kicker: 'data race', accent: '#38BDF8', secondary: 'ranking change'},
  {id: 'RemotionUI-KanbanMove', variant: 'kanban-move', title: '任务从计划流转到完成', kicker: 'workflow', accent: '#A3E635', secondary: 'agent pipeline'},
  {id: 'RemotionUI-DeviceMockup3D', variant: 'device-mockup-3d', title: '产品界面放进设备框', kicker: 'product demo', accent: '#F97316', secondary: 'screen recording'},
  {id: 'RemotionUI-SplitTextChars', variant: 'split-text-chars', title: 'Key Idea', kicker: 'title layer', accent: '#FACC15', secondary: 'character reveal'},
  {id: 'RemotionUI-AuroraBg', variant: 'aurora-bg', title: '柔性氛围背景', kicker: 'background', accent: '#60A5FA', secondary: 'title safe zone'},
  {id: 'RemotionUI-AudioWaveCaptions', variant: 'audio-wave-captions', title: '声波配字幕', kicker: 'voice visual', accent: '#FB7185', secondary: '旁白重点跟随声波'},
  {id: 'RemotionUI-EndCard', variant: 'end-card', title: '结尾行动卡', kicker: 'closing', accent: '#22C55E', secondary: 'next video'},
  {id: 'RemotionUI-GlassPanel', variant: 'glass-panel', title: '玻璃信息层', kicker: 'overlay', accent: '#38BDF8', secondary: 'source label'},
  {id: 'RemotionUI-PathDraw', variant: 'path-draw', title: '路径逐步画出', kicker: 'motion path', accent: '#F97316', secondary: 'route highlight'},
  {id: 'Rve-AreaChart', variant: 'area-chart', title: '趋势面积图', kicker: 'trend', accent: '#38BDF8', secondary: 'growth over time'},
  {id: 'Rve-CircularProgress', variant: 'circular-progress', title: '完成度环形进度', kicker: 'progress', accent: '#22C55E', secondary: 'delivery ratio'},
  {id: 'Rve-AnimatedList', variant: 'animated-list', title: '步骤依次出现', kicker: 'list', accent: '#FACC15', secondary: 'ordered points'},
  {id: 'Rve-NotificationPop', variant: 'notification-pop', title: '通知卡片弹出', kicker: 'notification', accent: '#FB7185', secondary: 'status update'},
  {id: 'Rve-SoundWave', variant: 'sound-wave', title: '音频波形强调', kicker: 'audio', accent: '#2DD4BF', secondary: 'voice segment'},
  {id: 'Rve-TextHighlight', variant: 'text-highlight', title: 'Highlight This', kicker: 'emphasis', accent: '#F97316', secondary: 'keyword emphasis'},
  {id: 'Rve-GalleryGrid', variant: 'gallery-grid', title: '多素材网格展示', kicker: 'gallery', accent: '#60A5FA', secondary: 'image set'},
  {id: 'Rve-ImageCarousel', variant: 'image-carousel', title: '图片轮播切换', kicker: 'carousel', accent: '#A3E635', secondary: 'sequence'},
  {id: 'Rve-ImageZoomReveal', variant: 'image-zoom-reveal', title: '图片推近揭示细节', kicker: 'zoom reveal', accent: '#38BDF8', secondary: 'focus point'},
  {id: 'Rve-MasonryGallery', variant: 'masonry-gallery', title: '瀑布流素材墙', kicker: 'masonry', accent: '#F43F5E', secondary: 'visual evidence'},
  {id: 'Rve-PhotoStack', variant: 'photo-stack', title: '照片堆叠展开', kicker: 'photo stack', accent: '#FACC15', secondary: 'story moments'},
  {id: 'Rve-PictureInPicture', variant: 'picture-in-picture', title: '主画面加讲解小窗', kicker: 'pip', accent: '#2DD4BF', secondary: 'speaker inset'},
  {id: 'Rve-PolaroidFrame', variant: 'polaroid-frame', title: '拍立得素材卡', kicker: 'polaroid', accent: '#F97316', secondary: 'memory card'},
  {id: 'Rve-ClockWipe', variant: 'clock-wipe', title: '时钟形转场', kicker: 'transition', accent: '#38BDF8', secondary: 'section change'},
  {id: 'Rve-IrisTransition', variant: 'iris-transition', title: '圆形开合转场', kicker: 'transition', accent: '#A3E635', secondary: 'focus reveal'},
  {id: 'RenderComp-PixelCandlestickOhlc', variant: 'pixel-candlestick-ohlc', title: 'A 股走势解读', kicker: 'market chart', accent: '#22C55E', secondary: 'OHLC data'},
  {id: 'RenderComp-RacingChart', variant: 'racing-chart', title: '榜单动态变化', kicker: 'ranking', accent: '#38BDF8', secondary: 'leaderboard'},
  {id: 'RenderComp-KpiCounter', variant: 'kpi-counter', title: '关键指标放大', kicker: 'kpi', accent: '#FACC15', secondary: 'verified number'},
  {id: 'RenderComp-GlassLowerThird', variant: 'glass-lower-third', title: '人物与来源说明', kicker: 'lower third', accent: '#2DD4BF', secondary: 'source / role'},
  {id: 'RenderComp-SocialReel', variant: 'social-reel', title: '竖屏短视频框架', kicker: 'reel', accent: '#FB7185', secondary: 'caption ready'},
  {id: 'RenderComp-PixelWaterfallCycle', variant: 'pixel-waterfall-cycle', title: '像素瀑布循环', kicker: 'texture', accent: '#60A5FA', secondary: 'style beat'},
  {id: 'RenderComp-PencilDraw', variant: 'pencil-draw', title: '手绘路径生成', kicker: 'sketch', accent: '#F97316', secondary: 'annotation'},
  {id: 'RenderComp-EyeReveal', variant: 'eye-reveal', title: '视线打开揭示', kicker: 'reveal', accent: '#A3E635', secondary: 'attention shift'},
  {id: 'RenderComp-NewsTicker', variant: 'news-ticker', title: '新闻跑马灯', kicker: 'ticker', accent: '#38BDF8', secondary: 'live updates'},
  {id: 'RenderComp-ProductSpotlight', variant: 'product-spotlight', title: '产品卖点聚焦', kicker: 'spotlight', accent: '#FACC15', secondary: 'feature card'},
]);

export const materializedCommunityComponentIds = Object.freeze(
  curatedMaterialDefinitions.map((definition) => definition.id),
);

const definitionsById = new Map(curatedMaterialDefinitions.map((definition) => [definition.id, definition]));

export const materializedCommunityComponentIdSet = new Set(materializedCommunityComponentIds);

const isCrop = (value: unknown): value is NativeMaterialCrop => {
  if (!value || typeof value !== 'object') return false;
  const crop = value as Record<string, unknown>;
  return ['x', 'y', 'width', 'height'].every((field) => typeof crop[field] === 'number');
};

const suppliedSecondary = (shot: TimelineShot): string | undefined => {
  if (shot.body.trim()) return shot.body;
  const props = shot.props as Record<string, unknown>;
  const metric = props.metric;
  if (metric && typeof metric === 'object') {
    const value = metric as Record<string, unknown>;
    if (typeof value.detail === 'string' && value.detail.trim()) return value.detail;
    if (typeof value.value === 'string' && value.value.trim()) return value.value;
  }
  if (Array.isArray(props.items)) {
    const items = props.items.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
    if (items.length) return items.slice(0, 2).join(' / ');
  }
  if (shot.source_label.trim()) return shot.source_label;
  return undefined;
};

const materialForShot = (shot: TimelineShot): NativeCuratedMaterial | undefined => {
  if (!shot.asset_src) return undefined;
  const props = shot.props as Record<string, unknown>;
  const startSeconds = typeof props.start_seconds === 'number' ? props.start_seconds : undefined;
  const endSeconds = typeof props.end_seconds === 'number' ? props.end_seconds : undefined;
  return {
    src: shot.asset_src,
    kind: /\.mp4$/i.test(shot.asset_src) ? 'video' : 'image',
    fit: props.asset_fit === 'cover' ? 'cover' : 'contain',
    ...(isCrop(props.asset_crop) ? {crop: props.asset_crop} : {}),
    ...(startSeconds === undefined ? {} : {startSeconds}),
    ...(endSeconds === undefined ? {} : {endSeconds}),
  };
};

export const curatedScenePropsForShot = (
  shot: TimelineShot,
  portrait: boolean,
): MaterializedCuratedSceneProps => {
  const definition = definitionsById.get(shot.component_id);
  if (!definition) {
    throw new Error(`Component is not a materialized curated preset: ${shot.component_id}`);
  }
  return {
    variant: definition.variant,
    layout: portrait ? 'portrait' : 'landscape',
    title: shot.title || definition.title,
    kicker: shot.source_label || definition.kicker,
    accent: shot.accent_color || definition.accent,
    secondary: suppliedSecondary(shot) || definition.secondary,
    material: materialForShot(shot),
  };
};
