import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';

/** Families without bundled font assets still use this explicit system fallback. */
export const LOCAL_FONT_FAMILY = '"Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI", sans-serif';
export const loadFont = (style?: unknown, options?: unknown) => {
  // Compatibility adapter for families whose original files have not been imported.
  void style;
  void options;
  return {fontFamily: LOCAL_FONT_FAMILY, waitUntilDone: () => Promise.resolve()};
};

type FontOptions = {weights?: readonly string[]; subsets?: readonly string[]};
const fontLoads = new Map<string, Promise<void>>();

const loadFace = (family: string, prefix: string, weight: string): Promise<void> => {
  if (typeof document === 'undefined' || typeof FontFace === 'undefined') {
    return Promise.resolve();
  }
  const key = `${family}-${weight}`;
  const existing = fontLoads.get(key);
  if (existing) return existing;

  const handle = delayRender(`Loading local font ${family} ${weight}`);
  const face = new FontFace(
    family,
    `url('${staticFile(`community/fonts/${prefix}-latin-${weight}-normal.woff2`)}') format('woff2')`,
    {style: 'normal', weight},
  );
  const ready = face.load().then((loaded) => {
    // TypeScript's DOM FontFaceSet omits the browser-supported add() member.
    const fonts = document.fonts as FontFaceSet & {add(font: FontFace): FontFaceSet};
    fonts.add(loaded);
    continueRender(handle);
  });
  // A missing font must fail the render instead of silently producing fallback typography.
  void ready.catch((error: unknown) => cancelRender(error));
  fontLoads.set(key, ready);
  return ready;
};

const localLoader = (family: string, prefix: string, weights: readonly string[]) =>
  (style = 'normal', options: FontOptions = {}) => {
    if (style !== 'normal') throw new Error(`Only normal ${family} is bundled.`);
    const selected = options.weights ?? weights;
    for (const weight of selected) {
      if (!weights.includes(weight)) throw new Error(`${family} weight ${weight} is not bundled.`);
    }
    const ready = Promise.all(selected.map((weight) => loadFace(family, prefix, weight))).then(() => undefined);
    // The render is already blocked by each face's delayRender handle.
    void ready.catch(() => undefined);
    // A family ending in a number (Source Serif 4) needs quotes in CSS syntax.
    return {fontFamily: `"${family}"`, waitUntilDone: () => ready};
  };

// Fontsource 5.3.0, unchanged Latin WOFF2 files. See licenses/community/snapcn/fonts.
export const loadInterFont = localLoader('Inter', 'inter', ['400', '500', '600', '700']);
export const loadSourceSerifFont = localLoader('Source Serif 4', 'source-serif-4', ['400', '600']);
