# 在工作流中插入人工审核

节点实现：`videoagents/nodes/human_review.py` 的 `HumanReviewNode`。
编排入口：`videoagents/graph/video_graph.py` 的构造函数和 `add_human_review()`。

2026-10-11 起，默认图接入两个固定人工审核点：`human_review_script`（文案）和 `director_human_gate`（导演逐镜图片）。它们都使用真正的 LangGraph interrupt。文案未确认时不会配音；全部镜头的当前审核包未确认时不会进入完整成片渲染。新制作不生成 30 秒导演 Demo，而为每个镜头生成一张原尺寸代表帧，附实际组件及组件套、旁白和设计说明。旧任务的 Demo 待办与独立组件样片仍可读取和续跑，不能替代新制作的逐镜审核。完整契约见 [导演逐镜审核](director-shot-review.md)。旧 `timeline_gate`、`human_review_timeline`、`human_review_render`、成片机器审核及最终发布人审链仍保持移除。`await_input` 保留补充输入、渲染失败和其他可恢复失败的续跑能力。旧的 `human_review` 注册仍保留，供自行编排使用，正常入口没有进入它的边。

项目的人工参与还包括补充信息、直接修改产物，以及提交意见让编剧或导演修订。文案审核的 `revise` 会把当前稿件和说明交给编剧，实际改稿后再次审核；导演逐镜审核的 `revise` 回到 `director`，保留匹配的音频和时间戳，让导演重做 `shots`、逐段表演和每镜代表帧及说明，再重新生成图片包。自行注册且未配置返工目标的审核节点仍会回到草稿，供手工保存新版本。

## 当前默认主流程

素材 → 编剧与文案审查讨论 → 文案人工审核 → 配音 → AudioGate → 导演读取组件知识库并输出 `shots + segment_performances + shot_reviews` → Remotion 为每镜渲染一张图片 → 导演逐镜人工审核 → 剪辑/Remotion 完整成片 → 结束。默认 1 轮文案审查；若审查要求修改，编剧最后改稿一次后直接交人工审核。

| 人工审核 | 用户检查 | 要求返工时 |
| --- | --- | --- |
| 文案 | 普通人视角、首句观看理由、主线、事实依据、自然收尾 | 编剧消费意见生成改稿，重新机器讨论和检查，再次人工审稿 |
| 导演逐镜图片 | 每镜实际组件/组件套、素材可读性、旁白和画面对应、表演设计是否合理；逐张加载并标记已阅 | 回到导演节点，保留当前配音和 alignment，处理按镜头编号记录的意见，重做设计并生成新图片包后重新审核 |

文案确认只放行配音；全部镜头确认只放行完整成片渲染。单张图片只能检查所选时刻，不代表整段动效或配音字幕同步已验证。成片生成后以 `DRAFT` / `complete` 结束，不授予 `READY_FOR_PUBLISH`，也不生成最终发布审核通过记录。

## 当前文案审核连线

编剧初稿进入 `script_reviewer`；审查通过或最后改稿完成后进入 `human_review_script`：

```python
graph.add_conditional_edges("clear_screenwriter", self.route, {
    "script_reviewer": "script_reviewer",
    "human_review_script": "human_review_script",
    "await_input": "await_input",
})
```

实际图通过 `add_cleanup_edge()` 生成 `clear_screenwriter` 和 `clear_script_reviewer`，两个角色的输出都先清理工具调用记录。旧 `script_gate` 仅为恢复已有 checkpoint 保留，新制作不进入它。默认人工审核的注册配置是：

```python
self.add_human_review(
    graph, "human_review_script",
    stage="script",
    title="文案人工审核",
    confirmation_requirements=("文案表达与事实来源", "截图及素材与文案一致"),
    next_node="after_script_review",
    revise_node="screenwriter",
)
```

## 后续制作与阶段停止

仅需配音时，在文案人工审核的 `POST /api/jobs/{job_id}/resume` 确认请求中加
`"stop_after": "voice"`。Worker 恢复原 checkpoint，将本次执行目标设为 `voice`；
顺序仍为文案确认 → 配音 → 工具清理 → 音频及时间戳校验，成功后停在
`DRAFT` / `voice`，不进入导演、剪辑。原文案、素材和人工反馈保留。
配音失败的输入中断也可带此选项续跑。该选项只接受 `confirm`，且只适用于
文案审核或配音输入中断；省略时沿用原执行目标。

配音完成后，通过 `POST /api/jobs/{job_id}/runs` 提交
`{"base_revision": 当前版本, "action": "produce", "continue_from": "voice", "idempotency_key": "新的唯一键"}`。
API 绑定已完成配音的原工作流，Worker 核对文案人工确认、音频文件和时间戳后，
从原共享状态进入 AudioGate → 导演 → 剪辑。素材、文案、配音及人工反馈保留；
只有当前版本停在 `DRAFT` / `voice` 且没有待办时可用。

已完成分镜、预览或成片后，只重做画面时，同一入口提交
`{"base_revision": 当前版本, "action": "produce", "rebuild_from": "director", "idempotency_key": "新的唯一键"}`。
Worker 绑定当前版本已完成的原 checkpoint，核对文案人工确认及原始音频后，
通过 AudioGate → 导演 → 剪辑重新制作。导演重新选择素材并编排镜头，不复用旧分镜；
文案、配音、素材和人工反馈保留。此入口要求 `DRAFT` / `director`、`render` 或
`complete`，没有待办，且原制作输入未改变。不能同时指定 `continue_from`。

导演成功后经 `clear_director` 进入保留旧 checkpoint 名称的 `director_demo`，新方案在此生成逐镜图片包。新普通制作的 `storyboard` 和 `preview` 都在设计及全部图片生成后结束为 `DRAFT` / `director`，不自动写入审核确认。`produce` / `final` 必须经过 `director_human_gate` 的 `confirm` 后才进入 `editing` 渲染完整成片，并以 `DRAFT` / `complete` 结束。旧 `review` 动作结束为草稿并提示审核流程已移除。

时间轴及素材的技术校验仍由导演、逐镜渲染和剪辑节点执行，失败进入 `await_input`。导演节点内同时检查镜头可读时长；已有短镜头通过原导演节点重做视觉切点。`director_plan` 与 timeline fingerprint、每张图片的帧号及 hash、素材 hash 和审核回执绑定；旧 token、旧 revision、内容变化或文件变化都会拒绝放行。剪辑指导只检查画面与渲染输入，输出问题只归属导演或剪辑，不重开已确认的文案和配音审查。剪辑输入包含程序计算的素材可用性；个人视频的素材可直接入片，历史“待核验”备注不阻止使用。有合适素材时必须在画面中使用，仍需匹配内容与时长。

`stage` 使用 `materials`、`script`、`voice`、`director`、`render` 或 `review`；素材审核示例见 [素材节点](videoagents-materials.md)。审核节点名称需唯一，`next_node` 要是图中已有节点。也可以指定 `END`，此时确认后结束本次执行，任务回到 `DRAFT`，不会留在运行中或标记发布通过。

## 人工决定与前端

| 决定 | 行为 |
| --- | --- |
| `confirm` | 核对当前版本、文件与对齐元数据，保存说明，走 `continue` 到 `next_node` |
| 说明过短 | 生成新待办，走 `retry` 回到同一审核点，继续等待 |
| `revise` | 默认审核节点将说明与产物快照放入 `extras.human_feedback`，走配置的返工目标；未配置目标的自定义节点回到 `DRAFT` |
| `cancel` | 保存决定，任务变为 `CANCELLED` 并结束 |

React 工作台显示阶段审核卡，并切到文案、分镜或剪辑页签。新导演卡片逐镜展示真实 PNG、组件及组件套、旁白和设计说明，可放大查看并填写镜头意见。全部图片加载且标记已阅后才能确认；确认请求还须提交所有 `reviewed_shot_ids`，后台再次核对完整性。旧任务仍展示其真实 Demo。默认说明至少 10 字，可通过 `min_note_length` 调整到 0–3000。审核决定保存为 `stage_review` JSON 产物，包含节点、阶段、版本、待办 token、输入指纹、决定与说明；逐镜确认还记录完整图片包及已审镜头编号。

阶段确认仅放行当前审核点。文案和音频检查、导演及剪辑的技术校验仍会执行。自行编排审核点时，应放在成功分支并保留错误分支的 `await_input`。

## 自己构建 StateGraph 时直接使用

```python
from videoagents.nodes.human_review import HumanReviewNode

graph.add_node("audio_review", HumanReviewNode(
    self.repo, node_name="audio_review", stage="voice", title="配音试听",
    confirmation_requirements=("读音正确", "语气自然", "字幕时间与声音一致"),
))
graph.add_conditional_edges("audio_review", self.route, {
    "continue": "director",
    "retry": "audio_review",
    "end": END,
})
```

如果直接将 `continue` 接到 `END`，同时设置 `finish_on_confirm=True`；辅助方法会自动处理。

暂停使用 `interrupt()` 和已有 SQLite checkpointer，恢复继续走 `POST /api/jobs/{job_id}/resume`，带最新 `base_revision`、`pending_token`、`decision`、`note` 及新的 `idempotency_key`。新逐镜确认另带 `reviewed_shot_ids`，例如 `["shot-01", "shot-02"]`，须包含当前全部镜头。API/worker 使用原 `thread_id` 和对应 interrupt ID，无需新增接口。直接调用 LangGraph 时，resume 值同样需包含以上审核字段。

共享 state 中，`human_decision` 保存最近一次审核记录，`human_review_rounds` 区分同一节点的多轮审核，`stage_review_pending` 保存校验失败后的新问题。每次节点调用只有一个 `interrupt()`；SQL 已保存、checkpoint 尚未提交时，稳定的审核记录 ID 支持重放。

`extras.human_feedback` 是最终人工制作意见，不是工具历史。角色须处理当前未应用的反馈并记录回应；文案返工不能复用旧讨论的通过状态，分镜返工不能直接返回旧 timeline。若角色禁用、预算不足或反馈超出可执行能力，明确暂停，不伪造修改成功。

`revise` 回执同时持久化待审产物快照。若当前角色存在 `UNKNOWN` 提交，使用草稿 API 保存新 revision 后，新的 Graph 会从仍未匹配 `human_feedback_applied` 的最新审核回执恢复返工说明；角色实际产出新结果并写入消费回执后才停止恢复。这样升版不会丢失人工意见，也不会用切换模型或盲重试绕过旧版本的 `UNKNOWN` 屏障。

人工文案返工生成新稿后，从第一轮重新开启机器讨论，沿用本次执行冻结的每周期轮数上限。旧讨论的不可变文件保留，新稿不会追加到已用满的旧周期，也不会继承旧稿的审查通过结果；整个任务的模型调用预算仍累计计算。

当前应用顺序处理一个待办，可自行串联审核节点，暂不支持并行分支同时待审。改图后重启 worker，使后续执行使用新编排。旧的分镜、剪辑或发布审核待办恢复时结束为草稿，提示重新提交制作；旧回复不会继续旧审核链。现有文案审核及补充输入待办仍正常恢复。

官方说明：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。
