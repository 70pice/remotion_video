# r15 第一镜固定手机框内轮播：返工与交付

任务 `08e74bed03e94c6e903c89f7f2fbea64`，任务分支 `video/08e74bed03e94c6e903c89f7f2fbea64`。本记录接续此前 `visual-r15-opening-audit-20261015.md`；前一版本的第一镜已被用户退回。

用户消息 `om_x100b623f475c18a0c013ec201e7c215` 明确通过第二镜、退回第一镜：要求在同一个地方轮播，而不是换镜头。前一包的19镜方案仅为历史候选；本次恢复16镜，等待新一轮人工逐镜审阅，没有自动确认整包。

## 结果与验证

- 第一镜只有一个 `shot-01`，原0–330帧（11秒）窗口、`Snapcn-PhoneFrame`、标题、正文、主素材及强调色保留。屏幕内部四张真实中文图片在局部0/83/166/249帧轮换，交叉淡化8帧；外框、标题与入场连续。后三张为contain整图，手机屏幕内有留黑，不冒充实拍视频。
- 第二镜为用户刚通过的r15版本；第二至第十六镜全部字段逐项相等。文案、素材集合、音频、字幕、画幅、总3714帧及30fps未改。返工前48条操作记录的整行哈希均未改。
- 正常摄影和渲染节点生成16张1080×1920逐镜PNG及24.5秒连续预览；预览为既有半尺寸540×960。完整解码通过；实际查看四张换图中间帧、第一处交叉淡化帧、全尺寸第一镜PNG。标题、来源与外框连续，无反复入场、裁掉弹窗主体或新增文字重叠。双屏截图的小标签在半尺寸预览仍较小，不声称所有图内小字均清楚可读。
- 当前timeline：`revisions/15/timeline-9d6a4d7a.json`。审核包：`revisions/15/shot-reviews/9d672cb97da445868ad01eb02e9adecf/director-shot-review.json`，artifact `17df44c853be48c5a36df3af720bf368`。
- 实际预览：`D:\remotion_video\.runtime\videoagents\jobs\08e74bed03e94c6e903c89f7f2fbea64\revisions\15\renders\44990a0bbdda4d50b7c99f04f9b39851\preview.mp4`，artifact `92fde019ca4e4782bbba536cadb6c033`，SHA256 `272bea2db3ee9e3960f6017852f73a09a5bb416e5333d7b98ef04694b11b05ec`。
- 群内只发送一个连续视频：[实际消息](https://applink.feishu.cn/client/chat/open?openChatId=oc_34b61a867da7f3916adeb716200f9794&position=244)。说明消息 `om_x100b623f36acf0a4c04e83ae4def3de`，视频消息 `om_x100b623f365d40b0c0ed3f58551a6ac`。精确回读身份、群及正文，下载视频哈希等于本地文件。

## 流程和实际阻断

1. 在原人工门通过 `resume --decision revise` 正常返工，命令 `e623954d49af46f9bced8dd45a7d55e6`，摄影操作 `f8592b77e53940f9b5cc5e1399175c92`。候选已正确生成单镜内轮播，但来源写成 `news.cnr.cn/time-weekly.com`，精确域名规则把后半段视为前一网站路径，进入NEEDS_INPUT；没有跳过该校验。
2. 通过输入恢复仅纠正来源分隔符为中文竖线，命令 `c9e910cd66af4a05ab6f926f0090085d`，摄影操作 `2092a1da39594abcbdbd1a59028526c3`。两次保存的模型结果对比证明只修改第一镜来源标签。随后真实渲染遇到来源标签单行容量不足，进入渲染输入暂停。
3. 通用组件修复后，正常 `resume --decision confirm` 仅续跑既有 `retry_node=director_demo`，命令 `51adc23291ea4ca69d4207a5e23c42fc` DONE。没有新增模型操作，没有再次请求摄影或重配音；confirm只恢复输入，未授予逐镜审核通过。

本次新增的两次模型操作均COMPLETED，使用Claude Code的`glm-5.3[1m] / xhigh / 1000000`配置；不是UNKNOWN，不重放任何未决提交。代码修复在独立维护分支，任务分支仅记录证据，没有手写生产timeline、直接调用provider或修改数据库。

## 共性代码与回归

- 维护提交 `c42d0cd`：普通PhoneFrame的正式`media_slides`多图槽位；每页校验真实图片、显示时间与旁白/批准关系；渲染器收集全部图片。更新摄影知识库和生产提示，明确固定位置轮播不能以拆镜替代。保留原单图、视频、教学路径。
- 维护提交 `aa6a550`：轮播的多来源标签可在原54px来源区域内换行；传统单图/视频仍保持原单行行为。实际来源文案先红后绿，不隐藏文字、不取消容量检查。
- 全量Python：1674 passed，3 skipped（真实浏览器集成需显式启用、Windows账号不可创建符号链接）；最后前端全量141 passed。typecheck、lint、ruff、生成契约、生产组件manifest和路径检查通过。维护树未生成可选组件飞书工作簿payload；未据此声称核验工作簿内容。

当前状态 `NEEDS_HUMAN / director`，待审token `cb043115a15446685fda142deadc0336`。本次新包未获整包确认，未渲染新完整成片、未发布。基线、监控、反馈、机器核验及交付收据见同目录 `visual-r15-fixed-carousel-*` 文件。
