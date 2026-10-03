# video-talkcraft 源码核查

核查日期：2026-10-02。仓库：[Vincentwei1021/video-talkcraft](https://github.com/Vincentwei1021/video-talkcraft)。默认分支 `main`，本次固定版本 `4cd673df4b7a6a35784a0881df223721789c5e23`。用户明确声明用于自己的非商业短视频制作后，已将全部 108 张 `template/cards` 原 TSX 导入当前工程；原始字节与 SHA-256 保持一致，没有安装整套 skill、多轨工作台或执行上游安装脚本。

本地卡片：`src/components/component-horizontal/video-talkcraft/cards`。来源清单：`licenses/community/video-talkcraft/source-manifest.json`。原 LICENSE、README 和素材来源说明保存在同目录。

## 它与 Remotion 的关系

它是配音驱动解说视频的 **Agent skill + Remotion 模板 + 多轨工作台**。Remotion 负责逐帧画面与渲染；这个仓库另外提供口播稿和配音对齐、分镜、动效卡、运镜、音效及验收流程。它可以用于不出镜的 AI 知识科普，人物素材是可选输入。

这不是只含 npm 组件的库。复用最直接的入口是 `template/cards/<slug>.tsx`：每卡一个 default 组件与 `meta`，单卡的实际 import 均只包含 `react`、`remotion`。部分文案与坐标在 CONFIG 或 JSX 常量中，需要改源码；不能把“工作台参数化”理解为每张原始卡的所有内容都已经暴露成 React props。

来源：[README](https://github.com/Vincentwei1021/video-talkcraft/blob/4cd673df4b7a6a35784a0881df223721789c5e23/README.md)、[模板说明](https://github.com/Vincentwei1021/video-talkcraft/blob/4cd673df4b7a6a35784a0881df223721789c5e23/template/README.md)。

## 数量与已有预览

本次逐项核对：`template/cards` 下 TSX **108 个**、`references/cards` 下 Markdown **108 个**、画廊 JSON 卡片 **108 条**，`gallery-media` release 中 MP4 **108 个**；108 个画廊项目全部有对应 TSX 文件与同名 release MP4。GitHub 简介写 109，当前 README 写 108，模板 README 局部仍写 78，表格以实际文件数 108 为准。

已经存在真实短动效预览视频，不只有截图或代码。它们是单张动效卡的短预览；本次未找到仓库内完整口播成片 MP4，不能把动效预览称为完整 AI 科普成片。

- [在线画廊](https://vincentwei1021.github.io/video-talkcraft/)
- [聚焦压暗：交互演示](https://vincentwei1021.github.io/video-talkcraft/demos/focus-dim-spotlight/index.html) / [MP4](https://github.com/Vincentwei1021/video-talkcraft/releases/download/gallery-media/focus-dim-spotlight.mp4)
- [荧光笔高亮：交互演示](https://vincentwei1021.github.io/video-talkcraft/demos/highlighter-sweep/index.html) / [MP4](https://github.com/Vincentwei1021/video-talkcraft/releases/download/gallery-media/highlighter-sweep.mp4)
- [证据长页巡游：MP4](https://github.com/Vincentwei1021/video-talkcraft/releases/download/gallery-media/evidence-scroll-tour.mp4)
- [ChatGPT 对话框：MP4](https://github.com/Vincentwei1021/video-talkcraft/releases/download/gallery-media/chat-gpt.mp4)
- [108 个预览视频的 release](https://github.com/Vincentwei1021/video-talkcraft/releases/tag/gallery-media)

HTTP 抽查：聚焦压暗与荧光笔的 `index.html` 均返回 200 / `text/html`；聚焦压暗站点 MP4 返回 200 / `video/mp4`。其余视频以 GitHub release 资产列表核对，没有逐个播放。部署方式见 [deploy-pages.yml](https://github.com/Vincentwei1021/video-talkcraft/blob/4cd673df4b7a6a35784a0881df223721789c5e23/.github/workflows/deploy-pages.yml)：画廊现场生成，预览 MP4 从 release 下载至站点 `media/`，因此源码树中没有 108 个 MP4 并不代表没有视频。

## 许可状态

该仓库的 [LICENSE](https://github.com/Vincentwei1021/video-talkcraft/blob/4cd673df4b7a6a35784a0881df223721789c5e23/LICENSE) 是 **PolyForm Noncommercial 1.0.0**，不是 MIT。许可证开头声明工具非商业使用免费，任何工具商业使用须事先取得作者授权；README 同样写明此要求，并提供作者邮箱。许可证也声明生成视频归创作者所有。

本次目录状态为“按用户声明的非商业用途导入”。保留原许可证与版权，使用范围以作者原条件为准；没有将“视频归创作者”推导为“工具可无限制商用”。演示素材还有各自来源说明。原 TSX 卡片没有 HTML 演示壳中的音效，本次导入不包含那套音效播放流程；其独立授权见 [音效授权清单](https://github.com/Vincentwei1021/video-talkcraft/blob/4cd673df4b7a6a35784a0881df223721789c5e23/demos/_lib/sfx/ATTRIBUTION.md)。

## 实际版本与接入范围

以 [runtime/package.json](https://github.com/Vincentwei1021/video-talkcraft/blob/4cd673df4b7a6a35784a0881df223721789c5e23/runtime/package.json) 为准：

| 范围 | 版本 / 依赖 | 对当前工程的影响 |
| --- | --- | --- |
| Remotion 全家 | 4.0.519 | 当前视频工程是 4.0.532；不能直接照搬它的运行时软链与版本升级脚本 |
| React / React DOM | 19.2.8 | 当前工程是 19.3.0；原卡在当前锁定版本下纳入类型与渲染检查 |
| 108 张单卡 | react、remotion | 不需要为了单卡安装整套工作台依赖 |
| 多轨工作台 | @remotion/player、@remotion/zod-types、zod 4.4.3、zustand 5.0.15、Vite 6.4.3 | 属于独立应用，不是复制卡片的必要条件 |
| 完整运行时还含 | gsap 3.15.0、lottie-web 5.13.0、animejs 4.5.0、three 0.186.0 及额外 @remotion 包 | 对应完整工具、桥接或高级动效，单卡不直接 import |
| 对齐与制作脚本 | Python、ffmpeg；本机对齐可用 sherpa-onnx / FireRedASR2-CTC 或 faster-whisper | 可在未来自动化工作流中单独评估；本次未运行或验证模型 |

本地注册直接求值每张卡的原始 `meta`：**107 张为 960×540 / 30fps，`douyin-follow-card` 为 500×483 / 30fps**，时长也读取该 `meta`。不能只按源码中是否出现数字判断画布规格。

Studio 的 `component-horizontal → Talkcraft` 提供 108 个原画布演示；`component-vertical → Talkcraft` 提供 108 个 1080×1920 / 30fps 组合。它们与已有 44 个组件一起构成 152 个组件、304 个 Composition。108 个竖屏实现在 `src/components/component-vertical/video-talkcraft/`，从原源码派生，保留原 CONFIG、时序和运动逻辑，调整 JSX、CSS 和坐标。普通预览移除主持人及其占位，并重排内容。横版目录的 `cards/` 108 文件仍保持字节一致。

来源文件使用部分 macOS 字体回退，Windows 字形可能不同。当前工程只为部分 Snapcn 组件嵌入 Inter / Source Serif 4；不能把这一修正解释为 Talkcraft 的全部字体、尤其中文字体都已原样嵌入。

## 原源码、演示效果与验证范围

108 个原 TSX 保持字节一致；接入层提供具名导出、原 `meta` 注册、预览素材 props 及 `IsolatedCard` 的样式隔离。没有为了消除 lint 警告而改写原卡。

“原 TSX 字节一致”仅说明程序文件来源：官网 HTML 还包含演示壳、素材注入、部分随镜头变化的数据与音效；MP4 又经过独立渲染与编码。字体、浏览器与素材加载也会影响像素结果，因此本地 TSX 预览不宣称与 HTML 或 MP4 样片逐帧一比一。

一些预览使用作者提供的 AI 主持人参考素材，帮助保留原演示的构图。用户的最终方向仍是不出镜 AI 科普：竖屏演示优先使用纯文字引用、代码、图表、流程与截图卡；普通预览去掉主持人后同时调整其余区域。以个人资料为内容的关注卡保留头像等必要元素。

在项目目录运行：

```powershell
npm run typecheck
npm run lint
npm run check:components
npm run catalog:components
```

`typecheck` 严格检查包括原 TSX 在内的全部源码。`lint` 检查本项目和接入层，原 `video-talkcraft/cards/**` 因字节保留而排除 ESLint 规则检查；不宣称原卡全部 lint 通过。`check:components` 首先校验 108 个源文件 SHA-256，再检查 304 个注册项，每个原版抽第 0 / 中间 / 末帧，每个原生竖屏也抽第 0 / 中间 / 末帧，使用原分辨率 `scale: 1` 并检查浏览器错误和素材加载。

这些是验证命令的范围，完整运行结果以 `out/components/verification.json` 为准，过程记录在 `verification-progress.json`。抽帧没有穷尽全部 Props、极端数据和所有帧，也不构成与作者样片的逐像素相等验证。

## AI 科普优先候选

| 卡片 | 现成效果 | AI 科普适配场景 |
| --- | --- | --- |
| focus-dim-spotlight 聚焦压暗切换 | 当前行保留亮度，其余版面压暗，焦点平滑切换 | 模型参数表、工具对比表逐项讲解 |
| highlighter-sweep 荧光笔高亮扫过 | 黄色高亮沿关键句扫过，其他文字退让 | 论文、官方文档、原始证据中的关键结论 |
| evidence-scroll-tour 证据长页巡游 | 长页面滚动，重点前减速并停留 | README、论文网页、产品公告；真实证据需换成实际素材 |
| chat-gpt ChatGPT 对话框 | 输入、发送、等待、分块流式回答 | Prompt 示例和单轮问答；它是演示动画，不会调用模型 |
| glass-code-walk 玻璃代码走读 | 代码进入后推近，逐行高亮并移焦 | API、提示词模板、AI Coding 核心代码 |
| terminal-typing-log 终端打字推进 | 命令打字，日志分块进入，滚动后出现结果 | CLI 工具、安装或自动执行流程 |
| line-chart-story-draw 折线分段叙事 | 历史线保留，预测段与比较线依次画出 | 模型能力或成本趋势；数字需来自明确来源 |
| unit-grid-proportion 百格占比图 | 百格逐步着色，同步显示百分比 | 通过率、覆盖率等真实比例解释 |
| source-converge 多源汇聚 | 多条来源路径汇到一个节点 | RAG、检索、聚合数据、工具输出整合 |
| ui-flow-theater 界面流程剧场 | 指针按时刻表操作开关、按钮，显示成功状态 | 产品工作流程解释；动画示意不能代替真实操作证据 |

108 张卡的完整逐行目录保存在 `docs/video-talkcraft-catalog.json`，包含中文名称、上游分类、效果、适用场景、源码固定版本链接、交互预览、真实 MP4、许可和导入状态。当前已导入全部原 TSX；[飞书组件表格](https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe) 汇总这些信息。
