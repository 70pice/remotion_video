import {createTikTokStyleCaptions, type Caption} from '@remotion/captions';

// Upstream's automatic breaks expect space-prefixed words. Chinese TTS tokens
// have no spaces, so supply explicit breaks before using the official grouping.
export const captionPages = (captions: Caption[]) => {
  let characters = 0;
  let startMs = 0;
  const prepared = captions.map((caption, index) => {
    if (characters === 0) startMs = caption.startMs;
    characters += caption.text.length;
    const next = captions[index + 1];
    const pageBreakAfter = !next || characters + next.text.length > 16 ||
      next.endMs - startMs > 1700 || next.startMs - caption.endMs >= 450;
    if (pageBreakAfter) characters = 0;
    return {...caption, pageBreakAfter};
  });
  return createTikTokStyleCaptions({captions: prepared, combineTokensWithinMilliseconds: 1400})
    .pages.map(page => ({...page, durationMs: Math.min(page.durationMs,
      page.tokens[page.tokens.length - 1].toMs + 180 - page.startMs)}));
};
