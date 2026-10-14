# CLI 非零退出诊断

生产角色的 CLI 进程退出码非零时，模型调用仍记为 `UNKNOWN`，不会把 stdout 中看似完整的业务结果当作成功，也不会自动重放。本次改动只增加安全的失败线索，不能据此断定某次真实失败的根因。

`CliFailure.reason` 和操作台账保留 `cli_nonzero_exit` 或 `invalid_cli_output` 前缀，后接一段 JSON。字段仅包括 `exit_code`、`stdout_bytes`、`stderr_tail_bytes`，以及固定集合中的 `stdout_shape`、`response_json_shape` 和 `subtype`。`exit_code` 在进程等待完成前为 `null`，不会猜测。普通 Claude CLI stdout 可区分外层 JSON 无效、错误/成功的 `result` 外壳，以及 `response_json` 为对象、其他 JSON、无效 JSON 或缺失；研究流和 Codex/TRAE 仅标记为事件流或空输出。只有 `subtype` 精确为 `success` 且 `is_error` 精确为 `false` 时，输出形态才记为成功外壳；这仍不能覆盖非零退出。`subtype` 字段只识别明确列入白名单的 `unrecognized_model`，其余统一为 `unknown`，不能把 CLI 返回的任意标识符当成安全类别。

stdout 原文、错误消息、业务 `result`、`response_json` 内容、`usage` 内容、凭据和 URL 均不进入诊断。stderr 只保留已截取尾部的字节数，不再拼接自由文本。旧台账不作变更；新字段只反映进程和输出形态，不能证明请求是否计费或生产结果是否成立。遇到 `UNKNOWN` 仍按原有对账和人工恢复边界处理。
