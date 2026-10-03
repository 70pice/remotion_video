# video-talkcraft import

Pinned commit: 4cd673df4b7a6a35784a0881df223721789c5e23.

108 template/cards TSX files copied byte for byte. source-manifest.json records SHA256 for each card. Original standalone defaults and metadata are preserved. demo.tsx supplies published author assets via preview-props.ts and isolates global CSS in a ShadowRoot; the card source is unchanged.

Use: user-declared noncommercial personal short videos. PolyForm Noncommercial 1.0.0 retained. Media attribution and unresolved asset provenance are recorded separately. Website HTML/MP4 demos are a different implementation and may include sounds absent from original TSX. Source equality is not a pixel-identical website or audio claim.

Original cards are vendored and excluded from first-party ESLint style rules. Strict TypeScript and frame render checks cover all imported cards.
