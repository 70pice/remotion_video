import type {FC} from 'react';
import {AbsoluteFill} from 'remotion';
import {ChatConversation} from './examples/ChatConversation';
import {StatRings} from './examples/StatRings';
import {CursorFlyover} from './examples/CursorFlyover';
import {KenBurns} from './examples/KenBurns';

export const ChatConversationDemo: FC = () => <ChatConversation messages={[
  {from: 'them', text: 'RAG 和普通聊天有什么区别？'},
  {from: 'me', text: 'RAG 会先查找相关资料。'},
  {from: 'them', text: '找到资料以后呢？'},
  {from: 'me', text: '把资料放进模型的上下文。'},
  {from: 'me', text: '然后结合资料组织答案。'},
  {from: 'them', text: '懂了，这是流程示意。'},
]} />;

export const StatRingsDemo: FC = () => <AbsoluteFill>
  <StatRings stats={[
    {label: '示例指标 A', value: 72, toFixed: 0},
    {label: '示例指标 B', value: 56, toFixed: 0},
    {label: '示例指标 C', value: 38, toFixed: 0},
  ]} />
  <div style={{position: 'absolute', top: 48, left: 64, color: '#cbd5e1', fontSize: 24, fontFamily: '"Microsoft YaHei UI", Arial, sans-serif'}}>演示数据 · 非真实模型评测</div>
</AbsoluteFill>;

export const CursorFlyoverDemo: FC = () => <AbsoluteFill style={{background: '#0b1020'}}><CursorFlyover /></AbsoluteFill>;
export const KenBurnsDemo: FC = () => <KenBurns stepDuration={60} transitionDuration={30} />;

type Demo = {id: string; name: string; slug: string; component: FC; width: number; height: number; durationInFrames: number; fps: 30; defaultProps?: Record<string, unknown>};
export const componentDemos: Demo[] = [
  {id: 'Bits-ChatConversation', name: 'Chat Conversation', slug: 'bits-chat-conversation', component: ChatConversationDemo, width: 1280, height: 720, durationInFrames: 180, fps: 30},
  {id: 'Bits-StatRings', name: 'Stat Rings', slug: 'bits-stat-rings', component: StatRingsDemo, width: 1280, height: 720, durationInFrames: 150, fps: 30},
  {id: 'Bits-CursorFlyover', name: 'Cursor Flyover', slug: 'bits-cursor-flyover', component: CursorFlyoverDemo, width: 1280, height: 720, durationInFrames: 300, fps: 30},
  {id: 'Bits-KenBurns', name: 'Ken Burns Effect', slug: 'bits-ken-burns', component: KenBurnsDemo, width: 1280, height: 720, durationInFrames: 300, fps: 30},
];
