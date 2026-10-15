# Claude 结构化提交的一次纠正

## 本轮发现与边界

2026-10-15 的摄影 r12 实际运行约15分钟后，Claude Code 以退出码1返回
`error_max_structured_output_retries / structured_output_retry_exhausted`，没有业务 JSON。
摄影超时为18000秒，此次不是引擎等待超时。台账已保存确切终止分类；原始验证错误正文未保存，
所以仍不知道 r12 首次提交的具体内容或字段，不能将本地模拟的字段错误当作本次实际字段错误，
也不能由 r12 解释旧 r11。

上次限损修护把结构化尝试设为1，没有给格式错误留纠正机会。本轮修复这个已复现的本地策略缺口，
同时明确输出协议与安全诊断；没有把旧 UNKNOWN 改成成功，没有发起第二笔真实摄影调用。

## 实际 CLI 的离线证据

新回归 `tests/videoagents/test_claude_structured_protocol.py` 使用本机实际 Claude Code 2.1.292，
经生产 `run_cli → build_arguments / _cli_environment → _claude_result` 调用链连接
`127.0.0.1` 的合成 Anthropic Messages 接口。响应使用请求里实际声明的内部工具名，完整模拟 SSE。
子进程环境采用系统启动变量白名单、临时 Claude 配置和合成 token，关闭遥测，不使用用户凭据。

| 合成响应顺序 | 结构化上限 | 实际本地请求数 | 结果 |
| --- | --- | --- | --- |
| 首次有效内部工具提交 | 1 | 1 | 成功 |
| 普通 JSON 文本，再有效工具提交 | 1 | 2 | 成功，排除普通文本消耗结构化次数的猜测 |
| `response_json` 是数字，再正确字符串 | 1 | 1 | 结构化尝试耗尽，不能纠正 |
| 同上 | 2 | 2 | 纠正成功 |
| 始终传数字 | 2 | 2 | 耗尽并停止 |
| 字段为字符串但内部 JSON 无效 | 2 | 1 | CLI 外层通过，适配器仍拒绝 |
| 使用实际生产策略，首错再正确 | 旧1 / 新2 | 1 / 2 | 修前红，修后绿 |

这证明有限纠正与本地协议，不证明真实 GLM 会遵循提示或本次 r12 的精确首错。合成响应中的
usage 是测试数据，不能作为真实 token 或账单统计。

## 通用修复

1. `videoagents/providers/cli_runner.py` 将 `MAX_STRUCTURED_OUTPUT_RETRIES` 从1改为2：
   首次加至多一次结构化纠正。API错误重试0、非流式超时重试0、watchdog关闭保持。
   正常文本/工具轮次仍可能产生额外请求；这不是总请求数或账单硬上限。
2. `videoagents/providers/llm.py` 将“禁止工具”精确为“禁止外部工具”；Claude 传输尾说明仅允许
   内部 `StructuredOutput` 提交最终结果，并举例要求 `response_json` 为序列化后的字符串。
   shell、文件、额外 MCP 仍禁用；研究阶段仅保留原启用的研究 MCP，不扩大权限。
3. 失败诊断精确识别 CLI 已验证的完整 `/response_json: must be string` 耗尽头，保存固定
   `reported_structured_error=response_json_not_string`、报告次数及固定来源，并显示明确提示。
   不保存字段值或错误原文；额外后缀、任意路径及未认识错误不伪装成已识别根因。
4. 保持模型、推理、五倍超时、业务 schema、严格内部 JSON 解析、请求指纹、COMPLETED缓存和
   UNKNOWN阻断。仅本地修复不会解除旧未决提交，也不代表摄影已恢复或逐镜审核已通过。

## 官方依据与验证

[Claude Code 环境变量](https://code.claude.com/docs/en/env-vars)区分结构化尝试与API错误重试；
计数实际行为已用上表的本机二进制验证。[结构化错误说明](https://code.claude.com/docs/en/agent-sdk/structured-outputs#error-handling)
说明耗尽也可能涉及模型切换撤回结果，因此仅凭 subtype 不断言具体 schema 错误。
本轮没有依据修改 GLM 能力开关或更换模型。

- 新提示与固定诊断回归修前4失败/4通过，修后8通过；生产策略真实CLI回归修前1失败，改为2后成功。
- 七项真实CLI协议回归与九项环境/台账/缓存回归合计16通过；无需真实供应商请求。
- 调用、清理、流限制、GLM、错误台账、仅摄影恢复、候选接续与摄影修复回执相关回归共
  311 passed / 134.33 秒。包含上述七项真实CLI协议回归。
- Ruff、TypeScript typecheck、lint、`git diff --check` 通过，未新增依赖。
- `uv build --wheel` 通过，产物为
  `C:\Users\70pic\AppData\Local\Temp\videoagents-structured-correction-wheel-20261015\videoagents_studio-0.1.0-py3-none-any.whl`。
- 独立只读复核通过：固定错误投影不泄露正文、测试环境与假接口隔离、外部工具禁用、请求指纹与
  未决/成功缓存边界保持。静态复核另验证六个固定诊断正反例。
