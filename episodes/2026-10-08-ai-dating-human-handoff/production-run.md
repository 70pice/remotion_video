# AI 聊天与真人验证：独立视频任务

- 分支：`episode/2026-10-08-ai-dating-human-handoff`
- 分支起点：`aa0f4e6`
- 任务 ID：`1a024549ad334d4dafe782f64c9e61f0`
- 初始版本：1
- 创建时间：2026-10-08（Asia/Shanghai）
- 输入：[production-brief.json](production-brief.json)
- 规格：个人用途，抖音竖屏，1080×1920，30 fps，目标约 240 秒。
- 一手核实对象：[Anthropic 2026 年 9 月威胁情报报告](https://www.anthropic.com/threat-intelligence-report-september-2026)中的 `GTG-15001: Deceptive dating app network`。

本次是新建任务，创建时 `script=null`、素材列表为空、时间线为空。通过 `POST /api/jobs` 创建（HTTP 201），通过 `POST /api/jobs/{job_id}/runs` 提交 `action=produce`（HTTP 202），由独立 Worker 运行 `VideoProductionGraph`。API 回读的 brief 与本地 UTF-8 输入完整一致。

生产顺序：素材研究 → 编剧及文案审查 → 文案人工确认 → 配音指导与合成 → 音频校验 → 导演组件学习及时间轴校验 → 剪辑渲染 → 结束。文案人工确认前不进入配音。缺输入与失败恢复使用项目入口。

## 第一版执行记录（已返工，不能用于确认当前稿）

- 第一版停在 `NEEDS_HUMAN` / `script`，暂停节点为 `human_review_script`，文案未获人工确认。
- 实际执行链：`materials → clear_materials → screenwriter → clear_screenwriter → script_reviewer → clear_script_reviewer → human_review_script`。素材与文案来自本次任务的 Graph 节点。
- 素材节点冻结了 2 条来源、6 个证据素材。主要事实来自 Anthropic 原始报告；另一条 YouTube 解说为同源转述，不能视为独立核实。
- 机器文案审查结果为 `APPROVE`，讨论状态为 `APPROVED`，没有最终返工轮。
- 已通过 API 下载并复核本版本 13 个登记产物的 SHA-256，全部匹配。人工待办绑定当前版本与实际产物。
- 未进入配音、导演或剪辑，未生成成片。后续状态以任务 API 和 Graph 持久化记录为准。
- 私有提交回执保存在 `.runtime/videoagents/ai-dating-human-handoff-submission.json`，任务产物由 Graph 保存到 `.runtime/videoagents/jobs/1a024549ad334d4dafe782f64c9e61f0/`。
- 私有流程事件及验证结果保存在 `.runtime/videoagents/ai-dating-human-handoff-evidence.json`。

## 流程记录

以下时间为 2026-10-08，Asia/Shanghai，来自任务事件回读：

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| 20:26:29 | 新建任务并提交 `produce` | `created` / `queued`，事件 2863、2864 |
| 20:26:30 | Worker 启动素材节点 | 事件 2865 |
| 20:37:12 | 素材冻结并进入编剧 | `research` 产物及事件 2878 |
| 20:39:58 | 初稿保存，进入文案审查 | `script` / `script_discussion` 产物及事件 2881 |
| 20:42:28 | 机器审查通过，进入人工审稿 | `APPROVED` / `APPROVE`，事件 2883、2884 |

## 工作台与第一版审稿资料

- 本机工作台：http://127.0.0.1:8000/#/jobs/1a024549ad334d4dafe782f64c9e61f0
- [待人工审读的口播稿](script-for-human-review.md)：仅按原文整理节点实际产出，没有人工改写。
- [Graph 文案 JSON](graph-script.json)：保留段落 ID、来源与素材关联。
- [Graph 机器审查 JSON](graph-script-discussion.json)：保留实际审查决定及意见。

按项目制作约定第 8 条，必须由用户人工审稿，再通过任务 API 的 `resume` 入口确认或返工；不能由操作者伪造通过。

## 普通观众反馈返工

用户收到第一版文案、6 张原始证据图及完整附件后，指出普通观众不能直接阅读整屏英文报告。此反馈属于返工，没有确认第一版文案。

- 通过 `PATCH /api/jobs/{job_id}/draft` 更新创作方向与受众，清除旧稿、讨论、旧人工待办，再经 `POST /runs` 从素材节点重跑。
- 版本 2 开始后，补充调研找到了本案的真实中文报道。为把具体链接交给素材节点，通过任务取消 API 停止版本 2 的早期素材运行，待 Worker 退出后保存版本 3，并正常提交 `produce`。没有直接改数据库或调用节点/provider。
- 中文来源补充输入：[production-brief-v3.json](production-brief-v3.json)。版本 2 输入保留为 [production-brief-v2.json](production-brief-v2.json)，供流程追溯。
- 中文阅读线索包括云头条/新浪 2026-09-11 转述、21世纪经济报道/新浪 2026-09-13 转述、GTG-15001 非官方中文译文。它们均基于同一份 Anthropic 报告，不当作多份独立调查证据；素材节点仍须自行读取、核对、截图和冻结。
- 英文原报告保留用于核实；主要观看画面要求中文可读。导演在人工确认与配音后，用现有竖版组件依据材料呈现中文关系、分工与收费说明，不能冒充官方中文图或涉事 app 实拍。
- 版本 3 的素材 CLI 达到 900 秒后没有最终响应，实际暂停为 `NEEDS_INPUT / materials`，原因是 `llm_operation` 的提交状态 `UNKNOWN`。没有将此操作改为完成或重复提交同一版本。
- 版本 3 的节点工作目录留下 `material-research.json`、4 份正文、8 张中文截图和 1 张官方原图。操作者确认引用的 13 个文件存在且 SHA-256 与清单一致；这仅证明输入文件完整，不等于素材节点已经成功冻结或审核通过。已下载 YouTube 视频因不能确认涉事 app 画面且字幕失败，没有进入可用视频清单。
- 当前生产输入：[production-brief-v4.json](production-brief-v4.json)。通过正常草稿和运行 API 新建版本 4，让素材节点读取并复核上述同一任务的已采材料、复制到本轮目录并真正返回有效 JSON，然后按 Graph 继续。版本 4 已提交 `produce`，保留版本 3 的真实未知状态记录；没有改动模型设置、素材资产数据库或审批状态。
- 后续以任务 API 当前状态与当前版本产物为准；第一版审稿入口和稿件仅作为历史记录。
- 私有提交回执：`.runtime/videoagents/ai-dating-human-handoff-v2-submission.json` 和 `.runtime/videoagents/ai-dating-human-handoff-v3-submission.json`。
- 恢复回执：`.runtime/videoagents/ai-dating-human-handoff-v4-submission.json`；未完成节点输入文件完整性核对：`.runtime/videoagents/ai-dating-v3-unfinished-material-files-verified.json`。

第一版附件通过实际飞书消息 ID 回读，下载的文案 TXT 和完整 ZIP 的 SHA-256 与原文件一致。返工版需重新发送，不能把已经送达的英文原件称为中文成片画面。

## 中文素材返工交付：版本 4，后续已要求修改开头

- 当前状态：`NEEDS_HUMAN / script`，实际暂停节点为 `human_review_script`。没有确认文案、配音、导演时间线或成片。
- 本轮素材节点实际冻结 4 条来源、9 个画面（8 张中文正文截图、1 张官方英文原图）。API 下载的当前版本 18 个登记产物全部通过 SHA-256 核对。
- 初稿机器审查为 `REVISE`：要求消除“自家模型 Claude”的指代歧义。编剧节点实际修订为“Anthropic 的模型 Claude”，并调整来源素材关联。
- 讨论状态为 `FINAL_REWRITE`：达到本轮讨论配置后交付最终改稿，没有新增一轮 `APPROVE`。人工仍须阅读最终稿和机器意见；没有伪造机器或人工通过。
- 当前稿件：[待人工审读的返工口播稿](script-for-human-review-v4.md)、[Graph 文案 JSON](graph-script-v4.json)、[实际讨论及最终改稿记录](graph-script-discussion-v4.json)。这些副本与节点交付一致，没有手工修改旁白。
- 已发到飞书：完整文案正文、8 张中文图预览、文案 TXT、含全部 9 个画面及中文说明的 ZIP。ZIP 共 12 个文件，完整性检查通过，9 个媒体条目的散列与登记原件一致。
- 发送消息 `om_x100b634d98f6dcacb363bfcb9be3ea4` 精确回读确认包含完整实际稿件与 8 个图片项；TXT 消息 `om_x100b634d989448a8b4bad652fb985ac`、ZIP 消息 `om_x100b634d98b808a0b2995de51d67a93` 的实际下载附件与原文件 SHA-256 一致，没有重复发送。
- 中文页面用于对应证据，未取得可验证的涉事 app 实录。后续导演仍需使用中文大字、关系和分工组件讲清楚，不能依靠文字截图铺满全片或让观众自行阅读英文原图。中文素材的编辑解读与原报告事实须继续区分。

以下时间来自任务事件 API，均为 2026-10-08，Asia/Shanghai：

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| 21:18:21 | 版本 3 素材运行暂停，提交结果未知 | 事件 2895，`NEEDS_INPUT` |
| 21:22:11 | 版本 4 Worker 启动素材节点 | 事件 2898 |
| 21:27:57 | 素材交接完成，进入编剧 | 事件 2916 |
| 21:31:49 | 初稿交付，进入机器审查 | 事件 2918 |
| 21:34:59 | 审查要求修正，编剧生成最终改稿 | 事件 2920 |
| 21:35:47 | 最终改稿进入文案人工审稿 | 事件 2923 |

私有证据保存在 `.runtime/videoagents/ai-dating-human-handoff-feedback-events.json` 与 `.runtime/videoagents/ai-dating-review-delivery-v4/`，包括产物、压缩包、发送及精确消息回读核对记录。后续必须使用当前版本的实际人工审稿待办，由用户决定确认或返工。

## 开头返工交付：后续已获用户确认

用户引用上述中文素材交付，指出《约会 App 最炸套路：4700 个 AI 狂撩 25000 人》比原稿的假设式开场更有吸引力。本轮是同一期的文案返工，没有确认文案或授权进入配音。

- 用户意见与提交给 Graph 的执行上下文保存在 [human-feedback-hook.json](human-feedback-hook.json)。通过正常 `POST /api/jobs/{job_id}/resume`，以实际待办提交 `decision=revise`，继续版本 4 的原 Graph 检查点。
- 实际执行路径为 `human_review_script → screenwriter → script_reviewer → human_review_script`，中间保留工具记录清理。已有素材沿用，不重采、不改图片、没有直接调用配音或渲染。
- 编剧节点将原来的“假设你聊了半个月”替换为具体规模、平台宣称与真人视频的冲突。首屏标题为“4700个AI在交友App撩人”；完整文案标题为“超4700个AI聊过至少2.5万人：真人哪来的？”。人数仍保留不同 AI 身份、至少互动人数和两周观察窗口的口径。
- 本轮实际文案审查为 `APPROVE`，讨论状态为 `APPROVED`。当前为 `NEEDS_HUMAN / script`，暂停节点 `human_review_script`；没有人工确认，没有音频、时间线或成片。
- 当前有效稿件：[完整待审口播稿](script-for-human-review-hook-rewrite.md)、[Graph 文案原件副本](graph-script-hook-rewrite.json)、[Graph 文案讨论原件副本](graph-script-discussion-hook-rewrite.json)。口播副本与登记产物、任务 API 回读一致，没有人工改写。
- 经 API 下载本轮文案、讨论、已应用的人工反馈与上轮审核记录，共 4 个登记产物，SHA-256 全部匹配。
- 已发送完整 12 段新稿正文及 TXT。正文消息 `om_x100b634e2d67d4a4b32b169be2922ca` 的精确回读与发送内容完整一致；附件消息 `om_x100b634e2d04cca4b32b263352c5c6c` 下载文件的 SHA-256 与本地原件一致。中文素材包沿用上一条交付，不重复发送。

以下时间来自任务事件 API，均为 2026-10-08，Asia/Shanghai：

| 时间 | 事件 | 证据 |
| --- | --- | --- |
| 22:08:21 | 人工返工命令持久化 | 事件 2924，`QUEUED` |
| 22:08:22 | 人工节点应用返工意见并返回编剧 | 事件 2926，`RUNNING` |
| 22:11:45 | 开头改稿交付并进入文案审查 | 事件 2928–2930，登记文案产物 |
| 22:15:53 | 机器审查通过并重新等待人工审稿 | 事件 2931–2933，`APPROVED / APPROVE`、`NEEDS_HUMAN` |

本轮私有证据保存在 `.runtime/videoagents/ai-dating-hook-feedback-submission.json` 与 `.runtime/videoagents/ai-dating-review-delivery-hook/`，包括任务人工待办、登记产物、Graph 事件、发送及精确回读记录。这里只记录本轮真实进度；用户确认前不继续配音。

## 用户确认文案后的继续制作

用户回复“这版本文案不错”。操作者先核对当前人工待办与已交付的开头改稿完全一致，再通过正常 `POST /api/jobs/{job_id}/resume` 提交 `decision=confirm`，继续版本 4 的原 Graph。用户原话与确认说明保存在 [human-approval-script.json](human-approval-script.json)，完整私有提交回执位于 `.runtime/videoagents/ai-dating-script-confirmation-submission.json`。本次确认仅针对文案，没有授予发布状态。

- 配音节点已经生成 `voice_guidance.json`、`narration.mp3`、`alignment.json` 与 `audio_report.json`，音频门校验后进入导演节点。
- 音频实测为 171.553958 秒，约 2 分 52 秒；没有为达到目标时长改变已确认文案或在剪辑阶段变速。实际长度以音频和成片测量为准。
- 字幕对齐来源为字节供应商，报告明确区分正文覆盖、顺序和时长校验与独立识别、人工听审。当前时间戳报告有 264 个低于 0.8 的词，不能将 `verified=true` 表述为已经人工确认同步。
- 导演节点交付了组件学习产物。通过项目实际校验函数核对全部 152 个竖版预设、161 个可选组件及当前清单与源码指纹，均匹配。
- 首次成片已于 22:38:56 由 Graph 完成并于 22:42 发送；用户随后反馈画面缺少冲击力，本期进入视觉返工。首次视频与生产证据保存在 `.runtime/videoagents/ai-dating-production-evidence/`，不能将该版记录成已获画面认可。

## 首次成片及视觉返工

- 首次导演输出 18 个镜头，仅使用 evidence、image_focus、comparison、conclusion、steps 五种基础组件。已完成全部 152 个竖版组件学习，但实际方案以同类报道卡片为主。
- 实际流程：事件 2934 提交确认后的命令，2936 人工确认，2937 配音，2942 导演，2947 剪辑，2949 渲染，3060 完成。对应时间为 22:25:56、22:25:57、22:25:57、22:29:38、22:34:41、22:35:51、22:38:56，均为 2026-10-08 Asia/Shanghai。
- 首次实际视频登记产物为 `4c2407755dd44c34b81467254ae921d6`，SHA-256 为 `4968601ecab35514025c58a522e28e9405f93572235bedf45218d81c5bf48a9d`；20,419,743 字节，H.264 1080×1920、30 fps、AAC 音频，视频流 171.566667 秒。完整解码及实际帧抽查通过，可读性检查不能替代用户对视觉表现的判断。
- 首次飞书正文消息 `om_x100b634ef35778a0b1ffa63db594897`、视频消息 `om_x100b634ef32ba4a8b48a8bac04bce57` 均精确回读；未发布。附件回读确认平台文件键与文件名，尚未独立下载该媒体消息复核传输后的文件 SHA。
- 用户两条真实反馈及执行方向见 [human-feedback-visual.json](human-feedback-visual.json)。文案、真实音频与供应商字幕时间戳继续沿用。
- 排查发现社区组件生产入口只允许 `props={}`，渲染固定演示，不能输入本期数据。通过通用生产绑定接通已有六个组件的实际参数，固定演示及历史任务保持可读；导演通过正常 `rebuild_from=director` 入口重做画面，不能手写本期时间轴替代节点。

## 初始交付验证

- 任务 brief 的 Pydantic 契约与竖屏生产策略校验通过，API 回读与提交文件完全一致。
- `npm run typecheck`、`npm run web:typecheck`、`npm run web:build` 通过。
- 工作台首页 HTTP 200；人工审稿待办已持久化。
- 本次仅新增本期输入、节点产出副本和流程记录，未修改生产代码。
- 返工通过正常版本化任务入口执行；当前版本产物、飞书图片项、全文及实际下载附件已经验证。前后端代码没有新增变化，因此未重复运行此前已通过的类型检查和构建。

## 视觉返工的通用修复及验证

- 生产绑定契约位于 `videoagents/production-bindings.json`，生成到组件清单并注入导演及完整组件学习资料。接通 Rve-StatCounter、Rve-PieChart、Rve-SplitScreen、Talkcraft-unit-grid-proportion、Talkcraft-source-converge、Bits-ChatConversation；六个是已接通接口数量，实际成片使用另行统计。
- 前后端依据同一契约校验必填字段、文字、数值、来源与比例口径；绑定直接调用既有底层组件。旧 `props={}` 仍显示原演示，其他 146 个固定预设继续拒绝未知参数。
- 百格与关系汇聚的竖版实现支持内部 productionHold，默认关闭；生产保持动画完成后的可读画面。原始横版源文件未改变，108 个上游原件 SHA 校验匹配。安全区保留标题、字幕与来源；聊天示意固定显示中文标识。
- 只有真实素材与合规来源比例图计入覆盖；单数字计数、解释面板和聊天示意不计入。source_ref 仍与本段已批准来源对应，未放宽覆盖要求。
- 新鲜验证：全量 Python/API 881 项通过，渲染时间轴 51 项通过，网页 88 项通过；根项目与网页 TypeScript 检查、ESLint、Python Ruff、网页生产构建、组件路径及生产清单检查、Pydantic 生成契约检查均通过。
- 全量回归中修正一条既有编剧 Prompt 测试的过时文字断言，使其匹配现有“不是现成口播稿”；编剧 Prompt 与已定稿正文没有改变。测试日志位于 `.runtime/videoagents/ai-dating-component-binding-backend-tests.txt`。
- 本机服务在无运行任务时通过项目 stop/start 正常刷新代码，健康检查通过。于 23:13:03 通过任务 API 提交 `action=produce, rebuild_from=director, base_revision=4`，HTTP 202、事件 3061；Worker 于事件 3062 进入导演，沿用既有音频。私有回执为 `.runtime/videoagents/ai-dating-visual-rebuild-submission.json`。

## 剪辑阻断后的导演修正

- 首次视觉返工由导演生成 19 镜头，实际用了 Rve-StatCounter、Rve-PieChart、Rve-SplitScreen、Talkcraft-source-converge 四种生产绑定组件；尚未生成这版实际视频。剪辑节点仍发现中文统计截图停留 26.23 秒、关键人机分工依赖整张英文图，事件 3071 如实暂停为 `NEEDS_INPUT / director`。待修记录与登记产物下载、SHA 回读位于 `.runtime/videoagents/ai-dating-visual-rebuild-evidence/`。
- 修复导演在剪辑阻断后忽略 `pending_snapshot / gate_issues`、复用当前旧分镜的恢复路径；有待修问题时必须重新规划，没有模型则继续暂停，不能恢复即放行。
- 剪辑模型只接收当前实际使用的 bound 组件 canonical 参数契约和后端计算的素材/图表覆盖报告，保留真实用户意见，不重新发送历史分镜或音频对齐。数字卡不计图表。
- 修正导演附加指令与真实覆盖规则的冲突：真实素材和有来源、对应当前旁白的数据图表合计须严格超过 70%；不再错误要求图片/视频本身超过 70%。后台校验和阈值没有放宽。
- 本次全量 Python/API 回归 885 项通过，导演、剪辑定向回归 85 项通过，Python Ruff、根项目及网页类型检查、ESLint、网页生产构建通过；全量日志为 `.runtime/videoagents/ai-dating-component-recovery-backend-tests.txt`。
- 无运行任务时正常刷新本机服务，再通过实际 `input / director` 待办提交技术 `confirm` 续跑，事件 3072，HTTP 202。这不是文案、画面或发布的人工认可。真实任务版本仍为 4，正文、音频、字幕保持一致；私有回执 `.runtime/videoagents/ai-dating-director-editing-recovery-submission.json`。
- 这次导演生成了 21 镜头候选，但给 `data.visualization=cards` 添加了不支持的 `source_ref`，事件 3074–3075 再次真实暂停，候选未登记为当前时间线，也未渲染。只读模型回执副本位于私有证据目录，不能把候选当成已经生成的视频。
- 补齐导演自己的参数说明，保留 cards 原契约与覆盖分类；仅在待修续跑时把真实 `editing_guidance` 交给导演，并投影本次技术补充为 `extras.timeline_repair_note`。技术意见不成为事实来源或人工认可，上一轮画面问题不能被新的参数错误覆盖。
- 导演/剪辑/Prompt 定向回归 195 项通过，正常服务刷新后，以当前真实 director 待办再次提交技术续跑，事件 3076、HTTP 202；回执 `.runtime/videoagents/ai-dating-director-card-contract-recovery-submission.json`。未导入手写分镜、未放宽校验、未改数据库审核标记。
- 最后这次交接修复后，全量 Python/API 885 项再次通过；根项目及网页类型检查、网页生产构建通过。全量新鲜日志 `.runtime/videoagents/ai-dating-final-recovery-backend-tests.txt`，不将测试通过表述为新版已经渲染。
