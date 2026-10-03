import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// quote-hold-arrow · 金句停留 —— 自包含 Remotion 源码（与 demos/quote-hold-arrow/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 128 };

const FPS = meta.fps;

// —— 可摘走的核心动画参数：前两行平铺淡入 → 末行先平淡后升级（框铺开 + punch）——
// 2026-08-26 用户定版：去掉了原来第三拍伸出的箭头。金句的落点是"这一句被点亮然后停住"。
const CONFIG = {
  lead: 0.4,          // 起手静置 s
  lineDur: 0.28,      // 单行淡入耗时 s
  lineStagger: 0.12,  // 前两行错峰 s
  lineRise: 8,        // 行上浮位移 px
  plainHold: 0.34,    // 命门：末行"平淡"停留 s，之后才升级。=0 就少了"重点在这一句"的推进
  hlDur: 0.24,        // 高亮框从中心铺开耗时 s
  punchScale: 1.05,   // 框到位后文字 punch 起始倍数（1.05→1）
  punchDur: 0.17,     // punch 5 帧 @30fps
  hold: 2.2,          // 收尾停留 s：金句要停（punch 完就进 hold）
};

/* 时间表（demo 秒）
   0.40+0.12i 行 i 淡入上浮 0.28s（power2.out）；末行 0.64–0.92
   1.26–1.50  高亮框从文字中心 scaleX 铺开（power3.out）
   1.50–1.67  末行文字 punch 1.05→1（power2.out）
   1.67–3.87  hold 定格 */

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

// —— 演示语境（不属于动效）：右侧人物列 + 左侧三行金句 ——
const CSS = `
.host-col { position: absolute; right: 10px; bottom: 0; width: 448px; height: 100%; }
.qh-block {
  position: absolute;
  left: 84px;
  top: 50%;
  transform: translateY(-50%);
  width: 460px;
}
.qh-line {
  font-size: 33px;
  font-weight: 600;
  line-height: 1.52;
  color: #1d1d1f;
  white-space: nowrap;
}
/* 末行：文字保持黑字，高亮框在下层铺开（荧光笔语义，不是反白 chip） */
.qh-last { position: relative; display: inline-block; }
.qh-hl {
  position: absolute;
  left: -12px; right: -14px;
  top: 4px; bottom: 4px;
  background: #FFE949;
  opacity: 0.62;
  mix-blend-mode: multiply;          /* 命门：框不许盖字 */
  border-radius: 11px 5px 9px 4px / 6px 11px 5px 9px;   /* 不规则圆角 = 笔触 */
  transform-origin: 50% center;      /* 从文字中心铺开（不是从左划过） */
  z-index: 0;
}
.qh-last-txt { position: relative; z-index: 1; display: inline-block; }
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


/* slug-specific portrait: quote block uses the middle canvas. */
.qh-block { top: 430px !important; transform: scale(1.25) !important; transform-origin: 0 0 !important; }

`;

export default function QuoteHoldArrow({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  // ① 三行逐行淡入上浮——末行此刻是普通样式（框还没出，第一拍是"平淡"）
  const lineStyle = (i: number): React.CSSProperties => {
    const p = tw(t, CONFIG.lead + i * CONFIG.lineStagger, CONFIG.lineDur, power2Out);
    return { opacity: p, transform: `translateY(${lerp(CONFIG.lineRise, 0, p)}px)` };
  };

  // ② 第二拍：末行升级——高亮框从文字中心 scaleX 铺开，框到位后文字 punch
  const upAt = CONFIG.lead + CONFIG.lineStagger * 2 + CONFIG.lineDur + CONFIG.plainHold;
  const hlX = tw(t, upAt, CONFIG.hlDur, power3Out);
  const punchAt = upAt + CONFIG.hlDur;
  const txtScale = t < punchAt
    ? 1
    : lerp(CONFIG.punchScale, 1, tw(t, punchAt, CONFIG.punchDur, power2Out));

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      

      <div className="qh-block">
        <div className="qh-line" style={lineStyle(0)}>你现在觉得难受</div>
        <div className="qh-line" style={lineStyle(1)}>不是因为你不行</div>
        <div className="qh-line" style={lineStyle(2)}>
          <span className="qh-last">
            <span className="qh-hl" style={{ transform: `scaleX(${hlX})` }} />
            <span className="qh-last-txt" style={{
              transform: `scale(${txtScale})`, transformOrigin: "50% 50%",
            }}>是因为你正在走出舒适区</span>
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
}
