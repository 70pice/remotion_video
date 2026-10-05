import type {Caption, Shot, Timeline as ContractTimeline} from '../../contracts/generated/models';

export type ProductionComponentId = Shot['component_id'];

export {productionComponentIds} from './validation.mjs';

// Runtime checks live in validation.mjs; shape types come from Python's
// generated contract so web, backend and Remotion share a single definition.
export type TimelineCaption = Caption;
export type TimelineShot = Shot;
export type Timeline = ContractTimeline;

export type TimelineVideoProps = {timeline: Timeline};

export type Highlight = {x: number; y: number; width: number; height: number};
export type DataItem = {label: string; value: string; detail?: string};
export type StepItem = {title: string; body?: string};
