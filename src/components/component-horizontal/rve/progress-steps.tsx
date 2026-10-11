// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/progress-steps.tsx. See licenses/community/rve/PROVENANCE.md.

/** Free Remotion Template Component
 * ---------------------------------
 * This template is free to use in your projects!
 * Credit appreciated but not required.
 *
 * Created by the team at https://www.reactvideoeditor.com
 *
 * Happy coding and building amazing videos! 🎉
 */

"use client";

import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";

export interface ProgressStepsProps {
  steps?: string[];
  title?: string;
  secondsPerStep?: number;
  layout?: "default" | "portrait";
  productionCompact?: boolean;
  largeCopy?: boolean;
  fontFamily?: string;
  compactBox?: boolean;
  compactSpacing?: boolean;
}

export default function ProgressSteps({
  steps = ["Research", "Design", "Build", "Launch"],
  title = "Project Timeline", secondsPerStep = 0.8, layout = "default", productionCompact = false, largeCopy = false, fontFamily, compactBox = false, compactSpacing = false,
}: ProgressStepsProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";
  const compactPortrait = portrait && productionCompact;

  const framesPerStep = Math.max(1, Math.floor(fps * secondsPerStep));

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "linear-gradient(180deg, #111827, #1f2937)",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
        fontFamily: fontFamily || "Inter, sans-serif",
      }}
    >
      <h2
        style={{
          color: "white",
          fontSize: compactBox ? "2.4rem" : compactPortrait ? "3.2rem" : portrait ? "5.2rem" : "2rem",
          fontWeight: "bold",
          marginBottom: compactBox ? "18px" : compactPortrait ? "36px" : portrait ? "80px" : "60px",
          margin: 0,
          marginTop: 0,
          paddingBottom: compactBox ? "14px" : compactPortrait ? "28px" : "60px",
        }}
      >
        {title}
      </h2>

      <div
        style={{
          display: "flex",
          flexDirection: portrait ? "column" : "row",
          alignItems: "center",
          justifyContent: "center",
          gap: "0px",
          position: "relative",
          width: compactBox ? "100%" : undefined,
        }}
      >
        {steps.map((label, i) => {
          const stepStart = i * framesPerStep;
          const fillProgress = interpolate(
            frame,
            [stepStart, stepStart + framesPerStep * 0.6],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );

          const isActive =
            frame >= stepStart && frame < stepStart + framesPerStep;
          const isComplete = frame >= stepStart + framesPerStep * 0.6;
          const highlighted = fillProgress > 0 || (compactBox && isActive);

          const pulse = isActive
            ? spring({
                frame: frame - stepStart,
                fps,
                config: { damping: 8, stiffness: 150, mass: 0.4 },
              })
            : 1;

          const circleScale = isActive ? 0.9 + pulse * 0.2 : isComplete ? 1.1 : 1;

          const lineProgress =
            i < steps.length - 1
              ? interpolate(
                  frame,
                  [stepStart + framesPerStep * 0.5, stepStart + framesPerStep],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                )
              : 0;

          return (
            <div
              key={i}
              style={{ display: "flex", flexDirection: portrait ? "column" : "row", alignItems: "center", width: compactBox ? "100%" : undefined }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: portrait ? "row" : "column",
                  alignItems: "center",
                  width: compactBox ? "100%" : compactPortrait ? "720px" : portrait ? "280px" : "80px",
                  padding: compactBox ? "0 26px" : undefined,
                  boxSizing: compactBox ? "border-box" : undefined,
                }}
              >
                <div
                  style={{
                    width: compactBox ? compactSpacing ? "60px" : "68px" : compactPortrait ? "86px" : portrait ? "130px" : "48px",
                    height: compactBox ? compactSpacing ? "60px" : "68px" : compactPortrait ? "86px" : portrait ? "130px" : "48px",
                    flexShrink: compactBox ? 0 : undefined,
                    borderRadius: "50%",
                    border: `3px solid ${highlighted ? "#3b82f6" : "#4b5563"}`,
                    background:
                      highlighted
                        ? `linear-gradient(135deg, #3b82f6, #7209b7)`
                        : "transparent",
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    transform: `scale(${circleScale})`,
                  }}
                >
                  <span
                    style={{
                      color: highlighted ? "white" : "#6b7280",
                      fontSize: compactBox ? "2rem" : largeCopy ? "2.5rem" : compactPortrait ? "2rem" : portrait ? "3.1rem" : "1rem",
                      fontWeight: "bold",
                    }}
                  >
                    {i + 1}
                  </span>
                </div>
                <span
                  style={{
                    color: largeCopy ? "white" : fillProgress > 0 ? "#93c5fd" : "#6b7280",
                    fontSize: compactBox ? "2.45rem" : largeCopy ? "3rem" : compactPortrait ? "2.1rem" : portrait ? "3rem" : "0.8rem",
                    fontWeight: "500",
                    marginTop: compactPortrait ? 0 : "10px",
                    marginLeft: compactBox ? "22px" : compactPortrait ? "28px" : undefined,
                    maxWidth: compactBox ? undefined : compactPortrait ? "590px" : undefined,
                    flex: compactBox ? 1 : undefined,
                    minWidth: compactBox ? 0 : undefined,
                    textWrap: compactBox ? "balance" : undefined,
                    whiteSpace: compactBox || compactPortrait ? "normal" : "nowrap",
                    textAlign: compactBox || compactPortrait ? "left" : undefined,
                  }}
                >
                  {label}
                </span>
              </div>

              {i < steps.length - 1 && (
                <div
                  style={{
                    width: portrait ? "4px" : "80px",
                    height: compactBox ? compactSpacing ? "22px" : "52px" : compactPortrait ? "62px" : portrait ? "150px" : "3px",
                    background: "#374151",
                    borderRadius: "2px",
                    position: "relative",
                    overflow: "hidden",
                    marginBottom: portrait ? "0" : "24px",
                  }}
                >
                  <div
                    style={{
                      width: portrait ? "100%" : `${lineProgress * 100}%`,
                      height: portrait ? `${lineProgress * 100}%` : "100%",
                      background: "linear-gradient(90deg, #3b82f6, #a855f7)",
                      borderRadius: "2px",
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
