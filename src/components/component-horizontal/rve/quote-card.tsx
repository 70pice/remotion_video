// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/quote-card.tsx. See licenses/community/rve/PROVENANCE.md.

"use client";

import { useCurrentFrame, interpolate } from "remotion";

export interface QuoteCardProps {
  quote?: string;
  attribution?: string;
  layout?: "default" | "portrait";
}

export default function QuoteCard({
  quote = "Design is not just what it looks like. Design is how it works.",
  attribution = "— Steve Jobs",
  layout = "default",
}: QuoteCardProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";

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
        backgroundColor: "#111827",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        padding: portrait ? "7rem 8rem 10rem 5rem" : "4rem",
        overflow: "hidden",
      }}
    >
      <span
        style={{
          color: "#3b82f6",
          fontSize: portrait ? "12rem" : "6rem",
          fontWeight: 700,
          lineHeight: 1,
          opacity: quoteMarkOpacity,
          fontFamily: "Georgia, serif",
          marginBottom: "1rem",
        }}
      >
        {"\u201C"}
      </span>
      <p
        style={{
          color: "white",
          fontSize: portrait ? "5.8rem" : "1.8rem",
          fontWeight: 400,
          lineHeight: 1.6,
          textAlign: "center",
          maxWidth: portrait ? "930px" : "700px",
          margin: 0,
          opacity: textOpacity,
          fontFamily: "Georgia, serif",
          fontStyle: "italic",
        }}
      >
        {quote}
      </p>
      <p
        style={{
          color: "#9ca3af",
          fontSize: portrait ? "3rem" : "1.1rem",
          fontWeight: 500,
          margin: 0,
          marginTop: "2rem",
          opacity: attributionOpacity,
          transform: `translateX(${attributionX}px)`,
          fontFamily: "Inter, sans-serif",
        }}
      >
        {attribution}
      </p>
    </div>
  );
}
