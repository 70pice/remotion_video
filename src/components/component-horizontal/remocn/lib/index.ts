// Vendored from remocn @ 8ae853e4c08108105684d4b8cac7f22400840d2a: registry/remocn-ui/core/index.ts
export {
  mixOklch,
  oklchToRgb,
  parseColor,
  rgbToOklch,
  toCss,
} from "./color";
export type { EasingName, SpringName } from "./motion";
export { easings, springs } from "./motion";
export type { RemocnTheme, RemocnUIProviderProps } from "./theme";
export {
  defaultDarkTheme,
  defaultLightTheme,
  RemocnUIProvider,
  useRemocnTheme,
} from "./theme";
export type { TypewriterOptions, TypewriterState } from "./timeline";
export {
  clamp01,
  framesFor,
  revealCount,
  revealedText,
  useCurrentState,
  useStateTransition,
  useTypewriter,
} from "./timeline";
export type { Step } from "./types";
