# r12 摄影恢复与监控

用户在已知旧 UNKNOWN 可能已有用量后明确要求“摄影节点重新开始工作。你来监控摄影节点。如果有问题记录下来修复”。2026-10-15 通过正常 `restart-unknown --director-only --acknowledge-possible-usage` 保存同任务 r12；本授权只覆盖本次摄影新尝试，不授予逐镜确认或发布。

- 任务：`08e74bed03e94c6e903c89f7f2fbea64`。
- 原操作：`a290785969554baab4bb2cebbbcd9c42`，保留 UNKNOWN，正文散列保持。
- 新运行：幂等键 `user-authorized-photography-r12-20261015`，命令 `5a0d32b433434656a016492b09987a85`。
- 新摄影操作：`cdef242d12dd438a86a10559928f884e`，Claude Code / `glm-5.3[1m]` / xhigh / 1000000 tokens 上下文。
- 代码：独立维护工作区 `D:\remotion_video_unknown_repair_20261015`，HEAD `9c7ff79`；显式指定原权威 runtime `D:\remotion_video\.runtime\videoagents`。没有把旧任务工作区代码当新修复代码使用。

本次 [摄影要求和授权说明](photography-r12-authorized-note-20261015.txt) 已逐字回读；[授权后、启动前验证](photography-r12-authorization-verification-20261015.json)确认原 Brief、七段已审文案、12 件素材/音频实体及旧 UNKNOWN 保持，未产生新批准，启动前没有 r12 操作。

北京时间 10:35:51 通过正常 `run` 启动，r12 / RUNNING / director。模型台账记录 API 错误重试0、结构化尝试1、非流式超时重试0及 watchdog=false，摄影超时18000秒。该记录不能证明模型已返回或供应商已完成，本次启动时还没有新方案或 PNG。

监控使用独立只读 SQLite 连接（mode=ro，query_only=ON），记录状态、固定诊断、操作和产物数量，不读取凭据、不修改图状态。原始监控投影见 [监控流水](photography-r12-monitor-20261015.jsonl)。结束时核对业务 JSON、实际 PNG、失败或待审边界；遇到本地缺陷先留证并回归，再用正常入口恢复。新 UNKNOWN 不自动循环提交。
