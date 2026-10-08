// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/donut-chart.tsx. See licenses/community/rve/PROVENANCE.md.

/**
 * Free Remotion Template Component
 * ---------------------------------
 * This template is free to use in your projects!
 * Credit appreciated but not required.
 *
 * Created by the team at https://www.reactvideoeditor.com
 *
 * Happy coding and building amazing videos! 🎉
 */

"use client";

import { interpolate, useCurrentFrame } from "remotion";

export interface ChartSegment { label: string; value: number; color: string; }

const defaultSegments: ChartSegment[] = [
    { label: "Completed", value: 40, color: "#4361ee" },
    { label: "In Progress", value: 25, color: "#7209b7" },
    { label: "Pending", value: 20, color: "#f72585" },
    { label: "Remaining", value: 15, color: "#4cc9f0" },
  ];

export interface DonutChartProps {
  segments?: ChartSegment[];
  title?: string;
  centerTarget?: number;
  centerValueText?: string;
  centerLabel?: string;
  layout?: "default" | "portrait";
  viewport?: { width: number; height: number };
  embedded?: boolean;
  revealFrame?: number;
  revealDurationFrames?: number;
}

const clamp = (value: number, min: number, max: number) => Math.max(min, Math.min(max, value));
const measureLegendUnits = (label: string) =>
  [...label].reduce((sum, char) => sum + (/^[\x20-\x7E]$/.test(char) ? 0.58 : 1), 0);

export default function DonutChart({
  segments = defaultSegments,
  title = "Completion Rate",
  centerTarget = 78,
  centerValueText,
  centerLabel = "Completion Rate",
  layout = "default",
  viewport,
  embedded = false,
  revealFrame,
  revealDurationFrames = 15,
}: DonutChartProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";
  const width = viewport?.width ?? (portrait ? 960 : 600);
  const height = viewport?.height ?? (portrait ? 1420 : 520);
  const titleHeight = embedded && title ? clamp(height * 0.14, 28, 96) : 0;
  const legendHeight = embedded ? clamp(height * 0.28, 58, 110) : 0;
  const drawingWidth = embedded ? width : portrait ? 960 : 600;
  const drawingHeight = embedded ? Math.max(1, height - titleHeight - legendHeight) : portrait ? 920 : 460;

  const total = Math.max(1, segments.reduce((sum, s) => sum + s.value, 0));
  const cx = embedded ? drawingWidth / 2 : portrait ? 480 : 300;
  const cy = embedded ? drawingHeight / 2 : portrait ? 370 : 230;
  const radius = embedded ? Math.max(1, Math.min(drawingWidth, drawingHeight) * 0.28) : portrait ? 270 : 120;
  const strokeWidth = embedded ? Math.max(4, Math.min(drawingWidth, drawingHeight) * 0.08) : portrait ? 72 : 20;
  const circumference = 2 * Math.PI * radius;
  const finalCenterText = centerValueText ?? `${centerTarget}%`;
  const centerTextLength = Math.max(1, [...finalCenterText].length);
  const centerLabelLength = Math.max(1, [...centerLabel].length);
  const centerFontBase = embedded ? clamp(Math.min(drawingWidth, drawingHeight) * 0.18, 12, portrait ? 128 : 48) : portrait ? 128 : 48;
  const centerLabelBase = embedded ? clamp(Math.min(drawingWidth, drawingHeight) * 0.07, 8, portrait ? 44 : 16) : portrait ? 44 : 16;
  const centerFontSize = embedded ? Math.min(centerFontBase, (radius * 1.28) / (centerTextLength * 0.72)) : centerFontBase;
  const centerLabelSize = embedded ? Math.min(centerLabelBase, (radius * 1.35) / (centerLabelLength * 0.58)) : centerLabelBase;
  const legendRows = embedded ? Math.max(1, segments.length) : 1;
  const legendRowGap = embedded ? clamp(legendHeight * 0.06, 2, 8) : 20;
  const legendLongestUnits = Math.max(1, ...segments.map((segment) => measureLegendUnits(segment.label)));
  const legendAvailableWidth = Math.max(1, width - 24);
  const legendFontByHeight = ((legendHeight - legendRowGap * (legendRows - 1)) / legendRows) * 0.58;
  const legendFontByWidth = legendAvailableWidth / (legendLongestUnits + 1.8);
  const legendFontSize = embedded
    ? clamp(Math.min(legendFontByHeight, legendFontByWidth), 8, portrait ? 42 : 13)
    : portrait ? 42 : 13;
  const legendDotSize = embedded ? clamp(legendFontSize * 0.55, 4, portrait ? 22 : 10) : portrait ? 22 : 10;

  let cumulativeOffset = 0;

  // Center stat animation
  const immediateEmbedded = embedded && revealFrame === undefined;
  const revealStart = revealFrame ?? 10;
  const revealEnd = revealFrame === undefined ? 50 : revealStart + revealDurationFrames;
  const progress = immediateEmbedded ? 1 : interpolate(frame, [revealStart, revealEnd], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  const centerValue = immediateEmbedded ? centerTarget : Math.round(
    interpolate(frame, [revealStart, revealEnd], [0, centerTarget], {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
    })
  );
  const centerText = revealFrame !== undefined && progress <= 0 ? "" : centerValueText ?? `${centerValue}%`;

  return (
    <div
      data-donut-chart
      data-embedded={embedded}
      style={{
        position: "absolute",
        top: embedded ? 0 : "50%",
        left: embedded ? 0 : "50%",
        transform: embedded ? "none" : "translate(-50%, -50%)",
        width: embedded ? width : "100%",
        height: embedded ? height : "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "Inter, system-ui, sans-serif",
        background: embedded ? "transparent" : "linear-gradient(to bottom right, #111827, #1f2937)",
      }}
    >
      <div
        style={{
          position: "relative",
          width,
          height,
          backgroundColor: embedded ? "transparent" : "rgba(0, 0, 0, 0.2)",
          borderRadius: embedded ? 0 : "16px",
          boxShadow: embedded ? "none" : "0 10px 30px rgba(0, 0, 0, 0.3)",
          overflow: "hidden",
          padding: embedded ? 0 : "20px",
        }}
      >
        {/* Title */}
        {title ? <div
          style={{
            position: "absolute",
            top: embedded ? 0 : "20px",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: portrait ? "76px" : "28px",
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 4px rgba(0,0,0,0.3)",
            letterSpacing: "-0.5px",
          }}
        >
          {title}
        </div> : null}

        <svg width={drawingWidth} height={drawingHeight} style={{ marginTop: embedded ? titleHeight : portrait ? "120px" : "10px" }}>
          {/* Background ring */}
          <circle
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth={strokeWidth}
          />

          {/* Donut segments */}
          {segments.map((segment, i) => {
            const segmentLength = (segment.value / total) * circumference;
            const currentOffset = cumulativeOffset;
            cumulativeOffset += segmentLength;

            const segmentProgress = immediateEmbedded
              ? 1
              : revealFrame === undefined
              ? interpolate(
                  frame,
                  [i * 12, 20 + i * 12],
                  [0, 1],
                  { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
                )
              : progress;

            const animatedLength = segmentLength * segmentProgress;
            if ((revealFrame !== undefined || immediateEmbedded) && segmentProgress <= 0) return null;

            return (
              <circle
                key={`seg-${i}`}
                data-donut-segment={segment.label}
                data-donut-ratio={Number((segment.value / total).toFixed(4))}
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke={segment.color}
                strokeWidth={strokeWidth}
                strokeLinecap="round"
                strokeDasharray={`${animatedLength} ${circumference - animatedLength}`}
                strokeDashoffset={-currentOffset}
                transform={`rotate(-90 ${cx} ${cy})`}
              />
            );
          })}

          {/* Center number */}
          <text
            x={cx}
            y={cy - 5}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="white"
            fontSize={centerFontSize}
            fontWeight="bold"
          >
            {centerText}
          </text>

          {/* Center label */}
          <text
            x={cx}
            y={cy + centerFontSize * 0.28}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="rgba(255,255,255,0.6)"
            fontSize={centerLabelSize}
          >
            {centerLabel}
          </text>
        </svg>

        {/* Legend */}
        <div
          data-donut-legend={embedded ? "embedded" : "default"}
          style={{
            position: "absolute",
            bottom: embedded ? 0 : "25px",
            height: embedded ? legendHeight : undefined,
            left: embedded ? 0 : "50%",
            right: embedded ? 0 : undefined,
            width: embedded ? "100%" : undefined,
            transform: embedded ? "none" : "translateX(-50%)",
            display: embedded ? "grid" : "flex",
            gridTemplateRows: embedded ? `repeat(${legendRows}, minmax(0, 1fr))` : undefined,
            rowGap: embedded ? legendRowGap : undefined,
            gap: embedded ? undefined : "20px",
            flexWrap: embedded ? undefined : "wrap",
            justifyContent: "center",
            justifyItems: embedded ? "center" : undefined,
            alignContent: "center",
            alignItems: embedded ? "center" : undefined,
            boxSizing: embedded ? "border-box" : undefined,
            padding: embedded ? "0 12px" : undefined,
            overflow: "hidden",
          }}
        >
          {segments.map((segment, i) => {
            const legendOpacity = interpolate(
              frame,
              revealFrame === undefined ? [5 + i * 12, 15 + i * 12] : [0, 1],
              [0, 1],
              { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
            );

            return (
              <div
                key={`legend-${i}`}
                data-donut-legend-item={segment.label}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: embedded ? "center" : undefined,
                  maxWidth: embedded ? "100%" : undefined,
                  minWidth: embedded ? 0 : undefined,
                  gap: embedded ? Math.max(4, legendFontSize * 0.35) : "6px",
                  opacity: legendOpacity,
                }}
              >
                <div
                  style={{
                    width: legendDotSize,
                    height: legendDotSize,
                    borderRadius: "50%",
                    backgroundColor: segment.color,
                  }}
                />
                <span
                  style={{
                    color: "rgba(255,255,255,0.8)",
                    fontSize: legendFontSize,
                    lineHeight: embedded ? 1 : undefined,
                    whiteSpace: embedded ? "nowrap" : undefined,
                    overflow: embedded ? "visible" : undefined,
                    textOverflow: embedded ? "clip" : undefined,
                  }}
                >
                  {segment.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
