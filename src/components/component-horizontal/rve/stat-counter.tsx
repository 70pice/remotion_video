// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/stat-counter.tsx. See licenses/community/rve/PROVENANCE.md.

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

import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface StatCounterProps {
  value?: number;
  label?: string;
  change?: string;
  period?: string;
  suffix?: string;
  prefix?: string;
  layout?: "default" | "portrait";
  productionCompact?: boolean;
  compactBox?: boolean;
  fontFamily?: string;
  accentColor?: string;
  slotWidth?: number;
  slotHeight?: number;
}

export default function StatCounter({
  value = 1247, label = "Total Users", change = "↑ 12.5%",
  period = "This Month", suffix = "", prefix = "", layout = "default", productionCompact = false, compactBox = false, fontFamily, accentColor = "#22c55e", slotWidth, slotHeight,
}: StatCounterProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";
  const compactPortrait = portrait && productionCompact;
  const slotCompact = compactBox && slotHeight !== undefined;
  const valueFont = slotCompact ? Math.max(44, Math.min(82, slotHeight * 0.34, (slotWidth ?? 500) * 0.18)) : compactBox ? "88px" : compactPortrait ? "132px" : portrait ? "220px" : "96px";
  const labelFont = slotCompact ? Math.max(22, Math.min(34, slotHeight * 0.15)) : compactBox ? "40px" : compactPortrait ? "42px" : portrait ? "64px" : "24px";
  const detailFont = slotCompact ? Math.max(20, Math.min(28, slotHeight * 0.13)) : compactBox ? "34px" : compactPortrait ? "30px" : portrait ? "46px" : "18px";
  const compactPadding = slotCompact ? `${Math.max(10, slotHeight * 0.07)}px ${Math.max(14, (slotWidth ?? 500) * 0.05)}px` : undefined;

  // Spring entrance
  const scaleSpring = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 100 },
  });

  // Count up animation
  const count = Math.round(
    interpolate(frame, [10, 60], [0, value], {
      extrapolateRight: "clamp",
      extrapolateLeft: "clamp",
    })
  );

  const subStatsOpacity = interpolate(frame, [40, 55], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
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
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
          padding: compactPadding ?? (compactBox ? "24px 28px" : compactPortrait ? "92px 82px" : portrait ? "140px 100px" : "60px 80px"),
          textAlign: "center",
          transform: `scale(${scaleSpring})`,
          maxWidth: compactBox ? "100%" : undefined,
          boxSizing: compactBox ? "border-box" : undefined,
        }}
      >
        {/* Main number */}
        <div
          style={{
            fontSize: valueFont,
            fontWeight: "bold",
            color: "white",
            textShadow: "0 4px 8px rgba(0,0,0,0.3)",
            letterSpacing: compactBox ? "0" : "-2px",
            lineHeight: "1",
          }}
        >
          {prefix}{count.toLocaleString("en-US")}{suffix}
        </div>

        {/* Label */}
        <div
          style={{
            fontSize: labelFont,
            color: "rgba(255,255,255,0.7)",
            marginTop: slotCompact ? "8px" : "12px",
            fontWeight: "500",
            letterSpacing: "1px",
            textWrap: compactBox ? "balance" : undefined,
            lineHeight: compactBox ? 1.12 : undefined,
          }}
        >
          {label}
        </div>

        {(!compactBox || change || period) ? <div
          style={{
            display: "flex",
            justifyContent: "center",
              gap: compactBox ? "18px" : compactPortrait ? "26px" : portrait ? "42px" : "30px",
            marginTop: slotCompact ? "10px" : compactBox ? "18px" : "30px",
            opacity: subStatsOpacity,
            flexWrap: compactBox ? "wrap" : undefined,
          }}
        >
          {(!compactBox || change) ? <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span
              style={{
                color: accentColor,
                fontSize: detailFont,
                fontWeight: "600",
              }}
            >
              {change}
            </span>
          </div> : null}
          {(!compactBox || period) ? <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span
              style={{
                color: "rgba(255,255,255,0.5)",
                fontSize: detailFont,
                fontWeight: "400",
                textWrap: compactBox ? "balance" : undefined,
                lineHeight: compactBox ? 1.12 : undefined,
              }}
            >
              {period}
            </span>
          </div> : null}
        </div> : null}
      </div>
    </div>
  );
}
