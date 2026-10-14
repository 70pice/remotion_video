# 排版修复验收与原任务接续准备

任务 `08e74bed03e94c6e903c89f7f2fbea64`，当前r11。用户指出首两镜文字硬塞、裁切与编排不合理。GLM生成的是摄影配置，实际排版由现有Remotion组件执行；修复既需要真实槽容量约束，也需要摄影重新安排信息与镜头。此文只记录已验证的通用修复，不代表视频画面通过。

## 独立维护提交

代码工作区 `D:\remotion_video_text_capacity_20261015`，分支 `maintenance/video-text-capacity-20261015`，HEAD `da5f3c7`。视频分支仍为 `video/08e74bed03e94c6e903c89f7f2fbea64`，未混入维护改动。

| 提交 | 通用改动 | 实际验证与边界 |
| --- | --- | --- |
| `6dfb625` | `adapters/index.tsx`为大数值开启已有FittedText单行优先；`TalkcraftNativeTitles.tsx`去掉与关键词完全相同的前缀 | 6项真实DOM测试：两周、至少25000人等不拆单位，保持24px字号下限；不可能容纳的数值明确报错；关键词只出现一次，正常前缀和正文保留 |
| `9961797` | `VideoFromTimeline.tsx`竖屏无叠层PIP使用同一个实际内缩值计算卡宽和文字宽度 | 原标题按880px量测而卡宽768px，真实右侧溢出17px；4项DOM测试通过，长标题至少32px且来源留在卡内，短标题及有叠层布局作为控制组 |
| `da5f3c7` | `ProductionComponentSetScene.tsx`传实际槽宽高；ProgressSteps和WordFlip生产模式等待字体加载后量测实际DOM，按当前文本/槽变化重新量测 | 11项测试通过，步骤字号下限34px、翻词42px，最多两行；运动行程和最长词同时计入容量，翻词25个动画帧检查；普通组件默认行为保留 |

三个切片各自在修改前建立了能稳定失败的真实渲染回归。生产小槽A02步骤456×210不能容纳原长文时，现在明确报错；改为456×320的测试布局可容纳。该测试布局不是手写生产分镜。B12原476×220步骤和456×220翻词测试可容纳。容量错误要求摄影增大槽、拆信息或换合适组件，不允许以任意缩小字号掩盖。

## 整合后的新鲜验证

在维护HEAD `da5f3c7` 上完成：

- `npm run test:timeline`：129 passed。
- `npm run typecheck`、`npm run lint`、`npm run check:production-components`、`npm run check:component-paths`通过；路径检查187对/374入口，未缺失组件源文件。
- Python相关回归119 passed：`test_director_component_sets.py`、`test_director_model_contract.py`、`test_director_shot_review.py`、`test_shot_review_contract.py`、`test_shot_review_render.py`。
- 真实生产入口 `src/video-production/index.tsx` 经现有 `@remotion/bundler` 构建通过，bundle在 `C:\Users\70pic\AppData\Local\Temp\videoagents-text-capacity-bundle-A7HKY3\bundle`；该构建没有调用模型、配音或渲染本视频。
- `git diff --check`通过，维护工作区干净。没有新增依赖。

测试锁定特定组件的排版容量与控制组行为，不等于所有画面都已美观或手机可读，也不替代整包人审。当前方案的五张重复图片、来源重复、模板英文、媒体模式不展示items、字幕切点等仍须正常摄影节点重新编排。

## 本次摄影真实停止

操作 `a290785969554baab4bb2cebbbcd9c42`，模型 `claude_code_cli / glm-5.3[1m] / xhigh`。约32分钟后退出码1，诊断为`cli_nonzero_exit`；stdout为`claude_error_result`，没有可用response_json，具体供应商错误原因未保留。配置超时3600秒，本次不是超时。已退出的Claude进程12876不再存在，对应会话元数据文件不存在。

00:17只读GET额度返回HTTP200，两个使用比例3%与45%，均有剩余。此查询没有生成请求，不能证明该笔操作是否消耗额度或排除此前瞬时故障。UNKNOWN原状态和台账保留。

停止后复验：原Brief、七段已审文案与12件素材/音频文件保持，前33笔操作与16+17张历史PNG散列保持。本轮有效方案和新PNG为0；上轮17图仍被退回，未用修复后代码重渲，未确认逐镜门或制作成片。

## 已准备的正常接续

[严格只读证明](photography-fixed-capacity-preflight-20261015.json)在修复后的代码工作区读取原权威runtime。现有批准链和真实音频成立，已证明r9操作`f1dcf1682a9c495289753483ce926b03`的16镜候选可作为修复底稿。数据库、checkpoint和读文件保持；没有模型/生产provider调用。预检记录了一次被守卫阻止的网络尝试，没有执行网络提交。

桥接继承的是已证明的原16镜候选；最新17镜已保存timeline不属于该桥接的逐字段冻结对象。新摄影应保留开场/收益截图放大、25万元单位、中文结尾等已见改善，同时按最新意见重排。不能声称新方案已经保留所有17镜或已经通过。

获得针对新UNKNOWN的明确可能用量确认后，由维护工作区的正常CLI显式使用 `--runtime-dir D:\remotion_video\.runtime\videoagents`，先`restart-unknown --director-only`保存同任务新版，再`run`。已核对该CLI从维护工作区加载Python节点和Remotion生产入口，原runtime仍为权威数据源。该入口保留原文案、素材、真实音频与飞书Base，跳过编剧、素材与配音，摄影出图后仍停整包审核。

当前未执行上述恢复或修改模型档位。保留用户明确选择的`xhigh`，不通过改设置绕过UNKNOWN。根据[项目未决提交规则](../../videoagents-unknown-restart.md)，新UNKNOWN须重新取得可能用量确认；[摄影要求草稿](photography-fixed-capacity-recovery-draft-20261015.txt)尚不是授权记录。
