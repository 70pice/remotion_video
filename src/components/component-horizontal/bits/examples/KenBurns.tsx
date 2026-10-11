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

type Crop = {x: number; y: number; width: number; height: number};

export interface KenBurnsProps { images?: string[]; stepDuration?: number; transitionDuration?: number; layout?: "default" | "portrait"; fit?: "contain" | "cover"; crop?: Crop | null; }
export const Component: React.FC<KenBurnsProps> = ({ images = [staticFile("community/landscape.svg"), staticFile("community/landscape.svg"), staticFile("community/landscape.svg")], stepDuration = 100, transitionDuration = 60, layout = "default", fit = "cover", crop = null }) => {
  const rect = useViewportRect();
  const portrait = layout === "portrait";
  const frameWidth = portrait ? rect.vw * 122 : rect.vmin * 177.78;
  const frameHeight = portrait ? rect.vh * 110 : rect.vmin * 100;
  const xShift = portrait ? rect.vw * 0.06 : rect.vmin * 4.63;
  const yShift = portrait ? rect.vh * 0.04 : rect.vmin * 5.56;
  const uniqueImages = Array.from(new Set(images.filter(Boolean)));
  const singleImage = uniqueImages[0];
  const cropStyle = crop ? {
    position: "absolute" as const,
    left: `${-crop.x / crop.width * 100}%`,
    top: `${-crop.y / crop.height * 100}%`,
    width: `${100 / crop.width}%`,
    height: `${100 / crop.height}%`,
    objectFit: "fill" as const,
  } : {
    width: "100%",
    height: "100%",
    objectFit: fit,
  };
  const ImageFrame = ({src}: {src: string}) => <div style={{position: "relative", width: frameWidth, height: frameHeight, overflow: "hidden"}}>
    <Img src={src} style={{...cropStyle, display: "block"}} />
  </div>;

  if (uniqueImages.length === 1 && singleImage) {
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
            exitTransition={{ opacity: [1, 1] }}
          >
            <StaggeredMotion
              style={{ width: frameWidth, height: frameHeight }}
              transition={{
                scale: [1.08, 1.24],
                x: [0, xShift],
                y: [0, -yShift],
                duration: stepDuration,
              }}
            >
              <ImageFrame src={singleImage} />
            </StaggeredMotion>
          </Step>
        </Scene3D>
      </AbsoluteFill>
    );
  }

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
            <ImageFrame src={images[0]} />
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
            <ImageFrame src={images[1] ?? images[0]} />
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
            <ImageFrame src={images[2] ?? images[0]} />
          </StaggeredMotion>
        </Step>
      </Scene3D>
    </AbsoluteFill>
  );
};

export const KenBurns = Component;
