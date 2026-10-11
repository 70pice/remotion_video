# 30 套组件套：导演选型与使用指导

备案来源：[component-set-registry.json](component-set-registry.json)。30 套全部登记；登记不等于人工品鉴通过，真实 review_status 与历史视频、分支及回执继续保留。

导演运行时直接从备案 JSON 和 `videoagents/component-set-capabilities.json` 注入逐套场景、排除场景、表达顺序、生产适配方法、内容与素材边界，不要求模型凭名字随机选择。本文与 JSON 的 director_guidance 保持一致。

## 创建普通视频时怎样使用

普通视频通过 `Shot.set_design` 做 typed production selection：导演按本段表达目的、素材类型和真实内容选择 `set_id`，有素材套绑定当前任务的 `asset_src` 与 `source_label`，Shot 级 `title/body` 承载公开标题和正文，并在 `set_design.content` 填本期条目、指标、takeaway 与 `source_refs`。模板固定 `parts` 使用 `start_frame`、`end_frame` 和 `box` 调整本镜头内的出现时刻、大小、位置与间距。

实际生产 native IDs 以 `videoagents/component-set-capabilities.json` 的 `sets[].parts[].component_id` 展开结果为准；component-demo 样片组合和 registry 历史 `components.native_ids` 可能不同，不能拿样片组合当生产组件计数。渲染器先展开 metadata 默认 part、box 和 start/end ratio，再做素材、内容、safe_area、focus、局部时钟和组件计数校验。

`component_demo` 仍用于样片回放和品鉴记录；普通生产不得再使用旧样片 marker，例如 `component_set`、`composition`、`rich_content`、`component_demo_recipe` 或任意 JSX/CSS。生产内容必须来自当前 job，不能从另一个 job_id 复用素材、音频或样片状态。

1. 按本段目的选套：人物/现场、App/操作、账单/数字、作品细节、关系流程、问题/概念/问答/结论。
2. 核对素材和事实：有素材套传当前 job 的 `asset_src` 与 `source_label`；无素材套不伪造素材。数字无依据就省略或留下缺口。
3. 填 Shot 字段和 `set_design.content`：Shot.title 不超过18字、Shot.body 不超过60字，content.takeaway 不超过18字；`items`、`supporting_items`、`metric`、`numeric_items` 按套件字段规则和事实口径填写。
4. 只有 metadata.focus_supported=true 的套件可传 `focus_steps/source_size`，当前是 A03、A05、A06、A09；其他套件用 parts 的 `start_frame/end_frame` 与 safe-area `box` 调整表达。
5. 为每个固定 part 设置本地起止帧和 safe_area 归一化 box。box 的 x/y/width/height 均在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400。
6. 镜头和 part 时长由实测 captions、阅读时间和素材可读性决定；不照搬样片 12–20 秒，不强制每 2–3 秒切套，也不设置硬性数量配额。
7. 经任务 API / Worker / VideoProductionGraph 生成不超过30秒的 director Demo MP4，停在 `director_human_gate` 等人工审核；审核通过后才进入 editing。Demo 待审时不能声称完整成片已渲染；完整剪辑实际完成后以 `DRAFT / complete` 交付成片，由用户决定是否发布。

底层组件参数和允许角色见 [组件知识库](knowledge/remotion-shot-library.md)、`videoagents/native-component-capabilities.json` 与导演当次输出 schema。共享套件名称、main_component_id、固定 part、默认 box、默认 start/end ratio、material_kind、focus_supported 和 safe_area 由现有 `videoagents/component-set-capabilities.json` 提供；本文档记录使用规则，不复制默认布局数值。

## 有素材：A01–A12

### A01 人物处境

什么时候用：需要先让观众知道这件事发生在谁身上、和家里人有什么关系。；素材主体是人物或生活场景，不需要逐项阅读证据。

怎么表达：先展示具体人物和生活现场 → 白字提出此人的处境 → 强调与本段问题有关的一条线索

普通生产怎么用：普通生产直接选择 set_design.set_id=A01，asset_src 绑定当前任务人物/生活图片，Shot.title/body 写本期人物处境，content 写线索和收束句；parts 使用模板固定 part_id，并按真实 captions 设置 start_frame/end_frame 与 caption-safe box。

set_design 填法：`set_id=A01`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Bits-KenBurns, Snapcn-TextReveal, Rve-QuoteCard, Rve-ProgressSteps, Snapcn-WordFlip, Snapcn-TextHighlight。

素材要求：人物或生活图片主体清晰，最好有手机、家庭或真实场景信息。 支持类型：image。

内容约束：身份、地点、经历来自本期资料；情境示意要明确身份，不能当案件照片。；A01 样片接口只开放素材和时长，不能通过替换素材宣称已替换固定样片文案。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合解释复杂关系图、操作教程或需要圈选原文的证据阅读。；不适合素材里主体太小、人物与主题无关的图片。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A02 App对象

什么时候用：需要先让观众认出这是哪个 App、页面或功能区域。；素材是手机界面图片或录屏，但本段只解释界面对象和入口职责，不演示连续操作。

怎么表达：先展示 App 或手机页面整体 → 用白字说明界面身份和本段要看的入口 → 用列表/强调 part 解释入口职责或注意点

普通生产怎么用：普通生产直接选择 set_design.set_id=A02，asset_src/source_label 绑定当前任务 App 界面图片或录屏，content.items 写真实入口/功能；metadata.material_kind=image_or_video 且 focus_supported=false，生产不传 focus_steps/source_size，不承诺橙色目标圈或逐步点击同步，只用 parts 的 start_frame/end_frame 与 safe-area box 调整界面说明。

set_design 填法：`set_id=A02`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-PhoneFrame, Snapcn-TextReveal, Rve-ProgressSteps, Snapcn-WordFlip, Talkcraft-source-converge, Snapcn-TextHighlight。

素材要求：手机界面图片或录屏，页面身份和主要入口清楚；生产用于识别对象和入口职责，不要求连续点击过程。 支持类型：image_or_video。

内容约束：App 名称、页面身份、入口职责必须来自当前素材或本期来源。；静态首页只能说明入口和功能位置，不能写成已经点击成功或完成操作。；完整操作教学、目标圈跟随和步骤结果需要另用 A03/A09 等 focus_supported=true 的套件。；component_sample 历史样片仍可使用 tutorial_steps；普通生产不传 tutorial_steps、focus_steps/source_size。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合完整操作教程、逐步点击跟随或需要目标圈同步的录屏；这类生产镜头用 focus_supported=true 的 A03/A09。；不适合控件太小、界面身份不清或关键入口被遮挡的素材。

component_sample 可调入参（历史样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, tutorial_steps[].start_frame, tutorial_steps[].end_frame, tutorial_steps[].instruction, tutorial_steps[].target。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A03 操作过程

什么时候用：素材是完整操作录屏，需要解释当前正在输入、点击或查看哪里。；旁白要强调动作过程，而不是只介绍 App 长什么样。

怎么表达：连续播放输入动作 → 按旁白指出点击动作 → 停留查看真实结果

普通生产怎么用：普通生产直接选择 set_design.set_id=A03，asset_src 绑定当前任务操作录屏，Shot.title/body 写本期操作说明，content 写真实操作口令；focus_steps 与 source_size 来自实测画面，part 本地时钟按每步 captions 重新展开。

set_design 填法：`set_id=A03`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套支持生产 focus_steps/source_size；只标当前素材中真实存在的位置或操作。

实际生产原生映射（来自 component-set-capabilities.json）：video, Snapcn-TextReveal, Rve-ProgressSteps, Snapcn-TextBuild, Snapcn-TextSwap, Snapcn-TextHighlight。

素材要求：操作录屏须覆盖完整动作，并能按帧标出输入框、按钮、结果区域。 支持类型：video。

内容约束：视频区间覆盖实际动作，不循环素材凑长度。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=true；focus_steps/source_size 只标当前素材中真实存在的位置或操作。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合静态证据资料或结果海报。；不适合动作与标题对不上的录屏。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, focus_steps[].start_frame, focus_steps[].end_frame, focus_steps[].instruction, focus_steps[].target。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A04 作品结果

什么时候用：素材本身是一个完整结果，需要保持展示感。；旁白要从整体作品逐步指向某几个细节。

怎么表达：先看完整作品 → 说明一个可见细节 → 回到作品整体与结果判断

普通生产怎么用：普通生产直接选择 set_design.set_id=A04，asset_src/source_label 绑定当前任务作品/结果图，Shot.title/body 写本期整体判断，content 写可见细节和收束句；metadata.focus_supported=false，生产不传 focus_steps/source_size，细节说明通过 parts 时序和 safe-area box 安排。

set_design 填法：`set_id=A04`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Talkcraft-tilt-3d-page, Snapcn-TextReveal, Rve-QuoteCard, Talkcraft-ink-underline, Snapcn-WordFlip, Snapcn-TextHighlight。

素材要求：作品或结果图完整清晰，局部亮点能用归一化框定位。 支持类型：image。

内容约束：完整作品、局部细节与旁白一致，不冒充已核实成果。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合需要逐步点击的教程录屏。；不适合小字密集证据资料，除非只看视觉结果。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, focus_steps[].start_frame, focus_steps[].end_frame, focus_steps[].instruction, focus_steps[].target。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A05 原文证据

什么时候用：素材是可读资料，需要解释资料身份、原文句子和关键词。；旁白必须对应原文，而不是只用截图当背景。

怎么表达：先交代资料来源和身份 → 展示能支撑旁白的原文 → 突出关键词并解释边界

普通生产怎么用：普通生产直接选择 set_design.set_id=A05，asset_src/source_label 绑定当前任务原文截图；metadata.focus_supported=true 时可用 focus_steps/source_size 标本期截图中真实存在的句子、数字或来源身份。

set_design 填法：`set_id=A05`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套支持生产 focus_steps/source_size；只标当前素材中真实存在的位置或操作。

实际生产原生映射（来自 component-set-capabilities.json）：evidence, Snapcn-TextReveal, Talkcraft-source-converge, Rve-QuoteCard, Snapcn-TextBuild, Snapcn-TextHighlight。

素材要求：原文截图或资料页需可读，有清楚来源身份；重点句和关键词可被定位。 支持类型：image。

内容约束：原文、否定词、数字单位都必须与当前旁白对应。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=true；focus_steps/source_size 只标当前素材中真实存在的位置或操作。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合不可读、来源身份不清或含播放器控件的截图。；不适合用论文截图硬凑画面节奏。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, focus_steps[].start_frame, focus_steps[].end_frame, focus_steps[].instruction, focus_steps[].target。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A06 关系图解

什么时候用：素材已经是一张清楚的图解，需要按节点或箭头讲清关系。；旁白讲的是结构，而不是单个证据句。

怎么表达：保留图解全貌 → 按旁白解释节点职责 → 沿已有箭头讲清连接和结果

普通生产怎么用：普通生产直接选择 set_design.set_id=A06，asset_src/source_label 绑定当前任务关系图，content.items 写图中真实节点/连接；metadata.focus_supported=true 时可用 focus_steps/source_size 定位已有节点或箭头，不新增假关系。

set_design 填法：`set_id=A06`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套支持生产 focus_steps/source_size；只标当前素材中真实存在的位置或操作。

实际生产原生映射（来自 component-set-capabilities.json）：image_focus, Snapcn-TextReveal, Rve-ProgressSteps, Rve-SplitScreen, Talkcraft-source-converge, Snapcn-TextHighlight。

素材要求：关系图需要节点和标签清楚，手机端可读；每个讲述点能用归一化框定位。 支持类型：image。

内容约束：节点、箭头和标签必须真实存在，不能把并列项读成因果。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=true；focus_steps/source_size 只标当前素材中真实存在的位置或操作。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合复杂到手机端看不清的图。；不适合没有明确节点、箭头或标签的普通图片。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, focus_steps[].start_frame, focus_steps[].end_frame, focus_steps[].instruction, focus_steps[].target。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A07 人物线索

什么时候用：人物、家庭或生活现场图片，需要把注意力落到具体线索和行动。

怎么表达：人物现场先建立代入 → 逐项解释可见线索 → 落到当事人的动作或处境

普通生产怎么用：普通生产直接选择 set_design.set_id=A07，asset_src 绑定当前任务人物线索图片，Shot.title/body 写本期标题正文，content 写真实 takeaway、items 与 supporting_items；parts 对应模板固定组件，逐项按 captions 调整本地起止和布局。

set_design 填法：`set_id=A07`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Talkcraft-slow-push-in, Snapcn-TextReveal, Rve-QuoteCard, Rve-ProgressSteps, Snapcn-WordFlip, Talkcraft-source-converge, Snapcn-TextHighlight。

素材要求：显式导入当前任务的对应素材；演示素材注明身份。 支持类型：image/png, image/jpeg, image/webp。

内容约束：线索能在图片或本期来源中定位，不能为人物编对白。；样片 items 与 supporting_items 各三项、一一对应；普通生产按 set_design 展开固定parts并映射真实原生组件。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：原文证据逐句阅读、完整操作教学或没有可说明线索的人物图片。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A08 界面功能拆解

什么时候用：介绍App首页不同入口的职责，让观众先认出界面再操作。

怎么表达：先认出 App 界面 → 按入口拆解职责 → 区分功能入口与使用结果

普通生产怎么用：普通生产直接选择 set_design.set_id=A08，asset_src 绑定当前任务界面图片，content.items 写真实入口职责；parts 可调入口出现时刻、字号和间距，不能把图片外不存在的功能结果写成事实。

set_design 填法：`set_id=A08`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-PhoneFrame, Snapcn-TextReveal, Rve-ProgressSteps, Rve-SplitScreen, Snapcn-WordFlip, Talkcraft-source-converge, Snapcn-TextHighlight。

素材要求：显式导入当前任务的对应素材；演示素材注明身份。 支持类型：image/png, image/jpeg, image/webp。

内容约束：样片 items 与 supporting_items 各三项，必须与界面入口对应。；首页图片仅能说明入口；真实操作和结果需另有连续录屏。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：静态首页无法支持完整点击过程或操作成功结果。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A09 操作跟随

什么时候用：连续操作录屏教学，口令、目标圈和操作步骤需要同步。

怎么表达：口令出现时圈住实际输入区域 → 保存动作与目标圈同步 → 列表结果出现后核对完成状态

普通生产怎么用：普通生产直接选择 set_design.set_id=A09，asset_src/source_label 绑定当前任务 MP4；metadata.focus_supported=true，content.items 必须与 focus_steps.instruction 对齐，focus_steps 连续覆盖真实操作区间，source_size 使用实测素材尺寸。

set_design 填法：`set_id=A09`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套支持生产 focus_steps/source_size；只标当前素材中真实存在的位置或操作。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-PhoneFrame, Snapcn-TextReveal, Rve-ProgressSteps, Rve-StatCounter, Snapcn-TextBuild, Snapcn-TextSwap, Snapcn-TextHighlight。

素材要求：显式导入当前任务的对应素材；演示素材注明身份。 支持类型：video/mp4。

内容约束：有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=true；focus_steps/source_size 只标当前素材中真实存在的位置或操作。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：没有连续动作的静态图片、按钮不可读或口令与画面不符的录屏。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric, focus_steps。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A10 账单核算

什么时候用：账单或费用图片，需要逐笔核对再看合计和累计口径。

怎么表达：在账单上逐笔核对 → 同步列出同单位金额 → 核算合计并解释累计口径

普通生产怎么用：普通生产直接选择 set_design.set_id=A10，asset_src 绑定当前任务账单图，content.numeric_items 写同单位真实金额，metric.value 等于合计；parts 的扫描、下划线、统计和图表按本期账单位置与 captions 重排。

set_design 填法：`set_id=A10`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Talkcraft-scanline-annotate, Snapcn-TextReveal, Rve-ChartAnimation, Rve-StatCounter, Snapcn-TextBuild, Rve-LineChart, Talkcraft-ink-underline。

素材要求：显式导入当前任务的对应素材；演示素材注明身份。 扫描框对应样例三笔明细行与合计行位置，替换图片须保持同版式；不自动识别金额区域。 支持类型：image/png, image/jpeg, image/webp。

内容约束：三笔 numeric_items 使用同单位，metric 合计必须等于三笔之和；金额来自当前账单。；样片扫描位置固定对应原样例三行明细和合计；替换图片须保持同版式，不自动识别新账单。；普通生产不得复制样片固定扫描位置或任何演示金额。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：与样片明细位置不匹配却直接替换的账单、没有真实金额口径的账单。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A11 作品细节

什么时候用：作品、插画或海报展示，需要拆出几个构图细节。

怎么表达：先看完整作品构图 → 拆出对应的几个细节 → 把细节汇合为作品判断

普通生产怎么用：普通生产直接选择 set_design.set_id=A11，asset_src 绑定当前任务作品图，content.items/supporting_items 写可见细节；parts 可调整页面透视、引用、汇合和墨线的起止，但不能裁掉关键构图。

set_design 填法：`set_id=A11`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Talkcraft-tilt-3d-page, Snapcn-TextReveal, Rve-QuoteCard, Snapcn-WordFlip, Talkcraft-source-converge, Talkcraft-ink-underline, Snapcn-TextHighlight。

素材要求：显式导入当前任务的对应素材；演示素材注明身份。 支持类型：image/png, image/jpeg, image/webp。

内容约束：样片 items 与 supporting_items 各三项，文字对应可见细节。；生产parts可调本地时钟和安全区布局，但不开放任意坐标或自由源码；不能裁掉重要构图。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：小字密集的报告证据、需要逐步点击的教程。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### A12 图解关系

什么时候用：流程或关系图片，需要说明每个环节的职责和连接。

怎么表达：先看关系全貌 → 逐项解释环节职责 → 说明连接方向和结果

普通生产怎么用：普通生产直接选择 set_design.set_id=A12，asset_src 绑定当前任务图解，content.items/supporting_items 写真实节点、职责和连接；parts 按关系讲述顺序展开，布局下沿保持在字幕安全线以上。

set_design 填法：`set_id=A12`；必须绑定当前 job 的 asset_src/source_label；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Talkcraft-slow-pull-reveal, Snapcn-TextReveal, Rve-SplitScreen, Rve-ProgressSteps, Talkcraft-source-converge, Snapcn-WordFlip, Snapcn-TextHighlight。

素材要求：显式导入当前任务的对应素材；演示素材注明身份。 支持类型：image/png, image/jpeg, image/webp。

内容约束：样片 items 与 supporting_items 各三项，与图中节点一一对应。；只说明来源支持的关系，不能把假设链路当案件结论；图中关键连接要保留。；有素材生产必须提供当前 job 的 asset_src 与 source_label。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：手机端不可读的复杂图、没有明确节点连接的图片。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：asset_id, duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

## 无素材：B01–B18

### B01 问题开场

什么时候用：开头需要抛出一个和普通人有关的问题。；没有合适图片或视频，但需要快速建立悬念。

怎么表达：提出普通人的具体问题 → 逐项揭示判断线索 → 落到本段需要回答的问题

普通生产怎么用：普通生产直接选择 set_design.set_id=B01，不传 asset_src；content 写本期真实问题、判断线索和收束句，metric 只有有来源数字时填写，parts 按开场旁白而非固定秒数展开。

set_design 填法：`set_id=B01`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-QuoteCard, Rve-ProgressSteps, Rve-StatCounter, Snapcn-WordFlip, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产必填 Shot.title、Shot.body 与 content.takeaway；component_sample 保留样片 content 标题字段。 支持类型：无外部素材。

内容约束：问题来自本期，不能编聊天记录；items 是核对线索。；样片 metric 只是演示锚点，新视频无依据数字应省略，不能为填满模板编数字。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合当作证据画面。；不适合替代真实人物案例素材。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B02 概念解释

什么时候用：解释 AI 机制、平台规则或新词。；需要把术语转成生活语言。

怎么表达：先指出容易混淆的词 → 换成白话动作或结果 → 保留条件并给出准确解释

普通生产怎么用：普通生产直接选择 set_design.set_id=B02，不传 asset_src；Shot.title/body 写本期概念说明，content 写改写前后说法，parts 按解释节奏调整，不用演示数字冒充模型能力。

set_design 填法：`set_id=B02`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Snapcn-WordFlip, Rve-ProgressSteps, Rve-StatCounter, Talkcraft-word-slot-cycle, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产必填 Shot.title、Shot.body 与 content.takeaway；component_sample 保留样片 content 标题字段。 支持类型：无外部素材。

内容约束：一段只解释一个概念；保留否定和条件。；演示次数不代表性能、风险或模型能力。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合承载真实引用原文。；不适合一次塞多个概念。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B03 两种情况对比

什么时候用：需要回答“为什么 A 和 B 不一样”。；需要让观众快速比较风险、成本或门槛。

怎么表达：明确比较的是哪两种情况 → 同维度展示差别 → 给出有条件的判断

普通生产怎么用：普通生产直接选择 set_design.set_id=B03，不传 asset_src；content.items/numeric_items 使用同一比较维度和口径，parts 按左右对比和结论时刻重排。

set_design 填法：`set_id=B03`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-SplitScreen, Rve-ComparisonChart, Snapcn-TextBuild, Snapcn-TextSwap, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产必填 Shot.title、Shot.body 与 content.takeaway；component_sample 保留样片 content 标题字段。 支持类型：无外部素材。

内容约束：两侧比较对象、时间范围和单位一致。；动作数或示意数字不能被解释成安全概率。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合三项以上复杂比较。；不适合没有明确比较维度的情绪表达。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B04 数字账本

什么时候用：需要让观众看懂代价、收益或规模。；旁白里有少量关键数字需要被记住。

怎么表达：逐笔显示金额 → 说明每笔是什么 → 核对合计与累计

普通生产怎么用：普通生产直接选择 set_design.set_id=B04，不传 asset_src；content.numeric_items 与 metric 使用同单位真实数字，parts 的计数、图表和条目揭示跟随本期 captions。

set_design 填法：`set_id=B04`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-StatCounter, Snapcn-TextBuild, Rve-ChartAnimation, Rve-LineChart, Talkcraft-ink-underline。

素材要求：不传图片或视频；普通生产必填 Shot.title、Shot.body 与 content.takeaway；component_sample 保留样片 content 标题字段。 支持类型：无外部素材。

内容约束：样片三笔 numeric_items 同单位，metric 为三笔之和。；普通视频的金额、单位、营收/利润等口径必须有本期来源。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合没有口径来源的数字。；不适合密集表格或多页报表。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B05 步骤演示

什么时候用：讲“先做什么、再看什么、最后怎么判断”。；结尾给家人可执行的检查流程。

怎么表达：显示第一步动作 → 下一步解释看什么 → 最后给出判断或确认动作

普通生产怎么用：普通生产直接选择 set_design.set_id=B05，不传 asset_src；content.items/supporting_items 写本期真实步骤，metric 仅表示步骤数或有来源指标，parts 按步骤本地时钟展开。

set_design 填法：`set_id=B05`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ProgressSteps, Rve-StatCounter, Rve-QuoteCard, Snapcn-TextBuild, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产必填 Shot.title、Shot.body 与 content.takeaway；component_sample 保留样片 content 标题字段。 支持类型：无外部素材。

内容约束：items 与 supporting_items 一一对应，metric 只表示步骤数。；无素材步骤图是说明，不得冒充 App 实录或操作成功。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合冒充真实 App 操作。；不适合替代 A02/A03 真实录屏教程。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B06 结论行动

什么时候用：需要把前文判断落到观众能做的 2-4 件事。；适合防骗、工具使用、家庭沟通类结尾。

怎么表达：回应开头问题 → 展开观众能做的动作 → 用最后一句收束判断

普通生产怎么用：普通生产直接选择 set_design.set_id=B06，不传 asset_src；Shot.title/body 写结论，content 写前文已经解释过的行动，parts 可按结尾旁白调整数量、间距和显隐时刻。

set_design 填法：`set_id=B06`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Bits-ChatConversation, Rve-StatCounter, Snapcn-TextBuild, Rve-ProgressSteps, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产必填 Shot.title、Shot.body 与 content.takeaway；component_sample 保留样片 content 标题字段。 支持类型：无外部素材。

内容约束：行动来自前文已解释的结论，不引入新主张。；样片三项结构不限制新视频行动数，普通生产仍按字段上限和阅读时间。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不适合空泛口号。；不适合引入未经解释的新观点。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B07 时间分配

什么时候用：旁白讲“先花几分钟分开做三件事”、解释时间分配或提醒观众先停一下再操作时使用。

怎么表达：给出总时间或时间条件 → 分拆各动作的时间 → 说明先后与暂停点

普通生产怎么用：普通生产直接选择 set_design.set_id=B07，不传 asset_src；content.numeric_items/metric 写同单位时间分配或明确示意，parts 按本期时间解释重排，不套用样片折线。

set_design 填法：`set_id=B07`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ProgressSteps, Rve-StatCounter, Snapcn-WordFlip, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：示意分配须标注，不能当实测耗时或风险降低证据。；各项时间同单位；合计与 metric 一致。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：没有实测来源却当作真实耗时统计。；声称示意时间分配能量化降低风险。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B08 预算拆分

什么时候用：需要解释预算去向、分拆金额，或提醒付款前先看用途。

怎么表达：先说明预算范围 → 分拆用途 → 核对总额并回到付款判断

普通生产怎么用：普通生产直接选择 set_design.set_id=B08，不传 asset_src；content.numeric_items/metric 写本期预算去向和总额，parts 按付款判断时刻揭示，不把示例价当行情。

set_design 填法：`set_id=B08`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-StatCounter, Snapcn-TextBuild, Rve-ChartAnimation, Snapcn-WordFlip, Talkcraft-ink-underline。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：示意预算不是市场价格或产品收费；真实报价需本期来源。；分项之和与 metric 总额一致。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：把示意预算写成真实收费标准、推荐价格或市场行情。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B09 数字差

什么时候用：旁白对比“直接照做”和“先回拨核实”等两种做法时使用。

怎么表达：展示两种做法 → 明确同维度数字 → 显示差值及其含义

普通生产怎么用：普通生产直接选择 set_design.set_id=B09，不传 asset_src；Shot.title/body 写对比主题，content 写两种做法、同口径数字和差值，parts 按对比到差值再解释含义的 captions 展开。

set_design 填法：`set_id=B09`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ComparisonChart, Rve-StatCounter, Snapcn-TextSwap, Talkcraft-strike-and-replace, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：差值按输入真实计算，单位和比较口径一致。；步骤差不是风险分、胜率或更安全的量化证明。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于证明某个选择一定更安全。；不用于概率、胜率或风险分数。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B10 累计账本

什么时候用：旁白讲“单次看不大，但合起来要算总账”时使用。

怎么表达：先展示单次金额或数量 → 逐项展开累计 → 核对总账并解释口径

普通生产怎么用：普通生产直接选择 set_design.set_id=B10，不传 asset_src；content.numeric_items/metric 写本期累计口径，parts 的累计、统计和趋势线按真实数据与旁白展开。

set_design 填法：`set_id=B10`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ChartAnimation, Rve-LineChart, Snapcn-TextBuild, Rve-StatCounter, Talkcraft-ink-underline。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：示意账本不是真实消费记录；真实账单需要实际来源。；累计严格来自逐笔数据，不能凭冲击力造大数字。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：把示意累计当作真实账单或消费记录。；没有逐笔口径的冲击性大数字。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B11 条件分支

什么时候用：旁白需要讲“如果出现这种条件，就做这个动作”的流程判断时使用。

怎么表达：说明触发条件 → 对应给出动作 → 保留未满足条件的另一结果

普通生产怎么用：普通生产直接选择 set_design.set_id=B11，不传 asset_src；content.items 写条件分支，保留“如果/否则/前提”等限定，parts 按分支说明时刻调整。

set_design 填法：`set_id=B11`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ProgressSteps, Rve-StatCounter, Snapcn-TextBuild, Talkcraft-word-slot-cycle, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：items 是条件，supporting_items 是对应动作。；流程图只解释本期规则，不声称系统已自动判定或执行。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于自动判定结果。；不用于替代真实产品流程图或真实规则。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B12 关系链

什么时候用：旁白解释 AI文字、真人视频、付款入口等链路关系时使用。

怎么表达：列出不同参与者或环节 → 解释每个职责 → 讲清连接方向与结果

普通生产怎么用：普通生产直接选择 set_design.set_id=B12，不传 asset_src；content.items/supporting_items 写来源支持的角色和连接，parts 按关系链顺序展开，不把并列关系写成因果。

set_design 填法：`set_id=B12`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-QuoteCard, Talkcraft-source-converge, Rve-ProgressSteps, Snapcn-WordFlip, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：AI 文字、真人视频、付款入口等具体事实需要本期证据。；图形解释不是真实关系图证据；不把示意数量当真实规模。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于认定真实案件事实。；不用于替代有来源的关系图证据。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B13 误区纠正

什么时候用：旁白纠正“会聊天就可信”“能视频就是真人”等捷径判断时使用。

怎么表达：显示被纠正的说法 → 保留否定并替换准确说法 → 给出能执行的判断依据

普通生产怎么用：普通生产直接选择 set_design.set_id=B13，不传 asset_src；Shot.title/body 写误区主题，content 写错误说法、纠正说法和必要否定，parts 按误区出现、划掉、改写和收束的本地时钟展开。

set_design 填法：`set_id=B13`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-SplitScreen, Talkcraft-error-retype, Rve-QuoteCard, Talkcraft-strike-and-replace, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：纠正具体判断依据，不能据此给具体人或平台定罪。；替代表述须有依据；数字只作明确的条目计数。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于给具体对象下结论。；不用于没有替代表述的空泛反驳。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B14 提问回答

什么时候用：旁白采用问答结构，例如“视频通话就可信吗？”时使用。

怎么表达：提出观众会问的问题 → 按口播回答 → 补充条件与下一步

普通生产怎么用：普通生产直接选择 set_design.set_id=B14，不传 asset_src；Shot.title/body 写本期真实提问，content 写回答要点，parts 按问答流展开，不伪造聊天头像或平台对话。

set_design 填法：`set_id=B14`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Snapcn-AnswerStream, Bits-ChatConversation, Snapcn-TextBuild, Rve-StatCounter, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：问答是说明，不能冒充客服、警方或当事人聊天记录。；回答保留条件，条目数字不表示可信度评分。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于真实聊天记录。；不用于冒充平台客服、警方或当事人对话。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B15 核实状态分类

什么时候用：旁白需要区分“有人这么说”“有出处”“还没确认”时使用。

怎么表达：列出本期说法 → 区分自述、有出处、未确认 → 说明每类还需怎样核对

普通生产怎么用：普通生产直接选择 set_design.set_id=B15，不传 asset_src；content.items/supporting_items 写每条说法及核实状态，parts 按分类和状态揭示时刻调整。

set_design 填法：`set_id=B15`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-QuoteCard, Rve-ChartAnimation, Rve-ProgressSteps, Snapcn-TextBuild, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：状态分类不是证据等级、真实性概率或权重。；每条状态依据本期来源；不能因为归类就认定必真或必假。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于证据等级排序。；不用于暗示某类信息一定真或一定假。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B16 优先级排序

什么时候用：旁白讲“先看A，再看B，最后看C”的操作建议时使用。

怎么表达：说明优先处理的动作 → 再显示后续动作 → 保留顺序理由

普通生产怎么用：普通生产直接选择 set_design.set_id=B16，不传 asset_src；content.items 写本期优先级和理由，parts 按排序说明逐项展开，不用排名视觉替代论证。

set_design 填法：`set_id=B16`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ProgressSteps, Rve-StatCounter, Snapcn-WordFlip, Rve-QuoteCard, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：排序是操作顺序，不是风险严重度评分。；没有先后关系的并列信息不套排序。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于风险严重度排序。；不用于没有顺序关系的并列信息。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B17 倒数检查

什么时候用：旁白提醒“转账前先问自己三件事”“先暂停一下”时使用。

怎么表达：在关键动作前提醒暂停 → 逐条提出检查问题 → 确认后再进入下一动作

普通生产怎么用：普通生产直接选择 set_design.set_id=B17，不传 asset_src；content.items 写本期倒数检查问题，parts 按检查节奏展开，倒数只表示条目进度，不改音频。

set_design 填法：`set_id=B17`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Bits-ChatConversation, Rve-ProgressSteps, Rve-StatCounter, Snapcn-TextBuild, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：计数与真实检查项一致，不能宣称检查后绝对安全。；适用于动作前提醒，不伪装为已发生交易的证据。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于真实聊天判断。；不用于已经完成付款后的证据展示。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。

### B18 操作步骤前后

什么时候用：旁白讲“以前只做一步，现在拆成三步”或解释操作改造前后时使用。

怎么表达：显示原来的操作方式 → 展开改造后的步骤 → 核对具体新增动作

普通生产怎么用：普通生产直接选择 set_design.set_id=B18，不传 asset_src；Shot.title/body 写前后对比主题，content 写动作差别和新增步骤，parts 按前后对比与步骤补充时刻展开。

set_design 填法：`set_id=B18`；不传 asset_src；Shot.title/body 与 content 来自当前脚本、素材和 source_refs；parts 使用 metadata 固定 part_id，默认展开后可按 captions 调整 start_frame/end_frame、大小和间距。本套不支持生产 focus_steps/source_size；用 parts 的 start_frame/end_frame 与 safe-area box 调整表达。

实际生产原生映射（来自 component-set-capabilities.json）：Snapcn-TextReveal, Rve-ComparisonChart, Rve-SplitScreen, Rve-ProgressSteps, Talkcraft-strike-and-replace, Snapcn-TextHighlight。

素材要求：不传图片或视频；普通生产传入 Shot.title、Shot.body 与结构化 set_design.content。 支持类型：无外部素材。

内容约束：前后动作与来源或明确建议一致，不能虚构亲测。；步骤变多不等于效果提升，不展示没有依据的提升率。；本套 metadata.focus_supported=false；普通生产不传 focus_steps/source_size，通过 parts 时序和 safe-area box 调整表达。

布局与时长：part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到画布后下沿不超过 y=1400；shot 时长按实测 captions 和阅读需要决定，不设硬性配额或固定2-3秒节奏。

不适合：不用于声称新做法一定提升效果。；不用于没有前后变化的普通步骤说明。

component_sample 可调入参（样片/回放接口，非生产 set_design 字段）：duration_seconds, sample_content.title, sample_content.body, sample_content.takeaway, sample_content.items, sample_content.supporting_items, sample_content.metric.label, sample_content.metric.value, sample_content.metric.detail, sample_content.numeric_items。普通生产使用 `set_design`，Shot.title/body 不放入 content，不传旧样片 marker。
