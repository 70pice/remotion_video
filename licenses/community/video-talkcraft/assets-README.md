# 原作者演示素材接入记录

上游：<https://github.com/Vincentwei1021/video-talkcraft>

固定版本：`4cd673df4b7a6a35784a0881df223721789c5e23`。

这些文件从本地已克隆的上游 Git 工作树直接复制，未重新编码，也未下载其他替代画面。
用途为本仓库里的组件演示预览；最终短视频应注入自己的素材。组件源文件不因此修改。

| 本地演示文件 | 上游文件 | 来源事实 |
| --- | --- | --- |
| `public/community/video-talkcraft/media/p-*.jpg` | `demos/_lib/media/p-*.jpg` | 上游 `ATTRIBUTION.md` 记为 Lorem Picsum 稳定 ID / Unsplash License；共 30 张 |
| `public/community/video-talkcraft/media/v-ocean.webm` | `demos/_lib/media/v-ocean.webm` | 上游记为 Mixkit 2091 海面、Free License、前 10 秒缩到 960 宽、静音 |
| `public/community/video-talkcraft/media/v-typing.webm` | `demos/_lib/media/v-typing.webm` | 上游记为 Mixkit 1811 打字、Free License、静音 |
| `public/community/video-talkcraft/dh-host.webm` | `demos/_lib/dh-host.webm` | 上游 README 称 AI 生成的演示形象占位，生产时替换为自己的素材；未找到单独素材许可文件 |
| `public/community/video-talkcraft/hand-pencil.png` | `demos/pencil-sketch-draw/hand-pencil.png` | 上游卡片说明记为绿幕抠像透明 PNG，817 × 640；未找到原摄影者、生成服务或单独素材许可文件 |

`assets-media-ATTRIBUTION.md` 是上游素材说明的逐字副本；其中限制视频不得单独或打包再分发。
这里仅作为原组件预览组成部分引用，没有把视频作为独立素材库发布。
`assets-host-README-excerpt.md` 与 `assets-hand-card.md` 保留上述主持人和手部图的原始描述。

映射依据是上游 `demos/_lib/media/ATTRIBUTION.md`、每张 `demos/<slug>/index.html`，
以及 `demos/_lib/demo-shell.js` 的主持人注入逻辑；实现位于
`src/components/component-horizontal/video-talkcraft/preview-props.ts`。

注意这些预览不是网站的完整录屏复刻：原卡保留系统字体回退；原 HTML 的额外音效来自
`demos/_lib/sfx*.js`，这 108 个 TSX 卡本身没有 `Audio`，本次没有补造音轨。
两张多版式巡演由预览 wrapper 按原时间表切换原照片，以补上原 TSX `srcs` prop 的演示上下文。

另外，上游 52 张原卡含全局 CSS reset。单独预览可保留，未来成片叠加其他组件时应隔离样式。
