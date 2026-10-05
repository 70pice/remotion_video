import type {Caption, Shot, Timeline as ContractTimeline} from '../../contracts/generated/models';

export type ProductionComponentId = Shot['component_id'];

export {productionComponentIds} from './validation.mjs';

// Runtime checks live in validation.mjs; shape types come from Python's
// generated contract so web, backend and Remotion share a single definition.
export type TimelineCaption = Caption;
export type TimelineShot = Shot;
export type Timeline = ContractTimeline;

export type VideoMetadata = {width: number; height: number; duration: number};
export type TimelineVideoProps = {timeline: Timeline; videoMetadata?: Record<string, VideoMetadata>};

export type Highlight = {x: number; y: number; width: number; height: number};
export type DataItem = {label: string; value: string; detail?: string; reveal_frame?: number};
export type StepItem = {title: string; body?: string; reveal_frame?: number};
