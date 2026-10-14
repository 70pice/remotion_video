# 摄影输入确认补充意见传递修护

问题：正常摄影校验失败后的 `resume --decision confirm --note ...` 会把意见保存在
`human_decision`，但摄影模型的字段投影不包含它，导致补充的业务修复要求丢失。

小计划：

1. 用已有真实图的同 revision 摄影修复回归，在模型输入捕获处证明 note 丢失。
2. 仅在 `DirectorNode.plan` 构造模型输入时，核对当前 `pending_snapshot` 是
   `input/director`、非空待办 token 与 confirm 的 token 一致、存在当前外部校验问题；
   只把非空业务 note 投影到 `extras.timeline_repair_note`。
3. 只在有效 note 路径追加读取说明；空 note、人工逐镜门、其他角色和旧 token 不带入。
   不把确认意见作为人审通过，不改候选来源证明、正常修复回执、未知提交屏障或完整输出校验。
4. 验证正常入口仍复用同 revision 的最新 COMPLETED 候选、真实音频及字幕，不重做上游；
   跑新增边界及相关候选/修复/指纹回归，再检查 Ruff、compileall、契约与 diff。

维护在独立 worktree，基于 `74597a7`；不读取凭据、真实任务/数据库/checkpoint，
不调用生产模型、配音、渲染或飞书，不修改任何已有业务响应。

验证使用 `D:\remotion_video\.venv\Scripts\python.exe`，工作目录为独立维护 worktree，
`PYTHONUTF8=1`。所有模型/代表帧均为本地测试替身。

- 修复前：`-m pytest -q tests/videoagents/test_director_repair_receipt.py::test_first_rejected_director_candidate_resumes_with_frozen_audio_and_completed_receipt`
  为 **1 failed / 1.04s**；真实图第二次模型输入的 `timeline_repair_note` 为 None。
- 同一命令修复后 **1 passed / 1.11s**。
- `-m pytest -q tests/videoagents/test_director_repair_receipt.py`：**17 passed / 1.53s**，
  覆盖正常确认续修、14 组绑定/排除边界、没有/空意见时模型请求及指纹不变，
  非空有效意见改变指纹；旧 extras note 不泄漏，模型不接收人工批准账本。
- `-m pytest -q tests/cli/test_director_candidate_continuation.py -k 'normal_restart_run or candidate_discovery_is_read_only or pure_request_fingerprint'`：
  **7 passed / 8.25s**；正常 CLI 确认 note 进入修复请求，仍接续原候选并跳过上游与成片，
  UNKNOWN 屏障和原指纹算法保持。
- `-m ruff check videoagents/nodes/director.py tests/videoagents/test_director_repair_receipt.py tests/cli/test_director_candidate_continuation.py`：通过。
- `-m compileall -q videoagents/nodes/director.py`、`scripts/export-contracts.py --check`、
  `git diff --check`：通过。没有新增依赖、全局契约或组件变动。

只在模型输入的私有副本中携带意见，不写回共享 extras 或生产状态。
同 revision 的最新 COMPLETED 候选选择与完整响应校验保留原行为，
意见不等于逐镜人审通过，不解除未知提交屏障。
