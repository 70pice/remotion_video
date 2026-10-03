import type {FC} from 'react';
import {AbsoluteFill} from 'remotion';
import {ChatConversation} from '../../component-horizontal/bits/examples/ChatConversation';
import {StatRings} from '../../component-horizontal/bits/examples/StatRings';
import {CursorFlyover} from '../../component-horizontal/bits/examples/CursorFlyover';
import {KenBurns} from '../../component-horizontal/bits/examples/KenBurns';

type Demo = {id: string; name: string; slug: string; component: FC; width: 1080; height: 1920; durationInFrames: number; fps: 30};

export const ChatConversationPortrait: FC = () => <ChatConversation messages={[
  {from: 'them', text: 'RAG 和普通聊天有什么区别？'},
  {from: 'me', text: 'RAG 会先查找相关资料。'},
  {from: 'them', text: '找到资料以后呢？'},
  {from: 'me', text: '把资料放进模型的上下文。'},
  {from: 'me', text: '然后结合资料组织答案。'},
  {from: 'them', text: '懂了，这是流程示意。'},
]} />;

export const StatRingsPortrait: FC = () => <AbsoluteFill>
  <StatRings layout="portrait" stats={[
    {label: '资料覆盖', value: 72, toFixed: 0},
    {label: '脚本清晰度', value: 56, toFixed: 0},
    {label: '发布完成', value: 38, toFixed: 0},
  ]} />
</AbsoluteFill>;

export const CursorFlyoverPortrait: FC = () => <CursorFlyover layout="portrait" />;
export const KenBurnsPortrait: FC = () => <KenBurns layout="portrait" stepDuration={60} transitionDuration={30} />;

export const nativeDemos: Demo[] = [
  {id: 'Bits-ChatConversation', name: 'Chat Conversation', slug: 'bits-chat-conversation', component: ChatConversationPortrait, width: 1080, height: 1920, durationInFrames: 180, fps: 30},
  {id: 'Bits-StatRings', name: 'Stat Rings', slug: 'bits-stat-rings', component: StatRingsPortrait, width: 1080, height: 1920, durationInFrames: 150, fps: 30},
  {id: 'Bits-CursorFlyover', name: 'Cursor Flyover', slug: 'bits-cursor-flyover', component: CursorFlyoverPortrait, width: 1080, height: 1920, durationInFrames: 300, fps: 30},
  {id: 'Bits-KenBurns', name: 'Ken Burns Effect', slug: 'bits-ken-burns', component: KenBurnsPortrait, width: 1080, height: 1920, durationInFrames: 300, fps: 30},
];

export const nativeLayoutNotes: Record<string, string> = {
  'Bits-ChatConversation': 'Original native 1080x1920 ChatConversation StaggeredMotion layout.',
  'Bits-StatRings': 'Original StatRings StaggeredMotion and AnimatedCounter with portrait column layout.',
  'Bits-CursorFlyover': 'Original CursorFlyover Scene3D, Step, and StepResponsive with portrait media bounds.',
  'Bits-KenBurns': 'Original KenBurns Scene3D, Step, and StaggeredMotion with full-bleed portrait frame bounds.',
};
