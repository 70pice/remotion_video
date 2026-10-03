import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// corner-bracket-frame · 对角角框 —— 自包含 Remotion 源码（与 demos/corner-bracket-frame/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 94 };

const FPS = meta.fps;

// ─────────────────────────────────────────────────────────────────────
// 可摘走的核心动画：对角角框（两个 L 同帧对角进入 → 标题两行错峰进框）
//   ① 两个 L 角框各自沿"外侧对角方向"平移进入：左上从左上方来、右下从右下方来。
//      **必须同帧同曲线** —— 对角对称是这个构图的骨架，错峰就散架。
//   ② 标题两行错峰淡入上浮（框先立住，字后进框）。
//   ③ hold：画完静置，不做 line boil / 定格抖动（design-language §4）。
//   ※ 标题下的手绘弧线（"下划线"）已按用户 2026-08-25 定版删除。
// ─────────────────────────────────────────────────────────────────────
const CONFIG = {
  lead: 0.4,          // 起手静置 s：等口播念到
  brIn: 0.3,          // 角框进入时长 s
  brTravel: 20,       // 角框沿对角方向的进入位移 px（沿 45° 各分量都是这个值）
  lineDur: 0.3,       // 标题单行淡入时长 s
  lineRise: 6,        // 标题上浮 px
  lineStagger: 0.1,   // 两行错峰 s
  linesAt: 0.22,      // 标题起步相对角框起步的延迟 s（框先立住）
  hold: 1.7,          // 收尾停留 s：让观众读完两行
};

/* 时间表（demo 秒）
   0.40–0.70  两个 L 同帧对角进入（power3.out）
   0.62–0.92  标题第一行淡入上浮（power2.out）
   0.72–1.02  标题第二行同法
   1.02–2.72  收尾静置 */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);

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

// —— 口播语境：主持人在右，左侧标题被两个对角 L 角框框住 ——
//    中性化：白底、墨字；唯一语义色 = 青 #0aa3a3，只上在角框（动效本体）上
const CSS = `
.cb-host {                      /* 演示语境：主持人列（不属于本卡动效） */
  position: absolute;
  right: 0; top: 0; bottom: 0;
  /* 448px 给 427.7px 宽的数字人留 ≥10px 呼吸边（人物不缩小、不截断、整体往中间挪） */
  width: 448px;
}
/* 取景骨架：一个不可见的方框，只在左上 / 右下两个角画 L —— 对角对称是本构图的骨架 */
.cb-frame {
  position: absolute;
  left: 66px; top: 152px;
  width: 450px; height: 200px;
}
.cb-br {                        /* L 角框：两臂等长（命门），靠 border 画 */
  position: absolute;
  width: 54px; height: 54px;    /* = 臂长；两臂必须相等 */
}
.cb-br.tl {
  left: 0; top: 0;
  border-left: 4px solid #0aa3a3;
  border-top: 4px solid #0aa3a3;
}
.cb-br.br {
  right: 0; bottom: 0;
  border-right: 4px solid #0aa3a3;
  border-bottom: 4px solid #0aa3a3;
}
.cb-line {
  position: absolute; left: 34px;
  font-size: 52px; font-weight: 700; line-height: 1;
  color: #1d1d1f;
  letter-spacing: 1px;
  white-space: nowrap;
}
.cb-line.l1 { top: 30px; }
.cb-line.l2 { top: 104px; }
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


/* slug-specific portrait: bracket frame marks a phone-safe content area. */
.cb-frame { left: 90px !important; right: 90px !important; top: 360px !important; bottom: 360px !important; }
.cb-line { stroke-width: 6px !important; }

`;

export default function CornerBracketFrame({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  const t0 = CONFIG.lead;
  // ① 两个 L 同帧进入（同曲线同时长——对角对称）
  const brP = tw(t, t0, CONFIG.brIn, power3Out);
  const d = lerp(CONFIG.brTravel, 0, brP);
  // ② 标题两行错峰淡入上浮
  const lineAt = t0 + CONFIG.linesAt;
  const l1P = tw(t, lineAt, CONFIG.lineDur, power2Out);
  const l2P = tw(t, lineAt + CONFIG.lineStagger, CONFIG.lineDur, power2Out);

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="cb-host"></div>
      <div className="cb-frame">
        <div className="cb-br tl" style={{ opacity: brP, transform: `translate(${-d}px, ${-d}px)` }} />
        <div className="cb-br br" style={{ opacity: brP, transform: `translate(${d}px, ${d}px)` }} />
        <div className="cb-line l1" style={{ opacity: l1P, transform: `translateY(${lerp(CONFIG.lineRise, 0, l1P)}px)` }}>一条思路</div>
        <div className="cb-line l2" style={{ opacity: l2P, transform: `translateY(${lerp(CONFIG.lineRise, 0, l2P)}px)` }}>讲清楚一件事</div>
      </div>
    </AbsoluteFill>
  );
}
