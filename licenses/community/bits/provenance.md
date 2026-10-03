# bits 来源与适配

- 上游：https://github.com/av/remotion-bits
- 固定默认分支提交：`de35fda84b7b6acbe549a0b302a82ef211e8ef1e`
- 文件来源及原文件 SHA-256：见 source-files.json。
- 未运行上游安装脚本或构建脚本。

## 必要适配

- 复制四个示例及其二十文件本地依赖闭包；增加精简 core/index.ts。全部 remotion-bits 导入改为局部 core，不依赖上游 npm 包。
- 保留示例的 Component 导出，新增同名可复用别名；聊天与圆环数据、截图 URL、Ken Burns 图片与时长暴露为 props。
- CursorFlyover 将普通 img 改为 Remotion Img，使渲染等待素材；采用本地 staticFile(community/ai-ui.svg)，画布比率调整为 1280×720。
- KenBurns 的远程随机照片改为本地 staticFile(community/landscape.svg)，Tailwind bg-black 改为内联背景；演示将每段和转场时长缩短到 60/30 帧。
- CSS 主题变量增加本地 fallback；保留动画算法、Scene3D、StepResponsive 和帧驱动时钟。上游 registry 漏列 StepResponsive.tsx，已按真实源码闭包补齐。
- 不复制上游简化 culori.d.ts，使用 @types/culori；不引入 MCP SDK、Prism 或网站代码。
- 修复上游 StaggeredMotion 在 map 回调里调用 hook 的问题：每个子项改由独立 StaggeredChild 组件调用 useMotionTiming，不增加 DOM 层级；保留原始错峰、样式合并和帧进度算法。
- 清理未使用导入/变量，用 typed ReactElement、EulerOrder、Hold 类型守卫和动态配置字典替代 any；补齐 effect/memo 依赖。Scene3D 的 registerStep 保留计数职责，不改用实时计时器。
- @remotion/non-pure-animation 会对解构名称为 transition 的普通参数也报警；这些参数实际交给 useCurrentFrame 驱动的 motion helper。仅在相应参数行保留带理由的规则豁免，没有禁用目录规则或 hook 检查。
- 新增 index.ts，具名导出四个组件与对应 props 类型。

## 版本边界

组件统一供 React 19 / Remotion 4 使用；所有 @remotion/* 包必须与主 Remotion 锁定同版。上游并未提供本项目的兼容保证，以本项目类型检查及渲染为准。默认演示使用本机字体和本地素材。源码中保留的示例代码、商标界面和工具计时均为动画内容，不表示真实 API 执行。
