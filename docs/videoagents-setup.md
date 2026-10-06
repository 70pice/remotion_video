# VideoAgents 使用说明

本项目新增完整 React 工作台，沿用已有 Remotion 组件库。Python 负责工作流、来源记录、音频与审核，Node 负责按冻结时间轴渲染。API 和 worker 分别运行，关闭浏览器不会终止后台任务。

## 首次安装（Windows PowerShell）

在 `D:\remotion_video` 执行：

```powershell
npm install
$env:UV_PROJECT_ENVIRONMENT = '.venv-videoagents'
uv sync --python 3.12
```

需要 Node 24、uv、Python 3.12、FFmpeg 和 FFprobe。本次开发使用独立 `.venv-videoagents`，原有 `.venv` 保留。依赖版本记录在 `package-lock.json` 和 `uv.lock`。

需要自动截取来源网页时，再安装 Playwright 浏览器：

```powershell
.venv-videoagents/Scripts/python.exe -m playwright install chromium
```

首次 Remotion 渲染会准备 Chrome Headless Shell，需要联网。素材节点现在统一调用模型，即使已有文案、图片和音频，也需要启用素材角色的 Codex CLI，或已有同版本冻结研究包。

## 启动与关闭

```powershell
npm run studio:dev
```

浏览器打开 `http://127.0.0.1:5173`。React 开发端口 5173，API 端口 8000；Vite 转发 `/api`。脚本启动 API、独立 worker 和前端，验证 API、worker 心跳和页面后才提示可用。进程与日志记录在 `.runtime/videoagents`。

构建并运行同源页面：

```powershell
npm run web:build
npm run studio:start
```

打开 `http://127.0.0.1:8000`。切换开发/构建模式前，先关闭已有工作台：

```powershell
npm run studio:stop
```

关闭脚本核对记录的 PID、启动时间和可执行文件，只停止本次工作台及其子进程。正在渲染时关闭会中断渲染；重启 worker 会根据持久化记录恢复或明确报告需要补充的信息。

## 自动生产

1. 在「设置」分别配置素材、编剧、文案审查、配音、导演、剪辑和审核的 CLI 提供方、模型名称和超时，并启用需要的角色。当前仅支持 Codex CLI 与 Claude Code CLI；模型留空使用对应 CLI 默认模型。素材默认选择「Codex 技能研究」，通过已安装技能检索并保存真实素材；Claude Code 或原有采集方式请选择「固定检索工具」，可使用 OpenCLI Google、Tavily 或已有 Google CSE。平台和预算见 [素材节点与完整平台目录](videoagents-materials.md)，安装清单和当前可用条件见 [研究技能环境](videoagents-research-skills.md)。
2. 配置字节配音：按新版 SOP 选择「字节 WebSocket 双向流式」，填写声音 ID、资源 ID 和 API Key。声音复刻 2.0 使用 `seed-icl-2.0`，语音合成模型默认 `seed-tts-2.0-expressive` 并附带短视频讲述风格；需要稳定但不接受情绪指导的普通合成时，可改用 `seed-tts-2.0-standard`，见 [配音表现力设置](videoagents-voice-performance.md)。资源及音色权限须由实际账号验证。旧 HTTP 接口仍可选择，兼容 API Key 或 App ID + Access Token。
3. 创建任务，输入主题或文案，设定受众、用途、画幅、帧率和来源链接。
4. 执行生产，按素材研究 → 编剧及可选文案讨论 → 配音 → 导演 → 渲染 → 审核推进。「素材研究」页签显示来源快照、图片与截图、检索方式及失败项。缺服务、缺授权记录或缺真实时间戳时，会显示待补充信息。
5. 在各阶段查看、编辑文案与素材。修改会递增版本并使相关产物和审核失效。
6. 查看成片和审核问题，按问题时间跳转播放，补充材料或修订。明确发布平台与用途、通过硬性检查后，需要人完整观看当前成片并填写复核记录，才进入 `READY_FOR_PUBLISH`。通用画幅选项不能替代具体发布平台。

`READY_FOR_PUBLISH` 表示本系统的发布前检查完成，实际平台的审核结果由平台决定。本版本产出可下载视频，不自动发布。

字节 WebSocket 使用固定官方地址 `wss://openspeech.bytedance.com/api/v3/tts/bidirection`，以 `X-Api-Key` 和 `X-Api-Resource-Id` 鉴权，不需要 App ID。合成模型与各角色的 CLI 模型分别配置；标准模型也可改为账号支持的原始语音模型 ID。音频输出为 24 kHz MP3，开启 `enable_subtitle`，收取服务端单词时间戳；字幕可能晚于音频，所以持续接收到当前会话的 `SessionFinished`。只有会话完成且收到音频才记录调用完成；随后仍检查音频能否解码、真实时长与全文对齐。缺少有效时间戳时保留已生成音频，等待真实对齐，不按字数猜时间。[官方调用 SOP](https://docs.volcengine.com/docs/DoubaoVoice/bidirectional-streaming-text-to-speech-websocket?lang=zh)。

连接/启动会话阶段没有提交正文，失败记为 `REJECTED`，修正配置后可用新命令重试。在发送正文前先持久化提交状态；之后超时、取消、服务错误或断流都按 `UNKNOWN` 暂停。同一版本更换 HTTP/WebSocket、音色或模型不能绕过未知提交；可对账或导入服务商已生成的真实音频。请求 ID 不代表服务商承诺的幂等保证。WebSocket 支持接收期间取消；旧 HTTP 的取消仍在节点边界生效。旧 HTTP 要求流终止成功码与音频，协议见[字节 HTTP 文档](https://www.volcengine.com/docs/6561/1598757?lang=zh)。

如果本机代理使用 `198.18.0.0/15` 虚拟 DNS 地址，WebSocket 仅在系统返回全部属于该网段时，使用固定 Cloudflare 公网入口的加密 DNS 查询获得字节域名的真实公网地址。查询只包含固定公开域名，不包含密钥、音色或文案；最终连接仍校验字节官方域名的 TLS 证书。其他私网地址和混合解析继续拒绝，不修改系统 DNS。[Cloudflare DNS over HTTPS](https://developers.cloudflare.com/1.1.1.1/encryption/dns-over-https/)。

## 每个角色的模型设置

设置页的七张卡独立保存，不共享全局模型。默认全部关闭；启用后，角色运行会启动其选择的本机 CLI。修改配置只影响后续实际调用，不会自动重做已有文案、分镜或成片。文案讨论开关也默认关闭，启用后默认最多两轮：编剧提交 → 文案审查 → 需要修改时编剧回应并改稿 → 再次审查；通过才进入来源硬检查，达到上限仍未通过则暂停。配置、工作区和恢复说明见 [文案讨论](videoagents-script-discussion.md)。各角色的模型作用如下：

Codex 每张卡可选择「CLI 默认模型」、CLI 模型列表中的模型或「自定义模型」。工作台通过与角色调用相同的可执行入口运行 `codex debug models` 查询目录，完整保留 CLI 返回的模型，包括隐藏项，不使用固定模型名单。「刷新模型列表」重新查询当前 CLI，不发起模型生成；列表刷新不覆盖未保存的角色配置。[官方 CLI 命令说明](https://learn.chatgpt.com/docs/developer-commands?surface=cli)。

CLI 版本不支持查询命令、查询失败或超时（12 秒）时，回退到 `$CODEX_HOME/models_cache.json`；未设置 `CODEX_HOME` 时使用用户目录下 `.codex`。页面会显示回退原因。共享缓存可能由其他 Codex 版本写入，也可能过时；模型列表不证明调用一定成功。未列出所需模型时仍可选择「自定义模型」，填写 CLI 支持的原始模型 ID；工作台不会以目录作为允许名单，保存后原样传给 `--model`。留空使用 CLI 默认模型。Claude Code 当前直接填写模型名称。工作台不自行读取登录凭据，目录查询由 CLI 管理认证，不创建生成会话。`gpt-reserve` 是 CLI 目录返回的隐藏模型 ID，隐藏标记不代表文件夹，也不证明它对应哪个公开版本。[官方缓存格式](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/models-manager/src/cache.rs#L61-L78)、[官方模型字段](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/codex-rs/protocol/src/openai_models.rs#L390-L402)。

| 角色 | 模型职责 | 后续执行 |
|---|---|---|
| 素材 | 默认由 Codex 读取检索技能，完成跨平台研究、歧义判断与真实文件清单；可切回固定工具规划 | 核验实际正文/图片文件、来源关联与 SHA256，冻结后交给编剧与导演 |
| 编剧 | 根据冻结的真实来源生成初稿，讨论轮读取反馈并改稿 | 本地校验事实来源与素材引用 |
| 文案审查 | 与编剧讨论事实、逻辑、开头吸引力、口播与画面，给出通过或修改决定 | 继续改稿，或通过后进入来源硬检查；达到上限等待修改 |
| 配音 | 检查读音、停顿、情绪和文案风险，保存 `voice_guidance` | 字节生成实际音频，或使用导入音频及实测对齐 |
| 导演 | 按实际音频时间选择镜头、构图与组件 | 验证帧区间、素材白名单和字幕不可被篡改 |
| 剪辑 | 检查节奏、文字密度与排版风险，保存 `editing_guidance` | Remotion 真实渲染 |
| 审核 | 核验来源、文案与分镜的语义关系 | 媒体硬检查与完整成片人工复核 |

已有人工文案与人工分镜优先使用。启用文案讨论后，人工文案也会先送审，需修改时由编剧模型改稿；需要保留人工稿不改时可关闭讨论。配音/剪辑指导中的阻塞问题会暂停任务，修改对应内容后再执行。模型不能生成假音频、假截图、字幕时间或任意可执行代码。

需要在任意阶段增加人工审核时，使用已注册但尚未接入主流程的 `human_review`，或注册多个审核点；编排示例见 [人工审核节点](videoagents-human-review.md)。

CLI 必须安装在启动 API 和 worker 的同一系统用户下，使用 CLI 自己的登录状态。工作台不收取模型 API Key，也不读取或复制 CLI 登录凭据。先用终端的 `codex --version` / `claude --version` 检查安装，再按相应 CLI 的登录流程完成认证，重新启动工作台，使新 PATH 生效。设置页的「可用」仅证明找到了启动文件，不能证明登录、额度或模型访问权限有效。2026-10-04 本机 Codex CLI 已升级到 `0.159.2`，尚未安装 Claude Code。

2026-10-04 核对过一次 App 与 CLI 不一致：App 内置 `0.159.2`，PATH 中的两处 npm 安装均为 `0.153.4`。同一账号、同一个 `gpt-6.1-sol`、同一套工作台隔离参数下，旧版返回「不支持 ChatGPT 账号使用该模型」，新版成功。两处 npm 安装升级到 `0.159.2` 后，工作台实际 `run_cli` 调用也返回了有效结构化结果。这是本机当日验证结果；以后遇到类似问题，应先比较实际执行入口与版本，而不能仅凭模型缓存或错误文案判定账号没有权限。`Get-Command codex -All` 可检查多处安装；升级后的新调用会使用新版，已启动的旧 CLI 会话仍使用原进程。

App 当前对话选中的模型、用户 `config.toml` 的默认模型、工作台七个角色保存的模型是不同的配置位置。工作台使用 `--ignore-user-config` 隔离用户工具和规则，并将每个角色选择的模型通过 `--model` 传入；留空使用隔离调用的 CLI 内置默认值，不继承 App 当前对话的模型。GPT 6.1 的原始模型 ID 为 `gpt-6.1-sol`，可以在 Settings 为各角色分别选择。[官方模型选择说明](https://learn.chatgpt.com/docs/models)。

如果 CLI 不在 PATH，可在启动工作台前设置 `VIDEOAGENTS_CODEX_EXECUTABLE` 或 `VIDEOAGENTS_CLAUDE_EXECUTABLE` 为绝对入口路径。Windows 支持 `.exe`、官方 npm shim 或 `.js` 入口；npm shim 转为 `node.exe + 官方入口`，不执行拼接的 shell 命令。模型名称也作为独立 argv 传入。超时范围为 30–1800 秒，每任务版本的模型调用上限统一由 `max_llm_calls` 控制。

每次调用使用临时空目录及结构化输出，避免加载项目指令。Codex 使用 read-only、ephemeral、忽略用户配置/规则、禁止 shell/多代理/插件/浏览器等功能；调用启动时从用户 `CODEX_HOME` 读取登录态，在临时 `CODEX_HOME` 中隔离 SQLite/日志写入，并在 `thread.started` 后删除临时认证副本，任务目录不会保存凭据。Claude 禁用内置工具与普通 hooks，限定空 MCP 配置，禁止持久会话。工具事件或未知协议会终止调用。组织管理策略可能施加额外配置或 hooks，这些设置不能被工作台承诺完全覆盖。Codex 的事后工具事件检查也不是工具执行前的完全隔离保证。

成功结果与使用量写入持久台账，相同输入重放复用成功结果；更换模型/CLI不能绕过该角色当前版本的未知提交。仅明确启动前失败允许新显式命令重试。CLI 启动后的超时、取消、错误退出或输出不完整均按 `UNKNOWN` 处理，因为无法证明服务方未计费。工作台不显示未经清理的 CLI 错误输出。协议回归验证使用独立的本机 subprocess fixture；2026-10-04 已通过实际 Codex CLI 验证 `gpt-6.1-sol` 的最小结构化调用，未因此重跑已有视频任务或清除未知提交记录。

实现参考：[Codex 非交互调用](https://developers.openai.com/codex/noninteractive)、[Codex CLI 参数](https://developers.openai.com/codex/cli/reference)、[Claude CLI 参数](https://code.claude.com/docs/en/cli-reference)、[Claude 程序化调用](https://code.claude.com/docs/en/headless)。

CLI 外层只接收必填 `response_json` 字符串、拒绝额外字段，解码后再由各角色的 Pydantic 契约验证业务对象。这保留时间轴的默认值与允许的组件属性，同时符合 Codex 严格 schema 子集；不会把字符串包装本身当作业务校验。参考：[Codex 对应版本严格输出测试](https://github.com/openai/codex/blob/3d2ee51ca2d5db578f328aa75e20aa22c0197c9a/sdk/typescript/tests/run.test.ts#L583-L627)、[严格输出 schema 规则](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)。

## 暂不接外部 API 的本机路径

1. 创建带完整文案的任务；保存编剧产出的段落后查看每段 `segment_id`。
2. 上传真实图片或网页截图，填写来源与授权说明；示意图选择 illustration，不把示意图作为事实证据。
3. 上传本地 MP3/WAV 等音频，并上传经过验证的对齐 JSON。音频须对应当前文案，字幕时间来自实际音频。
4. 生成分镜，或在分镜面板编辑镜头并选择组件。组件下拉会按任务用途开放统一生产清单：9 个可传入真实文案/数据/图片/视频的参数化适配器，加 152 个会自动匹配横版或原生竖版实现的固定视觉预设。固定预设不接收素材和自定义 props；Talkcraft 预设受非商业许可限制，商业任务不会出现。
5. 渲染预览、生成最终视频并运行审核。

对齐文件格式：

```json
{
  "origin": "manual",
  "verified": true,
  "audio_sha256": "填写上传音频实际SHA-256，共64个十六进制字符",
  "segments": [
    {"segment_id": "s1", "text": "与本段文案一致", "start_ms": 0, "end_ms": 2100}
  ],
  "note": "实际试听核对记录"
}
```

同一段可拆成多条实测字幕，每条不超过 72 字，按时间排序且不能重叠，合并文字须与对应口播段一致。上传或单独补充对齐时，服务端绑定所选音频的实际哈希；如果提交了非空哈希，必须匹配。切换所选音频会读取它自己保存的对齐记录。不会用字数平均分摊伪造对齐。

## 数据与 Review 入口

```text
web/src/                     React 页面、编辑器、API 与事件订阅
server/                      FastAPI、会话、上传与媒体服务
worker/                      持久任务领取、执行与恢复
videoagents/contracts/       Python 数据契约
videoagents/graph/           LangGraph 节点与路由
videoagents/providers/       模型、搜索、字节配音与对齐服务
videoagents/services/        版本编辑、导入与设置
videoagents/nodes/           六角色、阶段检查、人工审核及等待输入节点
videoagents/storage/         SQLite 命令、事件与外部操作台账
src/video-production/        9 个生产适配器、152 个预设注册与时间轴验证
contracts/generated/         由 Python 导出的类型、JSON Schema、OpenAPI
scripts/*studio*.ps1          本机启动与停止
tests/                       后端、工作流与联调测试
.runtime/videoagents/        本机数据库、日志、运行记录（不入 Git）
.runtime/videoagents/jobs/   单任务素材与各版本产物（不入 Git）
public/videoagents/          渲染用受控素材（不入 Git）
```

Windows 配置密钥使用当前用户的 DPAPI 加密后保存在运行数据库，不返回给浏览器，也不放入图状态、时间轴、事件或 Git。恢复加密凭据需要原 Windows 用户；备份运行目录仍按私有配置保存。非 Windows 的兼容路径仅限制文件权限，不提供同等凭据加密。素材来源及授权说明由用户和提供方给出；填写说明不等于系统获得版权许可。

接口契约由 Python 导出；改契约后执行：

```powershell
.venv-videoagents/Scripts/python.exe scripts/export-contracts.py
```

## 验证与故障排查

```powershell
.venv-videoagents/Scripts/python.exe -m pytest
.venv-videoagents/Scripts/python.exe -m ruff check server worker videoagents tests scripts/export-contracts.py
.venv-videoagents/Scripts/python.exe scripts/export-contracts.py --check
npm run typecheck
npm run lint
npm run test:timeline
npm run web:typecheck
npm run web:test
npm run web:build
npm run check:component-paths
npm run check:production-components
```

纯本机接口联调：启动隔离且未配置模型、搜索、配音或对齐服务的工作台，运行 `.venv-videoagents/Scripts/python.exe scripts/smoke-studio.py`。脚本验证素材模型关闭时暂停在 `materials`，再导入标记为 TEST 的文案、程序图案和测试音，验证媒体 Range 请求及再次执行仍暂停。它不调用付费服务，也不生成成片；下游流程使用已冻结的测试研究包在 Python 工作流测试中验证。测试音与 fixture 字幕不能作为真人口播、复刻声音或发布资格的证明。

- 端口占用：先执行 `npm run studio:stop`。脚本不会停止不属于本工作台的进程；若仍占用，检查端口对应的应用。
- 页面显示 worker 离线：查看 `.runtime/videoagents/*worker*.stderr.log`，确认独立 worker 已启动。
- 返回 409：任务版本已更新或正在执行，刷新读取当前版本后继续，避免旧页面覆盖新结果。
- 缺音频时间戳：补充真实对齐文件；已有音频不代表有准确字幕时间。
- `UNKNOWN` 外部操作：请求可能已被服务商接受，后台保留未决台账并暂停提交。先核对服务商记录和已有产物，配音可导入实际音频与实测对齐；不要直接重复提交。已确认被拒绝的鉴权请求可以在修正配置后通过新的显式命令重试。
- 网页截图失败：检查 Chromium 是否安装、来源是否公开可访问，再上传实际截图。登录页截图不会被当作目标页面内容。
- 渲染失败：查看任务错误和渲染日志，核对受控素材、时间轴、FFmpeg 与浏览器依赖。

真实模型需要对应 CLI 安装、登录及模型权限；搜索与复刻声音需要有效服务凭据。本机测试素材的成功不能证明这些外部服务已可用。
