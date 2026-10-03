# React 视频制作工作台

这是完整工作流的浏览器操作台，使用 React 19、TypeScript 和 Vite。页面通过 `/api` 调用 FastAPI，任务由独立 Worker 执行。

从项目根目录运行：

```powershell
npm run dev --workspace @videoagents/web
npm run typecheck --workspace @videoagents/web
npm run test --workspace @videoagents/web
npm run build --workspace @videoagents/web
```

开发地址为 `http://127.0.0.1:5173`，Vite 将 `/api` 转发到 `http://127.0.0.1:8000`。请同时启动 API 和 Worker，或使用根目录的统一启动脚本。

## 阅读 React 源码的顺序

1. `src/main.tsx`：把 `App` 挂载到 HTML 的 `root` 元素。
2. `src/app/App.tsx`：整体布局、导航、服务状态；`router.ts` 用 hash URL 切换页面。
3. `src/pages/CreateJobPage.tsx`：`useState` 保存表单值，`onChange` 更新它，`onSubmit` 通过 API 保存任务。
4. `src/pages/JobWorkspacePage.tsx`：六个工作区组合；通过 props 把任务、保存回调、执行命令传给子组件。
5. `src/features/script/ScriptEditor.tsx`：工作区自己管理未保存草稿，用 `base_revision` 防止覆盖新版本。
6. `src/api/useJob.ts`：`useEffect` 建立 SSE、轮询与清理；`useRef` 保存不会直接触发渲染的事件游标和请求序号。
7. `src/features/storyboard/StoryboardEditor.tsx`：把真实 Timeline 转成镜头卡片；纯函数 `timeline.ts` 保证拆分与合并后仍覆盖完整帧区间。
8. `src/features/render/RenderPanel.tsx`：原生 `<video>` 支持拖动和定位；`useRef` 获取播放器，审核问题通过 props 传入目标时间。

跨端类型来自 `contracts/generated/models.ts`，定义源在 Python contracts。修改契约后执行根目录生成脚本，不在页面中另维护一份模型。

## 状态与错误

- 每次读写先建立本机会话，写请求携带 CSRF 头。过期会话只用原始请求和原幂等键重试一次。
- SSE 断线后从事件 ID 重连，轮询继续读持久化任务；断线不会自动重启制作或付费配音。
- 未保存编辑切换六个工作区时继续保留；启动制作前须保存。关闭页面后通过后端恢复已保存版本。
- 草稿保存带旧版编号；409 冲突显示可理解说明，保留本地稿件供核对。
- 上传音频属于用户导入。手动字幕只接受用户实际测量的时间，初始文本不会生成估算时间。
- 配置中的密钥只写入后端，GET 返回配置状态。前端不把密钥写进 localStorage。
- “审核通过”要求存在当前版本最终视频，且视频 hash 与审核记录一致。
