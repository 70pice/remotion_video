import type {ComponentType} from 'react';
import {communityGroups, nativePortraitGroups} from '../components/community/CommunityRoot';
import {
  ComparisonAdapter,
  ConclusionAdapter,
  DataAdapter,
  EvidenceAdapter,
  ImageFocusAdapter,
  KeywordAdapter,
  StepsAdapter,
  TitleAdapter,
  VideoAdapter,
} from './adapters';
import type {AdapterProps} from './adapters/layout';
import {communityComponentIds} from './validation.mjs';

export const semanticProductionRegistry: Record<string, ComponentType<AdapterProps>> = {
  title: TitleAdapter,
  keyword: KeywordAdapter,
  evidence: EvidenceAdapter,
  image_focus: ImageFocusAdapter,
  comparison: ComparisonAdapter,
  data: DataAdapter,
  steps: StepsAdapter,
  conclusion: ConclusionAdapter,
  video: VideoAdapter,
};

export type CommunityPreset = {
  id: string;
  component: ComponentType;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
};

const collect = (groups: typeof communityGroups | typeof nativePortraitGroups) => {
  const result = new Map<string, CommunityPreset>();
  for (const group of groups) {
    for (const raw of group.demos) {
      const demo = raw as CommunityPreset;
      if (result.has(demo.id)) throw new Error(`Duplicate community component: ${demo.id}`);
      result.set(demo.id, demo);
    }
  }
  return result;
};

const horizontalPresets = collect(communityGroups);
const verticalPresets = collect(nativePortraitGroups);
const expected = new Set(communityComponentIds);
if (
  expected.size !== 152 ||
  horizontalPresets.size !== expected.size ||
  verticalPresets.size !== expected.size ||
  [...expected].some((id) => !horizontalPresets.has(id) || !verticalPresets.has(id))
) {
  throw new Error('Production preset registry must cover all 152 horizontal/vertical component pairs');
}

export const isSemanticComponent = (componentId: string) => componentId in semanticProductionRegistry;

export const resolveCommunityPreset = (componentId: string, portrait: boolean): CommunityPreset => {
  const preset = (portrait ? verticalPresets : horizontalPresets).get(componentId);
  if (!preset) throw new Error(`Unknown production preset: ${componentId}`);
  return preset;
};
