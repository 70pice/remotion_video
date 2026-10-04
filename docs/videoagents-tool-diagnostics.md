# 素材检索工具实测（2026-10-04）

本次验收针对原来 Meta Muse 视频的素材采集失败。区分安装、搜索、实际正文读取及节点接收；安装状态和 doctor 的结果不等于目标内容已经读取。

同日再次验收取得 B站实际字幕，另复验 GitHub、V2EX、RSS。下表保留首次诊断的证据范围，当前完整状态以 [平台实测表](videoagents-platform-status.md) 为准。

## 实际结果

| 能力 | 本次结果 | 已验证范围及限制 |
| --- | --- | --- |
| Exa / mcporter | 可检索 | 在 Codex 研究子进程中返回 Meta 官方站点候选；摘要只作线索 |
| Google / OpenCLI | 可检索 | 直接命令、项目 `_google()` 和 `discover()` 均返回两条 Meta 官方候选 |
| Jina Reader | 可读正文 | Codex 研究子进程保存 Meta 帮助中心和 Eigent 文章的实际正文 |
| B站 / bili | 可检索、读详情 | 搜索得到视频，读取非空标题与简介；本次未验收完整视频字幕 |
| YouTube / yt-dlp | 可检索 | 得到视频元数据与缩略图线索；自动字幕请求返回 HTTP 429，未取得字幕 |
| Reddit / OpenCLI | 可检索、读正文 | 两条搜索结果；一篇帖子正文 2,939 字符和两条评论 |
| 知乎 / OpenCLI | 指定文章可读 | 导出约 4,826 字正文和 13 个图片引用；搜索端点返回 AUTH_REQUIRED，图片未下载验图 |
| X / OpenCLI | 本次未成功 | 搜索返回 AUTH_REQUIRED/缺少 ct0；指定推文和长文读取返回 Navigation rejected |

Reddit 与知乎使用用户已有 Chrome 会话。没有执行登录、Cookie 提取、平台写操作或修改生产任务。上述状态是本次访问结果，不是永久可用性承诺。

## 复现与修复

1. 固定工具原先只查当前 PATH。`yt-dlp.exe` 和 `bili.exe` 已安装在用户 `.local/bin`，仍被报告为不可用。现在 PATH 优先，找不到时回退用户工具目录；子进程补齐目录和 Windows UTF-8，不修改全局 PATH。
2. 原来的 YouTube `--dump-json` 会展开格式与字幕信息；本次单条元数据达 11,676,157 bytes，撞上原生运行器的 2 MB 限制。固定搜索改为 `--flat-playlist`，保留大小、取消及超时保护。
3. 旧 `safe_get()` 禁用环境代理，直接请求 Meta 被重置、X 的 TLS 握手超时、知乎返回 403。这不能证明平台专用工具不可用。技能研究通过 Jina、OpenCLI 等适合当前平台的读取方式取得实际正文，没有放宽原公共网络地址校验。
4. Windows curl 读取 Jina 时出现系统证书错误；保持 TLS 校验的 Python 客户端成功读取同一地址。已将备用路径和视频轻量检索建议写入素材节点固定 Prompt。

调用链检查使用素材节点相同的 `run_cli(..., research_directory=...)`，没有替换权限参数或模拟网络返回。成功文件已逐一核验 SHA256。诊断不会触发配音、渲染或发布。

随后又执行了真实 `MaterialsNode`，使用独立数据库、给定的三条 URL 和正文验收范围，耗时 109.7 秒：Meta 正文 1,021 字符、Reddit 正文及部分评论 9,130 字符、知乎 Markdown 14,659 字符。三个来源均登记并写入共享状态，路由为 `screenwriter`；冻结产物散列复核通过，禁止模型调用后重放仍成功。该测试有意关闭图片和截图，没有推进配音、导演或渲染。社区及第三方说法的证据局限保留在研究结果中。

## 证据与回归

被 Git 忽略的本机证据在 `.runtime/materials-tool-diagnosis/`：

- `codex-result.json`：真实 Codex 研究子进程的 Exa、Jina、B站、YouTube 检查及已保存文件散列。
- `social-report.json`：Reddit、知乎和 X 的搜索/正文分别验收。
- `network-result.json`：旧通用 HTTP 读取路径的失败类型与耗时。
- `materials-context-check/result.json`：素材节点接收多平台正文的最终结果。

修复回归位于 `tests/videoagents/test_research_runtime.py`，原程序发现失败脚本现已通过；相关检索、素材与 CLI 测试 93 项通过，最终素材 Prompt 改动后又通过 29 项素材回归。新增工具或修改后端后，应重新执行实际只读命令，以非空正文或实际媒体文件验收。
