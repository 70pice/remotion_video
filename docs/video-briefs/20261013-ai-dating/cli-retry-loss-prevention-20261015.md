# UNKNOWN 后的重试限损修护

2026-10-15，任务 `08e74bed03e94c6e903c89f7f2fbea64`，当前仍 revision 11 / NEEDS_INPUT / director。

## 结论

供应商处理过请求、但结果未返回或未保存时，可能消耗 token 却没有可用产物；本次具体消耗量不能由 UNKNOWN 推断。不能保证供应商永不报错，也不能把延长超时或补充诊断称为彻底修复旧 r11。

本轮新增的是实际限损补丁：Claude Code 自身 API 错误重试、结构化重试和非流式超时重试独立于引擎调用计数。当前代码允许继承父环境放大的重试设置，因而一次逻辑操作可能自动重试更多次；但缺少旧回执，不能证明 r11 就是这样失败或消耗的。

## 已完成的代码修改

独立维护工作区 `D:\remotion_video_unknown_repair_20261015`，分支 `maintenance/unknown-classification-20261015`，提交 `9c7ff79`。包含此前错误诊断、五倍超时支持和共性排版修复。共性代码未混入视频任务分支。

| Claude 子进程配置 | 固定值 | 作用 |
| --- | --- | --- |
| `CLAUDE_CODE_MAX_RETRIES` | `0` | API 错误不自动重试 |
| `MAX_STRUCTURED_OUTPUT_RETRIES` | `1` | 只允许首次结构化生成，不自动重复修复 |
| `CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES` | `0` | 非流式超时不自动重试 |
| `CLAUDE_CODE_RETRY_WATCHDOG` | 从子进程环境移除 | 不继承无限容量错误重试开关 |

只改变 Claude 子进程，不改父环境、Codex/TRAE、模型、推理或已有五倍超时。新操作台账保存固定 `cli_retry_limits`。已有完成结果按指纹复用，UNKNOWN 继续阻止重复提交，不自动重发。

这会让瞬时错误更早暂停；正常工具流程仍可产生多次模型请求，不能当作“一次 CLI 只消耗一次”或 token/账单硬上限。官方定义见 [Claude Code 环境变量](https://code.claude.com/docs/en/env-vars)。

## 直接检查代码

- [cli_runner.py](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:35)：`CLAUDE_RETRY_ENV` 固定配置，`_cli_environment` 应用到 Claude 子进程并移除 watchdog。
- [llm.py](D:/remotion_video_unknown_repair_20261015/videoagents/providers/llm.py:164)：新操作台账的 `cli_retry_limits`。
- [故障与限损测试](D:/remotion_video_unknown_repair_20261015/tests/videoagents/test_cli_retry_limits.py:1)：真实本地 Python 子进程读取环境，验证 UNKNOWN 不重放和成功缓存复用。
- [维护说明](D:/remotion_video_unknown_repair_20261015/docs/cli-retry-loss-prevention.md:1)：修改前计划、依据、取舍与验收。

```powershell
git -C D:\remotion_video_unknown_repair_20261015 show 9c7ff79
```

## 验收与生产状态

新增测试修改前 5 failed / 4 passed，修改后 9 passed。相关调用、清理、流上限、GLM、台账与仅摄影恢复共 258 passed / 85.86 秒；摄影候选接续及修复回执共 41 passed / 53.39 秒。测试目录隔离修正后另跑新增 9 项，0.63 秒通过。Ruff、TypeScript、lint、wheel 构建及独立只读复核通过，无新增依赖。

本机 Claude 经项目解析入口只执行 `--version`，版本为 2.1.292，符合非流式设置所需版本；静态确认相关变量标识存在。没有调用真实模型验证供应商重试或计费。不是 GLM 真实恢复验收。

[生产只读复验](cli-retry-loss-prevention-verification-20261015.json)确认旧 r11 UNKNOWN 正文散列仍为 `fdab588015d5bb09440e0a1cfa9244a2bdd2992318c7ca3798ee99676c2883c8`，文案、12 件视觉/音频文件、33 笔历史操作及 16+17 张历史 PNG 均保持。本轮没有新模型请求、revision、摄影方案、图片或成片。

## 尚未消除的风险

供应商已经处理但没有返回有效结果，或本机在成功回执落入 SQLite 前崩溃，仍可能损失结果。本轮没有实现通用未完成片段恢复；已有完整且验证通过的完成结果可以复用，半截输出不能冒充成功。旧 r11 原始错误正文已经丢失，具体上游原因仍无法还原。此前诊断修复会保存以后回执中确实存在的安全分类，不能补造旧证据。

后续正常设置及恢复须从新维护工作区加载代码并明确原 runtime；任务分支保留旧代码，仅从任务根运行不会自动获得本补丁。当前未知提交仍受正常恢复入口约束，不因维护自动触发付费重跑。
