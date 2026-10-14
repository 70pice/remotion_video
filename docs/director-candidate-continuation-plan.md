# 摄影完成候选的有证据接续

本次只修共性恢复路径，不操作生产任务、模型、凭据或真实数据库。

1. 使用既有摄影恢复 fixture 经正常 `restart-unknown → run → resume`：摄影完成回执因阅读时长失败，修复请求再 UNKNOWN，然后摄影独立恢复版本。新请求必须包含完成候选而不是空白基线；先观察此断言失败。
2. 只沿同任务摄影恢复的批准与输入链追溯 COMPLETED 回执，以真实摄影请求构造复算原 input_hash。保存候选来源、完成结果指纹、当前已审上游与模型配置依据。找不到完成候选维持原路径；存在但不能证明则阻断。
3. 新摄影请求在已证明候选上修复明确问题，保留无问题镜头；完整输出继续走原契约、阅读、素材、代表帧和人工审核。
4. 覆盖跨版本、多次恢复、错误任务/回执/业务输入/模型/资产变化及原 UNKNOWN 屏障；运行相关回归、Ruff、契约检查与 diff 检查。

旧 COMPLETED/UNKNOWN 不改写；候选不构成有效 timeline 或人工通过。代码不会自动调用生产模型。

## 验证记录

确定性红测命令：

```powershell
python -m pytest -q tests/cli/test_director_candidate_continuation.py
```

实现前 `test_normal_restart_run_continues_completed_candidate_without_rebuilding_upstream[sixteen_shots]`
实际失败：旧16镜未进入新摄影请求，预期逐镜人工门 `NEEDS_HUMAN`，实际 `NEEDS_INPUT`。
结果 `1 failed in 3.85s`。实现后第一次同测试 `1 passed in 4.96s`；全部新边界补齐后，
对当前完整候选测试文件的新鲜验证为 `24 passed in 56.46s`。

相关回归命令：

```powershell
python -m pytest -q tests/cli/test_director_candidate_continuation.py tests/cli/test_director_only_restart.py tests/cli/test_approved_context_media.py tests/videoagents/test_director_repair_receipt.py tests/videoagents/test_director_model_contract.py tests/videoagents/test_providers.py tests/videoagents/test_glm_cli.py tests/videoagents/test_cli_models.py
```

结果 `291 passed in 243.61s`。此轮之后补充的 UNKNOWN 部分输出、已有有效 timeline 与错 revision
选测为 `3 passed in 11.64s`；纯指纹旧算法一致性与非法 GLM 非凭据身份选测为
`8 passed in 0.31s`，均已包含在最终24项新鲜验证中。

修改 Python 文件 Ruff、compileall、`scripts/export-contracts.py --check` 与 `git diff --check` 均通过。
没有新增依赖、全局 schema 或组件库修改。所有模型、配音、逐镜渲染均为临时仓库中的本地测试替身；
通过真实 CLI/图、请求指纹与现有验证入口，使用真实本地 WAV/PNG 检查阶段边界。

本修复保留完整模型响应接口：旧候选作为底稿，原完整校验保留。测试证明这份16镜底稿到达模型，
以及该测试返回的14个未受边界影响镜头逐字段未改变；生产接口没有新增强制冻结/局部 patch 契约。
本地验证不是实际视频任务成功，也不构成新提交、配音、逐镜门或成片的批准。
