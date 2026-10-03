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
}

export default function SplitScreen({
  leftTitle = "Panel A", leftText = "Left side content slides in from the left edge",
  rightTitle = "Panel B", rightText = "Right side content slides in from the right edge",
  layout = "default",
}: SplitScreenProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";

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
          padding: "2rem",
        }}
      >
        <h2
          style={{
            color: "white",
            fontSize: portrait ? "5rem" : "2.5rem",
            fontWeight: "bold",
            margin: 0,
          }}
        >
          {leftTitle}
        </h2>
        <p
          style={{
            color: "#bfdbfe",
            fontSize: portrait ? "2.1rem" : "1rem",
            marginTop: "0.75rem",
            textAlign: "center",
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
          padding: "2rem",
        }}
      >
        <h2
          style={{
            color: "white",
            fontSize: portrait ? "5rem" : "2.5rem",
            fontWeight: "bold",
            margin: 0,
          }}
        >
          {rightTitle}
        </h2>
        <p
          style={{
            color: "#ddd6fe",
            fontSize: portrait ? "2.1rem" : "1rem",
            marginTop: "0.75rem",
            textAlign: "center",
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
          opacity: dividerOpacity,
        }}
      />
    </div>
  );
}
