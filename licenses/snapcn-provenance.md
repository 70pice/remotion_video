# Snapcn TextBuild provenance

- Upstream repository: https://github.com/snapcndev/snapcn
- Pinned commit: `d4419a8c0366c4d6d3bf44d803e54593e8dd4ac3`
- Source path: `registry/snap-cn/text-build/index.tsx`
- Source: https://github.com/snapcndev/snapcn/blob/d4419a8c0366c4d6d3bf44d803e54593e8dd4ac3/registry/snap-cn/text-build/index.tsx
- Original source Git blob: `b6d92b9d6200b564cd83d8082bbdde7bba64559c`
- Local adapted file: `src/components/vendor/TextBuild.tsx`
- License: MIT, Copyright (c) 2026 Sri Nath (snap-cn).
- Upstream license: https://github.com/snapcndev/snapcn/blob/d4419a8c0366c4d6d3bf44d803e54593e8dd4ac3/LICENSE
- Full unchanged license text is retained in `licenses/snapcn-MIT.txt`.

## Retrieval

The GitHub Contents API JSON was read for the pinned commit. Its entire
`content` field was decoded from Base64 once and written as UTF-8 without a
BOM. The upstream animation source was adapted only after that write.

## Local changes

1. Removed the `@/lib/snap-cn-ui` theme and Google font-loading dependency,
   including the `theme` and `mode` props.
2. Defaulted `fontFamily` to `"Microsoft YaHei", sans-serif` and `color` to
   `#ffffff`. A caller can override either using ordinary CSS values.
3. Added `fontFamily` to `measureWordSizes` and its memo dependencies so the
   x-axis canvas measurement uses the same font as the rendered text.
4. Added a provenance comment. No dependencies were added.

The upstream frame-driven enter/reflow animation, `centeredPositions`, timing
defaults, axis settings, word splitting and blur/scale behavior are retained.
Text is split on spaces; Chinese callers should separate intended animation
units with spaces. Custom fonts must be loaded before mounting the component.

## Exports

- `TextBuild` and `TextBuildProps`
- `TextBuildAxis`
- `measureWordSizes(words, axis, fontSize, fontWeight, fontFamily?)`
- `centeredPositions(sizes, gap)`
