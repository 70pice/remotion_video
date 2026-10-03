// Adapted from reactvideoeditor/remotion-templates at 6209b724798e48ff395f8df1a6fa2d26082372b5.
// Upstream path: templates/progress-bars.tsx. See licenses/community/rve/PROVENANCE.md.

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

export interface SkillMetric { label: string; value: number; color: string; }

const defaultSkills: SkillMetric[] = [
    { label: "React", value: 90, color: "#4361ee" },
    { label: "TypeScript", value: 85, color: "#7209b7" },
    { label: "Node.js", value: 75, color: "#f72585" },
    { label: "Python", value: 60, color: "#4cc9f0" },
    { label: "Go", value: 45, color: "#a855f7" },
  ];

export interface ProgressBarsProps {
  skills?: SkillMetric[];
  title?: string;
  layout?: "default" | "portrait";
}

export default function ProgressBars({ skills = defaultSkills, title = "Skills Overview", layout = "default" }: ProgressBarsProps = {}) {
  const frame = useCurrentFrame();
  const portrait = layout === "portrait";



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
        background: "linear-gradient(to bottom right, #111827, #1f2937)",
      }}
    >
      <div
        style={{
          position: "relative",
          width: portrait ? "960px" : "700px",
          backgroundColor: "rgba(0, 0, 0, 0.2)",
          borderRadius: "16px",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.3)",
          padding: portrait ? "96px 72px" : "40px 50px",
        }}
      >
        {/* Title */}
        <div
          style={{
            fontSize: portrait ? "76px" : "28px",
            fontWeight: "bold",
            color: "white",
            textShadow: "0 2px 4px rgba(0,0,0,0.3)",
            letterSpacing: "-0.5px",
            marginBottom: "35px",
            textAlign: "center",
          }}
        >
          {title}
        </div>

        {/* Bars */}
        {skills.map((skill, i) => {
          const barProgress = interpolate(
            frame,
            [5 + i * 8, 25 + i * 8],
            [0, skill.value],
            { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
          );

          const labelOpacity = interpolate(
            frame,
            [i * 8, 5 + i * 8],
            [0, 1],
            { extrapolateRight: "clamp", extrapolateLeft: "clamp" }
          );

          return (
            <div
              key={`skill-${i}`}
              style={{
                marginBottom: i < skills.length - 1 ? (portrait ? "64px" : "22px") : "0",
                opacity: labelOpacity,
              }}
            >
              {/* Label row */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span
                  style={{
                    color: "white",
                    fontSize: portrait ? "50px" : "16px",
                    fontWeight: "600",
                  }}
                >
                  {skill.label}
                </span>
                <span
                  style={{
                    color: "rgba(255,255,255,0.8)",
                    fontSize: portrait ? "50px" : "16px",
                    fontWeight: "500",
                  }}
                >
                  {Math.round(barProgress)}%
                </span>
              </div>

              {/* Bar track */}
              <div
                style={{
                  width: "100%",
                  height: portrait ? "46px" : "14px",
                  backgroundColor: "rgba(255,255,255,0.1)",
                  borderRadius: "7px",
                  overflow: "hidden",
                }}
              >
                {/* Bar fill */}
                <div
                  style={{
                    width: `${barProgress}%`,
                    height: "100%",
                    backgroundColor: skill.color,
                    borderRadius: "7px",
                    boxShadow: `0 0 10px ${skill.color}40`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
