// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/pie-chart.tsx. See licenses/community/rve/PROVENANCE.md.

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
    { label: "Product A", value: 35, color: "#4361ee" },
    { label: "Product B", value: 25, color: "#7209b7" },
    { label: "Product C", value: 20, color: "#f72585" },
    { label: "Product D", value: 12, color: "#4cc9f0" },
    { label: "Product E", value: 8, color: "#a855f7" },
  ];

export interface PieChartProps {
  segments?: ChartSegment[];
  title?: string;
  layout?: "default" | "portrait";
}

export default function PieChart({ segments = defaultSegments, title = "Market Share", layout = "default" }: PieChartProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";



  const total = Math.max(1, segments.reduce((sum, s) => sum + s.value, 0));
  const cx = portrait ? 480 : 300;
  const cy = portrait ? 320 : 220;
  const radius = portrait ? 240 : 140;
  const circumference = 2 * Math.PI * radius;

  let cumulativeOffset = 0;

  return (
    <div
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        transform: "translate(-50%, -50%)",
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "Inter, system-ui, sans-serif",
        background: "linear-gradient(to bottom right, #111827, #1f2937)",
      }}
    >
      <div
        style={{
          position: "relative",
          width: portrait ? "960px" : "600px",
          height: portrait ? "1420px" : "520px",
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
          overflow: "hidden",
          padding: "20px",
        }}
      >
        {/* Title */}
        <div
          style={{
            position: "absolute",
            top: portrait ? "30px" : "20px",
            left: portrait ? "60px" : "50%",
            width: portrait ? "calc(100% - 120px)" : undefined,
            transform: portrait ? undefined : "translateX(-50%)",
            textAlign: portrait ? "center" : undefined,
            lineHeight: portrait ? 1.18 : undefined,
            fontSize: portrait ? "56px" : "28px",
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 4px rgba(0,0,0,0.3)",
            letterSpacing: "-0.5px",
          }}
        >
          {title}
        </div>

        <svg width={portrait ? 960 : 600} height={portrait ? 700 : 440} style={{ marginTop: portrait ? "260px" : "10px" }}>
          {/* Pie segments */}
          {segments.map((segment, i) => {
            const segmentLength = (segment.value / total) * circumference;
            const currentOffset = cumulativeOffset;
            cumulativeOffset += segmentLength;

            const segmentProgress = interpolate(
              frame,
              [i * 10, 15 + i * 10],
              [0, 1],
              { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
            );

            const animatedLength = segmentLength * segmentProgress;

            return (
              <circle
                key={`seg-${i}`}
                cx={cx}
                cy={cy}
                r={radius}
                fill="none"
                stroke={segment.color}
                strokeWidth={portrait ? "160" : "80"}
                strokeDasharray={`${animatedLength} ${circumference - animatedLength}`}
                strokeDashoffset={-currentOffset}
                transform={`rotate(-90 ${cx} ${cy})`}
              />
            );
          })}

          {/* Center circle for visual balance */}
          <circle cx={cx} cy={cy} r={portrait ? 88 : 60} fill="#111827" />
        </svg>

        {/* Legend */}
        <div
          style={{
            position: "absolute",
            bottom: portrait ? "36px" : "25px",
            left: "50%",
            width: portrait ? "840px" : undefined,
            transform: "translateX(-50%)",
            display: "flex",
            gap: portrait ? "18px" : "20px",
            flexDirection: portrait ? "column" : undefined,
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          {segments.map((segment, i) => {
            const legendOpacity = interpolate(
              frame,
              [5 + i * 10, 15 + i * 10],
              [0, 1],
              { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
            );

            return (
              <div
                key={`legend-${i}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: portrait ? "center" : undefined,
                  gap: portrait ? "14px" : "6px",
                  opacity: legendOpacity,
                }}
              >
                <div
                  style={{
                    width: portrait ? "22px" : "10px",
                    height: portrait ? "22px" : "10px",
                    borderRadius: "50%",
                    flexShrink: 0,
                    backgroundColor: segment.color,
                  }}
                />
                <span
                  style={{
                    color: "rgba(255,255,255,0.8)",
                    fontSize: portrait ? "48px" : "13px",
                    lineHeight: portrait ? 1.2 : undefined,
                    overflowWrap: portrait ? "anywhere" : undefined,
                  }}
                >
                  {segment.label} ({Math.round((segment.value / total) * 100)}%)
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
