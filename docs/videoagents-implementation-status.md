# VideoAgents 实现与验证记录

2026-10-03。React 前端、FastAPI API、独立 worker、持久 LangGraph 工作流和 Remotion 生产入口已实现并完成本机联调。设计记录见 [原方案](videoagents-design.md)，操作见 [使用说明](videoagents-setup.md)，接口见 [共享契约](videoagents-implementation-contract.md)。

## 自由选择模型更新

五张角色卡新增 Codex 模型下拉框：CLI 默认、本机缓存中的所有模型（含隐藏项）、自定义模型 ID。模型名称没有固定允许名单，保存和运行仍使用原始 ID。Claude 保留自由输入；选择、刷新或更换提供方不会自动改写其他角色。缓存读取单独使用受会话保护的 `GET /api/models/{provider}`，不启动 CLI，不读 auth/config，不发生成请求。缓存生成时间和权限边界在页面显示；读取失败仍可输入模型名称。

Fresh 验证：**94 Python、38 React、10 Remotion 时间轴测试通过**；Ruff、根 typecheck/lint、React typecheck/build、契约生成一致性检查通过。模型目录新增 23 项回归，覆盖隐藏项、目录外 ID、重复项、可空描述、大小上限、损坏与深层 JSON、UTC 时间、错误脱敏、缓存刷新、凭据文件不读取、会话校验、刷新不写设置及 Claude 自由模型名。

生产页面实际读到本机缓存的 **10 个模型**。浏览器验证不同角色分别选择目录项、隐藏项、自定义 ID 和 Claude 提供方，重读目录保留未保存值，保存后重载保留每角色配置；切换 CLI 仍保留当前自定义 ID。验证后恢复原来的五角色关闭、默认空模型。截图：`out/videoagents-model-selector-review.png`。没有执行真实模型生成，本次模型访问权限尚未付费验证。

本次两条独立审查均 **PASS**，无未解决 P0–P3 或架构阻断。审查发现的 Python 测试同名冲突已通过重命名解决，真实 JSON 深层递归失败已返回固定错误状态。生产服务重启时发现已退出进程的 `StartTime` 为空，补充身份检查保护后，停止/启动脚本与 API、worker 心跳实测通过；PID、启动时间、可执行文件验证保持有效。

## 五角色 CLI 模型配置更新

按最新要求，模型入口改为五角色独立设置，仅支持 `codex_cli` / `claude_code_cli`。React 设置页分别控制启用、提供方、模型名称与超时；模型名称为空使用 CLI 默认模型。PATCH 按角色、按变化字段合并，旧 HTTP 模型字段会被拒绝，原加密记录保留但不再读取。配置影响后续实际调用，已有人工文案、分镜与成片不会自动重做。

- 编剧、导演、审核按各自设置调用 CLI；配音与剪辑新增模型预检/指导产物，音频仍使用字节/真实导入对齐，视频仍由 Remotion 渲染。
- CLI 走固定 argv、UTF-8 stdin、空临时目录、工具限制、取消与超时、输出上限、Windows Job Object。两种 CLI 共用严格 `response_json` 外层，解析后仍由各角色原始 Pydantic 契约验证。
- 成功调用可重放；切换提供方或模型不能绕过当前角色/版本的 UNKNOWN。取消发生于启动前不会创建 CLI 进程；启动后失败的受理状态无法证明，保守记 UNKNOWN。
- 本机实际入口检测及 `--version` 验证：Codex CLI **0.153.4 可用**，Claude Code **未安装**。没有读取登录凭据或执行真实付费模型调用。

本次 fresh 验证：**71 Python 测试、30 React 测试、10 Remotion 时间轴测试通过**；Ruff、根 typecheck/lint、React typecheck/build、生成契约一致性检查通过。CLI 协议、中文 stdin、非法 envelope、错误事件、预取消、启动后取消、超时、输出上限均用独立本机进程 fixture 核验；取消保留任务 CANCELLED 终态及正确提交台账。Windows 回归实际运行 CLI runner 后硬终止 owner，确认 fixture CLI 及派生子进程退出。

正式服务重新启动于 `http://127.0.0.1:8000/`。浏览器实测五角色分别保存、刷新后保留、Claude 未安装提示及恢复默认空模型；测试没有启用付费调用。截图：`out/videoagents-role-models-review.png`。最新 HTTP smoke 任务 **3e782cf2ddcc41ca89ebb2c5e2f760f5** 使用 TEST 图片与测试音，实际渲染 **148891 bytes H.264/AAC MP4**，Range **206**，停在 **NEEDS_HUMAN**；这只证明本机视频链路。

两条独立审查 lane 已完成：代码 lane 没有剩余 CRITICAL/HIGH/MEDIUM/LOW，取消边界 MEDIUM 已修复并回归；该 lane 因工具没有提供其角色提示要求的 `lsp_diagnostics` 而保留 COMMENT，采用 tsc/Ruff/测试作为实际证据。架构 lane 为 **WATCH，无 BLOCK**；配置生效范围与 partial PATCH 的两项建议已落实。残留 WATCH 是 CLI `Popen` 到 Job Object 挂接的小窗口，测试没有证明它被消除；与原渲染进程同样保留这一边界。组织 managed hooks/policy 的隔离限制见使用说明。

## Review 从这里开始

```text
D:\remotion_video\
├─ web/                         React 19 + TypeScript + Vite
│  ├─ src/app/                   布局与 hash 路由
│  ├─ src/pages/                 任务、新建、工作台、组件库、设置
│  ├─ src/features/              文案、素材、配音、分镜、剪辑、审核
│  ├─ src/api/                   会话、HTTP、SSE、轮询与命令身份
│  └─ tests/                     编辑、会话、时间轴与 UNKNOWN 回归
├─ server/                      FastAPI、会话/CSRF、上传、媒体 Range
├─ worker/                      持久命令领取、租约、恢复、进程管理
├─ videoagents/
│  ├─ graph/video_graph.py       StateGraph、条件边、interrupt、恢复
│  ├─ agents/                   编剧、导演、审核
│  ├─ nodes/                    配音及 Remotion 剪辑节点
│  ├─ contracts/                canonical Pydantic 契约
│  ├─ providers/                LLM、搜索、字节、对齐、出站校验
│  ├─ services/                 版本编辑、导入及 write-only 设置
│  ├─ storage/                  SQLite 命令、事件、外部操作台账
│  └─ tools/                    来源、截图、媒体、组件、时间轴
├─ src/video-production/        独立 Remotion 入口与八个生产适配器
├─ contracts/generated/         TypeScript、JSON Schema、OpenAPI
├─ scripts/                     启动/停止、契约导出、渲染与 HTTP smoke
├─ tests/                       API、工作流、provider、worker、进程回归
├─ pyproject.toml + uv.lock      隔离 Python 3.12 环境
└─ package.json + package-lock.json
```

推荐阅读顺序：`web/src/pages/JobWorkspacePage.tsx` → `web/src/api/client.ts` → `server/main.py` → `worker/runner.py` → `videoagents/graph/video_graph.py` → 五个角色 → `src/video-production/VideoFromTimeline.tsx`。React 学习入口另见 [前端说明](../web/README.md)。

运行数据位于 `.runtime/videoagents/jobs/<job_id>/`；受控渲染素材在 `public/videoagents/<job_id>/`。运行数据库、密钥、日志、上传文件和测试输出不加入 Git。

## 已实现行为

- 新建与列表、六阶段工作台、组件目录、服务配置均调用真实 API。刷新页面后读取保存的状态；SSE 重连与轮询不重新启动付费任务。
- 草稿、素材或对齐变更递增版本，使相关分镜、视频和审核失效。编辑状态保留，保存期间保护正在提交的草稿，旧版本写入返回 409。
- 编剧可使用用户文案，或通过搜索与真实来源生成稿件。研究收据在模型请求前冻结，来源文件不可覆盖；实际网页截图可选启用，示意图不作为事实证据。
- 字节 v3 HTTP 流式配音 adapter、复刻音色配置、用户音频导入与实测对齐已接入。音频绑定内容及音色 fingerprint，导演使用所选音频的实测时间，而非按字数估时。
- 八个生产适配器支持横竖画幅：标题、关键词、证据截图、图片聚焦、前后对比、数据卡、步骤、结论。原 152 个组件作为演示参考保留；没有将所有 demo 伪装成可生产组件。
- 最终检查包括实际 MP4 完整解码、分辨率/帧率/时长、对齐文本、产物与素材 hash、来源与用途、渲染依赖绑定。缺少完整视听复核能力时明确要求人完整观看。
- 人工回复绑定版本、依赖 fingerprint、媒体 hash、pending token 和 LangGraph interrupt ID。旧配置回复重放不能回答后来的人审；人工确认不能绕过硬失败。
- 明确的服务拒绝可在修正配置后由新显式命令重试；受理未知则保留 UNKNOWN 台账、阻止盲重提。配音仍可导入实际服务结果与实测对齐进行恢复。

## 初版验证证据

| 检查 | 实测结果 |
|---|---|
| `.venv-videoagents/Scripts/python.exe -m pytest -q` | **47 passed**，包含 API、工作流、付费台账、跨语言契约、worker 与 Windows 进程测试 |
| Ruff（后端、worker、tests、导出和 smoke 脚本） | passed |
| `uv pip check --python .venv-videoagents/Scripts/python.exe` | 58 packages compatible |
| 根 `typecheck` / `lint` | passed |
| React `web:typecheck` / `web:test` / `web:build` | passed，**23 tests / 8 suites** |
| `test:timeline` | **10 passed** |
| `export-contracts.py --check` | passed，生成契约与 Python 一致 |
| 原 `check:component-paths` | 152 对、304 入口、108 个原 source 保留 |
| 原 `check:captions` | 42 页，单页最多 12 字 |
| 开发与正式启动脚本 | 已分别验证 API、worker 心跳与页面；死 worker 可单独重启，保留其他健康服务 |

`scripts/smoke-studio.py` 在没有配置外部 provider 的正式构建服务上实跑：新建 → 保存文案 → 导入 PNG 与两秒测试音/fixture 对齐 → 分镜 → 真实 Remotion H.264/AAC MP4 → 审核。最终任务 **c26828fb58b948e8a1b58d82a2f48e70** 停在 **NEEDS_HUMAN**，没有确认发布。

- MP4：148891 bytes；SHA-256 `4e526af3425ee3918a30b737d6d3811b7a6e622bf367ef4a643de9981e62cd92`。
- 封面：77096 bytes；字幕、文案、研究记录、分镜、时间轴和审核 JSON 可下载。
- HTTP Range 请求返回 **206**，指定 32 bytes 正确读取。
- 正式 React 页面实际播放至结束；浏览器解码结果 **360×640、2.005 秒、readyState 4**。
- 浏览器验证新建、保存新版本、缺配置暂停、实时同步、六工作区、分镜定位、目录授权说明、设置状态及人工确认门槛。
- 额外实渲染覆盖八适配器横屏/竖屏与密集中文内容，并检查画面没有溢出。

本机截图：`out/videoagents-studio-review.jpg`。详细 smoke 收据：`.runtime/videoagents/smoke-evidence.json`。这些 TEST 产物只证明本机链路，测试音不是口播、声音复刻或准确语音对齐的证明。

## 独立审查

两位没有实现代码的审查者分别检查代码/安全与架构/恢复。发现并修复了资料刷新绕过 UNKNOWN、旧音频复用、选定音频未生效、付费鉴权拒绝无法恢复、恢复指令跨 interrupt 重放、SQL/checkpoint 崩溃窗口、保存竞态与 UNKNOWN 显示等问题。

最终代码审查没有剩余 CRITICAL/HIGH/MEDIUM；最后一项 LOW 的模型 UNKNOWN 提示已修正并通过 React 检查。架构审查为非阻断 WATCH。独立审查时实跑 45 个 Python 测试；之后新增两项冻结来源/UNKNOWN 中断回归，主代理最后重跑全部 **47 项**。

## 已声明边界与后续事项

1. 真实 LLM、Tavily、字节自有复刻音色和自动对齐 provider 尚未使用真实凭据进行付费端到端验证。配置后需要用实际样片核验协议、音色、时间戳和成本；未接入的能力明确暂停，不返回假成功。
2. 自动内容检查不能代替完整人耳/人眼复核，也不能承诺平台最终审核或版权授权；发布平台与用途必须明确。本版本生成发布包，不执行平台上传发布。
3. Windows Job Object 的硬终止回归证明**挂接后**的进程树清理；`Popen` 到挂接仍有极窄窗口。后续可用挂起启动、挂接后恢复消除窗口。
4. 渲染完成到 checkpoint 提交之间崩溃允许重新计算本机视频，可能留下无引用的 render 目录；后续补运行目录清理。付费 provider 有独立持久台账，不依赖这类本机重算。
5. `npm audit` 仍报告原 Remotion ESLint 间接依赖的 10 个 high（braces 链），当前依赖树没有可用修复。新加 Vitest 已升级以移除其 advisory；未强行升级原 Remotion 或破坏已有组件。
6. 此工作区原来没有任何 Git 提交，原视频库和用户素材均未跟踪。本次提交只收录新应用和必要根配置/注册改动；原组件、媒体及许可证继续保留在本机。该提交用于本机 Review，并非包含原素材的完整迁移包。

运行方式：`npm run studio:dev`（5173）；正式构建 `npm run studio:start`（8000）；关闭 `npm run studio:stop`。Python 环境为新建 `.venv-videoagents`，原 Python 3.14 `.venv` 保留。
