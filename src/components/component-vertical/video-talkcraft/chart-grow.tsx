import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// chart-grow · 图表生长 —— 自包含 Remotion 源码（与 demos/chart-grow/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用（本卡为全图表卡，无主持人）。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 68 };

const FPS = meta.fps;

// —— 可摘走的核心动画参数（照抄 demo 的 CONFIG）——
const CONFIG = {
  axisIn: 0.3,      // 轴+网格淡入耗时 s：先立坐标系再长柱子
  barGrow: 0.5,     // 单柱 scaleY 0→1 耗时 s（origin bottom）
  barStagger: 0.13, // 柱间错峰 100~150ms："逐项列举"的语感
  maxVal: 100,      // y 轴满量程：全程固定，中途缩放会让对比失真
  labelPopAt: 0.72, // 柱顶数字在柱子长到多少进度时 pop（0~1）
  punchScale: 1.03, // 最高柱到顶时整图轻 punch 幅度
};

// 柱数据：最后一根是高亮柱（hot）
const COLS = [
  { v: 12, year: "2020", hot: false },
  { v: 18, year: "2021", hot: false },
  { v: 27, year: "2022", hot: false },
  { v: 45, year: "2023", hot: false },
  { v: 86, year: "2024", hot: true },
];

/* 时间表（demo 秒）
   0.20–0.50  标题 + 轴 + 网格淡入（power2.out）
   0.55+0.13i 第 i 根柱 scaleY 0→1，0.5s（power3.out）
   +0.36      柱顶数字弹出 opacity/scale 0.4→1，0.25s（back.out(2)）
   1.57–1.65  整图 punch scale 1→1.03（power2.out）
   1.65–1.87  回弹到 1（back.out(3)） */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const backOut = (s = 1.70158) => (x: number) => {
  const u = x - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};

// —— 演示语境（不属于动效）：图表底，白底 + 灰阶坐标系 ——
const CSS = `
.chart-wrap { position: absolute; left: 120px; right: 120px; top: 108px; bottom: 92px; }
.chart-title {
  position: absolute; top: 62px; left: 120px;
  font-size: 22px; font-weight: 700; color: #1d1d1f; letter-spacing: 2px;
}
.axis-x, .axis-y { position: absolute; background: #c8c8cc; }
.axis-x { left: 0; right: 0; bottom: 0; height: 2px; }
.axis-y { left: 0; top: 0; bottom: 0; width: 2px; }
.gridline { position: absolute; left: 2px; right: 0; height: 1px; background: #ececef; }
.bars {
  position: absolute; left: 30px; right: 10px; top: 0; bottom: 2px;
  display: flex; align-items: flex-end; justify-content: space-around;
}
.bar-col {
  width: 76px; display: flex; flex-direction: column; align-items: center;
  position: relative; height: 100%; justify-content: flex-end;
}
/* —— 动效本体 —— 普通柱走灰阶，关键柱用语义高亮色（层级色是本卡语义的一部分） */
.bar {
  width: 100%; background: #d2d2d7; border-radius: 5px 5px 0 0;
  transform-origin: 50% 100%;   /* 从地面长出来 */
}
.bar-col.hot .bar { background: #d8383a; }
.bar-val { position: absolute; font-size: 20px; font-weight: 800; color: #1d1d1f; }
.bar-col.hot .bar-val { color: #d8383a; font-size: 24px; }
.bar-year { position: absolute; bottom: -30px; font-size: 15px; color: #8a8a8a; }
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

/* slug-specific portrait: keep the chart title inside the 1080x1920 canvas. */
.chart-title { left: 70px !important; right: 70px !important; top: 118px !important; font-size: 68px !important; line-height: 1.05 !important; letter-spacing: 0 !important; }
.chart-wrap { left: 70px !important; top: 360px !important; width: 940px !important; height: 1060px !important; }

`;

export default function ChartGrow() {
  const t = useCurrentFrame() / FPS;

  // ① 先立坐标系（标题 + 轴 + 网格一起淡入）
  const axisP = tw(t, 0.2, CONFIG.axisIn, power2Out);

  // ③ 最高的那根（高亮柱）到顶：整图轻 punch 一拍
  const lastTop = 0.55 + (COLS.length - 1) * CONFIG.barStagger + CONFIG.barGrow;
  const punch = t < lastTop + 0.08
    ? lerp(1, CONFIG.punchScale, tw(t, lastTop, 0.08, power2Out))
    : lerp(CONFIG.punchScale, 1, tw(t, lastTop + 0.08, 0.22, backOut(3)));

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="chart-title" style={{ opacity: axisP }}>年营收（亿元）</div>
      <div className="chart-wrap" style={{ transform: `scale(${punch})` }}>
        <div className="gridline" style={{ bottom: "25%", opacity: axisP }} />
        <div className="gridline" style={{ bottom: "50%", opacity: axisP }} />
        <div className="gridline" style={{ bottom: "75%", opacity: axisP }} />
        <div className="axis-y" style={{ opacity: axisP }} />
        <div className="axis-x" style={{ opacity: axisP }} />
        <div className="bars">
          {COLS.map((col, i) => {
            const h = (col.v / CONFIG.maxVal) * 100;   // 柱高（% of 量程）
            // ② 柱子逐根长出，柱顶数字在该柱快到顶时弹出
            const at = 0.55 + i * CONFIG.barStagger;
            const barP = tw(t, at, CONFIG.barGrow, power3Out);
            const valP = tw(t, at + CONFIG.barGrow * CONFIG.labelPopAt, 0.25, backOut(2));
            return (
              <div key={i} className={"bar-col" + (col.hot ? " hot" : "")}>
                <div className="bar" style={{ height: `${h}%`, transform: `scaleY(${barP})` }} />
                <div className="bar-val" style={{
                  bottom: `calc(${h}% + 10px)`,
                  opacity: Math.min(1, valP),
                  transform: `scale(${lerp(0.4, 1, valP)})`,
                }}>{col.v}</div>
                <div className="bar-year">{col.year}</div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
}
