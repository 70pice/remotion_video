// Vendored from snapcndev/snapcn at 4399d249002afae506497cc90ac3f064e189127d. MIT; see licenses/community/snapcn.
// Only the style context is used by these scenes; no Tailwind control runtime.
import {mixOklch, type SnapCnTheme} from "./core";

export interface InputStyleContext {
  idleBorder: string;
  hoverBorder: string;
  activeBorder: string;
  invalidBorder: string;
  ring: string;
  invalidRing: string;
  background: string;
  hoverBackground: string;
  foreground: string;
  mutedForeground: string;
}

export function inputStyleContext(theme: SnapCnTheme): InputStyleContext {
  return {
    idleBorder: theme.input,
    hoverBorder: mixOklch(theme.input, theme.foreground, 0.18),
    activeBorder: theme.ring,
    invalidBorder: theme.destructive,
    ring: mixOklch(theme.background, theme.ring, 0.5),
    invalidRing: mixOklch(theme.background, theme.destructive, 0.4),
    background: theme.background,
    hoverBackground: mixOklch(theme.background, theme.muted, 0.4),
    foreground: theme.foreground,
    mutedForeground: theme.mutedForeground,
  };
}

