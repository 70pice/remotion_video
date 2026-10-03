import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// evidence-scroll-tour · 证据长页慢滚 —— 自包含 Remotion 源码（与 demos/evidence-scroll-tour/index.html 同画面）
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 320 };

const FPS = meta.fps;

// —— 动效本体（可整段摘走）：一条速度曲线（缓入→匀速→减速停→再启动→滚完）+ 停留防死呼吸 ——
const CONFIG = {
  scrollSpeed: 130,  // 匀速滚速 px/s（≈10% 页高/s）：快了读不到小标题，慢了拖节奏
  stopHold: 1.5,     // 关键条目停留时长 s，对齐"你看这一条"的台词
  stopAlign: 0.5,    // 目标条目停在视口高度的比例位置（0.5 = 垂直中线）
  decelDist: 90,     // 减速提前量 px：太短像急刹（程序 seek 感）
  accelDist: 45,     // 起滚/再启动的加速距离 px：0 会瞬间满速，读作跳变
  breathScale: 1.03, // 停留期红框呼吸幅度：连续缓动防死，不是随机抖
  startDelay: 0.6,   // 起滚前静置一拍，等口播开场
};

// 长页几何（demo 运行时测量，移植按同版式实测定值）：
// 视口高 369，页高 1162 ⇒ maxScroll 793；#stop-box 顶到页顶 629.94、高 30
const GEO = { vh: 369, pageH: 1162, boxTop: 629.94, boxH: 30 };

/* 时间表（demo 秒）——由 CONFIG + GEO 推出（stopY = 460.44，maxScroll = 793）：
   0.600–1.292  缓入起滚 y 0→−45（power2.in）
   1.292–3.796  匀速巡览 y→−370.44（linear）
   3.796–5.180  提前减速 y→−460.44，红框停在视口中线（power2.out）
   5.180–6.680  停留：红框一次完整呼吸 scale 1→1.03→1（sine.inOut yoyo）
   6.680–7.373  再启动 y→−505.44（power2.in）
   7.373–8.892  匀速 y→−703（linear）
   8.892–10.277 收尾减速 y→−793（power2.out） */

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const linear = (x: number) => x;
const power2In = (x: number) => x * x * x;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const sineInOut = (x: number) => -(Math.cos(Math.PI * x) - 1) / 2;

const CSS = `
/* 与 demo 外壳一致的全局 reset（demo-shell.css）：不带它 UA 缺省 margin/content-box 会让版式整体走样 */
* { margin: 0; padding: 0; box-sizing: border-box; }
.doc-window {
  position: absolute;
  left: 50%;
  top: 62px;
  transform: translateX(-50%);
  width: 620px;
  height: 404px;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  background: #ffffff;
  overflow: hidden;
}
.doc-titlebar {
  height: 34px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 12px;
  border-bottom: 1px solid #ececec;
  font-size: 12px;
  color: #8a8a8a;
}
.doc-titlebar i { width: 9px; height: 9px; border-radius: 50%; background: #d2d2d7; }
.doc-titlebar .fname { margin-left: 8px; letter-spacing: 1px; }
.doc-viewport {
  position: relative;
  height: 369px;            /* 404 - 34 - 1px 边线 */
  overflow: hidden;
}
/* 长页：页面 y 位移是全卡唯一持续运动的属性 */
.doc-page {
  position: absolute;
  left: 0; right: 0; top: 0;
  padding: 26px 36px 34px;
  will-change: transform;
  color: #1d1d1f;
}
.doc-page h1 { font-size: 21px; font-weight: 700; text-align: center; margin-bottom: 8px; }
.doc-page .meta { font-size: 12px; color: #8a8a8a; text-align: center; margin-bottom: 14px; }
.doc-page .rule { height: 1px; background: #ececec; margin: 0 0 16px; }
.doc-page h2 { font-size: 14.5px; font-weight: 700; margin: 18px 0 10px; }
.doc-page .bar { height: 9px; border-radius: 3px; background: #e3e3e6; margin: 12px 0; }
.doc-page .bar.lt { background: #ececef; }
.doc-page .w92 { width: 92%; } .doc-page .w85 { width: 85%; }
.doc-page .w78 { width: 78%; } .doc-page .w66 { width: 66%; }
.doc-page .w52 { width: 52%; } .doc-page .w40 { width: 40%; }
.doc-page .clause { font-size: 13.5px; line-height: 1.7; margin: 12px 0; }
.doc-page .sign { display: flex; gap: 60px; margin-top: 26px; }
.doc-page .sign > div { flex: 1; }

/* —— 动效本体相关：预置红框标注（semantic 红），随页滚动、不现场画 —— */
.mark-wrap { position: relative; display: inline-block; font-weight: 700; }
.mark-box {
  position: absolute;
  left: -9px; right: -9px; top: -4px; bottom: -3px;
  border: 2.5px solid #e53935;
  border-radius: 7px 4px 8px 5px / 5px 8px 4px 7px;   /* 不规则圆角：手标感，不是文本选区 */
  pointer-events: none;
}

/* —— 演示语境：角标主持人 —— */
`;
const PORTRAIT_CSS = `

/* Native portrait adaptation: keep source timing/CONFIG, reflow stage to 1080x1920. */
.data-panel, .gm-zone, .right, .panel, .stage, .desk, .screen, .theater, .flow, .phone, .doc, .wall, .strip, .wrap {
  max-width: none;
}
.data-panel {
  left: 72px !important; right: 72px !important; top: 420px !important; bottom: 160px !important;
  border-left: 0 !important; padding: 0 !important; justify-content: flex-start !important; gap: 76px !important;
}
.metric-block, .slab-block, .grid-wrap, .chip-wrap, .term-wrap, .map-wrap, .steps-wrap, .timeline-wrap, .prop-wrap {
  left: 76px !important; right: 76px !important; top: 520px !important; width: auto !important; transform: none !important;
}
.scv-svg, svg { max-width: 100%; }
.gm-zone { left: 0 !important; top: 460px !important; bottom: 160px !important; right: 0 !important; }
.gm-pic { transform-origin: 50% 50%; }
.big-row .num, .big-num .value { font-size: 132px !important; line-height: .95 !important; }
.big-row .unit { font-size: 58px !important; }
.big-num .delta { display: block; margin-top: 22px; font-size: 46px !important; }
.odometer .digit { width: 102px !important; height: 126px !important; border-radius: 18px !important; }
.odometer .reel span { height: 126px !important; line-height: 126px !important; font-size: 82px !important; }
.odometer .comma { font-size: 76px !important; line-height: 118px !important; }
.odometer .unit { font-size: 36px !important; }
.metric .label, .metric-block .label { font-size: 34px !important; }
.spark, .spark .xlabels { width: 820px !important; }
.spark svg { width: 820px !important; height: 220px !important; }

/* native-portrait manual layout: evidence-scroll-tour */
.doc-window { left: 62px !important; right: 62px !important; top: 210px !important; width: auto !important; height: 1460px !important; transform: none !important; border-radius: 24px !important; box-shadow: 0 28px 90px rgba(0,0,0,.10) !important; }
.doc-titlebar { height: 72px !important; gap: 12px !important; padding: 0 26px !important; font-size: 22px !important; }
.doc-titlebar i { width: 16px !important; height: 16px !important; }
.doc-titlebar .fname { overflow: hidden !important; text-overflow: ellipsis !important; white-space: nowrap !important; }
.doc-viewport { height: 1387px !important; }
.doc-page { padding: 52px 62px 70px !important; }
.doc-page h1 { font-size: 43px !important; margin-bottom: 18px !important; }
.doc-page .meta { font-size: 22px !important; margin-bottom: 32px !important; }
.doc-page h2 { font-size: 30px !important; margin: 34px 0 22px !important; }
.doc-page .bar { height: 18px !important; border-radius: 9px !important; margin: 24px 0 !important; }
.doc-page .clause { font-size: 28px !important; line-height: 1.78 !important; margin: 26px 0 !important; }
.mark-box { left: -16px !important; right: -16px !important; top: -8px !important; bottom: -6px !important; border-width: 4px !important; border-radius: 12px !important; }
`;

export default function EvidenceScrollTour() {
  const t = useCurrentFrame() / FPS;
  const C = CONFIG;

  // 停点：让红框中心停在视口 stopAlign 位置
  const maxScroll = Math.max(0, GEO.pageH - GEO.vh);
  let stopY = GEO.boxTop + GEO.boxH / 2 - GEO.vh * C.stopAlign;
  stopY = Math.max(0, Math.min(stopY, maxScroll));

  // 分段时长：加/减速段按 2*距离/速度（保证与匀速段速度连续，无阶跃）
  const v = C.scrollSpeed;
  const tAccel = (2 * C.accelDist) / v;
  const tDecel = (2 * C.decelDist) / v;
  const u1 = Math.max(0, stopY - C.decelDist - C.accelDist);
  const u2 = Math.max(0, maxScroll - C.decelDist - stopY - C.accelDist);

  // 绝对时刻表
  const a0 = C.startDelay;               // 缓入起滚
  const a1 = a0 + tAccel;                // 匀速巡览
  const a2 = a1 + u1 / v;                // 提前减速
  const a3 = a2 + tDecel;                // 停留（呼吸）
  const a4 = a3 + C.stopHold;            // 再启动
  const a5 = a4 + tAccel;                // 匀速
  const a6 = a5 + u2 / v;                // 收尾减速

  let y: number;
  if (t < a1) y = lerp(0, -C.accelDist, tw(t, a0, tAccel, power2In));
  else if (t < a2) y = lerp(-C.accelDist, -(stopY - C.decelDist), tw(t, a1, u1 / v, linear));
  else if (t < a4) y = lerp(-(stopY - C.decelDist), -stopY, tw(t, a2, tDecel, power2Out));
  else if (t < a5) y = lerp(-stopY, -(stopY + C.accelDist), tw(t, a4, tAccel, power2In));
  else if (t < a6) y = lerp(-(stopY + C.accelDist), -(maxScroll - C.decelDist), tw(t, a5, u2 / v, linear));
  else y = lerp(-(maxScroll - C.decelDist), -maxScroll, tw(t, a6, tDecel, power2Out));

  // 停留期红框一次完整呼吸（sine.inOut yoyo repeat 1）
  let boxScale = 1;
  if (t > a3 && t < a4) {
    const half = C.stopHold / 2;
    const cyc = (t - a3) / half;
    const p = cyc < 1 ? cyc : 2 - cyc;
    boxScale = lerp(1, C.breathScale, sineInOut(clamp01(p)));
  }

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="doc-window">
        <div className="doc-titlebar"><i /><i /><i /><span className="fname">个人借款服务协议（2024 修订版）.pdf</span></div>
        <div className="doc-viewport">
          <div className="doc-page" style={{ transform: `translateY(${y}px)` }}>
            <h1>个人借款服务协议</h1>
            <div className="meta">合同编号：2024-XJD-1107 · 甲方：某消费金融有限公司</div>
            <div className="rule" />

            <h2>第一条 借款金额与期限</h2>
            <div className="bar w92" /><div className="bar w85" /><div className="bar lt w78" />
            <div className="bar w92" /><div className="bar lt w66" /><div className="bar w85" />
            <div className="bar lt w52" /><div className="bar w78" />

            <h2>第二条 利息与综合费用</h2>
            <div className="bar w92" /><div className="bar lt w85" />
            <div className="clause"><span className="mark-wrap"><span className="mark-box" />综合年化费率以签约页面实际展示为准</span>，并可能包含服务费。</div>
            <div className="bar w85" /><div className="bar lt w78" /><div className="bar w66" /><div className="bar lt w40" />

            <h2>第三条 逾期与违约责任</h2>
            <div className="bar w92" /><div className="bar lt w85" /><div className="bar w78" /><div className="bar lt w66" />
            <div className="clause"><span className="mark-wrap"><span className="mark-box" style={{ transform: `scale(${boxScale})`, transformOrigin: "50% 50%" }} />逾期费率按日 1%，且不设累计上限</span>，自逾期之日起计收。</div>
            <div className="bar w85" /><div className="bar lt w52" /><div className="bar w66" />

            <h2>第四条 个人信息授权</h2>
            <div className="bar w92" /><div className="bar lt w85" /><div className="bar w78" />
            <div className="bar lt w92" /><div className="bar w66" /><div className="bar lt w52" /><div className="bar w85" />

            <h2>第五条 争议解决</h2>
            <div className="bar w92" /><div className="bar lt w78" /><div className="bar w85" />
            <div className="bar lt w66" /><div className="bar w40" />

            <div className="sign">
              <div><div className="bar w66" /><div className="bar lt w40" /></div>
              <div><div className="bar w66" /><div className="bar lt w40" /></div>
            </div>
          </div>
        </div>
      </div>

    </AbsoluteFill>
  );
}

