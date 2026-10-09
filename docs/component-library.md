# 现成 Remotion 组件库

导演学习入口见 [镜头知识库](knowledge/remotion-shot-library.md)，其历史快照来自用户指定飞书表。当前生产调用以仓库内 `docs/component-paths.json`、`docs/component-use-guide.json` 和 `videoagents/component-manifest.json` 为准，覆盖 187 条社区预设。

实际源码分成两套：竖版在 `src/components/component-vertical`，横版在 `src/components/component-horizontal`。每个来源库下的 `entries/<slug>.tsx` 提供单独的演示入口。`src/components/community` 保留注册、目录元数据和共享工具，与每一期视频的模板分开。

运行时统一固定 Remotion 4.0.532。此前 4.0.531 的发布包含空 JavaScript 文件，会令 Studio 报 `getRenderQueue is not a function`；本次使用[官方修复版本](https://github.com/remotion-dev/remotion/releases/tag/v4.0.532)，组件的上游 commit 保持原记录。

当前共 **187 个社区组件**：原先 152 个，加上 RemotionUI 10 个、RVE 15 个、RenderComp 10 个精选补充。目录数据见 `community-components.json`，原作者、固定 commit 与适配记录见 `licenses/community`。

| 组件库 | 已导入数量 | 接入方式 |
| --- | ---: | --- |
| Snapcn | 21 | 原组件及依赖闭包，字体和示例素材适配 |
| RVE | 26 | 原模板与精选补充，增加数据 props 与边界处理 |
| Remocn | 5 | 原组件及依赖闭包，字体和演示参数适配 |
| RemotionUI | 13 | 原场景与精选补充，字体和演示参数适配 |
| RenderComp | 10 | 精选补充组件，统一横竖版入口与演示参数 |
| Bits | 4 | 原示例及依赖闭包，素材、props 和 Hook 修正 |
| video-talkcraft | 108 | 原 TSX 字节保留，预览素材和样式隔离由接入层提供 |

原先 152 个由 44 个精选接入组件和 Talkcraft 108 张卡组成；本次再补充
RemotionUI 10 个、RVE 15 个、RenderComp 10 个，形成当前 187 个社区组件。
Talkcraft 的 108 个对应本次固定提交下全部卡片，其他来源仍是精选接入范围，
不代表上游网站的全部组件。

## 看效果

在项目目录运行：

```powershell
npm ci
npm run components
```

打开 `http://127.0.0.1:3102`。左侧分为两组，共 374 个 Composition：

- `component-horizontal → 组件库 → Composition`：187 个横版演示，Talkcraft 沿用来源画布；Bits 聊天演示改用 1280×720。
- `component-vertical → 组件库 → Vertical-Composition`：同一批 187 个组件的原生竖屏布局，统一 1080×1920 / 30fps。

例如原版 `Talkcraft-highlighter-sweep` 与竖屏版 `Vertical-Talkcraft-highlighter-sweep`。原视频仍在 `npm run dev` 的 `AiScience`；主入口也注册这些演示。

`component-vertical/<组件库>/` 提供独立的竖屏布局。文字、图表、聊天、面板和运动坐标分别调整，原动画逻辑与时序尽量沿用。详见 [原生竖屏说明](native-portrait.md)。

`out/components/index.html` 是验证后生成的离线效果目录，包含原版抽帧、竖屏中间帧、原作者预览与固定版本源码链接。原版按 Composition 的完整分辨率渲染，竖屏图片为 1080×1920。连续动画需在 Studio 播放。

## 在新视频中复用

### 通过 VideoAgents Timeline 直接选择

全部 187 个逻辑组件已经作为固定视觉 preset 开放给生产 Timeline，并与 9 个
参数化 adapter 组成 196 个稳定 `component_id`。导演 Prompt、`/api/catalog`、
React 分镜选择器、Python/Node 校验和 Remotion registry 共用
`videoagents/component-manifest.json`；同一 ID 会根据 timeline 方向自动使用横版
或原生竖版实现。

preset 当前保留已验证的示例参数作为视觉骨架，同时可接收统一安全素材槽位：
shot 的 title/body/source_label/accent_color、当前任务图片或 MP4，以及
content_mode、asset_fit、asset_crop、start_seconds/end_seconds、短列表和单个
指标。不能把原卡的演示文字、人物或数字当作事实证据，也不能给 preset 注入
任意私有 props、CSS、URL、函数或源码路径。需要精确证据框、复杂数据、对比
或步骤同步时，仍使用 9 个参数化 adapter，或先为目标 preset 建立有类型和测试
的独立适配器。Talkcraft preset 只对
personal/unspecified 任务开放，commercial 任务会在生成和校验阶段拒绝。

### 在自定义 Composition 中手工导入

飞书表中的相对路径从仓库根目录 `D:\remotion_video` 起算。竖屏短视频用 `component-vertical/<组件库>/entries/<slug>.tsx`，横版用 `component-horizontal/<组件库>/entries/<slug>.tsx`。每个入口文件导出 `Component`、`demo` 和 `meta`，沿用已验证的示例参数；入口是代码索引，竖版布局实际源码也已移动到竖版目录。

例如，在 `src/videos/` 下可以组合现成竖版示例：

```tsx
import {Sequence} from 'remotion';
import WordFlip from '../components/component-vertical/snapcn/entries/word-flip';
import Highlight from '../components/component-vertical/video-talkcraft/entries/highlighter-sweep';

export const ExampleVideo = () => <>
  <Sequence durationInFrames={90}><WordFlip /></Sequence>
  <Sequence from={90} durationInFrames={60}><Highlight /></Sequence>
</>;
```

修改真实文案或数据时，从 `docs/component-paths.json` 的 `verticalSourcePath` / `horizontalSourcePath` 找到实际实现，按组件已有 Props 接口传参。Talkcraft 入口已包含素材 props 和样式隔离。

底层源码仍提供六个命名空间，避免两家组件同名：`Snapcn`、`RVE`、`Remocn`、`RemotionUI`、`Bits`、`VideoTalkcraft`。

```tsx
import {AbsoluteFill} from 'remotion';
import {Snapcn, RVE} from '../components/community';

export const ConceptTitle = () => (
  <AbsoluteFill style={{background: '#faf9f6'}}>
    <Snapcn.TextBuild
      text="先 检索 再 回答"
      fontFamily='"Microsoft YaHei UI", sans-serif'
    />
  </AbsoluteFill>
);

export const SourceQuote = () => (
  <RVE.QuoteCard
    quote="这里替换成已核对的引用内容。"
    attribution="来源：原始文档"
  />
);
```

组件是画面；镜头顺序和时长仍由每期视频的 `Sequence` / `Series` 安排，Composition 注册整支视频。导入组件不会调用真实 AI、检索或 TTS 服务，图表也不会自动获取数据。

Talkcraft 原卡包含样式标签及重复类名。复用时沿用接入层的 `IsolatedCard`，将卡片样式限制在自己的 ShadowRoot 内，并按原 `meta` 画布组织镜头。例如无主持人的高亮引用卡：

```tsx
import {IsolatedCard, VideoTalkcraft} from '../components/community';

export const HighlightReference = () => (
  <IsolatedCard>
    <VideoTalkcraft.HighlighterSweep />
  </IsolatedCard>
);
```

这张原卡是 960×540 / 30fps，时长 60 帧，引用文案仍为原作者示例。原卡不一定把文案和布局暴露成 props；正式镜头要先确定配音与内容，再决定外部包装、数据接口或独立改编，不能将演示内容当成真实论据。

## 验证与重新生成目录

```powershell
npm run typecheck
npm run lint
npm run check:components
npm run catalog:components
npm run check:component-paths
npm run check:production-components
```

这些命令的检查范围为：

- `typecheck`：严格 TypeScript 检查覆盖项目及 108 张原始 Talkcraft 卡。
- `lint`：检查本项目和接入层；为保留原始字节，`video-talkcraft/cards/**` 排除 ESLint 风格与规则检查，这不代表这些原卡获得了 lint 通过结论。
- `check:components`：核对 108 个原卡 SHA-256、187 个原版及 187 个竖屏注册项；原版抽起始 / 中间 / 结束三帧，原生竖屏也抽起始 / 中间 / 结束三帧，均使用 `scale: 1`。检查浏览器错误、素材加载与抽样画面变化。
- `catalog:components`：根据验证报告生成目录，不能替代前面的源码和渲染检查。
- `check:component-paths`：检查187对入口与实现、374条入口路径、表格行数据和108个原卡哈希。
- `check:production-components`：重新推导 9 个 adapter + 187 个 preset 的统一生产清单，检查 ID、用途许可和组件目录是否漂移。

更新已有飞书表格时运行 `python scripts/update-component-path-sheet.py --execute`，随后 `python scripts/verify-component-path-sheet.py` 回读全部1399个单元格。省略 `--execute` 仅预览请求。

完整结果保存在 `out/components/verification.json`，运行过程记录在 `verification-progress.json`。抽帧检查没有穷尽全部 Props、极端数据或所有帧，也没有证明与作者网站的视频逐像素相等。

单独导出一个演示：

```powershell
npx remotion render src/community.ts Snapcn-TextBuild out/text-build-demo.mp4
```

## 使用时需要适配的内容

- `component-horizontal` 提供横版对照，`component-vertical` 使用原生竖屏布局。自然横向素材、笔记本设备、相机推近产生的局部裁切可以保留；换成真实脚本时仍须检查长文本、字幕和平台界面遮挡。
- 图表数值、对话、SVG 界面都是演示素材。生产视频需要替换为有来源的数据与真实素材。
- 部分 Snapcn 组件嵌入真实 Inter / Source Serif 4 拉丁字体，并在渲染前等待字体加载；其他字体与中文仍回退系统字体。系统字体在不同电脑上的字形可能不同，不应宣称中文排版像素一致。
- Snapcn 部分文字组件按空格分词，当前中文示例已手动拆词；同步字幕需要真实配音时间戳。
- 部分原始组件保留上游默认素材 URL。直接调用时应明确传自己的本地素材，核对其授权。
- RVE 与 Bits 上游只有 README/package 的 MIT 声明，缺少独立 LICENSE；已保存真实声明，不伪造许可证。Remotion 核心许可仍单独适用。

## video-talkcraft

按用户明确声明的非商业短视频用途，已导入 **108 张原卡**，与原先 44 个分目录存放。源文件位于 `src/components/component-horizontal/video-talkcraft/cards`，`licenses/community/video-talkcraft/source-manifest.json` 记录原 SHA-256；原 TSX 字节保持一致，外部预览 props、素材与样式隔离不写入原卡。

107 张原卡的 `meta` 为 960×540，`douyin-follow-card` 为 500×483；规格与时长读取实际 `meta`，不根据画廊截图猜测。原 TSX 不包含官网 HTML 演示壳的音效，源码字节相同也不等同于 HTML、TSX、MP4 整套样片逐帧一比一。

预览中的 AI 主持人是作者的参考素材。我们制作不出镜视频时，选择无主持人组件，或针对选定镜头调整布局；只把人物素材移除，原来的占位和构图不一定合适。不需要为使用单卡安装整套 skill、多轨工作台或语音对齐工具。

上游许可为 **PolyForm Noncommercial 1.0.0**。本次保留作者原 LICENSE 及素材来源说明；工具商业使用仍需要作者授权。详情见 [video-talkcraft 源码核查](video-talkcraft-review.md)。

## 与原作者预览的视觉一致性

原先 44 个组件使用真实上游源码，但适配过字体、文案、素材、参数接口和部分演示时长，不是官网样片的像素级复刻。简单 SVG 界面不能提供真实截图和照片的细节，系统字体也会改变字宽、标题气质和换行。

当前 `Snapcn-PromptZoom` 已恢复固定提交下官方预览的英文文案、参数、90 帧时长，以及真实 Inter / Source Serif 4 的 sans / serif 区别。镜头硬切、几何布局、打字与光标公式仍保持上游代码。其他组件的具体改动见各自 `licenses/community/*/provenance.md` 或 `PROVENANCE.md`；“能运行”与“成片视觉已完成”需要分别判断。

飞书表格：[Remotion 组件库与 video-talkcraft 调研](https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe)。当前本地总目录187行，五列为组件名称、竖版相对文件路径、横版相对文件路径、适合表达的内容、适用场景。仓库说明另存来源与许可。
