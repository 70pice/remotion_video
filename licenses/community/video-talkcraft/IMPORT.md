# video-talkcraft import

Pinned commit: 4cd673df4b7a6a35784a0881df223721789c5e23.

108 template/cards TSX files were imported from the pinned upstream source. `source-manifest.json` keeps the original upstream/import SHA256 for every card and never overwrites it. Some local card files now also carry `local_sha256` plus an `adaptation` note when VideoAgents added optional production slot or host-media styling hooks. Files without `local_sha256` are checked after CRLF-to-LF normalization so Windows line endings do not obscure source equality.

Standalone demo defaults and metadata are preserved for the local card modules. Production adaptations are optional props used by VideoAgents render bindings; they are separate from the original source hash record. `demo.tsx` supplies published author assets via `preview-props.ts` and isolates global CSS in a ShadowRoot.

Use: user-declared noncommercial personal short videos. PolyForm Noncommercial 1.0.0 retained. Media attribution and unresolved asset provenance are recorded separately. Website HTML/MP4 demos are a different implementation and may include sounds absent from original TSX. Source hash equality is not a pixel-identical website or audio claim.

Original import hashes and local adaptation hashes are both verified by `scripts/check-component-paths.mjs`. Original cards are vendored and excluded from first-party ESLint style rules. Strict TypeScript and frame render checks cover all imported cards when the full component verification pipeline is run.
