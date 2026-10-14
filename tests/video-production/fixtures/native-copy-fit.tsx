import {Component, type ReactNode} from 'react';
import {Composition, registerRoot} from 'remotion';
import {DataAdapter} from '../../../src/video-production/adapters';
import {TalkcraftNativeTitle} from '../../../src/video-production/TalkcraftNativeTitles';
import type {TimelineShot} from '../../../src/video-production/types';

type FixtureProps = {
  scenario: 'data' | 'keyword';
  values?: string[];
  title?: string;
  body?: string;
  keyword?: string;
};

// Test inputs only; mount real adapters without task state, media or providers.
class Boundary extends Component<{children: ReactNode}, {error: string | null}> {
  state: {error: string | null} = {error: null};
  static getDerivedStateFromError(error: Error) {
    return {error: error.message};
  }
  render() {
    return this.state.error ? <div role="alert">{this.state.error}</div> : this.props.children;
  }
}

const Fixture = ({scenario, values, title, body = '', keyword}: FixtureProps) => {
  const shot: TimelineShot = {
    shot_id: 'native-copy-fit-test', start_frame: 0, end_frame: 180,
    component_id: scenario === 'data' ? 'data' : 'Talkcraft-keyword-pop-highlight',
    title: title ?? (scenario === 'data' ? '观察数据' : '同一个Claude'), body,
    asset_src: null, source_label: '', accent_color: '#38BDF8', layers: [],
    props: scenario === 'data' ? {
      items: (values ?? ['2026年4月·两周', '至少25000人', '4700+个', '约236万条'])
        .map((value, index) => ({label: `观察项${index + 1}`, value})),
    } : {items: [keyword ?? '同一个Claude']},
  };
  return <Boundary>
    {scenario === 'data' ? <div data-copy-fit="data" style={{position: 'absolute', top: 180, left: 72, right: 72}}>
      <DataAdapter shot={shot} durationInFrames={180} />
    </div> : <TalkcraftNativeTitle shot={shot} layerRole="emphasis" />}
  </Boundary>;
};

registerRoot(() => <Composition id="NativeCopyFit" component={Fixture}
  width={1080} height={1920} fps={30} durationInFrames={180}
  defaultProps={{scenario: 'data'}} />);
