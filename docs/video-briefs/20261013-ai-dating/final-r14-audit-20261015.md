# AI付费社交欺诈：r14成片记录

- 任务：`08e74bed03e94c6e903c89f7f2fbea64`，revision `14`。
- 视频分支：`video/08e74bed03e94c6e903c89f7f2fbea64`。
- 用户在新版镜头2、3已交付后回复：“继续吧，下一步就时成片了吧”。结合此前通过意见，本次记录当前16镜整包确认并进入剪辑。原文与明确范围见 `final-r14-user-confirmation-20261015.txt`。
- 生产入口为 Python 图引擎的正常 `videoagents resume`，未直接调用配音、摄影或渲染 provider，未手改任务、checkpoint或审核标记。成片交付查看，不含发布授权。

## 首轮预检与恢复

整包确认命令 `d5aaebbe1da248acbbcb7fc1d33437d7`（幂等键 `cli-r14-all-shots-confirm-final-20261015`）已完成，真实人工审核回执为 `382dc6101f8ba4de1fb92ad3d40e9e4e`。

首轮剪辑模型调用 `53c2c9e7f0dc4f9ea3cc6df7adfd3b56` 正常完成，返回了一个阻断意见：要求镜头3采用早期画面需求单里提过的中文编程视频。该意见与用户后来明确不要编译器画面、改用与钱相关素材且确认新版代表帧的指示冲突。这不是超时或 UNKNOWN。

原因：旧剪辑上下文为避免历史快照干扰，过滤掉已应用的人工返工意见，导致剪辑只看见早期 `visual_need`，看不见后续真实视觉取舍。

通用修复单独提交于维护分支 `maintenance/unknown-classification-20261015`，提交 `7693484`：

- `videoagents/nodes/editing.py` 从真实同版本 `stage_review` 和匹配 token、note 的 `human_feedback_applied` 收据提取已执行意见；当前整包确认还须通过现有审核有效性校验。只传文字及绑定信息，不传旧文案、旧时间轴或其他checkpoint内容。
- `videoagents/prompts/editing.md` 明确后续人工画面取舍优先于早期采集偏好，同时继续检查事实误导、来源混用、素材不对应、越界、字幕和不可渲染等实质问题。
- 46项相关 Python 回归通过，ruff及diff检查通过。包含实际图流程的正常续跑测试：首轮阻断后，仅更新剪辑契约，通过普通 `resume confirm` 再跑剪辑，禁止摄影与配音被调用，原阻断记录及冻结输入不变。另已通过 TypeScript 类型检查和 lint。

正常恢复命令 `2c5c725973794ab692e4bdd16c805409`（幂等键 `cli-r14-editing-recheck-human-direction-20261015`）由既有过期剪辑意见恢复路由进入剪辑，未更改审核状态或摄影方案。恢复说明见 `final-r14-editing-recheck-note-20261015.txt`。本轮第二次剪辑调用为 `385328428a954492b96b8c0d56652b49`；首轮检查同样发生了模型调用，不能从成本记录中抹去。

首轮完整意见和原始产物哈希保存在 `final-r14-first-preflight-block-20261015.json`；冻结基线保存在 `final-r14-before-render-baseline-20261015.json`；持续状态在 `final-r14-render-monitor-20261015.jsonl`。

## 实际成片与交付

第二次剪辑预检正常完成，无阻断finding，正常渲染随后完成。恢复命令状态 `DONE`，任务为 `DRAFT / complete`，无待输入；该状态表示成片已生成，不能解释为可以发布。

- 实际视频：`D:\remotion_video\.runtime\videoagents\jobs\08e74bed03e94c6e903c89f7f2fbea64\revisions\14\renders\c1fd902219654394bd4f52e0fd2e72d4\final.mp4`。
- 视频产物：`c63c5cb365594fa093870dc4e8ff1565`；封面产物：`27301253e9fa45a3a1ff0511b3c19932`。
- 规格：1080×1920，30fps，3714帧，123.8秒；文件20,151,013字节。
- SHA-256：`766ed5da5657cc05466e9a51008df0884bea51a5256e70bc31bc0959bce9538c`。
- 视频与音频均可完整解码，音频非静音，时长匹配。视频、封面注册哈希一致。文案、素材、时间轴及原44次操作记录与冻结基线一致；本轮实际有两次已完成的剪辑模型检查，没有新摄影/配音调用。首轮阻断意见原文件仍保持原始哈希。
- 从实际MP4抽出全部16镜的审核代表帧，与已确认PNG比较，最低SSIM为0.990234。共19项文件、流程与一致性检查通过，详情见 `final-r14-render-verification-20261015.json`。

### 画面检查的实际限制

逐张查看全部16个实际MP4代表帧及封面后，仍发现4项问题，详见 `final-r14-visual-inspection-20261015.json`：

1. 镜头6有重复信息，部分辅助标签很小。
2. 镜头11把同一收益长图重复成六个缩略图，金额难以阅读。
3. 镜头13左下辅助组件有重复文字在边界被截断。
4. 镜头16结束卡仍显示模板英文占位字 `next action`。

这些问题同样存在于此前已确认的代表帧中，不是视频编码导致。已在交付消息里明确披露主要问题；未将文件检查通过、人工旧帧确认或模型无阻断等同于发布前画面质量通过。当前版本不具备已通过发布前画面检查的结论。只做了代表帧视觉查看与媒体解码检测，没有声称完整动态播放或人工听审。保留已确认输入，未未经流程重写画面或偷偷修改审核记录。

### 飞书实际交付

通过 BotMux 仅发送一次成片与封面。BotMux返回的是说明卡片ID，视频作为独立media消息发出；后续精确查询两个ID，避免把说明卡片送达误当作视频送达。

- 说明卡片：`om_x100b623e75c818b0c1360857d4b5dfe`，完整正文匹配。
- 视频消息：`om_x100b623e759d30b0c138320f72893e0`。
- [群内成片审看版](https://applink.feishu.cn/client/chat/open?openChatId=oc_34b61a867da7f3916adeb716200f9794&position=233)。
- 两条消息均在原群 `oc_34b61a867da7f3916adeb716200f9794`，发送者是video agent，未删除；精确回读视频消息确认一个MP4及其封面。又从该精确消息下载视频，文件大小与SHA-256均和本地实际渲染产物一致。
- 脱敏交付凭据：`final-r14-group-delivery-20261015.json`。文件key、图片key及原始返回仅留TEMP，不写进任务文档。

交付为成片审看版，尚未发布，也未伪造发布审核通过。
