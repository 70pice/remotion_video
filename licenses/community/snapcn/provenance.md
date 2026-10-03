# Snapcn source provenance

- Repository: https://github.com/snapcndev/snapcn
- Commit: `4399d249002afae506497cc90ac3f064e189127d`
- Imported: 2026-10-02
- License: MIT, Copyright (c) 2026 Sri Nath (snap-cn). See LICENSE.txt.
- Source: 21 selected `registry/snap-cn/{slug}/index.tsx` files, their `registry/snap-cn-ui/core` dependencies, Caret, and the Input style-context function.
- Local changes: absolute aliases become relative imports; most network Google font calls use an explicit system-font fallback adapter; the unused Tailwind Input UI is excluded, retaining its original context types and function; development-only console warning guards no longer require Node's process typings.
- Demo wrappers preserve upstream frame animation and provide Chinese examples and local SVG fixtures. No original website assets are downloaded.
- Inter (normal 400/500/600/700) and Source Serif 4 (normal 400/600) are now bundled from Fontsource 5.3.0 as unchanged Latin WOFF2 files. The two font imports in PromptZoom and AnswerStream select these real, separate sans/serif faces; they are loaded using FontFace and delayRender/continueRender. Asset hashes, package integrity and original OFL licenses are preserved under fonts/.
- Fonts without bundled assets still resolve to an explicit system fallback, including Geist, Space Grotesk, Outfit, Montserrat and Instrument Serif. Bundled Latin faces do not contain Chinese glyphs; Chinese still depends on installed fallback fonts and is not a pixel-identical reproduction.
- Motion, timing, props, geometry and theme helpers are preserved. Source comments identifying the pinned upstream commit are included in vendored files.
- TextSwap's destructured scene-preset name has one narrowly scoped eslint exception: the rule mistakes its `transition` prop for a CSS transition; the animation remains derived from useCurrentFrame.
- TerminalSimulator demo uses speed 1.2 and explicit short output-line delays. The midpoint therefore shows the landed terminal rather than the upstream transition before output starts; camera mathematics is unchanged. Frame 0 remains the intentional start of the title fade-in.
- Runtime dependencies: React, Remotion, culori. Type dependency: @types/culori.

## PromptZoom visual-fidelity correction

- The initial local preview replaced the author's English text with Chinese, used a single system font for both Inter and Source Serif 4, and extended the 90-frame preview to 180 frames. These choices changed typography and pacing even though the component's geometry and hard-cut algorithm were unchanged.
- The preview now follows the pinned `registry/snap-cn/prompt-zoom/config.ts`: original greeting/prompt/placeholder/model/effort, cut at 1.0s, typing at 0.35s, 18 chars/s, 2.547x scale, focus (0.27, 0.516), #266DF0 accent, 1280x720 at 30 fps and 90 frames. The Composition ID remains Snapcn-PromptZoom.
- No camera, typing, caret, layout or animation formula was edited. Matching the same font family and preview props is closer to the authored preview, not a guarantee of byte-identical pixels across font builds and Chrome versions.

The previous video uses its earlier TextBuild vendor copy. This namespace does not replace it.
