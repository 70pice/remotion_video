import {useLayoutEffect, useRef, useState, type ReactNode} from 'react';
import {createPortal} from 'react-dom';
import {continueRender, delayRender} from 'remotion';

// Original Talkcraft cards include global resets and repeated CSS class names.
// Portals preserve Remotion context while a ShadowRoot keeps those styles local.
export const IsolatedCard = ({children}: {children: ReactNode}) => {
  const host = useRef<HTMLDivElement>(null);
  const [shadow, setShadow] = useState<ShadowRoot | null>(null);
  const [handle] = useState(() => delayRender('Attach original card style isolation'));
  useLayoutEffect(() => {
    const element = host.current;
    if (!element) return;
    setShadow(element.shadowRoot ?? element.attachShadow({mode: 'open'}));
  }, []);
  useLayoutEffect(() => {
    if (shadow) continueRender(handle);
  }, [handle, shadow]);
  return <div ref={host} style={{width: '100%', height: '100%', position: 'relative'}}>
    {shadow ? createPortal(children, shadow) : null}
  </div>;
};
