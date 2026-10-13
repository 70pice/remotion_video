# 明确授权后重新执行 UNKNOWN 模型任务

模型提交后超时、断流或响应过大可能已经消耗额度；修复传输或修改设置不会解除同角色、同版本的
UNKNOWN 屏障。能取得时核对供应商记录与已有产物；无法确定是否计费时，只有用户明确接受可能已
消耗额度并授权新的尝试，导演才可以通过以下正常入口保存同一个视频的新 revision：

```powershell
videoagents restart-unknown <job_id> --operation-id <当前UNKNOWN操作ID> --acknowledge-possible-usage --note "用户明确允许再次提交，接受上次可能已消耗额度" --brief brief.json
videoagents status <job_id>
videoagents run <job_id>
```

`--brief` 可省略，省略时保存当前完整 Brief；提供时使用该 JSON 的完整 Brief。授权说明必须非空，
`--acknowledge-possible-usage` 必须明确提供。`restart-unknown` 只保存新版 DRAFT，不执行模型、配音
或渲染；随后使用 `run` 才会进入正常图流程。文案与素材人工审核、逐镜人工审核仍须分别回答。

默认只接受编剧 `NEEDS_INPUT / script / kind=input` 待办所绑定的 UNKNOWN 模型操作，校验任务 ID、
revision、阶段与编剧角色。素材阶段的 UNKNOWN 默认仍被拒绝；如果需要弃用已完成文案，重核
来源并重新采集素材，取得用户对重做文案与素材、可能再次消耗额度的明确新授权后，增加
`--rebuild-script`：

```powershell
videoagents restart-unknown <job_id> --operation-id <当前素材UNKNOWN操作ID> --acknowledge-possible-usage --rebuild-script --note "用户明确授权重做编剧与素材，接受旧提交可能已消耗额度" --brief brief.json
```

只接受素材 `NEEDS_INPUT / materials / kind=input` 且 provider 为 `llm:materials` 的 UNKNOWN；此选项
始终清空旧稿和当前研究结果引用，保存新版 DRAFT，后续 `run` 从编剧开始再进入素材。它不提供
自动复用旧稿的捷径，也不启动付费调用。配音、摄影、剪辑阶段、活动命令、SUBMITTING、
其他未决操作、普通缺配置待办和人工审核门仍被拒绝。配音供应商的 UNKNOWN 应检查已有真实音频
或供应商回执。

版本更新、授权事件和授权回执在一个 SQLite 事务中保存。旧操作仍为 UNKNOWN，不被修改成
REJECTED，也不表示已完成供应商对账；旧 checkpoint、事件及产物文件和注册记录保留。事件保存
操作 ID、用户授权说明、源/目标 revision 及旧产物 ID/路径；`job_inputs` 的
`authorized_model_restart:<operation_id>` 保存旧待办、旧/新 Brief 快照和旧稿件快照。编剧的新版本
清空未完成稿件与当前文案产物引用，由正常编剧节点重新产出。`rebuild_script` 写入事件与授权回执，
旧已完成文案也保存快照、注册记录及实体文件，不再作为新版稿件使用。

同一操作 ID 与相同授权说明、Brief 和 `rebuild_script` 参数重复执行只返回已保存的任务，不再创建
revision；改变授权说明、Brief 或此选项会报冲突。重发时保持原参数，包括是否提供 `--brief`。
未指定此选项时保留旧授权回执的幂等指纹兼容。接受风险的授权和正常运行分开，
重复授权命令不会自动重放付费提交。

## 保留已审口播，仅重采素材

用户明确要求保留已审文案并重新采集素材时，可选择互斥的 `--materials-only`。采集要求与授权说明
分开保存，不通过修改 Brief 触发编剧，也不篡改已审口播：

```powershell
videoagents restart-unknown <job_id> --operation-id <当前素材UNKNOWN操作ID> --acknowledge-possible-usage --materials-only --note "用户明确授权新的素材尝试，接受旧提交可能已有用量" --materials-note-file materials-requirements.md
videoagents run <job_id>
```

`--materials-note-file` 读取 UTF-8 文本，也可用 `--materials-note` 直接传入；要求非空、最多30000字符。
不能与 `--rebuild-script` 或 `--brief` 一起用。只接受当前素材 UNKNOWN，沿用现有活动命令、角色、
版本、其他未决操作等拒绝边界。授权命令仍只保存新版 DRAFT，不排队、不调用模型。

进入新版前，验证原文案人工确认回执、原稿实体、读取审计及已登记来源的真实文件与 hash。
原稿需与已审内容一致，带旧素材引用的稿件不能清空旧素材后直接沿用。本入口保存原批准依据和
源 Job 快照，没有生成新版“通过”回执；仅改变 Script 的 revision，保留口播、来源与完整 Brief。
新版清空素材清单与下游产物引用，在独立研究目录重新采集，旧文件与 UNKNOWN 台账保留。

旧文案门没有逐来源文件归属清单，因此研究根目录现有 `.txt` 的额外快照标记为
`restart_time_research_root_texts`：它用于授权后复验字节和文件是否缺失，不证明历史编剧来源集合
完整，也不声称原人审已绑定这些正文。不会扫描失败素材子目录或 CLI 临时凭据目录。

正常 `run` 仅在该显式授权版本从素材开始。采集要求只交素材模型，并参与模型调用及研究缓存指纹；
新的画面来源只记入素材研究清单，不扩写已审 Brief。原稿、批准回执或快照发生变化会在调用前停止。
采集后仍停在新的“文案与素材人工审核”，不继承旧联合门或逐镜门的批准，不进入配音。
同操作 ID、同说明及同采集要求重发幂等；改变范围或要求会报冲突，不自动发起第二次素材尝试。
