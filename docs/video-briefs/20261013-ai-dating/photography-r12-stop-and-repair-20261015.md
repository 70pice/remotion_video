# r12 摄影停止与通用修护

追加：用户随后明确要求“两次纠正”。维护提交 **dfde322** 将当前总结构化尝试上限设为3（首次加最多两次纠正），
17项定向回归、Ruff、类型、lint与wheel构建通过。未再次提交摄影；本次Coding Plan兼容性归因仍未确认。
以下“首次加一次”的修复说明是a1443e1时点，当前次数以本追加和维护文档顶部为准。

## 实际生产结果

- 任务 `08e74bed03e94c6e903c89f7f2fbea64`，本次经用户明确要求正常重启为 r12，仅摄影。
- 正常命令 `5a0d32b433434656a016492b09987a85`，摄影操作 `cdef242d12dd438a86a10559928f884e`。
- 北京时间10:35:52进入摄影，10:50:54停止，约15分钟；Claude Code退出1，报告
  `error_max_structured_output_retries / structured_output_retry_exhausted`，没有可用业务JSON。
  摄影等待上限18000秒，此次不是引擎等待超时。
- 当前 r12 / NEEDS_INPUT / director，操作UNKNOWN，待办 `a0eb9616a1114fbdbfe983f8c69efa56`。
  正常命令DONE只表示图已停止，不代表摄影成功；新方案、PNG及成片均为0。

## 原因能确认到哪里

本次实际错误类别已被保存，不再只有unknown。旧限损策略设置结构化尝试为1，没有留格式纠正机会。
但r12的原始验证正文未保留，不能断言具体哪个字段错了，也不能据此说明旧r11的供应商根因。

用本机真实Claude Code 2.1.292连接本地合成接口验证：首次有效提交在上限1可成功；普通JSON文本
后再提交内部工具也可成功，排除了“普通文本提前耗尽”的猜测。首次把 `response_json` 错传数字时，
上限1失败、上限2可纠正成功；连续两次错误仍停止，内层坏JSON仍被适配器拒绝。这是本地已证明的
失败路径，不是本次实际首错内容。测试只连接127.0.0.1，使用临时配置与合成token，不调用供应商。

## 已提交修复

维护工作区 `D:\remotion_video_unknown_repair_20261015`，分支
`maintenance/unknown-classification-20261015`，提交 **a1443e1**。

1. 结构化尝试改为2，允许首次后至多一次格式纠正。API错误/非流式超时重试仍为0，watchdog关闭。
2. 提示禁止外部工具，明确允许Claude内部StructuredOutput提交，并给出字符串封装示例。
   现有shell、文件与额外MCP工具限制保持。
3. 若CLI明确报告已验证的 `/response_json: must be string` 完整错误头，安全诊断保存固定类型码、
   报告次数和来源，提示具体字段。其他未知错误不伪装为该类型，不保存自由错误原文或字段值。
4. UNKNOWN阻断、成功缓存、严格业务JSON解析、模型/推理、已设五倍超时均保持。

这是有限纠正与诊断修复，不是总请求数或账单硬上限，也不证明真实GLM下一次必定成功。

## 代码与验收

- [重试上限与子进程环境](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:37)
- [安全错误投影](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:506)
- [内部提交说明](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:807)
- [摄影等普通任务提示](D:/remotion_video_unknown_repair_20261015/videoagents/providers/llm.py:190)
- [真实CLI离线回归](D:/remotion_video_unknown_repair_20261015/tests/videoagents/test_claude_structured_protocol.py:1)
- [共性修护完整证据与官方依据](D:/remotion_video_unknown_repair_20261015/docs/claude-structured-output-correction.md)

提示与诊断回归修前4失败、修后通过；真实CLI生产策略回归修前失败、修后通过。相关调用、流限制、
台账、摄影恢复与候选接续等 **311项通过/134.33秒**。Ruff、TypeScript、lint、wheel构建及独立只读
复核通过。代码未混入视频任务分支，后续正常入口需从上述维护工作区加载修复代码并指定原runtime。

## 当前保护与续跑边界

[停止后只读复验](photography-r12-postrepair-verification-20261015.json)确认原Brief、七段已审文案、
12件素材/音频及33张历史PNG保持，旧r11 UNKNOWN正文散列不变。本次仅一笔新摄影操作，共35笔历史
操作、10笔UNKNOWN；没有活动命令、新批准、新配音或再次摄影提交。

本轮没有新图可交逐镜审核。[监控流水](photography-r12-monitor-20261015.jsonl)记录真实运行与停止。
本次真实调用可能已有用量，无法用UNKNOWN判断账单。按[摄影UNKNOWN恢复规则](../../videoagents-unknown-restart.md)，
“再次出现摄影 UNKNOWN 时须再针对新操作明确授权”。因此修复后没有自动发起r13；下一次只能通过正常
仅摄影恢复入口，并保留文案、素材、真实配音及人工逐镜门。
