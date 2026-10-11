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
  compactBox?: boolean;
  unit?: string;
  fontFamily?: string;
}

export default function ChartAnimation(props: ChartAnimationProps = {}) {
  const {layout = "default", compactBox = false, fontFamily, unit = ""} = props;
  const data = compactBox ? (props.data ?? []) : (props.data ?? defaultData);
  const title = props.title ?? (compactBox ? "" : "Monthly Performance");
  const subtitle = props.subtitle ?? (compactBox ? "" : "Data visualization for 2023");
  const maxValue = props.maxValue ?? 100;
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
  const chartWidth = compactBox ? 640 : portrait ? 960 : 900;
  const chartHeight = compactBox ? 360 : portrait ? 1380 : 500;
  const padding = compactBox ? Math.max(82, String(Math.round(maxValue)).length * 12 + unit.length * 19 + 18) : portrait ? 115 : 60;
  const plotTop = compactBox ? 104 : padding;
  const plotBottom = compactBox ? 58 : padding;
  const plotHeight = chartHeight - plotTop - plotBottom;
  const baselineY = chartHeight - plotBottom;

  // Scale data to fit chart dimensions
  const xScale = (x: number) =>
    (compactBox ? (x + 0.5) / Math.max(1, data.length) : x / Math.max(1, data.length - 1))
      * (chartWidth - padding * 2) + padding;
  const barWidth = data.length ? ((chartWidth - padding * 2) / data.length) * 0.62 : 0;

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
        fontFamily: fontFamily || "Inter, system-ui, sans-serif",
        background: compactBox ? "transparent" : "linear-gradient(to bottom right, #111827, #1f2937)",
      }}
    >
      <div
        style={{
          position: "relative",
          width: compactBox ? "100%" : `${chartWidth}px`,
          height: compactBox ? "100%" : `${chartHeight}px`,
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          borderRadius: compactBox ? "24px" : "16px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
          overflow: "hidden",
          padding: compactBox ? 0 : portrait ? "30px" : "20px",
        }}
      >
        <svg width={compactBox ? "100%" : chartWidth} height={compactBox ? "100%" : chartHeight} viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
          {compactBox ? (maxValue < 2 ? [0, maxValue] : [0, maxValue * 0.5, maxValue]).map((val) => (
            <g key={`grid-${val}`}>
              <line
                x1={padding}
                y1={baselineY - (val / Math.max(1, maxValue)) * plotHeight}
                x2={chartWidth - padding}
                y2={baselineY - (val / Math.max(1, maxValue)) * plotHeight}
                stroke="rgba(255, 255, 255, 0.13)"
                strokeWidth="1"
              />
              <text
                x={padding - 12}
                y={baselineY - (val / Math.max(1, maxValue)) * plotHeight + 7}
                textAnchor="end"
                fill="rgba(255,255,255,0.58)"
                fontSize="19"
                fontWeight="700"
              >
                {`${Math.round(val)}${unit}`}
              </text>
            </g>
          )) : null}
          {/* X-axis line */}
          <line
            x1={padding}
            y1={baselineY}
            x2={chartWidth - padding}
            y2={baselineY}
            stroke="rgba(255, 255, 255, 0.2)"
            strokeWidth="2"
          />

          {/* X-axis labels */}
          {data.map((point, i) => (
            <text
              key={`x-label-${i}`}
              x={xScale(point.x)}
              y={compactBox ? chartHeight - 24 : chartHeight - padding + 25}
              textAnchor="middle"
              fill="rgba(255, 255, 255, 0.8)"
              fontSize={compactBox ? "22" : portrait ? "40" : "14"}
              fontWeight="500"
            >
              {point.label}
            </text>
          ))}

          {/* Bar chart with animation and different colors */}
          {data.map((point, i) => {
            const barHeight = (point.y / Math.max(1, maxValue)) * (compactBox ? plotHeight : chartHeight - padding * 2);

            // Animation that grows bars from bottom
            const barProgress = interpolate(
              frame,
              [i * 3, 15 + i * 3],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );

            const currentHeight = barHeight * barProgress;
            const currentY = baselineY - currentHeight;

            return (
              <g key={`bar-${i}`}>
                <rect
                  x={xScale(point.x) - barWidth / 2}
                  y={currentY}
                  width={barWidth}
                  height={currentHeight}
                  fill={colors[i % colors.length]}
              rx={compactBox ? "8" : portrait ? "12" : "6"}
              ry={compactBox ? "8" : portrait ? "12" : "6"}
                  filter="url(#shadow)"
                />
                <text
                  x={xScale(point.x)}
                  y={Math.max(plotTop + 20, currentY - 10)}
                  textAnchor="middle"
                  fill="white"
                  fontSize={compactBox ? "22" : portrait ? "42" : "14"}
                  fontWeight="bold"
                  opacity={barProgress > 0.9 ? 1 : 0}
                >
                  {`${point.y}${unit}`}
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
            top: compactBox ? "20px" : "25px",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: compactBox ? "26px" : portrait ? "76px" : "28px",
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 4px rgba(0,0,0,0.3)",
            letterSpacing: "-0.5px",
            lineHeight: 1.05,
            whiteSpace: "nowrap",
          }}
        >
          {title}
        </div>

        {/* Chart subtitle */}
        <div
          style={{
            position: "absolute",
            top: compactBox ? "54px" : portrait ? "116px" : "60px",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: compactBox ? "18px" : portrait ? "42px" : "16px",
            color: "rgba(255, 255, 255, 0.7)",
            textShadow: "0 1px 2px rgba(0,0,0,0.2)",
            whiteSpace: "nowrap",
          }}
        >
          {subtitle}
        </div>
      </div>
    </div>
  );
}
