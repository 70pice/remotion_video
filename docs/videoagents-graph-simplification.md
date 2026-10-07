# 生产图精简（2026-10-07）

按用户本次决定，生产流程只保留文案阶段的人工审核：

```text
START → materials → screenwriter ↔ script_reviewer
      → human_review_script → after_script_review → voice → audio_gate
      → director → editing → END
```

每个制作角色仍经过对应的 `clear_*`，失败及缺少输入仍进入 `await_input`。

## 修改计划

1. 先用拓扑、文案确认后连续制作、暂停恢复和阶段动作回归锁定预期行为。
2. 移除 `timeline_gate`、`human_review_timeline`、`human_review_render`、
   `reviewers`、`review_gate`，及失去用途的 `clear_reviewers`、
   `after_timeline_review`、`after_render_review`；同步角色返回的路由。
3. `storyboard` 在导演完成后结束；`preview` 在预览生成后结束；
   `produce` / `final` 在成片生成后以 `DRAFT` / `complete` 结束。
   时间轴及素材的程序校验仍在导演、剪辑节点执行。
4. 保留文案确认、返工和取消；保留缺素材、配音失败等输入待办及恢复。
   旧成片审核待办结束为草稿，提示重新提交制作；旧 `review` 动作不再调用审核。
   制作完成不创建审核通过记录，也不自动标记 `READY_FOR_PUBLISH`。
5. 更新生产约定及使用说明，执行对应回归、Python 静态检查、契约检查、
   Remotion/React 类型检查、lint 和前端构建。

历史审核类和数据契约可继续读取旧记录；新生产图不注册或执行成片审核节点。
发布仍是工作流之外的操作。
