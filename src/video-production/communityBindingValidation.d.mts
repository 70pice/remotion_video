import type {TimelineShot} from './types';

export const communityProductionBindings: Readonly<Record<string, unknown>>;
export const boundCommunityComponentIds: readonly string[];
export function hasBoundCommunityComponent(componentId: string): boolean;
export function hasProductionCommunityProps(shot: TimelineShot): boolean;
export function validateCommunityBindingProps(shot: TimelineShot, name: string): void;
export function createCommunityBindingSpec(shot: TimelineShot): null | {
  component: string;
  props: Record<string, unknown>;
  holdFrame?: number;
  revealFrame?: number;
  badge?: string;
};
