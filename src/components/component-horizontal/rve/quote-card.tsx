// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/quote-card.tsx. See licenses/community/rve/PROVENANCE.md.

"use client";

import { useCurrentFrame, interpolate } from "remotion";

export interface QuoteCardProps {
  quote?: string;
  attribution?: string;
  layout?: "default" | "portrait";
  productionCompact?: boolean;
  fontFamily?: string;
  transparentStage?: boolean;
  quoteFontSize?: number;
  instantReveal?: boolean;
  slotWidth?: number;
  slotHeight?: number;
}

export default function QuoteCard({
  quote = "Design is not just what it looks like. Design is how it works.",
  attribution = "— Steve Jobs",
  layout = "default",
  productionCompact = false,
  fontFamily,
  transparentStage = false,
  quoteFontSize,
  instantReveal = false,
  slotWidth,
  slotHeight,
}: QuoteCardProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";
  const compactPortrait = portrait && productionCompact;
  const slotCompact = compactPortrait && slotHeight !== undefined;
  const markSize = slotCompact ? Math.max(28, Math.min(58, slotHeight * 0.22)) : compactPortrait ? "6.2rem" : portrait ? "12rem" : "6rem";
  const textSize = quoteFontSize ?? (slotCompact ? Math.max(24, Math.min(44, slotHeight * 0.24, (slotWidth ?? 900) * 0.09)) : compactPortrait ? "2.7rem" : portrait ? "5.8rem" : "1.8rem");
  const slotPadding = slotCompact ? `${Math.max(10, slotHeight * 0.07)}px ${Math.max(18, (slotWidth ?? 500) * 0.06)}px` : undefined;

  const quoteMarkOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const textOpacity = interpolate(frame, [10, 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const attributionOpacity = interpolate(frame, [30, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const attributionX = interpolate(frame, [30, 45], [40, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: transparentStage ? "transparent" : "#111827",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: slotPadding ?? (transparentStage ? "2rem 3rem" : compactPortrait ? "5rem 5.2rem 8rem" : portrait ? "7rem 8rem 10rem 5rem" : "4rem"),
        overflow: "hidden",
        boxSizing: "border-box",
      }}
    >
      <span
        style={{
          color: "#3b82f6",
          fontSize: markSize,
          fontWeight: 700,
          lineHeight: 1,
          opacity: instantReveal ? 1 : quoteMarkOpacity,
          fontFamily: "Georgia, serif",
          marginBottom: slotCompact ? 0 : "1rem",
        }}
      >
        {"\u201C"}
      </span>
      <p
        style={{
          color: "white",
          fontSize: textSize,
          fontWeight: 400,
          lineHeight: slotCompact ? 1.18 : compactPortrait ? 1.32 : 1.6,
          textAlign: "center",
          maxWidth: compactPortrait ? "900px" : portrait ? "930px" : "700px",
          margin: 0,
          opacity: instantReveal ? 1 : textOpacity,
          fontFamily: fontFamily || "Georgia, serif",
          fontStyle: fontFamily ? "normal" : "italic",
        }}
      >
        {quote}
      </p>
      {(!transparentStage || attribution) && <p
        style={{
          color: "#9ca3af",
          fontSize: compactPortrait ? "1.75rem" : portrait ? "3rem" : "1.1rem",
          fontWeight: 500,
          margin: 0,
          marginTop: "2rem",
          opacity: attributionOpacity,
          transform: `translateX(${attributionX}px)`,
          fontFamily: "Inter, sans-serif",
        }}
      >
        {attribution}
      </p>}
    </div>
  );
}
