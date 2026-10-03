# remocn 来源与适配

- 上游：https://github.com/Remocn/remocn
- 固定默认分支提交：`8ae853e4c08108105684d4b8cac7f22400840d2a`
- 文件来源及原文件 SHA-256：见 source-files.json。
- 未运行上游安装脚本或构建脚本。
- 新增 index.ts，具名导出五个组件、props 类型及必要的时长计算 helpers。

## 必要适配

- 复制五个组件及 ChatGpt 的 caret 和六个共享 core 文件；将项目别名改为局部相对导入。
- 移除 ChatGpt 模块中的在线 Google 字体加载，使用 Microsoft YaHei UI / Microsoft YaHei / Arial / sans-serif 真实字体栈。
- 保留组件导出与帧驱动动画；demo.tsx 提供无必填参数的演示包装与中文示例。Agent 的默认演示明确标注模拟执行。
- 未引入网站 Next.js、fumadocs、分析埋点和后端代码。

## 版本边界

组件统一供 React 19 / Remotion 4 使用；所有 @remotion/* 包必须与主 Remotion 锁定同版。上游并未提供本项目的兼容保证，以本项目类型检查及渲染为准。默认演示使用本机字体和本地素材。源码中保留的示例代码、商标界面和工具计时均为动画内容，不表示真实 API 执行。
