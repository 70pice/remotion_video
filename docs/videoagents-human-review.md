# 在工作流中插入人工审核

节点实现：`videoagents/nodes/human_review.py` 的 `HumanReviewNode`。
编排入口：`videoagents/graph/video_graph.py` 的构造函数和 `add_human_review()`。

默认图现在接入三处审核：`human_review_script`（文案）、`human_review_timeline`（导演分镜）、`human_review_render`（剪辑成片）。每处使用真正的 LangGraph interrupt，未确认时不会执行下游。旧的 `human_review` 注册仍保留，以兼容此前自行编排的阶段待办。

项目的人工参与还包括补充信息、直接修改产物，以及提交意见让对应节点修订，完整产品要求见 [制作标准：人工参与](videoagents-storytelling-standard.md#2-人工参与是制作流程的核心)。三个默认审核节点的 `revise` 会把当前产物和说明交给编剧或导演修订，而后再次审核；自行注册且未配置返工目标的审核节点仍会回到草稿，供手工保存新版本。

## 当前默认主流程

素材 → 编剧与文案审查讨论 → ScriptGate → 文案人工审核 → 配音 → AudioGate → 导演组件学习和分镜 → TimelineGate → 分镜人工审核 → 剪辑/Remotion → 成片人工审核 → 成片机器审核 → 最终发布人审。

| 人工审核 | 用户检查 | 要求返工时 |
| --- | --- | --- |
| 文案 | 普通人视角、首句观看理由、主线、事实依据、自然收尾 | 编剧消费意见生成改稿，重新机器讨论和检查，再次人工审稿 |
| 分镜 | 音画对应、视频选段、证据、竖屏可读性、组件表达 | 导演在实测音频约束下修改分镜，再次校验与人工审核 |
| 剪辑 | 播放实际视频，检查画面、字幕、声音与节奏 | 画面修改返回导演，分镜重新确认后再渲染，再次审核成片 |

阶段确认不授予 `READY_FOR_PUBLISH`。最终机器审核与发布人工复核仍保留。

## 继续自行编排：成功分支接入审核

在构造函数中，替换原来 `script_gate` 的条件边：

```python
graph.add_conditional_edges("script_gate", self.route, {
    "voice": "human_review_script",
    "await_input": "await_input",
})
```

得到：`screenwriter / script_reviewer → script_gate → human_review_script → after_script_review → voice → …`。
这里 `"voice"` 是 `ScriptGateNode` 返回的路由值，`"human_review_script"` 是实际目标，不用改 `nodes/gates.py` 中的节点实现。

**替换原成功分支，不要追加一条普通边**；同时保留原来的错误分支，否则配音和人工审核可能同时执行。默认人工审核的注册配置是：

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

## 默认第二个审核点：分镜检查后、剪辑前

在 `graph.compile(...)` 前注册：

```python
self.add_human_review(
    graph, "human_review_timeline",
    stage="director",
    title="分镜人工审核",
    confirmation_requirements=("音画对应", "关键镜头表现力", "字幕与素材可读性"),
    next_node="after_timeline_review",
    revise_node="director",
    min_note_length=10,
)
```

替换原 `timeline_gate` 条件边：

```python
graph.add_conditional_edges("timeline_gate", self.route, {
    "editing": "human_review_timeline",
    "await_input": "await_input",
    "end": "human_review_timeline",
    "reviewers": "human_review_timeline",
})
```

这些成功分支均先审核分镜，确认后的 `after_timeline_review` 再按 action 决定结束本次 storyboard、进入 editing，或进入已有成片的 reviewers；不会让单独生成分镜意外启动渲染。preview 在剪辑人工审核确认后结束，不自动进入发布审核。

`stage` 使用 `materials`、`script`、`voice`、`director`、`render` 或 `review`；素材审核示例见 [素材节点](videoagents-materials.md)。审核节点名称需唯一，`next_node` 要是图中已有节点。也可以指定 `END`，此时确认后结束本次执行，任务回到 `DRAFT`，不会留在运行中或标记发布通过。

## 人工决定与前端

| 决定 | 行为 |
| --- | --- |
| `confirm` | 核对当前版本、文件与对齐元数据，保存说明，走 `continue` 到 `next_node` |
| 说明过短 | 生成新待办，走 `retry` 回到同一审核点，继续等待 |
| `revise` | 默认审核节点将说明与产物快照放入 `extras.human_feedback`，走配置的返工目标；未配置目标的自定义节点回到 `DRAFT` |
| `cancel` | 保存决定，任务变为 `CANCELLED` 并结束 |

React 工作台显示阶段审核卡，并切到文案、分镜或剪辑页签。卡片直接展示对应的真实稿件、镜头清单或当前版本 preview/final 视频，不将原始素材视频当成成片。默认说明至少 10 字，可通过 `min_note_length` 调整到 0–3000。审核决定保存为 `stage_review` JSON 产物，包含节点、阶段、版本、待办 token、输入指纹、决定与说明。

阶段确认仅放行当前审核点。文案、音频、分镜和成片的硬检查，以及原有的最终人工复核，仍会执行。把审核点放在阶段成功分支，并保留错误分支的 `await_input`。

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

暂停使用 `interrupt()` 和已有 SQLite checkpointer，恢复继续走 `POST /api/jobs/{job_id}/resume`，带最新 `base_revision`、`pending_token`、`decision`、`note` 及新的 `idempotency_key`。API/worker 使用原 `thread_id` 和对应 interrupt ID，无需新增接口。直接调用 LangGraph 时，resume 值同样需包含 `decision`、`note` 和待办的 `pending_token`。

共享 state 中，`human_decision` 保存最近一次审核记录，`human_review_rounds` 区分同一节点的多轮审核，`stage_review_pending` 保存校验失败后的新问题。每次节点调用只有一个 `interrupt()`；SQL 已保存、checkpoint 尚未提交时，稳定的审核记录 ID 支持重放。

`extras.human_feedback` 是最终人工制作意见，不是工具历史。角色须处理当前未应用的反馈并记录回应；文案返工不能复用旧讨论的通过状态，分镜返工不能直接返回旧 timeline。若角色禁用、预算不足或反馈超出可执行能力，明确暂停，不伪造修改成功。

`revise` 回执同时持久化待审产物快照。若当前角色存在 `UNKNOWN` 提交，使用草稿 API 保存新 revision 后，新的 Graph 会从仍未匹配 `human_feedback_applied` 的最新审核回执恢复返工说明；角色实际产出新结果并写入消费回执后才停止恢复。这样升版不会丢失人工意见，也不会用切换模型或盲重试绕过旧版本的 `UNKNOWN` 屏障。

人工文案返工生成新稿后，从第一轮重新开启机器讨论，沿用本次执行冻结的每周期轮数上限。旧讨论的不可变文件保留，新稿不会追加到已用满的旧周期，也不会继承旧稿的审查通过结果；整个任务的模型调用预算仍累计计算。

当前应用顺序处理一个待办，可串联多个审核节点，暂不支持并行分支同时待审。改图后重启 worker，使后续执行使用新编排；已暂停的运行应保留原节点名称和检查要求，改变待审要求时重新发起执行。旧回复不能放行新内容。

官方说明：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。
