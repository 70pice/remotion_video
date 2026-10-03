// Vendored from remotion-bits @ de35fda84b7b6acbe549a0b302a82ef211e8ef1e: docs/src/bits/examples/scene-3d/KenBurns.tsx
import React from "react";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { Scene3D, Step, StaggeredMotion, useViewportRect } from "../core";

export const metadata = {
  name: "Ken Burns Effect",
  description: "Slow camera movement over images using Scene3D steps",
  tags: ["scene-3d", "camera", "ken-burns", "motion"],
  duration: 300,
  width: 1920,
  height: 1080,
  registry: {
    name: "bit-ken-burns",
    title: "Ken Burns Effect",
    description: "Slow camera movement over images using Scene3D steps with Ken Burns effect.",
    type: "bit" as const,
    add: "when-needed" as const,
    registryDependencies: ["scene-3d"],
    dependencies: [],
    files: [
      {
        path: "docs/src/bits/examples/scene-3d/KenBurns.tsx",
      },
    ],
  },
};

export interface KenBurnsProps { images?: string[]; stepDuration?: number; transitionDuration?: number; layout?: "default" | "portrait"; }
export const Component: React.FC<KenBurnsProps> = ({ images = [staticFile("community/landscape.svg"), staticFile("community/landscape.svg"), staticFile("community/landscape.svg")], stepDuration = 100, transitionDuration = 60, layout = "default" }) => {
  const rect = useViewportRect();
  const portrait = layout === "portrait";
  const frameWidth = portrait ? rect.vw * 122 : rect.vmin * 177.78;
  const frameHeight = portrait ? rect.vh * 110 : rect.vmin * 100;
  const xShift = portrait ? rect.vw * 0.06 : rect.vmin * 4.63;
  const yShift = portrait ? rect.vh * 0.04 : rect.vmin * 5.56;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <Scene3D
        stepDuration={stepDuration}
        transitionDuration={transitionDuration}
      >
        <Step
          id="0"
          z={0}
          duration={stepDuration}
          transition={{ opacity: [0, 1] }}
          exitTransition={{ opacity: [1, 0] }}
        >
          <StaggeredMotion
            style={{ width: frameWidth, height: frameHeight }}
            transition={{
              scale: [1.1, 1.4],
              x: [0, xShift],
              duration: stepDuration,
            }}
          >
            <Img
              src={images[0]}
              style={{ width: frameWidth, height: frameHeight, objectFit: "cover" }}
            />
          </StaggeredMotion>
        </Step>

        <Step
          id="1"
          z={-10}
          duration={stepDuration}
          transition={{ opacity: [0, 1] }}
          exitTransition={{ opacity: [1, 0] }}
        >
          <StaggeredMotion
            style={{ width: frameWidth, height: frameHeight }}
            transition={{
              scale: [1.3, 1.1],
              x: [-xShift, 0],
              duration: stepDuration,
            }}
          >
            <Img
              src={images[1] ?? images[0]}
              style={{ width: frameWidth, height: frameHeight, objectFit: "cover" }}
            />
          </StaggeredMotion>
        </Step>

        <Step
          id="2"
          z={-20}
          duration={stepDuration}
          transition={{ opacity: [0, 1] }}
          exitTransition={{ opacity: [1, 0] }}
        >
          <StaggeredMotion
            style={{ width: frameWidth, height: frameHeight }}
            transition={{
              scale: [1.0, 1.2],
              y: [yShift, -yShift],
              duration: stepDuration,
            }}
          >
            <Img
              src={images[2] ?? images[0]}
              style={{ width: frameWidth, height: frameHeight, objectFit: "cover" }}
            />
          </StaggeredMotion>
        </Step>
      </Scene3D>
    </AbsoluteFill>
  );
};

export const KenBurns = Component;
