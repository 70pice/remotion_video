import {staticFile} from 'remotion';

// The author injects these assets into the HTML demonstrations. This file only
// supplies preview props; template/cards source and animation timing stay intact.
// Evidence: demos/_lib/media/ATTRIBUTION.md and demos/<slug>/index.html at
// 4cd673df4b7a6a35784a0881df223721789c5e23.
const image = (id: number) =>
  staticFile(`community/video-talkcraft/media/p-${id}.jpg`);
const images = (...ids: number[]) => ids.map(image);
const hostSrc = staticFile('community/video-talkcraft/dh-host.webm');

// Each of these original cards actually consumes hostSrc. The author's
// demo-shell.js injects the same AI-generated alpha video into its HTML hosts.
const hostCards = [
  'alt-block-lines',
  'bar-chart-growth',
  'behind-text-title',
  'chapter-progress-list',
  'chapter-title-card',
  'chat-gpt',
  'chat-message-flow',
  'chevron-lower-third',
  'claude-code',
  'color-slam-beat-card',
  'converging-arrows',
  'corner-bracket-frame',
  'count-badge-title',
  'cursor-actor-demo',
  'danmu-bubble-praise',
  'evidence-scroll-tour',
  'focus-dim-spotlight',
  'gooey-morph',
  'hand-drawn-ellipse',
  'host-card-glass-board',
  'host-shrink-to-chip',
  'impact-open-title',
  'info-term-card',
  'ink-underline',
  'keyword-pop-highlight',
  'line-chart-story-draw',
  'lower-third-nameplate',
  'map-route-pin',
  'media-pop-in',
  'metric-with-sparkline',
  'motion-blur-slam-in',
  'number-counter',
  'number-slab-pop',
  'numbered-step-stack',
  'outline-box-title',
  'parallel-items-with-host',
  'pip-zoom-box',
  'quote-bracket-pull',
  'quote-card',
  'quote-hold-arrow',
  'shape-wipe-transition',
  'slab-punch-title',
  'speed-slab-title',
  'split-60-40-story',
  'step-timeline-vertical',
  'strike-and-replace',
  'subscribe-cta',
  'terminal-typing-log',
  'type-contrast-emphasis',
  'typewriter-reveal',
  'ui-prop-theater',
] as const;

export const originalPreviewProps: Record<string, Record<string, unknown>> =
  Object.fromEntries(hostCards.map((slug) => [slug, {hostSrc}]));

// Only the original demonstration assets are used, with the original order.
Object.assign(originalPreviewProps, {
  'bed-echo-blur': {
    src: staticFile('community/video-talkcraft/media/v-ocean.webm'),
  },
  'split-60-40-story': {
    hostSrc,
    src: staticFile('community/video-talkcraft/media/v-typing.webm'),
  },
  'rack-focus-pair': {srcs: images(367, 24)},
  'split-compare-slider': {
    srcBefore: image(1043),
    srcAfter: image(1043),
  },
  'filmstrip-conveyor': {srcs: images(1015, 1036, 1039, 1050, 1057, 1018)},
  'grid-to-hero': {srcs: images(1018, 1050, 1059, 1036)},
  'gallery-wall-dolly': {srcs: images(1015, 1036, 1039)},
  'timeline-photo-strip': {srcs: images(0, 180, 60, 1059)},
  'parallel-items-with-host': {hostSrc, srcs: images(63, 24, 250)},
  'stack-fan-out': {srcs: images(1015, 1036, 1050, 1057, 1018)},
  'still-layout-relay': {srcs: images(250, 355, 319)},
  'word-relay-filmstrip': {srcs: images(63, 24, 250, 366, 160)},
  'info-card-assemble': {src: image(24)},
  'line-carry-transition': {srcB: image(180)},
  'pencil-sketch-draw': {
    handSrc: staticFile('community/video-talkcraft/hand-pencil.png'),
  },
});

// The HTML tours change their pictures per layout. Their unchanged TSX cards
// expose only one srcs array, so the preview wrapper supplies the current array.
const parallelTourImages = [
  images(63, 24, 250),
  images(1018, 1053, 1067),
  images(366, 180, 160),
  images(823, 0, 816),
  images(1015, 866, 1050),
  images(1036, 845, 177),
  images(1067, 392, 274),
];

export const originalPreviewPropsAtFrame = (
  slug: string,
  frame: number,
): Record<string, unknown> => {
  const base = originalPreviewProps[slug] ?? {};
  if (slug === 'parallel-items-with-host') {
    // Original CONFIG.per = 3.1 seconds; original meta.fps = 30.
    const index = Math.min(6, Math.max(0, Math.floor(frame / 30 / 3.1)));
    return {...base, srcs: parallelTourImages[index]};
  }
  if (slug === 'still-layout-relay' && frame / 30 >= 8.08) {
    // Original perOf('hero-duo') = 7.6 + 0.04 * 2 + 0.4 seconds.
    return {...base, srcs: images(1027, 349, 823)};
  }
  return base;
};
