# 节点代码与编排入口

角色实现统一放在 `videoagents/nodes/`。一个节点类同时负责本阶段的业务、状态更新、保存产物和返回路由，直接注册进 LangGraph。`videoagents/graph/video_graph.py` 负责注册、连线、checkpoint 和命令恢复。

```text
videoagents/
├─ nodes/
│  ├─ materials.py      MaterialsNode：跨平台研究、来源、图片、截图与冻结研究包
│  ├─ screenwriter.py    ScreenwriterNode：读取素材包、初稿、讨论改稿和保存
│  ├─ script_reviewer.py ScriptReviewerNode：文案审查、修改建议和讨论路由
│  ├─ voice.py           VoiceNode：配音指导、真实音频和实测对齐
│  ├─ director.py        DirectorNode：按音频时间生成和保存分镜
│  ├─ editing.py         EditingNode：剪辑指导、Remotion 渲染和产物登记
│  ├─ reviewers.py       ReviewersNode：检查成片、来源、对齐和用途
│  ├─ gates.py           ScriptGateNode / AudioGateNode / TimelineGateNode / ReviewGateNode
│  ├─ human_review.py    HumanReviewNode：可自行接入的阶段人工审核
│  ├─ await_input.py     AwaitInputNode：等待补充输入、最终人工复核和发布包
│  ├─ clear_tools.py     ClearToolsNode：每个模型角色完成后清空工具历史
│  └─ common.py          共用的版本/取消校验、阶段状态、讨论保存和输入请求
├─ graph/
│  └─ video_graph.py     注册节点、条件边、执行与恢复
├─ providers/            CLI 模型、搜索、字节配音和对齐接口
├─ services/             任务版本、导入和设置
├─ contracts/            Pydantic 数据契约
├─ storage/              持久化
├─ tools/                来源、媒体和时间轴工具
└─ state.py              节点共享的 VideoState
```

## 读取或修改一个节点

以编剧为例，从 `ScreenwriterNode.__call__(state)` 开始读：

1. `start_stage()` 先检查数据库中的版本和取消状态，将 `VideoState` 中的业务输入差异保存并补齐上下文，然后将阶段标记为运行中。
2. 读取素材节点冻结的研究包和本次执行冻结的讨论配置。`write_script(job)` 生成初稿；开启讨论时，后续轮次通过 `rewrite(job, discussion)` 读取审查反馈并改稿。CLI 模型调用也在这个文件里。
3. 保存文案及 JSON 产物，用 `state_context()` 返回包含当前业务数据的上下文；开启讨论时路由为 `script_reviewer`，未开启时为 `script_gate`。
4. 能力或输入不足时，`request_input()` 保存待办并返回 `{"route": "await_input", ...}`。

其他角色也从 `__call__` 开始读。`collect()`、`prepare_audio()`、`plan()`、`render_video()`、`review()` 是所在节点内部的业务步骤，没有独立 Agent 类。当前起点是 `START → materials → clear_materials → screenwriter`，平台清单和交接见 [素材节点](videoagents-materials.md)。

各阶段数据集中在 `VideoState`，自定义节点可以直接读文案、素材、分镜、审核及人工记录，并返回部分业务字段或 `extras`。字段、增量交接、持久化和恢复规则见 [通用上下文](videoagents-context.md)。

## 在图中注册和连线

```python
graph.add_node("screenwriter", ScreenwriterNode(repository, self.service))
self.add_cleanup_edge(graph, "screenwriter", {
    "script_reviewer": "script_reviewer",
    "script_gate": "script_gate",
    "await_input": "await_input",
})
```

`ScreenwriterNode(...)` 创建节点对象；`add_node` 把对象注册为 `screenwriter`。工作流到达它时，LangGraph 调用对象的 `__call__(state)`。返回的增量更新共享状态，先进入 `clear_screenwriter` 清理工具历史，然后 `self.route(state)` 读取 `route`，条件边再选择下一个节点。

素材、编剧、文案审查、配音、导演、剪辑、审核七个角色均使用 `add_cleanup_edge()`；检查和等待节点沿用原条件边。自己编排角色后的人工审核时，修改 `add_cleanup_edge()` 的路由映射，保留清理节点。例如让 `script_gate` 路由先进入自定义人工审核；不要另加一条绕过清理的角色条件边。

调整业务去对应的节点文件；调整顺序和分支去图文件。编剧与文案审查的交替、轮数和记录见 [文案讨论](videoagents-script-discussion.md)。插入人工审核仍使用 `add_human_review()`，示例见 [人工审核编排](videoagents-human-review.md)。原有节点和恢复 API 保留；已经执行到文案后阶段的旧 checkpoint 不会补做新讨论，启动新执行后按新配置进入。

## 修改模型提示词

七个模型角色的提示词独立保存在 `videoagents/prompts/*.md`；节点文件顶部保留兼容的 `PROMPT` 常量，编剧另保留 `REWRITE_PROMPT`。共享创作标准位于 `shared-style.md`，导演的组件参数示例由加载器注入；动态 schema 只限制当前稿件的段落 ID、当前任务可用的图片路径等运行条件。

例如编剧的模型调用：

```python
value = self.model.invoke(
    state, "screenwriter", PROMPT,
    fields=("brief", "research", "assets"),
    output_schema=Script.model_json_schema(),
)
```

`JsonModel` 负责 Codex/Claude CLI 的结构化调用及提交台账。节点负责选择 state 输入、校验最终产物、保存和路由；前后角色通过 state 交接。工具过程留在审计文件中，交接清理的规则见 [通用上下文](videoagents-context.md#agent-的输入与最终输出)。

## 本次精简范围与验证

重构前先运行现有 200 项 Python 回归。精简范围是分离的 Agent 类、图中的 `node_*` 包装和动态 `getattr` 注册；先合并角色，再迁移检查/等待节点，最后修正调用、测试和说明。

保留的恢复行为都有业务依据：冻结来源防止重放时再次调用模型，UNKNOWN 台账防止重复提交，人工补充输入用于缺少真实素材或能力的情况，人工审核校验及记录用于恢复同一版本的决定。这些行为不属于要删除的包装逻辑。

重构后新增 23 项节点独立调用及版本/取消回归，全量 223 Python、51 React 测试通过。Ruff、契约一致性、React typecheck/build 通过；原有人工审核及崩溃恢复测试继续通过。服务已重新加载节点实现，本次未执行实际模型、配音或渲染调用。

五角色业务方法与原实现的 AST 语句对比一致。独立审查无可行动问题，定向回归、Ruff 和 Python 编译检查通过；不可用的 LSP/AST 搜索工具未作为完成证据。
