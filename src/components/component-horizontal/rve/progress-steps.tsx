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
}

export default function ProgressSteps({
  steps = ["Research", "Design", "Build", "Launch"],
  title = "Project Timeline", secondsPerStep = 0.8, layout = "default",
}: ProgressStepsProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";

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
        fontFamily: "Inter, sans-serif",
      }}
    >
      <h2
        style={{
          color: "white",
          fontSize: portrait ? "5.2rem" : "2rem",
          fontWeight: "bold",
          marginBottom: portrait ? "80px" : "60px",
          margin: 0,
          marginTop: 0,
          paddingBottom: "60px",
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
              style={{ display: "flex", flexDirection: portrait ? "column" : "row", alignItems: "center" }}
            >
              <div
                style={{
                  display: "flex",
                  flexDirection: portrait ? "row" : "column",
                  alignItems: "center",
                  width: portrait ? "280px" : "80px",
                }}
              >
                <div
                  style={{
                    width: portrait ? "130px" : "48px",
                    height: portrait ? "130px" : "48px",
                    borderRadius: "50%",
                    border: `3px solid ${fillProgress > 0 ? "#3b82f6" : "#4b5563"}`,
                    background:
                      fillProgress > 0
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
                      color: fillProgress > 0 ? "white" : "#6b7280",
                      fontSize: portrait ? "3.1rem" : "1rem",
                      fontWeight: "bold",
                    }}
                  >
                    {i + 1}
                  </span>
                </div>
                <span
                  style={{
                    color: fillProgress > 0 ? "#93c5fd" : "#6b7280",
                    fontSize: portrait ? "3rem" : "0.8rem",
                    fontWeight: "500",
                    marginTop: "10px",
                    whiteSpace: "nowrap",
                  }}
                >
                  {label}
                </span>
              </div>

              {i < steps.length - 1 && (
                <div
                  style={{
                    width: portrait ? "4px" : "80px",
                    height: portrait ? "150px" : "3px",
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
