import {Composition, registerRoot, useCurrentFrame} from 'remotion';
import capabilities from '../../../videoagents/component-set-capabilities.json';
import {ProductionComponentSetScene} from '../../../src/video-production/ProductionComponentSetScene';
import type {TimelineShot} from '../../../src/video-production/types';
import {WordFlip} from '../../../src/components/component-horizontal/snapcn/word-flip';

// Regression inputs only: no task state, media, provider, or production output.
const cases = {
  A02: {
    steps: {width: 456, height: 210},
    words: {width: 476, height: 210},
    items: ['两周观察窗：2026年4月', '至少25000名独立用户', '独立用户≠已证实受害人数'],
  },
  B12: {
    steps: {width: 476, height: 220},
    words: {width: 456, height: 220},
    items: ['中国匿名工作室', '用Claude开发20多款App', '目标用户在美国'],
  },
};

const Fixture = ({scenario, items, onlyNativeId, stepHeight, wordWidth, wordHeight, changedAtFrame, nextWordWidth, nextItems, standalone}: {
  scenario: keyof typeof cases; items?: string[]; onlyNativeId?: string; stepHeight?: number;
  wordWidth?: number; wordHeight?: number; changedAtFrame?: number; nextWordWidth?: number; nextItems?: string[];
  standalone?: boolean;
}) => {
  const frame = useCurrentFrame();
  if (standalone) return <div data-set-part="standalone" data-native-id="Snapcn-WordFlip"
    style={{position: 'absolute', width: 1080, height: 600}}><WordFlip /></div>;
  const input = cases[scenario];
  const changed = changedAtFrame !== undefined && frame >= changedAtFrame;
  const set = capabilities.sets.find((entry) => entry.set_id === scenario)!;
  const safe = capabilities.safe_area;
  const parts = set.parts.map((part) => {
    const selected = !onlyNativeId || part.component_id === onlyNativeId;
    const size = !selected ? null : part.component_id === 'Rve-ProgressSteps' ? {...input.steps, height: stepHeight ?? input.steps.height}
      : part.component_id === 'Snapcn-WordFlip' ? {...input.words,
        width: changed ? nextWordWidth ?? input.words.width : wordWidth ?? input.words.width,
        height: wordHeight ?? input.words.height} : null;
    return {
      part_id: part.part_id,
      // Only the two actual production adapters mount during measured frames.
      start_frame: size ? 0 : 300,
      end_frame: size ? 180 : 360,
      box: size ? {
        x: part.component_id === 'Rve-ProgressSteps' ? 0 : 0.5,
        y: 0,
        width: size.width / safe.width,
        height: size.height / safe.height,
      } : part.box,
    };
  });
  const shot = {
    shot_id: `text-fit-${scenario}`, start_frame: 0, end_frame: 360,
    component_id: set.main_component_id, title: '', body: '', asset_src: null,
    source_label: '', accent_color: '#38BDF8', props: {}, layers: [],
    set_design: {set_id: scenario, content: {takeaway: '', items: changed ? nextItems ?? input.items : items ?? input.items}, parts},
  } as TimelineShot;
  return <ProductionComponentSetScene shot={shot} />;
};

registerRoot(() => <Composition id="ProductionTextFit" component={Fixture}
  width={1080} height={1920} fps={30} durationInFrames={360}
  defaultProps={{scenario: 'A02'}} />);
