# 素材研究节点

## 流程和职责

流程调整为 `START → materials → screenwriter → script_reviewer（可选讨论）→ script_gate → voice → director → editing → reviewers`。

`materials` 负责检索、读取来源、采集真实图片与网页截图；编剧只消费冻结的研究结果。导演同时获得素材文件、出处、说明和与口播段落的关联。节点仍统一定义在 `videoagents/nodes/`。

素材节点直接启动 **Codex 模型研究**：模型读取 `agent-reach` 和已安装的互补技能，自行选择检索、网页读取、视频字幕、原图及截图工具。Python 接收并验证最终文件清单，没有单独的规划或固定检索分支。技能安装、各平台实测状态与待配置项见 [检索环境清单](videoagents-research-skills.md)。

未安装工具、登录状态未知、页面被拦截、时间与预算不足均作为资料缺口记录。搜索摘要只是线索；实际读取的来源和下载成功的素材另外保存。安装技能不代表账号已经登录，也不保证覆盖全网。

复用已有的公开网络地址校验、凭据保护、外部调用台账、文件 hash、版本检查与人工待办。冻结结果在编剧模型调用前提交；同一版本重复执行复用素材包。素材缺失可以补链接/图片或调整配置后恢复，不能以空研究包冒充完成。

已有用户文案、稿件和来源链接也交给素材模型，模型根据输入核验和补充资料。旧 checkpoint 已经过编剧的任务继续原进度；新执行从素材节点开始。

## 数据交接

入口是 `videoagents/nodes/materials.py` 的 `MaterialsNode.__call__()`。`collect()` 优先复用冻结包，否则调用一次模型，再由 `save_research()` 校验和登记最终文件。编剧不再自行采集。

调用链：

```text
VideoState → MaterialsNode.collect()
  → JsonModel.invoke(brief, assets, settings)
  → Codex CLI：agent-reach / web_search / shell / 截图技能
  → MaterialResearch：sources + visuals + limitations
  → Python 核验文件、SHA256、数量、来源关联、图片格式及尺寸
  → 冻结 research / assets → VideoState → 编剧与导演
```

业务 Prompt 独立保存在 `videoagents/prompts/materials.md`，`materials.py` 的 `PROMPT` 仅负责加载共享风格与角色规则。没有单独的规划 Prompt、方法、契约或规划产物。
素材研究目前要求启用素材模型并选择 `codex_cli`；模型关闭或选择尚不支持研究的 CLI 时暂停并提示能力缺口。

每版本研究目录为 `jobs/<job_id>/revisions/<revision>/skills-research/`。
最终清单中的 `text_file` / `file` 必须为目录内相对路径，文件实际存在且散列一致。
通过验证的来源和画面复制到冻结目录、登记为当前任务产物；权限尚未确认的原图与截图仍需后续审核。
目录只是执行空间，不进入下一个 Agent 的输入。`material-skill-manifest.json` 与脱敏的
`material-tool-audit-*.jsonl` 仅用于追溯，`VideoState` 中只传最终研究结果和已登记素材。

搜索调用数属于 Prompt 指令预算；来源与画面数量由 Python 强制限制。
CLI 调用账本保留原有 `UNKNOWN` 阻断，切换 CLI 或模型不能绕过未知提交。
已完成的研究同版本复用，不因配置变化自动重新抓取；需要刷新请保存新版本。

`VideoState.research` 只保存最终来源、画面及资料局限，`assets`/`asset_metadata` 保存实际媒体与说明。编剧据此写稿，用 `source_refs`/`asset_ids` 关联段落；导演读取同样的正文、出处与视觉说明匹配镜头。Remotion 使用已登记的本地素材。多义主题尚未确认的含义写入 `limitations`。

主题任务没有读到来源时停在 `materials` 待办，可补链接或修正配置后恢复。完成包需要刷新内容时，保存新版本再执行。

## 可选研究目标（32 项）

这是设置页的完整目标目录。模型自行选择已安装技能提供的能力，表中的既有索引/CLI 仅说明可用入口，不代表节点逐项调度或所有平台均已连通。访问结果取决于公开索引、页面限制和本机工具。

| ID | 平台 | 当前检索方式 |
| --- | --- | --- |
| `web` | 全网网页 | 配置的通用搜索服务 |
| `google` | Google | OpenCLI Google；或已有 Google CSE |
| `bing` | Bing | `bing.com` 公开页面索引 |
| `baidu` | 百度/百度百科 | `baidu.com`、`baike.baidu.com` 公开索引 |
| `x` | X / Twitter | `x.com`、`twitter.com` 公开索引 |
| `youtube` | YouTube | 本机 yt-dlp 搜索元数据；或公开索引 |
| `zhihu` | 知乎 | `zhihu.com` 公开索引 |
| `reddit` | Reddit | `reddit.com` 公开索引 |
| `bilibili` | B站 | 本机 bili-cli 搜索；或公开索引 |
| `xiaohongshu` | 小红书 | `xiaohongshu.com`、`xhslink.com` 公开索引 |
| `weibo` | 微博 | `weibo.com` 公开索引 |
| `douyin` | 抖音 | `douyin.com` 公开索引 |
| `kuaishou` | 快手 | `kuaishou.com` 公开索引 |
| `wechat` | 微信公众号/搜狗微信 | 微信文章与搜狗微信公开索引 |
| `wikipedia` | Wikipedia | 百科公开索引 |
| `wikimedia` | Wikimedia Commons | 图片页面与原图公开索引 |
| `github` | GitHub | 本机 gh 搜索仓库；或公开索引 |
| `arxiv` | arXiv | 论文页面公开索引 |
| `stackoverflow` | Stack Overflow | 问答公开索引 |
| `hackernews` | Hacker News | HN、Algolia 公开索引 |
| `v2ex` | V2EX | 社区公开索引 |
| `medium` | Medium | 文章公开索引 |
| `quora` | Quora | 问答公开索引 |
| `douban` | 豆瓣 | 公开页面索引 |
| `google_scholar` | Google Scholar | 学术条目公开索引 |
| `pexels` | Pexels | 图片页面公开索引 |
| `unsplash` | Unsplash | 图片页面公开索引 |
| `instagram` | Instagram | 公开页面索引 |
| `facebook` | Facebook | 公开页面索引 |
| `linkedin` | LinkedIn | 公开页面索引 |
| `producthunt` | Product Hunt | 产品与评论公开索引 |
| `official` | 官方网站/新闻稿 | 主题加 `official` 搜索，是否官方仍需核验 |

索引检索使用选择的搜索服务加域名过滤，结果再次核验所属站点。比如 `backend=opencli_google_indexed` 表示 Google 索引中的目标平台页面。X、Reddit、小红书等账号原生适配尚未接入本项目，安装相关工具也不代表登录已验证。Google、YouTube、GitHub、B站的原生只读适配在入口可用时尝试，失败与兜底分别记录。Bing/百度当前没有调用其搜索 API。

## 配置与使用

1. 在「系统设置」启用素材角色，选择 Codex CLI 和模型。其他角色的模型仍独立选择。
2. 确认设置页列出的技能已安装。素材 Agent 可用内置网页检索及 Agent Reach 路由；具体平台/转写服务所需登录或 Key 仍要配置。
3. 勾选平台。默认七项：全网、X、YouTube、知乎、Reddit、B站、Google。建议给素材角色更充足的超时；同一任务不要求每个平台都有结果，缺口会显示在研究包中。
4. 开启截图及真实图片下载。Windows 技能浏览器可直接调用 `npx --yes --package @playwright/cli playwright-cli`；系统没有 Bash，不能原样调用其 `.sh` wrapper。
5. 新建主题任务，输入“Muse是什么”。执行后先查看「素材研究」页签，再查看文案和来源引用。

`opencli doctor` 可诊断浏览器连接。Google CSE 的 JSON API 已停止接受新客户，现有客户需在 2027-01-01 前迁移；保留该配置兼容已有账号。[Google 官方说明](https://developers.google.com/custom-search/v1/overview)。

模型可通过已配置的技能后端读取网页、字幕及其他格式；实际能力见环境清单，缺少转写 Key 时不能声称已转写。

登录墙、验证码、地区限制或无法读取的格式会记录为缺口。浏览器连接成功不代表各平台登录已验证。图片/截图再利用许可由后续审核确认。

原 Meta Muse 任务的失败已按实际调用层复验；当前网页、B站、YouTube 搜索、Reddit 正文及指定知乎文章均有真实返回。2026-10-04 的再次验收取得 B站真实字幕；YouTube 字幕、X 搜索和知乎搜索仍有缺口。完整平台表见 [当前实测状态](videoagents-platform-status.md)，调用层修复见 [工具诊断与修复记录](videoagents-tool-diagnostics.md)。

## 本机验证记录（2026-10-04）

使用独立 SQLite 和研究目录，以 `gpt-6.1-sol` 执行了一次实际素材节点，限定 Muse 乐队官网、一份正文、一张原图，耗时 70.3 秒。节点读取 `https://www.muse.mu/`，通过 Jina Reader 保存正文，下载并核验了 750×1260 的真实图片，返回 `screenwriter`。这是素材节点验证，没有执行配音、导演或渲染。官网内容不够支持的背景事实、未核验的图片使用权均保留在 `limitations`。

六个登记产物的 SHA256 全部复核通过；重放时禁止调用模型仍成功复用冻结结果，新增操作数为零；审计日志和原始清单没有进入下游 Agent 输入。完整 Python 测试 389 项、React 测试 66 项通过，最终 CLI 权限与素材交接相关回归 106 项通过；Ruff、React 类型检查与构建、契约一致性检查通过。实际结果记录在被 Git 忽略的 `.runtime/materials-skills-smoke/bb71a3cb2b/`。

研究会话在 Windows 显式设置 `windows.sandbox="unelevated"`、`--sandbox workspace-write` 和网络访问。原因是 `--ignore-user-config` 会同时忽略用户的 Windows 沙盒设置；Codex 0.159.2 在 Windows 沙盒未启用时会将 `workspace-write` 降为只读，导致无法保存研究文件。此配置只用于研究子进程，不修改全局 Codex 配置；其他角色保留原有只读且不调用工具的执行方式。[Codex 0.159.2 官方实现](https://github.com/openai/codex/blob/rust-v0.159.2/codex-rs/config/src/config_toml.rs#L786-L833)。

## 插入素材人工审核

在图编译前注册节点，并**替换**原素材 `add_cleanup_edge()` 的路由映射，保留 `clear_materials`：

```python
self.add_human_review(
    graph, "materials_review", stage="materials", title="素材人工审核",
    confirmation_requirements=("主题含义明确", "来源与知识对应", "截图可用且出处完整"),
    next_node="screenwriter",
)
self.add_cleanup_edge(graph, "materials", {
    "screenwriter": "materials_review", "await_input": "await_input",
})
```

确认后进入编剧，返工后保存新版本再执行。复用现有待办、指纹及 checkpoint；详见 [人工审核编排](videoagents-human-review.md)。
