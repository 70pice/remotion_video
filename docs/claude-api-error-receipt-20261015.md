# r13 实际 API 错误回执与保护验证

2026-10-15，摄影操作 `1eaeeda9e64049c9abe59f2c922250e2` 在北京时间12:26:05提交，
任务于12:54:28进入 `NEEDS_INPUT / director`。此次是同r13的正常排版返工，
不是旧UNKNOWN重放，也不是重新启动编剧、素材或配音。

## 已证实的停止原因

Claude Code退出码1；可安全记录的回执为：

```json
{
  "reported_terminal_reason": "api_error",
  "stdout_shape": "claude_error_result",
  "subtype": "unknown",
  "response_json_shape": "absent",
  "stdout_bytes": 1701,
  "stderr_tail_bytes": 78
}
```

这不是上一轮的 `structured_output_retry_exhausted`。本次没有取得可识别的HTTP状态、
API错误类型或固定连接错误；不能判断是限流、额度、接口参数、供应商中断或Coding Plan兼容性。
约28分22秒后结束，未达到18000秒节点等待上限；这只排除本机节点超时，不能排除接口内部超时。
原始自由错误正文不持久化，此次不能从已保存信息补出未记录的上游细节或实际账单。

操作被保存为UNKNOWN，代表已提交但未取得可接受业务结果、可能已有用量；它不表示整个执行过程
没有任何诊断。引擎正常命令DONE只表示已停止，不能作为生产成功证据。

## 本次验收与代码

- `videoagents/providers/cli_runner.py` 的 `_failure_diagnostic` 从回执中投影固定终止原因，
  `CliFailure.hint` 显示“CLI报告API错误，未提供可识别的HTTP状态”。
- `videoagents/providers/llm.py` 捕获已提交的CLI失败，保留原因并写UNKNOWN；重复同角色、版本、
  输入调用受未决屏障阻断。没有把失败伪装为成功或清空旧记录。
- 原配置保留：API错误重试0、非流式超时重试0、watchdog关闭、总结构化尝试3，即首次加最多两次纠正。
  台账限值不是实际API调用次数或账单证明。
- `tests/videoagents/test_cli_models.py` 的终止原因参数化回归新增此次 `api_error` 无HTTP状态形态，
  验证保留真实终止码、不给出HTTP猜测、提示有具体错误类别。

CLI模型与重试限值117项测试通过（7.26秒），Ruff与diff检查通过；均为本地fixture，
不访问真实供应商。本次只补充实际失败形态的回归，没有声称修复未知的上游故障。

任务分支的 `photography-r13-preservation-verification-20261015.json` 证明：原七段已审文案、
12件素材/音频文件、35笔旧操作、33张历史图片及首轮r13的16镜完整候选保持；无本轮新PNG，
无配音、剪辑或上游新提交。后续须依摄影UNKNOWN正常授权入口，不能自动重放这笔调用。
