# GLM Coding Plan 与 Claude Code

2026-10-13 的生产模型约定：七个模型角色 `materials`、`screenwriter`、`script_reviewer`、`voice`、`director`、`editing`、`review` 均使用 Claude Code CLI 的 `glm-5.3[1m]`，默认最高推理 `max`，上下文窗口 `1,000,000` tokens。用户明确选择 extra high 时，通过公开 Settings 字段 `glm_reasoning_effort` 设置为 `xhigh`，所有 GLM 角色与配音指导统一采用该档位。`xhigh` 与 `max` 是不同档位，旧安装未设置该字段时仍使用 `max`。保留 `review` 的配置兼容性，不因此新增生产图节点。实际语音合成继续使用已配置的字节 TTS；`voice` 角色负责其表演指导。

GPT-6.1 Sol 由操作者会话负责监控任务事件、定位失败、修复共性代码并通过现有补充/续跑入口推进。模型角色的替换不代表新增全天守护进程，也不绕过文案人工确认和逐镜 PNG 审核。

## 本机配置

1. 使用当前 Claude Code 安装方式升级。已有 WinGet 安装使用 `winget upgrade --id Anthropic.ClaudeCode --exact`；升级后用 `claude --version` 验证实际版本。智谱接入文档要求至少 2.1.140，具体以当前安装器和 CLI 行为为准。
2. 在系统设置中填入智谱 Coding Plan API Key。密钥按平台加密保存在运行数据库：Windows 使用当前账户的 DPAPI，macOS 使用 Keychain（服务名 `VideoAgents`），其他平台回退 base64；公开 Settings 仅返回是否已配置，旧的 `local:` 记录仍可读取。密钥不写入角色输入、命令参数、仓库或工具审计。
3. 七个角色启用 Claude Code CLI、选择 `glm-5.3[1m]`。新安装的角色默认值已统一；已有数据库保留原配置，需通过 Settings 服务修改。旧豆包 Claude 兼容路由仍可明确选择，GLM 路由不会因豆包 Key 已存在而改用豆包。GLM 子进程默认使用智谱官方 endpoint `https://open.bigmodel.cn/api/anthropic`，需要覆盖时设置 `VIDEOAGENTS_ZHIPU_BASE_URL` 环境变量。
4. 通过 `videoagents settings set glm_reasoning_effort xhigh` 更新推理档位，再用 `videoagents settings get` 回读。字段只接受 `xhigh` 或 `max`；模型与 1M 上下文保持原约定。
5. 确认搜索入口、截图能力及原有字节 TTS 配置仍可用，随后通过 `videoagents` CLI 发起生产。仅修改模型配置不能证明真实工具调用或最终视频制作已完成。

macOS 等价说明：Claude Code 按所用包管理器（npm、brew 等）安装与升级，同样以 `claude --version` 验证；下文的 `%USERPROFILE%\.claude\settings.json` 对应 `~/.claude/settings.json`；`winget upgrade` 替换为所用包管理器的升级命令。项目保存在运行数据库中的密钥在 macOS 使用 Keychain（服务名 `VideoAgents`），同样只进入本机私有配置。

独立使用 Claude 时，合并 `%USERPROFILE%\.claude\settings.json` 的 `env` 配置，不覆盖已有设置。主要配置如下，Key 只填入本机私有文件：

```json
{
  "model": "glm-5.3[1m]",
  "env": {
    "ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "<自己的 Coding Plan API Key>",
    "ANTHROPIC_MODEL": "glm-5.3[1m]",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3[1m]",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.3[1m]",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.3[1m]",
    "CLAUDE_CODE_SUBAGENT_MODEL": "glm-5.3[1m]",
    "CLAUDE_CODE_EFFORT_LEVEL": "max",
    "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1000000",
    "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "1000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "ANTHROPIC_DEFAULT_OPUS_MODEL_SUPPORTED_CAPABILITIES": "effort,xhigh_effort,max_effort,thinking,adaptive_thinking",
    "ANTHROPIC_DEFAULT_SONNET_MODEL_SUPPORTED_CAPABILITIES": "effort,xhigh_effort,max_effort,thinking,adaptive_thinking",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL_SUPPORTED_CAPABILITIES": "effort,xhigh_effort,max_effort,thinking,adaptive_thinking"
  }
}
```

关闭旧的 `CLAUDE_CODE_DISABLE_1M_CONTEXT`，处理已有 OAuth、API Key 或其他云路由与上述认证的冲突。自定义模型的能力声明用于让 Claude 真正发送推理档位；持续档位使用 `CLAUDE_CODE_EFFORT_LEVEL`，单次调用使用 `--effort max` 或 `--effort xhigh`。选择 `xhigh` 时，独立 Claude 配置的环境变量也改为 `xhigh`，并保留 `xhigh_effort` 能力声明。不要把不接受 `max` 的 `effortLevel` 设置当作等效配置。项目按 `glm_reasoning_effort` 为 GLM 子进程同时注入参数与环境变量，因其隔离运行不读取用户全局 Settings，不依赖全局文件偶然生效。操作台账与请求指纹记录所选档位，切换档位不会误复用另一档的已完成结果，也不能绕过同角色同版本的 `UNKNOWN` 提交屏障。

`[1m]` 用于 Claude 的上下文选择，调用供应商时可去掉后缀。1M 是上下文窗口；自动压缩会为输出等保留空间，不意味着每次请求都能输入整整 1M tokens。GLM-5.3 本体是文本模型，不能把图片输入、Flash 变体或某次短请求成功当成整窗实测。

## 素材研究能力

Claude 材料研究只挂载项目的 `videoagents_research` stdio MCP。内置工具、其他 MCP、Hooks 与会话持久化关闭，模型可调用以下工具：

| 工具 | 返回内容与边界 |
| --- | --- |
| `skill(name)` | 读取已安装、目录中列出的检索技能指南；不执行指南脚本，不允许指定文件路径。 |
| `search(query, platforms)` | 复用已有公开搜索及原生只读适配，遵守配置的平台、每平台结果数及累计调用预算。原生失败后兜底检索同样计数。 |
| `source(url, platform)` | 真实读取 HTML/纯文本，将解析后的 UTF-8 正文保存在任务研究目录，返回标题、出处、正文、图像线索和真实散列。 |
| `visual(source_url, url, kind, description)` | 对已读取来源下载直接图片或 MP4，返回实际文件、真实散列及探测尺寸/视频时长。图片开关生效；图片不超过 10 MiB、视频不超过 100 MiB。 |
| `screenshot(source_url, description)` | 截图开关开启时，复用既有 Playwright 公网采集器，保存并探测真实 PNG。 |

工作目录必须是当前任务当前版本的 `jobs/<job_id>/revisions/<revision>/skills-research`，文件名由 Python 生成。拒绝目录链接逃逸、私网或本机 URL、未知任务版本和已取消任务；研究目录累计文件体积不超过 256 MiB。下载和截图继续使用既有公网连接与重定向校验。工具失败不回传原始异常或凭据。

工具返回 `source` 或 `visual` 字段中的清单条目供模型汇总为 `MaterialResearch`，额外正文、图片线索和实测媒体元数据仅辅助研究。素材节点再次验证来源关联、文件、散列及媒体，将最终产物冻结后交给下游。搜索结果、流媒体页面、视频链接和截图动画不能作为已取得的真实视频。无法取得的正文、视频、字幕或语义检查写入 `limitations`，走现有人工补充入口；无合适视频不算失败。

显式选择 Codex CLI 的旧研究路径保留，其权限、工具和搜索预算方式见 [素材研究节点](videoagents-materials.md)。两条路径不共享其他任务的素材与状态。

## 验证与恢复

先验证 Claude 实际版本和模型路由，再做小请求与素材工具调用；最后通过正常任务入口检查资料冻结、任务事件和人工审核。模型显示名称、短请求成功和回归测试分别证明配置、连接与代码行为，不能互相替代。供应商限流或模型不可用时保留失败并通过原节点重试；调用提交状态 `UNKNOWN` 继续阻断，不自动更换模型或重发未知请求。同版本已冻结研究仍复用，刷新内容通过任务新版本进行。

官方依据：[智谱 Claude 接入](https://docs.bigmodel.cn/cn/coding-plan/tool/claude)、[GLM 最新模型与推理映射](https://docs.bigmodel.cn/cn/coding-plan/latest-model)、[Claude 自定义模型能力与上下文](https://code.claude.com/docs/en/model-config)、[MCP stdio 协议](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。
