// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/comparison-chart.tsx. See licenses/community/rve/PROVENANCE.md.

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

export interface ComparisonChartProps {
  title?: string;
  before?: number;
  after?: number;
  beforeLabel?: string;
  afterLabel?: string;
  maxValue?: number;
  suffix?: string;
  layout?: "default" | "portrait";
  compactBox?: boolean;
  fontFamily?: string;
}

export default function ComparisonChart({
  title = "Performance Comparison", before = 34, after = 89,
  beforeLabel = "Before", afterLabel = "After", maxValue = 100, suffix = "%", layout = "default", compactBox = false, fontFamily,
}: ComparisonChartProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";

  const maxBarHeight = compactBox ? 80 : portrait ? 620 : 280;

  // Before value animation
  const beforeValue = Math.round(
    interpolate(frame, [10, 40], [0, before], {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
    })
  );

  const beforeBarHeight = interpolate(frame, [10, 40], [0, (before / Math.max(1, maxValue)) * maxBarHeight], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  // After value animation (starts slightly later)
  const afterValue = Math.round(
    interpolate(frame, [20, 50], [0, after], {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
    })
  );

  const afterBarHeight = interpolate(frame, [20, 50], [0, (after / Math.max(1, maxValue)) * maxBarHeight], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });

  // Divider line animation
  const dividerOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateRight: "clamp",
  });

  const dividerHeight = interpolate(frame, [0, 20], [0, 350], {
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
        fontFamily: fontFamily || "Inter, system-ui, sans-serif",
        background: "linear-gradient(to bottom right, #111827, #1f2937)",
      }}
    >
      <div
        style={{
          position: "relative",
          width: compactBox ? "100%" : portrait ? "960px" : "700px",
          height: compactBox ? "100%" : portrait ? "1420px" : "480px",
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
          padding: compactBox ? "18px" : "40px",
          boxSizing: compactBox ? "border-box" : undefined,
        }}
      >
        {/* Title */}
        <div
          style={{
            fontSize: compactBox ? "32px" : portrait ? "76px" : "28px",
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 4px rgba(0,0,0,0.3)",
            letterSpacing: "-0.5px",
            textAlign: "center",
            marginBottom: compactBox ? "8px" : "30px",
            lineHeight: compactBox ? 1.1 : undefined,
          }}
        >
          {title}
        </div>

        {/* Comparison container */}
        <div
          style={{
            display: "flex",
            flexDirection: compactBox ? "row" : portrait ? "column" : "row",
            alignItems: "flex-end",
            justifyContent: "center",
            height: compactBox ? "calc(100% - 52px)" : `${maxBarHeight + 80}px`,
            position: "relative",
          }}
        >
          {/* Before side */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              flex: 1,
            }}
          >
            {/* Value */}
            <div
              style={{
                fontSize: compactBox ? "46px" : portrait ? "126px" : "48px",
                fontWeight: "bold",
                color: "#ef4444",
                marginBottom: compactBox ? "8px" : "15px",
                lineHeight: compactBox ? 1.05 : undefined,
              }}
            >
              {beforeValue}{suffix}
            </div>

            {/* Bar */}
            <div
              style={{
                width: compactBox ? "120px" : portrait ? "300px" : "120px",
                height: `${beforeBarHeight}px`,
                backgroundColor: "#ef4444",
                borderRadius: "8px 8px 0 0",
                boxShadow: "0 0 20px rgba(239, 68, 68, 0.3)",
              }}
            />

            {/* Label */}
            <div
              style={{
                fontSize: compactBox ? "28px" : portrait ? "52px" : "20px",
                fontWeight: "600",
                color: "rgba(255,255,255,0.8)",
                marginTop: compactBox ? "8px" : "15px",
                lineHeight: compactBox ? 1.1 : undefined,
              }}
            >
              {beforeLabel}
            </div>
          </div>

          {/* Divider */}
          <div
            style={{
              width: compactBox ? "2px" : portrait ? "70%" : "2px",
              height: compactBox ? "100%" : portrait ? "2px" : `${dividerHeight}px`,
              backgroundColor: "rgba(255,255,255,0.2)",
              opacity: dividerOpacity,
              alignSelf: "center",
              margin: compactBox ? "0 22px" : portrait ? "42px 0" : "0 30px",
            }}
          />

          {/* After side */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              flex: 1,
            }}
          >
            {/* Value */}
            <div
              style={{
                fontSize: compactBox ? "46px" : portrait ? "126px" : "48px",
                fontWeight: "bold",
                color: "#4361ee",
                marginBottom: compactBox ? "8px" : "15px",
                lineHeight: compactBox ? 1.05 : undefined,
              }}
            >
              {afterValue}{suffix}
            </div>

            {/* Bar */}
            <div
              style={{
                width: compactBox ? "120px" : portrait ? "300px" : "120px",
                height: `${afterBarHeight}px`,
                backgroundColor: "#4361ee",
                borderRadius: "8px 8px 0 0",
                boxShadow: "0 0 20px rgba(67, 97, 238, 0.3)",
              }}
            />

            {/* Label */}
            <div
              style={{
                fontSize: compactBox ? "28px" : portrait ? "52px" : "20px",
                fontWeight: "600",
                color: "rgba(255,255,255,0.8)",
                marginTop: compactBox ? "8px" : "15px",
                lineHeight: compactBox ? 1.1 : undefined,
              }}
            >
              {afterLabel}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
