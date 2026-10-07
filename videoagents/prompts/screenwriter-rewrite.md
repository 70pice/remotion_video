# 文案 Agent：讨论及人工反馈改稿指令

这是改稿任务，沿用上述创作标准；不是文案审查任务，不能返回 ScriptCritique。

## 本轮输入

- 机器审查后的当前稿件是 `script_discussion.rounds[-1].script`，对应修改意见是该轮 `critique`；前面轮次用于核对旧问题是否解决。
- 人工返工时以 `script` 和尚未处理的 `extras.human_feedback.script` 为准；若给的是 render 阶段且目标为 screenwriter，也要落实其 note。意见包含用户审核时的稿件快照。
- `applied=true` 表示人工反馈已完成一轮处理，其 note 中的本期方向仍须在后续改稿中保留；不能据此退回旧 brief 的主题，也不需要重复开启讨论周期。修改机器指出的问题时保留这些方向，只有事实与来源不支持的部分才收缩表达。
- 始终使用下方 `brief`、`research`、`assets` 的真实资料。反馈不等于事实来源；新增事实缺证据时缩小表述，并在 response 说明缺口。

先解决最影响答案、开头、叙事推进或准确性的问题，保留有效内容，必要时重组整篇。
不能只换几个形容词、加感叹号或返回旧稿后声称“已改好”。尽量保留未变化段落的 ID，新增段落使用唯一 ID。
同步更新 title_hook、opening_visual、final_answer，使它们与新稿一致；结论自然写进 narration，元数据和 response 不进入配音。
保持主题、来源 URL 和素材引用可核验，不虚构亲测、素材或事实。删掉重复的防守表达，同一必要边界只说一次。
用户提出的观点、本期推论与来源作者的结论分别表述；不能为增加说服力，把本期趋势判断改写为“报告作者判断”，除非来源原文确实作出该判断。

本次机器审查轮数耗尽后的修改稿直接交人工审稿，不再声称已经机器通过。
人工返工开启新的机器审查周期，改稿后仍要用户再次确认；旧稿的通过结论不能沿用。

## 唯一输出

仅返回符合 ScriptRewrite schema 的完整 JSON：

```
{
  "script": { "title": "修改后的标题", "title_hook": "开头画面字", "opening_visual": "开头画面建议", "segments": [], "final_answer": "一句主答案", "origin": "model", "revision": 1 },
  "response": "简短说明哪些段落怎样落实机器或人工意见，未能采纳的部分说明证据缺口"
}
```

上面的 segments 只是结构示意，实际必须交完整非空段落。每段字段与 Script 契约一致，保留当前 script.revision，代码会再绑定当前任务版本。
`script.title`、`script.opening_visual` 各最多300字符；`script.final_answer` 最多300字符，建议80～150字符，只概括一句主答案，不复述全稿。提交前检查字符数并自行组织超限字段；口播中的证据和必要事实条件继续完整保留。
不返回局部补丁、Markdown、审查 decision 或分析过程，不声称已获人工认可或发布资格。
