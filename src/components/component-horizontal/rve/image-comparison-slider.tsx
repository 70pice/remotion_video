// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/image-comparison-slider.tsx. See licenses/community/rve/PROVENANCE.md.

"use client";

import { Img, staticFile, useCurrentFrame, interpolate, useVideoConfig } from "remotion";

export interface ImageComparisonSliderProps {
  beforeSrc?: string;
  afterSrc?: string;
  beforeLabel?: string;
  afterLabel?: string;
  layout?: "default" | "portrait";
}

export default function ImageComparisonSlider({
  beforeSrc = staticFile("community/landscape.svg"),
  afterSrc = staticFile("community/ai-ui.svg"),
  beforeLabel = "Before", afterLabel = "After", layout = "default",
}: ImageComparisonSliderProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";

  const duration = fps * 3;
  const dividerPercent = interpolate(frame, [10, duration], [5, 95], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#111827",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: portrait ? "92%" : "85%",
          height: portrait ? "86%" : "75%",
          borderRadius: portrait ? "34px" : "12px",
          overflow: "hidden",
          position: "relative",
        }}
      >
        {/* After (full background) */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(135deg, #4361ee, #7209b7, #a855f7)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <Img src={afterSrc} style={{position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover"}} />
          <span
            style={{
              color: "white",
              fontSize: portrait ? "5rem" : "1.5rem",
              fontWeight: 600,
              fontFamily: "Inter, sans-serif",
              opacity: 0.8,
              position: "relative",
              textShadow: "0 2px 8px #000",
            }}
          >
            {afterLabel}
          </span>
        </div>
        {/* Before (clipped) */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            clipPath: `inset(0 ${100 - dividerPercent}% 0 0)`,
            background: "linear-gradient(135deg, #1e293b, #374151, #4b5563)",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
          }}
        >
          <Img src={beforeSrc} style={{position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover"}} />
          <span
            style={{
              color: "#ffffff",
              position: "relative",
              textShadow: "0 2px 8px #000",
              fontSize: portrait ? "5rem" : "1.5rem",
              fontWeight: 600,
              fontFamily: "Inter, sans-serif",
            }}
          >
            {beforeLabel}
          </span>
        </div>
        {/* Divider */}
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: `${dividerPercent}%`,
            width: portrait ? "6px" : "3px",
            backgroundColor: "white",
            zIndex: 2,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: portrait ? "70px" : "28px",
              height: portrait ? "70px" : "28px",
              borderRadius: "50%",
              backgroundColor: "white",
              border: "3px solid #3b82f6",
            }}
          />
        </div>
      </div>
    </div>
  );
}
