# r13 摄影接续监控

任务：`08e74bed03e94c6e903c89f7f2fbea64`。任务分支：`video/08e74bed03e94c6e903c89f7f2fbea64`。

## 授权与运行范围

用户引用消息 `om_x100b6230b86c0cb4c044da13f8d271e`，明确回复“继续吧”。被引用消息已说明r12
UNKNOWN、新尝试可能产生用量，以及共性代码现已支持首次尝试加最多两次结构化纠正。本次仅授权一次新的
摄影提交，不代表逐镜包确认或成片发布，也没有授权后续UNKNOWN自动重放。

通过正常CLI `restart-unknown --director-only --acknowledge-possible-usage`，针对旧操作
`cdef242d12dd438a86a10559928f884e` 保存r13；2026-10-15 12:12:15（北京时间）保存为DRAFT。
授权要求全文见[本次说明](photography-r13-authorized-note-20261015.txt)。

只读启动前验证确认Brief、七段已审文案和12件素材/真实音频保持，文件散列有效；旧r12 UNKNOWN完整
记录保持，并保存全部35笔旧操作的状态及记录散列供结束后比对。没有新配音、编剧或素材提交。
见[验证与基线](photography-r13-authorization-verification-20261015.json)。

## 实际提交

2026-10-15 12:13:13（北京时间），从独立维护工作区
`D:\remotion_video_unknown_repair_20261015`、维护提交 `dfde322`，加载原权威runtime
`D:\remotion_video\.runtime\videoagents`，执行正常 `videoagents.main run`。

- 幂等键：`user-authorized-photography-r13-20261015`。
- 命令：`3d403649503f4fa49a56286f491e253c`，启动PID `24708`。
- 摄影操作：`90912e13e0bd43bba8638c7b0247a099`。
- 输入指纹：`d7ea645cb3cb292978ef656a823377acc0d7c72ed7eac61e8926cfcf68455ed9`。
- 模型与推理：`claude_code_cli` / `glm-5.3[1m]` / `xhigh`，没有偷偷降级。
- 操作台账：`structured_output_attempts=3`、API错误重试0、非流式超时重试0、无限重试watchdog关闭。
- 保留已设置摄影18000秒、共享渲染9000秒上限，没有再次乘五。

`3`是结构化提交上限，不是全部API请求数或费用硬上限。两次纠正已通过真实Claude CLI的本地隔离协议
回归验证；这不证明本次真实供应商一定成功，也不证明旧r12首错的具体字段或Coding Plan兼容性根因。

## 监控与终止条件

以SQLite `mode=ro` 和 `query_only=ON` 读取任务与台账，不改数据库、审核标记或产物。
观察记录追加至[JSONL](photography-r13-monitor-20261015.jsonl)。不因终端没有输出而重新提交运行命令。

截至12:15:31，实际为r13 / RUNNING / director，摄影操作SUBMITTING；当前版本新方案与PNG均为0。
SUBMITTING只表示引擎等待外部结果，不代表供应商具体生成进度。后续结果须以实际新记录为准。

成功生成后经正常入口呈递逐镜PNG，保留人工整包审核；不会自动进入成片确认或发布。
若再次UNKNOWN，记录真实错误并保留已有结果与输入，不自动追加付费请求。若是可复现的共性代码问题，
在独立维护分支修复并跑相应回归，再走正常恢复入口，禁止手改方案或伪造渲染。
