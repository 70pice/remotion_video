import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// strike-and-replace · 划线纠错替换 —— 自包含 Remotion 源码（与 demos/strike-and-replace/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 98 };

const FPS = meta.fps;

// ─────────────────────────────────────────────────────────────────────────
// 可摘走的核心动画：划线纠错替换（"不是 A，而是 B"）
//   三拍：
//     快斩    划掉线 scaleX 0→1，0.15s power3.out（origin left，线高 = 字号 8%）
//     立换    +0.1s 旧值淡出 + 新值从 y+8 同位淡入 0.25s（同位叠放 ⇒ 替换感）
//     定格    划线与新值同屏 hold：论证已完成，让观众读
//   变体 b（value-swap）：把 from/to 里更长的字符串当隐形尺子撑宽容器，
//   换值零位移——本卡的 .ruler 就是它，两个变体共用同一套骨架。
// ─────────────────────────────────────────────────────────────────────────
const CONFIG = {
  strikeDur: 0.15,   // 划线时长 s：一瞬间的快斩（>0.4s 读作"慢慢涂"）
  swapLag: 0.10,     // 交换相对划线结束的延迟 s：斩完立刻换，不留犹豫
  swapDur: 0.25,     // 交换时长 s（旧值淡出 + 新值升入）
  hold: 2.0,         // 定格 s：划线 + 新值同屏，让观众读完"旧 → 新"
  lead: 0.35,        // 起手静置：等口播念到这个数
  toRise: 8,         // 新值从下方多少 px 升入（约字号 20%）
  keepStrike: true,  // 划线是否留在屏上（false = 交换时一起淡出，读作"改完了"）
  from: "128K",      // 旧值
  to: "1M",          // 新值
};

/* 时间表（demo 秒）
   0.35–0.50  划线 scaleX 0→1（power3.out）
   0.60–0.85  旧值淡出（power1.out）+ 新值 y 8→0 淡入（power2.out）
   0.85–2.85  hold 定格 */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);
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

// —— 演示语境（不属于动效）：主持人占左一列，右侧白区排一句口播句子 ——
const CSS = `
.host-wrap { position: absolute; left: 0; top: 0; bottom: 0; width: 47%; overflow: hidden; }
.sr-line {
  position: absolute;
  left: 45%; right: 3%;
  top: 50%; transform: translateY(-50%);
  font-size: 32px; font-weight: 700; line-height: 1.5;
  white-space: nowrap;                  /* 单行：替换槽后面必须还有字，才看得出"零位移" */
  color: #1d1d1f;
}
/* 替换槽：inline-block，宽度由"隐形尺子"撑住——旧字与新字都绝对定位在它里面，占同一个位置 */
.slot { position: relative; display: inline-block; vertical-align: baseline; }
/* 隐形尺子：把 from / to 里更长的那一串排进来占位、visibility:hidden。容器宽度一次定死，换值零位移 */
.ruler { visibility: hidden; white-space: nowrap; }
/* 两个值都以槽的中线为锚（translateX(-50%)），短值在预留宽度里居中 */
.word {
  position: absolute; left: 50%; top: 0;
  white-space: nowrap;
  will-change: transform, opacity;
}
.word.from { color: #1d1d1f; }          /* 旧值保持墨色——语义色只上那条线 */
.word.to { color: #1d1d1f; }            /* 新值也是墨色：变色会抢掉"划掉"这一拍 */
/* 划掉线：唯一的语义色。origin left + scaleX 0→1。它是 .word.from 的子节点 ⇒ 旧值淡出时线跟着一起走 */
.strike {
  position: absolute; left: 0; top: 50%;
  height: 3px;                          /* = 字号 8%，随字号等比 */
  width: 100%;
  background: #e0452c;
  border-radius: 2px;
  transform-origin: left center;
  will-change: transform;
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


/* slug-specific portrait: native multiline sentence; replacement slot owns its own strike geometry. */
.sr-line { left:80px!important; right:80px!important; top:620px!important; width:920px!important; transform:none!important; font-size:76px!important; line-height:1.28!important; white-space:normal!important; letter-spacing:-2px!important; }
.slot { min-width:150px!important; text-align:center!important; }
.word { top:0!important; }
.strike { height:7px!important; border-radius:999px!important; }
.slot > .strike { left:0!important; top:50%!important; width:100%!important; }

`;

export default function StrikeAndReplace({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  // ① 划线：一瞬间快斩到底（power3.out 冲出去收住）
  const strikeX = tw(t, CONFIG.lead, CONFIG.strikeDur, power3Out);

  // ② 交换：斩完立刻换——旧值淡出、新值从 y+8 淡入回落（同位叠放 ⇒ 替换感）
  const swapAt = CONFIG.lead + CONFIG.strikeDur + CONFIG.swapLag;
  const fromOpacity = 1 - tw(t, swapAt, CONFIG.swapDur, power1Out);
  const toP = tw(t, swapAt, CONFIG.swapDur, power2Out);
  const toY = lerp(CONFIG.toRise, 0, toP);
  const strikeOpacity = CONFIG.keepStrike ? 1 : fromOpacity;

  // 尺子：from / to 里更长的那一串
  const longer = CONFIG.from.length >= CONFIG.to.length ? CONFIG.from : CONFIG.to;

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      
      <div className="sr-line">
        上下文窗口是
        <span className="slot">
          <span className="ruler">{longer}</span>
          <span className="word from" style={{
            opacity: fromOpacity, transform: "translateX(-50%)",
          }}>
            {CONFIG.from}
          </span>
          <span className="word to" style={{
            opacity: toP, transform: `translateX(-50%) translateY(${toY}px)`,
          }}>{CONFIG.to}</span>
          <span className="strike" style={{
            opacity: strikeOpacity,
            transform: `translateY(-50%) scaleX(${strikeX})`,
          }} />
        </span>
        ，一年翻了八倍
      </div>
    </AbsoluteFill>
  );
}
