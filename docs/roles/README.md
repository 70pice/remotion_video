# 角色条例索引

本目录每个角色一篇启动条例。在这个项目目录启动的任何 Agent(或人),先按身份读对应的一篇,再看
[AGENTS.md](../../AGENTS.md) 的全局制作规则。角色之间的区别一句话:**导演只监督不创作,操作者只修
系统不碰产线,六个生产角色由引擎无头调用、只对自己的阶段负责。**

| 角色 | 启动方式 | 条例 | 一句话职责 |
| --- | --- | --- | --- |
| 导演(监督) | 你在项目根手动开强模型 CLI 会话(GPT-6 Astra / Opus 5.5) | [director.md](director.md) | 建/驱动/监控任务,呈递文案、文案与素材、逐镜三个人工门,失败恢复与上报;不创作、不代替人工确认 |
| 操作者(修护) | 你(或 GPT-6.1 Sol 会话) | [operator.md](operator.md) | 改共性代码、跑回归、走正常续跑入口修问题;不手改数据库、不绕过节点 |
| 编剧 | 引擎自动调用(GLM) | [screenwriter.md](screenwriter.md) | 流水线最前:检索来源、设计段落与口播、交画面需求清单 |
| 素材 | 引擎自动调用(GLM) | [materials.md](materials.md) | 按文案清单核验来源、下载真实画面、冻结素材、记录缺口 |
| 配音 | 引擎自动调用(GLM + 字节 TTS) | [voice.md](voice.md) | 表演指导先行,字节 expressive 合成,实测时间戳 |
| 摄影 | 引擎自动调用(GLM) | [cinematography.md](cinematography.md) | 镜头设计、组件选择、逐镜代表帧渲染 |
| 剪辑 | 引擎自动调用(GLM + Remotion) | [editing.md](editing.md) | 冻结素材、渲染成片、渲染前预检 |

人工审核界面是**飞书多维表格**(一个视频一个 Base,见 [feishu.md](feishu.md));命令行 `resume` 是飞书
不可用时的兜底。原 Web 工作台已于 2026-10-13 移除。
