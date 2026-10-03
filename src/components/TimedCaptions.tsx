import {useMemo} from 'react';
import type {Caption} from '@remotion/captions';
import {useCurrentFrame, useVideoConfig} from 'remotion';
import {captionPages} from './captionPages';

// Timing comes from real TTS word boundaries; this official utility groups it.
export const TimedCaptions = ({captions}: {captions: Caption[]}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const milliseconds = frame / fps * 1000;
  const pages = useMemo(() => captionPages(captions), [captions]);
  const page = pages.find(p => milliseconds >= p.startMs && milliseconds < p.startMs + p.durationMs);
  if (!page) return null;
  return (
    <div style={{position: 'absolute', top: 1480, left: 80, right: 80, minHeight: 150,
      display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center',
      padding: '25px 30px', background: '#fff', border: '2px solid #deded5', borderRadius: 22,
      color: '#182822', fontSize: 49, fontWeight: 700, lineHeight: 1.5}}>
      <div>{page.tokens.map((token, index) => (
        <span key={index} style={{color: milliseconds >= token.fromMs && milliseconds < token.toMs ? '#147458' : '#182822'}}>
          {token.text}
        </span>
      ))}</div>
    </div>
  );
};
