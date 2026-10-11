# 生产图精简（2026-10-10）

2026-10-07 的“只保留文案人工审核、导演直接进入剪辑”已成为历史说明。2026-10-10 起，默认生产图恢复一个窄口径的导演 Demo 人工审核，但不复活旧 `timeline_gate`、`human_review_timeline`、`human_review_render`、`reviewers`、`review_gate` 或最终发布审核链。

当前主流程：

```text
START → materials → screenwriter ↔ script_reviewer
      → human_review_script → after_script_review → voice → audio_gate
      → director → director_demo → director_human_gate
      → after_director_demo_review → editing → END
```

每个制作角色仍经过对应的 `clear_*`；失败及缺少输入仍进入 `await_input`。`director` 只负责设计：输出经校验的 `shots`、逐段表演方案 `segment_performances`，以及用于 Demo 的原时间轴连续帧范围 `demo`。`director_demo` 用真实时间轴渲染最长 30 秒 Demo；`director_human_gate` 人工确认后才进入 `editing` 渲染完整成片。

## 当前合同

1. 文案人工确认后才进入配音；配音保留真实音频和 provider/人工对齐时间戳。
2. 导演读取实测字幕、素材和组件知识库，写入 `timeline` 与 `director_plan`。`director_plan` 绑定当前 timeline fingerprint，包含 `shots`、逐段表演、组件选择理由和 `demo: {start_frame, end_frame, reason}`；不得修改音频、字幕或用其他任务产物。
3. `director_demo` 按 `director_plan.demo` 渲染真实 Demo，范围是原 timeline 的 end-exclusive 连续区间，长度不超过全片或 30 秒。预览目标本身在 Demo 生成后结束为 `DRAFT`，不自动生成审核通过记录。
4. `director_human_gate` 审核当前导演方案和 Demo。`confirm` 后进入 `editing`；`revise` 回到 `director`，保留匹配的音频和对齐信息，让导演重做镜头/表演/Demo 方案；`cancel` 结束任务。旧 token、旧 revision、内容或文件 hash 变化都会 fail closed。
5. `editing` 只在当前导演 Demo 审核仍有效时渲染完整成片；旧 checkpoint 直接落到 `editing` 也会被送回 `director_demo`。完整成片以 `DRAFT` / `complete` 结束，不创建最终发布审核通过记录。
6. `storyboard` 只让导演完成设计后结束，不渲染 Demo 或成片；旧 `review` 动作仍按已移除审核链处理。

## 历史精简范围

2026-10-07 删除的旧时间轴/成片审核链仍保持删除状态：`timeline_gate`、`human_review_timeline`、`human_review_render`、`reviewers`、`review_gate`、`clear_reviewers`、`after_timeline_review`、`after_render_review` 不在当前生产图注册。历史审核类和数据契约可继续读取旧记录；新生产图不注册或执行成片审核节点。发布仍是工作流之外的操作。

真实制作必须通过任务 API → Worker → `VideoProductionGraph` 正常续跑。历史独立 demo 脚本、手写分镜、直接渲染 provider 或改数据库审核标记都不是生产入口。
