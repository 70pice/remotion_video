import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// lower-third-nameplate · 人名条展示牌 —— 自包含 Remotion 源码（与 demos/lower-third-nameplate/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 107 };

const FPS = meta.fps;

// —— 可摘走的核心动画：色条展开 → 姓名揭示 → 头衔跟进 → 反向收回 ——
const CONFIG = {
  barDur: 0.3,       // 色条 scaleX 展开时长 s
  nameDur: 0.25,     // 姓名 clip-path 揭示时长 s
  titleLag: 0.15,    // 头衔相对姓名的延迟 s：同时出 = 层次塌
  hold: 2.0,         // 停留 s（实拍建议 3~5s，demo 压短）
  outDur: 0.3,       // 出场时长 s：反向收回，不是淡出
};

/* 时间表（demo 秒）
   0.40–0.70  色条 scaleX 0→1（power4.out）
   0.61–0.86  姓名 clip 从左揭示（power2.out，色条走完 70% 时起步）
   0.76–1.01  头衔同法（延迟 0.15）
   2.70–2.91  头衔反向收回（power2.in）
   2.78–2.99  姓名反向收回（power2.in）
   2.86–3.16  色条 scaleX→0（power4.in） */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power4Out = (x: number) => 1 - Math.pow(1 - x, 5);
const power2In = (x: number) => x * x * x;
const power4In = (x: number) => x * x * x * x * x;

// 主持人占位：演示语境素材，不属于动效本体
const Host: React.FC<{ src?: string }> = ({ src }) => (
  <div style={{ position: "absolute", inset: 0, display: "flex",
                alignItems: "flex-end", justifyContent: "center", background: "#fff" }}>
    {src ? (
      <Loop durationInFrames={13 * FPS}>
        <OffthreadVideo src={src} muted transparent style={{
          position: "absolute", bottom: 0, left: "50%",
          transform: "translateX(-50%)", height: "88%" }} />
      </Loop>
    ) : (
      <div style={{ width: "42%", height: "78%", background:
        "radial-gradient(ellipse 46% 26% at 50% 13%, #e3e3e6 60%, transparent 61%)," +
        "radial-gradient(ellipse 50% 62% at 50% 84%, #ececef 60%, transparent 61%)" }} />
    )}
  </div>
);

// —— 口播语境：真人出镜访谈画面，左下打人名条 ——
const CSS = `
.lt {
  position: absolute;
  left: 56px; bottom: 64px;
}
.lt .name {
  font-size: 42px;
  font-weight: 800;
  color: #1d1d1f;
  line-height: 1.15;
  letter-spacing: 2px;
}
/* 色条 = 动效本体（scaleX 展开的那根）。中性墨色；复用时这里换品牌色 */
.lt .bar {
  height: 7px;
  width: 100%;
  background: #1d1d1f;
  border-radius: 2px;
  margin: 10px 0 10px;
  transform-origin: left center;
}
.lt .title {
  font-size: 19px;
  color: #8a8a8a;
  letter-spacing: 1.5px;
}
`;


const PORTRAIT_CSS = `

/* Native portrait override for 1080x1920. Original CONFIG/tween/data code above is retained. */
* { box-sizing: border-box; }
.host-wrap, .host-badge, .host-col, .host-full, .bt-host, .cb-host { display: none !important; }
.doc-eyebrow, .doc-head, .ch-label { left: 80px !important; right: 80px !important; top: 120px !important; font-size: 28px !important; letter-spacing: 4px !important; text-align: left !important; }
.table-card { left: 80px !important; top: 240px !important; width: 920px !important; min-height: 780px !important; border-radius: 34px !important; padding-top: 24px !important; box-shadow: 0 36px 110px rgba(15,23,42,.12) !important; }
.trow { padding: 34px 44px !important; grid-template-columns: 1.35fr 1fr .8fr .8fr !important; }
.trow.head { font-size: 25px !important; padding: 10px 44px 24px !important; }
.trow.data { font-size: 37px !important; border-top-width: 2px !important; }
.card-foot { padding: 30px 44px !important; font-size: 25px !important; }
.spot, .ring { border-radius: 24px !important; }
.panel { left: 80px !important; top: 250px !important; width: 920px !important; height: 1350px !important; }
.panel .title, .chart-title { left: 0 !important; top: 0 !important; font-size: 76px !important; line-height: 1.08 !important; font-weight: 750 !important; }
.chart { left: 0 !important; right: 0 !important; bottom: 160px !important; width: 920px !important; height: 760px !important; }
.bars { gap: 22px !important; }
.bar { width: 82px !important; border-radius: 14px 14px 0 0 !important; }
.baseline { height: 5px !important; }
.xlabels { bottom: -66px !important; font-size: 28px !important; }
.xlabels span { width: 82px !important; }
.grow-chip { font-size: 42px !important; padding: 18px 30px !important; border-radius: 24px !important; }
.chart-wrap { left: 70px !important; top: 275px !important; width: 940px !important; height: 1220px !important; }
.axis-x, .axis-y { font-size: 26px !important; }
.bar-year, .bar-val { font-size: 28px !important; }
.annot { font-size: 32px !important; }
.qh-block { left: 72px !important; right: 72px !important; top: 360px !important; bottom: auto !important; min-height: 960px !important; }
.qh-line, .quote-line { font-size: 72px !important; line-height: 1.2 !important; }
.sr-line { left: 74px !important; right: 74px !important; top: 650px !important; font-size: 86px !important; line-height: 1.2 !important; }
.lt, .clt { left: 70px !important; right: 70px !important; bottom: 220px !important; min-height: 260px !important; }
.name { font-size: 72px !important; }
.title { font-size: 38px !important; }
.bt-title { left: 70px !important; right: 70px !important; top: 510px !important; font-size: 112px !important; line-height: .98 !important; }
.bt-sub { left: 76px !important; right: 76px !important; top: 980px !important; font-size: 42px !important; }
.czp-shot { left: 70px !important; right: 70px !important; top: 360px !important; bottom: 300px !important; }
.czp-k, .czp-tg { font-size: 92px !important; }
.db-b { font-size: 44px !important; padding: 24px 34px !important; border-radius: 999px !important; }
.dfc-card, .xfc-card, .sub-card { left: 70px !important; right: 70px !important; top: 360px !important; min-height: 1040px !important; border-radius: 56px !important; }
.hcg-card, .hstc-card, .parallel-wrap { left: 70px !important; right: 70px !important; top: 260px !important; bottom: 210px !important; border-radius: 46px !important; }
.hl-wrap, .quote-card, .mag-inner, .ruler, .scan-card, .reticle-scene, .cb-frame { left: 70px !important; right: 70px !important; top: 290px !important; bottom: 260px !important; width: auto !important; height: auto !important; border-radius: 42px !important; }
.hl-block, .quote-line, .line, .fine, .body, .lab { font-size: 48px !important; line-height: 1.35 !important; }
.scaler { left: 70px !important; top: 260px !important; }
.card { border-radius: 56px !important; }
.cover { min-height: 580px !important; }
.cursor { transform-origin: 0 0 !important; }
.piwh-card { transform-origin: center center !important; }
.piwh-tag { font-size: 30px !important; left: 52px !important; top: 50px !important; }


/* slug-specific portrait: nameplate sits in the short-video lower third at readable size. */
.lt { left: 90px !important; right: 90px !important; bottom: 520px !important; transform: scale(1.45) !important; transform-origin: 0 100% !important; }

`;

export default function LowerThirdNameplate({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  const t0 = 0.4;
  const nameAt = t0 + CONFIG.barDur * 0.7;               // 色条走完 70% 时姓名起步
  const titleAt = nameAt + CONFIG.titleLag;
  const outAt = t0 + CONFIG.barDur + CONFIG.hold;        // = 2.7

  // 色条：scaleX 展开（power4.out）→ 最后反向收回（power4.in）
  const barScale = t < outAt + 0.16
    ? tw(t, t0, CONFIG.barDur, power4Out)
    : 1 - tw(t, outAt + 0.16, CONFIG.outDur, power4In);

  // 姓名/头衔：clip-path 从左揭示（shown = 可见比例 0~1）
  const nameShown = t < outAt + 0.08
    ? tw(t, nameAt, CONFIG.nameDur, power2Out)
    : 1 - tw(t, outAt + 0.08, CONFIG.outDur * 0.7, power2In);
  const titleShown = t < outAt
    ? tw(t, titleAt, CONFIG.nameDur, power2Out)
    : 1 - tw(t, outAt, CONFIG.outDur * 0.7, power2In);

  const clip = (shown: number) => `inset(0% ${(1 - shown) * 100}% 0% 0%)`;

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      
      <div className="lt">
        <div className="name" style={{ clipPath: clip(nameShown) }}>王砚秋</div>
        <div className="bar" style={{ transform: `scaleX(${barScale})` }} />
        <div className="title" style={{ clipPath: clip(titleShown) }}>半导体行业分析师 · 从业 14 年</div>
      </div>
    </AbsoluteFill>
  );
}
