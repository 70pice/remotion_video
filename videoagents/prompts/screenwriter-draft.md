# 文案 Agent：初稿交付指令

读取下方上下文 JSON 的 brief、research、assets，按照上述创作标准写完整初稿。
仅返回符合 Script schema 的 JSON，不加 Markdown、解释文字或分析过程。

- 填写 title、title_hook、opening_visual、final_answer；画面建议只描述现有素材或可解释的结构化画面，不虚构已拍摄镜头。
- segments 按口播顺序排列，每段填写唯一 segment_id、narration、screen_text、source_refs、asset_ids。
- 专业词第一次出现先说人话；只保留真正推动本期答案的数字，简化不能改变原始统计口径。
- 每段 source_refs 必须有真实来源，逐段对应正文。来源和 limitations 是写作边界，不是固定口播免责声明。
- 所有 narration 连起来应像一个人在讲一件事，结尾自然回答开头，不要单独宣布“我的观点”。
- origin 填 model，revision 填 1；当前任务版本由代码绑定。
