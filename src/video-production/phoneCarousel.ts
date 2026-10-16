export type PhoneCarouselSlide = {
  asset_src: string;
  start_frame: number;
  asset_fit: 'contain' | 'cover';
  asset_crop?: {x: number; y: number; width: number; height: number};
};

// Frame is local to this single shot, never the composition's global frame.
export const phoneCarouselAt = (slides: PhoneCarouselSlide[], frame: number,
  durationInFrames: number, transitionFrames = 6) => {
  if (!slides.length) throw new Error('Phone carousel requires registered images');
  let currentIndex = 0;
  for (let i = 1; i < slides.length && slides[i].start_frame <= frame; i++) currentIndex = i;
  const start = slides[currentIndex].start_frame;
  const end = slides[currentIndex + 1]?.start_frame ?? durationInFrames;
  const fadeFrames = Math.min(transitionFrames, end - start);
  const opacity = currentIndex === 0 || fadeFrames === 0 ? 1
    : Math.min(1, (frame - start + 1) / fadeFrames);
  return {currentIndex, previousIndex: opacity < 1 ? currentIndex - 1 : null, opacity};
};
