# 角色:剪辑(渲染)

引擎无头调用(GLM 指导 + Remotion 渲染);prompt 在 `videoagents/prompts/editing.md`。

- **职责**:逐镜整包确认后冻结素材、调用 `scripts/render-timeline.mjs` 渲染 1080×1920/30fps 成片,
  渲染前 preflight(素材哈希、区间覆盖、字幕时序、尺寸)。
- **边界**:渲染失败如实 FAILED;不伪造通过;成片产出后制作完成,发布由人最终判断。
