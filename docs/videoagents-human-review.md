# 在工作流中插入人工审核

节点实现：`videoagents/nodes/human_review.py` 的 `HumanReviewNode`。
编排入口：`videoagents/graph/video_graph.py` 的构造函数和 `add_human_review()`。

默认图已注册 `human_review`，但没有接入主流程，当前运行行为保持原样。它默认审核文案，通过后去 `voice`；你可以修改配置和连线，也可以增加多个不同名称的审核点。

## 文案检查后、配音前：只改一处成功分支

在构造函数中，替换原来 `script_gate` 的条件边：

```python
graph.add_conditional_edges("script_gate", self.route, {
    "voice": "human_review",   # 原来是 "voice": "voice"
    "await_input": "await_input",
})
```

得到：`screenwriter → script_gate → human_review → voice → audio_gate → …`。
这里 `"voice"` 是 `ScriptGateNode` 返回的路由值，`"human_review"` 是实际目标，不用改 `nodes/gates.py` 中的节点实现。

**替换原成功分支，不要追加一条普通边**；同时保留原来的错误分支，否则配音和人工审核可能同时执行。默认人工审核的注册配置是：

```python
self.add_human_review(
    graph, "human_review",
    stage="script",
    title="文案人工审核",
    confirmation_requirements=("文案表达与事实来源", "截图及素材与文案一致"),
    next_node="voice",
)
```

## 增加第二个审核点：分镜检查后、剪辑前

在 `graph.compile(...)` 前注册：

```python
self.add_human_review(
    graph, "storyboard_human_review",
    stage="director",
    title="分镜人工审核",
    confirmation_requirements=("音画对应", "关键镜头表现力", "字幕与素材可读性"),
    next_node="editing",
    min_note_length=10,
)
```

替换原 `timeline_gate` 条件边：

```python
graph.add_conditional_edges("timeline_gate", self.route, {
    "editing": "storyboard_human_review",
    "await_input": "await_input",
    "end": END,
    "reviewers": "reviewers",
})
```

这会审核进入剪辑的分镜。单独“生成分镜”的 `end` 分支和只审核已有视频的 `reviewers` 分支保持各自行为；要审核它们，分别选择合适的后续节点，避免单独生成分镜时意外启动渲染。

`stage` 使用 `materials`、`script`、`voice`、`director`、`render` 或 `review`；素材审核示例见 [素材节点](videoagents-materials.md)。审核节点名称需唯一，`next_node` 要是图中已有节点。也可以指定 `END`，此时确认后结束本次执行，任务回到 `DRAFT`，不会留在运行中或标记发布通过。

## 人工决定与前端

| 决定 | 行为 |
| --- | --- |
| `confirm` | 核对当前版本、文件与对齐元数据，保存说明，走 `continue` 到 `next_node` |
| 说明过短 | 生成新待办，走 `retry` 回到同一审核点，继续等待 |
| `revise` | 保存返工说明，回到 `DRAFT` 并结束本次执行；手动修改、保存新版本后再启动 |
| `cancel` | 保存决定，任务变为 `CANCELLED` 并结束 |

React 工作台在所有页签上方显示阶段审核卡，包含检查清单、说明、核对勾选和三个决定按钮，无需已有成片或最终审核结果。默认说明至少 10 字，可通过 `min_note_length` 调整到 0–3000。审核决定保存为 `stage_review` JSON 产物，包含节点、阶段、版本、待办 token、输入指纹、决定与说明。

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

当前应用顺序处理一个待办，可串联多个审核节点，暂不支持并行分支同时待审。改图后重启 worker，使后续执行使用新编排；已暂停的运行应保留原节点名称和检查要求，改变待审要求时重新发起执行。旧回复不能放行新内容。

官方说明：[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)。
