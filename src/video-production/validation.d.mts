import type {ProductionComponentId, Timeline} from './types';

export const productionComponentIds: readonly ProductionComponentId[];
export function validateMediaSource(source: unknown, jobId: string, name?: string): void;
export function validateTimeline(input: unknown): Timeline;
