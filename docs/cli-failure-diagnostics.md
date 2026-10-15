# CLI 非零退出诊断

生产角色的 CLI 进程退出码非零时，模型调用仍记为 `UNKNOWN`，不会把 stdout 中看似完整的业务结果当作成功，也不会自动重放。本次改动只增加安全的失败线索，不能据此断定某次真实失败的根因。

`CliFailure.reason` 和操作台账保留 `cli_nonzero_exit` 或 `invalid_cli_output` 前缀，后接一段 JSON；普通 Claude 结构化调用的 `cli_reported_error` 也保留相同投影，研究流与 Codex/TRAE 的该错误分支维持原有错误码。基础六字段是 `exit_code`、`stdout_bytes`、`stderr_tail_bytes`，以及固定集合中的 `stdout_shape`、`response_json_shape` 和 `subtype`。`exit_code` 在进程等待完成前为 `null`，不会猜测。普通 Claude CLI stdout 可区分外层 JSON 无效、错误/成功的 `result` 外壳，以及 `response_json` 为对象、其他 JSON、无效 JSON 或未取得可检查的内层字符串；`absent` 也涵盖外层/内层字段类型不符，不能据此声称整个structured_output字段不存在。研究流和 Codex/TRAE 仅标记为事件流或空输出。只有 `subtype` 精确为 `success` 且 `is_error` 精确为 `false` 时，输出形态才记为成功外壳；这仍不能覆盖非零退出。

`subtype` 仅保留官方固定的 `error_during_execution`、`error_max_turns`、`error_max_budget_usd`、`error_max_structured_output_retries`，以及既有兼容项`unrecognized_model`；其余统一为`unknown`。类型必须为字符串且精确匹配，不接受任意标识符或错误正文。零退出但返回错误result时也保留相同投影，不把退出码0当业务成功。依据：[官方类型参考](https://code.claude.com/docs/en/agent-sdk/typescript.md)、[官方结构化输出说明](https://code.claude.com/docs/en/agent-sdk/structured-outputs)。

已知分类经固定中文提示进入正常输入门，例如结构化输出重试耗尽会明确显示该原因，不再笼统要求检查登录/账户额度。会话轮次上限与单次调用预算上限分别说明，不等同于供应商账户额度不足。`error_max_structured_output_retries`也可能来自模型fallback撤回后无成功重试，不能只凭该类型断言schema过于复杂；`error_during_execution`本身仍不能定位具体供应商错误。

有可识别证据时，最多再增加 `reported_http_status`、`reported_error_kind`、`error_detail_source` 和 `reported_terminal_reason` 四项；没有证据时字段缺省：

- 仅在 Claude `result.is_error is True` 时读取错误详情。兼容 `errors` 的字符串列表或旧版单字符串，也可从 `result` 中匹配标准 `API Error:` 头；只有原回执中的整数 `api_error_status`，或标准头中实际出现的状态，才保存 HTTP 状态。不从错误类型反推状态，不把字符串状态强转为整数。
- `terminal_reason` 仅保留官方固定集合，且同样要求错误回执；`completed` 只是失败上下文中的泛化结束标签，优先级低于具体失败 subtype，不能证明生产成功。
- stdout 无可识别详情时，可从已截取的 stderr 尾部精确匹配固定 HTTP 头、连接错误、请求超时、流关闭、流格式错误或 JSON 意外结尾。只留固定代码与来源标记，不保存消息正文。stderr 的识别是尽力而为，不保证所有 CLI 版本与供应商文本均可识别。
- HTTP 提示说明 CLI 实际报告的状态；429 不擅自区分限流和额度，400/422 不猜具体参数。连接错误不能区分本机网络与供应商中断；JSON 意外结尾只是解析症状。单独的 `End` 不识别为失败原因。

依据：[SDK结果字段与终止原因](https://code.claude.com/docs/en/agent-sdk/typescript.md#sdkresultmessage)、[Python SDK 对 errors/result 的兼容处理](https://github.com/anthropics/claude-agent-sdk-python/blob/main/src/claude_agent_sdk/_errors.py#L39-L79)、[官方接口错误](https://platform.claude.com/docs/en/api/errors)、[流中断提示](https://code.claude.com/docs/en/errors#the-response-above-may-be-incomplete)。这些资料支持诊断字段设计，不能证明旧版本 CLI 当时返回了哪些字段，也不能证明本次 GLM 供应商故障的根因。

stdout 原文、错误消息正文、业务 `result`、`response_json` 内容、`usage` 内容、凭据和 URL 均不进入持久诊断。原文仅在当前进程内供严格匹配，旧台账不作变更。新字段反映回执中确有的线索，不能证明请求是否计费、生产结果成立或上游故障已修好。遇到 `UNKNOWN` 仍按原有对账和人工恢复边界处理。

本地协议回归使用Python模拟CLI子进程，覆盖四种官方错误类型与退出码0/1、正常模型门提示、脱敏及同一UNKNOWN禁止重放。它验证诊断修复，不是真实供应商失败的复现，不证明旧操作可恢复或供应商现已正常。
