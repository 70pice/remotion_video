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

## 第一次返回与正常摄影返工

12:17:31，摄影操作 `90912e13e0bd43bba8638c7b0247a099` 已COMPLETED，保存16镜候选；
命令正常结束，任务停在NEEDS_INPUT / director，问题为 `B12.emphasis 显示区间不足阅读或超出镜头`。
这次不是UNKNOWN、Claude非零退出或引擎等待超时。候选保存不等于有效生产timeline；新PNG仍为0。

只读调用真实校验器复现：

| 镜头与部件 | 实际/最低显示帧数 | 完整绑定文字字符数 |
| --- | --- | --- |
| shot-02 B12.emphasis | 55/65 | 20 |
| shot-05 B03.support_3 | 100/113 | 39 |
| shot-06 A07.support_3 | 65/73 | 23 |
| shot-06 A07.support_4 | 70/78 | 25 |

同时，shot-02/05/06/13存在增强套非空正文、字数、条数或metric条件不符。代码正确阻止产物进入
有效timeline。已发现通用正文可空建议与增强套正文必填的提示歧义；独立维护提交 `ebe47a1`
从实际运行时规则派生生产内容条件并澄清阅读公式，没有修改校验器或放宽边界。
新增3项回归先红后绿，相关161项回归、Ruff、TypeScript、lint及wheel构建通过；独立只读复核无阻断。
详见维护工作区 `docs/production-kit-prompt-contracts.md`。

监督复核还定位到未落实的原画面要求：2256帧已进入真人零工口播，候选仍至2310帧才从充值图切换；
QuoteCard实际取body优先，shot-14标题中的封禁主事实没有进入实际主文；shot-07横条图的默认cover
会裁掉使用按钮；shot-09仅文字说明焦点而无实际裁切绑定，多镜正文与来源重复。这些不是已经看过
新PNG的结论，均来自实际候选字段、原图/实测字幕和渲染器绑定的只读核查。

12:26:05，从维护提交 `ebe47a1` 使用正常 `resume --decision confirm` 回答摄影kind=input待办
`af9d562131694afaab4d82eec6f7baef`；此confirm只是输入校验返工，不是逐镜整包人审通过。
新的1880字符[集中意见](photography-r13-layout-feedback-20261015.txt)已经中文逐字读回一致，
要求以r13完整候选续修、保留无问题镜头和所有上游，完整输出并继续真实逐镜审阅。

- 命令：`bbfbc337d1c0429480bd58780b71c645`；启动PID `24856`。
- 幂等键：`photography-r13-layout-repair-20261015`。
- 新摄影操作：`1eaeeda9e64049c9abe59f2c922250e2`，当前SUBMITTING。
- 输入指纹：`8f759f222c752c19bbf12b2539450cfe2a67f0d5163239ea3b48c226793f2d4e`。
- 仍为同任务r13、GLM-5.3[1m]/xhigh、首次加最多两次结构化纠正；没有重放旧UNKNOWN或启动上游。

12:26:46只读复验：原Brief、七段文案、12件文件、35笔旧操作与33张历史图保持；r13首次COMPLETED
候选完整记录保持。当前共两笔摄影操作，新PNG/有效timeline仍0，未授予逐镜审核或发布。
见[完整保留验证](photography-r13-preservation-verification-20261015.json)与监控JSONL后续观察。
