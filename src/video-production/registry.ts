import type {ComponentType} from 'react';
import {ComparisonAdapter, ConclusionAdapter, DataAdapter, EvidenceAdapter, ImageFocusAdapter, KeywordAdapter, StepsAdapter, TitleAdapter} from './adapters';
import type {AdapterProps} from './adapters/layout';
import type {ProductionComponentId} from './types';

// Only reviewed parameter adapters can enter a job timeline. Community demos
// retain their own compositions and are never dynamically executed by ID.
export const productionRegistry: Record<ProductionComponentId, ComponentType<AdapterProps>> = {
  title: TitleAdapter,
  keyword: KeywordAdapter,
  evidence: EvidenceAdapter,
  image_focus: ImageFocusAdapter,
  comparison: ComparisonAdapter,
  data: DataAdapter,
  steps: StepsAdapter,
  conclusion: ConclusionAdapter,
};
