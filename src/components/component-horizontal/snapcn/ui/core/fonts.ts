// Vendored from snapcndev/snapcn at 4399d249002afae506497cc90ac3f064e189127d. MIT; see licenses/community/snapcn.
/** Offline aliases: only bundled families resolve to their real font face. */
import { LOCAL_FONT_FAMILY, loadInterFont, loadSourceSerifFont } from '../local-font';

export const FONTS: Record<string, string> = Object.fromEntries(
  ['Inter', 'Geist', 'Space Grotesk', 'Outfit', 'Montserrat', 'Instrument Serif']
    .map((name) => [name, name === 'Inter' ? loadInterFont().fontFamily : LOCAL_FONT_FAMILY]),
);
FONTS['Source Serif 4'] = loadSourceSerifFont().fontFamily;
export const DEFAULT_FONT = 'Default';
export const FONT_NAMES = [DEFAULT_FONT, ...Object.keys(FONTS)];
export const resolveFont = (name?: string): string | undefined =>
  !name || name === DEFAULT_FONT ? undefined : (FONTS[name] ?? name);
