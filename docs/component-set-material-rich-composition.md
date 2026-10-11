# 有素材 rich 组件套 A07-A12

这份说明用于复用 A07-A12 六套有素材 rich 组件套。它们和 A01-A06 一样必须传入当前任务已导入的 `asset_id`，但画面结构更完整：上方保留真实素材或模拟素材主体，下方用深色背景承载白字标题、正文、条目、图表或收束句；标题不加白色底板。

使用时走正常 `POST /api/jobs/{job_id}/component-demo` 入口，指定 `composition: "rich"`，由 Worker 执行 `component_demo → director_demo → end`。不要用独立 demo 脚本、手写时间轴、旧任务 state、旧 `asset_id` 或别的 job 里的运行目录替代。每个 `asset_id` 必须是当前 job 显式导入过的素材。

## 通用输入与边界

- 公共字段：`content.title`、`content.body`、`content.takeaway`。标题最多 18 字，正文最多 60 字，收束句最多 18 字。
- 公共请求字段：`base_revision`、`idempotency_key`、`set_id`、`asset_id`、`composition: "rich"`、`duration_seconds`、`content`。
- 时长：12-20 秒。A09 的实测素材是 371 帧 / 30 fps，约 12.37 秒；其余样例 manifest 为 18 秒。
- 素材：A07、A08、A10、A11、A12 使用图片；A09 使用 MP4 操作录屏。
- 不传任意 JSX、CSS、组件 props 或自定义时间轴。A09 请求使用 `focus_steps`；`focus_source_size` 由节点读取素材实测尺寸后写入，不是请求入参。其他套件不能传步骤框。
- `items` 用短关键词，建议每项不超过 8 字；完整解释写在 `supporting_items`。合流图使用条目的前 8 字作为节点标签。
- 不能把演示内容写成真实案例、真实统计、亲测结论或上级已批准。样片生成只代表可品鉴，不代表人工通过或可发布。

请求形状示例：

先创建本次样片的任务，再通过 `POST /api/jobs/{job_id}/assets` 上传图片或视频，取得这个任务自己的 `asset_id`。读取当前 `revision` 后提交下面的请求；等待 Worker 完成，再从任务的 `preview` 产物下载视频。历史样片的外部备案包中，“素材”目录提供六套对应的样例输入；该素材包未随仓库附带，使用时须取得或自行准备匹配素材，不能直接沿用记录里另一个任务的素材 ID。

```json
{
  "base_revision": 3,
  "idempotency_key": "component-rich-A07-001",
  "set_id": "A07",
  "asset_id": "当前任务导入后的素材ID",
  "composition": "rich",
  "duration_seconds": 18,
  "content": {
    "title": "先看人，再看动作",
    "body": "手机、家人、停顿，把生活场景里的线索拆开。",
    "takeaway": "一起核对再决定",
    "items": ["看手机", "找家人", "停一下"],
    "supporting_items": ["看清当前消息", "一起核对信息", "决定之前先暂停"]
  }
}
```

## 六套分工

| 套件 | 什么时候用 | 素材类型 | 固定字段数量 |
| --- | --- | --- | --- |
| A07 人物线索 | 讲普通人、家人、停顿、神情、手机等生活线索时使用。 | 人物或生活场景图片 | `items` 3 项，`supporting_items` 3 项 |
| A08 界面功能拆解 | 讲一个界面里的入口、功能区或三类操作时使用。 | App / 网页 / 截图类图片 | `items` 3 项，`supporting_items` 3 项 |
| A09 操作跟随 | 需要跟随真实录屏里的三步操作，并让框选区域跟画面同步时使用。 | MP4 操作录屏 | `items` 3 项，`supporting_items` 3 项，`metric.value` 等于 3 步，`focus_steps` 3 段连续覆盖全片 |
| A10 账单核算 | 讲三笔金额、三项数字和合计关系时使用。 | 账单、表格、金额截图或模拟账单图片 | `items` 3 项，`numeric_items` 3 项，`metric` 合计；不传 `supporting_items` |
| A11 作品细节 | 讲一张作品、海报、插画或截图中的三处细节时使用。 | 作品图片 | `items` 3 项，`supporting_items` 3 项 |
| A12 图解关系 | 讲人物、AI、流程、节点关系或图解链路时使用。 | 关系图 / 流程图图片 | `items` 3 项，`supporting_items` 3 项 |

A07、A08、A11、A12 只能使用 `items` 和 `supporting_items`，不能加 `metric`、`numeric_items`、`focus_steps`。A10 只使用 `items`、`metric`、`numeric_items`，三笔数字必须与合计同单位且相加等于 `metric.value`。A09 的 `metric.value` 必须等于 `items` 数量，单位固定为 `步`。

## A07 人物线索

用途：把人物画面里的动作和关系拆成几条线索，让观众先看人，再看动作。

组件组合：`Talkcraft-slow-push-in` + `Snapcn-TextReveal` + `Snapcn-TextHighlight` + `Rve-QuoteCard` + `Rve-ProgressSteps` + `Snapcn-WordFlip` + `Talkcraft-source-converge`。

素材：人物、家庭、办公、生活场景图片。样例素材说明为“AI生成的虚构母女生活场景”，不是现实事件。

示例 content：

```json
{
  "title": "先看人，再看动作",
  "body": "手机、家人、停顿，把生活场景里的线索拆开。",
  "takeaway": "一起核对再决定",
  "items": ["看手机", "找家人", "停一下"],
  "supporting_items": ["看清当前消息", "一起核对信息", "决定之前先暂停"]
}
```

可改项：`asset_id`、`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、`items` 三项、`supporting_items` 三项。组件组合、图片素材类型、字段数量、白字深色底固定。

## A08 界面功能拆解

用途：把一个界面拆成三个入口或三个功能，适合解释“先认入口，再操作”。

组件组合：`Snapcn-PhoneFrame` + `Snapcn-TextReveal` + `Snapcn-TextHighlight` + `Rve-ProgressSteps` + `Rve-SplitScreen` + `Snapcn-WordFlip` + `Talkcraft-source-converge`。

素材：App、网页、设置页、工具界面截图。样例素材说明为“本地虚构App界面，非实际产品”。

示例 content：

```json
{
  "title": "一屏里，三个入口",
  "body": "提醒、问答、共享，各自解决不同的小事。",
  "takeaway": "先认入口再操作",
  "items": ["待办提醒", "生活问答", "家人共享"],
  "supporting_items": ["把重要的小事记下来", "先看建议再核对", "把安排告诉家里人"]
}
```

可改项：`asset_id`、`duration_seconds`、公共文案、`items` 三项和 `supporting_items` 三项。不要把虚构界面写成真实产品功能或亲测结果。

## A09 操作跟随

用途：把一个 MP4 操作录屏拆成三段，画面跟着目标区域走，适合讲“输入、点击、查看结果”这类连续动作。

组件组合：`Snapcn-PhoneFrame` + `Snapcn-TextReveal` + `Snapcn-TextHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Snapcn-TextBuild` + `Snapcn-TextSwap`。

素材：MP4 操作录屏。样例素材说明为“本地模拟App真实操作录屏，非实际产品”，实测 371 帧 / 30 fps，约 12.37 秒。

示例 content：

```json
{
  "title": "输入、保存、查看列表",
  "body": "写下事项，再点保存，最后确认提醒出现在列表。",
  "takeaway": "看到结果才算完成",
  "items": ["输入事项", "点保存", "查看列表"],
  "supporting_items": ["写清要提醒的事项", "输入完成后保存", "确认新提醒已出现"],
  "metric": {"label": "操作步骤", "value": "3步", "detail": "输入→保存→列表"}
}
```

对应 `focus_steps`：

```json
[
  {
    "instruction": "输入事项",
    "start_frame": 0,
    "end_frame": 115,
    "target": {"x": 0.108333, "y": 0.275825, "width": 0.783333, "height": 0.061111}
  },
  {
    "instruction": "点保存",
    "start_frame": 115,
    "end_frame": 179,
    "target": {"x": 0.108333, "y": 0.353602, "width": 0.277778, "height": 0.054167}
  },
  {
    "instruction": "查看列表",
    "start_frame": 179,
    "end_frame": 371,
    "target": {"x": 0.063889, "y": 0.513889, "width": 0.872222, "height": 0.115278}
  }
]
```

`focus_steps` 固定三段，必须连续覆盖整条 shot，每段至少 30 帧；`instruction` 必须逐项等于 `content.items`；`target` 是原始素材坐标里的归一化矩形，不是手机外框坐标。`focus_source_size` 由素材节点写入实测尺寸，调用者不用手填。本例为 `{"width": 720, "height": 1440}`，其他尺寸的录屏也可以使用；素材实际时长必须覆盖请求的样片区间。

可改项：`asset_id`、`duration_seconds`、公共文案、三步文字、三条说明、`metric.label/detail`、每步帧段和目标框。`metric.value` 必须等于 `3步`；A09 不能改成图片素材。

## A10 账单核算

用途：把三笔金额或三项同单位数字算成合计，让观众看清“逐笔对上再看合计”。

组件组合：`Talkcraft-scanline-annotate` + `Snapcn-TextReveal` + `Talkcraft-ink-underline` + `Rve-ChartAnimation` + `Rve-StatCounter` + `Snapcn-TextBuild` + `Rve-LineChart`。

素材：账单、表格、报价单、费用截图或模拟账单图片。样例素材说明为“新建模拟账单，133元三笔合计399元，非真实消费”。当前扫描框按样例三笔明细行与合计行的位置排列；换图要保持相同版式，可以参考外部历史备案包的 `素材/A10.png`（该素材包未随仓库附带）。异形账单需先整理为匹配的版式，数字和含义仍对应原始资料；只替换 `asset_id` 不会自动识别金额位置。

示例 content：

```json
{
  "title": "三笔账，看清总额",
  "body": "133元、133元、133元，合起来是399元。",
  "takeaway": "逐笔对上再看合计",
  "items": ["第1笔", "第2笔", "第3笔"],
  "metric": {"label": "三笔合计", "value": "399元", "detail": "133元+133元+133元"},
  "numeric_items": ["第1笔:133元", "第2笔:133元", "第3笔:133元"]
}
```

可改项：`asset_id`、`duration_seconds`、公共文案、三笔标签、`metric` 和 `numeric_items`。三条 `numeric_items` 必须同单位，合计必须等于 `metric.value`；A10 不传 `supporting_items`，也不传 `focus_steps`。

## A11 作品细节

用途：讲一张作品、插画、海报或截图中的三个细节，让观众按顺序看画面如何服务主题。

组件组合：`Talkcraft-tilt-3d-page` + `Snapcn-TextReveal` + `Snapcn-TextHighlight` + `Rve-QuoteCard` + `Snapcn-WordFlip` + `Talkcraft-source-converge` + `Talkcraft-ink-underline`。

素材：作品、插画、海报、视觉稿图片。样例素材说明为“AI生成的普通人与AI插画作品”。

示例 content：

```json
{
  "title": "一张作品，三处重点",
  "body": "人物、手机、AI形象，按顺序看它们怎样组成画面。",
  "takeaway": "细节共同回应主题",
  "items": ["人物", "手机", "AI形象"],
  "supporting_items": ["故事从普通人开始", "手机连接生活场景", "AI形象回应主题"]
}
```

可改项：`asset_id`、`duration_seconds`、公共文案、`items` 三项、`supporting_items` 三项。它适合看作品细节，不适合伪装成真实人物经历或真实产品截图。

## A12 图解关系

用途：把人、AI、信息、核对动作之间的关系讲清楚，适合关系图、流程图和节点图。

组件组合：`Talkcraft-slow-pull-reveal` + `Snapcn-TextReveal` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-ProgressSteps` + `Talkcraft-source-converge` + `Snapcn-WordFlip`。

素材：关系图、流程图、结构图、链路示意图。样例素材说明为“本地简化关系示意图，非运行记录”。

示例 content：

```json
{
  "title": "关系图，先拆三个环节",
  "body": "人提问，AI整理，人核对；确认后再采用合适结果。",
  "takeaway": "核对之后再采用",
  "items": ["人提出问题", "AI整理建议", "人核对信息"],
  "supporting_items": ["说清具体要解决什么", "提供可以检查的内容", "结合实际情况判断"]
}
```

可改项：`asset_id`、`duration_seconds`、公共文案、`items` 三项、`supporting_items` 三项。素材要保留关系全貌，不能裁掉关键节点后让文字替它补事实。

## 填写时的快速判断

有真人或生活场景，用 A07；有手机界面或功能截图，用 A08；有连续操作录屏，用 A09；有三笔同单位数字要合计，用 A10；有作品要看细节，用 A11；有关系链或流程图，用 A12。

所有字段都服务当前素材和当前旁白。素材里没有的产品事实、金额事实、操作结果或人物经历，不靠组件文案补出来；已经导入到别的任务里的素材，也不靠复用旧 `asset_id` 带进当前任务。

## 实际交付状态

A07-A12 六条实际静音样片已由 Graph 生成并发送，逐条回查附件、完整解码并检查阶段帧；A09另检查每个操作边界。五条18秒，A09为371帧、约12.37秒。全部待用户品鉴，任务和回执详见目录与JSON备案。
