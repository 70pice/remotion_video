# VideoAgents 使用说明

本项目新增完整 React 工作台，沿用已有 Remotion 组件库。Python 负责工作流、来源记录、音频与审核，Node 负责按冻结时间轴渲染。API 和 worker 分别运行，关闭浏览器不会终止后台任务。

## 首次安装（Windows PowerShell）

在 `D:\remotion_video` 执行：

```powershell
npm install
$env:UV_PROJECT_ENVIRONMENT = '.venv-videoagents'
uv sync --python 3.12
```

需要 Node 24、uv、Python 3.12、FFmpeg 和 FFprobe。本次开发使用独立 `.venv-videoagents`，原有 `.venv` 保留。依赖版本记录在 `package-lock.json` 和 `uv.lock`。

需要自动截取来源网页时，再安装 Playwright 浏览器：

```powershell
.venv-videoagents/Scripts/python.exe -m playwright install chromium
```

首次 Remotion 渲染会准备 Chrome Headless Shell，需要联网。已准备浏览器后，手工输入文案、导入素材和音频的路径可以在本机运行。

## 启动与关闭

```powershell
npm run studio:dev
```

浏览器打开 `http://127.0.0.1:5173`。React 开发端口 5173，API 端口 8000；Vite 转发 `/api`。脚本启动 API、独立 worker 和前端，验证 API、worker 心跳和页面后才提示可用。进程与日志记录在 `.runtime/videoagents`。

构建并运行同源页面：

```powershell
npm run web:build
npm run studio:start
```

打开 `http://127.0.0.1:8000`。切换开发/构建模式前，先关闭已有工作台：

```powershell
npm run studio:stop
```

关闭脚本核对记录的 PID、启动时间和可执行文件，只停止本次工作台及其子进程。正在渲染时关闭会中断渲染；重启 worker 会根据持久化记录恢复或明确报告需要补充的信息。

## 自动生产

1. 在「设置」填写模型地址、模型名称和密钥，配置 Tavily 搜索。密钥写入后界面只显示已配置状态。
2. 配置字节配音：选择 `byte_http`，填写声音 ID、资源 ID 和 API Key；旧鉴权也支持 App ID 与 Access Token。具体资源须与用户已复刻的声音匹配。
3. 创建任务，输入主题或文案，设定受众、用途、画幅、帧率和来源链接。
4. 执行生产，按编剧 → 配音 → 导演 → 渲染 → 审核推进。缺服务、缺授权记录或缺真实时间戳时，会显示待补充信息。
5. 在各阶段查看、编辑文案与素材。修改会递增版本并使相关产物和审核失效。
6. 查看成片和审核问题，按问题时间跳转播放，补充材料或修订。明确发布平台与用途、通过硬性检查后，需要人完整观看当前成片并填写复核记录，才进入 `READY_FOR_PUBLISH`。通用画幅选项不能替代具体发布平台。

`READY_FOR_PUBLISH` 表示本系统的发布前检查完成，实际平台的审核结果由平台决定。本版本产出可下载视频，不自动发布。

字节 v3 使用流式音频接口；只有终止成功码与完整音频确认后才记录完成。若请求已提交但响应超时或中断，操作进入 `UNKNOWN` 并暂停，避免重复付费提交。API 的请求 ID 没有被当作服务商承诺的幂等保证。官方协议参考：[字节大模型语音合成](https://www.volcengine.com/docs/6561/1598757?lang=zh)。

## 暂不接外部 API 的本机路径

1. 创建带完整文案的任务；保存编剧产出的段落后查看每段 `segment_id`。
2. 上传真实图片或网页截图，填写来源与授权说明；示意图选择 illustration，不把示意图作为事实证据。
3. 上传本地 MP3/WAV 等音频，并上传经过验证的对齐 JSON。音频须对应当前文案，字幕时间来自实际音频。
4. 生成分镜，或在分镜面板编辑镜头并选择已上传的素材。镜头使用八个可生产适配器；原有 152 个演示组件在组件库中另行浏览。
5. 渲染预览、生成最终视频并运行审核。

对齐文件格式：

```json
{
  "origin": "manual",
  "verified": true,
  "audio_sha256": "填写上传音频实际SHA-256，共64个十六进制字符",
  "segments": [
    {"segment_id": "s1", "text": "与本段文案一致", "start_ms": 0, "end_ms": 2100}
  ],
  "note": "实际试听核对记录"
}
```

同一段可拆成多条实测字幕，每条不超过 72 字，按时间排序且不能重叠，合并文字须与对应口播段一致。上传或单独补充对齐时，服务端绑定所选音频的实际哈希；如果提交了非空哈希，必须匹配。切换所选音频会读取它自己保存的对齐记录。不会用字数平均分摊伪造对齐。

## 数据与 Review 入口

```text
web/src/                     React 页面、编辑器、API 与事件订阅
server/                      FastAPI、会话、上传与媒体服务
worker/                      持久任务领取、执行与恢复
videoagents/contracts/       Python 数据契约
videoagents/graph/           LangGraph 节点与路由
videoagents/providers/       模型、搜索、字节配音与对齐服务
videoagents/services/        版本编辑、导入与设置
videoagents/agents/          编剧、导演和审核角色
videoagents/nodes/           配音及 Remotion 剪辑节点
videoagents/storage/         SQLite 命令、事件与外部操作台账
src/video-production/        八个生产适配器与时间轴验证
contracts/generated/         由 Python 导出的类型、JSON Schema、OpenAPI
scripts/*studio*.ps1          本机启动与停止
tests/                       后端、工作流与联调测试
.runtime/videoagents/        本机数据库、日志、运行记录（不入 Git）
.runtime/videoagents/jobs/   单任务素材与各版本产物（不入 Git）
public/videoagents/          渲染用受控素材（不入 Git）
```

Windows 配置密钥使用当前用户的 DPAPI 加密后保存在运行数据库，不返回给浏览器，也不放入图状态、时间轴、事件或 Git。恢复加密凭据需要原 Windows 用户；备份运行目录仍按私有配置保存。非 Windows 的兼容路径仅限制文件权限，不提供同等凭据加密。素材来源及授权说明由用户和提供方给出；填写说明不等于系统获得版权许可。

接口契约由 Python 导出；改契约后执行：

```powershell
.venv-videoagents/Scripts/python.exe scripts/export-contracts.py
```

## 验证与故障排查

```powershell
.venv-videoagents/Scripts/python.exe -m pytest
.venv-videoagents/Scripts/python.exe -m ruff check server worker videoagents tests scripts/export-contracts.py
.venv-videoagents/Scripts/python.exe scripts/export-contracts.py --check
npm run typecheck
npm run lint
npm run test:timeline
npm run web:typecheck
npm run web:test
npm run web:build
npm run check:component-paths
```

纯本机端到端测试：启动工作台后运行 `.venv-videoagents/Scripts/python.exe scripts/smoke-studio.py`。脚本先确认没有配置模型、搜索、配音或对齐服务，防止测试调用付费服务；它使用标记为 TEST 的程序图案和测试音，生成真实 MP4，并停在 `NEEDS_HUMAN`。测试音与 fixture 字幕不能作为真人口播、复刻声音或发布资格的证明。

- 端口占用：先执行 `npm run studio:stop`。脚本不会停止不属于本工作台的进程；若仍占用，检查端口对应的应用。
- 页面显示 worker 离线：查看 `.runtime/videoagents/*worker*.stderr.log`，确认独立 worker 已启动。
- 返回 409：任务版本已更新或正在执行，刷新读取当前版本后继续，避免旧页面覆盖新结果。
- 缺音频时间戳：补充真实对齐文件；已有音频不代表有准确字幕时间。
- `UNKNOWN` 外部操作：请求可能已被服务商接受，后台保留未决台账并暂停提交。先核对服务商记录和已有产物，配音可导入实际音频与实测对齐；不要直接重复提交。已确认被拒绝的鉴权请求可以在修正配置后通过新的显式命令重试。
- 网页截图失败：检查 Chromium 是否安装、来源是否公开可访问，再上传实际截图。登录页截图不会被当作目标页面内容。
- 渲染失败：查看任务错误和渲染日志，核对受控素材、时间轴、FFmpeg 与浏览器依赖。

真实模型、搜索与复刻声音需要用户配置有效凭据；本机测试素材的成功不能证明这些外部服务已可用。
