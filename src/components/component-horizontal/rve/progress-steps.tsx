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

import {useEffect, useState} from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig, cancelRender, continueRender, delayRender } from "remotion";

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
  slotWidth?: number;
  slotHeight?: number;
}

export default function ProgressSteps(props: ProgressStepsProps = {}) {
  const key = props.productionCompact ? JSON.stringify([props.steps, props.title, props.fontFamily,
    props.slotWidth, props.slotHeight, props.layout, props.compactBox]) : undefined;
  return <ProgressStepsContent key={key} {...props} />;
}

function ProgressStepsContent({
  steps = ["Research", "Design", "Build", "Launch"],
  title = "Project Timeline", secondsPerStep = 0.8, layout = "default", productionCompact = false, largeCopy = false, fontFamily, compactBox = false, compactSpacing = false, slotWidth, slotHeight,
}: ProgressStepsProps = {}) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const portrait = layout === "portrait";
  const compactPortrait = portrait && productionCompact;
  const slotCompact = compactPortrait && compactBox && slotWidth !== undefined && slotHeight !== undefined;
  const [handle] = useState(() => slotCompact ? delayRender("progress-steps: measuring production slot") : null);
  const [fit, setFit] = useState<{fontSize: number; heights: number[]; titleHeight: number} | null>(null);
  const [fitError, setFitError] = useState<string | null>(null);

  useEffect(() => {
    if (!slotCompact || handle === null || fit) return;
    let cancelled = false;
    const measure = async () => {
      await document.fonts.ready;
      if (cancelled) return;
      if (!Number.isFinite(slotWidth + slotHeight) || slotWidth <= 0 || slotHeight <= 0 || steps.length < 1 || steps.length > 4) {
        throw new Error("ProgressSteps production layout requires positive finite slot dimensions and one to four steps.");
      }
      if (slotWidth <= 2 + 36 + 44 + 16) {
        throw new Error(`ProgressSteps production slot ${Math.round(slotWidth)}x${Math.round(slotHeight)} cannot fit the step marker and readable labels. Increase this slot.`);
      }
      const probe = document.createElement("div");
      Object.assign(probe.style, {position: "fixed", left: "-10000px", top: "0", visibility: "hidden",
        fontFamily: fontFamily || "Inter, sans-serif", fontWeight: "600", lineHeight: "1.35",
        whiteSpace: "normal", textWrap: "balance"});
      document.body.append(probe);
      try {
        // 34px at a 1080px canvas is the minimum for these supporting labels.
        // Two lines per step keeps the list scannable on a phone.
        for (const size of [40, 38, 36, 34]) {
          probe.style.fontSize = `${size}px`;
          const read = (text: string, width: number, weight = "600") => {
            probe.style.width = `${width}px`;
            probe.style.fontWeight = weight;
            probe.textContent = text;
            const range = document.createRange();
            range.selectNodeContents(probe);
            const rects = Array.from(range.getClientRects());
            const box = probe.getBoundingClientRect();
            return {height: Math.max(box.height, range.getBoundingClientRect().height),
              fits: rects.length <= 2 && rects.every((rect) => rect.left >= box.left - 0.5 && rect.right <= box.right + 0.5)};
          };
          const labels = steps.map((text) => read(text, slotWidth - 2 - 36 - 44 - 16));
          const heading = title ? read(title, slotWidth - 2 - 36, "700") : {height: 0, fits: true};
          const heights = labels.map((label) => Math.max(44 * 1.05, label.height));
          const total = heights.reduce((sum, height) => sum + height, 0) + Math.max(0, steps.length - 1) * 8
            + (title ? heading.height + 8 : 0) + 16;
          if (heading.fits && labels.every((label) => label.fits) && total <= slotHeight - 2) {
            setFit({fontSize: size, heights, titleHeight: heading.height});
            return;
          }
        }
        throw new Error(`ProgressSteps production slot ${Math.round(slotWidth)}x${Math.round(slotHeight)} cannot fit ${steps.length} steps at 34px with at most two lines per step. Increase this slot or split the steps.`);
      } finally {
        probe.remove();
      }
    };
    measure().catch((error: Error) => {
      if (!cancelled) {setFitError(error.message); cancelRender(error);}
    });
    return () => {cancelled = true; continueRender(handle);};
  }, [slotCompact, handle, slotWidth, slotHeight, steps, title, fontFamily, fit]);

  useEffect(() => {if (fit && handle !== null) continueRender(handle);}, [fit, handle]);
  if (fitError) throw new Error(fitError);

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
        overflow: slotCompact ? "visible" : "hidden",
        boxSizing: slotCompact ? "border-box" : undefined,
        padding: slotCompact ? "8px 0" : undefined,
        visibility: slotCompact && !fit ? "hidden" : undefined,
        fontFamily: fontFamily || "Inter, sans-serif",
      }}
    >
      {(!slotCompact || title) && <h2
        style={{
          color: "white",
          fontSize: slotCompact ? fit?.fontSize : compactBox ? "2.4rem" : compactPortrait ? "3.2rem" : portrait ? "5.2rem" : "2rem",
          height: slotCompact ? fit?.titleHeight : undefined,
          width: slotCompact ? "calc(100% - 36px)" : undefined,
          textWrap: slotCompact ? "balance" : undefined,
          flexShrink: slotCompact ? 0 : undefined,
          lineHeight: slotCompact ? 1.35 : undefined,
          fontWeight: "bold",
          marginBottom: compactBox ? "18px" : compactPortrait ? "36px" : portrait ? "80px" : "60px",
          margin: 0,
          marginTop: 0,
          paddingBottom: slotCompact ? "8px" : compactBox ? "14px" : compactPortrait ? "28px" : "60px",
        }}
      >
        {title}
      </h2>}

      <div
        style={{
          display: "flex",
          flexDirection: portrait ? "column" : "row",
          alignItems: "center",
          justifyContent: "center",
          gap: "0px",
          position: "relative",
          width: compactBox ? "100%" : undefined,
          flexShrink: slotCompact ? 0 : undefined,
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

          const circleScale = slotCompact ? Math.min(1.05, isActive ? 0.9 + pulse * 0.2 : 1)
            : isActive ? 0.9 + pulse * 0.2 : isComplete ? 1.1 : 1;

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
                  padding: slotCompact ? "0 18px" : compactBox ? "0 26px" : undefined,
                  boxSizing: compactBox ? "border-box" : undefined,
                  height: slotCompact ? fit?.heights[i] : undefined,
                }}
              >
                <div
                  data-progress-step-circle={i}
                  style={{
                    width: slotCompact ? "44px" : compactBox ? compactSpacing ? "60px" : "68px" : compactPortrait ? "86px" : portrait ? "130px" : "48px",
                    height: slotCompact ? "44px" : compactBox ? compactSpacing ? "60px" : "68px" : compactPortrait ? "86px" : portrait ? "130px" : "48px",
                    boxSizing: slotCompact ? "border-box" : undefined,
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
                  data-progress-step-label={i}
                  style={{
                    color: largeCopy ? "white" : fillProgress > 0 ? "#93c5fd" : "#6b7280",
                    fontSize: slotCompact ? fit?.fontSize : compactBox ? "2.45rem" : largeCopy ? "3rem" : compactPortrait ? "2.1rem" : portrait ? "3rem" : "0.8rem",
                    lineHeight: slotCompact ? 1.35 : undefined,
                    fontWeight: slotCompact ? "600" : "500",
                    marginTop: compactPortrait ? 0 : "10px",
                    marginLeft: slotCompact ? "16px" : compactBox ? "22px" : compactPortrait ? "28px" : undefined,
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
                    height: slotCompact ? "8px" : compactBox ? compactSpacing ? "22px" : "52px" : compactPortrait ? "62px" : portrait ? "150px" : "3px",
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
