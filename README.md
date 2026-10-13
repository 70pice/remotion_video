# AI 科普视频工作台

**VideoAgents** 通过 `videoagents` CLI、Python 图引擎(多 Agent 工作流)和 Remotion 渲染,
制作面向关心 AI 如何影响自己的钱、工作和生活的普通人看的 AI 科普、避坑、案例和工具判断视频。
作者身份是大厂程序员,但默认不要求观众主动关注 AI、懂编程或懂专业术语。2026-10-13 起**没有
Web 前端和 HTTP 服务**:监督由导演会话(强模型 CLI,见 [docs/roles/director.md](docs/roles/director.md))
通过命令行驱动,人工审核在**飞书多维表格**(一个视频一个 Base,见
[docs/roles/feishu.md](docs/roles/feishu.md))。

## 快速开始

```bash
npm ci && npm run generate:contracts        # Node 依赖 + 契约
python -m pip install -e . pytest           # Python 3.12(或用 .venv-videoagents)
brew install ffmpeg                          # macOS;二进制需能解码标准 WAV
# 配置:videoagents settings set zhipu_api_key <key>
#       videoagents settings set feishu_folder_token <飞书文件夹token>
videoagents create --brief brief.json        # 建任务
videoagents run <job_id>                     # 执行到下一个人工门(渲染建议后台跑)
videoagents status <job_id>                  # 阶段/待办/产物路径
videoagents poll <job_id>                    # 读飞书「审核记录」决定并续跑(resume 为兜底)
videoagents shots <job_id>                   # 逐镜审核包(PNG 路径+组件清单)
```

当前生产图:**编剧(最前,带只读检索)→ 素材(按画面需求单取证)→ 人工审文案与素材 → 配音 →
摄影(镜头设计与逐镜代表帧)→ 人工逐镜审核 → 剪辑成片**。全部检查见 `npm run check:all`;
详见 [AGENTS.md](AGENTS.md)、[角色条例](docs/roles/README.md)、
[使用说明](docs/videoagents-setup.md) 与 [实现与验证记录](docs/videoagents-implementation-status.md)。

每个正式视频应使用一条独立任务分支,建议按 `video/<job_id>` 命名。运行数据、
素材、音频、分镜、成片和 checkpoint 都以 `job_id` 与 `revision` 隔离;跨视频
复用必须显式导入为当前任务素材或来源,不能直接引用另一个视频的运行目录。

## Remotion 依赖与许可

Remotion 系列统一固定 4.0.532(修复 4.0.531 的空文件问题,见
[官方发布说明](https://github.com/remotion-dev/remotion/releases/tag/v4.0.532))。
Shapes、Captions 等官方包为 MIT;Remotion 核心受
[Remotion 许可证](https://github.com/remotion-dev/remotion/blob/v4.0.532/LICENSE.md) 约束,
使用方需按组织情况确认许可。

## 187 个现成组件:生产选择与复用

实际源码与复用入口在 `src/components/component-vertical` 和
`src/components/component-horizontal`;注册、目录元数据和共享工具在
`src/components/community`。每个库下的 `entries/<slug>.tsx` 是单组件入口,
路径索引见 `docs/component-paths.json`。当前共 187 个社区组件:原先 152 个,
加上 RemotionUI 10 个、RVE 15 个、RenderComp 10 个精选补充;横竖两版各 187 个、
共 374 个 Composition,竖版为 1080×1920 / 30fps 原生布局。详见
[原生竖屏说明](docs/native-portrait.md)。

组件预览已无交互式 Studio 入口(2026-10-13 随前端移除);组件健康由
`npm run check:components` **无头渲染**守护:核对 108 个原始 Talkcraft 源码
SHA-256,并在原分辨率渲染每个横版与原生竖版的起始/中间/结束帧。结果以生成的
`out/components/verification.json` 为准(不入 Git),`npm run catalog:components`
据其更新离线效果页。

VideoAgents 的生产 Timeline 已开放全部 187 个社区组件,并提供 9 个可参数化
适配器,共 196 个稳定 `component_id`。同一社区组件不拆成两个生产 ID。374 个
Composition 服务无头组件校验;生产 timeline 中部分组件有专用原生画面,其余渲染为
安全内容槽位的统一画面,能力边界详见
[组件知识库](docs/knowledge/remotion-shot-library.md)。统一清单由
`scripts/build-production-component-manifest.mjs` 从组件目录和使用指南生成到
`videoagents/component-manifest.json`,Python 摄影/校验与 Remotion registry 共用;
运行 `npm run check:production-components` 可检查清单是否漂移。

187 个社区组件以**安全内容槽位**接入:摄影按组件知识库选择合适预设,把当前
任务的素材、短文案、指标、列表或视频片段塞进 `content_mode`、`items`、`metric`、
`asset_fit`、`asset_crop`、`start_seconds`、`end_seconds` 等受控字段;内置演示
文案和数字不能作为本片事实证据。需要完全结构化的数据图、步骤、对比、结论或证据图时,
继续优先使用 9 个参数化适配器。Talkcraft 的 108 个预设受 PolyForm Noncommercial
限制,仅对 personal/unspecified 任务开放,commercial 任务会在摄影 schema 和后端
校验中排除。

原先 44 个组件是上游源码的导入与适配,不是官网样片的像素级复刻;字体、文案、
演示素材和部分时长有差异。PromptZoom 已恢复官方预览文案、时序和
Inter / Source Serif 4 字体。只有部分组件嵌入这两个字体,其余字体及中文仍使用
系统回退。

video-talkcraft 按用户声明的非商业短视频用途导入。108 个 `template/cards` TSX
保持原始字节,哈希记录在 `licenses/community/video-talkcraft/source-manifest.json`;
没有安装整套 skill 或工作台。其许可为 PolyForm Noncommercial,完整来源及接入边界见
[源码核查](docs/video-talkcraft-review.md)。
[飞书组件表格](https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe)
收录各组件效果、场景、预览及许可。详细用法见 [组件库说明](docs/component-library.md)。
