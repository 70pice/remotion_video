# 素材研究节点

## 流程和职责

流程调整为 `START → materials → screenwriter → script_reviewer（可选讨论）→ script_gate → voice → director → editing → reviewers`。

`materials` 负责检索、读取来源、采集真实图片与网页截图；编剧只消费冻结的研究结果。导演同时获得素材文件、出处、说明和与口播段落的关联。节点仍统一定义在 `videoagents/nodes/`。

平台工具通过目录声明能力，明确区分原生工具与搜索引擎的站点检索。未配置搜索服务、未安装工具、登录状态未知、页面被拦截和预算耗尽均作为结果记录，不虚构成功。搜索摘要只是线索；实际读取的来源和下载成功的素材另外保存。

复用已有的公开网络地址校验、凭据保护、外部调用台账、文件 hash、版本检查与人工待办。冻结结果在编剧模型调用前提交；同一版本重复执行复用素材包。素材缺失可以补链接/图片或调整配置后恢复，不能以空研究包冒充完成。

已有用户文案或稿件不会强制新增搜索；手工来源仍会进入素材采集。旧 checkpoint 已经过编剧的任务继续原进度；新执行从素材节点开始。

## 数据交接

入口是 `videoagents/nodes/materials.py` 的 `MaterialsNode.__call__()`；平台工具在 `videoagents/tools/research.py`，编剧不再自行采集。

1. 根据主题生成检索规划。素材角色可独立选择 Codex CLI 或 Claude Code CLI、模型和超时；关闭素材模型时仍可直接用主题检索。像“Muse是什么”这样的多义名称保留原检索词，启用模型后可在 `plan.ambiguities` 记录歧义。
2. 按选定平台检索，记录标题、链接、搜索摘要、实际 backend 和失败项。摘要只是发现线索。
3. 读取实际 HTML/正文，保存获取时间、最终 URL 和文件 hash；下载图片并截取页面，验证真实格式、尺寸后登记本地素材。
4. 冻结 `material-plan.json`、`material-discovery.json`、`research.json`。完成包在同版本重放时复用；页面读取中断时复用已登记来源和搜索记录。
5. `VideoState.research` 保存研究包，`assets`/`asset_metadata` 保存实际媒体与说明。编剧据此写稿，用 `source_refs`/`asset_ids` 关联段落；导演读取同样的正文、出处与视觉说明匹配镜头。Remotion 使用已登记的本地素材。

主题任务没有读到来源时停在 `materials` 待办，可补链接或修正配置后恢复。完成包需要刷新内容时，保存新版本再执行。

## 完整平台目录（32 项）

这是当前实现的完整目录，表示可选择的检索目标。访问结果取决于公开索引、页面限制和本机工具。

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

1. 在「系统设置」配置素材角色模型（可选），其他六角色的模型仍独立选择。
2. 检索服务选择 `opencli_google`（本机 OpenCLI + 浏览器扩展，无需检索密钥）、`tavily`（填密钥）、`google_cse`（已有账号，填密钥和搜索引擎 ID）或 `none`（手工来源/已安装原生工具）。
3. 勾选平台。默认七项：全网、X、YouTube、知乎、Reddit、B站、Google；每平台 3 条，最多 8 次检索、读取 12 个来源、尝试采集 8 个图片/截图。按选定顺序执行，原生失败后的兜底也消耗预算；需要更多平台时增加预算。
4. 开启截图及真实图片下载。截图优先使用 Playwright Chromium，未下载时尝试系统 Chrome 的独立无登录实例；没有 Chrome 时安装浏览器：`.venv-videoagents/Scripts/python.exe -m playwright install chromium`。每来源最多采集一张成功原图，失败时在预算内尝试下一个候选；图片与截图共享采集尝试上限。
5. 新建主题任务，输入“Muse是什么”。执行后先查看「素材研究」页签，再查看文案和来源引用。

`opencli doctor` 可诊断浏览器连接。Google CSE 的 JSON API 已停止接受新客户，现有客户需在 2027-01-01 前迁移；保留该配置兼容已有账号。[Google 官方说明](https://developers.google.com/custom-search/v1/overview)。

登录墙、验证码、地区限制或无法读取的格式会记录为失败。当前正文读取支持 HTML/纯文本；PDF、视频字幕和完整视频下载未在本次实现，需要可读取网页或人工素材。截图使用隔离的无登录浏览器，不能保证登录后页面可见。图片/截图再利用许可由后续审核确认。

## 插入素材人工审核

在图编译前注册节点，并**替换**原素材条件边：

```python
self.add_human_review(
    graph, "materials_review", stage="materials", title="素材人工审核",
    confirmation_requirements=("主题含义明确", "来源与知识对应", "截图可用且出处完整"),
    next_node="screenwriter",
)
graph.add_conditional_edges("materials", self.route, {
    "screenwriter": "materials_review", "await_input": "await_input",
})
```

确认后进入编剧，返工后保存新版本再执行。复用现有待办、指纹及 checkpoint；详见 [人工审核编排](videoagents-human-review.md)。
