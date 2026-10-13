# 角色:素材(按文案清单取证供画面)

引擎无头调用(GLM + videoagents_research MCP 全量工具);prompt 在 `videoagents/prompts/materials.md`。

- **输入**:编剧的文案(每段 source_refs 是必核清单、visual_need 是画面采集单)+ brief + 已登记素材。
- **输出**:冻结的 research(核验过的来源正文)+ 真实素材(图片/截图/视频文件)+ limitations
  (按 [证据缺口]/[画面缺口] 等前缀如实交接)。
- **边界**:画面必须是真实下载/截图的文件;拿不到就写缺口,不硬凑、不用截图动画冒充视频;
  真实视频优先但不强制。
