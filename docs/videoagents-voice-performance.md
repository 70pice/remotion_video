# 配音的讲述风格与起伏

## 当前复刻音色的两种模型

字节声音复刻 2.0 的 `seed-tts-2.0-standard` 不支持语音指令；即使传入表演说明，也会被过滤。`seed-tts-2.0-expressive` 是表现力增强版，支持自然语言描述讲述方式。音色 ID 保持自己的 `S_...`，资源 ID 使用 `seed-icl-2.0`，账号是否有对应权限以实际调用结果为准。[官方双向 WebSocket V3 文档](https://docs.volcengine.com/docs/6561/1329505?lang=zh)

## 工作台设置

在「设置 → 你的声音」选择字节 WebSocket，填入 `seed-tts-2.0-expressive`，再填写「讲述风格」。例如：

> 像面对观众讲解一个新发现。开头的问题带好奇，重点词加重，长句有自然停顿，结尾坚定收住。语气有变化，避免机械播报和夸张喊叫。

「语速调整」默认 0，支持 -50 到 100；它控制整体速度，不能代替情绪、重音和停顿指导。风格变化后需要重新生成音频，字幕及分镜要依据新音频重新对齐，已有视频不会自动改变。

配音节点保留原文，先检查朗读风险，然后将用户的讲述风格和模型的 `delivery_notes` 合并成一条表演指令。用户设置优先；已生成且匹配当前配置和正文的音频仍可复用。模型建议不等于实际试听结果。

## 实际请求与恢复

双向接口将讲述风格放在 `req_params.additions` 中。这个字段是 **JSON 字符串**，内部的 `context_texts` 是数组，只有第一条有效；语速放在 `req_params.audio_params.speech_rate`。例如：

```python
req_params = {
    "model": "seed-tts-2.0-expressive",
    "speaker": "自己的复刻音色 ID",
    "audio_params": {
        "format": "mp3",
        "sample_rate": 24000,
        "enable_subtitle": True,
        "speech_rate": 0,
    },
    "additions": json.dumps({"context_texts": ["自然讲解，问题带好奇，重点加重。"]}, ensure_ascii=False),
}
```

请求指纹绑定实际表演指令与语速，音频配置指纹绑定用户设置；改变风格不能复用旧风格的音频。正文提交后的未知结果仍按 `UNKNOWN` 暂停，换模型或风格不会绕过对账要求。

本项目的表演指令先支持 WebSocket 的复刻 expressive 模型。standard 和旧 HTTP 配置不能静默接受不生效的显式风格。没有给当前复刻音色强行添加未经确认的 `emotion="happy"` 枚举，也没有把双向接口不支持的 SSML `<break>` 塞进口播正文。[官方 SSML 说明](https://docs.volcengine.com/docs/DoubaoVoice/SSMLmarkuplanguage?lang=zh)

表现力增强版仍可能存在随机性。先生成短样音，实际听重音、节奏、专名发音和音色，再决定用于全稿。[声音复刻 2.0 最佳实践](https://docs.volcengine.com/docs/DoubaoVoice/SoundReplication20BestPractices?lang=zh)
