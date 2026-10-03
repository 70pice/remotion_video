import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// bar-chart-growth · 柱状增长 —— 自包含 Remotion 源码（与 demos/bar-chart-growth/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 110 };

const FPS = meta.fps;

// ===== 可摘走的核心动画参数 =====
// 语义：七根柱是"一串"不是七个动效 —— 错峰要密（0.06s），整组读作一次连续升起；
//       结论 chip 只在最后一根到顶那一帧弹出（数据讲完才允许下结论）。
const CONFIG = {
  lead: 0.3,          // 起手静置 s
  titleIn: 0.2,       // 标题淡入 s
  baseAt: 0.42,       // 基线开画时刻 s
  baseDur: 0.24,      // 基线 scaleX 0→1 s：先立地面再长柱
  barsAt: 0.62,       // 第一根柱起点 s
  barStagger: 0.06,   // 柱间错峰 s：本卡命门，>0.1 就散成"七个动效"
  barGrow: 0.28,      // 单柱 scaleY 0→1 s
  maxVal: 100,        // 量程：全程固定，中途缩放对比就是骗人
  chipGap: 18,        // chip 底边距最高柱顶的留白 px：不许压柱顶
  chipPop: 0.2,       // chip 弹出 s
  chipScale: 0.8,     // chip 起始缩放
  hold: 1.8,          // 收尾定格 s
};

// 柱数据（data-v，量程 100）与月份标签
const BARS = [16, 23, 30, 41, 52, 66, 84];
const MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月"];
const CHART_H = 760; // .chart 高度 px = CONFIG 的量程高度

/* 时间表（demo 秒）
   0.30–0.50  标题淡入（power2.out）
   0.42–0.66  基线从左画出 scaleX 0→1（power2.out）
   0.62+0.06i 第 i 根柱 scaleY 0→1，0.28s（power3.out）
   1.26–1.46  最后一根到顶：chip 弹出 opacity/scale 0.8→1（back.out(1.4)）
   1.46–3.26  收尾 hold 1.8s */

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

// —— 演示语境（不属于动效）：主持人占位在右，左侧一组柱；白底零装饰、无网格无坐标轴 ——
const CSS = `
.host-wrap { position: absolute; right: 0; top: 0; bottom: 0; width: 47%; overflow: hidden; }
.panel { position: absolute; left: 96px; top: 0; bottom: 0; width: 420px; }
.panel .title {
  position: absolute; left: 0; top: 96px;
  font-size: 34px; font-weight: 600; color: #1d1d1f; letter-spacing: 1px;
}
/* —— 动效本体 —— 柱组 + 基线 + 结论 chip —— */
.chart { position: absolute; left: 0; bottom: 96px; width: 420px; height: ${CHART_H}px; }
.baseline {
  position: absolute; left: 0; right: 0; bottom: -1px; height: 2px;
  background: #d2d2d7; transform-origin: 0% 50%;
}
.bars {
  position: absolute; inset: 0;
  display: flex; align-items: flex-end; justify-content: space-between;
}
.bar {
  width: 44px;
  background: #e8720c;                 /* 唯一语义强调色（橙），只上在柱体上 */
  border-radius: 4px 4px 0 0;
  transform-origin: 50% 100%;          /* 命门：只用 scaleY，改 height 每帧重排 */
}
.xlabels {
  position: absolute; left: 0; right: 0; bottom: -30px;
  display: flex; justify-content: space-between;
  font-size: 13px; color: #8a8a8a;
}
.xlabels span { width: 44px; text-align: center; }
/* 结论 chip：坐在最高柱顶上方的留白里（bottom 按柱高算，绝不压柱顶） */
.grow-chip {
  position: absolute; right: 0;
  padding: 8px 16px; border-radius: 12px;
  background: #e8720c; color: #ffffff;
  font-size: 22px; font-weight: 600; line-height: 1; letter-spacing: 1px;
  white-space: nowrap; font-variant-numeric: tabular-nums;
  transform-origin: 100% 50%;
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

`;

export default function BarChartGrowth({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  // ① 标题淡入
  const titleP = tw(t, CONFIG.lead, CONFIG.titleIn, power2Out);
  // ② 基线从左画出（先有地面，柱子才有"从地里长出来"的语义）
  const baseP = tw(t, CONFIG.baseAt, CONFIG.baseDur, power2Out);
  // ④ 最后一根到顶那一帧：结论 chip 弹出
  const lastTop = CONFIG.barsAt + (BARS.length - 1) * CONFIG.barStagger + CONFIG.barGrow;
  const chipP = tw(t, lastTop, CONFIG.chipPop, backOut(1.4));

  // chip 落位由最高柱算出——换数据自动跟着抬高，永远压不到柱顶
  const maxH = (Math.max(...BARS) / CONFIG.maxVal) * CHART_H;

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="panel">
        <div className="title" style={{ opacity: titleP }}>数据说话</div>
        <div className="chart">
          <div className="grow-chip" style={{
            bottom: maxH + CONFIG.chipGap,
            opacity: Math.min(1, chipP),
            transform: `scale(${lerp(CONFIG.chipScale, 1, chipP)})`,
          }}>增长 42%</div>
          <div className="bars">
            {BARS.map((v, i) => {
              // ③ 七根柱逐根升起，错峰密到读作一次连续动作
              const p = tw(t, CONFIG.barsAt + i * CONFIG.barStagger, CONFIG.barGrow, power3Out);
              return (
                <div key={i} className="bar" style={{
                  height: (v / CONFIG.maxVal) * CHART_H,
                  transform: `scaleY(${p})`,
                }} />
              );
            })}
          </div>
          <div className="baseline" style={{ transform: `scaleX(${baseP})` }} />
          <div className="xlabels">
            {MONTHS.map((m) => <span key={m}>{m}</span>)}
          </div>
        </div>
      </div>
      
    </AbsoluteFill>
  );
}
