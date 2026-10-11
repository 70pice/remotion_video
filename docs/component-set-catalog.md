# 组件套目录

这个目录把组件当成“表达套件”管理：先看这一段要完成什么表达，再选择素材类型、组件套和可调参数。

**A01-A12、B01-B18 共30套已全部备案。** 逐套“什么时候用、怎么表达、普通生产怎么用、哪里可以改”见
[导演使用指导](component-set-director-guide.md)；导演运行时从 [备案 JSON](component-set-registry.json)
直接注入这些指导。登记状态与人工品鉴状态分开保存，不能把全部备案说成全部审核通过。

以下各节的 `component-demo` 入参用于独立样片。普通生产通过 `Shot.set_design` 选整套，
传入本期真实内容和素材，并调整内部 `parts` 的时间、大小、位置与间距。固定部件和
默认布局、实际生产 native IDs、material_kind 与 focus_supported 以 [生产套件映射](../videoagents/component-set-capabilities.json) 为准；目录下“组件组合”描述的是 component-demo 样片组合，可能不同于生产 parts 展开结果。旧的
`props.component_set/composition/rich_content` 仍只用于样片。导演完成不超过30秒的
director Demo MP4 后停在人工审核；审核通过后才进入剪辑成片。当前交付边界是 Demo 待审，不提前声称完整成片已渲染。每套完整生产用法见上方导演使用指导。

当前分两类：

- 有素材组件套 A01-A12：必须传入当前任务已导入的 `asset_id`，用真实图片或视频承载画面。
- 无素材组件套 B01-B18：不传 `asset_id`，由 `content` 生成图形化表达；18 套样片均已通过通用 API/Graph 入口生成、发送并回查，全部为待品鉴。

共同视觉约定：素材在上、白字在下、深色背景、没有白色标题底板、没有黄色标题。圈注、局部放大和坐标映射只在 metadata.focus_supported=true 的生产套件开放，当前为 A03、A05、A06、A09；其他套件通过 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

## A01 人物处境

状态：已备案，已人工 review 通过。

什么时候用：需要先让观众带入一个具体的人、家庭或生活现场，比如“家里老人遇到 AI 陪聊骗局”“孩子帮父母学会先核对信息”。它解决的是“这事和谁有关”，不是解释证据或流程。

素材要求：人物、家庭、手机、生活现场图片。主体要清楚，画面要能直接服务本段旁白。

component-demo 样片组合：`Bits-KenBurns` 主图，`Talkcraft-corner-bracket-frame` 标题层，`Snapcn-TextHighlight` 强调层。

怎么用：`component-demo` 请求传 `set_id=A01`、`asset_id`、`duration_seconds`、`base_revision`、`idempotency_key`。可调的是素材和时长；标题层与强调节奏由组件套控制。

不适合：操作教学、原文证据、复杂关系图。

样片：`321ff7f80522406b88e2f91a24144ef6` R6，视频回执 `om_x100b63909686a0a0b2a8d4acaed2823`。

## A02 App对象

状态：已备案，待用户品鉴。

什么时候用：识别 App 或手机界面对象，说明界面身份、主要入口和本段要看的区域；生产不做逐步点击教学。

素材要求：手机界面图片或录屏，页面身份和主要入口清楚；生产用于识别对象和入口职责，不要求连续点击过程。

component-demo 样片组合：历史样片用 `Snapcn-PhoneFrame` 承载录屏，`Snapcn-TextReveal` 显示白字口令，并用 `tutorial_steps` 驱动橙色手绘圈。这个目标圈只属于 component-demo 样片/回放说明。

普通生产怎么用：选择 `set_design.set_id=A02`，绑定当前 job 的 `asset_src/source_label`，用 Shot.title/body 和 content.items 说明界面身份、入口职责或注意点。当前 metadata.material_kind=image_or_video 且 focus_supported=false，生产不传 `focus_steps/source_size`，不承诺橙色目标圈或逐步点击同步。

不适合：完整操作教程、逐步点击跟随或需要目标圈同步的录屏；这类生产镜头用 focus_supported=true 的 A03/A09。

样片：`056a63b5d8224c918ef2790737ef40b7` R7，视频回执 `om_x100b6392310298a0b3b2178776f2bd1`。

## A03 操作过程

状态：已备案，待用户品鉴。

什么时候用：需要展示一段操作从输入到结果的过程，但重点不是介绍 App 外观，而是动作先后顺序。

素材要求：完整操作录屏。输入框、按钮、结果区域都能按帧定位。

component-demo 样片组合：语义素材 `video` 加 `Snapcn-TextReveal`；橙色圈由 `focus_steps` 驱动。

怎么用：传 `set_id=A03`、`asset_id`、`duration_seconds`、`focus_steps`。可调的是素材、时长、每步时间、白字口令和目标框。`focus_steps` 必须连续覆盖整段，每步至少 30 帧。

不适合：静态原文证据、结果海报、动作与标题对不上的录屏。

样片：`134fcfaed09b41cb95d1180bdae529bb` R9，视频回执 `om_x100b6392ca4804a4b32bb105939f1ec`。

## A04 作品结果

状态：已备案，待用户品鉴。

什么时候用：要展示一个最终作品、结果图、生成图或页面成果，先看整体，再看局部亮点。

素材要求：完整作品或结果图。局部亮点能被圈出来，且不需要观众阅读大量小字。

component-demo 样片组合：`Talkcraft-tilt-3d-page` 展示作品，`Snapcn-TextReveal` 显示白字口令；圈注跟随页面透视变换。

怎么用：传 `set_id=A04`、`asset_id`、`duration_seconds`、`focus_steps`。可调的是素材、时长、每步口令和目标框。

不适合：逐步教程录屏、密集论文截图、需要逐句引用的证据材料。

样片：`047f66a5b78c4ea991038d23fd6951ad` R7，视频回执 `om_x100b6392c454b0a8b49253d679c1903`。

## A05 原文证据

状态：已备案，待用户品鉴。

什么时候用：要让观众读报告、政策、论文、网页原文里的某一句，并知道这句话为什么能支撑当前旁白。

素材要求：可读资料截图，来源身份清楚，重点句和关键词能定位。素材如果自带播放器控件、进度条、水印或遮挡，应重新采集。

component-demo 样片组合：语义素材 `evidence` 加 `Snapcn-TextReveal`；橙色圈和可选局部放大由 `focus_steps` 驱动。

怎么用：传 `set_id=A05`、`asset_id`、`duration_seconds`、`focus_steps`。可调的是素材、时长、口令、时间和目标框。模拟资料必须明确标注身份，不能写成真实资料。

不适合：把报告截图当背景、字太小读不清、没有来源身份的截图。

样片：`801368e7e70440c2b1e6670e2ee4baed` R8，视频回执 `om_x100b6392c15ad0a8b1643156ab8b401`。

## A06 关系图解

状态：已备案，待用户品鉴。

什么时候用：要解释人、AI、平台、钱、结果之间的关系，适合流程图、因果图和节点图。

素材要求：关系图节点清楚、标签可读、箭头或分区明确，手机端能看懂。

component-demo 样片组合：语义素材 `image_focus` 加 `Snapcn-TextReveal`；橙色圈和可选局部放大由 `focus_steps` 驱动。

怎么用：传 `set_id=A06`、`asset_id`、`duration_seconds`、`focus_steps`。可调的是素材、时长、每步口令和目标框。画面要保留关系全貌，不能裁掉关键节点。

不适合：没有明确结构的普通图片、过密的复杂图、只靠换标题重复同一张素材。

样片：`d4d6fa0f46a54b5692eaf0e5eb9cf0c4` R6，视频回执 `om_x100b6392d843e4a0b1b17a1e15602bf`。

## B01 问题开场

状态：增强版实际 Demo 已发送并回读核对，待用户品鉴。上一版因表达过于简单进入返工记录。

什么时候用：问题输入、疑问句、数字锚点和核对线索逐步展开，适合没有现场图片的开场。

component-demo 样片组合：`Rve-QuoteCard` + `Snapcn-SearchTyping` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-ProgressSteps`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B01`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 15 秒，可在 12–20 秒内调整。内容字段：`title`, `body`, `takeaway`, `items`, `metric`。字段定义及示例见 [增强版说明](component-set-rich-composition.md) 和 [备案 JSON](component-set-registry.json)。

真实样片：`78f3751ddc314125b2b0a54c51035759` R5，分支 `video/78f3751ddc314125b2b0a54c51035759-component-set-b01`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B01/B01-问题开场-无素材增强版-R5.mp4`，sha256 `7bc247f55c6c1ed3a61cdcd07aad8382df7fbb2a939f0f6a9447ea8c250d3ab0`，媒体回执 `om_x100b639a4cb4e0a0b3d69e76c3cfeb8`。

## B02 概念解释

状态：增强版实际 Demo 已发送并回读核对，待用户品鉴。上一版因表达过于简单进入返工记录。

什么时候用：改写容易混淆的说法，配合词语翻换、白话说明和数字锚点拆开判断。

component-demo 样片组合：`keyword` + `Snapcn-TextRewrite` + `Snapcn-AnswerHighlight` + `Rve-StatCounter` + `Snapcn-WordFlip`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B02`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 16 秒，可在 12–20 秒内调整。内容字段：`title`, `body`, `takeaway`, `items`, `metric`。字段定义及示例见 [增强版说明](component-set-rich-composition.md) 和 [备案 JSON](component-set-registry.json)。

真实样片：`a0c74c1a18a9478cb8d8ee751e8f8bc5` R5，分支 `video/a0c74c1a18a9478cb8d8ee751e8f8bc5-component-set-b02`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B02/B02-概念解释-无素材增强版-R5.mp4`，sha256 `d2cda3b928db7e7ade3e0a92705dce879767cf82cb2a81a020e204fd3bacc03a`，媒体回执 `om_x100b639a7f3328a8b4a8efc7b08d660`。

## B03 两种情况对比

状态：增强版实际 Demo 已发送并回读核对，待用户品鉴。上一版因表达过于简单进入返工记录。

什么时候用：把两种做法的文字差别和同单位数字放在同一画面，不把动作数解释成安全概率。

component-demo 样片组合：`Rve-SplitScreen` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-ComparisonChart` + `Snapcn-TextBuild`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B03`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`, `body`, `takeaway`, `items`, `numeric_items`。字段定义及示例见 [增强版说明](component-set-rich-composition.md) 和 [备案 JSON](component-set-registry.json)。

真实样片：`9e02e93221ee43a5987a960f1b92f812` R2，分支 `video/9e02e93221ee43a5987a960f1b92f812-component-set-b03`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B03/B03-两种情况对比-无素材增强版-R2.mp4`，sha256 `1760ef0bdba45e1eede7d82ab4d1cc621e244e049b159800337372a6293aad24`，媒体回执 `om_x100b639a79ca10a4b3dc54b3c32c3d4`。

## B04 数字账本

状态：增强版实际 Demo 已发送并回读核对，待用户品鉴。上一版因表达过于简单进入返工记录。

什么时候用：给出每笔金额、累计变化和总账；合计必须等于三笔输入之和。

component-demo 样片组合：`Rve-StatCounter` + `Snapcn-TextRewrite` + `Snapcn-TextHighlight` + `Rve-ChartAnimation` + `Snapcn-TextBuild`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B04`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 16 秒，可在 12–20 秒内调整。内容字段：`title`, `body`, `takeaway`, `metric`, `numeric_items`。字段定义及示例见 [增强版说明](component-set-rich-composition.md) 和 [备案 JSON](component-set-registry.json)。

真实样片：`1a78f99564d34e1c8fd98cea6704d6d2` R3，分支 `video/1a78f99564d34e1c8fd98cea6704d6d2-component-set-b04`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B04/B04-数字账本-无素材增强版-R3.mp4`，sha256 `2cdf54c79c8ee5e276433a6bbcfd8b8075c1ca9af91fa81e3017ff511620234f`，媒体回执 `om_x100b639a084e24a0b104acbdd1f8c1c`。

## B05 步骤演示

状态：增强版实际 Demo 已发送并回读核对，待用户品鉴。上一版因表达过于简单进入返工记录。

什么时候用：动作流程、对应说明和总步数一起展开；适合没有录屏时解释步骤。

component-demo 样片组合：`Rve-ProgressSteps` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-QuoteCard`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B05`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`, `body`, `takeaway`, `items`, `supporting_items`, `metric`。字段定义及示例见 [增强版说明](component-set-rich-composition.md) 和 [备案 JSON](component-set-registry.json)。

真实样片：`336f8b4c65f041d1ac783ee7e15205b5` R3，分支 `video/336f8b4c65f041d1ac783ee7e15205b5-component-set-b05`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B05/B05-步骤演示-无素材增强版-R3.mp4`，sha256 `a987bb7304a7cf3ace858617fc0b7cd80e36e01fd7f5a24b7300a0aa375cfa6d`，媒体回执 `om_x100b639a10b738a0b3e019a741e14ef`。

## B06 结论行动

状态：增强版实际 Demo 已发送并回读核对，待用户品鉴。上一版因表达过于简单进入返工记录。

什么时候用：从明示模拟的聊天情景转到行动原则、数字锚点和行动清单。

component-demo 样片组合：`conclusion` + `Snapcn-TextReveal` + `Snapcn-AnswerHighlight` + `Bits-ChatConversation` + `Rve-StatCounter` + `Snapcn-TextBuild`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B06`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 15 秒，可在 12–20 秒内调整。内容字段：`title`, `body`, `takeaway`, `items`, `supporting_items`, `metric`。字段定义及示例见 [增强版说明](component-set-rich-composition.md) 和 [备案 JSON](component-set-registry.json)。

真实样片：`dd0eea7fa2434e82be39f2e0c1f1416c` R3，分支 `video/dd0eea7fa2434e82be39f2e0c1f1416c-component-set-b06`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B06/B06-结论行动-无素材增强版-R3.mp4`，sha256 `7a374c1222380c310bff6e2d11b8d0acac48834814b9039a72e63fa1966f83ef`，媒体回执 `om_x100b639a2babc8acb3def298c583885`。

增强版时间轴 1080×1920 / 30fps；发送预览 540×960 / 30fps。每条完整解码并检查实际阶段帧。当前未记录六套增强版的人工通过。

<!-- B07-B18-EXPANDED:START -->
## B07 时间分配

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白讲“先花几分钟分开做三件事”、解释时间分配或提醒观众先停一下再操作时使用。

component-demo 样片组合：`Rve-ChartAnimation` + `Talkcraft-typewriter-reveal` + `Snapcn-TextHighlight` + `Rve-QuoteCard` + `Rve-StatCounter` + `Rve-ProgressSteps` + `Snapcn-WordFlip`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B07`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`metric`、`numeric_items`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于真实耗时统计。；不用于声称某种时间分配能降低风险。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`79d377e97adb47a0b941ab1e8bfdf4b7` R2，分支 `video/79d377e97adb47a0b941ab1e8bfdf4b7-component-set-b07`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B07/B07-时间分配-无素材增强版-R2.mp4`，sha256 `95670ddf1675032ab958ab3a584e21a3608f48d84f5009ca553aee014c447ec7`，媒体回执 `om_x100b639ab17624a0b3c7ca54ca87d83`。

## B08 预算拆分

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白需要讲“100元怎么拆开看”、预算去向、付款前先看用途时使用。

component-demo 样片组合：`Rve-StatCounter` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-ChartAnimation` + `Snapcn-WordFlip` + `Talkcraft-ink-underline`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B08`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`metric`、`numeric_items`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于真实收费标准。；不用于推荐价格或市场行情。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`8fe2ced8db294852a47179261da1971a` R2，分支 `video/8fe2ced8db294852a47179261da1971a-component-set-b08`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B08/B08-预算拆分-无素材增强版-R2.mp4`，sha256 `d344c1756676270956ead7abd6a5b49bd35531e1f64f8bbab20f703b93e2cae0`，媒体回执 `om_x100b639b44337c88b2c85bb7e6676f9`。

## B09 数字差

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白对比“直接照做”和“先回拨核实”等两种做法时使用。

component-demo 样片组合：`Rve-ComparisonChart` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-StatCounter` + `Talkcraft-strike-and-replace`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B09`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`metric`、`numeric_items`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于证明某个选择一定更安全。；不用于概率、胜率或风险分数。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`4968fc3e451f4b5a850f1a89f52fc17f` R2，分支 `video/4968fc3e451f4b5a850f1a89f52fc17f-component-set-b09`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B09/B09-数字差-无素材增强版-R2.mp4`，sha256 `21ef8c507130caff7abd709e44c26a8cbacdf1fb990f9469b718987e8e94eb66`，媒体回执 `om_x100b639b5ad6b0b0b25b56d02624185`。

## B10 累计账本

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白讲“单次看不大，但合起来要算总账”时使用。

component-demo 样片组合：`Rve-ChartAnimation` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-LineChart` + `Talkcraft-ink-underline`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B10`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`metric`、`numeric_items`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于真实账单或真实消费记录。；不用于没有逐笔口径的冲击性大数字。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`4d8ab6d506e7402188d555d3c8d2d119` R2，分支 `video/4d8ab6d506e7402188d555d3c8d2d119-component-set-b10`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B10/B10-累计账本-无素材增强版-R2.mp4`，sha256 `228cc668d5165d7959403cf1a4d7fb0e3d219df3170c98c1a5c7121eb65f1b2a`，媒体回执 `om_x100b639b6b3e84a0b1df30c5512e998`。

## B11 条件分支

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白需要讲“如果出现这种条件，就做这个动作”的流程判断时使用。

component-demo 样片组合：`Rve-ProgressSteps` + `Snapcn-TextBuild` + `Snapcn-AnswerHighlight` + `Rve-SplitScreen` + `Rve-StatCounter` + `Talkcraft-word-slot-cycle`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B11`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于自动判定结果。；不用于替代真实产品流程图或真实规则。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`96a2e74bbfbb476faac9893081a83bb6` R1，分支 `video/96a2e74bbfbb476faac9893081a83bb6-component-set-b11`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B11/B11-条件分支-无素材增强版-R1.mp4`，sha256 `0aabe1ee17fac8cf8ce49793f7b2a98f0690c6e9f1d4d4386c25cefbbe357137`，媒体回执 `om_x100b639b67687ca0b12e0c7d99b4572`。

## B12 关系链

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白解释 AI文字、真人视频、付款入口等链路关系时使用。

component-demo 样片组合：`Rve-QuoteCard` + `Snapcn-WordFlip` + `Snapcn-TextHighlight` + `Talkcraft-source-converge` + `Rve-StatCounter` + `Rve-ProgressSteps`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B12`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于认定真实案件事实。；不用于替代有来源的关系图证据。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`cdcc40d383f44cecaee60c80cf07c085` R2，分支 `video/cdcc40d383f44cecaee60c80cf07c085-component-set-b12`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B12/B12-关系链-无素材增强版-R2.mp4`，sha256 `d574169adde19784c2c49b692d90c1c6aa996219147920101ba786e2e9ff0386`，媒体回执 `om_x100b639b7b1188a4b2afb079d40327f`。

## B13 误区纠正

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白纠正“会聊天就可信”“能视频就是真人”等捷径判断时使用。

component-demo 样片组合：`Rve-SplitScreen` + `Snapcn-TextRewrite` + `Snapcn-TextHighlight` + `Snapcn-TextSwap` + `Rve-StatCounter` + `Talkcraft-error-retype` + `Rve-QuoteCard` + `Talkcraft-strike-and-replace`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B13`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于给具体对象下结论。；不用于没有替代表述的空泛反驳。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`58ea685395964c5299ccd480791a20b8` R1，分支 `video/58ea685395964c5299ccd480791a20b8-component-set-b13`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B13/B13-误区纠正-无素材增强版-R1.mp4`，sha256 `7251c1aaf18fe165f3c2201b226fd0225d3ee8d17eaee19123866a31e1b7a638`，媒体回执 `om_x100b639b774f74a0b3092107fefecc2`。

## B14 提问回答

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白采用问答结构，例如“视频通话就可信吗？”时使用。

component-demo 样片组合：`Snapcn-AnswerStream` + `Snapcn-SearchTyping` + `Snapcn-AnswerHighlight` + `Bits-ChatConversation` + `Snapcn-TextBuild` + `Rve-StatCounter`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B14`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于真实聊天记录。；不用于冒充平台客服、警方或当事人对话。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`b0245efd3db34046b15a52e9e6bea464` R1，分支 `video/b0245efd3db34046b15a52e9e6bea464-component-set-b14`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B14/B14-提问回答-无素材增强版-R1.mp4`，sha256 `b61923c9fbbcf66ce56a471f42254f5557fad639b591bb9edac964904e7ac989`，媒体回执 `om_x100b639b70c76cacb48d34117014e75`。

## B15 核实状态分类

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白需要区分“有人这么说”“有出处”“还没确认”时使用。

component-demo 样片组合：`Rve-QuoteCard` + `Talkcraft-title-demote-to-label` + `Snapcn-TextHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Rve-ChartAnimation` + `Snapcn-TextBuild`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B15`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`、`numeric_items`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于证据等级排序。；不用于暗示某类信息一定真或一定假。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`72daf450e6084d4a87bdba26db3ae75c` R2，分支 `video/72daf450e6084d4a87bdba26db3ae75c-component-set-b15`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B15/B15-核实状态分类-无素材增强版-R2.mp4`，sha256 `591f651fd59d4fc5846641bb1b1a5305f6a1eeb470cad3963824b8ae359fda98`，媒体回执 `om_x100b639b09dc18a8b16922f81a286bd`。

## B16 优先级排序

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白讲“先看A，再看B，最后看C”的操作建议时使用。

component-demo 样片组合：`Rve-ProgressSteps` + `Talkcraft-title-demote-to-label` + `Talkcraft-keyword-pop-highlight` + `Rve-StatCounter` + `Snapcn-WordFlip` + `Rve-QuoteCard` + `Snapcn-TextHighlight`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B16`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于风险严重度排序。；不用于没有顺序关系的并列信息。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`771fd77fc49a4c008127170d54c904a8` R1，分支 `video/771fd77fc49a4c008127170d54c904a8-component-set-b16`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B16/B16-优先级排序-无素材增强版-R1.mp4`，sha256 `da6476600de75b3534ecb98fcf88c5a25597f415998890e7a4f678dcc23f56ba`，媒体回执 `om_x100b639b046c28a0b1cb01f3f44fa9a`。

## B17 倒数检查

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白提醒“转账前先问自己三件事”“先暂停一下”时使用。

component-demo 样片组合：`Bits-ChatConversation` + `Talkcraft-line-by-line-slide` + `Snapcn-AnswerHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Snapcn-TextBuild`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B17`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于真实聊天判断。；不用于已经完成付款后的证据展示。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`62d2f3fd1e8540e2b4240087b7158bde` R1，分支 `video/62d2f3fd1e8540e2b4240087b7158bde-component-set-b17`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B17/B17-倒数检查-无素材增强版-R1.mp4`，sha256 `53f0bd54988270c0fc4a28e7a3755f1dbb0407ecd11173bfe4e3e0ede5ae6a56`，媒体回执 `om_x100b639b1b7b7cacb11a08af355fdc7`。

## B18 操作步骤前后

状态：实际 Demo 已发送并回读核对，待用户品鉴；未记录人工通过。

什么时候用：旁白讲“以前只做一步，现在拆成三步”或解释操作改造前后时使用。

component-demo 样片组合：`Rve-ComparisonChart` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-ProgressSteps` + `Talkcraft-strike-and-replace`。背景、边框和连接线不计为原生组件。

怎么用：不传 `asset_id`，通过任务 API 提交 `set_id=B18`、`composition=rich`、`content`、`base_revision`、`idempotency_key`。本次 18 秒，可在 12–20 秒内调整。内容字段：`title`、`body`、`takeaway`、`items`、`supporting_items`、`metric`、`numeric_items`。字段定义及示例见 [扩展说明](component-set-expanded-composition.md) 和 [备案 JSON](component-set-registry.json)。

不适合：不用于声称新做法一定提升效果。；不用于没有前后变化的普通步骤说明。

数字边界：演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成风险比例、证据权重、成功率、调查统计或真实价格。

真实样片：`ba3755ea92ba4df884e747ca2b8b7f2f` R1，分支 `video/ba3755ea92ba4df884e747ca2b8b7f2f-component-set-b18`，文件 `.runtime/videoagents/component-set-samples/no-material-delivery/B18/B18-操作步骤前后-无素材增强版-R1.mp4`，sha256 `feb238525d52f4c4eda004d586a94d64dd6f9fc5d2897ed936739f94e38d96af`，媒体回执 `om_x100b639b178c8cbcb2995bfb87cb478`。
<!-- B07-B18-EXPANDED:END -->

<!-- A07-A12-MATERIAL-RICH:START -->
## 有素材增强组件套 A07-A12

六条样片均由任务 API / Worker / Graph 生成，已发送并精确回查。每套7个实际原生组件，素材在上、白字在下，仍待用户品鉴。

详细用途、素材、入参与可改参数见 [有素材增强组件套使用说明](component-set-material-rich-composition.md)。

| 编号 | 用途 | 实际任务 / 版本 | 视频回执 |
| --- | --- | --- | --- |
| A07 人物线索 | 人物、家庭或生活现场图片，需要把注意力落到具体线索和行动。 | `88699705e1784fb5adffe8452ff8c676` R3 / 18.00秒 | `om_x100b6384510c70a0b4aa4c8c02faff6` |
| A08 界面功能拆解 | 介绍App首页不同入口的职责，让观众先认出界面再操作。 | `3851a63f29b247fcb1aebfce1804acac` R3 / 18.00秒 | `om_x100b638466a53ca0b2cf2a495d8dd12` |
| A09 操作跟随 | 连续操作录屏教学，口令、目标圈和操作步骤需要同步。 | `d7b2fe4a7fe14bafb3e6f7993017dc1f` R3 / 12.37秒 | `om_x100b63847782e8a4b27e3725b19ae6d` |
| A10 账单核算 | 账单或费用图片，需要逐笔核对再看合计和累计口径。 | `fac8ff86018a4981995ee8c43e51c64b` R3 / 18.00秒 | `om_x100b6384064a90a0b392cd842bd90d0` |
| A11 作品细节 | 作品、插画或海报展示，需要拆出几个构图细节。 | `78592f4580164ae3938611648e9c1cce` R3 / 18.00秒 | `om_x100b63841b00b4a4b1c8fd891dc47b2` |
| A12 图解关系 | 流程或关系图片，需要说明每个环节的职责和连接。 | `e962e518df924294a1f451a751ce6672` R2 / 18.00秒 | `om_x100b6384143694a8b1b01cb11b3de04` |

<!-- A07-A12-MATERIAL-RICH:END -->
