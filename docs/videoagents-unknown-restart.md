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
自动复用旧稿的捷径，也不启动付费调用。配音、剪辑阶段、活动命令、SUBMITTING、
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

## 保留联合批准与真实音频，仅重做摄影

摄影 `NEEDS_INPUT / director / kind=input` 待办绑定的 `llm:director / UNKNOWN` 可用
`--director-only`。必须针对该次未知提交取得可能用量确认；修复代码或延长超时不代替确认。

```powershell
videoagents restart-unknown <job_id> --operation-id <当前摄影UNKNOWN操作ID> --acknowledge-possible-usage --director-only --note "用户明确接受旧摄影提交可能已有用量，授权新尝试；保留文案与真实音频，使用合适真实素材，组件套补画面表达缺口并明确标示示意"
videoagents status <job_id>
videoagents run <job_id>
```

`--note` 同时是正式授权说明和最新摄影要求，最多3000字符，并进入摄影调用指纹。
不得同时提供 `--brief`、`--rebuild-script`、`--materials-only` 或素材采集要求；要求修改文案、
配音或语速时此入口拒绝。它只保存一次新版 DRAFT；旧 UNKNOWN、旧文件与注册记录不改变，
同一操作与相同请求重复执行不升版本、不排队、不再次提交。

新版保留原 Brief 与文案正文、当前全部素材、选用真实音频和 alignment、voice_guidance、audio_report，
以及真实文案门/联合门回执与原飞书 Base。仅 Script 的 revision 前进，旧 timeline、摄影方案、
逐镜图片和剪辑衍生引用清空，不创建任何新版 confirm。授权保存原 Job、素材 metadata 与文件依据；
正常 `run` 再验证这些依据，经 audio_gate 直接进入摄影，跳过编剧、素材与配音，仍停逐镜整包人工审核。

历史联合门 confirm 通常不含完整 subject。系统保留原 revision、Brief、Script、视觉素材、源正文、
研究产物、素材审计、素材取舍后的顺序及原 metadata，尝试排除已证明匹配的有效音频和已知配音输出，
然后与真实联合回执的 dependency/policy 指纹精确比较。人审前已导入的音频保留在候选投影中。
存在 confirm 本身不构成批准继承；不能还原指纹、最新联合决定不是 confirm、原稿/音频不匹配、
缺文件、hash 改变、活动命令、错 provider/操作/revision 或其他当前未决提交都会阻断。

摄影上下文仅恢复当前有效画面与最终证据结论及新 note；拒绝素材不回流，恢复台账和审核流水不交给模型。
素材前批准通过既有补采/取舍链验证；再次出现摄影 UNKNOWN 时须再针对新操作明确授权。

操作者可使用纯只读预检函数，成功只返回依据，不授权、不改 revision、不调用模型或配音：

```python
from videoagents.services.director_recovery import verify_director_recovery_inputs

proof = verify_director_recovery_inputs(repo, repo.get_job(job_id))
```

预检会读取登记文件、使用本机 ffprobe 检测音频时长，并验证真实批准指纹；无法证明历史输入时如实报冲突。

### 延续已完成但校验未通过的摄影候选

`--director-only` 如有同任务已保存的摄影 COMPLETED 候选，且该候选尚未进入有效 timeline，
会沿摄影恢复的 `previous_job` 输入链发现来源。系统使用正常 `state_context → DirectorNode.plan`
构造原初次摄影请求，以与 `JsonModel.call` 相同的纯指纹函数精确复算原 `input_hash`。
同时核验已审文案与 Brief、素材文件/hash/metadata、原音频/alignment、批准链、摄影模型及推理配置，
并绑定源版本 UNKNOWN 修复提交。保存这些依据不会改变旧 COMPLETED 或 UNKNOWN。

新版正常 `run` 把这份候选的全部镜头作为修复底稿，给摄影模型明确校验问题；要求保留未涉及问题的
镜头，确需改变相邻边界或发现新问题时说明受影响镜头与理由。模型仍返回完整方案，之后照常执行完整
契约、素材关联、阅读时长、组件与媒体覆盖校验，渲染逐镜 PNG 并停整包人工审核。候选不会被复制成
已通过 timeline，不恢复逐镜确认，也不渲染成片。

无完成候选时保留原摄影逻辑；存在候选但源输入指纹不能精确证明时阻断。初次请求复算不支持任意历史
CLI 对话或含修复 extras 的后续请求重建。多次摄影独立恢复优先沿用已证明候选，不让较晚未经证明的
修复响应替换它；同一版本内的正常 `resume` 仍可按原节点逻辑使用最新完成回执继续修复。已接受的旧
timeline 继续使用原反馈/重做规则，不属于本桥接范围。模型保留无问题镜头是输入要求，本接口不新增
强制逐字段冻结或局部 patch 契约，仍须逐镜审阅实际修改。校验可能先报告第一个问题，修复后仍可能
发现新的问题，不能宣称旧候选其余镜头已全部验证。

以下入口只读返回可用性、来源操作/revision、镜头数量、指纹及已发现问题，不输出候选业务正文：

```python
from videoagents.services.director_recovery import verify_director_candidate_continuation

proof = verify_director_candidate_continuation(repo, repo.get_job(job_id))
```

它不授予可能用量授权，不升版本、不调用模型、不修改数据库或生产状态；当前版本 UNKNOWN 屏障保持。
Claude CLI 使用 `--no-session-persistence`，本功能是保存产物的阶段接续，不是恢复已退出 CLI 的内部会话。
