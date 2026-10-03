# RVE template imports

- Upstream: https://github.com/reactvideoeditor/remotion-templates
- Fixed source commit: `6209b724798e48ff395f8df1a6fa2d26082372b5`
- Imported: 11 standalone files under `templates/` (listed in the catalogue).
- License evidence: `README.upstream.md` preserves the complete upstream README; `LICENSE-DECLARATION.md` preserves its actual MIT declaration. This checkout does not supply a standalone LICENSE file; we do not manufacture one.

## Adaptations

- Kept upstream JSX, colors, typography, layout and frame-driven entrance animations.
- Exposed core text, values, datasets and labels as optional typed props; defaults retain upstream examples.
- Removed the `border-color 0.1s` CSS transition in Progress Steps: border color is still derived from the current frame.
- Clamped delayed bar growth on the left to avoid upstream negative SVG heights before each bar starts.
- Guarded empty/single point divisions and zero total divisions; custom chart scales use `maxValue`.
- Image Comparison Slider originally demonstrates colored panels; it now accepts image URLs and uses two locally provided demonstration fixtures by default.
- Fixed numeric locale to `en-US` for deterministic Stat Counter formatting across render machines.
- Removed an unused upstream `yScale` helper from Bar Chart to satisfy the project lint rules.
- The upstream Pie Chart is visually a thick ring, despite its name; the catalogue states this.

## Scope and limitations

These are actual imported templates, with basic data props added for reuse. Defaults are demonstrative sample data and quoted sample text, not verified factual claims. Layouts still use upstream fixed card dimensions and are previewed at 1280×720; a 9:16 production layout needs a separate composition adaptation. Arbitrarily many data points/steps, negative values and unusually long strings are not validated by these examples. Animation timings use upstream fixed frame intervals except components that already read fps. All 11 preview compositions last 180 frames at 30 fps.
