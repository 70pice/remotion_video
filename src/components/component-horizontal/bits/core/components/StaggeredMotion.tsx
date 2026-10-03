// Vendored from remotion-bits @ de35fda84b7b6acbe549a0b302a82ef211e8ef1e: src/components/StaggeredMotion.tsx
import React from "react";
import { random } from "remotion";
import {
  useMotionTiming,
  buildMotionStyles,
  getEasingFunction,
  type AnimatedValue,
  type TransformProps,
  type VisualProps,
  type TimingProps,
} from "../utils/motion";

export type { AnimatedValue };

export type StaggerDirection = "forward" | "reverse" | "center" | "random";

export type StaggeredMotionTransitionProps = TransformProps & VisualProps & TimingProps & {
  stagger?: number;
  staggerDirection?: StaggerDirection;
};

export type StaggeredMotionProps = {
  transition?: StaggeredMotionTransitionProps;
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
  cycleOffset?: number;
};

function calculateStaggerIndex(
  actualIndex: number,
  totalChildren: number,
  direction: StaggerDirection
): number {
  if (direction === "reverse") {
    return totalChildren - 1 - actualIndex;
  }

  if (direction === "center") {
    const mid = Math.floor(totalChildren / 2);
    return Math.abs(actualIndex - mid);
  }

  if (direction === "random") {
    const indices = Array.from({ length: totalChildren }, (_, i) => i);
    for (let i = indices.length - 1; i > 0; i--) {
      const j = Math.floor(random(`stagger-${i}`) * (i + 1));
      [indices[i], indices[j]] = [indices[j], indices[i]];
    }
    return indices.indexOf(actualIndex);
  }

  return actualIndex;
}

interface StaggeredChildProps {
  child: React.ReactNode;
  staggerIndex: number;
  transition?: StaggeredMotionTransitionProps;
  cycleOffset?: number;
}

const StaggeredChild: React.FC<StaggeredChildProps> = ({
  child,
  staggerIndex,
  // eslint-disable-next-line @remotion/non-pure-animation -- useMotionTiming reads useCurrentFrame(); this is not a CSS transition.
  transition,
  cycleOffset,
}) => {
  const {
    opacity,
    color,
    backgroundColor,
    blur,
    borderRadius,
    frames,
    duration,
    delay = 0,
    stagger = 0,
    easing,
  } = transition ?? {};

  const easingFn = getEasingFunction(easing);

    const resolvedDuration = duration ?? (frames ? frames[1] - frames[0] : 30);

    const progress = useMotionTiming({
      frames,
      duration,
      delay,
      stagger,
      unitIndex: staggerIndex,
      easing,
      cycleOffset: cycleOffset !== undefined ? cycleOffset - delay : undefined,
    });

    const motionStyle = buildMotionStyles({
      progress,
      transforms: transition,
      styles: { opacity, color, backgroundColor, blur, borderRadius },
      easing: easingFn,
      duration: resolvedDuration,
    });

    if (React.isValidElement<{style?: React.CSSProperties}>(child)) {
      const existingStyle = child.props.style ?? {};
      return React.cloneElement(child, {
        style: { ...existingStyle, ...motionStyle },
      });
    }

    return (
      <span style={motionStyle}>
        {child}
      </span>
    );
};

export const StaggeredMotion: React.FC<StaggeredMotionProps> = ({
  // eslint-disable-next-line @remotion/non-pure-animation -- Configuration forwarded to the frame-driven StaggeredChild.
  transition,
  children, className, style, cycleOffset,
}) => {
  const childArray = React.Children.toArray(children);
  const direction = transition?.staggerDirection ?? "forward";

  return (
    <div
      className={className}
      style={style}
    >
      {childArray.map((child, index) => (
        <StaggeredChild
          key={index}
          child={child}
          staggerIndex={calculateStaggerIndex(index, childArray.length, direction)}
          transition={transition}
          cycleOffset={cycleOffset}
        />
      ))}
    </div>
  );
};
