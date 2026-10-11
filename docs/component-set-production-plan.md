# 组件套进入普通视频生产

用户目标：导演先按表达目的、素材类型和本期内容选择已登记组件套，通过 `Shot.set_design` typed production selection 绑定当前任务素材、文字、数字和来源，并调整每个固定 part 的出现/结束时刻、尺寸与间距，输出不超过30秒的实际 Demo 供人工审核。

## 生产契约

- 普通 `Shot` 增加生产专用 `set_design` 字段，不复用 props 里的旧样片 marker。`set_design.set_id` 限定 `A01`–`A12` / `B01`–`B18`；旧时间线和静音样片保持可读，component sample 继续服务回放和品鉴。
- Shot 级 `title`、`body` 承载公开标题和正文；`set_design.content` 只接收当前 job 的真实结构化内容：`takeaway`、`items`、`supporting_items`、`metric {label,value,detail}`、`numeric_items`、`source_refs`。字段长度与内容组合遵守生产契约和各套校验规则；短标题、结论及列表按真实阅读时间安排，不随机凑数。
- 有素材套必须绑定当前 job 的 `asset_src` 与 `source_label`。只有 `videoagents/component-set-capabilities.json` 中 `focus_supported=true` 的套件才允许 `focus_steps/source_size`；当前为 A03、A05、A06、A09。其他套件通过 parts 的 `start_frame/end_frame` 与 safe-area `box` 调整表达。不得复用其他 job 的 asset_id、timeline_src、音频或样片状态。
- 每套有固定生产原生组件映射与固定 part 模板。共享元数据 `videoagents/component-set-capabilities.json` 已提供实际生产 `parts[].component_id`、默认 box、默认 start/end ratio、material_kind 和 focus_supported；生产适配器先展开 defaults，再做素材、内容、布局、字幕安全区、focus 边界、时钟和原生组件计数校验。
- 每个 part 使用本 shot 内的 `start_frame` / `end_frame` 和 `box {x,y,width,height}`。part 动画使用自己的本地时钟；调整出现时刻必须同步调整动画时钟，不能只设置透明度让动画提前结束。
- 默认视觉结构是上方素材、下方深色底白字，无白色标题底板。文字、素材与字幕安全区独立；所有 part 的 box 在 safe_area {x:64,y:96,width:952,height:1304} 内归一化，换算到 1080×1920 后下沿不超过 y=1400，不能遮挡字幕或关键图内标注。
- 镜头时长、揭示时刻和阅读停留依据真实 captions、素材可读性和当前段落叙事决定；不套用样片 12–20 秒，不强制 2–3 秒切套，也不为满足模板编造数字、事实或统计。
- 普通生产禁止旧样片字段或自由代码注入：不得输出 `component_set`、`composition`、`rich_content`、`component_demo_recipe`、任意 JSX/CSS、远程素材路径或样片事实。
- 真实音频、字幕、总帧数和当前任务素材身份不变。原生组件统计根据 set_design defaults 展开后的实际挂载、可见时段及能力计算，不能按模板清单虚增。
- 登记、品鉴、单片 Demo 批准和最终成片审核状态分开记录；不得把样片发送回执、内部验证或 30 秒 Demo 自动写成用户已品鉴通过。

## 节点交接

任务 API → Worker → VideoProductionGraph → 导演选择 `set_design` 并写入本期内容/素材/part 时钟/布局 → defaults 展开 → 时间线与组件套校验 → `director_demo` 渲染不超过30秒 Demo → `director_human_gate` 人工审核 → 人工通过后 `editing` 剪辑与成片渲染。

导演按场景、素材和内容选择：人物/生活照片优先 A01/A07，App 界面或操作优先 A02/A08/A09，账单和数字核算优先 A10/B04/B08/B10，作品细节优先 A04/A11，关系/流程优先 A06/A12/B11/B12/B16/B18，问题、概念、问答、核实、结论等无素材表达优先 B01/B02/B14/B15/B06。选择理由写入 `component_reason`；本期内容、来源、duration/layout overrides、part 本地时钟和 Demo 说明写入 `visual_action` 或导演方案。

人工返工沿现有 revision 与导演续跑入口：`director_human_gate` 的 revise 可以附带导演要求并回到 director，重新生成 Demo；confirm 才继续 editing。不得改数据库审批标记，不跳过 `director_demo` 或 `director_human_gate`。

## 维护和运行

- 复用现有原生组件与 rich renderer，不新增依赖或额外模型轮次。30 套实际生产 native IDs 以 `videoagents/component-set-capabilities.json` 的 `sets[].parts[].component_id` 去重结果为准；registry 中的 component_sample/历史 components 只记录样片或历史组合，Python/TS 校验保持一致，并通过生成器更新前后端模型。
- 权限沿用本机任务 API 会话与 CSRF；不新增发布动作。普通生产、component sample、用户品鉴和媒体回执分别记录。
- 异常沿 `await_input` 回报具体字段与缺素材原因；不自动退回旧卡片方案，不修改数据库审核标记。
- 重启加载新代码前检查无运行中任务。真实验证通过待验证任务的正常制作或导演返工 API 执行，返工时保留该任务已确认的原稿、原音频和字幕，生成不超过30秒的 director Demo MP4，并停在 `director_human_gate` 待人工 review；记录任务 ID、节点事件、输入、导演方案、stage_review 和 Demo artifact，不在人工 confirm 前声称完整成片已渲染。独立试验任务不能继承其他任务的素材、音频或人工通过状态。
- `videoagents/component-set-capabilities.json` 已提供 version、safe_area 与 30 套 parts；文档引用该文件作为默认展开来源，不在文档中复制或臆造默认 part 数值。

## 验证

覆盖 30 套 `set_design` 选择与内容约束、当前 job 素材隔离、合法 duration/layout overrides、safe_area 归一化 box 与 y=1400 下沿、空间重叠/太晚揭示拒绝、仅 A03/A05/A06/A09 接受 `focus_steps+source_size`、part 局部动画时钟、defaults 展开后原生计数、旧样片兼容、生产音频字幕保留、导演 schema/Prompt 与 30 秒人工审核守卫；运行对应 Python/JS 回归、类型检查、lint、契约生成校验及前端构建，并用正常 Graph 生成真实 director Demo MP4 待审作为交付证据。
