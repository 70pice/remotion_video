# remotion-ui 来源与适配

- 上游：https://github.com/riaz37/remotion-ui
- 固定默认分支提交：`b7e0e6becc3d22b8b03dfef72c064f72ff9fad1f`
- 文件来源及原文件 SHA-256：见 source-files.json。
- 未运行上游安装脚本或构建脚本。

## 必要适配

- 复制三个 scene 及七个 lib 工具文件；将 @/remotion/lib 别名改为局部相对导入。
- 移除在线 Google 字体加载；正文改为 Microsoft YaHei UI / Microsoft YaHei / Arial / sans-serif，代码改为 Consolas / Courier New / monospace。字体字宽与原在线字体可能有轻微差异。
- 保留 DataFlowPipes、CodeReveal、AnimatedBarChart 的导出接口与动画逻辑；demo.tsx 使用中文流程和明确标注的演示数据。
- 未安装 registry CLI 或引入整套网站。
- DataFlowPipes 的 holdSeconds 注释称“进入后的保持时长”，实际实现用绝对时间 at(holdSeconds) 作为退出起点；演示省略此参数，确保流水完整运行且末帧保留流程图，不修改上游时间算法。
- 修复 code-syntax 正则的多余斜杠转义，新增 index.ts 具名导出三个 scene 及 props 类型。

## 版本边界

组件统一供 React 19 / Remotion 4 使用；所有 @remotion/* 包必须与主 Remotion 锁定同版。上游并未提供本项目的兼容保证，以本项目类型检查及渲染为准。默认演示使用本机字体和本地素材。源码中保留的示例代码、商标界面和工具计时均为动画内容，不表示真实 API 执行。
