# r13 API错误分析与固定分类保留

## 结论与证据边界

实际操作 `1eaeeda9e64049c9abe59f2c922250e2` 退出1，Claude Code明确报告终止原因 `api_error`，
未返回可接受业务JSON。失败在模型调用返回阶段，尚未进入Remotion渲染；约28分22秒后结束，
未触发18000秒摄影节点上限。不能由此排除接口内部超时，也不能断定限流、额度或Coding Plan兼容性。
前一笔同r13调用曾成功保存16镜，仅能证明该路由曾成功取得结构化结果。

另外查实一个本地记录缺陷：适配器识别HTTP状态和有限错误文本，但忽略CLI的固定类型字段
`result.api_error`；若CLI给出分类，现有操作台账仍可能丢掉。它解释了诊断链路的遗漏，
不证明本次实际回执曾有该字段，更不能把模拟的分类当成本次上游根因。

## 已安装CLI的静态证据

2026-10-15本机执行 `claude --version`（解析真实安装路径，不发模型请求）得到 **2.1.292**。
二进制SHA256：`eb95bb65955f8b1702e800815f9a2c0388a5de0f196c354c7ee1dd5cb9a2ba23`。
嵌入SDK定义的 `api_error` 固定枚举位于字节偏移209497104；结果schema的
`api_error_status`、`api_error_code`、`api_error` 定义邻近209538185。
结果生成逻辑邻近224721118：API错误也可能输出 `subtype=success`、`is_error=true`，
该subtype不证明调用成功。这里只描述本机安装代码，不作为本次实际回执字段证明。

独立只读检索本次精确Claude项目目录（创建12:26:07.276）只找到空memory，没有JSONL；
本次临时cwd已不存在，debug/logs目录不存在，telemetry最新10月11日，未当成本次证据。
任务目录在12:25–12:56窗口无新产物。调用开启 `--no-session-persistence`，临时目录finally清理，
可解释通常为何无会话文件；不能据此推断具体API触发原因。没有读取凭据或重新提交模型。

## 最小反馈环与修复

新增真实子进程fixture通过 `run_cli` 输入 `subtype=success/is_error=true/terminal_reason=api_error`，
分别附固定分类 `max_output_tokens`、`no_response`、`effort_requires_thinking`。
修复前3项均因 `reported_api_error` 缺失失败，证明代码会丢弃明确分类；不是复现供应商故障。

```powershell
python -B -m pytest tests/videoagents/test_cli_models.py -q -p no:cacheprovider -k typed_api_error_survives_without_http_status
```

修复仅触及 `videoagents/providers/cli_runner.py` 的固定诊断：

1. 只在 `type=result` 且 `is_error is True` 时，保存已安装CLI定义的已知 `api_error` 枚举与来源。
2. 保留合法原始 `subtype=success`，仍按 `is_error` 把它归类为错误。
3. HTTP与固定传输错误提示优先，typed字段补充诊断；未知值、对象、非错误回执不提升为原因。
4. 不保存自由错误原文或任意 `api_error_code`，不改成功解析、UNKNOWN、缓存、重试、模型或超时。

回归覆盖退出0/1、HTTP与typed并存优先级、秘密哨兵不入台账、UNKNOWN入账及同操作禁止重放。
CLI模型/流限制/清理/重试/GLM/摄影契约合计 **236项通过，15.81秒**；Ruff、TypeScript、lint、
wheel构建通过，独立只读复核无阻断。测试均为本地fixture，没有供应商调用。

## 未完成的事实判断

这笔历史调用的原始回执不可恢复，补丁无法补出未保存的 `api_error`、HTTP状态或账单。
现在修复的是“上游已有固定分类时不再丢弃”，不是“供应商API不再失败”。
若未来CLI只给通用 `api_error` 且没有HTTP/typed分类，仍须保留未确定的原因，不能猜测。
生产任务继续保持r13/NEEDS_INPUT，已保存输入和16镜候选未改；没有发起新付费尝试。
