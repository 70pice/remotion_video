import {makeCuratedDemos} from '../../component-horizontal/curated/CuratedScene';
import {renderCompDefinitions} from '../../component-horizontal/rendercomp/demo';

export const nativeDemos = makeCuratedDemos(
  renderCompDefinitions,
  'portrait',
  {width: 1080, height: 1920},
);

export const nativeLayoutNotes: Record<string, string> = Object.fromEntries(
  renderCompDefinitions.map((item) => [item.id, 'Curated portrait version with 1080x1920 safe margins and material-slot overlay compatibility.']),
);
