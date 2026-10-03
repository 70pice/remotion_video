import {Composition, Folder} from 'remotion';
import {componentDemos as snapcn} from '../component-horizontal/snapcn/demo';
import {componentDemos as rve} from '../component-horizontal/rve/demo';
import {componentDemos as remocn} from '../component-horizontal/remocn/demo';
import {componentDemos as remotionUi} from '../component-horizontal/remotion-ui/demo';
import {componentDemos as bits} from '../component-horizontal/bits/demo';
import {componentDemos as talkcraft} from '../component-horizontal/video-talkcraft/demo';
import {nativeDemos as snapcnPortrait} from '../component-vertical/snapcn/demo';
import {nativeDemos as rvePortrait} from '../component-vertical/rve/demo';
import {nativeDemos as remocnPortrait} from '../component-vertical/remocn/demo';
import {nativeDemos as remotionUiPortrait} from '../component-vertical/remotion-ui/demo';
import {nativeDemos as bitsPortrait} from '../component-vertical/bits/demo';
import {nativeDemos as talkcraftA} from '../component-vertical/video-talkcraft/group-a';
import {nativeDemos as talkcraftB} from '../component-vertical/video-talkcraft/group-b';
import {nativeDemos as talkcraftC} from '../component-vertical/video-talkcraft/group-c';
import {nativeDemos as talkcraftD} from '../component-vertical/video-talkcraft/group-d';
import {verticalVideoFormat} from './portrait-format';

export const communityGroups = [
  {name: 'Snapcn', demos: snapcn},
  {name: 'RVE', demos: rve},
  {name: 'Remocn', demos: remocn},
  {name: 'RemotionUI', demos: remotionUi},
  {name: 'Bits', demos: bits},
  {name: 'Talkcraft', demos: talkcraft},
];

export const nativePortraitGroups = [
  {name: 'Snapcn', demos: snapcnPortrait},
  {name: 'RVE', demos: rvePortrait},
  {name: 'Remocn', demos: remocnPortrait},
  {name: 'RemotionUI', demos: remotionUiPortrait},
  {name: 'Bits', demos: bitsPortrait},
  {name: 'Talkcraft', demos: [...talkcraftA, ...talkcraftB, ...talkcraftC, ...talkcraftD]},
];

// Require one explicit native layout for every source demo. No landscape fallback.
for (const group of communityGroups) {
  const native = nativePortraitGroups.find((entry) => entry.name === group.name);
  const originalIds = new Set(group.demos.map((demo) => demo.id));
  if (!native || native.demos.length !== originalIds.size ||
    new Set(native.demos.map((demo) => demo.id)).size !== originalIds.size ||
    native.demos.some((demo) => !originalIds.has(demo.id))) {
    throw new Error(`Native portrait coverage differs from originals: ${group.name}`);
  }
}

export const CommunityRoot = () => <>
  <Folder name="component-horizontal">
    {communityGroups.map(({name, demos}) => <Folder key={name} name={name}>
      {demos.map((demo) => <Composition key={demo.id} id={demo.id}
        component={demo.component} width={demo.width} height={demo.height}
        fps={demo.fps} durationInFrames={demo.durationInFrames} />)}
    </Folder>)}
  </Folder>
  <Folder name="component-vertical">
    {nativePortraitGroups.map(({name, demos}) => <Folder key={name} name={name}>
      {demos.map((demo) => <Composition key={demo.id} id={`Vertical-${demo.id}`}
        component={demo.component} {...verticalVideoFormat}
        durationInFrames={demo.durationInFrames} />)}
    </Folder>)}
  </Folder>
</>;
