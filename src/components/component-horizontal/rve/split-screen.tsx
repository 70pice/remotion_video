// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/split-screen.tsx. See licenses/community/rve/PROVENANCE.md.

"use client";

import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

export interface SplitScreenProps {
  leftTitle?: string;
  leftText?: string;
  rightTitle?: string;
  rightText?: string;
  layout?: "default" | "portrait";
  productionCompact?: boolean;
  largeCopy?: boolean;
  compactBox?: boolean;
}

export default function SplitScreen({
  leftTitle = "Panel A", leftText = "Left side content slides in from the left edge",
  rightTitle = "Panel B", rightText = "Right side content slides in from the right edge",
  layout = "default",
  productionCompact = false,
  largeCopy = false,
  compactBox = false,
}: SplitScreenProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";
  const compactPortrait = portrait && productionCompact;
  const slotCompact = compactBox || compactPortrait;
  const panelPadding = compactBox ? "18px 22px" : compactPortrait ? "3.2rem" : "2rem";
  const titleSize = compactBox ? (largeCopy ? "48px" : "44px") : largeCopy ? "4rem" : compactPortrait ? "3.2rem" : portrait ? "5rem" : "2.5rem";
  const bodySize = compactBox ? "34px" : largeCopy ? "3rem" : compactPortrait ? "1.55rem" : portrait ? "2.1rem" : "1rem";
  const bodyLineHeight = compactBox ? 1.22 : compactPortrait ? 1.35 : undefined;

  // Left panel slides in from left
  const leftSlide = spring({
    frame,
    fps,
    config: { damping: 15, stiffness: 80 },
  });

  // Right panel slides in from right with slight delay
  const rightSlide = spring({
    frame: frame - 5,
    fps,
    config: { damping: 15, stiffness: 80 },
  });

  const leftTranslateX = interpolate(leftSlide, [0, 1], [-100, 0]);
  const rightTranslateX = interpolate(rightSlide, [0, 1], [100, 0]);
  const leftTranslateY = interpolate(leftSlide, [0, 1], [-100, 0]);
  const rightTranslateY = interpolate(rightSlide, [0, 1], [100, 0]);

  // Divider fades in after panels meet
  const dividerOpacity = interpolate(frame, [fps * 0.6, fps * 0.9], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        backgroundColor: "#111827",
        overflow: "hidden",
        display: "flex",
        flexDirection: portrait ? "column" : "row",
      }}
    >
      {/* Left panel */}
      <div
        style={{
          width: portrait ? "100%" : "50%",
          height: portrait ? "50%" : "100%",
          transform: portrait ? `translateY(${leftTranslateY}%)` : `translateX(${leftTranslateX}%)`,
          background: "linear-gradient(135deg, #1e3a5f, #1d4ed8)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: panelPadding,
        }}
      >
        <h2
          style={{
            color: "white",
            fontSize: titleSize,
            fontWeight: "bold",
            margin: 0,
            lineHeight: compactBox ? 1.06 : undefined,
            maxWidth: "100%",
            textAlign: "center",
            overflowWrap: "anywhere",
          }}
        >
          {leftTitle}
        </h2>
        <p
          style={{
            color: "#bfdbfe",
            fontSize: bodySize,
            marginTop: compactBox ? "10px" : "0.75rem",
            textAlign: "center",
            lineHeight: bodyLineHeight,
            maxWidth: "100%",
            overflowWrap: "anywhere",
          }}
        >
          {leftText}
        </p>
      </div>

      {/* Right panel */}
      <div
        style={{
          width: portrait ? "100%" : "50%",
          height: portrait ? "50%" : "100%",
          transform: portrait ? `translateY(${rightTranslateY}%)` : `translateX(${rightTranslateX}%)`,
          background: "linear-gradient(135deg, #5b21b6, #7c3aed)",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: panelPadding,
        }}
      >
        <h2
          style={{
            color: "white",
            fontSize: titleSize,
            fontWeight: "bold",
            margin: 0,
            lineHeight: compactBox ? 1.06 : undefined,
            maxWidth: "100%",
            textAlign: "center",
            overflowWrap: "anywhere",
          }}
        >
          {rightTitle}
        </h2>
        <p
          style={{
            color: "#ddd6fe",
            fontSize: bodySize,
            marginTop: compactBox ? "10px" : "0.75rem",
            textAlign: "center",
            lineHeight: bodyLineHeight,
            maxWidth: "100%",
            overflowWrap: "anywhere",
          }}
        >
          {rightText}
        </p>
      </div>

      {/* Center divider */}
      <div
        style={{
          position: "absolute",
          top: portrait ? "50%" : "10%",
          bottom: portrait ? undefined : "10%",
          left: portrait ? "10%" : "50%",
          right: portrait ? "10%" : undefined,
          transform: portrait ? "translateY(-50%)" : "translateX(-50%)",
          width: portrait ? undefined : "2px",
          height: portrait ? "2px" : undefined,
          background: "linear-gradient(180deg, transparent, rgba(255,255,255,0.8), transparent)",
          opacity: slotCompact ? Math.max(0.55, dividerOpacity) : dividerOpacity,
        }}
      />
    </div>
  );
}
