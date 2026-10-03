import type {ComponentType, ReactNode} from 'react';
import {AbsoluteFill, Img, staticFile} from 'remotion';
import {LOCAL_FONT_FAMILY} from './ui/local-font';
import {
TextReveal,TextBuild,TextHighlight,TextRewrite,TextSwap,WordFlip,WordCaptions,KaraokeCaptions,SearchTyping,PromptSend,PromptZoom,AnswerStream,AnswerHighlight,AgentSteps,TerminalSimulator,ChannelThread,PhoneFrame,LaptopFrame,ScreenRecording,CursorTrack,MoodboardReveal
} from './index';

const canvas = (children: ReactNode, dark = false) => (
  <AbsoluteFill style={{backgroundColor: dark ? '#101421' : '#faf9f6', fontFamily: LOCAL_FONT_FAMILY,
    justifyContent: 'center', alignItems: 'center', overflow: 'hidden'}}>
    {children}
  </AbsoluteFill>
);
const uiImage = () => staticFile('community/ai-ui.svg');
const photo = () => staticFile('community/landscape.svg');

const TextRevealDemo = () => canvas(<TextReveal text="认识 AI 智能体" fontFamily={LOCAL_FONT_FAMILY}/>);
const TextBuildDemo = () => canvas(<TextBuild text="让 知识 变成 视频" fontFamily={LOCAL_FONT_FAMILY}/>);
const TextHighlightDemo = () => canvas(<TextHighlight before="AI 的关键是 " highlight="上下文" preset="marker" fontFamily={LOCAL_FONT_FAMILY}/>);
const TextRewriteDemo = () => canvas(<TextRewrite headline="写一个 短视频 脚本" keep={1} append="清晰的 科普脚本" fontFamily={LOCAL_FONT_FAMILY}/>);
const TextSwapDemo = () => canvas(<TextSwap fromText="手动 操作" toText="自动 执行" fontFamily={LOCAL_FONT_FAMILY}/>);
const WordFlipDemo = () => canvas(<WordFlip prefix="AI 可以" words={['搜索', '推理', '执行']} suffix="任务" fontFamily={LOCAL_FONT_FAMILY}/>);
const WordCaptionsDemo = () => canvas(<><Img src={photo()} style={{width:'100%',height:'100%',objectFit:'cover'}}/><WordCaptions words="人工智能 可以 帮你 理解 知识 自动 制作 视频" framesPerWord={18} fontFamily={LOCAL_FONT_FAMILY}/></>, true);
const KaraokeCaptionsDemo = () => canvas(<><Img src={photo()} style={{width:'100%',height:'100%',objectFit:'cover'}}/><KaraokeCaptions text="我们 把 复杂 的 AI 知识 讲 清楚" emphasize="讲 清楚" fontFamily={LOCAL_FONT_FAMILY}/></>, true);
const SearchTypingDemo = () => canvas(<SearchTyping text="AI 智能体如何工作？" fontFamily={LOCAL_FONT_FAMILY}/>);
const PromptSendDemo = () => canvas(<PromptSend text="请解释什么是 RAG，并举一个例子。" chips={['解释概念','举例说明','整理步骤']} fontFamily={LOCAL_FONT_FAMILY}/>);
// Match the pinned author's preview config; do not replace its serif/sans pair with one font.
const PromptZoomDemo = () => canvas(<PromptZoom
  greeting="Up late?"
  placeholder="How can I help you today?"
  text="Get me a plan for tomorrow"
  model="Auto"
  effort="Medium"
  typeStart={0.35}
  cutAt={1}
  zoom={2.547}
  charsPerSecond={18}
  focusX={0.27}
  focusY={0.516}
  accentColor="#266DF0"
  mode="light"
/>);
const AnswerStreamDemo = () => canvas(<AnswerStream question="什么是 AI 智能体？" answer="智能体 接收 目标，制订 计划，调用 工具，再 根据 结果 调整 下一步。" headline="三个关键能力" cards={[{title:'理解',body:'把目标转成可执行步骤'},{title:'工具',body:'搜索、读取和操作软件'},{title:'反馈',body:'检查结果并继续行动'}]} fontFamily={LOCAL_FONT_FAMILY}/>);
const AnswerHighlightDemo = () => canvas(<AnswerHighlight question="AI 为什么需要上下文？" answer="上下文 提供 当前 任务 的 背景 和 约束。清晰的 目标 和 充分的 信息 能 帮助 模型 给出 更 相关 的 回答。" statement="清晰的 目标" word="目标" fontFamily={LOCAL_FONT_FAMILY}/>);
const AgentStepsDemo = () => canvas(<AgentSteps query="把一段文章做成 AI 科普视频" steps={[{running:'正在理解文本…',done:'提取 3 个重点',icon:'check'},{running:'正在检索资料…',done:'找到可靠来源',icon:'globe'},{running:'正在生成脚本…',done:'完成分镜',icon:'check'},{running:'正在渲染视频…',done:'完成视频',icon:'check'}]} result="视频已生成" fontFamily={LOCAL_FONT_FAMILY}/>);
const TerminalSimulatorDemo = () => canvas(
  <TerminalSimulator
    intro="用 *代码* 制作视频"
    command={{text:'npx remotion render'}}
    lines={[
      {text:'准备脚本和素材',type:'command',delay:0,pause:0},
      {text:'渲染帧 1 / 300',type:'log',delay:8,pause:0},
      {text:'渲染完成',type:'success',delay:8,pause:0},
    ]}
    speed={1.2}
    fontFamily={LOCAL_FONT_FAMILY}
  />,
  true,
);
const ChannelThreadDemo = () => canvas(<ChannelThread messages={[{author:'策划 Agent',time:'09:41',text:'先理解文章，再确定重点。',avatar:uiImage(),at:0},{author:'策划 Agent',time:'09:41',text:'脚本已经准备好了。',avatar:uiImage(),at:30},{author:'制作 Agent',time:'09:42',text:'我来匹配组件和素材。',avatar:uiImage(),at:72},{author:'制作 Agent',time:'09:42',text:'开始生成视频。',avatar:uiImage(),at:110}]} fontFamily={LOCAL_FONT_FAMILY}/>,true);
const PhoneFrameDemo = () => canvas(<PhoneFrame screenSrc={uiImage()} variant="tilt" fontFamily={LOCAL_FONT_FAMILY}/>);
const LaptopFrameDemo = () => canvas(<LaptopFrame screenSrc={uiImage()} entrance="open" finale="zoom-to-screen" notchLabel="AI 正在运行" fontFamily={LOCAL_FONT_FAMILY}/>);
const ScreenRecordingDemo = () => canvas(<ScreenRecording src={uiImage()} sourceAspect={16/9} camera={[{at:30,duration:25,zoom:1.9,x:0.68,y:0.55},{at:100,duration:25,zoom:1}]}/>);
const CursorTrackDemo = () => canvas(<CursorTrack><Img src={uiImage()} style={{width:'100%',height:'100%'}}/></CursorTrack>);
const MoodboardRevealDemo = () => canvas(<MoodboardReveal leadIn="让" emphasis="知识" tailIn="可视化" images={[photo(),uiImage(),photo(),uiImage()]} heroImage={uiImage()} fontFamily={LOCAL_FONT_FAMILY}/>);

export type SnapcnDemo = {
  id: string; name: string; slug: string; component: ComponentType;
  width: number; height: number; durationInFrames: number; fps: number;
};

export const componentDemos: SnapcnDemo[] = [
  {id:'Snapcn-TextReveal',name:'TextReveal',slug:'text-reveal',component:TextRevealDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-TextBuild',name:'TextBuild',slug:'text-build',component:TextBuildDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-TextHighlight',name:'TextHighlight',slug:'text-highlight',component:TextHighlightDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-TextRewrite',name:'TextRewrite',slug:'text-rewrite',component:TextRewriteDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-TextSwap',name:'TextSwap',slug:'text-swap',component:TextSwapDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-WordFlip',name:'WordFlip',slug:'word-flip',component:WordFlipDemo,width:1280,height:720,durationInFrames:210,fps:30},
  {id:'Snapcn-WordCaptions',name:'WordCaptions',slug:'word-captions',component:WordCaptionsDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-KaraokeCaptions',name:'KaraokeCaptions',slug:'karaoke-captions',component:KaraokeCaptionsDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-SearchTyping',name:'SearchTyping',slug:'search-typing',component:SearchTypingDemo,width:1280,height:720,durationInFrames:210,fps:30},
  {id:'Snapcn-PromptSend',name:'PromptSend',slug:'prompt-send',component:PromptSendDemo,width:1280,height:720,durationInFrames:210,fps:30},
  {id:'Snapcn-PromptZoom',name:'PromptZoom',slug:'prompt-zoom',component:PromptZoomDemo,width:1280,height:720,durationInFrames:90,fps:30},
  {id:'Snapcn-AnswerStream',name:'AnswerStream',slug:'answer-stream',component:AnswerStreamDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-AnswerHighlight',name:'AnswerHighlight',slug:'answer-highlight',component:AnswerHighlightDemo,width:1280,height:720,durationInFrames:210,fps:30},
  {id:'Snapcn-AgentSteps',name:'AgentSteps',slug:'agent-steps',component:AgentStepsDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-TerminalSimulator',name:'TerminalSimulator',slug:'terminal-simulator',component:TerminalSimulatorDemo,width:1280,height:720,durationInFrames:300,fps:30},
  {id:'Snapcn-ChannelThread',name:'ChannelThread',slug:'channel-thread',component:ChannelThreadDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-PhoneFrame',name:'PhoneFrame',slug:'phone-frame',component:PhoneFrameDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-LaptopFrame',name:'LaptopFrame',slug:'laptop-frame',component:LaptopFrameDemo,width:1280,height:720,durationInFrames:210,fps:30},
  {id:'Snapcn-ScreenRecording',name:'ScreenRecording',slug:'screen-recording',component:ScreenRecordingDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-CursorTrack',name:'CursorTrack',slug:'cursor-track',component:CursorTrackDemo,width:1280,height:720,durationInFrames:180,fps:30},
  {id:'Snapcn-MoodboardReveal',name:'MoodboardReveal',slug:'moodboard-reveal',component:MoodboardRevealDemo,width:1280,height:720,durationInFrames:180,fps:30},
];
