# VideoState 通用上下文

## 本次改造计划

目标：每个节点只接收 `VideoState`，从中读取任务和上游结果，返回上下文增量；文案、讨论、素材、音频对齐、分镜、产物、审核及人工意见可以在一个结构中找到。数据库继续用于持久化、版本/取消检查及提交台账；文件保存实际媒体，上下文保存元信息和受控引用。CLI 对象、数据库连接及密钥不进入 checkpoint。

1. 先运行现有回归，锁定讨论、暂停恢复、人工审核、取消和 UNKNOWN 行为。
2. 扩展 `state.py` 的业务字段，并提供公开配置、来源/指导记录、音频、渲染及人工记录；用 `extras` 承载自定义 JSON 数据。
3. 图执行入口构造完整上下文；已有精简 checkpoint 在节点入口补全。节点从上下文构造现有校验所需的 Job 数据，完成后统一返回最新上下文。
4. 节点正常交接使用上下文的数据；SQL 比 checkpoint 更新时先恢复已提交的结果，防止崩溃恢复重复调用。任何版本变化和取消仍先拒绝。
5. 补充真实 LangGraph checkpoint/恢复及自定义节点数据交接回归，运行后端测试、静态检查、共享契约一致性检查，并进行独立审查。

改动范围：`videoagents/state.py`、`nodes/`、图执行入口和相关测试/说明。保留 HTTP Job 契约、原节点名、边及 provider 调用方式，不新增依赖。

## 上下文的内容

`videoagents/state.py` 定义一个扁平的 `TypedDict`。运行时就是普通字典，字段值都是 JSON 数据。所有节点仍只有一个入口：`__call__(state: VideoState)`。

| 字段 | 内容 |
| --- | --- |
| `brief` | 主题、原始文案、受众、平台、用途、视频尺寸和来源链接 |
| `script`、`script_discussion` | 当前完整稿件，每轮稿件、审查意见、回应和讨论状态 |
| `research` | 素材节点最终研究包：主题歧义、来源正文、图片/截图引用及资料局限；不含工具调用过程 |
| `assets`、`asset_metadata` | 素材清单、受控 URL、hash、来源、许可、音频时长和对齐元信息 |
| `audio`、`audio_asset_id` | 当前音频素材及其 ID，音频文件通过 URL 引用 |
| `alignment`、`duration_seconds`、`audio_report` | 音频字幕时间轴、实测时长和核验报告 |
| `voice_guidance`、`editing_guidance` | 模型生成的朗读和剪辑建议 |
| `timeline` | 镜头、帧区间、字幕、音频路径和 Remotion 参数 |
| `artifacts`、`artifact_metadata`、`render` | 当前业务产物，预览、成片、封面、字幕和发布包引用及核验元信息；不携带原始供应商回执 |
| `review` | 成片技术与内容检查结果，以及最终人工确认状态 |
| `pending_input`、`human_decision`、`human_reviews` | 当前人工待办、最近一次回复、阶段/成片人工记录 |
| `settings` | 七角色模型、素材工具与制作配置的公开快照，不包含 API Key 或令牌 |
| `metrics` | 当前版本的调用预算计数；外部操作台账只保存在数据库，不进入 Agent 共享 state |
| `extras` | 自定义节点的数据，例如选题评分、讨论摘要、发布标题候选 |

任务身份、版本、执行 ID、路由、阶段、进度和 checkpoint 恢复字段也在同一上下文里。尚未生成的业务对象为 `None`，集合为空列表或字典。节点应通过条件检查处理尚未完成的上游步骤。

## 自己增加节点

例如在编剧前加入一个节点，修改受众并记录选题分析：

```python
from videoagents.state import VideoState


def audience_analysis(state: VideoState) -> dict:
    brief = {**state["brief"], "audience": "第一次接触这个话题的观众"}
    return {
        "brief": brief,
        "extras": {"audience_analysis": {"opening": "先从日常例子解释"}},
    }


graph.add_node("audience_analysis", audience_analysis)
graph.add_edge(START, "audience_analysis")
graph.add_edge("audience_analysis", "materials")
# 替换原先 START -> materials 的边，再 compile。
```

后面的节点可以直接读取 `state["brief"]` 和 `state["extras"]["audience_analysis"]`。需要改文案时，返回完整 `script` 字典，保留当前 `revision`；分镜也必须对应当前 `job_id` 和 `revision`。嵌套业务对象采用整体替换，例如修改受众时先展开原来的 `brief`。

每个内置节点先调用 `current_job()`（阶段执行节点通过 `start_stage()` 调用），保存上游上下文中的合法输入差异，再执行本阶段。节点返回 `state_context()` 生成的完整上下文，因此自定义节点可以读取已保存的文案、素材或结果，无需自行查数据库。自定义节点也可以只返回局部更新，由 LangGraph 合并进共享上下文。

`extras` 使用浅合并：`{"score": 80}` 不会删除之前的 `audience_analysis`；`{"score": None}` 会把 `score` 设置为 `null`。嵌套对象仍整体替换。值只接受字符串、有限数字、布尔值、`None`、列表和字符串键字典；bytes、`Path`、模型客户端、数据库连接、循环引用和 `NaN` 都会被拒绝。文件路径需要使用字符串，媒体通过已登记的素材/产物引用传递。

新增固定顶层字段时，在 `VideoState` 中声明；临时扩展放入 `extras`。LangGraph 只持久化已声明的状态字段。

## Agent 的输入与最终输出

所有调用大模型的角色都使用 `JsonModel.invoke(state, role, PROMPT, fields=...)`。`fields` 选择当前角色需要的最终业务字段，输入来自同一个 `VideoState`；不把 `Job`、查询连接、聊天消息或调用回执传给模型。固定提示词独立保存在 `videoagents/prompts/*.md`，对应 `nodes/*.py` 在导入时组合成兼容的 `PROMPT` 常量；编剧改稿另有 `REWRITE_PROMPT`。

素材 → 编剧读取 `research`、`assets`；编剧 → 文案审查读取 `script`、`script_discussion`；审查 → 编剧读取最后一轮 `critique` 再改稿。讨论历史是各轮最终产物，因此保留。配音、导演、剪辑、成片审核同样从 state 选择业务输入，模型返回的最终 JSON 经契约校验、保存后再更新 state。

TradingAgents-astock 的分析师结束后走 `Msg Clear <角色>`：用 `RemoveMessage` 清空 `messages`，保留 state 中的最终报告。本项目 CLI 返回最终 JSON，没有 LangChain 消息通道，因此不用 `RemoveMessage` 或占位消息；在七个模型角色后各注册 `clear_<角色>`，执行 `ClearToolsNode` 后才按原 `route` 路由。文案每次改稿、审查也都经过清理。

`state_context()` 在正常返回和恢复时使用 `clean_handoff()`，模型输入再使用同一清理规则。递归删除 `messages`、`tool_calls`、`tool_results`、`tool_trace`、`intermediate_steps`、`search_results` 等执行历史容器（完整保留字段名见 `state.py` 的 `TOOL_HISTORY_FIELDS`）。`extras` 的合并 reducer 同样清理合并结果，防止省略字段时保留旧工具记录。这些字段名不用于自定义最终业务数据；稿件正文、讨论各轮最终意见、来源和媒体引用继续保留。顶层运行记录及素材研究包中的 `tools`、`operations` 按位置排除；`extras.tools` 可表示最终软件清单、`extras.operations` 可表示制作步骤，不会因同名被删除。自定义节点的执行轨迹统一使用 `tool_trace` 等保留容器，不得伪装为业务清单。

CLI 的事件流不进入 state；研究中的原始工具记录只保存在审计文件，失败转换为资料局限。素材审计及原始清单的产物引用、元信息也不传给下一个角色。研究交接包保留正文、出处、真实视觉素材及 `limitations`，不会把搜索摘要当作已核验知识。数据库的 UNKNOWN 提交台账与私有审计文件保留，供去重和排障；清理节点不删除它们。

自定义节点同样只把最终业务结果放入 `extras`，不要将工具消息、原始 API 响应或调用轨迹存进去。素材节点直接启动 Codex CLI，模型按技能选择检索工具，Python 接收、验证和冻结最终资料；没有单独的规划或固定工具分支。素材审计与原始清单产物不进入下一个 Agent 的共享上下文，其余角色保持无工具的结构化调用。

## 数据交接、持久化与恢复

正常交接允许节点修改 `brief`、`script`、`timeline`、`assets`；这些字段会通过原 Pydantic 契约校验并保存。遗漏字段使用当前数据库值；显式 `script=None` 或 `timeline=None` 表示清除。修改输入时，旧分镜、视频及审核引用按依赖关系失效，避免新稿仍使用旧成片。

传入 `assets` 时，素材必须已经登记到当前任务：核验产物归属、声明的 URL/hash/大小/MIME 及真实文件内容，媒体路径必须位于当前任务目录。音频还需要来源及有限正数的实测时长元信息；对齐仍由配音和音频检查节点核验。不能仅构造一个素材字典来代替上传或登记文件。

`status`、`revision`、任务身份、事件水位、待办 token、已登记产物和审核凭据由现有执行/持久化流程管理。自定义节点不能通过返回这些字段伪造完成或发布通过。已有文案讨论轮次或人工待办时，内容已被冻结；需通过工作台保存新版本，再重新执行。

数据库每次保存都会更新 `latest_event_id`。如果数据库比 checkpoint 更新，节点恢复已提交结果，避免旧上下文覆盖已生成稿件或重复调用模型。业务差异必须在阶段/暂停写入前保存；提交还校验事件水位，拒绝并发变化。旧精简 checkpoint 会在下一个内置节点入口补全。取消和版本失效始终先检查。

人工审核仍使用原来的 `pending_snapshot`、interrupt ID/token 和内容指纹绑定。新的数据库待办不会替换旧 checkpoint 的原回复目标。`execute()` 返回包含最新待办的 JSON 上下文；LangGraph 自身附加的运行时 `Interrupt` 对象不放入 `VideoState`。

配置快照通过 `SettingsService.public()` 获取。角色真实调用仍按原规则读取当时的模型配置；讨论开关和最大轮次继续按本次执行冻结。真实媒体留在文件系统，凭据留在设置服务，运行时连接留在节点对象中。
