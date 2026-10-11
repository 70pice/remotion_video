# 扩展无素材组件套 B07-B18

这份说明用于登记和复用 B07-B18 十二套无素材 rich 组件套。无素材不是“空画面”，而是不传外部图片、录屏或视频；画面由 `content` 里的问题、条目、数字、模拟对话和它们之间的关系组成。

十二套都已通过正常 `POST /api/jobs/{job_id}/component-demo` 入口提交，指定 `composition: "rich"`，由 Worker 执行 `component_demo → director_demo → end`。每条实际样片均为 18 秒，已发送并回查；catalog / demos / registry 已按真实任务输出、`director_plan.actual_composition_components`、媒体回执和独立分支记录完成备案。下面列出用途、输入契约和可改参数。样片生成和发送只代表可品鉴，不代表人工通过。

## 通用输入与边界

- 必填公共字段：`content.title`、`content.body`、`content.takeaway`。标题和收束句最多 18 字，正文最多 60 字。
- 时长：12–20 秒，按表达复杂度调整。B07-B18 当前设计多为 18 秒，不是强制固定。
- 禁止字段：`asset_id`、`tutorial_steps`、`focus_steps`、任意时间轴、JSX、CSS、组件 props。
- `metric.value` 必须是 0–99999 的 ASCII 整数加 1–2 个汉字单位，例如 `6分钟`、`100元`、`3项`、`3问`。不接受百分号、小数、风险分、证据权重。
- `numeric_items` 格式为 `标签:数字加单位`，同一套必须使用同一单位；B04/B10 等账本类必须能和 `metric.value` 对上。
- 演示数字只表示分配、计数、步骤、预算、时长或算术关系；不能写成真实统计、真实价格、风险概率、成功率或调查结论。
- 图层文案只能从已传入的 `content` 字段派生，不能在组件内部新增事实。
- 下方组件组合用于说明当前后端契约；正式备案以每套真实 `director_plan.actual_composition_components` 回填，不从早期设计表推断。

## 十二套分工

| 套件 | 什么时候用 | 需要的额外内容 | 数字边界 |
| --- | --- | --- | --- |
| B07 时间分配 | 旁白讲“先花几分钟分开做三件事”、解释时间分配或提醒观众先停一下再操作时使用。 | title/body/takeaway、items 三项、metric 合计、numeric_items 三项同单位时长 | 演示口径，不代表现实统计或效果承诺 |
| B08 预算拆分 | 旁白需要讲预算去向、付款前先看用途时使用。 | title/body/takeaway、items 三项、metric 合计、numeric_items 三项同单位金额 | 演示口径，不代表现实统计或效果承诺 |
| B09 数字差 | 旁白对比“直接照做”和“先回拨核实”等两种做法时使用。 | title/body/takeaway、items 两项、metric 差值、numeric_items 两项同单位动作数 | 演示口径，不代表现实统计或效果承诺 |
| B10 累计账本 | 旁白讲“单次看不大，但合起来要算总账”时使用。 | title/body/takeaway、items 三项账本标签、metric 合计、numeric_items 三笔同单位数字 | 演示口径，不代表现实统计或效果承诺 |
| B11 条件分支 | 旁白需要讲“如果出现这种条件，就做这个动作”的流程判断时使用。 | title/body/takeaway、items 三个条件、supporting_items 三个动作、metric 分支数 | 演示口径，不代表现实统计或效果承诺 |
| B12 关系链 | 旁白解释 AI文字、真人视频、付款入口等链路关系时使用。 | title/body/takeaway、items 三个节点、supporting_items 三个追问、metric 节点数 | 演示口径，不代表现实统计或效果承诺 |
| B13 误区纠正 | 旁白纠正“会聊天就可信”“能视频就是真人”等捷径判断时使用。 | title/body/takeaway、items 两个前后说法、supporting_items 三个拆解点、metric 条目数 | 演示口径，不代表现实统计或效果承诺 |
| B14 提问回答 | 旁白采用问答结构，例如“视频通话就可信吗？”时使用。 | title/body/takeaway、items 三个行动点、supporting_items 两条模拟对话、metric 核实点数 | 演示口径，不代表现实统计或效果承诺 |
| B15 核实状态分类 | 旁白需要区分“有人这么说”“有出处”“还没确认”时使用。 | title/body/takeaway、items 三类状态、supporting_items 三条解释、metric 类别数、numeric_items 三项同单位分类计数 | 演示口径，不代表现实统计或效果承诺 |
| B16 优先级排序 | 旁白讲“先看A，再看B，最后看C”的操作建议时使用。 | title/body/takeaway、items 三个检查项、supporting_items 三条解释、metric 检查项数 | 演示口径，不代表现实统计或效果承诺 |
| B17 倒数检查 | 旁白提醒“转账前先问自己三件事”“先暂停一下”时使用。 | title/body/takeaway、items 三个问题、supporting_items 两条模拟对话、metric 问题数 | 演示口径，不代表现实统计或效果承诺 |
| B18 操作步骤前后 | 旁白讲“以前只做一步，现在拆成三步”或解释操作改造前后时使用。 | title/body/takeaway、items 两项前后对比、supporting_items 三个新步骤、metric 新步骤数、numeric_items 两项同单位步骤数 | 演示口径，不代表现实统计或效果承诺 |

## B07 时间分配

用途：把核对动作拆成几个时间块，说明先看、再回拨、再记录的时间分配。

什么时候用：旁白讲“先花几分钟分开做三件事”、解释时间分配或提醒观众先停一下再操作时使用。

组件组合：`Rve-ChartAnimation` + `Talkcraft-typewriter-reveal` + `Snapcn-TextHighlight` + `Rve-QuoteCard` + `Rve-StatCounter` + `Rve-ProgressSteps` + `Snapcn-WordFlip`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三项、metric 合计、numeric_items 三项同单位时长。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "6分钟，分三段做",
  "body": "这里演示的是时间分配，不是风险规律。",
  "takeaway": "分开核对",
  "items": [
    "看清消息",
    "回拨核实",
    "留下记录"
  ],
  "metric": {
    "label": "演示分配合计",
    "value": "6分钟",
    "detail": "2分钟+3分钟+1分钟"
  },
  "numeric_items": [
    "看消息:2分钟",
    "回拨:3分钟",
    "记录:1分钟"
  ]
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B08 预算拆分

用途：把一个演示预算拆成几类去向，让观众先看钱流向哪里。

什么时候用：旁白需要讲预算去向、付款前先看用途时使用。

组件组合：`Rve-StatCounter` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-ChartAnimation` + `Snapcn-WordFlip` + `Talkcraft-ink-underline`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三项、metric 合计、numeric_items 三项同单位金额。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "100元，先拆开看",
  "body": "这只是演示预算，不代表实际收费。",
  "takeaway": "先看去向",
  "items": [
    "沟通费用",
    "核实成本",
    "预留不付"
  ],
  "metric": {
    "label": "演示预算合计",
    "value": "100元",
    "detail": "30元+20元+50元"
  },
  "numeric_items": [
    "沟通:30元",
    "核实:20元",
    "预留:50元"
  ]
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B09 数字差

用途：比较两个选择多了哪一步动作，强调差别是操作数量，不是安全概率。

什么时候用：旁白对比“直接照做”和“先回拨核实”等两种做法时使用。

组件组合：`Rve-ComparisonChart` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-StatCounter` + `Talkcraft-strike-and-replace`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 两项、metric 差值、numeric_items 两项同单位动作数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "差的不是快慢",
  "body": "这里比较的是动作数量，不评价结果概率。",
  "takeaway": "多一步核对",
  "items": [
    "直接判断：看完就做",
    "回拨核实：再确认一次"
  ],
  "metric": {
    "label": "多出的核对动作",
    "value": "1步",
    "detail": "2步-1步"
  },
  "numeric_items": [
    "直接判断:1步",
    "回拨核实:2步"
  ]
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B10 累计账本

用途：把多次小额或重复动作加成总账，提醒观众看累计口径。

什么时候用：旁白讲“单次看不大，但合起来要算总账”时使用。

组件组合：`Rve-ChartAnimation` + `Snapcn-TextBuild` + `Snapcn-TextHighlight` + `Rve-StatCounter` + `Rve-LineChart` + `Talkcraft-ink-underline`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三项账本标签、metric 合计、numeric_items 三笔同单位数字。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "三次小额，合起来看",
  "body": "这是算账演示，不代表真实消费记录。",
  "takeaway": "看总账",
  "items": [
    "第1次",
    "第2次",
    "第3次"
  ],
  "metric": {
    "label": "三次合计",
    "value": "399元",
    "detail": "133元+133元+133元"
  },
  "numeric_items": [
    "第1次:133元",
    "第2次:133元",
    "第3次:133元"
  ]
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B11 条件分支

用途：把条件和对应动作配对，形成 if/then 的操作分支。

什么时候用：旁白需要讲“如果出现这种条件，就做这个动作”的流程判断时使用。

组件组合：`Rve-ProgressSteps` + `Snapcn-TextBuild` + `Snapcn-AnswerHighlight` + `Rve-SplitScreen` + `Rve-StatCounter` + `Talkcraft-word-slot-cycle`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三个条件、supporting_items 三个动作、metric 分支数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "先看条件，再做动作",
  "body": "条件分支只是演示流程，不代表自动判断。",
  "takeaway": "按条件走",
  "items": [
    "能公开核对",
    "只催私下付款",
    "说法前后不一"
  ],
  "supporting_items": [
    "回拨确认",
    "暂停付款",
    "截图留存"
  ],
  "metric": {
    "label": "演示分支",
    "value": "3项",
    "detail": "三个条件对应三个动作"
  }
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B12 关系链

用途：把多个角色或环节画成关系链，帮助观众分清谁在聊天、谁在接管、钱到哪里。

什么时候用：旁白解释 AI文字、真人视频、付款入口等链路关系时使用。

组件组合：`Rve-QuoteCard` + `Snapcn-WordFlip` + `Snapcn-TextHighlight` + `Talkcraft-source-converge` + `Rve-StatCounter` + `Rve-ProgressSteps`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三个节点、supporting_items 三个追问、metric 节点数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "先把关系链画出来",
  "body": "这是一张角色关系示意，不是事实认定。",
  "takeaway": "分清角色",
  "items": [
    "AI文字",
    "真人视频",
    "付款入口"
  ],
  "supporting_items": [
    "谁在聊天",
    "谁在接管",
    "钱到哪里"
  ],
  "metric": {
    "label": "链路节点",
    "value": "3个",
    "detail": "演示关系，不是案件事实"
  }
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B13 误区纠正

用途：把一句常见误区改写成更准确的判断方式。

什么时候用：旁白纠正“会聊天就可信”“能视频就是真人”等捷径判断时使用。

组件组合：`Rve-SplitScreen` + `Rve-QuoteCard` + `Snapcn-TextRewrite` + `Snapcn-TextHighlight` + `Snapcn-TextSwap` + `Rve-StatCounter` + `Talkcraft-error-retype` + `Talkcraft-strike-and-replace`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 两个前后说法、supporting_items 三个拆解点、metric 条目数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "会聊天不等于可信",
  "body": "纠正的是一句判断方式，不是给某个对象下结论。",
  "takeaway": "先核实身份",
  "items": [
    "会聊天＝真人",
    "会聊天≠可信"
  ],
  "supporting_items": [
    "能接话",
    "能视频",
    "能核实"
  ],
  "metric": {
    "label": "纠正点",
    "value": "3条",
    "detail": "三条是表达拆解"
  }
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B14 提问回答

用途：把一个观众问题变成模拟问答，再落到几项可执行核实点。

什么时候用：旁白采用问答结构，例如“视频通话就可信吗？”时使用。

组件组合：`Snapcn-AnswerStream` + `Snapcn-SearchTyping` + `Snapcn-AnswerHighlight` + `Bits-ChatConversation` + `Snapcn-TextBuild` + `Rve-StatCounter`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三个行动点、supporting_items 两条模拟对话、metric 核实点数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "视频通话就可信吗？",
  "body": "回答是机制示意，不是真实对话记录。",
  "takeaway": "视频也要核实",
  "items": [
    "看号码",
    "问来源",
    "停付款"
  ],
  "supporting_items": [
    "对方：我可以视频",
    "我：先核对号码"
  ],
  "metric": {
    "label": "核实点",
    "value": "3项",
    "detail": "演示问答，不是判断结论"
  }
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B15 核实状态分类

用途：把说法分成自述、有来源、待核三类，提醒观众标出待核状态。

什么时候用：旁白需要区分“有人这么说”“有出处”“还没确认”时使用。

组件组合：`Rve-QuoteCard` + `Talkcraft-title-demote-to-label` + `Snapcn-TextHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Rve-ChartAnimation` + `Snapcn-TextBuild`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三类状态、supporting_items 三条解释、metric 类别数、numeric_items 三项同单位分类计数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "先分三类状态",
  "body": "分类只是帮助整理，不代表证据权重。",
  "takeaway": "待核要标出来",
  "items": [
    "自述",
    "有来源",
    "待核"
  ],
  "supporting_items": [
    "自己说的",
    "能找到出处",
    "还没确认"
  ],
  "metric": {
    "label": "核实状态",
    "value": "3类",
    "detail": "分类演示，不是证据等级"
  },
  "numeric_items": [
    "自述:1类",
    "有来源:1类",
    "待核:1类"
  ]
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B16 优先级排序

用途：把检查动作排成先后顺序，告诉观众先看什么、再看什么。

什么时候用：旁白讲“先看A，再看B，最后看C”的操作建议时使用。

组件组合：`Rve-ProgressSteps` + `Talkcraft-title-demote-to-label` + `Talkcraft-keyword-pop-highlight` + `Rve-StatCounter` + `Snapcn-WordFlip` + `Rve-QuoteCard` + `Snapcn-TextHighlight`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三个检查项、supporting_items 三条解释、metric 检查项数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "先看哪三件事",
  "body": "顺序是操作建议，不是风险排序。",
  "takeaway": "先看付款动作",
  "items": [
    "付款动作",
    "身份来源",
    "联系号码"
  ],
  "supporting_items": [
    "是否让你转钱",
    "身份能否回查",
    "号码是否熟悉"
  ],
  "metric": {
    "label": "优先检查",
    "value": "3项",
    "detail": "操作顺序演示"
  }
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B17 倒数检查

用途：用倒数三问制造停顿，让观众在转账、付款或行动前先自检。

什么时候用：旁白提醒“转账前先问自己三件事”“先暂停一下”时使用。

组件组合：`Bits-ChatConversation` + `Talkcraft-line-by-line-slide` + `Snapcn-AnswerHighlight` + `Rve-ProgressSteps` + `Rve-StatCounter` + `Snapcn-TextBuild`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 三个问题、supporting_items 两条模拟对话、metric 问题数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "转账前倒数三问",
  "body": "这是停顿检查，不是真实聊天判断。",
  "takeaway": "三问不过不付",
  "items": [
    "谁让我付",
    "钱到哪里",
    "能否回拨"
  ],
  "supporting_items": [
    "对方：先转一点",
    "我：先过三问"
  ],
  "metric": {
    "label": "倒数检查",
    "value": "3问",
    "detail": "操作前自检"
  }
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。

## B18 操作步骤前后

用途：对比旧做法和新做法，把原来一步拆成更清楚的几步。

什么时候用：旁白讲“以前只做一步，现在拆成三步”或解释操作改造前后时使用。

组件组合：`Rve-ComparisonChart` + `Snapcn-TextSwap` + `Snapcn-TextHighlight` + `Rve-SplitScreen` + `Rve-ProgressSteps` + `Talkcraft-strike-and-replace`。背景、边框、连接线不登记为原生组件。

入参：title/body/takeaway、items 两项前后对比、supporting_items 三个新步骤、metric 新步骤数、numeric_items 两项同单位步骤数。公共字段仍为 `title`、`body`、`takeaway`。

示例 content：

```json
{
  "title": "以前一步，现在三步",
  "body": "这里只比较操作步骤，不声称效果提升。",
  "takeaway": "把动作拆开",
  "items": [
    "以前：看完就回复",
    "现在：看清再核对"
  ],
  "supporting_items": [
    "看消息",
    "回拨核实",
    "记录结果"
  ],
  "metric": {
    "label": "现在步骤",
    "value": "3步",
    "detail": "操作拆分演示"
  },
  "numeric_items": [
    "以前:1步",
    "现在:3步"
  ]
}
```

可改项：`duration_seconds`、`content.title`、`content.body`、`content.takeaway`、各数组字段整体内容，以及 `content.metric.label`、`content.metric.value`、`content.metric.detail`。组件组合、字段数量、数字单位规则、白字深色底和无素材边界固定。

数字边界：本套数字只用于演示分配、计数、步骤或算术关系；真实视频使用时必须替换为当前任务有来源的事实，或明确写成演示口径。
