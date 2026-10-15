# r13 本次接续结果与实际停止原因

任务：`08e74bed03e94c6e903c89f7f2fbea64`。用户明确“继续吧”后，经正常入口仅恢复摄影。
本轮包含首轮生成与一次正常排版返工，没有重做已审文案、素材或配音。

## 两次调用须分开判断

| 项目 | 首轮摄影 | 正常排版返工 |
| --- | --- | --- |
| 操作ID | `90912e13e0bd43bba8638c7b0247a099` | `1eaeeda9e64049c9abe59f2c922250e2` |
| 时间（北京时间） | 12:13:13至12:17:31 | 12:26:05至12:54:28 |
| 模型结果 | COMPLETED，完整16镜候选已保存 | UNKNOWN，没有可用业务JSON |
| 停止原因 | B12强调文字55帧，阅读预算至少65帧；另有已复现内容条件问题 | Claude Code退出1，终止原因 `api_error` |
| 下游 | 输入校验停止，无有效timeline或新PNG | 输入待办停止，无有效timeline或新PNG |

首轮证明这次曾取得有效传输的结构化结果；不能据此声称全部画面已合格，或供应商后续不会出错。
返工使用同r13、实际16镜候选和[集中意见](photography-r13-layout-feedback-20261015.txt)，
属于正常kind=input修复，不是逐镜人审确认或对旧UNKNOWN自动重试。

## 本次错误已知与未知

返工台账保存：`cli_nonzero_exit`、`exit_code=1`、`reported_terminal_reason=api_error`、
`stdout_shape=claude_error_result`、`subtype=unknown`、`response_json_shape=absent`、
`stdout_bytes=1701`、`stderr_tail_bytes=78`。

约28分22秒后结束，未达到当前18000秒摄影节点上限，排除该节点等待超时；接口内部是否超时未确认。
没有取得可识别HTTP状态、具体API错误类型或固定连接错误，不能判断限流、额度、参数问题、
供应商中断或Coding Plan兼容性。不能把本次错误说成旧r12的“结构化纠正耗尽”。
自由错误原文不持久化，不能从现有台账补出未保存的上游细节或实际扣费。

UNKNOWN表示已经提交、未取得可接受结果且可能已有用量；这次同时保存了明确API错误类别。
正常命令DONE只说明图执行已停止，不代表模型、方案或视频成功。

## 修护与代码阅读入口

首轮排版失败后在独立维护分支提交 `ebe47a1`：从运行时规则派生增强组件套的正文、字数、
条数和metric条件，澄清与实际校验器一致的阅读预算。没有放宽校验或修改已审事实。
3项新增测试先红后绿，相关161项回归、Ruff、TypeScript、lint、wheel构建和独立复核通过。
此提示修复不等于修复未知的API故障；因返工调用未返回，尚无实际修正版验证。

- [摄影提示派生](D:/remotion_video_unknown_repair_20261015/videoagents/nodes/director.py:447)
- [生产组件套提示修护证据](D:/remotion_video_unknown_repair_20261015/docs/production-kit-prompt-contracts.md)
- [错误回执投影](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:539)
- [错误提示解释](D:/remotion_video_unknown_repair_20261015/videoagents/providers/cli_runner.py:179)
- [失败写入与停止重复调用](D:/remotion_video_unknown_repair_20261015/videoagents/providers/llm.py:214)
- [此次API错误回归与证据边界](D:/remotion_video_unknown_repair_20261015/docs/claude-api-error-receipt-20261015.md)

维护提交 `1768b5f` 另补API终止但无HTTP状态的回归；CLI模型与限值117项本地测试通过，Ruff和diff检查通过。
没有调用供应商测试或声称真实API已恢复。当前配置仍为首次加最多两次结构化纠正、API错误重试0、
非流式超时重试0、watchdog关闭；限值不证明实际计费请求数。五倍超时没有再乘一次。

## 已有成果与下一步边界

[12:55:34只读复验](photography-r13-preservation-verification-20261015.json)确认原Brief、七段已审文案、
12件素材/音频文件、35笔旧操作、33张历史PNG及首轮r13完整16镜候选保持。
当前r13 / NEEDS_INPUT / director；本轮有效timeline、新PNG与成片均0。
具体停止记录在[监控流水](photography-r13-monitor-20261015.jsonl)，未授予逐镜审核或发布。

按[项目摄影UNKNOWN规则](../../videoagents-unknown-restart.md)，
“再次出现摄影 UNKNOWN 时须再针对新操作明确授权”。本次新UNKNOWN未重放；后续只能针对这笔操作
经正常仅摄影入口接续，继续保留已有文案、素材、真实音频和人工逐镜门。
