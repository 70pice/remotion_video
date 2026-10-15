# UNKNOWN 原因与代码核对

2026-10-15。任务 `08e74bed03e94c6e903c89f7f2fbea64`。

## 先回答修复状态

最新 r11 调用失败的上游根因尚未查明，不能宣称这次调用已经修好或保证不再发生。已修好并通过回归的是错误诊断丢失：之前只保存错误外壳和计数，现在保存回执确实报告的固定错误类型、HTTP 状态、终止原因和可识别的连接/流错误。旧记录没有的内容不能补写为事实。

修复代码位于独立维护工作区 `D:\remotion_video_unknown_repair_20261015`，分支 `maintenance/unknown-classification-20261015`，HEAD `f1a82d11a6fd68dadafb50624a559bf63fb19317`。包含上一轮 `cc4fb8e` 的错误类型修复、`ac5c32d` 的五倍超时支持及更早的排版修复。视频任务分支只保存本次证据和说明，共性代码没有混入任务分支。

## 上一轮实际发生了什么

操作 `a290785969554baab4bb2cebbbcd9c42`，r11，摄影 `llm:director`，Claude Code CLI / `glm-5.3[1m]` / xhigh。SQLite 原因原样如下：

```json
{
  "reason_code": "cli_nonzero_exit",
  "exit_code": 1,
  "response_json_shape": "absent",
  "stderr_tail_bytes": 78,
  "stdout_bytes": 1701,
  "stdout_shape": "claude_error_result",
  "subtype": "unknown"
}
```

- 确认 Claude 子进程退出码为 1，stdout 是错误结果外壳，未取得可检查的业务 JSON。这不是引擎 `cli_timeout` 分支；当时摄影等待上限为 3600 秒。
- 任务事件在北京时间 2026-10-14 23:39:56 进入 RUNNING，2026-10-15 00:11:06 进入 NEEDS_INPUT。这是任务事件区间，不是精确的子进程计时；之前“约32分钟”的口头概述不应当作精确运行时长。
- `response_json_shape=absent` 也可能是字段类型不符，不能据此证明整个 `structured_output` 字段不存在。
- 当时的诊断代码把除 `unrecognized_model` 外的类型统一投影为 `unknown`，没有保存错误详情。它可能丢弃有效分类，但不能反过来断言本笔原始 subtype 一定属于某个已知类型。
- 本机对应时段没有找到可恢复的 Claude 原始回执；默认 debug 目录不存在，projects/sessions/telemetry/daemon 没有存活的匹配时段日志文件。已检查任务事件、操作、登记产物及历史安全审计，没有找到 r11 原始错误正文。这里只能说明这些已查位置没有找到证据。
- 因此，不能确定是网络、接口、结构化生成、模型或其他错误；不能把剩余额度查询正常当成这次调用成功或未计费的证明。

两种 `unknown` 含义不同：回执里的 `subtype=unknown` 是原诊断没有保留具体分类；操作 `status=UNKNOWN` 是模型已可能提交，但没有可用结果，无法排除消耗用量。`llm.py` 因后者阻止重复请求，不会把它改成成功来解除阻断。

## 本任务全部九笔 UNKNOWN

下表来自本轮 SQLite `mode=ro / query_only` 查询，不是猜测。完整 operation_id、模型、原因散列和当前事件见 [只读清单](unknown-causes-readonly-20261015.json)。相同原因码不代表上游根因相同。

| revision / 阶段 | operation_id | 已保存原因 | 现有证据能说明什么 |
| --- | --- | --- | --- |
| r1 编剧 | `560106d6ee24433e8be3be0f6bf10e6a` | `cli_output_limit` | 输出触及本地安全上限；历史共性修护已分开研究流累计预算和单事件/最终结果预算，旧操作仍 UNKNOWN。 |
| r2 素材 | `2013f7e0f2be44a8b6613f2718750429` | `unexpected_cli_event` | 收到当时解析器不接受的事件；原始事件类型未保留。后来补充三种官方合法元数据兼容，但无法证明它们就是本笔触发类型。 |
| r3 编剧 | `515a815f0a5e4baf85e0230e52168023` | `cli_timeout` | 引擎在配置期限内没等到有效完成；慢或卡住的更深原因未保留。 |
| r4 素材 | `c34539df84044a7cb5eb6cbe86c3ff32` | `PermissionError` | Python 权限异常类型；该台账没有具体文件/系统调用栈，不能解释为供应商 API 权限不足。历史收尾代码有修护，不足以证明本笔精确根因。 |
| r7 摄影 | `c2ee429eee8940b6ab47e7a2bc5e8967` | `cli_timeout` | 到本地等待上限，没有可用完成回执；不是已证实的供应商超时码。 |
| r8 摄影 | `2cb7f646bd224feb88565a9b7c2af96f` | `cli_timeout` | 同上，具体卡住环节不明。 |
| r9 摄影 | `0b7c7172b84c49a7b3b49a88b785fb50` | `invalid_cli_output` | CLI 输出解析路径失败，未登记修复结果；历史有模型提示，但不能据此认定供应商拒绝模型。 |
| r10 摄影 | `3e16804dab4444beaee599634f0bea95` | `cli_nonzero_exit` | CLI 非零退出；这笔旧记录未保存退出码和具体错误结果。 |
| r11 摄影 | `a290785969554baab4bb2cebbbcd9c42` | `cli_nonzero_exit` | 已确认退出 1、Claude 错误结果外壳；具体上游错误丢失，仍无法还原。 |

历史修护依据在 [任务历史](README.md)，本表不把后来的成功或相似回归测试当成旧事故根因证明。旧 UNKNOWN 记录留存不表示这九笔仍在执行，也不表示每个历史版本都阻塞当前版本。

## 亲自看代码的顺序

以下位置全部指向新维护工作区，避免误看任务分支旧代码。

1. [cli_runner.py:896](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:896)：`process.wait` 后遇到非零退出，生成 `cli_nonzero_exit`。同文件 858、867、906、925 附近分别是超时、输出上限、无完整结果、解析异常。这是失败触发层。
2. [cli_runner.py:517](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:517)：`_failure_diagnostic` 构造安全诊断；[同文件:489](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:489) 精确匹配标准错误头和固定传输错误。新字段必须有回执证据才出现，不保存任意正文。
3. [cli_runner.py:171](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:171)：`CliFailure.hint` 将诊断映射为固定中文解释；状态、连接症状、终止原因、subtype 按明确优先级显示。固定映射在同文件 47 附近，完整边界见 [诊断规则](D:/remotion_video_unknown_repair_20261015/docs/cli-failure-diagnostics.md)。
4. [llm.py:206](D:/remotion_video_unknown_repair_20261015/videoagents/providers/llm.py:206)：`status = "REJECTED" if not exc.submitted or exc.rejected else "UNKNOWN"`，保存失败原因并暂停。218 附近是其他异常只保留异常类名的分支；[同文件:129](D:/remotion_video_unknown_repair_20261015/videoagents/providers/llm.py:129) 是禁止未决操作重复调用的屏障。
5. [test_cli_models.py:170](D:/remotion_video_unknown_repair_20261015/tests/videoagents/test_cli_models.py:170)：真实本地模拟子进程验证错误码、脱敏与中文提示；189 附近验证正常 JsonModel → SQLite UNKNOWN → 同操作禁止重放；257、282 附近验证非错误字段与 `completed` 不被误归因。

用 Git 查看完整修改：

```powershell
git -C D:\remotion_video_unknown_repair_20261015 show f1a82d1 -- videoagents/providers/cli_runner.py tests/videoagents/test_cli_models.py docs/cli-failure-diagnostics.md
git -C D:\remotion_video_unknown_repair_20261015 diff da5f3c7..f1a82d1 -- videoagents/providers/cli_runner.py videoagents/providers/llm.py
```

第一条看本轮补充，第二条包含上一轮错误类型修复。它们只读，不触发模型调用。

## 本轮具体修了什么

- 原有官方失败 subtype、零退出错误结果与中文提示的修复继续保留。
- 兼容错误详情位于 `errors` 列表/单字符串、错误 `result` 文本，以及可选 `api_error_status` / `terminal_reason` 字段；所有 stdout 错误详情要求 `is_error is True`。
- HTTP 状态必须来自实际整数状态或标准 `API Error:` 头；不根据 `error.type` 推测 HTTP，不把 HTTP 429 直接说成余额不足。
- 可识别的连接、超时、流关闭、流格式及 JSON 截断提示只保存固定症状代码；这仍不足以定位本机还是供应商出了问题。
- 非错误业务字段不能提升为失败原因，`completed` 不覆盖更具体的失败 subtype，单独的 `End` 不归因。
- 保留 UNKNOWN 状态和重复提交屏障；没有改模型、请求指纹、schema、审核标记或旧台账，没有自动重放。

官方字段及错误形式依据见维护工作区的 [诊断规则](D:/remotion_video_unknown_repair_20261015/docs/cli-failure-diagnostics.md)。该资料用于设计读取路径，不是 r11 旧事故的证据。

## End / DONE 为什么不能当成完成

本次外层命令 `15a0ac7bf45f49f39ae805066d33ed03` 为 `DONE`，任务却是 `NEEDS_INPUT`，操作为 `UNKNOWN`。图在输入门暂停后正常返回，[worker/runner.py:31](D:/remotion_video_unknown_repair_20261015/worker/runner.py:31) 会完成本次命令；[main.py:52](D:/remotion_video_unknown_repair_20261015/videoagents/main.py:52) 仅在任务为 FAILED 时返回 1，因此外层退出 0 也不证明模型成功。不要把内层 Claude 的退出 1 与外层命令退出码混为一谈。

代码中 LangGraph 的 `END` 是图执行结束的哨兵，例如 [video_graph.py:115](D:/remotion_video_unknown_repair_20261015/videoagents/graph/video_graph.py:115)，不是供应商错误原因。已查记录没有名为 `End` 的具体错误；用户所见 End 的完整原行尚未取得，不能断言它对应哪个字段。

## 验收和实际生产边界

首批新增七项诊断测试修前失败、修后通过；独立复核又发现非错误回执的 terminal 字段误归因，先增加负向用例复现失败，再收紧读取条件。最终相关回归 **249 passed / 81.82 秒**，102 项 CLI 模型测试全通过，独立只读复核解除阻断。Ruff、TypeScript 类型检查、lint、diff 检查和 wheel 构建通过，无新增依赖。

```powershell
D:\remotion_video\.venv\Scripts\python.exe -B -m pytest tests/videoagents/test_claude_research_metadata.py tests/videoagents/test_cli_cleanup.py tests/videoagents/test_cli_models.py tests/videoagents/test_cli_stream_limits.py tests/videoagents/test_glm_cli.py tests/videoagents/test_providers.py tests/cli/test_director_only_restart.py -q
```

从新维护工作区执行以上测试。它使用本地模拟 CLI，不调用供应商；它证明诊断和重复提交保护，不是真实 GLM 失败复现。wheel 位于 `C:\Users\70pic\AppData\Local\Temp\videoagents-failure-cause-repair-wheel-20261015\videoagents_studio-0.1.0-py3-none-any.whl`。

本轮 [生产只读复验](unknown-cause-repair-production-verification-20261015.json) 确认 Brief、已审七段文案、12 件视觉/音频文件、33 笔历史操作、16+17 张历史 PNG 及旧 UNKNOWN 正文散列保持。当前仍 r11 / NEEDS_INPUT / director，本轮没有新供应商调用、revision、摄影方案、PNG 或成片。所有角色超时已在上一轮按要求设为五倍；延长等待不能解决 CLI 主动报错退出。

要证明真实流程恢复，仍需针对当前未知操作按 [正常恢复入口](../../videoagents-unknown-restart.md) 授权并成功完成新的摄影调用，再逐镜审核。本轮只修诊断、提供证据和代码，没有把用户“先修”或“我要看代码”解释为新用量授权。
