# 组件套样片

组件套样片用于查看素材和组件的搭配效果。它通过任务 API 入队，由 Worker 执行 `VideoProductionGraph` 的 `component_demo` 节点，再通过 `director_demo` 渲染预览。它是独立的无旁白视觉样片，结束后等待用户品鉴，不生成发布审核记录。

每条样片使用独立任务；有素材样片的素材必须明确导入当前任务。生成画面、模拟界面、模拟资料和示意图应在素材说明和画面里写清身份。原视频的文案、配音和导演审核不受样片影响。

机器可读备案在 [component-set-registry.json](component-set-registry.json)，人读选择规则在 [component-set-catalog.md](component-set-catalog.md)。本文件保留样片入口、请求约束和当前真实 Demo 说明。

目前有素材组件套提供六套：

| 编号 | 表达目的 | 合适的素材 | 本次样片输入 |
| --- | --- | --- | --- |
| A01 | 建立人物生活处境 | 人物、家庭、现场图片 | 生成的母女共同看手机画面 |
| A02 | 介绍 App 对象，或逐步演示操作 | 清楚的手机页面；教学版使用连续操作录屏 | 虚构「邻里小助手」首页 / 添加提醒录屏 |
| A03 | 展示操作与结果 | 覆盖动作的手机录屏 | 在模拟 App 添加提醒的操作录像 |
| A04 | 展示作品结果 | 完整作品、结果页面 | 生成的「普通人与 AI」插画 |
| A05 | 阅读原文并定位重点 | 可读的原文资料 | 明确标注身份的模拟资料 |
| A06 | 解释关系 | 有清楚关系和标签的图 | 人与 AI 配合的简化关系图 |

这六套已完成项目内备案。A01 R6 已经用户 review 通过；A02 R7、A03 R9、A04 R7、A05 R8、A06 R6 为已备案待品鉴，不写成已通过。备案只记录当前可复用表达方式、真实任务、分支、视频回执和输入边界，不修改历史审核记录。

调用流程：

1. 创建 1080×1920、30 fps 的新任务。
2. 通过 `/api/jobs/{job_id}/assets` 导入这一条样片的素材。
3. 向 `/api/jobs/{job_id}/component-demo` 提交 `base_revision`、`idempotency_key`、`set_id`、`asset_id` 和 `duration_seconds`。
4. 查询任务及流程记录，获取 `preview` 和 `cover` 产物。

请求不接受分镜、任意组件 ID 或组件 props；镜头由节点内的可复用组件套构造并校验。接口拒绝已有文案、配音、时间轴、普通生产历史或人工待办的任务，避免把样片入口用于绕过生产审核。已有组件样片可通过草稿入口保存新版本，清理下游产物后重新提交；同一版本不能重复发起新制作命令。

样片时间轴使用 `presentation=component_sample`，要求无音频、无字幕，给主要素材留出更大的画面空间。默认生产时间轴仍使用原有字幕和来源安全区。

这些套的时长按本次素材、动作和阅读需要设置，不代表以后每个镜头固定时长，也不要求每期全部使用。组合能否定为长期规则，仍以用户观看实际样片后的意见为准。

## A02 教学版：当前口令与手绘圈同步

适用于需要观众跟着点的手机教程：输入、保存、查找结果等。素材必须能看清控件和动作；讲保存时录屏应已经输入完成，讲结果时结果应真实出现在录屏中。原来的图片首页模式继续可用，不能把单张首页当作完整操作过程。

先把连续 MP4 录屏导入当前任务，再给 `component-demo` 请求添加 `tutorial_steps`：

```json
{
  "set_id": "A02",
  "asset_id": "当前任务导入的MP4素材ID",
  "duration_seconds": 12,
  "base_revision": 6,
  "idempotency_key": "每次新版本唯一的请求键",
  "tutorial_steps": [
    {"start_frame": 0, "end_frame": 120, "instruction": "输入事项", "target": {"x": 0.1, "y": 0.2, "width": 0.8, "height": 0.08}},
    {"start_frame": 120, "end_frame": 210, "instruction": "点保存", "target": {"x": 0.1, "y": 0.35, "width": 0.28, "height": 0.06}},
    {"start_frame": 210, "end_frame": 360, "instruction": "查看列表", "target": {"x": 0.06, "y": 0.52, "width": 0.88, "height": 0.12}}
  ]
}
```

示例坐标和时刻必须换成实际素材测量值，不能直接套到其他录屏。`instruction` 是当前的一句短口令，最多24字；`start_frame` 包含、`end_frame` 不包含，按30fps计算，相邻步骤连续覆盖整段，每步至少30帧。`target` 是原始素材中控件位置除以素材宽高后的归一化框，不能填手机外框坐标或像素数。素材原始尺寸由上传后的实测 metadata 提供，接口不接受自行伪造尺寸。

节点用真实 `Snapcn-PhoneFrame` 承载录屏，`Snapcn-TextReveal` 显示当前白色口令；生产适配器在同一素材平面上画无填充手绘圈，包含 contain-fit 留边的坐标转换。圈是适配器的标注能力，不额外冒充一个原生组件ID。按用户确认的 A01 风格，素材在上、白字在下，文字直接放在深色背景上，没有白色底框或黄色标题。口令保持单行并紧接手机下方，手机在教学时停止漂浮；教学样片不显示全片进度线和底部来源页脚。模拟素材在 App 顶部保留紧凑身份标注。

可改内容是素材、时长、口令、每步时间和目标框。通用布局在 `src/video-production/PhoneFrameMaterial.tsx`，圈的映射与形状在 `phoneTutorial.ts`；不是让操作者直接提交任意 JSX、CSS 或分镜。飞书播放器的居中播放标属于外层控件，MP4 无法移动；素材布局和发送封面要避开关键控件。

## A03–A06：标题与素材重点同步

四套保留不同的表达目的：A03 连续播放操作录屏；A04 用真实 Tilt3dPage 展示作品；A05 阅读原文；A06 解释关系。修订模式通过 `focus_steps` 提交当前短标题、连续局部帧段及原始素材内的目标框，字段格式和上面的 `tutorial_steps` 相同，二者不能同时提交。尺寸由当前任务上传素材的实测 metadata 提供，接口不接收自行填写的素材尺寸或时间轴。

适合素材中有明确位置需要观众看的场景。每步标题最多24字、至少30帧，连续覆盖整条样片；口令和圈选同时切换，时间必须与录屏动作或图片解释对应。操作录屏先输入完成再讲保存，结果实际出现后才讲查看结果。图片可以在一个连续镜头里依次解释不同区域，不能仅换组件或颜色重复切镜。

此模式只显示一个紧凑透明的 `Snapcn-TextReveal` 白字口令。素材放在上方；有局部放大时，放大画面接在主素材下方，白字紧接最后一个素材区域。没有顶部标题区、白色标题底框或黄色文字。简短素材身份用小字放在白字口令下方，画面顶端只留素材；取消样片进度线和底部来源页脚，保留任务里的真实来源。A04 的圈在作品页面内部，跟随相同的3D变换；A05、A06 的圈直接映射原图；图片下方有空间时显示当前目标的局部放大，便于读清。操作视频占据纵向空间，不叠加放大副图。圈注和局部放大是生产适配器能力，不增加原生组件计数。

当前开放范围为竖屏 `component_sample` 样片；普通成片的字幕和来源安全区保持既有契约。

可改输入是当前任务的 `asset_id`、时长、每步时间、短标题和归一化目标。布局在 `MaterialFocus.tsx`、`focusGeometry.ts` 和 `TalkcraftNativeMedia.tsx`；`focusCompositionLayout` 根据实际素材比例和局部放大计算白字位置，手机使用同一文件中的 `guidedPhoneTitleTop`。白字颜色在 `SnapcnNativeTitles.tsx`，圈注仍用橙色以便定位。未启用该模式的历史样片仍使用原布局。素材本身含有遮挡或播放器控件时应重新采集清洁素材，不靠标注层掩盖。

## B01-B06：无素材组件套增强版

无素材指不传外部图片、录屏或视频；请求仍须提供具体文案、条目和数字。样片通过任务 API 入队，由 Worker 执行 `component_demo → director_demo → end`，生成后等待用户品鉴。

先创建独立空素材草稿；已有样片先通过草稿入口前进一个 revision。下面以新任务 R1 为例，`base_revision` 替换为当前草稿的实际整数版本：

```json
{
  "set_id": "B01",
  "composition": "rich",
  "duration_seconds": 15,
  "base_revision": 1,
  "idempotency_key": "每次新版本唯一的请求键",
  "content": {
    "title": "一句熟悉的话，够吗？",
    "body": "对方会接话，也肯视频。你还需要核对什么？",
    "takeaway": "先核实身份",
    "items": [
      "消息里的称呼",
      "来电的身份",
      "付款的理由"
    ],
    "metric": {
      "label": "要核对的线索",
      "value": "3项",
      "detail": "演示拆解，不是风险统计"
    }
  }
}
```

六套共有字段为 `content.title`、`body`、`takeaway`。增强版时长为 12–20 秒；B01/B02 增加三项 `items` 和条目计数 `metric`，B03 增加两项 `items` 和两项同单位 `numeric_items`，B04 增加合计 `metric` 和三笔同单位 `numeric_items`，B05 增加三步 `items`、三条对应 `supporting_items` 和步数 `metric`，B06 增加两到三项 `items`、两条模拟对话 `supporting_items` 和动作数量 `metric`。

条目计数必须等于 `items` 数量；B04 合计必须等于三笔输入之和。完整字段、字数和数字限制见 [增强版说明](component-set-rich-composition.md)。接口拒绝 `asset_id`、`tutorial_steps`、`focus_steps`、任意时间轴和组件 props。旧 `composition: "basic"` 请求保持可读，原来的简单样片作为返工历史保留。

| 编号 | 实际组件组合 | 任务 / revision | 视频与发送回执 |
| --- | --- | --- | --- |
| B01 | `Rve-QuoteCard` + `Snapcn-SearchTyping` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-ProgressSteps` | `78f3751ddc314125b2b0a54c51035759` R5 / 15 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B01/B01-问题开场-无素材增强版-R5.mp4`；回执 `om_x100b639a4cb4e0a0b3d69e76c3cfeb8` |
| B02 | `keyword` + `Snapcn-TextRewrite` + `Snapcn-AnswerHighlight` + `Rve-StatCounter` + `Snapcn-WordFlip` | `a0c74c1a18a9478cb8d8ee751e8f8bc5` R5 / 16 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B02/B02-概念解释-无素材增强版-R5.mp4`；回执 `om_x100b639a7f3328a8b4a8efc7b08d660` |
| B03 | `Rve-SplitScreen` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-ComparisonChart` + `Snapcn-TextBuild` | `9e02e93221ee43a5987a960f1b92f812` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B03/B03-两种情况对比-无素材增强版-R2.mp4`；回执 `om_x100b639a79ca10a4b3dc54b3c32c3d4` |
| B04 | `Rve-StatCounter` + `Snapcn-TextRewrite` + `Snapcn-TextHighlight` + `Rve-ChartAnimation` + `Snapcn-TextBuild` | `1a78f99564d34e1c8fd98cea6704d6d2` R3 / 16 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B04/B04-数字账本-无素材增强版-R3.mp4`；回执 `om_x100b639a084e24a0b104acbdd1f8c1c` |
| B05 | `Rve-ProgressSteps` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-QuoteCard` | `336f8b4c65f041d1ac783ee7e15205b5` R3 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B05/B05-步骤演示-无素材增强版-R3.mp4`；回执 `om_x100b639a10b738a0b3e019a741e14ef` |
| B06 | `conclusion` + `Snapcn-TextReveal` + `Snapcn-AnswerHighlight` + `Bits-ChatConversation` + `Rve-StatCounter` + `Snapcn-TextBuild` | `dd0eea7fa2434e82be39f2e0c1f1416c` R3 / 15 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B06/B06-结论行动-无素材增强版-R3.mp4`；回执 `om_x100b639a2babc8acb3def298c583885` |

六条实际静音 Demo 已通过 Graph 生成、发送并回读，等待用户品鉴。原始时间轴 1080×1920 / 30fps，发送预览 540×960 / 30fps，每条完整解码并检查实际阶段帧。演示数字和模拟对话不充当现实证据。

<!-- B07-B18-EXPANDED-DEMOS:START -->
## B07-B18：扩展无素材组件套样片

以下 12 套均为无素材 rich 样片：不传 `asset_id`，只传结构化 `content`。每条已经由 Graph 生成、发送并精确回读，当前状态为待品鉴，不是人工通过。

| 编号 | 组件组合 | 任务 / revision | 文件与回执 |
| --- | --- | --- | --- |
| B07 | `Rve-ChartAnimation` + `Talkcraft-typewriter-reveal` + `Snapcn-TextHighlight` + `Rve-QuoteCard` + `Rve-StatCounter` + `Rve-ProgressSteps` + `Snapcn-WordFlip` | `79d377e97adb47a0b941ab1e8bfdf4b7` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B07/B07-时间分配-无素材增强版-R2.mp4`；sha256 `95670ddf1675032ab958ab3a584e21a3608f48d84f5009ca553aee014c447ec7`；回执 `om_x100b639ab17624a0b3c7ca54ca87d83` |
| B08 | `Rve-StatCounter` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-ChartAnimation` + `Snapcn-WordFlip` + `Talkcraft-ink-underline` | `8fe2ced8db294852a47179261da1971a` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B08/B08-预算拆分-无素材增强版-R2.mp4`；sha256 `d344c1756676270956ead7abd6a5b49bd35531e1f64f8bbab20f703b93e2cae0`；回执 `om_x100b639b44337c88b2c85bb7e6676f9` |
| B09 | `Rve-ComparisonChart` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-StatCounter` + `Talkcraft-strike-and-replace` | `4968fc3e451f4b5a850f1a89f52fc17f` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B09/B09-数字差-无素材增强版-R2.mp4`；sha256 `21ef8c507130caff7abd709e44c26a8cbacdf1fb990f9469b718987e8e94eb66`；回执 `om_x100b639b5ad6b0b0b25b56d02624185` |
| B10 | `Rve-ChartAnimation` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-LineChart` + `Talkcraft-ink-underline` | `4d8ab6d506e7402188d555d3c8d2d119` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B10/B10-累计账本-无素材增强版-R2.mp4`；sha256 `228cc668d5165d7959403cf1a4d7fb0e3d219df3170c98c1a5c7121eb65f1b2a`；回执 `om_x100b639b6b3e84a0b1df30c5512e998` |
| B11 | `Rve-ProgressSteps` + `Snapcn-TextBuild` + `Snapcn-AnswerHighlight` + `Rve-SplitScreen` + `Rve-StatCounter` + `Talkcraft-word-slot-cycle` | `96a2e74bbfbb476faac9893081a83bb6` R1 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B11/B11-条件分支-无素材增强版-R1.mp4`；sha256 `0aabe1ee17fac8cf8ce49793f7b2a98f0690c6e9f1d4d4386c25cefbbe357137`；回执 `om_x100b639b67687ca0b12e0c7d99b4572` |
| B12 | `Rve-QuoteCard` + `Snapcn-WordFlip` + `Snapcn-TextHighlight` + `Talkcraft-source-converge` + `Rve-StatCounter` + `Rve-ProgressSteps` | `cdcc40d383f44cecaee60c80cf07c085` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B12/B12-关系链-无素材增强版-R2.mp4`；sha256 `d574169adde19784c2c49b692d90c1c6aa996219147920101ba786e2e9ff0386`；回执 `om_x100b639b7b1188a4b2afb079d40327f` |
| B13 | `Rve-SplitScreen` + `Snapcn-TextRewrite` + `Snapcn-TextHighlight` + `Snapcn-TextSwap` + `Rve-StatCounter` + `Talkcraft-error-retype` + `Rve-QuoteCard` + `Talkcraft-strike-and-replace` | `58ea685395964c5299ccd480791a20b8` R1 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B13/B13-误区纠正-无素材增强版-R1.mp4`；sha256 `7251c1aaf18fe165f3c2201b226fd0225d3ee8d17eaee19123866a31e1b7a638`；回执 `om_x100b639b774f74a0b3092107fefecc2` |
| B14 | `Snapcn-AnswerStream` + `Snapcn-SearchTyping` + `Snapcn-AnswerHighlight` + `Bits-ChatConversation` + `Snapcn-TextBuild` + `Rve-StatCounter` | `b0245efd3db34046b15a52e9e6bea464` R1 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B14/B14-提问回答-无素材增强版-R1.mp4`；sha256 `b61923c9fbbcf66ce56a471f42254f5557fad639b591bb9edac964904e7ac989`；回执 `om_x100b639b70c76cacb48d34117014e75` |
| B15 | `Rve-QuoteCard` + `Talkcraft-title-demote-to-label` + `Snapcn-TextHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Rve-ChartAnimation` + `Snapcn-TextBuild` | `72daf450e6084d4a87bdba26db3ae75c` R2 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B15/B15-核实状态分类-无素材增强版-R2.mp4`；sha256 `591f651fd59d4fc5846641bb1b1a5305f6a1eeb470cad3963824b8ae359fda98`；回执 `om_x100b639b09dc18a8b16922f81a286bd` |
| B16 | `Rve-ProgressSteps` + `Talkcraft-title-demote-to-label` + `Talkcraft-keyword-pop-highlight` + `Rve-StatCounter` + `Snapcn-WordFlip` + `Rve-QuoteCard` + `Snapcn-TextHighlight` | `771fd77fc49a4c008127170d54c904a8` R1 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B16/B16-优先级排序-无素材增强版-R1.mp4`；sha256 `da6476600de75b3534ecb98fcf88c5a25597f415998890e7a4f678dcc23f56ba`；回执 `om_x100b639b046c28a0b1cb01f3f44fa9a` |
| B17 | `Bits-ChatConversation` + `Talkcraft-line-by-line-slide` + `Snapcn-AnswerHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Snapcn-TextBuild` | `62d2f3fd1e8540e2b4240087b7158bde` R1 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B17/B17-倒数检查-无素材增强版-R1.mp4`；sha256 `53f0bd54988270c0fc4a28e7a3755f1dbb0407ecd11173bfe4e3e0ede5ae6a56`；回执 `om_x100b639b1b7b7cacb11a08af355fdc7` |
| B18 | `Rve-ComparisonChart` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-ProgressSteps` + `Talkcraft-strike-and-replace` | `ba3755ea92ba4df884e747ca2b8b7f2f` R1 / 18 秒 | `.runtime/videoagents/component-set-samples/no-material-delivery/B18/B18-操作步骤前后-无素材增强版-R1.mp4`；sha256 `feb238525d52f4c4eda004d586a94d64dd6f9fc5d2897ed936739f94e38d96af`；回执 `om_x100b639b178c8cbcb2995bfb87cb478` |

所有扩展样片的数字、预算、时长、动作数和模拟对话都是表达样片；真实视频使用时必须替换为当前任务有来源的事实或明确写成演示口径。
<!-- B07-B18-EXPANDED-DEMOS:END -->

<!-- A07-A12-MATERIAL-RICH:START -->
## A07-A12：有素材增强 Graph 样片

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
