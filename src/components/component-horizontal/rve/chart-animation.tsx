// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/chart-animation.tsx. See licenses/community/rve/PROVENANCE.md.

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

export interface ChartPoint { x: number; y: number; label: string; }

const defaultData: ChartPoint[] = [
    { x: 0, y: 50, label: "Jan" },
    { x: 1, y: 80, label: "Feb" },
    { x: 2, y: 30, label: "Mar" },
    { x: 3, y: 70, label: "Apr" },
    { x: 4, y: 45, label: "May" },
    { x: 5, y: 90, label: "Jun" },
    { x: 6, y: 60, label: "Jul" },
    { x: 7, y: 75, label: "Aug" },
    { x: 8, y: 40, label: "Sep" },
    { x: 9, y: 85, label: "Oct" },
  ];

export interface ChartAnimationProps {
  data?: ChartPoint[];
  title?: string;
  subtitle?: string;
  maxValue?: number;
  layout?: "default" | "portrait";
}

export default function ChartAnimation({ data = defaultData, title = "Monthly Performance", subtitle = "Data visualization for 2023", maxValue = 100, layout = "default" }: ChartAnimationProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";

  // Sample data points (can be replaced with your actual data)


  // Color palette for bars
  const colors = [
    "#4361ee",
    "#3a0ca3",
    "#7209b7",
    "#f72585",
    "#4cc9f0",
    "#4895ef",
    "#560bad",
    "#b5179e",
    "#f15bb5",
    "#00b4d8",
  ];

  // Chart dimensions
  const chartWidth = portrait ? 960 : 900;
  const chartHeight = portrait ? 1380 : 500;
  const padding = portrait ? 115 : 60;

  // Scale data to fit chart dimensions
  const xScale = (x: number) =>
    (x / (Math.max(1, data.length - 1))) * (chartWidth - padding * 2) + padding;
  const barWidth = ((chartWidth - padding * 2) / data.length) * 0.7;

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
          width: `${chartWidth}px`,
          height: `${chartHeight}px`,
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
          overflow: "hidden",
          padding: portrait ? "30px" : "20px",
        }}
      >
        <svg width={chartWidth} height={chartHeight}>
          {/* X-axis line */}
          <line
            x1={padding}
            y1={chartHeight - padding}
            x2={chartWidth - padding}
            y2={chartHeight - padding}
            stroke="rgba(255, 255, 255, 0.2)"
            strokeWidth="2"
          />

          {/* X-axis labels */}
          {data.map((point, i) => (
            <text
              key={`x-label-${i}`}
              x={xScale(point.x)}
              y={chartHeight - padding + 25}
              textAnchor="middle"
              fill="rgba(255, 255, 255, 0.8)"
              fontSize={portrait ? "40" : "14"}
              fontWeight="500"
            >
              {point.label}
            </text>
          ))}

          {/* Bar chart with animation and different colors */}
          {data.map((point, i) => {
            const barHeight = (point.y / Math.max(1, maxValue)) * (chartHeight - padding * 2);

            // Animation that grows bars from bottom
            const barProgress = interpolate(
              frame,
              [i * 3, 15 + i * 3],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );

            const currentHeight = barHeight * barProgress;
            const currentY = chartHeight - padding - currentHeight;

            return (
              <g key={`bar-${i}`}>
                <rect
                  x={xScale(point.x) - barWidth / 2}
                  y={currentY}
                  width={barWidth}
                  height={currentHeight}
                  fill={colors[i % colors.length]}
              rx={portrait ? "12" : "6"}
              ry={portrait ? "12" : "6"}
                  filter="url(#shadow)"
                />
                <text
                  x={xScale(point.x)}
                  y={currentY - 10}
                  textAnchor="middle"
                  fill="white"
                  fontSize={portrait ? "42" : "14"}
                  fontWeight="bold"
                  opacity={barProgress > 0.9 ? 1 : 0}
                >
                  {point.y}
                </text>
              </g>
            );
          })}

          {/* Define shadow filter */}
          <defs>
            <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="4" stdDeviation="4" floodOpacity="0.3" />
            </filter>
          </defs>
        </svg>

        {/* Chart title */}
        <div
          style={{
            position: "absolute",
            top: "25px",
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
        </div>

        {/* Chart subtitle */}
        <div
          style={{
            position: "absolute",
            top: portrait ? "116px" : "60px",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: portrait ? "42px" : "16px",
            color: "rgba(255, 255, 255, 0.7)",
            textShadow: "0 1px 2px rgba(0,0,0,0.2)",
          }}
        >
          {subtitle}
        </div>
      </div>
    </div>
  );
}
