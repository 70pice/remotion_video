# r14 摄影授权重试与监控

- 任务：`08e74bed03e94c6e903c89f7f2fbea64`；沿用本视频分支。
- 用户在获知 r13 API 失败、可能产生用量及诊断记录修复后明确要求：“你再试一下吧”。据此仅重试摄影，不再次请求同一授权。
- 维护代码：`ecb745f`。通过正常 `restart-unknown --director-only --acknowledge-possible-usage` 新建 r14，再执行 `run`。
- 前置快照：`photography-r14-pre-retry-baseline-20261015.json`。授权读回：`photography-r14-authorization-verification-20261015.json`。返工需求：`photography-r14-authorized-note-20261015.txt`。
- 保留已审 7 段文案、11 件视觉素材和 1 件真实音频；12 个文件均通过 SHA-256 校验。原有 37 次操作的状态、输入指纹和正文哈希未改动。
- 旧操作 `1eaeeda9e64049c9abe59f2c922250e2` 仍为 UNKNOWN，不篡改旧结果或盲重放。正常恢复入口沿用已验证来源的候选方案与返工意见。
- 2026-10-15 13:40（北京时间）启动摄影。新命令 `f66e63b08ffc42ec87433c8d71697305`；新模型操作 `49badb7416bb49fa9dd4d8161750ba51`。
- 实际参数：Claude Code CLI、`glm-5.3[1m]`、`xhigh`；结构化输出最多初次加两次纠正；API 错误自动重试 0 次；摄影超时沿用已增加后的 18000 秒。
- 只读监控写入 `photography-r14-monitor-20261015.jsonl`，不执行数据库写入或额外供应商调用。

## 结果边界

启动时状态 RUNNING / director，模型提交 SUBMITTING；此时没有 r14 镜头 PNG、没有通过的时间线。模型返回后仍需实际校验与渲染，整包镜头图片交用户审核后才可剪辑成片。不把“已提交”写成“已完成”。

若再次 UNKNOWN，保留新诊断结果并停止自动付费重放。新增的具体 API 错误类型记录仅改善定位能力，不代表已证明或消除了上游服务失败原因。

## 首次返回与同版返工

13:55:26 首次模型操作 COMPLETED，完整保存 16 镜。任务停在 NEEDS_INPUT / director，具体原因是第 3、7、8 镜关键词弹出层只写了 title，props 为空；缺少 keyword_required 所要求的 props.highlight 或 props.items[0]。没有发生 UNKNOWN，也未生成 r14 PNG。

用只读 SQLite 和生产校验函数离线核对原始候选，没有调用供应商、修改方案或生产数据库。时间线、阅读规则、素材覆盖规则、五套组件内容与布局均通过；原生组件校验复现上述三项遗漏。结果见 `photography-r14-candidate-validation-20261015.json`。这不等于渲染后的视觉审核通过。

13:59:43 经正常 `resume --decision confirm` 回复 **kind=input** 待办，保持 r14，提交 `photography-r14-layout-feedback-20261015.txt`。要求从本轮已完成的 16 镜候选继续，只纠正遗漏并实现已要求的收费行放大，不回退旧候选、改文案或重配音。此 confirm 是校验返工指令，不是逐镜人审通过。

返工命令 `cb53bdf9fbfa4832bb8fffe7994601fa`；新模型操作 `ffa0032d4b5c450a8de5d1f9a7ff4669`。UTF-8 要求原文、待办 token 和上轮完整候选哈希读回见 `photography-r14-input-repair-verification-20261015.json`。

## 实际渲染发现的容量问题

14:10 返工操作 `ffa0032d4b5c450a8de5d1f9a7ff4669` COMPLETED，16 镜时间线、摄影方案和 storyboard 已保存。关键词参数、收费行裁切、2249 帧切点和第14镜处理进展正文均已读回。引擎实际开始生成逐镜 PNG，14:10:14 因以下明确错误停止为 NEEDS_INPUT / director，没有 UNKNOWN：

`Remotion 渲染失败：ProgressSteps production slot 476x220 cannot fit 3 steps at 34px with at most two lines per step. Increase this slot or split the steps.`

对应第2镜 B12 的 support_2，实际绑定 items 三条：“报告披露：GTG-15001”“中国匿名工作室用Claude开发”“20多款交友App·用户在美国”。安全区 952×1304，槽宽0.5、高0.1687，换算为476×220。并非第1镜 A02（其步骤槽为571×241）。

使用现有 `production-text-fit.test.mjs` 真实 Chromium/Remotion DOM 测试复现：原尺寸明确拒绝；同文案476×320可完整容纳，检查每条不超过两行、字号至少34px及实际文字/标记不越界。13项字体回归均通过。这是容量验证，不是生产画面已生成或整体编排已通过。

同时发现通用恢复缺陷：DirectorDemoNode 对所有渲染异常均记录 retry_node=director_demo；普通 confirm 会重渲染原布局，无法把已知文字容量错误交回摄影。维护分支新增精确识别 ProgressSteps/WordFlip 已知容量错误的路由修复；旧待办也经正常 resume 恢复，不手改 pending、checkpoint 或审核记录。其他超时、Node缺失、素材不可读、PNG不完整继续由渲染节点处理，UNKNOWN 不据此重放。

回归先复现5失败/7通过，修复后新增16个边界用例及完整图内恢复路径通过；包括当前与旧格式渲染待办，确认最新完成候选、当前意见、真实音频/字幕保持，最终仍停逐镜人工门且不调用上游或成片渲染。相关63项Python测试通过，Ruff、TypeScript、ESLint、wheel构建通过。后续状态及实际生产续跑另行记录。

渲染错误待办 token：`75f87c849dfc4b02a0cacc05e17ac076`。修复意见见 `photography-r14-text-fit-feedback-20261015.txt`。截至此记录，完整16镜PNG包尚未生成，不可标记人审通过。

## 容量返工的正常续跑

维护修复提交 `5a883ab`（独立维护分支）。63项针对性Python回归、381项扩展CLI/节点/流程回归、13项真实字体DOM回归均通过；Ruff、TypeScript、ESLint、wheel构建通过。

14:23:05 通过正常 `resume --decision confirm` 回答上述 kind=input 旧格式渲染待办。命令 `39493ddba8664ed6a84fb69c899b1e8d`，模型操作 `977a646624a44cd8aa08e88a20a536f5`。没有手改待办路由，而是经已修复的 AwaitInputNode 回到摄影。1350字符UTF-8意见逐字匹配读回，最新完成候选 `ffa0032d4b5c450a8de5d1f9a7ff4669` 仍为 COMPLETED、16镜，正文 SHA-256 为 `08ed0b7bdb1621d654721733ae3a89737b05106dd1aa4f9f3a65a733b907aff7`。核验记录见 `photography-r14-text-fit-repair-verification-20261015.json`。

14:26 仍 RUNNING / director，新操作 SUBMITTING；当前已有时间线继续保留，尚未发布完整PNG审核包。模型返回后的校验、真实渲染结果另行补录。原37次历史操作、已审文案与12个素材文件持续只读核对保持。

14:33 模型操作 `977a646624a44cd8aa08e88a20a536f5` COMPLETED，真实渲染再次报同一476×220文字容量错误；没有 UNKNOWN，也没有完整PNG包。只读比较原始模型结果和SQL已保存时间线发现：模型只在第2镜 component_reason 声称“把Rve-ProgressSteps换成Rve-AnimatedList”，实际 parts 没有写可替换组件字段，也没有改变 box 或 items。B12 套内组件按固定目录绑定，只允许调整时间和box，故渲染器仍使用ProgressSteps。引擎没有丢弃尺寸修改；原始返回中就没有尺寸修改。比较证据见 `photography-r14-layout-result-comparison-20261015.json`。

这次待办 fields 已正确为 timeline/render、无 retry_node，证明 `5a883ab` 的线上失败分类已生效。没有重渲染同一方案来碰运气；先检查原始返回再给摄影补充固定套部件约束与实际容量参数。下一次意见见 `photography-r14-fixed-kit-feedback-20261015.txt`。

14:35:24 通过正常 resume 回复 kind=input 待办 `7a3995f553254ab5b942a9498706a3af`，保持r14，从最新16镜候选继续。命令 `0c920069c93348cc951d5c1aa9622a7d`，模型操作 `993966f781df4f8a9a87fad76d64be87`。848字符UTF-8意见逐字读回；候选 `977a646624a44cd8aa08e88a20a536f5` 正文SHA-256为 `78f16fb9a16607d1752805e200c81bb96fe5729459d78ce7048da8d0ba7a3eca`。见 `photography-r14-fixed-kit-repair-verification-20261015.json`。没有写入人工通过记录，没有额外修改公共代码或重新调用上游生产节点。

## 最终结果：实际16镜包已生成，画面尚未通过

14:49模型操作 `993966f781df4f8a9a87fad76d64be87` COMPLETED，正常渲染生成16张1080×1920 PNG。实际B12 support_2的box.height已由0.1687改为0.27，三条长文案完整显示。任务进入NEEDS_HUMAN / director，stage_review / per_shot_stills，待办令牌 `740b2b7c63dba8b621189b75edbce2f4`。本轮4次摄影操作均COMPLETED，没有新的UNKNOWN；这不代表旧r13上游错误原因已经消除。

16张图逐张打开检查，第3镜关键词重复、第5镜数字与标题重叠/长字裁切、第11镜六次重复截图、第13镜重复字裁切、第16镜英文占位词仍需处理。详见[实际逐镜观察](photography-r14-visual-audit-20261015.md)。结构校验和渲染成功不等于视觉质量通过，没有将图包标为合格。

## 飞书附件同步故障及修复

正常sync-review最初返回synced=true，只读回表却仍是旧图片。诊断确认维护工作目录在 `D:\remotion_video_unknown_repair_20261015`，真实产物在 `D:\remotion_video\.runtime`；lark-cli 1.0.97内置路径范围限制拒绝直接读取工作目录之外的文件，返回validation/invalid_argument/unsafe file path，退出码2。它不是用户授权缺失，也不是模型UNKNOWN。`_rewrite_table`又吞掉上传异常，导致同步成功失实。

维护修复 `87c541c`：上传前把原始文件字节暂存到CLI明确支持的账号临时目录，完成或失败后清理副本，不改变CLI文件访问规则；逐镜必需附件失败/缺失向上传递，不再报告全部同步成功。素材原有附件保留逻辑不变。4个新增回归先全部失败，修复后飞书/CLI/人工门74项回归通过，Ruff、TypeScript、ESLint和wheel构建通过。代码保留在独立维护分支。

随后只走正常sync-review，没有重新提交模型或重渲染。15:01完整回读确认16件当前图片均在对应镜头行中，文件名和字节大小匹配本地SHA核验过的原图。旧附件和旧shot-02b行保留，本轮只审shot-01至shot-16；监督诊断给首镜追加了一份本轮图片，同步后首镜存在两份相同当前附件，未将副本计成新镜头。没有下载远程文件重新算SHA。见[交付验证](photography-r14-feishu-delivery-verification-20261015.json)。

审核记录 `reczz28NapJQRJdS` 仍是逐镜/待审/意见空。没有poll、没有伪造用户确认或返工结论，没有进入剪辑成片或发布。最终只读快照再次确认已审文案、12个资产文件和原37次操作不变，旧r13操作仍UNKNOWN。实际文件见[逐镜PNG清单](photography-r14-shot-package-20261015.json)。
