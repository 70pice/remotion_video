# CLI 重试限损修护

## 本轮范围

用户要求避免 UNKNOWN 后重复消耗 token。本轮先修可验证的本地预算缺口，不把 r11 旧错误缺失推断为内部重试所致，也不承诺供应商不会中断或一定退还用量。

1. 用真实本地 Python 子进程复现：Claude 子进程会继承父进程任意大的 API/结构化重试及无限重试 watchdog；引擎的 `max_llm_calls` 只计 CLI 逻辑操作，未限制内部重试。
2. 所有 Claude 生产调用显式设置 `CLAUDE_CODE_MAX_RETRIES=0`、`MAX_STRUCTURED_OUTPUT_RETRIES=1`、`CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES=0`，移除 `CLAUDE_CODE_RETRY_WATCHDOG`。不继承父会话放大的重试配置，不改父进程环境或 Codex/TRAE 行为。
3. 新 Claude 操作台账保存固定 `cli_retry_limits`，使配置可核对；不改变请求指纹、已完成缓存、UNKNOWN 屏障、模型/推理或五倍超时设置。
4. 验证子进程读到的值、父环境不变、研究/普通模式及 GLM/Ark 路由，验证错误仍停 UNKNOWN 且新命令不能绕过，已完成结果不重复提交。运行对应回归、Ruff、类型、lint及构建。

这是明确取舍：瞬时错误也可能更早暂停，结构化生成不再由 CLI 默默重复返工。一次 CLI 仍可能为正常工具流程发出多次模型请求，本配置不是 token 或账单硬上限。

## 官方依据

[Claude Code 环境变量](https://code.claude.com/docs/en/env-vars)说明两层重试是不同循环：结构化默认5次（首次加4次重试）；API错误默认10次重试，watchdog可在容量错误时无限重试。非流式超时重试设置要求 v2.1.285+。本机本轮使用项目解析入口核对版本与变量标识，不调用真实模型。

[成本口径](https://code.claude.com/docs/en/agent-sdk/cost-tracking)与[CLI预算参数](https://code.claude.com/docs/en/cli-reference)不能给自定义 GLM 计划提供真实账单的硬上限；resume 仍会消耗 token，不自动恢复 UNKNOWN。[流式输出](https://code.claude.com/docs/en/agent-sdk/streaming-output#known-limitations)可保存未校验片段，但不是已完成产物；通用部分结果恢复需要独立协议与故障验证，本轮不假装已经实现。

## 已有结果保护与剩余风险

已有 COMPLETED 业务结果按指纹复用，摄影跨版本有已证明完成候选的接续入口；临时文件清理不能覆盖有效成功回执的保护已有回归。成功回执尚未写入 SQLite 时的进程死亡，以及供应商已处理但没有回传结果，仍可能造成损失。把数据库提交挪到回调只缩小窗口，不能消除它，故本轮不把这种改动宣传为根治。

实际 token 消耗不能由 UNKNOWN 推断，本轮没有新的供应商请求。旧 r11 仍需原始供应商回执才能进一步定位；新的正常摄影调用仍按现有恢复入口和可能用量确认处理。

## 本轮验收

- 回归先复现旧行为：新增测试修前 5 failed / 4 passed；修后 9 passed。真实本地 Python 子进程读取最终环境，不调用模型。测试隔离 CODEX_HOME / TRAE_HOME，不读取用户登录文件。
- 调用、清理、流上限、GLM、台账和仅摄影恢复回归共 258 passed / 85.86 秒；已有摄影候选接续及修复回执回归 41 passed / 53.39 秒。测试隔离修正后另跑新增 9 项，0.63 秒全通过。
- Ruff、TypeScript typecheck、lint、wheel 构建通过；无新增依赖。wheel 位于 `C:\Users\70pic\AppData\Local\Temp\videoagents-retry-loss-prevention-wheel-20261015\videoagents_studio-0.1.0-py3-none-any.whl`。
- 通过项目 executable_prefix 解析真实 Claude 可执行入口，只执行 `--version`，本机版本为 2.1.292；静态确认该版本包含四个相关环境变量标识。没有用真实供应商请求验证重试次数或计费。
- 独立只读复核通过：修改仅影响 Claude 子进程环境和固定台账字段，不改变父环境、其他 CLI、指纹、缓存及 UNKNOWN 屏障。测试凭据目录隔离问题修正后解除阻断。

共性修护继续留在独立维护分支。视频任务分支只存证据，不把本地回归称作真实摄影恢复，也不通过修改 UNKNOWN 或审核记录来继续生产。
