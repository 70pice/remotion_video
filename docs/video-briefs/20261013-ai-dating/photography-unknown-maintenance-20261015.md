# UNKNOWN 诊断修复验收

2026-10-15 08:33（北京时间）。任务 `08e74bed03e94c6e903c89f7f2fbea64`，r11。用户引用消息 `om_x100b62350c0938a4de0066372af2e49` 的原文是“先修 unkonwn”，本轮执行诊断修护，没有将其记录为新摄影提交的用量授权。

## 已修复的确定缺陷

维护工作区 `D:\remotion_video_unknown_repair_20261015`，分支 `maintenance/unknown-classification-20261015`，提交 `cc4fb8e934074cbe8ce7886e5ad79364c78ed26f`，基于包含排版修复的 `da5f3c7`。视频分支仅保存本验收与只读核对记录，未混入共性代码。

原实现把 Claude 已知错误类型统一记为 `unknown`，普通结构化调用退出码0但返回错误结果时也未保存安全诊断，输入门只给通用提示。修复范围：

- `videoagents/providers/cli_runner.py` 精确识别执行失败、轮次上限、单次预算上限、结构化输出重试耗尽四个官方固定类型，保留既有 `unrecognized_model`；其余继续记为 `unknown`。普通 Claude 结构化调用的零退出错误也保留相同的六字段安全诊断。
- `videoagents/providers/llm.py` 使用固定中文提示显示已知原因；结果不确定仍进入 `UNKNOWN`，同一操作禁止自动重放。没有改变操作指纹、缓存、状态分类、模型、推理、超时、schema或供应商提交参数。
- `tests/videoagents/test_cli_models.py` 用真实 Python 子进程模拟 CLI，覆盖四种官方错误类型与退出码0/1、正常模型输入门、台账和重复调用阻断。错误正文、凭据、usage和URL不进入诊断。
- `docs/cli-failure-diagnostics.md` 记录分类来源与边界。分类为执行失败仍不等于已确定供应商原因；结构化输出重试耗尽也不能证明schema过于复杂。研究流与Codex/TRAE原有错误分支保持。

## 新鲜验证

修改前新增回归10 failed；修复后同组10 passed。完整相关回归231 passed（83.01秒）：

```powershell
D:\remotion_video\.venv\Scripts\python.exe -B -m pytest tests/videoagents/test_claude_research_metadata.py tests/videoagents/test_cli_cleanup.py tests/videoagents/test_cli_models.py tests/videoagents/test_cli_stream_limits.py tests/videoagents/test_glm_cli.py tests/videoagents/test_providers.py tests/cli/test_director_only_restart.py -q
```

Ruff、`npm run typecheck`、`npm run lint`、`git diff --check`通过，`uv build --wheel`通过，产物为 `C:\Users\70pic\AppData\Local\Temp\videoagents-unknown-repair-wheel-20261015\videoagents_studio-0.1.0-py3-none-any.whl`。独立只读复核无阻断意见；仅文档按复核建议限定普通Claude结构化分支。未增加依赖，未调用真实模型复现供应商故障。

只读调用核查确认本机 Claude Code 2.1.292 支持现有参数，未发现项目设置低轮次或低单次美元预算。本笔约32分钟后退出1，记录分支不是3600秒超时。没有足够证据归因于参数、登录、账户额度或schema，因此未试改这些配置。

## 当前真实任务仍保留 UNKNOWN

08:32只读复验见[任务与产物核对](photography-unknown-repair-verification-20261015.json)。操作 `a290785969554baab4bb2cebbbcd9c42` 的正文散列仍为 `fdab588015d5bb09440e0a1cfa9244a2bdd2992318c7ca3798ee99676c2883c8`，原原因仍是 `cli_nonzero_exit / exit_code=1 / claude_error_result / subtype=unknown`。当时未保存具体错误类型，新修复不能还原已经丢失的内容，未改写旧原因或输入门提示。

原Brief、七段已审文案、12件素材/音频文件、前33笔操作和16+17张历史PNG保持。本轮未新增revision、模型提交、有效摄影方案或PNG，当前仍 `r11 / NEEDS_INPUT / director`；上一轮17图仍被退回，没有逐镜整包通过、成片或发布。

新代码工作区对原权威runtime的接续预检通过，已证明r9原16镜候选可作为底稿，并不等于最新17镜逐字段冻结。完整本机报告：`C:\Users\70pic\AppData\Local\Temp\videoagents-director-unknown-repair-preflight-20261015.json`，SHA-256 `a206e79968ad6e712180ad8888dd9b56c913b7796d25b609adf9e2ddd479cb79`。数据库、checkpoint及789个读文件散列保持，模型/生产provider未调用；一次网络尝试被只读守卫阻止。预检不构成生产提交或人审通过。

本轮修复的是诊断丢失，尚未证实供应商现在可成功返回。针对新UNKNOWN的新调用仍按[正常恢复规则](../../videoagents-unknown-restart.md)处理；本轮没有执行恢复命令，也没有重做文案、素材或配音。

## 按追加要求将所有角色超时设为当前值的五倍

用户随后明确要求“修完之后每一个agent的超时时间设置为原来的5倍”。08:38已通过新维护工作区的正常 `videoagents.main settings set` 写入原权威runtime，并 `settings get` 读回；详见[设置变更回执](photography-timeout-fivefold-20261015.json)。本次范围为全部七个配置角色（含两个历史审核配置）以及摄影/剪辑共用渲染等待。

| 配置 | 变更前 | 变更后 |
| --- | --- | --- |
| 素材 materials | 1800秒 / 30分钟 | 9000秒 / 150分钟 |
| 编剧 screenwriter | 900秒 / 15分钟 | 4500秒 / 75分钟 |
| 历史文案审核 script_reviewer | 900秒 / 15分钟 | 4500秒 / 75分钟 |
| 配音指导 voice | 900秒 / 15分钟 | 4500秒 / 75分钟 |
| 摄影 director | 3600秒 / 60分钟 | 18000秒 / 300分钟 |
| 剪辑 editing | 900秒 / 15分钟 | 4500秒 / 75分钟 |
| 历史审核 review | 900秒 / 15分钟 | 4500秒 / 75分钟 |
| 共享渲染 render_timeout_seconds | 1800秒 / 30分钟 | 9000秒 / 150分钟 |

为支持这些值，维护提交 `ac5c32dd98c6a21616c872a9c7702586affa76fc` 将角色与共享渲染的设置上限从7200秒放宽为36000秒，下限和默认值保留；仅Pydantic契约、导出schema、CLI回归及使用说明变化。相关超时用例修改前4 failed / 4 passed，修改后8 passed；完整CLI12 passed，设置/GLM/Codex回归43 passed，Ruff、契约导出检查、类型检查、lint和wheel构建通过。独立静态复核无阻断项，确认生产消费端没有额外旧上限截断，超时不参与请求指纹。

CLI实际读回与预期逐字段相同，原模型、provider、推理档位、其他设置和所有生产数据表散列保持。08:38[变更后产物复验](photography-timeout-postchange-verification-20261015.json)确认原文案、12件文件、33笔旧操作及16+17PNG保持，原UNKNOWN正文散列与输入门未改。本次没有新提交，不会延长已结束的旧调用。延长等待也不能解决CLI主动错误退出本身。

后续设置读取和正常续跑使用 `D:\remotion_video_unknown_repair_20261015` 中的新CLI（维护HEAD `ac5c32d`，显式runtime目录）；旧视频分支的契约仍限制7200秒，不能用旧代码读取新值。任务分支继续只存生产记录，共性修护保持独立。

08:39尝试重跑严格接续预检时，守卫因设置写入后存在非空WAL而在读取前拒绝：`nonempty_wal_requires_consistent_readonly_snapshot`。没有关闭守卫、强制checkpoint或覆盖原数据库；08:25的成功接续预检只代表变更前时点。配置读回和逐文件复验已经通过，该严格预检未作为变更后成功证据。
