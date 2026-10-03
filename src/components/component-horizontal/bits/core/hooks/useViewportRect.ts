// Vendored from remotion-bits @ de35fda84b7b6acbe549a0b302a82ef211e8ef1e: src/hooks/useViewportRect.ts
import { useMemo } from 'react';
import { useVideoConfig } from 'remotion';
import { createRect, Rect } from '../utils/geometry';

/**
 * Returns a Rect representing the current video composition's viewport.
 * Uses useVideoConfig() internally.
 */
export const useViewportRect = (): Rect => {
  const { width, height } = useVideoConfig();

  return useMemo(() => {
    return createRect(width, height);
  }, [width, height]);
};
