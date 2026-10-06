# AI 科普视频工作台

**VideoAgents 全栈视频工作台**通过 React 前端、FastAPI 接口、多 Agent 工作流和
Remotion 渲染，制作面向普通大众的 AI 科普、AI 新闻/产品解释和 AI 工具使用
视频。默认不要求观众懂编程或 AI 专业术语；素材、文案、配音、导演、剪辑和
审核共同把专业信息翻译成生活与工作中能听懂、能判断、能使用的内容。运行
`npm run studio:dev` 后打开 `http://127.0.0.1:5173`。首次安装、配置、操作和
故障排查见 [VideoAgents 使用说明](docs/videoagents-setup.md)；代码 Review 入口
见 [实现与验证记录](docs/videoagents-implementation-status.md)，原方案见
[工作流设计](docs/videoagents-design.md)。React 学习阅读顺序见
[前端说明](web/README.md)。

下面保留原有单集视频作为渲染兼容性回归样片。它不是当前账号的受众定位，
也不是 Agent 的选题或文案示例；正式生产统一从 VideoAgents 工作流进入。

历史第一版：**AI 写完代码，就算完成了吗？**。依据用户提供的
《AI Coding 大厂中的发展历程（三）》改编，8 个镜头，1080×1920，30 fps，
约 71 秒。镜头时长由真实配音长度决定。

## 在本机看结果

- 成片：`out/ai-coding-v1.mp4`
- 播放页：`out/index.html`，双击可以离线播放成片。
- 口播与分镜：`episodes/001-ai-coding/script-and-storyboard.md`
- 预览、编辑：`npm run dev`，在 Remotion Studio 中选择 `AiScience`。

## 重做一集

1. 修改 `episodes/001-ai-coding/episode.json` 的文案和镜头信息。
2. 首次安装：`npm ci`；`python -m venv .venv`；`.\.venv\Scripts\python.exe -m pip install -r scripts/requirements.txt`。
3. 生成配音/字幕/时间线：`.\.venv\Scripts\python.exe scripts/prepare_episode.py`。
4. 检查：`npm run typecheck`、`npm run lint`、`npm run check:captions`、`.\.venv\Scripts\python.exe scripts/validate_episode.py`。
5. 导出：`npm run render`。重新生成封面：`npm run still`。

需要联网获取依赖、初次下载 Chrome 和生成配音；成片及播放页可离线查看。不要手动修改 `src/episode.generated.json`，它由脚本生成。每镜头缓存配音和词级时间戳，文案/声音参数不变时复用，失败后可重跑，不重复生成已成功的镜头。

配音目前用 Microsoft Edge 在线语音服务，中文男声 `zh-CN-YunxiNeural`，通过社区 `edge-tts` 调用，不是已配置的商业 TTS API。仅改编后的口播稿发给配音服务；原文密码、链接和图片不发送。后续长期生产可替换成具有明确授权和 SLA 的 TTS 服务，保留同样的音频与时间戳输出契约。

## 文件分工

```text
src/index.ts                         Remotion 入口
src/Root.tsx                         视频规格与 Composition 注册
src/templates/AiScienceVideo.tsx      可复用科普视频模板 / 镜头编排
src/components/TimedCaptions.tsx      使用官方工具分组的同步字幕
src/components/vendor/TextBuild.tsx  复制并适配的社区动态文字组件
episodes/001-ai-coding/episode.json   本期可编辑脚本、镜头与来源说明
src/episode.generated.json           根据真实音频生成的时间线
public/episodes/001-ai-coding/        配音、字幕数据和本期截图
scripts/prepare_episode.py           分镜配音、缓存与帧时间线生成
scripts/validate_episode.py          时序、素材与成片检查
licenses/                            组件来源及许可证
out/                                 可播放 MP4、封面与播放页
```

新选题先复用已有镜头类型。遇到新表达需求再补组件；镜头数量和文案不必通过修改 Root.tsx 来硬编码。

原始阅读记录与原文截图只保存在本机并被 Git 忽略，防止将受密码保护的内容随仓库上传；换电脑需要一起复制这些截图文件。生成的 AI 配音明确标识。没有推送仓库或发布到抖音。

## 现成组件的复用

- 社区 [Snapcn TextBuild](https://github.com/snapcndev/snapcn/blob/d4419a8c0366c4d6d3bf44d803e54593e8dd4ac3/registry/snap-cn/text-build/index.tsx)：标题动画，MIT，保留作者声明。仅移除上游全局主题/在线字体配置，使用本地中文字体；详见 `licenses/snapcn-provenance.md`。
- 官方 [TransitionSeries + fade](https://www.remotion.dev/docs/transitions/transitionseries)：镜头淡化过渡。
- 官方 [Arrow / Circle](https://www.remotion.dev/docs/shapes)：流程图和状态标记。
- 官方 [createTikTokStyleCaptions](https://www.remotion.dev/docs/captions/create-tiktok-style-captions)：根据已有时间戳整理字幕段落；不是转写服务。
- 官方 [Audio](https://www.remotion.dev/docs/media/audio)：配音播放与合成。

Remotion 系列统一固定 4.0.532。该版本修复 4.0.531 发布包中的空 JavaScript 文件，避免 Studio 的 `getRenderQueue is not a function` 错误，见[官方发布说明](https://github.com/remotion-dev/remotion/releases/tag/v4.0.532)。Shapes、Captions 和 Snapcn 为 MIT；Remotion 核心及转场受 [Remotion 许可证](https://github.com/remotion-dev/remotion/blob/v4.0.532/LICENSE.md) 约束，使用方需按组织情况确认许可。

## 152 个现成组件的预览、生产选择与复用

运行 `npm run components`，打开 `http://127.0.0.1:3102`。实际源码与复用入口分别在 `src/components/component-vertical` 和 `src/components/component-horizontal`；注册、目录元数据和共享工具在 `src/components/community`。每个库下的 `entries/<slug>.tsx` 是单组件入口，路径索引见 `docs/component-paths.json`。当前包含原先 44 个组件（Snapcn 21、RVE 11、Remocn 5、RemotionUI 3、Bits 4）和新增 video-talkcraft 108 张卡，共 152 个。

Studio 分两个同名文件夹：`component-horizontal` 展示 152 个横版演示；`component-vertical` 展示对应的 152 个 1080×1920 / 30fps 原生竖屏演示，共 304 个 Composition。竖屏使用独立布局：文字分行、对比上下排列、界面内容纵向展开、图表和动画路径使用竖屏坐标。Bits 聊天组件的横版演示使用1280×720，其余横版沿用来源画布。详见 [原生竖屏说明](docs/native-portrait.md)。

VideoAgents 的生产 Timeline 已开放全部 152 个逻辑组件，并提供 9 个可参数化
适配器，共 161 个稳定 `component_id`。同一社区组件不拆成两个生产 ID，渲染器
会根据 timeline 方向自动选择横版或原生竖版实现。统一清单由
`scripts/build-production-component-manifest.mjs` 从组件目录和使用指南生成到
`videoagents/component-manifest.json`，Python 导演/校验、React 分镜编辑器和
Remotion registry 共用；运行 `npm run check:production-components` 可检查清单
是否漂移。

152 个社区组件目前以**固定视觉预设**接入：`props={}`、`asset_src=null`，内置
演示文案和数字不能作为本片事实证据；真实文案、数据、证据图、视频和步骤应
使用 9 个参数化适配器。Talkcraft 的 108 个预设受 PolyForm Noncommercial
限制，仅对 personal/unspecified 任务开放，commercial 任务会在导演 schema、
后端校验和前端选择器中排除。

详细用法见 [组件库说明](docs/component-library.md)。`npm run check:components` 会核对 108 个原始 Talkcraft 源码 SHA-256，在原分辨率渲染每个原版的起始 / 中间 / 结束帧及每个原生竖屏的起始 / 中间 / 结束帧；`npm run catalog:components` 据验证结果更新离线效果页 `out/components/index.html`。具体检查结果以生成的 `out/components/verification.json` 为准。

原先 44 个组件是上游源码的导入与适配，不是官网样片的像素级复刻；字体、文案、演示素材和部分时长有差异。PromptZoom 已恢复官方预览文案、时序和 Inter / Source Serif 4 字体。只有部分组件嵌入这两个字体，其余字体及中文仍使用系统回退。

video-talkcraft 按用户声明的非商业短视频用途导入。108 个 `template/cards` TSX 保持原始字节，哈希记录在 `licenses/community/video-talkcraft/source-manifest.json`；没有安装整套 skill 或工作台。其许可为 PolyForm Noncommercial，完整来源及接入边界见 [源码核查](docs/video-talkcraft-review.md)。[飞书组件表格](https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe) 收录各组件效果、场景、预览及许可。

## 内容边界与素材

受密码保护的飞书文档是本期主来源。原文的个人实践按案例讲述，不写成特定企业的普及率结论。Graph Engineering 在原文中尚无统一定义，因此视频直接解释任务、依赖与交接，没有将它包装成行业标准。

登录页、手机到远程环境流程为教学示意；Multica 小队与看板为用户原文里的截图，不是我们实际搭建的系统或对方企业内部系统。没有虚构效率提升百分比或“10次循环降至1次”的实测结果。评测方案按原文标注为早期验证。

原文提到的两个外部参考已核对：[Claude Managed Agents 概览](https://platform.claude.com/docs/en/managed-agents/overview)、[Multica 项目](https://github.com/multica-ai/multica)。视频没有复制它们的程序代码，也没有将它们的授权延伸到原文图片。
