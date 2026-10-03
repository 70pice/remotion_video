// Vendored from remotion-bits @ de35fda84b7b6acbe549a0b302a82ef211e8ef1e: docs/src/bits/examples/scene-3d/CursorFlyover.tsx
import React from "react";
import { Img, staticFile } from "remotion";
import {
  Scene3D,
  Step,
  Element3D,
  StepResponsive,
  useViewportRect,
  createRect,
  resolvePoint,
} from "../core";

export const metadata = {
  name: "Cursor Flyover",
  description: "Camera flies over an app screenshot while a cursor highlights different areas",
  tags: ["3d", "camera", "cursor", "screenshot", "presentation"],
  duration: 300,
  width: 1920,
  height: 1080,
  registry: {
    name: "bit-cursor-flyover",
    title: "Cursor Flyover",
    description: "Camera flies over an app screenshot while a cursor highlights different areas",
    type: "bit" as const,
    add: "when-needed" as const,
    registryDependencies: ["scene-3d", "use-viewport-rect", "geometry"],
    dependencies: [],
    files: [
      {
        path: "docs/src/bits/examples/scene-3d/CursorFlyover.tsx",
      },
    ],
  },
};

export interface CursorFlyoverProps { src?: string; layout?: "default" | "portrait"; }
export const Component: React.FC<CursorFlyoverProps> = ({ src = staticFile("community/ai-ui.svg"), layout = "default" }) => {
  const rect = useViewportRect();
  const portrait = layout === "portrait";

  const imgWidth = portrait ? rect.vw * 72 : rect.vmin * 120;
  const imgHeight = portrait ? rect.vh * 56 : imgWidth * (720 / 1280);
  const imgRect = createRect(imgWidth, imgHeight, -imgWidth / 2, -imgHeight / 2);
  const zoom = imgWidth * (portrait ? 0.55 : 0.2);
  const corner = (anchor: Parameters<typeof resolvePoint>[1]) => resolvePoint(imgRect, anchor);
  const cameraPoint = (anchor: Parameters<typeof resolvePoint>[1]) => {
    const point = corner(anchor);
    return portrait ? { x: 0, y: point.y * 0.55 } : point;
  };

  const Cursor: React.FC<{ size: number }> = ({ size }) => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{
        position: "absolute",
          top: 0,
        filter: "drop-shadow(2px 4px 6px rgba(0,0,0,0.5))",
      }}
    >
      <path d="M4.037 4.688a.495.495 0 0 1 .651-.651l16 6.5a.5.5 0 0 1-.063.947l-6.124 1.58a2 2 0 0 0-1.438 1.435l-1.579 6.126a.5.5 0 0 1-.947.063z" />
    </svg>
  );

  return (
    <Scene3D
      perspective={portrait ? 2400 : 1200}
      transitionDuration={portrait ? 60 : 45}
      stepDuration={portrait ? 60 : 45}
      easing="easeInOutCubic"
      style={{ background: "#0a0a0a" }}
    >
      <Element3D x={-imgWidth / 2} y={-imgHeight / 2} z={0}>
        {portrait ? (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width={imgWidth}
            height={imgHeight}
            viewBox="0 0 720 1100"
            style={{
              display: "block",
              borderRadius: rect.vmin * 1.5,
              boxShadow: `0 ${rect.vmin * 2}px ${rect.vmin * 6}px rgba(0,0,0,0.6)`,
            }}
          >
            <rect width="720" height="1100" rx="28" fill="#101827" />
            <rect width="720" height="70" rx="28" fill="#1f2937" />
            <circle cx="38" cy="35" r="9" fill="#ef4444" />
            <circle cx="66" cy="35" r="9" fill="#fbbf24" />
            <circle cx="94" cy="35" r="9" fill="#34d399" />
            <text x="124" y="44" fill="#cbd5e1" fontFamily="Arial, sans-serif" fontSize="25">AI Assistant</text>
            <text x="56" y="170" fill="#f8fafc" fontFamily="Arial, sans-serif" fontSize="48" fontWeight="700">How does an</text>
            <text x="56" y="228" fill="#f8fafc" fontFamily="Arial, sans-serif" fontSize="48" fontWeight="700">AI agent work?</text>
            <rect x="52" y="286" width="616" height="128" rx="26" fill="#334155" />
            <text x="82" y="342" fill="#f8fafc" fontFamily="Arial, sans-serif" fontSize="31">Explain the process</text>
            <text x="82" y="382" fill="#f8fafc" fontFamily="Arial, sans-serif" fontSize="31">with a simple example.</text>
            <text x="70" y="502" fill="#34d399" fontFamily="Arial, sans-serif" fontSize="34" fontWeight="700">1. Understand the goal</text>
            <text x="70" y="582" fill="#93c5fd" fontFamily="Arial, sans-serif" fontSize="34" fontWeight="700">2. Choose a tool</text>
            <text x="70" y="662" fill="#c4b5fd" fontFamily="Arial, sans-serif" fontSize="34" fontWeight="700">3. Check the result</text>
            <rect x="52" y="880" width="616" height="112" rx="28" fill="#1f2937" stroke="#475569" strokeWidth="3" />
            <text x="82" y="948" fill="#94a3b8" fontFamily="Arial, sans-serif" fontSize="30">Ask a follow-up...</text>
            <circle cx="614" cy="936" r="34" fill="#34d399" />
            <path d="M598 942l16-18 16 18M614 925v31" stroke="#101827" fill="none" strokeWidth="5" />
          </svg>
        ) : (
          <Img
            src={src}
            style={{
              width: imgWidth,
              height: imgHeight,
              objectFit: "cover",
              borderRadius: rect.vmin * 1.5,
              boxShadow: `0 ${rect.vmin * 2}px ${rect.vmin * 6}px rgba(0,0,0,0.6)`,
            }}
          />
        )}
      </Element3D>

      <Step id="overview" x={0} y={0} z={imgWidth * (portrait ? 1.1 : 0.5)} transition={{ opacity: [0, 1] }} />
      <Step id="top-left" {...cameraPoint("topLeft")} z={zoom} />
      <Step id="top-right" {...cameraPoint("topRight")} z={zoom} />
      <Step id="bottom-left" {...cameraPoint("bottomLeft")} z={zoom} />
      <Step id="bottom-right" {...cameraPoint("bottomRight")} z={zoom} />
      <Step id="zoom-out" x={0} y={0} z={imgWidth * (portrait ? 1.2 : 0.6)} exitTransition={{ opacity: [1, 0] }} />

      <StepResponsive
        steps={{
          "overview": { ...corner("center"), opacity: 0, scale: 1.0 },
          "top-left": { ...corner("topLeft"), opacity: 1, scale: [1, 2.0, 1] },
          "top-right": { ...corner("topRight"), opacity: 1, scale: 1 },
          "bottom-left": { ...corner("bottomLeft"), opacity: 1, scale: [1, 2.0, 1] },
          "bottom-right": { ...corner("bottomRight"), opacity: 1, scale: 1 },
          "zoom-out": { ...corner("center"), opacity: 0, scale: 0.5 },
        }}
        transition={{
          duration: 35,
          easing: "easeInOutCubic",
        }}
      >
        <Element3D z={1}>
          <Cursor size={rect.vmin * 5} />
        </Element3D>
      </StepResponsive>
    </Scene3D>
  );
};

export const CursorFlyover = Component;
