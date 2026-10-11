// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/line-chart.tsx. See licenses/community/rve/PROVENANCE.md.

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
    { x: 0, y: 25, label: "Jan" },
    { x: 1, y: 40, label: "Feb" },
    { x: 2, y: 35, label: "Mar" },
    { x: 3, y: 55, label: "Apr" },
    { x: 4, y: 50, label: "May" },
    { x: 5, y: 70, label: "Jun" },
    { x: 6, y: 65, label: "Jul" },
    { x: 7, y: 80, label: "Aug" },
    { x: 8, y: 75, label: "Sep" },
    { x: 9, y: 90, label: "Oct" },
  ];

export interface LineChartProps {
  data?: ChartPoint[];
  title?: string;
  maxValue?: number;
  layout?: "default" | "portrait";
  compactBox?: boolean;
  unit?: string;
  subtitle?: string;
  accentColor?: string;
}

export default function LineChart(props: LineChartProps = {}) {
  const {layout = "default", compactBox = false, unit = "", subtitle, accentColor = "#4361ee"} = props;
  const data = compactBox ? (props.data ?? []) : (props.data ?? defaultData);
  const title = props.title ?? (compactBox ? "" : "Revenue Growth");
  const maxValue = props.maxValue ?? (compactBox ? Math.max(1, ...data.map((point) => point.y)) : 100);
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";



  const chartWidth = compactBox ? 760 : portrait ? 960 : 900;
  const chartHeight = compactBox ? 420 : portrait ? 1380 : 500;
  const padding = compactBox ? 64 : portrait ? 125 : 70;

  const xScale = (x: number) =>
    (x / (Math.max(1, data.length - 1))) * (chartWidth - padding * 2) + padding;
  const yScale = (y: number) =>
    chartHeight - padding - (y / Math.max(1, maxValue)) * (chartHeight - padding * 2);

  // Build polyline points
  const points = data.map((d) => `${xScale(d.x)},${yScale(d.y)}`).join(" ");

  // Calculate total polyline length (approximate)
  let totalLength = 0;
  for (let i = 1; i < data.length; i++) {
    const dx = xScale(data[i].x) - xScale(data[i - 1].x);
    const dy = yScale(data[i].y) - yScale(data[i - 1].y);
    totalLength += Math.sqrt(dx * dx + dy * dy);
  }

  // Animate line drawing
  const dashOffset = interpolate(frame, [0, 60], [totalLength, 0], {
    extrapolateRight: "clamp",
  });

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
        background: compactBox ? "transparent" : "linear-gradient(to bottom right, #111827, #1f2937)",
      }}
    >
      <div
        style={{
          position: "relative",
          width: `${chartWidth}px`,
          height: `${chartHeight}px`,
          backgroundColor: compactBox ? "rgba(15, 23, 42, 0.58)" : "rgba(0, 0, 0, 0.2)",
          border: compactBox ? "1px solid rgba(148, 163, 184, 0.24)" : undefined,
          borderRadius: compactBox ? "28px" : "16px",
          boxShadow: compactBox ? "0 18px 48px rgba(0, 0, 0, 0.22)" : "0 10px 30px rgba(0, 0, 0, 0.3)",
          overflow: "hidden",
          padding: compactBox ? "0" : "20px",
        }}
      >
        <svg width={chartWidth} height={chartHeight}>
          {/* Grid lines */}
          {[0, maxValue * 0.25, maxValue * 0.5, maxValue * 0.75, maxValue].map((val) => (
            <line
              key={`grid-${val}`}
              x1={padding}
              y1={yScale(val)}
              x2={chartWidth - padding}
              y2={yScale(val)}
              stroke="rgba(255,255,255,0.1)"
              strokeWidth="1"
            />
          ))}

          {/* Y-axis labels */}
          {[0, maxValue * 0.25, maxValue * 0.5, maxValue * 0.75, maxValue].map((val) => (
            <text
              key={`y-${val}`}
              x={padding - 15}
              y={yScale(val) + 5}
              textAnchor="end"
              fill="rgba(255,255,255,0.6)"
              fontSize={compactBox ? "24" : portrait ? "38" : "12"}
            >
              {`${Math.round(val)}${unit}`}
            </text>
          ))}

          {/* X-axis line */}
          <line
            x1={padding}
            y1={chartHeight - padding}
            x2={chartWidth - padding}
            y2={chartHeight - padding}
            stroke="rgba(255,255,255,0.2)"
            strokeWidth="2"
          />

          {/* Y-axis line */}
          <line
            x1={padding}
            y1={padding}
            x2={padding}
            y2={chartHeight - padding}
            stroke="rgba(255,255,255,0.2)"
            strokeWidth="2"
          />

          {/* X-axis labels */}
          {data.map((point, i) => (
            <text
              key={`x-label-${i}`}
              x={xScale(point.x)}
              y={chartHeight - padding + 25}
              textAnchor="middle"
              fill="rgba(255,255,255,0.8)"
              fontSize={compactBox ? "24" : portrait ? "38" : "13"}
              fontWeight="500"
            >
              {point.label}
            </text>
          ))}

          {/* Animated polyline */}
          <polyline
            points={points}
            fill="none"
            stroke={accentColor}
            strokeWidth={compactBox ? "8" : portrait ? "14" : "3"}
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeDasharray={totalLength}
            strokeDashoffset={dashOffset}
          />

          {/* Data points */}
          {data.map((point, i) => {
            const pointProgress = interpolate(
              frame,
              [5 + i * 6, 10 + i * 6],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            );

            return (
              <circle
                key={`point-${i}`}
                cx={xScale(point.x)}
                cy={yScale(point.y)}
                r={(portrait ? 20 : 5) * pointProgress}
                fill={compactBox ? "#f8fafc" : "#f72585"}
                stroke="white"
                strokeWidth={compactBox ? "4" : "2"}
                opacity={pointProgress}
              />
            );
          })}
        </svg>

        {/* Chart title */}
        <div
          style={{
            position: "absolute",
            top: compactBox ? "24px" : "25px",
            left: "50%",
            transform: "translateX(-50%)",
            fontSize: compactBox ? "34px" : portrait ? "76px" : "28px",
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 4px rgba(0,0,0,0.3)",
            letterSpacing: "-0.5px",
            whiteSpace: "nowrap",
          }}
        >
          {title}
        </div>
        {compactBox && subtitle ? (
          <div
            style={{
              position: "absolute",
              left: "50%",
              bottom: "28px",
              transform: "translateX(-50%)",
              fontSize: "24px",
              fontWeight: 700,
              color: "rgba(226,232,240,0.88)",
              whiteSpace: "nowrap",
            }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}
