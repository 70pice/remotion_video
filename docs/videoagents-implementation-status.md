# VideoAgents 实现与验证记录

2026-10-03。React 前端、FastAPI API、独立 worker、持久 LangGraph 工作流和 Remotion 生产入口已实现并完成本机联调。设计记录见 [原方案](videoagents-design.md)，操作见 [使用说明](videoagents-setup.md)，接口见 [共享契约](videoagents-implementation-contract.md)。

## 素材节点优先与跨平台研究更新

起点调整为 `START → materials → screenwriter`。新增独立素材模型配置（Codex CLI / Claude Code CLI），角色总数七个。素材节点采集来源正文、真实图片和网页截图，冻结研究包后交给编剧；导演同时读取出处、说明和知识摘录匹配素材。编剧自身的采集逻辑已移除，文案讨论和人工审核继续保留。完整 **32 项平台目录**、配置、数据交接与素材人工审核示例见 [素材节点](videoagents-materials.md)。

前端增加平台勾选、预算、图片/截图开关及默认素材研究页签。检索方式、结果数、不可用/失败/预算耗尽、来源快照、登记图片与出处可查看。原生工具和公开索引分开记录；未接入账号原生能力的平台不声称已登录可用。Google 检索支持本机 OpenCLI，Tavily/已有 Google CSE 保留。

最终全量 **300 Python、60 React 测试通过**；Ruff、共享契约一致性、根 TypeScript/lint、React typecheck/build 通过。新回归覆盖图顺序、素材暂停/恢复、来源与视觉交接、部分失败、域名过滤、图片归属、失败图片兜底、冻结重放、UNKNOWN 结果限额变化保护、原生子进程取消及提交水位竞态。独立静态审查提出的三个 P2 已修复并通过定向回归。

真实只读联调使用“Muse是什么”：Google 原生 OpenCLI 和 Reddit 的 Google 公开索引均返回结果；读取 4268 字符来源正文并登记网页截图。首轮成功下载真实 JPEG，复测时同 CDN 返回 ConnectError，失败按实记录，截图继续可用。该联调限定两个平台、一个来源、两个视觉尝试，证明本机获取链路，不代表 32 个平台全部可访问，也没有调用语言模型、配音或渲染。联调收据在 `out/videoagents-materials-live-evidence.json`，使用独立测试运行库。

正式工作台已刷新于 `http://127.0.0.1:8000`，首页 200、worker 心跳正常；公开设置返回七角色和 32 项工具，无原始密钥。已配置本机 OpenCLI Google、截图和真实图片下载；原有各角色模型及配音设置未被替换。

浏览器联调确认 32 个平台控件、素材独立模型和实际研究包/登记图片加载，无浏览器运行错误。素材页面使用独立联调任务的真实回执作为只读 fixture，没有在正式库创建示例任务。界面截图为 `out/videoagents-materials-settings-review.png` 与 `out/videoagents-materials-workspace-review.png`。独立复审重新执行四项修复回归通过，三个 P2 均已关闭。

## VideoState 通用上下文更新

`VideoState` 扩展为贯穿全部节点的业务上下文：任务要求、文案与讨论、研究来源、素材和媒体元信息、音频/对齐、朗读与剪辑指导、分镜、产物、审核与人工记录、公开设置及操作/预算记录都在同一字典中。`extras` 接收自定义 JSON 数据并浅合并，遗漏保留、显式 null 留值。真实媒体保存引用，密钥和运行时连接留在服务/节点对象中。字段、调用和自定义节点示例见 [通用上下文](videoagents-context.md)。

内置节点入口将上下文中的合法 `brief/script/timeline/assets` 增量先保存，再推进阶段或人工待办；完成后返回最新完整上下文。身份、版本、状态、审批与提交凭据由持久化流程管理，SQL 领先 checkpoint 时复用已提交结果，旧精简 checkpoint 在节点入口补全。业务变更使旧下游产物失效；已冻结讨论或人工待办必须通过新版本修改。新执行不会复用上一次执行的讨论策略。素材增量必须绑定当前任务的已登记文件、hash/大小/MIME/URL、受控路径及音频实测元信息。

Fresh 验证：新增 **26 项上下文回归**，全量 **270 Python 测试通过**；Ruff、生成契约一致性、React typecheck 通过。覆盖真实 LangGraph 自定义节点部分交接、SQLite 关闭重开、旧 checkpoint、SQL 领先、版本/取消、清空字段、JSON 限制、公开配置、指导与人审回执，以及合法/缺失/跨任务/篡改素材。独立审查发现的素材归属 P2 已修复并回归，最终无遗留可行动问题；正式判定为 COMMENT，因为该 lane 不提供 LSP，采用 Ruff、Python 编译与定向回归验证。

确认没有 PENDING/CLAIMED 命令后重启本机 API/worker。首页 HTTP 200、API health 和 worker 心跳正常；受会话保护的设置接口仍返回六角色且不包含密钥。本次未调用实际 CLI 模型、配音或渲染服务，HTTP Job 契约及前端界面保持兼容。

## 编剧与文案审查讨论更新

参考同级 TradingAgents 的多空辩论：节点顺序交替，将历史写入共享 state，并用计数限制轮次。新增 `nodes/script_reviewer.py`，与 `ScreenwriterNode` 在文案阶段循环；审查给出结构化问题，编剧读取历史及意见生成完整修改稿和回应。通过后进入原有来源/素材硬检查，达到上限仍需修改则暂停。默认关闭，启用后默认 2 轮，可配置 1–5 轮；编剧与文案审查各自选择 CLI 和任意模型 ID。源码、状态和操作见 [文案讨论说明](videoagents-script-discussion.md)。

React 设置页增加第六张模型卡及讨论配置，文案工作区显示每轮完整稿件、来源/素材引用、意见、建议、回应和已完成审查轮数。开关及轮数在本次执行首次调用模型前冻结；模型设置仍影响后续实际调用，UNKNOWN 继续阻止同角色/版本重复提交。讨论和稿件保存为不可变 JSON，SQL 已保存但 checkpoint 未保存的恢复会复用已有轮次。编辑、素材导入或对齐形成新版本时清空旧讨论。

Fresh 验证：本次新增 **21 项后端回归**（18 项讨论、2 项节点保护、1 项设置 API），全量 **244 Python、56 React 测试通过**；Ruff、契约一致性、React typecheck/build、根 typecheck/lint 和 10 项 Remotion 时间轴测试通过。覆盖真实改稿、1/5 轮上限、缺模型恢复、矛盾审查输出、假来源拒绝、来源硬检查、UNKNOWN 模型切换、冻结开关/轮数、首稿/改稿/审查保存后的 checkpoint 崩溃重放及版本清空。独立审查发现同版本自动改稿后的旧视频引用问题，修复后回归验证仅改稿时清空当前下游引用；审查最终 **APPROVE，无遗留可行动问题**。

本机服务已重启，首页 HTTP 200、API health 和 worker 心跳正常；受会话保护的设置接口实测返回六角色、讨论默认关闭及最多 2 轮。本次未调用真实 CLI 模型、配音或渲染服务。前端验证采用组件测试和构建，浏览器 CDP 连接超时，未把该次浏览器检查算作成功。

## 节点代码合并更新

删除 `videoagents/agents/`，编剧、配音、导演、剪辑和审核统一为 `videoagents/nodes/` 下的 callable 节点类。各类的 `__call__(state)` 直接完成阶段执行、保存和路由；图中不再有 `node_*` 包装方法及动态 `getattr` 注册，只保留明确的 `add_node`、连线、checkpoint 和命令执行/恢复。检查节点集中在 `nodes/gates.py`，等待输入及最终人工确认在 `nodes/await_input.py`；可编排人工审核保持原入口。结构与调用说明见 [节点说明](videoagents-nodes.md)。

保持原有节点名、路由和状态契约，CLI 角色配置及外部操作台账不变。新增加 **23 项节点独立调用及版本/取消回归**，全量 **223 Python、51 React 测试通过**；Ruff、契约一致性、React typecheck/build 通过。已有人工审核、崩溃恢复与 UNKNOWN 测试继续通过。服务在确认无等待/执行命令后重启；本次没有执行实际模型、配音或视频渲染调用。

五角色业务方法的 AST 对比确认搬迁前后语句一致；独立代码审查无可行动问题，95 项定向回归、Ruff 及 Python 编译检查通过。审查环境没有 `lsp_diagnostics` / `ast_grep_search`，使用上述检查替代；审查正式标记为 COMMENT，没有声称完成不可用工具的验证。重启后首页 HTTP 200、API health 及 worker 心跳正常。

## 可编排人工审核节点更新

新增独立 `HumanReviewNode` 和 `add_human_review()` 注册入口。默认图增加 `human_review`，没有接入主流程；用户可替换任意阶段的成功分支，配置标题、检查清单、阶段、说明长度和通过后的节点，也可串联多个审核点。编排示例见 [人工审核节点](videoagents-human-review.md)。确认继续，返工停止等待版本编辑，取消结束；确认通向 END 时任务回到 DRAFT，阶段确认不会生成发布资格。

复用现有 SQLite checkpoint、恢复 API 和 interrupt ID/token 绑定。待审输入覆盖当前文案、分镜、素材、真实文件 hash 及音频对齐元数据；内容、版本或审核要求变化后的旧回复不能通过。审核记录使用稳定文件及 artifact ID，恢复不会重复生成记录。React 工作台顶层提供阶段审核卡，无需已生成成片；最终成片审核继续保留。

Fresh 验证：新增 **21 项后端、8 项前端测试**，总计 **200 Python、51 React 测试通过**；Ruff、契约一致性及 React typecheck/build 通过。回归覆盖默认流程不变、暂停后重建图恢复、confirm/revise/cancel、短说明新待办、过期 token、内容/配置/文件/对齐元数据变更、串联两个审核点，以及 SQL 保存后 checkpoint 前的确认和新问题崩溃恢复。现有认证 API 可恢复阶段审核并读取记录；React SSR 验证无需成片也显示审核卡且隐藏最终成片确认。未发起实际模型、配音或渲染调用。生产服务已重启，HTTP 200 和 worker 健康检查通过。

## 字节双向 WebSocket 配音更新

按用户提供的[新版 SOP](https://docs.volcengine.com/docs/DoubaoVoice/bidirectional-streaming-text-to-speech-websocket?lang=zh)接入 `byte_ws`：API Key +资源 ID 鉴权、可配置语音模型、24 kHz MP3 和真实字幕事件 364。保留旧 HTTP。React 声音卡独立配置语音合成模型，隐藏 WebSocket 不使用的旧 App ID/令牌；五角色 CLI 配置保持独立。用户凭据只写入 Windows DPAPI 保护的运行数据库，公开 API 仅返回已配置状态。

正文发送前持久化台账并再次检查取消；会话匹配的 152 与非空音频确认调用完成，随后由现有解码/时长/全文对齐检查决定是否交给导演。发送后不确定结果按 UNKNOWN 暂停，切换 HTTP/WebSocket 或模型不能绕过。配音指导期间修改配置的两处指纹竞态已修复：选择旧音频前刷新配置，新音频使用 provider 实际请求指纹。

本机代理 DNS 将字节域名映射到 `198.18.0.9`，原公共地址检查在正文提交前正确拒绝。已增加仅针对全部 `198.18.0.0/15` 结果的固定 Cloudflare DoH 回退，仍要求全部真实公网答案与字节原域名 TLS 验证。没有修改系统 DNS，也不向 DNS 服务发送密钥、音色或文案。联调还识别并清理了同工作区遗留旧 worker；它没有创建外部配音提交。

Fresh 验证：**179 Python、43 React、10 Remotion 时间轴测试通过**；Ruff、根 typecheck/lint、React typecheck/build、契约一致性、Python 依赖检查通过。两条独立审查为 **APPROVE / CLEAR**，取消与指纹两项 P2 已关闭，DoH 增量独立审查通过。

真实短语音任务 `88b8e95c2bdd4629bf166fccbfd9cf42` 已成功调用用户提供的音色，收到会话完成并保留 **22893 bytes、2.856 秒、单声道 24000 Hz MP3**，FFprobe 解码信息有效。只发送过一条短正文；首次网络失败明确发生于连接阶段，修正网络后以新命令恢复，同一个操作的第二次连接成功。字幕返回 8 个词，两个置信度低于既有 0.8 阈值（约 0.168 / 0.740），所以任务正确停在 **NEEDS_INPUT / alignment**，没有进入剪辑或降低门槛。音频及服务商真实时间戳已保留，可配置可靠对齐服务或人工试听核对后继续，恢复时复用已完成的配音。

截图：`out/videoagents-byte-ws-settings-review.png`；私有运行收据：`.runtime/videoagents/byte-ws-live-evidence.json`；音频在该任务的 operations 目录。音色听感需由用户试听，短调用成功不等于完整视频发布审核通过。

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
│  ├─ graph/video_graph.py       StateGraph 注册、条件边、checkpoint 与恢复
│  ├─ nodes/                    六角色、阶段检查、人工审核及等待输入节点
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

推荐阅读顺序：`web/src/pages/JobWorkspacePage.tsx` → `web/src/api/client.ts` → `server/main.py` → `worker/runner.py` → `videoagents/graph/video_graph.py` → `videoagents/nodes/` → `src/video-production/VideoFromTimeline.tsx`。节点修改与调用入口见 [节点说明](videoagents-nodes.md)，React 学习入口另见 [前端说明](../web/README.md)。

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

1. 真实 LLM、Tavily 和自动对齐 provider 尚未付费端到端验证。字节自有音色已完成一次真实短配音验证，字幕因两个低置信度词暂停在对齐关卡，尚未用该音色完成视频全流程。未接入或未可靠验证的能力明确暂停，不返回假成功。
2. 自动内容检查不能代替完整人耳/人眼复核，也不能承诺平台最终审核或版权授权；发布平台与用途必须明确。本版本生成发布包，不执行平台上传发布。
3. Windows Job Object 的硬终止回归证明**挂接后**的进程树清理；`Popen` 到挂接仍有极窄窗口。后续可用挂起启动、挂接后恢复消除窗口。
4. 渲染完成到 checkpoint 提交之间崩溃允许重新计算本机视频，可能留下无引用的 render 目录；后续补运行目录清理。付费 provider 有独立持久台账，不依赖这类本机重算。
5. `npm audit` 仍报告原 Remotion ESLint 间接依赖的 10 个 high（braces 链），当前依赖树没有可用修复。新加 Vitest 已升级以移除其 advisory；未强行升级原 Remotion 或破坏已有组件。
6. 此工作区原来没有任何 Git 提交，原视频库和用户素材均未跟踪。本次提交只收录新应用和必要根配置/注册改动；原组件、媒体及许可证继续保留在本机。该提交用于本机 Review，并非包含原素材的完整迁移包。

运行方式：`npm run studio:dev`（5173）；正式构建 `npm run studio:start`（8000）；关闭 `npm run studio:stop`。Python 环境为新建 `.venv-videoagents`，原 Python 3.14 `.venv` 保留。
