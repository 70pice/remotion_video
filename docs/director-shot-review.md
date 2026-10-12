# 导演逐镜审核

2026-10-11 用户要求：普通制作取消导演30秒Demo，导演每次明确每镜组件或组件套，为每镜渲染一张代表帧，人工审阅全部镜头后才渲染完整成片。

## 实施与验证计划

1. 复用现有导演、Remotion与LangGraph人工审核入口。新导演方案使用 `review_mode=per_shot_stills`，包含每镜 `shot_reviews`：镜头ID、全片绝对代表帧、选型理由和画面动作。程序校验每镜都存在一条设计，帧落在镜内；从实际时间轴派生组件、套内成员、素材、旁白与时间范围。
2. 同一次Remotion bundle/browser逐张生成原画幅PNG，使用完整时间轴及真实绝对帧。不能改音频、字幕时刻、素材或画面组件来伪造审核图。全部成功后才登记完整审核包；取消、超时或缺图走原有补充/续跑入口。
3. 审核包绑定当前任务、revision、导演方案SHA、timeline fingerprint、输入依赖以及每张图的登记与真实文件SHA。遗漏、重复、跨任务、越界、字节变化与陈旧方案均不能通过审核。
4. 前端按镜头顺序显示PNG、组件/套及成员、旁白、设计说明与镜头反馈。图片成功加载后可标记已阅；所有镜头已阅才允许整包确认，提交 `reviewed_shot_ids`。返工意见交回导演，重新生成审核图并等待新审核。
5. 先写失败回归，再实现契约、节点、渲染与UI。完成相关Python/API/JS/Web回归、Ruff、契约导出检查、前后端类型检查及构建，再通过正常Graph做真实Remotion图片冒烟验证。真实制作仍等待用户审核，不替用户确认或发布。

## 使用与维护

普通生产：文案人审 → 配音 → 导演设计 → 所有镜头的PNG审核包 → 逐镜已阅与整包确认 → 完整成片 → `DRAFT / complete`。

默认使用每镜一张PNG，展示的是导演选择的真实代表帧。它可以检查布局、素材、文字大小和当前字幕，不能证明整个镜头的动态过程或配音同步。导演应选择主要信息已显现、未退场的帧，并在说明中交代其他时刻的动作。

`director_demo`、`director_human_gate` 等历史节点名保留为checkpoint兼容入口。旧导演方案与组件套独立静音样片保持原有Demo读取/回放方式，不把历史审核改写为已完成新逐镜审核。新普通导演方案不再要求或产出30秒Demo。

输入、音频对齐或草稿revision变化后，逐镜审核包与帧产物失效。人工确认只授予当前版本完整渲染资格，仍不授予发布资格。渲染由已有Worker独占、超时与取消机制管理，无新依赖或外部服务。

## 回归验证

- `tests/videoagents/test_shot_review_contract.py`、`test_director_shot_review.py` 覆盖每镜设计、完整图片包、当前版本及文件指纹校验。
- API、Graph 与人工审核回归覆盖漏审拒绝、返工重新出图和旧 Demo 兼容；`tests/integration/test_shot_review_render.py` 覆盖 Worker 的批量渲染、失败、取消与超时。
- `src/video-production/shot-review-render.test.mjs` 覆盖绝对帧、原尺寸 PNG、完整发布及失败不交付半包；前端 `director-shot-review.test.tsx` 覆盖图片加载、逐镜已阅及整包提交。
- 设置 `VIDEOAGENTS_RUN_LIVE_RENDER=1` 执行 `tests/integration/test_shot_review_graph_live.py`，可通过测试任务 API、Worker 和真实 Remotion 验证两镜出图后停在导演人审。测试使用空研究结果、测试文字、人工导入静音测试音轨和模拟文案审查，不合成配音，不自动确认导演图包，不修改生产任务。默认回归跳过真实浏览器渲染。
