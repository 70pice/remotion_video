# CLAUDE.md

本项目的全局制作规则、角色条例与最新架构约定都在 [AGENTS.md](AGENTS.md)(含账号定位、生产流程、
飞书工作流与模型约定)。启动后按身份先读对应角色条例:[docs/roles/](docs/roles/README.md)
——导演(监督会话)、操作者(修护)、编剧/素材/配音/摄影/剪辑(引擎无头生产角色)。

快速事实:本仓库通过 `videoagents` CLI 驱动 Python 图引擎制作抖音竖屏科普视频;无 Web 前端
(2026-10-13 移除);人工审核在飞书多维表格(`videoagents poll` 读回决定);生产模型为智谱
`glm-5.3[1m]`(Claude Code CLI);渲染用 Remotion(`npm run test:timeline` 等检查)。
