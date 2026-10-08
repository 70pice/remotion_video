# Remotion 镜头库：飞书知识快照

来源：[Remotion组件库与video-talkcraft调研（2026-10-02）](https://icnpfyu4nynj.feishu.cn/sheets/UPpgsQJnLhgA0WtzlU2crIXqnOe)。

读取时间：2026-10-07T19:55:56+08:00；飞书版本：113；来源研究日期：2026-10-02。

这是来源表格的本地内容快照，覆盖全部 4 个工作表；导出读取了每表 A1:T200，包括隐藏行列，剔除纯空白行列。
表格中的历史验证、预览端口和版本记录属于来源说明，不代表当前服务已启动或本期视频已验证。

[结构化快照](remotion-shot-library.feishu.json) 保留工作表 ID、读取范围和真实行号。

## 导演学习入口

先通读本页的使用说明和组件目录，再结合 [组件库说明](../component-library.md)、[入口及源码索引](../component-paths.json)、[表达内容与适用场景](../component-use-guide.json) 和对应竖版源码学习。

正式制作由既有 component-study 步骤学习全部 152 个竖版预设和 9 个参数化适配器。无工具调用通过 component_source_guide 接收完整清单、用途、源码摘要和 SHA256，不把文件路径当作已读取的内容。本次导出的 152 条组件路径、表达内容与使用场景已逐条比对仓库索引，完全一致。

社区预设用于动效与布局；本期真实图片、视频、数据用参数化适配器承载。表中的演示图片、数字、代码和主持人不作为本期事实或新增素材。

2026-10-08 生产适配器补充：`evidence` / `image_focus` 的 `focus_cues` 可按真实旁白时刻，在同一镜头中连续展示总览、放大实测区域、聚焦压暗并拉回。坐标必须经过对应原图像素核验，保留口径与单位；固定18帧过渡，不能替换字幕时间或反复重新入场。数据卡的比较对象与必要单位开头可见，`reveal_frame` 仅揭示数值；竖屏两项为上下布局。导演要检查起点、等待阶段、每个揭示点前后及中段，避免只看最终状态漏掉大面积空白。

2026-10-08 连续读图补充：`region` 同时控制相机和聚焦，窄图例框会真正改变景别。比较多条曲线时先交代颜色与口径，保持完整趋势、坐标与必要图例可见；讲曲线变化时不单独放大图例。一次适度放大后，后续 cues 可以沿用同一实测 region、仅更新 label，避免观众在曲线、图例和坐标间反复重新找位置。该规则属于仓库制作经验，不是飞书原表中的历史能力。

2026-10-08 数据图生产接入：`data.visualization=bars/donuts` 复用 RemotionUI 动画柱状图、RVE 圆环底层，使用真实 `numeric_value`、单位、共同量程/基准和当前段落 `source_ref`。原默认数值卡与固定演示入口保留。图表 label 开头可见，detail 与数值、图形按实测 `reveal_frame` 用15帧揭示，预留说明空间，避免补集或倍数提前透露结果；无 cue 时直接显示。条形从0开始，圆环每项独立以100为分母。倍数比较用条形，组成比例用圆环，不把不同人群比例拼成一个整体。来源重绘的图表与原图/视频在覆盖报告中分开统计，不能称作实拍。只重画明确数值，不从曲线截图补造逐点数据。该能力是仓库本次生产接入，不是飞书原表已验证的历史生产能力。

## 飞书表格原始内容

### 组件目录

工作表 `aa0d33`；152 条记录。

| 飞书行号 | 组件名称 | 竖版相对文件路径 | 横版相对文件路径 | 适合表达的内容 | 适用场景 |
| --- | --- | --- | --- | --- | --- |
| 2 | Snapcn / TextReveal | src/components/component-vertical/snapcn/entries/text-reveal.tsx | src/components/component-horizontal/snapcn/entries/text-reveal.tsx | 表达一个新概念或章节标题正式登场 | 视频开场、章节开头，先把本段主题立住 |
| 3 | Snapcn / TextBuild | src/components/component-vertical/snapcn/entries/text-build.tsx | src/components/component-horizontal/snapcn/entries/text-build.tsx | 表达概念由零到完整的逐步搭建 | 解释 AI 概念定义、总结三层结构时使用 |
| 4 | Snapcn / TextHighlight | src/components/component-vertical/snapcn/entries/text-highlight.tsx | src/components/component-horizontal/snapcn/entries/text-highlight.tsx | 表达一句话中最该记住的关键词 | 口播讲到核心结论、术语或判断词时使用 |
| 5 | Snapcn / TextRewrite | src/components/component-vertical/snapcn/entries/text-rewrite.tsx | src/components/component-horizontal/snapcn/entries/text-rewrite.tsx | 表达旧提示词被修正成更好版本 | 讲提示词优化、纠错、改写前后对比时使用 |
| 6 | Snapcn / TextSwap | src/components/component-vertical/snapcn/entries/text-swap.tsx | src/components/component-horizontal/snapcn/entries/text-swap.tsx | 表达观点或措辞从 A 替换成 B | 讲旧说法不准、换成新结论时使用 |
| 7 | Snapcn / WordFlip | src/components/component-vertical/snapcn/entries/word-flip.tsx | src/components/component-horizontal/snapcn/entries/word-flip.tsx | 表达同一主体拥有多种能力或标签 | 列举 AI 能写作、检索、分析等能力时使用 |
| 8 | Snapcn / WordCaptions | src/components/component-vertical/snapcn/entries/word-captions.tsx | src/components/component-horizontal/snapcn/entries/word-captions.tsx | 表达配音中当前正在说的重点词 | 给短句口播做逐词强调字幕时使用 |
| 9 | Snapcn / KaraokeCaptions | src/components/component-vertical/snapcn/entries/karaoke-captions.tsx | src/components/component-horizontal/snapcn/entries/karaoke-captions.tsx | 表达连续讲解中观众应跟读的长句 | 长句字幕、旁白同步、解释性口播中使用 |
| 10 | Snapcn / SearchTyping | src/components/component-vertical/snapcn/entries/search-typing.tsx | src/components/component-horizontal/snapcn/entries/search-typing.tsx | 表达从一个问题开始寻找答案 | AI 搜索、问题引入、打开选题悬念时使用 |
| 11 | Snapcn / PromptSend | src/components/component-vertical/snapcn/entries/prompt-send.tsx | src/components/component-horizontal/snapcn/entries/prompt-send.tsx | 表达人向 AI 发出明确任务请求 | 演示输入提示词、点击发送、开始任务时使用 |
| 12 | Snapcn / PromptZoom | src/components/component-vertical/snapcn/entries/prompt-zoom.tsx | src/components/component-horizontal/snapcn/entries/prompt-zoom.tsx | 表达提示词写作是本段核心动作 | 讲提示词模板、输入框细节、产品首页时使用 |
| 13 | Snapcn / AnswerStream | src/components/component-vertical/snapcn/entries/answer-stream.tsx | src/components/component-horizontal/snapcn/entries/answer-stream.tsx | 表达 AI 正在生成答案或整理结论 | 展示模型输出、回答生成过程、结果揭晓时使用 |
| 14 | Snapcn / AnswerHighlight | src/components/component-vertical/snapcn/entries/answer-highlight.tsx | src/components/component-horizontal/snapcn/entries/answer-highlight.tsx | 表达长回答里真正有价值的一句 | 提炼 AI 答案、划出可执行建议时使用 |
| 15 | Snapcn / AgentSteps | src/components/component-vertical/snapcn/entries/agent-steps.tsx | src/components/component-horizontal/snapcn/entries/agent-steps.tsx | 表达 Agent 把复杂任务拆成步骤完成 | 讲工具调用、任务规划、自动化流程时使用 |
| 16 | Snapcn / TerminalSimulator | src/components/component-vertical/snapcn/entries/terminal-simulator.tsx | src/components/component-horizontal/snapcn/entries/terminal-simulator.tsx | 表达命令行中按顺序执行和反馈的过程 | AI Coding、部署、测试、终端教程中使用 |
| 17 | Snapcn / ChannelThread | src/components/component-vertical/snapcn/entries/channel-thread.tsx | src/components/component-horizontal/snapcn/entries/channel-thread.tsx | 表达多人或多 Agent 正在协作讨论 | 团队协作、Agent 群聊、对话式决策时使用 |
| 18 | Snapcn / PhoneFrame | src/components/component-vertical/snapcn/entries/phone-frame.tsx | src/components/component-horizontal/snapcn/entries/phone-frame.tsx | 表达手机端 AI 产品或 App 场景 | 展示移动应用、竖屏产品界面时使用 |
| 19 | Snapcn / LaptopFrame | src/components/component-vertical/snapcn/entries/laptop-frame.tsx | src/components/component-horizontal/snapcn/entries/laptop-frame.tsx | 表达桌面端 AI 工具或网页产品 | 展示网站、后台、桌面录屏容器时使用 |
| 20 | Snapcn / ScreenRecording | src/components/component-vertical/snapcn/entries/screen-recording.tsx | src/components/component-horizontal/snapcn/entries/screen-recording.tsx | 表达真实界面操作中的一个关键步骤 | 教程、产品演示、点击路径讲解时使用 |
| 21 | Snapcn / CursorTrack | src/components/component-vertical/snapcn/entries/cursor-track.tsx | src/components/component-horizontal/snapcn/entries/cursor-track.tsx | 表达观众应该跟随鼠标看某个操作 | 按钮点击、路径指引、交互教学时使用 |
| 22 | Snapcn / MoodboardReveal | src/components/component-vertical/snapcn/entries/moodboard-reveal.tsx | src/components/component-horizontal/snapcn/entries/moodboard-reveal.tsx | 表达多个案例共同构成一个主题印象 | 案例开场、图片集锦、视觉灵感墙时使用 |
| 23 | RVE / Quote Card | src/components/component-vertical/rve/entries/quote-card.tsx | src/components/component-horizontal/rve/entries/quote-card.tsx | 表达引用来源、权威观点或原文证据 | 展示论文、官方文档、人物原话时使用 |
| 24 | RVE / Bar Chart | src/components/component-vertical/rve/entries/chart-animation.tsx | src/components/component-horizontal/rve/entries/chart-animation.tsx | 表达多个对象在同一指标上的差异 | 比较模型成本、性能、速度、价格时使用 |
| 25 | RVE / Line Chart | src/components/component-vertical/rve/entries/line-chart.tsx | src/components/component-horizontal/rve/entries/line-chart.tsx | 表达某个指标随时间变化的趋势 | 讲模型发展、用户增长、价格变化时使用 |
| 26 | RVE / Pie Chart | src/components/component-vertical/rve/entries/pie-chart.tsx | src/components/component-horizontal/rve/entries/pie-chart.tsx | 表达一个整体由几部分构成 | 讲预算占比、用户来源、能力构成时使用 |
| 27 | RVE / Donut Chart | src/components/component-vertical/rve/entries/donut-chart.tsx | src/components/component-horizontal/rve/entries/donut-chart.tsx | 表达完成率、覆盖率或结构占比 | 讲任务进度、数据构成、比例结果时使用 |
| 28 | RVE / Stat Counter | src/components/component-vertical/rve/entries/stat-counter.tsx | src/components/component-horizontal/rve/entries/stat-counter.tsx | 表达一个大数字值得被单独记住 | 抛出参数量、用户数、下载量等关键数字时使用 |
| 29 | RVE / Progress Bars | src/components/component-vertical/rve/entries/progress-bars.tsx | src/components/component-horizontal/rve/entries/progress-bars.tsx | 表达多个能力维度的完成程度 | 讲模型能力、产品评分、项目进度时使用 |
| 30 | RVE / Progress Steps | src/components/component-vertical/rve/entries/progress-steps.tsx | src/components/component-horizontal/rve/entries/progress-steps.tsx | 表达流程必须按顺序一步步推进 | 讲 Agent 流程、内容生产步骤、研发阶段时使用 |
| 31 | RVE / Comparison Chart | src/components/component-vertical/rve/entries/comparison-chart.tsx | src/components/component-horizontal/rve/entries/comparison-chart.tsx | 表达优化前后或方案 A/B 的差距 | 讲改版效果、模型对比、成本变化时使用 |
| 32 | RVE / Split Screen | src/components/component-vertical/rve/entries/split-screen.tsx | src/components/component-horizontal/rve/entries/split-screen.tsx | 表达两种方法或结果并列比较 | 讲 A/B 方案、新旧模型、两类观点时使用 |
| 33 | RVE / Image Comparison Slider | src/components/component-vertical/rve/entries/image-comparison-slider.tsx | src/components/component-horizontal/rve/entries/image-comparison-slider.tsx | 表达图像处理前后的视觉差异 | AI 修图、生成图、界面改版前后对比时使用 |
| 34 | Remocn / Animated Line Chart | src/components/component-vertical/remocn/entries/remocn-animated-line-chart.tsx | src/components/component-horizontal/remocn/entries/remocn-animated-line-chart.tsx | 表达一个指标沿时间线持续变化 | 讲增长曲线、模型迭代、长期趋势时使用 |
| 35 | Remocn / Code Morph | src/components/component-vertical/remocn/entries/remocn-code-morph.tsx | src/components/component-horizontal/remocn/entries/remocn-code-morph.tsx | 表达代码或提示词从旧版演进到新版 | 讲 RAG 加上下文、API 改写、重构时使用 |
| 36 | Remocn / ChatGPT | src/components/component-vertical/remocn/entries/remocn-chat-gpt.tsx | src/components/component-horizontal/remocn/entries/remocn-chat-gpt.tsx | 表达向 ChatGPT 提问这一动作 | 提示词教学、AI 产品介绍、提问示范时使用 |
| 37 | Remocn / Agent Run | src/components/component-vertical/remocn/entries/remocn-agent-run.tsx | src/components/component-horizontal/remocn/entries/remocn-agent-run.tsx | 表达 Agent 先计划再执行再回答 | 解释自动化任务、工具调用、带引用回答时使用 |
| 38 | Remocn / Search Reveal | src/components/component-vertical/remocn/entries/remocn-search-reveal.tsx | src/components/component-horizontal/remocn/entries/remocn-search-reveal.tsx | 表达从搜索问题揭晓产品或答案 | 问题式开场、产品名揭晓、选题引入时使用 |
| 39 | RemotionUI / Data Flow Pipes | src/components/component-vertical/remotion-ui/entries/remotion-ui-data-flow-pipes.tsx | src/components/component-horizontal/remotion-ui/entries/remotion-ui-data-flow-pipes.tsx | 表达数据在多个节点间流动处理 | 讲 RAG、自动化管线、AI 工作流时使用 |
| 40 | RemotionUI / Code Reveal | src/components/component-vertical/remotion-ui/entries/remotion-ui-code-reveal.tsx | src/components/component-horizontal/remotion-ui/entries/remotion-ui-code-reveal.tsx | 表达一段关键代码正在被讲解 | 讲 API 调用、提示词结构、代码样例时使用 |
| 41 | RemotionUI / Animated Bar Chart | src/components/component-vertical/remotion-ui/entries/remotion-ui-animated-bar-chart.tsx | src/components/component-horizontal/remotion-ui/entries/remotion-ui-animated-bar-chart.tsx | 表达多项指标的横向排名和差距 | 比较成本、延迟、任务指标时使用 |
| 42 | Bits / Chat Conversation | src/components/component-vertical/bits/entries/bits-chat-conversation.tsx | src/components/component-horizontal/bits/entries/bits-chat-conversation.tsx | 表达人机或多角色对话来回推进 | AI 问答、Agent 对话、好坏提示词对比时使用 |
| 43 | Bits / Stat Rings | src/components/component-vertical/bits/entries/bits-stat-rings.tsx | src/components/component-horizontal/bits/entries/bits-stat-rings.tsx | 表达几个比例指标同时达成多少 | 展示覆盖率、完成度、准确率等比例时使用 |
| 44 | Bits / Cursor Flyover | src/components/component-vertical/bits/entries/bits-cursor-flyover.tsx | src/components/component-horizontal/bits/entries/bits-cursor-flyover.tsx | 表达镜头带观众巡看界面重点 | 讲产品界面、论文截图、浏览器工具时使用 |
| 45 | Bits / Ken Burns Effect | src/components/component-vertical/bits/entries/bits-ken-burns.tsx | src/components/component-horizontal/bits/entries/bits-ken-burns.tsx | 表达静态图片也有叙事推进感 | 给照片、论文截图、发布图增加镜头运动时使用 |
| 46 | Talkcraft / 聚焦压暗切换 | src/components/component-vertical/video-talkcraft/entries/focus-dim-spotlight.tsx | src/components/component-horizontal/video-talkcraft/entries/focus-dim-spotlight.tsx | 表达“我正在讲这一处”的逐项指认 | 表格、清单、代码逐行解释时使用 |
| 47 | Talkcraft / 手绘圈重点 | src/components/component-vertical/video-talkcraft/entries/hand-drawn-ellipse.tsx | src/components/component-horizontal/video-talkcraft/entries/hand-drawn-ellipse.tsx | 表达某个短语被手动圈为重点 | 口播说“记住这个词”时使用 |
| 48 | Talkcraft / 荧光笔高亮扫过 | src/components/component-vertical/video-talkcraft/entries/highlighter-sweep.tsx | src/components/component-horizontal/video-talkcraft/entries/highlighter-sweep.tsx | 表达报告或原文里这一句最关键 | 引用论文、新闻、文档证据时使用 |
| 49 | Talkcraft / 手绘圈注箭头 | src/components/component-vertical/video-talkcraft/entries/scribble-annotation.tsx | src/components/component-horizontal/video-talkcraft/entries/scribble-annotation.tsx | 表达截图上的具体位置需要被点名 | 测评、拆解、扒图指认时使用 |
| 50 | Talkcraft / 标注引出线 | src/components/component-vertical/video-talkcraft/entries/callout-line-label.tsx | src/components/component-horizontal/video-talkcraft/entries/callout-line-label.tsx | 表达画面中某个部位有解释标签 | 产品图、地图、截图局部说明时使用 |
| 51 | Talkcraft / 双箭头聚焦 | src/components/component-vertical/video-talkcraft/entries/converging-arrows.tsx | src/components/component-horizontal/video-talkcraft/entries/converging-arrows.tsx | 表达多个视线都指向同一个关键词 | 清单、方法论里强调唯一关键点时使用 |
| 52 | Talkcraft / 对角角框 | src/components/component-vertical/video-talkcraft/entries/corner-bracket-frame.tsx | src/components/component-horizontal/video-talkcraft/entries/corner-bracket-frame.tsx | 表达一句话被框定为本段主题 | 章节小标题、开场立论点时使用 |
| 53 | Talkcraft / 急推特写 | src/components/component-vertical/video-talkcraft/entries/crash-zoom-punch.tsx | src/components/component-horizontal/video-talkcraft/entries/crash-zoom-punch.tsx | 表达“看这里”这种强制视线聚焦 | 截图某一行、某个数字突然成为证据时使用 |
| 54 | Talkcraft / 墨迹下划线 | src/components/component-vertical/video-talkcraft/entries/ink-underline.tsx | src/components/component-horizontal/video-talkcraft/entries/ink-underline.tsx | 表达关键词被像笔记一样划线保存 | 定义、对比、观点句中的关键词时使用 |
| 55 | Talkcraft / 局部放大镜 | src/components/component-vertical/video-talkcraft/entries/magnifier-detail.tsx | src/components/component-horizontal/video-talkcraft/entries/magnifier-detail.tsx | 表达密集截图里的小细节值得放大看 | 按钮、数字、条款、参数讲解时使用 |
| 56 | Talkcraft / 金句停留 | src/components/component-vertical/video-talkcraft/entries/quote-hold-arrow.tsx | src/components/component-horizontal/video-talkcraft/entries/quote-hold-arrow.tsx | 表达铺垫之后真正要记住的那一句 | 结论句、转折句、行动号召前使用 |
| 57 | Talkcraft / 扫描线逐处点名 | src/components/component-vertical/video-talkcraft/entries/scanline-annotate.tsx | src/components/component-horizontal/video-talkcraft/entries/scanline-annotate.tsx | 表达一张图被系统逐处读懂和标注 | AI 读文档、落地页分析、财报点评时使用 |
| 58 | Talkcraft / 划线纠错替换 | src/components/component-vertical/video-talkcraft/entries/strike-and-replace.tsx | src/components/component-horizontal/video-talkcraft/entries/strike-and-replace.tsx | 表达旧认知被划掉并换成新结论 | 辟谣、纠错、版本替换、参数修正时使用 |
| 59 | Talkcraft / 准星咬合 | src/components/component-vertical/video-talkcraft/entries/reticle-lock-on.tsx | src/components/component-horizontal/video-talkcraft/entries/reticle-lock-on.tsx | 表达关键目标被准星锁定 | 点名按钮、数字、关键参数时使用 |
| 60 | Talkcraft / 人名条展示牌 | src/components/component-vertical/video-talkcraft/entries/lower-third-nameplate.tsx | src/components/component-horizontal/video-talkcraft/entries/lower-third-nameplate.tsx | 表达人物身份或引用来源需要交代 | 嘉宾、作者、被引用对象首次出现时使用 |
| 61 | Talkcraft / 并列句排版（人物在场） | src/components/component-vertical/video-talkcraft/entries/parallel-items-with-host.tsx | src/components/component-horizontal/video-talkcraft/entries/parallel-items-with-host.tsx | 表达真人旁边列出三项并列信息 | 出镜口播讲三件事、三步骤时使用 |
| 62 | Talkcraft / 人后大字视差 | src/components/component-vertical/video-talkcraft/entries/behind-text-title.tsx | src/components/component-horizontal/video-talkcraft/entries/behind-text-title.tsx | 表达人物与大标题共同建立主题气场 | 真人开场题眼、章节标题、结尾点题时使用 |
| 63 | Talkcraft / 动态人名条 | src/components/component-vertical/video-talkcraft/entries/chevron-lower-third.tsx | src/components/component-horizontal/video-talkcraft/entries/chevron-lower-third.tsx | 表达更有节目感的人物身份介绍 | 访谈、播客、科技节目嘉宾出场时使用 |
| 64 | Talkcraft / 弹幕气泡 | src/components/component-vertical/video-talkcraft/entries/danmu-bubble-praise.tsx | src/components/component-horizontal/video-talkcraft/entries/danmu-bubble-praise.tsx | 表达评论区或用户反馈形成共识 | 开场证明热度、结尾引导互动时使用 |
| 65 | Talkcraft / 抖音主页关注卡 | src/components/component-vertical/video-talkcraft/entries/douyin-follow-card.tsx | src/components/component-horizontal/video-talkcraft/entries/douyin-follow-card.tsx | 表达某个抖音账号值得被认识或关注 | 介绍作者、嘉宾、来源账号时使用 |
| 66 | Talkcraft / 人物竖卡玻璃台 | src/components/component-vertical/video-talkcraft/entries/host-card-glass-board.tsx | src/components/component-horizontal/video-talkcraft/entries/host-card-glass-board.tsx | 表达人持续讲解，旁边展示系统步骤 | 工作流、工具链、多步教程时使用 |
| 67 | Talkcraft / 人物缩位让台 | src/components/component-vertical/video-talkcraft/entries/host-shrink-to-chip.tsx | src/components/component-horizontal/video-talkcraft/entries/host-shrink-to-chip.tsx | 表达讲者让位给图表或截图继续讲 | 从口播切到数据、截图、流程图时使用 |
| 68 | Talkcraft / 多平台关注 CTA | src/components/component-vertical/video-talkcraft/entries/subscribe-cta.tsx | src/components/component-horizontal/video-talkcraft/entries/subscribe-cta.tsx | 表达看完后可以关注或订阅 | 视频结尾、价值兑现后提醒关注时使用 |
| 69 | Talkcraft / 关注卡弹出 | src/components/component-vertical/video-talkcraft/entries/x-follow-card.tsx | src/components/component-horizontal/video-talkcraft/entries/x-follow-card.tsx | 表达 X/Twitter 账号作为观点来源 | 介绍作者、嘉宾、引用账号时使用 |
| 70 | Talkcraft / 柱状增长 | src/components/component-vertical/video-talkcraft/entries/bar-chart-growth.tsx | src/components/component-horizontal/video-talkcraft/entries/bar-chart-growth.tsx | 表达连续区间内的增长或下滑 | 讲半年趋势、月度变化、销量走势时使用 |
| 71 | Talkcraft / 图表生长 | src/components/component-vertical/video-talkcraft/entries/chart-grow.tsx | src/components/component-horizontal/video-talkcraft/entries/chart-grow.tsx | 表达多个数据项依次形成对比 | 财经、科普、评测里的数据对比段落使用 |
| 72 | Talkcraft / 折线分段推演 | src/components/component-vertical/video-talkcraft/entries/line-chart-story-draw.tsx | src/components/component-horizontal/video-talkcraft/entries/line-chart-story-draw.tsx | 表达同一起点下的两种未来走势 | 政策复盘、假设推演、投资算账时使用 |
| 73 | Talkcraft / 数字带趋势 | src/components/component-vertical/video-talkcraft/entries/metric-with-sparkline.tsx | src/components/component-horizontal/video-talkcraft/entries/metric-with-sparkline.tsx | 表达一个关键数字背后还有趋势 | 效率提升、退货率下降、指标变化时使用 |
| 74 | Talkcraft / 数字滚动计数 | src/components/component-vertical/video-talkcraft/entries/number-counter.tsx | src/components/component-horizontal/video-talkcraft/entries/number-counter.tsx | 表达关键数字正在增长到结论值 | 抛出营收、销量、涨幅等数字时使用 |
| 75 | Talkcraft / 数字弹出 | src/components/component-vertical/video-talkcraft/entries/number-slab-pop.tsx | src/components/component-horizontal/video-talkcraft/entries/number-slab-pop.tsx | 表达一个单点数字就是本段结论 | 封面数字、步骤数量、核心百分比时使用 |
| 76 | Talkcraft / 点阵比例图 | src/components/component-vertical/video-talkcraft/entries/unit-grid-proportion.tsx | src/components/component-horizontal/video-talkcraft/entries/unit-grid-proportion.tsx | 表达“多少人里有多少个”的比例感 | 成功率、留存率、调研比例讲解时使用 |
| 77 | Talkcraft / 五选一反黑 | src/components/component-vertical/video-talkcraft/entries/chip-grid-single-select.tsx | src/components/component-horizontal/video-talkcraft/entries/chip-grid-single-select.tsx | 表达多个选项中最终选中一个 | 工具选择、方案筛选、投票结果揭晓时使用 |
| 78 | Talkcraft / 名词解释悬浮卡 | src/components/component-vertical/video-talkcraft/entries/info-term-card.tsx | src/components/component-horizontal/video-talkcraft/entries/info-term-card.tsx | 表达专业名词需要快速解释 | AI 术语、财经概念、黑话第一次出现时使用 |
| 79 | Talkcraft / 地图路线图钉 | src/components/component-vertical/video-talkcraft/entries/map-route-pin.tsx | src/components/component-horizontal/video-talkcraft/entries/map-route-pin.tsx | 表达地点、路线或事件移动路径 | 事件复盘、行程、地域扩散讲解时使用 |
| 80 | Talkcraft / 编号步骤堆入 | src/components/component-vertical/video-talkcraft/entries/numbered-step-stack.tsx | src/components/component-horizontal/video-talkcraft/entries/numbered-step-stack.tsx | 表达几个并列要点可以截图保存 | 方法清单、操作要点、干货总结时使用 |
| 81 | Talkcraft / 竖向步骤线 | src/components/component-vertical/video-talkcraft/entries/step-timeline-vertical.tsx | src/components/component-horizontal/video-talkcraft/entries/step-timeline-vertical.tsx | 表达步骤之间有明确先后依赖 | 流程复盘、三步走、项目进度时使用 |
| 82 | Talkcraft / 界面道具剧场 | src/components/component-vertical/video-talkcraft/entries/ui-prop-theater.tsx | src/components/component-horizontal/video-talkcraft/entries/ui-prop-theater.tsx | 表达产品参数、状态和进度如何变化 | AI 工具测评、参数讲解、教程流程时使用 |
| 83 | Talkcraft / 多源汇聚 | src/components/component-vertical/video-talkcraft/entries/source-converge.tsx | src/components/component-horizontal/video-talkcraft/entries/source-converge.tsx | 表达多个来源汇聚成一个结论 | RAG、多渠道数据、证据归纳时使用 |
| 84 | Talkcraft / 同源模糊底床 | src/components/component-vertical/video-talkcraft/entries/bed-echo-blur.tsx | src/components/component-horizontal/video-talkcraft/entries/bed-echo-blur.tsx | 表达竖屏素材需要自然放进横屏画面 | 竖拍实拍、竖屏录屏、网友投稿时使用 |
| 85 | Talkcraft / 聊天记录自演 | src/components/component-vertical/video-talkcraft/entries/chat-message-flow.tsx | src/components/component-horizontal/video-talkcraft/entries/chat-message-flow.tsx | 表达聊天记录作为证据逐条出现 | 客户反馈、AI 对话、团队讨论还原时使用 |
| 86 | Talkcraft / 光标演员演示 | src/components/component-vertical/video-talkcraft/entries/cursor-actor-demo.tsx | src/components/component-horizontal/video-talkcraft/entries/cursor-actor-demo.tsx | 表达软件操作由光标带着观众完成 | 工具教程、AI 产品演示、设置引导时使用 |
| 87 | Talkcraft / 证据长页慢滚 | src/components/component-vertical/video-talkcraft/entries/evidence-scroll-tour.tsx | src/components/component-horizontal/video-talkcraft/entries/evidence-scroll-tour.tsx | 表达长文档证据需要边滚边讲 | 协议、README、报告、搜索结果讲解时使用 |
| 88 | Talkcraft / 素材弹入堆叠 | src/components/component-vertical/video-talkcraft/entries/media-pop-in.tsx | src/components/component-horizontal/video-talkcraft/entries/media-pop-in.tsx | 表达多张证据被一张张甩出来 | 爆料、辟谣、盘点、截图列举时使用 |
| 89 | Talkcraft / 新闻卡片划重点 | src/components/component-vertical/video-talkcraft/entries/news-card-desk.tsx | src/components/component-horizontal/video-talkcraft/entries/news-card-desk.tsx | 表达一条新闻是本段讨论依据 | 时事、财经、行业新闻解读时使用 |
| 90 | Talkcraft / 对比双分屏（滑动揭示） | src/components/component-vertical/video-talkcraft/entries/split-compare-slider.tsx | src/components/component-horizontal/video-talkcraft/entries/split-compare-slider.tsx | 表达同一对象前后或 A/B 差异 | 改版、修图、生成图、参数对比时使用 |
| 91 | Talkcraft / 多图排版 + 焦点接力 | src/components/component-vertical/video-talkcraft/entries/still-layout-relay.tsx | src/components/component-horizontal/video-talkcraft/entries/still-layout-relay.tsx | 表达主图和辅助图共同证明观点 | 一主两辅证据、三张截图对照时使用 |
| 92 | Talkcraft / 界面流程剧场 | src/components/component-vertical/video-talkcraft/entries/ui-flow-theater.tsx | src/components/component-horizontal/video-talkcraft/entries/ui-flow-theater.tsx | 表达一个产品功能从头到尾如何操作 | AI 工具上手、SaaS 教程、流程演示时使用 |
| 93 | Talkcraft / ChatGPT 对话框 | src/components/component-vertical/video-talkcraft/entries/chat-gpt.tsx | src/components/component-horizontal/video-talkcraft/entries/chat-gpt.tsx | 表达一次 ChatGPT 提问和回答 | 提示词技巧、模型能力演示、AI 科普时使用 |
| 94 | Talkcraft / 编码智能体终端 | src/components/component-vertical/video-talkcraft/entries/claude-code.tsx | src/components/component-horizontal/video-talkcraft/entries/claude-code.tsx | 表达编码智能体正在修改或运行代码 | AI 编程工具测评、开发者教程时使用 |
| 95 | Talkcraft / 文档驻留发牌 | src/components/component-vertical/video-talkcraft/entries/doc-park-left-pill-deal.tsx | src/components/component-horizontal/video-talkcraft/entries/doc-park-left-pill-deal.tsx | 表达从文档中提炼出几条结论 | 论文、报告、长文总结类 AI 话题时使用 |
| 96 | Talkcraft / 传送带列举 + 减速停靠 | src/components/component-vertical/video-talkcraft/entries/filmstrip-conveyor.tsx | src/components/component-horizontal/video-talkcraft/entries/filmstrip-conveyor.tsx | 表达很多案例中其中一个最重要 | 工具盘点、作品回顾、案例列表时使用 |
| 97 | Talkcraft / 照片墙推轨 | src/components/component-vertical/video-talkcraft/entries/gallery-wall-dolly.tsx | src/components/component-horizontal/video-talkcraft/entries/gallery-wall-dolly.tsx | 表达多个平级案例被逐个巡看 | 案例集、作品集、三个方案讲解时使用 |
| 98 | Talkcraft / 玻璃代码走读 | src/components/component-vertical/video-talkcraft/entries/glass-code-walk.tsx | src/components/component-horizontal/video-talkcraft/entries/glass-code-walk.tsx | 表达带观众读一小段关键代码 | 技术教程、开源项目、配置讲解时使用 |
| 99 | Talkcraft / 图块拼入 | src/components/component-vertical/video-talkcraft/entries/gooey-morph.tsx | src/components/component-horizontal/video-talkcraft/entries/gooey-morph.tsx | 表达几张证据属于同一组 | 多平台对比、组图、九宫格素材时使用 |
| 100 | Talkcraft / 网格收成主角 | src/components/component-vertical/video-talkcraft/entries/grid-to-hero.tsx | src/components/component-horizontal/video-talkcraft/entries/grid-to-hero.tsx | 表达从多个候选里选出主角 | 封面候选、版本选择、重点案例揭晓时使用 |
| 101 | Talkcraft / 信息卡逐字段自建 | src/components/component-vertical/video-talkcraft/entries/info-card-assemble.tsx | src/components/component-horizontal/video-talkcraft/entries/info-card-assemble.tsx | 表达人物、工具或课程信息被结构化 | 介绍书、工具、人、课程档案时使用 |
| 102 | Talkcraft / Logo 登场 | src/components/component-vertical/video-talkcraft/entries/logo-enter.tsx | src/components/component-horizontal/video-talkcraft/entries/logo-enter.tsx | 表达品牌、系列或频道身份登场 | 片头、片尾、产品名正式露出时使用 |
| 103 | Talkcraft / 模糊甩入急停 | src/components/component-vertical/video-talkcraft/entries/motion-blur-slam-in.tsx | src/components/component-horizontal/video-talkcraft/entries/motion-blur-slam-in.tsx | 表达证据或观点被强势甩到台前 | 爆点拆解、硬观点、数据卡压上时使用 |
| 104 | Talkcraft / 铅笔手绘揭示 | src/components/component-vertical/video-talkcraft/entries/pencil-sketch-draw.tsx | src/components/component-horizontal/video-talkcraft/entries/pencil-sketch-draw.tsx | 表达概念像手绘草图一样被画出来 | 流程解释、轻松科普、概念示意时使用 |
| 105 | Talkcraft / 焦点接力 | src/components/component-vertical/video-talkcraft/entries/rack-focus-pair.tsx | src/components/component-horizontal/video-talkcraft/entries/rack-focus-pair.tsx | 表达两个对象之间来回比较 | A/B 产品、两种观点、新旧方案对照时使用 |
| 106 | Talkcraft / 60/40 主从分屏 | src/components/component-vertical/video-talkcraft/entries/split-60-40-story.tsx | src/components/component-horizontal/video-talkcraft/entries/split-60-40-story.tsx | 表达主素材旁边同步列出讲解要点 | 录屏加要点、产品演示、教程旁白时使用 |
| 107 | Talkcraft / 卡堆扇形展开 | src/components/component-vertical/video-talkcraft/entries/stack-fan-out.tsx | src/components/component-horizontal/video-talkcraft/entries/stack-fan-out.tsx | 表达一叠素材展开成候选清单 | 照片、截图、评论卡汇总展示时使用 |
| 108 | Talkcraft / 终端逐行推进 | src/components/component-vertical/video-talkcraft/entries/terminal-typing-log.tsx | src/components/component-horizontal/video-talkcraft/entries/terminal-typing-log.tsx | 表达命令行执行结果可作为证据 | 构建、部署、测试、AI 编程演示时使用 |
| 109 | Talkcraft / 时间线照片带 | src/components/component-vertical/video-talkcraft/entries/timeline-photo-strip.tsx | src/components/component-horizontal/video-talkcraft/entries/timeline-photo-strip.tsx | 表达多个时间点按顺序串成故事 | 版本演进、年度回顾、事件时间线时使用 |
| 110 | Talkcraft / 动词接力胶片 | src/components/component-vertical/video-talkcraft/entries/word-relay-filmstrip.tsx | src/components/component-horizontal/video-talkcraft/entries/word-relay-filmstrip.tsx | 表达一个主体拥有连续多种能力 | AI 能力清单、产品场景巡礼时使用 |
| 111 | Talkcraft / 缓拉全貌 | src/components/component-vertical/video-talkcraft/entries/slow-pull-reveal.tsx | src/components/component-horizontal/video-talkcraft/entries/slow-pull-reveal.tsx | 表达先看局部再退回全貌 | 长表格、数据看板、全景总结时使用 |
| 112 | Talkcraft / 缓推特写 | src/components/component-vertical/video-talkcraft/entries/slow-push-in.tsx | src/components/component-horizontal/video-talkcraft/entries/slow-push-in.tsx | 表达观众视线慢慢收拢到素材重点 | 网页截图、文档、图片的冷静讲解时使用 |
| 113 | Talkcraft / 光标锁定跟拍 | src/components/component-vertical/video-talkcraft/entries/cursor-locked-zoom.tsx | src/components/component-horizontal/video-talkcraft/entries/cursor-locked-zoom.tsx | 表达镜头紧跟一个移动或长文本目标 | 长命令、代码行、表单字段讲解时使用 |
| 114 | Talkcraft / 环绕微漂 | src/components/component-vertical/video-talkcraft/entries/orbit-drift.tsx | src/components/component-horizontal/video-talkcraft/entries/orbit-drift.tsx | 表达静态页面在长讲述中保持呼吸感 | 长时间展示网页、报告、截图背景时使用 |
| 115 | Talkcraft / 画中画放大 | src/components/component-vertical/video-talkcraft/entries/pip-zoom-box.tsx | src/components/component-horizontal/video-talkcraft/entries/pip-zoom-box.tsx | 表达保留全景同时单独放大局部 | 讲产品细节、表情、截图一角时使用 |
| 116 | Talkcraft / 长页兴趣点巡游 | src/components/component-vertical/video-talkcraft/entries/stage-keyframe-tour.tsx | src/components/component-horizontal/video-talkcraft/entries/stage-keyframe-tour.tsx | 表达长页面按兴趣点逐站游览 | 落地页、长截图、长报表巡讲时使用 |
| 117 | Talkcraft / 左右摇移 | src/components/component-vertical/video-talkcraft/entries/sway-parallax.tsx | src/components/component-horizontal/video-talkcraft/entries/sway-parallax.tsx | 表达横向长素材需要顺着讲过去 | 时间线、宽流程图、超宽截图时使用 |
| 118 | Talkcraft / 3D 立面展示 | src/components/component-vertical/video-talkcraft/entries/tilt-3d-page.tsx | src/components/component-horizontal/video-talkcraft/entries/tilt-3d-page.tsx | 表达网页或 UI 像产品模型一样展示 | 作品展示、产品介绍、案例墙时使用 |
| 119 | Talkcraft / 黑震切转场 | src/components/component-vertical/video-talkcraft/entries/black-slam-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/black-slam-transition.tsx | 表达全片最大反转或揭示即将发生 | 悬念停顿后切出答案时使用 |
| 120 | Talkcraft / 章节标题卡 | src/components/component-vertical/video-talkcraft/entries/chapter-title-card.tsx | src/components/component-horizontal/video-talkcraft/entries/chapter-title-card.tsx | 表达长视频进入新的正式章节 | 5 分钟以上内容的段落切换时使用 |
| 121 | Talkcraft / 纯色硬切节拍卡 | src/components/component-vertical/video-talkcraft/entries/color-slam-beat-card.tsx | src/components/component-horizontal/video-talkcraft/entries/color-slam-beat-card.tsx | 表达一句观点被当作节拍重锤 | 短口播下判断、列条目、砸观点时使用 |
| 122 | Talkcraft / 过曝翻页转场 | src/components/component-vertical/video-talkcraft/entries/overexpose-flip-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/overexpose-flip-transition.tsx | 表达郑重翻页进入下一段证据 | 章节翻页、关键截图之后转场时使用 |
| 123 | Talkcraft / 粒子溶接转场 | src/components/component-vertical/video-talkcraft/entries/particle-weld-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/particle-weld-transition.tsx | 表达同一概念从一种形态变成另一种 | 数据变图表、概念变案例时使用 |
| 124 | Talkcraft / 后拉冷却转场 | src/components/component-vertical/video-talkcraft/entries/pullback-cool-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/pullback-cool-transition.tsx | 表达激烈段落结束后退一步看 | 结论前呼吸、情绪冷却、沉淀转场时使用 |
| 125 | Talkcraft / 推穿转场 | src/components/component-vertical/video-talkcraft/entries/push-through-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/push-through-transition.tsx | 表达从概念推进到证据或细节 | 全景到局部、观点到案例之间使用 |
| 126 | Talkcraft / 色块扫屏转场 | src/components/component-vertical/video-talkcraft/entries/shape-wipe-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/shape-wipe-transition.tsx | 表达话题切换，节奏进入下一块 | 章节切分、快节奏换主题时使用 |
| 127 | Talkcraft / 横甩转场 | src/components/component-vertical/video-talkcraft/entries/whip-pan-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/whip-pan-transition.tsx | 表达平级案例之间快速横向切换 | A 到 B、人物切换、市场切换时使用 |
| 128 | Talkcraft / 光标擦除转场 | src/components/component-vertical/video-talkcraft/entries/caret-wipe-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/caret-wipe-transition.tsx | 表达文本、代码或版本被重写 | 编辑器、文档、AI 生成内容转场时使用 |
| 129 | Talkcraft / 章节进度 | src/components/component-vertical/video-talkcraft/entries/chapter-progress-list.tsx | src/components/component-horizontal/video-talkcraft/entries/chapter-progress-list.tsx | 表达观众需要知道现在讲到哪 | 长口播目录、章节进度、系列内容时使用 |
| 130 | Talkcraft / 线条接力转场 | src/components/component-vertical/video-talkcraft/entries/line-carry-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/line-carry-transition.tsx | 表达上一镜的线索牵出下一镜 | 章节接缝、图形亲缘强的两镜之间使用 |
| 131 | Talkcraft / 长镜头世界画布 | src/components/component-vertical/video-talkcraft/entries/long-take-world.tsx | src/components/component-horizontal/video-talkcraft/entries/long-take-world.tsx | 表达一个大系统可被一镜到底走完 | 流程、地图、生态图、世界观段落时使用 |
| 132 | Talkcraft / 冲击开场 | src/components/component-vertical/video-talkcraft/entries/impact-open-title.tsx | src/components/component-horizontal/video-talkcraft/entries/impact-open-title.tsx | 表达开场钩子要立刻抓住注意力 | 视频前 3 秒、强观点章节开幕时使用 |
| 133 | Talkcraft / 关键词弹出强调 | src/components/component-vertical/video-talkcraft/entries/keyword-pop-highlight.tsx | src/components/component-horizontal/video-talkcraft/entries/keyword-pop-highlight.tsx | 表达这一词就是当前信息峰值 | 数字、反转词、核心结论出现时使用 |
| 134 | Talkcraft / 重点放大 | src/components/component-vertical/video-talkcraft/entries/slab-punch-title.tsx | src/components/component-horizontal/video-talkcraft/entries/slab-punch-title.tsx | 表达前半句铺垫，后半句才是重点 | 观点号、干货号的小标题或重音句使用 |
| 135 | Talkcraft / 标题降格成标签 | src/components/component-vertical/video-talkcraft/entries/title-demote-to-label.tsx | src/components/component-horizontal/video-talkcraft/entries/title-demote-to-label.tsx | 表达标题让位后变成小节路标 | 教程、方法论、问答式小节交接时使用 |
| 136 | Talkcraft / 字体对比重音 | src/components/component-vertical/video-talkcraft/entries/type-contrast-emphasis.tsx | src/components/component-horizontal/video-talkcraft/entries/type-contrast-emphasis.tsx | 表达重音来自字体气质的反差 | 克制观点句、不是 A 而是 B 时使用 |
| 137 | Talkcraft / 词槽轮换 | src/components/component-vertical/video-talkcraft/entries/word-slot-cycle.tsx | src/components/component-horizontal/video-talkcraft/entries/word-slot-cycle.tsx | 表达一个位置快速轮换多种用途 | AI 能帮你做 A/B/C/D 的功能列举时使用 |
| 138 | Talkcraft / 双色块对句 | src/components/component-vertical/video-talkcraft/entries/alt-block-lines.tsx | src/components/component-horizontal/video-talkcraft/entries/alt-block-lines.tsx | 表达两句对照关系清晰并列 | 不是 A 而是 B、以前现在对比时使用 |
| 139 | Talkcraft / 数字重音标题 | src/components/component-vertical/video-talkcraft/entries/count-badge-title.tsx | src/components/component-horizontal/video-talkcraft/entries/count-badge-title.tsx | 表达这段内容有明确数量承诺 | 三个方法、五个坑、两件事开场时使用 |
| 140 | Talkcraft / 打字改口 | src/components/component-vertical/video-talkcraft/entries/error-retype.tsx | src/components/component-horizontal/video-talkcraft/entries/error-retype.tsx | 表达先写错认知再改成正确认知 | 纠正常见误解、反转 hook、提示词改口时使用 |
| 141 | Talkcraft / 首词占满补句 | src/components/component-vertical/video-talkcraft/entries/lead-word-zoom-assemble.tsx | src/components/component-horizontal/video-talkcraft/entries/lead-word-zoom-assemble.tsx | 表达句子主语或首词先成为主角 | 金句、产品名、数字先行标题时使用 |
| 142 | Talkcraft / 逐行滑入 | src/components/component-vertical/video-talkcraft/entries/line-by-line-slide.tsx | src/components/component-horizontal/video-talkcraft/entries/line-by-line-slide.tsx | 表达多行要点作为一组进入画面 | 三四条清单、步骤、分行金句时使用 |
| 143 | Talkcraft / 描边框标题 | src/components/component-vertical/video-talkcraft/entries/outline-box-title.tsx | src/components/component-horizontal/video-talkcraft/entries/outline-box-title.tsx | 表达一个短语被定义成核心结论 | 立论点、术语定义、理性结论框定时使用 |
| 144 | Talkcraft / 逐字升起 | src/components/component-vertical/video-talkcraft/entries/per-character-rise.tsx | src/components/component-horizontal/video-talkcraft/entries/per-character-rise.tsx | 表达一句短主张有力站起来 | 论点句、口号、结论句上屏时使用 |
| 145 | Talkcraft / 引号夹句 | src/components/component-vertical/video-talkcraft/entries/quote-bracket-pull.tsx | src/components/component-horizontal/video-talkcraft/entries/quote-bracket-pull.tsx | 表达某句话被当成引用郑重呈现 | 引用他人原话、观众留言、自我金句时使用 |
| 146 | Talkcraft / 金句大字卡 | src/components/component-vertical/video-talkcraft/entries/quote-card.tsx | src/components/component-horizontal/video-talkcraft/entries/quote-card.tsx | 表达整段观点达到金句峰值 | 结论、暴论、情绪收束动作时使用 |
| 147 | Talkcraft / 柔焦淡入 | src/components/component-vertical/video-talkcraft/entries/soft-blur-in.tsx | src/components/component-horizontal/video-talkcraft/entries/soft-blur-in.tsx | 表达温和旁白或小标题轻轻出现 | 冷静结论、品牌片、素材切换后第一句时使用 |
| 148 | Talkcraft / 速度块标题 | src/components/component-vertical/video-talkcraft/entries/speed-slab-title.tsx | src/components/component-horizontal/video-talkcraft/entries/speed-slab-title.tsx | 表达效率、提速、抢先这类快感 | 短口播开场、效率主题、速度重音时使用 |
| 149 | Talkcraft / 字距收拢 | src/components/component-vertical/video-talkcraft/entries/tracking-in.tsx | src/components/component-horizontal/video-talkcraft/entries/tracking-in.tsx | 表达一句大标题需要发布会气质 | 开场标题、片尾落版、品牌短句时使用 |
| 150 | Talkcraft / 打字机档案戳 | src/components/component-vertical/video-talkcraft/entries/typewriter-reveal.tsx | src/components/component-horizontal/video-talkcraft/entries/typewriter-reveal.tsx | 表达时间地点档案被逐字记录 | 纪录片、调查、悬疑盘点交代背景时使用 |
| 151 | Talkcraft / 数字弧落标题 | src/components/component-vertical/video-talkcraft/entries/countdown-arc-scatter.tsx | src/components/component-horizontal/video-talkcraft/entries/countdown-arc-scatter.tsx | 表达数字本身带悬念和揭晓感 | 5 分钟、3 个原则、倒计时开场时使用 |
| 152 | Talkcraft / 关键词隧道 | src/components/component-vertical/video-talkcraft/entries/flying-words.tsx | src/components/component-horizontal/video-talkcraft/entries/flying-words.tsx | 表达大量概念围绕一个主题涌来 | AI 名词科普开场、能力清单背景时使用 |
| 153 | Talkcraft / 逐字裂升 | src/components/component-vertical/video-talkcraft/entries/split-text-stagger.tsx | src/components/component-horizontal/video-talkcraft/entries/split-text-stagger.tsx | 表达标题从基线中利落长出来 | 章节题、频道名、短金句入场时使用 |

### 仓库说明

工作表 `Z1PGqC`；6 条记录。

| 飞书行号 | 仓库 | 定位 | 本次目录数量 | 本次导入数量 | 许可 | 接入方式 | 固定版本 | GitHub | 演示入口 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | Snapcn | 可复制的参数化视频组件 | 21 | 21 | MIT（独立 LICENSE） | 复制组件与工具；部分离线 Inter / Source Serif 4 字体；本地示例素材 | 4399d249002afae506497cc90ac3f064e189127d | https://github.com/snapcndev/snapcn | https://snapcn.dev/docs/components |
| 3 | RVE | 单文件视频模板 | 11 | 11 | README 声明 MIT；无独立 LICENSE | 复制选定模板，补基础 Props；保留原版并新增竖屏布局分支 | 6209b724798e48ff395f8df1a6fa2d26082372b5 | https://github.com/reactvideoeditor/remotion-templates | https://www.reactvideoeditor.com/remotion-templates |
| 4 | Remocn | 可复制的视频组件与工具 | 5 | 5 | MIT（独立 LICENSE） | 复制组件及实际依赖闭包 | 8ae853e4c08108105684d4b8cac7f22400840d2a | https://github.com/Remocn/remocn | https://remocn.dev |
| 5 | RemotionUI | 通过 registry 分发的视频组件 | 3 | 3 | MIT（独立 LICENSE） | 复制组件及工具；不安装整套网站 | b7e0e6becc3d22b8b03dfef72c064f72ff9fad1f | https://github.com/riaz37/remotion-ui | https://remotionui.com/docs/components |
| 6 | Bits | 动画基础工具及组合示例 | 4 | 4 | package.json / README 声明 MIT；无独立 LICENSE | 复制四个示例及底层动画依赖闭包 | de35fda84b7b6acbe549a0b302a82ef211e8ef1e | https://github.com/av/remotion-bits | https://remotion-bits.dev/docs/bits/ |
| 7 | video-talkcraft | Agent skill + Remotion 卡片 + 独立工作台 | 108 | 108 | PolyForm Noncommercial 1.0.0 | 108 张原始 TSX 字节保持；作者示例素材；按用户声明非商业用途导入 | 4cd673df4b7a6a35784a0881df223721789c5e23 | https://github.com/Vincentwei1021/video-talkcraft | https://vincentwei1021.github.io/video-talkcraft/ |

### video-talkcraft

工作表 `9m13RU`；108 条记录。

| 飞书行号 | 组件名称 | 竖版相对文件路径 | 横版相对文件路径 | 适合表达的内容 | 适用场景 |
| --- | --- | --- | --- | --- | --- |
| 2 | Talkcraft / 聚焦压暗切换 | src/components/component-vertical/video-talkcraft/entries/focus-dim-spotlight.tsx | src/components/component-horizontal/video-talkcraft/entries/focus-dim-spotlight.tsx | 表达“我正在讲这一处”的逐项指认 | 表格、清单、代码逐行解释时使用 |
| 3 | Talkcraft / 手绘圈重点 | src/components/component-vertical/video-talkcraft/entries/hand-drawn-ellipse.tsx | src/components/component-horizontal/video-talkcraft/entries/hand-drawn-ellipse.tsx | 表达某个短语被手动圈为重点 | 口播说“记住这个词”时使用 |
| 4 | Talkcraft / 荧光笔高亮扫过 | src/components/component-vertical/video-talkcraft/entries/highlighter-sweep.tsx | src/components/component-horizontal/video-talkcraft/entries/highlighter-sweep.tsx | 表达报告或原文里这一句最关键 | 引用论文、新闻、文档证据时使用 |
| 5 | Talkcraft / 手绘圈注箭头 | src/components/component-vertical/video-talkcraft/entries/scribble-annotation.tsx | src/components/component-horizontal/video-talkcraft/entries/scribble-annotation.tsx | 表达截图上的具体位置需要被点名 | 测评、拆解、扒图指认时使用 |
| 6 | Talkcraft / 标注引出线 | src/components/component-vertical/video-talkcraft/entries/callout-line-label.tsx | src/components/component-horizontal/video-talkcraft/entries/callout-line-label.tsx | 表达画面中某个部位有解释标签 | 产品图、地图、截图局部说明时使用 |
| 7 | Talkcraft / 双箭头聚焦 | src/components/component-vertical/video-talkcraft/entries/converging-arrows.tsx | src/components/component-horizontal/video-talkcraft/entries/converging-arrows.tsx | 表达多个视线都指向同一个关键词 | 清单、方法论里强调唯一关键点时使用 |
| 8 | Talkcraft / 对角角框 | src/components/component-vertical/video-talkcraft/entries/corner-bracket-frame.tsx | src/components/component-horizontal/video-talkcraft/entries/corner-bracket-frame.tsx | 表达一句话被框定为本段主题 | 章节小标题、开场立论点时使用 |
| 9 | Talkcraft / 急推特写 | src/components/component-vertical/video-talkcraft/entries/crash-zoom-punch.tsx | src/components/component-horizontal/video-talkcraft/entries/crash-zoom-punch.tsx | 表达“看这里”这种强制视线聚焦 | 截图某一行、某个数字突然成为证据时使用 |
| 10 | Talkcraft / 墨迹下划线 | src/components/component-vertical/video-talkcraft/entries/ink-underline.tsx | src/components/component-horizontal/video-talkcraft/entries/ink-underline.tsx | 表达关键词被像笔记一样划线保存 | 定义、对比、观点句中的关键词时使用 |
| 11 | Talkcraft / 局部放大镜 | src/components/component-vertical/video-talkcraft/entries/magnifier-detail.tsx | src/components/component-horizontal/video-talkcraft/entries/magnifier-detail.tsx | 表达密集截图里的小细节值得放大看 | 按钮、数字、条款、参数讲解时使用 |
| 12 | Talkcraft / 金句停留 | src/components/component-vertical/video-talkcraft/entries/quote-hold-arrow.tsx | src/components/component-horizontal/video-talkcraft/entries/quote-hold-arrow.tsx | 表达铺垫之后真正要记住的那一句 | 结论句、转折句、行动号召前使用 |
| 13 | Talkcraft / 扫描线逐处点名 | src/components/component-vertical/video-talkcraft/entries/scanline-annotate.tsx | src/components/component-horizontal/video-talkcraft/entries/scanline-annotate.tsx | 表达一张图被系统逐处读懂和标注 | AI 读文档、落地页分析、财报点评时使用 |
| 14 | Talkcraft / 划线纠错替换 | src/components/component-vertical/video-talkcraft/entries/strike-and-replace.tsx | src/components/component-horizontal/video-talkcraft/entries/strike-and-replace.tsx | 表达旧认知被划掉并换成新结论 | 辟谣、纠错、版本替换、参数修正时使用 |
| 15 | Talkcraft / 准星咬合 | src/components/component-vertical/video-talkcraft/entries/reticle-lock-on.tsx | src/components/component-horizontal/video-talkcraft/entries/reticle-lock-on.tsx | 表达关键目标被准星锁定 | 点名按钮、数字、关键参数时使用 |
| 16 | Talkcraft / 人名条展示牌 | src/components/component-vertical/video-talkcraft/entries/lower-third-nameplate.tsx | src/components/component-horizontal/video-talkcraft/entries/lower-third-nameplate.tsx | 表达人物身份或引用来源需要交代 | 嘉宾、作者、被引用对象首次出现时使用 |
| 17 | Talkcraft / 并列句排版（人物在场） | src/components/component-vertical/video-talkcraft/entries/parallel-items-with-host.tsx | src/components/component-horizontal/video-talkcraft/entries/parallel-items-with-host.tsx | 表达真人旁边列出三项并列信息 | 出镜口播讲三件事、三步骤时使用 |
| 18 | Talkcraft / 人后大字视差 | src/components/component-vertical/video-talkcraft/entries/behind-text-title.tsx | src/components/component-horizontal/video-talkcraft/entries/behind-text-title.tsx | 表达人物与大标题共同建立主题气场 | 真人开场题眼、章节标题、结尾点题时使用 |
| 19 | Talkcraft / 动态人名条 | src/components/component-vertical/video-talkcraft/entries/chevron-lower-third.tsx | src/components/component-horizontal/video-talkcraft/entries/chevron-lower-third.tsx | 表达更有节目感的人物身份介绍 | 访谈、播客、科技节目嘉宾出场时使用 |
| 20 | Talkcraft / 弹幕气泡 | src/components/component-vertical/video-talkcraft/entries/danmu-bubble-praise.tsx | src/components/component-horizontal/video-talkcraft/entries/danmu-bubble-praise.tsx | 表达评论区或用户反馈形成共识 | 开场证明热度、结尾引导互动时使用 |
| 21 | Talkcraft / 抖音主页关注卡 | src/components/component-vertical/video-talkcraft/entries/douyin-follow-card.tsx | src/components/component-horizontal/video-talkcraft/entries/douyin-follow-card.tsx | 表达某个抖音账号值得被认识或关注 | 介绍作者、嘉宾、来源账号时使用 |
| 22 | Talkcraft / 人物竖卡玻璃台 | src/components/component-vertical/video-talkcraft/entries/host-card-glass-board.tsx | src/components/component-horizontal/video-talkcraft/entries/host-card-glass-board.tsx | 表达人持续讲解，旁边展示系统步骤 | 工作流、工具链、多步教程时使用 |
| 23 | Talkcraft / 人物缩位让台 | src/components/component-vertical/video-talkcraft/entries/host-shrink-to-chip.tsx | src/components/component-horizontal/video-talkcraft/entries/host-shrink-to-chip.tsx | 表达讲者让位给图表或截图继续讲 | 从口播切到数据、截图、流程图时使用 |
| 24 | Talkcraft / 多平台关注 CTA | src/components/component-vertical/video-talkcraft/entries/subscribe-cta.tsx | src/components/component-horizontal/video-talkcraft/entries/subscribe-cta.tsx | 表达看完后可以关注或订阅 | 视频结尾、价值兑现后提醒关注时使用 |
| 25 | Talkcraft / 关注卡弹出 | src/components/component-vertical/video-talkcraft/entries/x-follow-card.tsx | src/components/component-horizontal/video-talkcraft/entries/x-follow-card.tsx | 表达 X/Twitter 账号作为观点来源 | 介绍作者、嘉宾、引用账号时使用 |
| 26 | Talkcraft / 柱状增长 | src/components/component-vertical/video-talkcraft/entries/bar-chart-growth.tsx | src/components/component-horizontal/video-talkcraft/entries/bar-chart-growth.tsx | 表达连续区间内的增长或下滑 | 讲半年趋势、月度变化、销量走势时使用 |
| 27 | Talkcraft / 图表生长 | src/components/component-vertical/video-talkcraft/entries/chart-grow.tsx | src/components/component-horizontal/video-talkcraft/entries/chart-grow.tsx | 表达多个数据项依次形成对比 | 财经、科普、评测里的数据对比段落使用 |
| 28 | Talkcraft / 折线分段推演 | src/components/component-vertical/video-talkcraft/entries/line-chart-story-draw.tsx | src/components/component-horizontal/video-talkcraft/entries/line-chart-story-draw.tsx | 表达同一起点下的两种未来走势 | 政策复盘、假设推演、投资算账时使用 |
| 29 | Talkcraft / 数字带趋势 | src/components/component-vertical/video-talkcraft/entries/metric-with-sparkline.tsx | src/components/component-horizontal/video-talkcraft/entries/metric-with-sparkline.tsx | 表达一个关键数字背后还有趋势 | 效率提升、退货率下降、指标变化时使用 |
| 30 | Talkcraft / 数字滚动计数 | src/components/component-vertical/video-talkcraft/entries/number-counter.tsx | src/components/component-horizontal/video-talkcraft/entries/number-counter.tsx | 表达关键数字正在增长到结论值 | 抛出营收、销量、涨幅等数字时使用 |
| 31 | Talkcraft / 数字弹出 | src/components/component-vertical/video-talkcraft/entries/number-slab-pop.tsx | src/components/component-horizontal/video-talkcraft/entries/number-slab-pop.tsx | 表达一个单点数字就是本段结论 | 封面数字、步骤数量、核心百分比时使用 |
| 32 | Talkcraft / 点阵比例图 | src/components/component-vertical/video-talkcraft/entries/unit-grid-proportion.tsx | src/components/component-horizontal/video-talkcraft/entries/unit-grid-proportion.tsx | 表达“多少人里有多少个”的比例感 | 成功率、留存率、调研比例讲解时使用 |
| 33 | Talkcraft / 五选一反黑 | src/components/component-vertical/video-talkcraft/entries/chip-grid-single-select.tsx | src/components/component-horizontal/video-talkcraft/entries/chip-grid-single-select.tsx | 表达多个选项中最终选中一个 | 工具选择、方案筛选、投票结果揭晓时使用 |
| 34 | Talkcraft / 名词解释悬浮卡 | src/components/component-vertical/video-talkcraft/entries/info-term-card.tsx | src/components/component-horizontal/video-talkcraft/entries/info-term-card.tsx | 表达专业名词需要快速解释 | AI 术语、财经概念、黑话第一次出现时使用 |
| 35 | Talkcraft / 地图路线图钉 | src/components/component-vertical/video-talkcraft/entries/map-route-pin.tsx | src/components/component-horizontal/video-talkcraft/entries/map-route-pin.tsx | 表达地点、路线或事件移动路径 | 事件复盘、行程、地域扩散讲解时使用 |
| 36 | Talkcraft / 编号步骤堆入 | src/components/component-vertical/video-talkcraft/entries/numbered-step-stack.tsx | src/components/component-horizontal/video-talkcraft/entries/numbered-step-stack.tsx | 表达几个并列要点可以截图保存 | 方法清单、操作要点、干货总结时使用 |
| 37 | Talkcraft / 竖向步骤线 | src/components/component-vertical/video-talkcraft/entries/step-timeline-vertical.tsx | src/components/component-horizontal/video-talkcraft/entries/step-timeline-vertical.tsx | 表达步骤之间有明确先后依赖 | 流程复盘、三步走、项目进度时使用 |
| 38 | Talkcraft / 界面道具剧场 | src/components/component-vertical/video-talkcraft/entries/ui-prop-theater.tsx | src/components/component-horizontal/video-talkcraft/entries/ui-prop-theater.tsx | 表达产品参数、状态和进度如何变化 | AI 工具测评、参数讲解、教程流程时使用 |
| 39 | Talkcraft / 多源汇聚 | src/components/component-vertical/video-talkcraft/entries/source-converge.tsx | src/components/component-horizontal/video-talkcraft/entries/source-converge.tsx | 表达多个来源汇聚成一个结论 | RAG、多渠道数据、证据归纳时使用 |
| 40 | Talkcraft / 同源模糊底床 | src/components/component-vertical/video-talkcraft/entries/bed-echo-blur.tsx | src/components/component-horizontal/video-talkcraft/entries/bed-echo-blur.tsx | 表达竖屏素材需要自然放进横屏画面 | 竖拍实拍、竖屏录屏、网友投稿时使用 |
| 41 | Talkcraft / 聊天记录自演 | src/components/component-vertical/video-talkcraft/entries/chat-message-flow.tsx | src/components/component-horizontal/video-talkcraft/entries/chat-message-flow.tsx | 表达聊天记录作为证据逐条出现 | 客户反馈、AI 对话、团队讨论还原时使用 |
| 42 | Talkcraft / 光标演员演示 | src/components/component-vertical/video-talkcraft/entries/cursor-actor-demo.tsx | src/components/component-horizontal/video-talkcraft/entries/cursor-actor-demo.tsx | 表达软件操作由光标带着观众完成 | 工具教程、AI 产品演示、设置引导时使用 |
| 43 | Talkcraft / 证据长页慢滚 | src/components/component-vertical/video-talkcraft/entries/evidence-scroll-tour.tsx | src/components/component-horizontal/video-talkcraft/entries/evidence-scroll-tour.tsx | 表达长文档证据需要边滚边讲 | 协议、README、报告、搜索结果讲解时使用 |
| 44 | Talkcraft / 素材弹入堆叠 | src/components/component-vertical/video-talkcraft/entries/media-pop-in.tsx | src/components/component-horizontal/video-talkcraft/entries/media-pop-in.tsx | 表达多张证据被一张张甩出来 | 爆料、辟谣、盘点、截图列举时使用 |
| 45 | Talkcraft / 新闻卡片划重点 | src/components/component-vertical/video-talkcraft/entries/news-card-desk.tsx | src/components/component-horizontal/video-talkcraft/entries/news-card-desk.tsx | 表达一条新闻是本段讨论依据 | 时事、财经、行业新闻解读时使用 |
| 46 | Talkcraft / 对比双分屏（滑动揭示） | src/components/component-vertical/video-talkcraft/entries/split-compare-slider.tsx | src/components/component-horizontal/video-talkcraft/entries/split-compare-slider.tsx | 表达同一对象前后或 A/B 差异 | 改版、修图、生成图、参数对比时使用 |
| 47 | Talkcraft / 多图排版 + 焦点接力 | src/components/component-vertical/video-talkcraft/entries/still-layout-relay.tsx | src/components/component-horizontal/video-talkcraft/entries/still-layout-relay.tsx | 表达主图和辅助图共同证明观点 | 一主两辅证据、三张截图对照时使用 |
| 48 | Talkcraft / 界面流程剧场 | src/components/component-vertical/video-talkcraft/entries/ui-flow-theater.tsx | src/components/component-horizontal/video-talkcraft/entries/ui-flow-theater.tsx | 表达一个产品功能从头到尾如何操作 | AI 工具上手、SaaS 教程、流程演示时使用 |
| 49 | Talkcraft / ChatGPT 对话框 | src/components/component-vertical/video-talkcraft/entries/chat-gpt.tsx | src/components/component-horizontal/video-talkcraft/entries/chat-gpt.tsx | 表达一次 ChatGPT 提问和回答 | 提示词技巧、模型能力演示、AI 科普时使用 |
| 50 | Talkcraft / 编码智能体终端 | src/components/component-vertical/video-talkcraft/entries/claude-code.tsx | src/components/component-horizontal/video-talkcraft/entries/claude-code.tsx | 表达编码智能体正在修改或运行代码 | AI 编程工具测评、开发者教程时使用 |
| 51 | Talkcraft / 文档驻留发牌 | src/components/component-vertical/video-talkcraft/entries/doc-park-left-pill-deal.tsx | src/components/component-horizontal/video-talkcraft/entries/doc-park-left-pill-deal.tsx | 表达从文档中提炼出几条结论 | 论文、报告、长文总结类 AI 话题时使用 |
| 52 | Talkcraft / 传送带列举 + 减速停靠 | src/components/component-vertical/video-talkcraft/entries/filmstrip-conveyor.tsx | src/components/component-horizontal/video-talkcraft/entries/filmstrip-conveyor.tsx | 表达很多案例中其中一个最重要 | 工具盘点、作品回顾、案例列表时使用 |
| 53 | Talkcraft / 照片墙推轨 | src/components/component-vertical/video-talkcraft/entries/gallery-wall-dolly.tsx | src/components/component-horizontal/video-talkcraft/entries/gallery-wall-dolly.tsx | 表达多个平级案例被逐个巡看 | 案例集、作品集、三个方案讲解时使用 |
| 54 | Talkcraft / 玻璃代码走读 | src/components/component-vertical/video-talkcraft/entries/glass-code-walk.tsx | src/components/component-horizontal/video-talkcraft/entries/glass-code-walk.tsx | 表达带观众读一小段关键代码 | 技术教程、开源项目、配置讲解时使用 |
| 55 | Talkcraft / 图块拼入 | src/components/component-vertical/video-talkcraft/entries/gooey-morph.tsx | src/components/component-horizontal/video-talkcraft/entries/gooey-morph.tsx | 表达几张证据属于同一组 | 多平台对比、组图、九宫格素材时使用 |
| 56 | Talkcraft / 网格收成主角 | src/components/component-vertical/video-talkcraft/entries/grid-to-hero.tsx | src/components/component-horizontal/video-talkcraft/entries/grid-to-hero.tsx | 表达从多个候选里选出主角 | 封面候选、版本选择、重点案例揭晓时使用 |
| 57 | Talkcraft / 信息卡逐字段自建 | src/components/component-vertical/video-talkcraft/entries/info-card-assemble.tsx | src/components/component-horizontal/video-talkcraft/entries/info-card-assemble.tsx | 表达人物、工具或课程信息被结构化 | 介绍书、工具、人、课程档案时使用 |
| 58 | Talkcraft / Logo 登场 | src/components/component-vertical/video-talkcraft/entries/logo-enter.tsx | src/components/component-horizontal/video-talkcraft/entries/logo-enter.tsx | 表达品牌、系列或频道身份登场 | 片头、片尾、产品名正式露出时使用 |
| 59 | Talkcraft / 模糊甩入急停 | src/components/component-vertical/video-talkcraft/entries/motion-blur-slam-in.tsx | src/components/component-horizontal/video-talkcraft/entries/motion-blur-slam-in.tsx | 表达证据或观点被强势甩到台前 | 爆点拆解、硬观点、数据卡压上时使用 |
| 60 | Talkcraft / 铅笔手绘揭示 | src/components/component-vertical/video-talkcraft/entries/pencil-sketch-draw.tsx | src/components/component-horizontal/video-talkcraft/entries/pencil-sketch-draw.tsx | 表达概念像手绘草图一样被画出来 | 流程解释、轻松科普、概念示意时使用 |
| 61 | Talkcraft / 焦点接力 | src/components/component-vertical/video-talkcraft/entries/rack-focus-pair.tsx | src/components/component-horizontal/video-talkcraft/entries/rack-focus-pair.tsx | 表达两个对象之间来回比较 | A/B 产品、两种观点、新旧方案对照时使用 |
| 62 | Talkcraft / 60/40 主从分屏 | src/components/component-vertical/video-talkcraft/entries/split-60-40-story.tsx | src/components/component-horizontal/video-talkcraft/entries/split-60-40-story.tsx | 表达主素材旁边同步列出讲解要点 | 录屏加要点、产品演示、教程旁白时使用 |
| 63 | Talkcraft / 卡堆扇形展开 | src/components/component-vertical/video-talkcraft/entries/stack-fan-out.tsx | src/components/component-horizontal/video-talkcraft/entries/stack-fan-out.tsx | 表达一叠素材展开成候选清单 | 照片、截图、评论卡汇总展示时使用 |
| 64 | Talkcraft / 终端逐行推进 | src/components/component-vertical/video-talkcraft/entries/terminal-typing-log.tsx | src/components/component-horizontal/video-talkcraft/entries/terminal-typing-log.tsx | 表达命令行执行结果可作为证据 | 构建、部署、测试、AI 编程演示时使用 |
| 65 | Talkcraft / 时间线照片带 | src/components/component-vertical/video-talkcraft/entries/timeline-photo-strip.tsx | src/components/component-horizontal/video-talkcraft/entries/timeline-photo-strip.tsx | 表达多个时间点按顺序串成故事 | 版本演进、年度回顾、事件时间线时使用 |
| 66 | Talkcraft / 动词接力胶片 | src/components/component-vertical/video-talkcraft/entries/word-relay-filmstrip.tsx | src/components/component-horizontal/video-talkcraft/entries/word-relay-filmstrip.tsx | 表达一个主体拥有连续多种能力 | AI 能力清单、产品场景巡礼时使用 |
| 67 | Talkcraft / 缓拉全貌 | src/components/component-vertical/video-talkcraft/entries/slow-pull-reveal.tsx | src/components/component-horizontal/video-talkcraft/entries/slow-pull-reveal.tsx | 表达先看局部再退回全貌 | 长表格、数据看板、全景总结时使用 |
| 68 | Talkcraft / 缓推特写 | src/components/component-vertical/video-talkcraft/entries/slow-push-in.tsx | src/components/component-horizontal/video-talkcraft/entries/slow-push-in.tsx | 表达观众视线慢慢收拢到素材重点 | 网页截图、文档、图片的冷静讲解时使用 |
| 69 | Talkcraft / 光标锁定跟拍 | src/components/component-vertical/video-talkcraft/entries/cursor-locked-zoom.tsx | src/components/component-horizontal/video-talkcraft/entries/cursor-locked-zoom.tsx | 表达镜头紧跟一个移动或长文本目标 | 长命令、代码行、表单字段讲解时使用 |
| 70 | Talkcraft / 环绕微漂 | src/components/component-vertical/video-talkcraft/entries/orbit-drift.tsx | src/components/component-horizontal/video-talkcraft/entries/orbit-drift.tsx | 表达静态页面在长讲述中保持呼吸感 | 长时间展示网页、报告、截图背景时使用 |
| 71 | Talkcraft / 画中画放大 | src/components/component-vertical/video-talkcraft/entries/pip-zoom-box.tsx | src/components/component-horizontal/video-talkcraft/entries/pip-zoom-box.tsx | 表达保留全景同时单独放大局部 | 讲产品细节、表情、截图一角时使用 |
| 72 | Talkcraft / 长页兴趣点巡游 | src/components/component-vertical/video-talkcraft/entries/stage-keyframe-tour.tsx | src/components/component-horizontal/video-talkcraft/entries/stage-keyframe-tour.tsx | 表达长页面按兴趣点逐站游览 | 落地页、长截图、长报表巡讲时使用 |
| 73 | Talkcraft / 左右摇移 | src/components/component-vertical/video-talkcraft/entries/sway-parallax.tsx | src/components/component-horizontal/video-talkcraft/entries/sway-parallax.tsx | 表达横向长素材需要顺着讲过去 | 时间线、宽流程图、超宽截图时使用 |
| 74 | Talkcraft / 3D 立面展示 | src/components/component-vertical/video-talkcraft/entries/tilt-3d-page.tsx | src/components/component-horizontal/video-talkcraft/entries/tilt-3d-page.tsx | 表达网页或 UI 像产品模型一样展示 | 作品展示、产品介绍、案例墙时使用 |
| 75 | Talkcraft / 黑震切转场 | src/components/component-vertical/video-talkcraft/entries/black-slam-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/black-slam-transition.tsx | 表达全片最大反转或揭示即将发生 | 悬念停顿后切出答案时使用 |
| 76 | Talkcraft / 章节标题卡 | src/components/component-vertical/video-talkcraft/entries/chapter-title-card.tsx | src/components/component-horizontal/video-talkcraft/entries/chapter-title-card.tsx | 表达长视频进入新的正式章节 | 5 分钟以上内容的段落切换时使用 |
| 77 | Talkcraft / 纯色硬切节拍卡 | src/components/component-vertical/video-talkcraft/entries/color-slam-beat-card.tsx | src/components/component-horizontal/video-talkcraft/entries/color-slam-beat-card.tsx | 表达一句观点被当作节拍重锤 | 短口播下判断、列条目、砸观点时使用 |
| 78 | Talkcraft / 过曝翻页转场 | src/components/component-vertical/video-talkcraft/entries/overexpose-flip-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/overexpose-flip-transition.tsx | 表达郑重翻页进入下一段证据 | 章节翻页、关键截图之后转场时使用 |
| 79 | Talkcraft / 粒子溶接转场 | src/components/component-vertical/video-talkcraft/entries/particle-weld-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/particle-weld-transition.tsx | 表达同一概念从一种形态变成另一种 | 数据变图表、概念变案例时使用 |
| 80 | Talkcraft / 后拉冷却转场 | src/components/component-vertical/video-talkcraft/entries/pullback-cool-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/pullback-cool-transition.tsx | 表达激烈段落结束后退一步看 | 结论前呼吸、情绪冷却、沉淀转场时使用 |
| 81 | Talkcraft / 推穿转场 | src/components/component-vertical/video-talkcraft/entries/push-through-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/push-through-transition.tsx | 表达从概念推进到证据或细节 | 全景到局部、观点到案例之间使用 |
| 82 | Talkcraft / 色块扫屏转场 | src/components/component-vertical/video-talkcraft/entries/shape-wipe-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/shape-wipe-transition.tsx | 表达话题切换，节奏进入下一块 | 章节切分、快节奏换主题时使用 |
| 83 | Talkcraft / 横甩转场 | src/components/component-vertical/video-talkcraft/entries/whip-pan-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/whip-pan-transition.tsx | 表达平级案例之间快速横向切换 | A 到 B、人物切换、市场切换时使用 |
| 84 | Talkcraft / 光标擦除转场 | src/components/component-vertical/video-talkcraft/entries/caret-wipe-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/caret-wipe-transition.tsx | 表达文本、代码或版本被重写 | 编辑器、文档、AI 生成内容转场时使用 |
| 85 | Talkcraft / 章节进度 | src/components/component-vertical/video-talkcraft/entries/chapter-progress-list.tsx | src/components/component-horizontal/video-talkcraft/entries/chapter-progress-list.tsx | 表达观众需要知道现在讲到哪 | 长口播目录、章节进度、系列内容时使用 |
| 86 | Talkcraft / 线条接力转场 | src/components/component-vertical/video-talkcraft/entries/line-carry-transition.tsx | src/components/component-horizontal/video-talkcraft/entries/line-carry-transition.tsx | 表达上一镜的线索牵出下一镜 | 章节接缝、图形亲缘强的两镜之间使用 |
| 87 | Talkcraft / 长镜头世界画布 | src/components/component-vertical/video-talkcraft/entries/long-take-world.tsx | src/components/component-horizontal/video-talkcraft/entries/long-take-world.tsx | 表达一个大系统可被一镜到底走完 | 流程、地图、生态图、世界观段落时使用 |
| 88 | Talkcraft / 冲击开场 | src/components/component-vertical/video-talkcraft/entries/impact-open-title.tsx | src/components/component-horizontal/video-talkcraft/entries/impact-open-title.tsx | 表达开场钩子要立刻抓住注意力 | 视频前 3 秒、强观点章节开幕时使用 |
| 89 | Talkcraft / 关键词弹出强调 | src/components/component-vertical/video-talkcraft/entries/keyword-pop-highlight.tsx | src/components/component-horizontal/video-talkcraft/entries/keyword-pop-highlight.tsx | 表达这一词就是当前信息峰值 | 数字、反转词、核心结论出现时使用 |
| 90 | Talkcraft / 重点放大 | src/components/component-vertical/video-talkcraft/entries/slab-punch-title.tsx | src/components/component-horizontal/video-talkcraft/entries/slab-punch-title.tsx | 表达前半句铺垫，后半句才是重点 | 观点号、干货号的小标题或重音句使用 |
| 91 | Talkcraft / 标题降格成标签 | src/components/component-vertical/video-talkcraft/entries/title-demote-to-label.tsx | src/components/component-horizontal/video-talkcraft/entries/title-demote-to-label.tsx | 表达标题让位后变成小节路标 | 教程、方法论、问答式小节交接时使用 |
| 92 | Talkcraft / 字体对比重音 | src/components/component-vertical/video-talkcraft/entries/type-contrast-emphasis.tsx | src/components/component-horizontal/video-talkcraft/entries/type-contrast-emphasis.tsx | 表达重音来自字体气质的反差 | 克制观点句、不是 A 而是 B 时使用 |
| 93 | Talkcraft / 词槽轮换 | src/components/component-vertical/video-talkcraft/entries/word-slot-cycle.tsx | src/components/component-horizontal/video-talkcraft/entries/word-slot-cycle.tsx | 表达一个位置快速轮换多种用途 | AI 能帮你做 A/B/C/D 的功能列举时使用 |
| 94 | Talkcraft / 双色块对句 | src/components/component-vertical/video-talkcraft/entries/alt-block-lines.tsx | src/components/component-horizontal/video-talkcraft/entries/alt-block-lines.tsx | 表达两句对照关系清晰并列 | 不是 A 而是 B、以前现在对比时使用 |
| 95 | Talkcraft / 数字重音标题 | src/components/component-vertical/video-talkcraft/entries/count-badge-title.tsx | src/components/component-horizontal/video-talkcraft/entries/count-badge-title.tsx | 表达这段内容有明确数量承诺 | 三个方法、五个坑、两件事开场时使用 |
| 96 | Talkcraft / 打字改口 | src/components/component-vertical/video-talkcraft/entries/error-retype.tsx | src/components/component-horizontal/video-talkcraft/entries/error-retype.tsx | 表达先写错认知再改成正确认知 | 纠正常见误解、反转 hook、提示词改口时使用 |
| 97 | Talkcraft / 首词占满补句 | src/components/component-vertical/video-talkcraft/entries/lead-word-zoom-assemble.tsx | src/components/component-horizontal/video-talkcraft/entries/lead-word-zoom-assemble.tsx | 表达句子主语或首词先成为主角 | 金句、产品名、数字先行标题时使用 |
| 98 | Talkcraft / 逐行滑入 | src/components/component-vertical/video-talkcraft/entries/line-by-line-slide.tsx | src/components/component-horizontal/video-talkcraft/entries/line-by-line-slide.tsx | 表达多行要点作为一组进入画面 | 三四条清单、步骤、分行金句时使用 |
| 99 | Talkcraft / 描边框标题 | src/components/component-vertical/video-talkcraft/entries/outline-box-title.tsx | src/components/component-horizontal/video-talkcraft/entries/outline-box-title.tsx | 表达一个短语被定义成核心结论 | 立论点、术语定义、理性结论框定时使用 |
| 100 | Talkcraft / 逐字升起 | src/components/component-vertical/video-talkcraft/entries/per-character-rise.tsx | src/components/component-horizontal/video-talkcraft/entries/per-character-rise.tsx | 表达一句短主张有力站起来 | 论点句、口号、结论句上屏时使用 |
| 101 | Talkcraft / 引号夹句 | src/components/component-vertical/video-talkcraft/entries/quote-bracket-pull.tsx | src/components/component-horizontal/video-talkcraft/entries/quote-bracket-pull.tsx | 表达某句话被当成引用郑重呈现 | 引用他人原话、观众留言、自我金句时使用 |
| 102 | Talkcraft / 金句大字卡 | src/components/component-vertical/video-talkcraft/entries/quote-card.tsx | src/components/component-horizontal/video-talkcraft/entries/quote-card.tsx | 表达整段观点达到金句峰值 | 结论、暴论、情绪收束动作时使用 |
| 103 | Talkcraft / 柔焦淡入 | src/components/component-vertical/video-talkcraft/entries/soft-blur-in.tsx | src/components/component-horizontal/video-talkcraft/entries/soft-blur-in.tsx | 表达温和旁白或小标题轻轻出现 | 冷静结论、品牌片、素材切换后第一句时使用 |
| 104 | Talkcraft / 速度块标题 | src/components/component-vertical/video-talkcraft/entries/speed-slab-title.tsx | src/components/component-horizontal/video-talkcraft/entries/speed-slab-title.tsx | 表达效率、提速、抢先这类快感 | 短口播开场、效率主题、速度重音时使用 |
| 105 | Talkcraft / 字距收拢 | src/components/component-vertical/video-talkcraft/entries/tracking-in.tsx | src/components/component-horizontal/video-talkcraft/entries/tracking-in.tsx | 表达一句大标题需要发布会气质 | 开场标题、片尾落版、品牌短句时使用 |
| 106 | Talkcraft / 打字机档案戳 | src/components/component-vertical/video-talkcraft/entries/typewriter-reveal.tsx | src/components/component-horizontal/video-talkcraft/entries/typewriter-reveal.tsx | 表达时间地点档案被逐字记录 | 纪录片、调查、悬疑盘点交代背景时使用 |
| 107 | Talkcraft / 数字弧落标题 | src/components/component-vertical/video-talkcraft/entries/countdown-arc-scatter.tsx | src/components/component-horizontal/video-talkcraft/entries/countdown-arc-scatter.tsx | 表达数字本身带悬念和揭晓感 | 5 分钟、3 个原则、倒计时开场时使用 |
| 108 | Talkcraft / 关键词隧道 | src/components/component-vertical/video-talkcraft/entries/flying-words.tsx | src/components/component-horizontal/video-talkcraft/entries/flying-words.tsx | 表达大量概念围绕一个主题涌来 | AI 名词科普开场、能力清单背景时使用 |
| 109 | Talkcraft / 逐字裂升 | src/components/component-vertical/video-talkcraft/entries/split-text-stagger.tsx | src/components/component-horizontal/video-talkcraft/entries/split-text-stagger.tsx | 表达标题从基线中利落长出来 | 章节题、频道名、短金句入场时使用 |

### 使用说明

工作表 `jdNBUs`；12 条记录。

| 飞书行号 | 事项 | 说明 |
| --- | --- | --- |
| 2 | 目录范围 | 组件目录统一收录 152 个组件：Snapcn 21、RVE 11、Remocn 5、RemotionUI 3、Bits 4、Talkcraft 108。每行同时提供竖版、横版入口及表达内容、使用场景。Talkcraft 子表保留108行便于筛选。 |
| 3 | 预览方式 | 在 D:\remotion_video 运行 npm run components，进入 http://127.0.0.1:3102。Studio 中 component-vertical 是原生竖版，component-horizontal 是横版对照。原有 Composition ID 保持不变。 |
| 4 | 本地效果目录 | http://127.0.0.1:63204/ 或 out/components/index.html。152 个组件提供全分辨率原版三帧；152 个已接入原生竖屏三帧；可切换画布视图、筛选组件库。 |
| 5 | 复用入口 | 相对路径以 D:\remotion_video 为根目录。实际竖版、横版源码分别在 src/components/component-vertical、src/components/component-horizontal；entries/<slug>.tsx 是单组件演示入口，导出 Component、demo、meta。community 只保留注册、目录元数据和共享工具。 |
| 6 | 已经验证 | Remotion 4.0.532：304 个注册项；152 原版起始/中间/结束帧，152 原生竖屏起始/中间/结束帧。108 原源码 SHA256 一致；全部 TypeScript 与接入层及竖屏代码 lint 通过。渲染抽样不等于任意长文案均已排版验证。 |
| 7 | 竖屏适配 | 竖版统一 1080×1920 / 30fps，面向 TikTok/抖音/快手；源码按竖屏重排，ID 为 Vertical- 加原 Composition。横版沿用来源规格，聊天示例使用1280×720。换文案后检查排版。 |
| 8 | 示例数据 | 图表数据、对话内容与界面 SVG 都是演示，不是实测模型排行或真实产品操作证据。 |
| 9 | 字体与字幕 | PromptZoom 恢复官方英文 props、90 帧和离线 Inter / Source Serif 4；部分组件及中文仍回退系统字体。原44个演示修改过文案/素材，并非像素一比一。生产字幕需实际配音时间戳。 |
| 10 | 上游默认素材 | Talkcraft 原图、视频与AI示例主持人按作者 HTML 注入并保存来源；其它库部分仍用示例 SVG。主持人可选，手部素材独立许可未核实；网站音效不在原 TSX 中。 |
| 11 | 来源与许可 | 每个库固定上游 commit，证据保存在 licenses/community。RVE / Bits 的 MIT 来自上游声明，未伪造其缺失的 LICENSE。Remotion 核心许可仍单独适用。 |
| 12 | video-talkcraft | 已按用户声明的非商业个人用途复制108原卡；保留 PolyForm Noncommercial 和来源。不安装整个工作台。原卡字节一致，Windows字体、网站HTML/MP4、音效仍可能与本地预览不同。 |
| 13 | 研究日期 | 2026-10-02。源码、预览、许可与版本按这次核对记录；以后更新需重新核对。 |
