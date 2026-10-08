// Vendored from remotion-ui @ b7e0e6becc3d22b8b03dfef72c064f72ff9fad1f: apps/web/registry/bases/default/scenes/animated-bar-chart/index.tsx
import type {CSSProperties} from "react";
import {interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";
import {
  formatAxisValue,
  formatCompactNumber,
  niceDomain,
  readDelta,
  type ChartDatum,
} from "../../lib/chart-utils";
import {getSafeAreaPadding, scaleFont} from "../../lib/layout";
import {DURATION, EASING, STAGGER} from "../../lib/motion-tokens";

const fontFamily = '"Microsoft YaHei UI", "Microsoft YaHei", Arial, sans-serif';

export type AnimatedBarDatum = ChartDatum & {
  detail?: string;
  displayValue?: string;
  revealFrame?: number;
};

export type AnimatedBarChartProps = {
  data: AnimatedBarDatum[];
  title?: string;
  /** Supporting line under the title - the read, not a repeat of the title. */
  subtitle?: string;
  /** Fixed axis top. Defaults to a rounded domain above the largest bar. */
  maxValue?: number;
  /** Formats the value on the end of each bar. */
  valueFormatter?: (value: number, datum?: AnimatedBarDatum, progress?: number) => string;
  /** Label of the bar that carries `accentColor`. */
  highlightLabel?: string;
  /** Vertical gridlines and the value axis under the bars. */
  showAxis?: boolean;
  /** Bars beyond this count are dropped rather than squeezed. */
  maxBars?: number;
  barColor?: string;
  accentColor?: string;
  backgroundColor?: string;
  /** Fixed drawing size for embedding inside another Remotion scene. */
  viewport?: {width: number; height: number};
  /** Removes the full-scene plate so callers can keep their own safe area. */
  embedded?: boolean;
  /** Explicit baseline marker in the same units as the bars. */
  referenceValue?: number;
  referenceLabel?: string;
  /** Cued production reveals use a linear measured duration instead of the demo spring. */
  revealDurationFrames?: number;
  /**
   * Seconds the finished chart holds before it retreats. Omit to leave it up
   * for the rest of the scene - inside a `TransitionSeries` the transition
   * should cover the tail rather than the chart fading under it.
   */
  holdSeconds?: number;
};

const COLORS = {
  bg: "#080810",
  label: "rgba(250,250,250,0.62)",
  axis: "rgba(250,250,250,0.42)",
  grid: "rgba(250,250,250,0.08)",
  track: "rgba(250,250,250,0.05)",
  ink: "#fafafa",
  bar: "#2dd4bf",
  accent: "#e8b86d",
  up: "#2dd4bf",
  down: "#f87171",
} as const;

/** Length of the retreat once `holdSeconds` is up, in seconds. */
const EXIT_FOR = 0.42;

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

const exactZeroDomain = (maxValue: number, tickCount: number) => {
  const max = Math.max(1, maxValue);
  const ticks = Array.from({length: tickCount + 1}, (_, index) =>
    Number(((max * index) / tickCount).toPrecision(12)),
  );
  return {min: 0, max, span: max, ticks};
};

/**
 * Ranked bar chart scene.
 *
 * Bars are measured against a rounded axis rather than the largest value, so
 * the longest bar stops short of the frame edge and the numbers under it read
 * as a scale instead of decoration. Each bar's length and its counter share one
 * progress value - the number can never claim a total the bar has not reached yet.
 */
export const AnimatedBarChart: React.FC<AnimatedBarChartProps> = ({
  data,
  title,
  subtitle,
  maxValue,
  valueFormatter = (value) => formatCompactNumber(value),
  highlightLabel,
  showAxis = true,
  maxBars = 6,
  barColor = COLORS.bar,
  accentColor = COLORS.accent,
  backgroundColor = COLORS.bg,
  viewport,
  embedded = false,
  referenceValue,
  referenceLabel = "100 基准线",
  revealDurationFrames = DURATION.slow,
  holdSeconds,
}) => {
  const frame = useCurrentFrame();
  const videoConfig = useVideoConfig();
  const fps = videoConfig.fps;
  const width = viewport?.width ?? videoConfig.width;
  const height = viewport?.height ?? videoConfig.height;
  const safe = embedded
    ? {paddingLeft: 0, paddingRight: 0, paddingTop: 0, paddingBottom: 0}
    : getSafeAreaPadding({width, height});
  const isPortrait = embedded ? videoConfig.height > videoConfig.width : height > width;

  const bars = data.slice(0, maxBars);
  const tickCount = isPortrait ? 3 : 4;
  const domain = embedded && maxValue !== undefined
    ? exactZeroDomain(maxValue, tickCount)
    : niceDomain(maxValue === undefined ? bars.map((item) => item.value) : [0, maxValue], {includeZero: true, tickCount});

  const gap = scaleFont(embedded && isPortrait ? 22 : 16, width);
  const longestLabel = bars.reduce(
    (longest, item) => Math.max(longest, item.label.length),
    0,
  );
  const labelSize = scaleFont(isPortrait ? 46 : 28, width);
  const detailSize = scaleFont(isPortrait ? embedded ? 26 : 23 : 17, width);
  const valueSize = scaleFont(isPortrait ? embedded ? 46 : 52 : 30, width);
  const measuredLabelWidth = Math.round(Math.min(longestLabel, 16) * labelSize * 0.62) + gap;
  const labelWidth = embedded
    ? Math.min(Math.round(width * 0.36), Math.max(Math.round(width * 0.18), measuredLabelWidth))
    : Math.min(Math.round(width * 0.26), measuredLabelWidth);
  const valueWidth = Math.round(scaleFont(isPortrait ? embedded ? 160 : 150 : 96, width));
  const rowGap = embedded && isPortrait ? Math.round(Math.min(height * 0.055, scaleFont(72, width))) : scaleFont(18, width);
  const barHeight = embedded && isPortrait
    ? Math.max(1, Math.min(scaleFont(160, width), Math.floor((height - scaleFont(116, width) - rowGap * Math.max(0, bars.length - 1)) * 0.85 / Math.max(1, bars.length))))
    : Math.min(scaleFont(isPortrait ? 92 : 52, width), Math.round((height * (isPortrait ? 0.44 : 0.52)) / Math.max(1, bars.length)));

  const exit =
    holdSeconds === undefined
      ? 0
      : interpolate(frame, [holdSeconds * fps, (holdSeconds + EXIT_FOR) * fps], [0, 1], {
          easing: EASING.exit,
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
  const leaving = {
    opacity: 1 - exit,
    translate: `0 ${exit * -scaleFont(26, width)}px`,
  };

  const headerProgress = interpolate(frame, [0, DURATION.normal], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASING.enter,
  });
  const subtitleProgress = interpolate(frame, [STAGGER.tight, STAGGER.tight + DURATION.normal], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASING.enter,
  });
  const axisProgress = interpolate(frame, [STAGGER.normal, STAGGER.normal + DURATION.normal], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASING.enter,
  });

  return (
    <div
      data-animated-bar-chart
      data-embedded={embedded}
      style={{
        width,
        height,
        background: embedded ? "transparent" : backgroundColor,
        color: COLORS.ink,
        fontFamily,
        paddingLeft: safe.paddingLeft,
        paddingRight: safe.paddingRight,
        paddingTop: safe.paddingTop,
        paddingBottom: safe.paddingBottom,
        display: "flex",
        flexDirection: "column",
        justifyContent: isPortrait ? "center" : "flex-start",
        gap: scaleFont(embedded ? 26 : 40, width),
      }}
    >
      {title ? (
        <header style={{display: "grid", gap: scaleFont(12, width), ...leaving}}>
          <h2
            style={{
              margin: 0,
              fontSize: scaleFont(isPortrait ? 104 : 64, width),
              fontWeight: 700,
              lineHeight: 1.02,
              letterSpacing: embedded ? 0 : "-0.025em",
              opacity: headerProgress,
              translate: `0 ${(1 - headerProgress) * scaleFont(18, width)}px`,
            }}
          >
            {title}
          </h2>
          {subtitle ? (
            <p
              style={{
                margin: 0,
                color: COLORS.label,
                fontSize: scaleFont(isPortrait ? 44 : 30, width),
                fontWeight: 500,
                lineHeight: 1.25,
                opacity: subtitleProgress,
                translate: `0 ${(1 - subtitleProgress) * scaleFont(12, width)}px`,
              }}
            >
              {subtitle}
            </p>
          ) : null}
        </header>
      ) : null}

      <div style={{flex: isPortrait ? "0 0 auto" : 1, display: "flex", flexDirection: "column", justifyContent: embedded ? "flex-start" : "center", ...leaving}}>
        <div style={{position: "relative", display: "flex", flexDirection: "column", gap: rowGap}}>
          {showAxis ? (
            <div
              style={{
                position: "absolute",
                left: labelWidth + gap,
                right: valueWidth + gap,
                top: 0,
                bottom: 0,
                opacity: axisProgress,
              }}
            >
              {domain.ticks.map((tick) => (
                <div
                  key={tick}
                  style={{
                    position: "absolute",
                    top: 0,
                    bottom: 0,
                    left: `${((tick - domain.min) / domain.span) * 100}%`,
                    width: 1,
                    background: COLORS.grid,
                  }}
                />
              ))}
              {referenceValue === undefined ? null : (
                <div
                  data-reference-line
                  style={{
                    position: "absolute",
                    top: 0,
                    bottom: 0,
                    left: `${clamp01((referenceValue - domain.min) / domain.span) * 100}%`,
                    width: 2,
                    background: `${accentColor}a8`,
                    boxShadow: `0 0 ${scaleFont(12, width)}px ${accentColor}55`,
                  }}
                />
              )}
            </div>
          ) : null}

          {bars.map((item, index) => {
            const delay = STAGGER.normal + index * STAGGER.normal;
            const hasCue = item.revealFrame !== undefined;
            const immediateEmbedded = embedded && !hasCue;
            const enter = immediateEmbedded
              ? 1
              : hasCue
              ? interpolate(frame, [item.revealFrame ?? 0, (item.revealFrame ?? 0) + revealDurationFrames], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })
              : spring({
                  frame: frame - delay,
                  fps,
                  config: {damping: 20, stiffness: 110, mass: 0.9},
                  durationInFrames: DURATION.slow,
                });
            const isHighlighted = highlightLabel === item.label;
            const fill = item.color ?? (isHighlighted ? accentColor : barColor);
            const ratio = Math.max(0, (item.value - domain.min) / domain.span);
            const delta = readDelta(item.delta);
            const valueText = hasCue && enter <= 0 ? "" : item.displayValue ?? valueFormatter(item.value, item, enter);
            const detailText = hasCue && enter <= 0 ? "" : item.detail;
            const rowStyle: CSSProperties = hasCue
              ? {opacity: 1, translate: "0 0"}
              : immediateEmbedded
                ? {opacity: 1, translate: "0 0"}
              : {opacity: Math.min(1, enter * 1.6), translate: `0 ${(1 - enter) * scaleFont(14, width)}px`};

            return (
              <div
                key={item.label}
                data-bar-row={item.label}
                data-reveal-progress={Number(enter.toFixed(3))}
                style={{
                  display: "grid",
                  gridTemplateColumns: `${labelWidth}px 1fr ${valueWidth}px`,
                  gap,
                  alignItems: "center",
                  ...rowStyle,
                }}
              >
                <div style={{display: "grid", gap: scaleFont(5, width)}}>
                  <div
                    style={{
                      color: isHighlighted ? COLORS.ink : COLORS.label,
                      fontSize: labelSize,
                      fontWeight: isHighlighted ? 700 : 600,
                      letterSpacing: embedded ? 0 : "-0.01em",
                      lineHeight: 1.08,
                      overflow: embedded ? "visible" : "hidden",
                      textOverflow: embedded ? "clip" : "ellipsis",
                      whiteSpace: embedded ? "normal" : "nowrap",
                      overflowWrap: embedded ? "anywhere" : "normal",
                    }}
                  >
                    {item.label}
                  </div>
                  {item.detail ? (
                    <div style={{color: COLORS.label, fontSize: detailSize, fontWeight: 500, lineHeight: 1.15, whiteSpace: "normal", opacity: hasCue ? enter : 1}}>
                      {detailText}
                    </div>
                  ) : null}
                </div>

                <div style={{position: "relative", height: barHeight, borderRadius: barHeight / 2, background: COLORS.track}}>
                  <div
                    data-bar-fill={item.label}
                    data-bar-ratio={Number(ratio.toFixed(4))}
                    style={{
                      width: `${enter <= 0 ? 0 : (embedded ? ratio : Math.max(ratio, 0.015)) * enter * 100}%`,
                      height: "100%",
                      borderRadius: barHeight / 2,
                      background: `linear-gradient(90deg, ${fill}e6 0%, ${fill} 62%)`,
                      boxShadow: isHighlighted ? `0 0 ${scaleFont(28, width)}px ${fill}44` : undefined,
                    }}
                  />
                </div>

                <div style={{display: "grid", justifyItems: "end", gap: scaleFont(4, width), visibility: hasCue && enter <= 0 ? "hidden" : "visible", opacity: hasCue ? enter : 1}}>
                  <div
                    data-bar-value={item.label}
                    style={{
                      fontSize: valueSize,
                      fontWeight: 700,
                      letterSpacing: embedded ? 0 : "-0.02em",
                      lineHeight: 1,
                      fontVariantNumeric: "tabular-nums",
                      color: isHighlighted ? fill : COLORS.ink,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {valueText}
                  </div>
                  {delta.text ? (
                    <div
                      style={{
                        fontSize: scaleFont(21, width),
                        fontWeight: 600,
                        lineHeight: 1,
                        color: delta.direction === "down" ? COLORS.down : delta.direction === "up" ? COLORS.up : COLORS.label,
                        opacity: interpolate(enter, [0.7, 1], [0, 1], {
                          extrapolateLeft: "clamp",
                          extrapolateRight: "clamp",
                        }),
                      }}
                    >
                      {delta.text}
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>

        {showAxis ? (
          <div
            style={{
              position: "relative",
              height: scaleFont(referenceValue === undefined ? 24 : 52, width),
              marginLeft: labelWidth + gap,
              marginRight: valueWidth + gap,
              marginTop: scaleFont(10, width),
              opacity: axisProgress,
            }}
          >
            {domain.ticks.map((tick, index) => (
              <div
                key={tick}
                style={{
                  position: "absolute",
                  top: 0,
                  left: `${((tick - domain.min) / domain.span) * 100}%`,
                  transform: index === 0 ? "none" : index === domain.ticks.length - 1 ? "translateX(-100%)" : "translateX(-50%)",
                  color: COLORS.axis,
                  fontSize: scaleFont(21, width),
                  fontWeight: 600,
                  fontVariantNumeric: "tabular-nums",
                  whiteSpace: "nowrap",
                }}
              >
                {formatAxisValue(tick)}
              </div>
            ))}
            {referenceValue === undefined ? null : (
              <div
                data-reference-label
                style={{
                  position: "absolute",
                  top: scaleFont(26, width),
                  left: `${clamp01((referenceValue - domain.min) / domain.span) * 100}%`,
                  transform: "translateX(-50%)",
                  color: accentColor,
                  fontSize: scaleFont(19, width),
                  fontWeight: 700,
                  whiteSpace: "nowrap",
                }}
              >
                {referenceLabel}
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
};
