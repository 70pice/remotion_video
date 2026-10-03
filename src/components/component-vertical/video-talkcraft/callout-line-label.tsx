import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// callout-line-label · 标注引出线 —— 自包含 Remotion 源码（与 demos/callout-line-label/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 148 };

const FPS = meta.fps;

// —— 可摘走的核心动画参数 ——
const CONFIG = {
  dotR: 7,             // 圆点半径 px
  dotIn: 0.2,          // 圆点 pop 时长 s（back.out）
  lineDraw: 0.4,       // 折线描画时长 s
  labelIn: 0.25,       // 标签遮罩展开时长 s；文字再滞后 0.1s
  hold: 1.6,           // 全部标注就位后的停留 s
  out: 0.5,            // 反向收回总时长 s
  stagger: 0.8,        // 第二个标注的延迟 s（多标注必须错峰）
  color: "#d8383a",    // 点/涟漪/线同色的标注色（唯一语义色；白底上保对比，深底可换高亮黄）
  // 每个 callout：target = 圆点位置；elbow/end = 折线拐点与终点（45° 或水平）；标签贴 end
  callouts: [
    {
      target: { x: 690, y: 455 },
      points: [{ x: 585, y: 365 }, { x: 250, y: 365 }],
      label: { lines: ["1 英寸大底主摄", "同价位唯一"], x: 82, y: 300, from: "right" },
    },
    {
      target: { x: 934, y: 690 },
      points: [{ x: 820, y: 815 }, { x: 650, y: 815 }],
      label: { lines: ["钛合金中框", "整机减重 19g"], x: 322, y: 750, from: "left" },
    },
  ],
};

/* 时间表（demo 秒，i = 标注序号 0/1，t0 = 0.6 + i*0.8）
   t0        圆点 pop（0.2s back.out(2.2)）
   t0+0.05   涟漪扩散（0.5s power2.out，scale 0.4→3.2 / opacity 0.9→0）
   t0+0.2    折线描画（0.4s power2.out）
   t0+0.6    标签 clip 展开（0.25s power3.out）；文字 +0.1s 淡入（0.2s）
   outAt = 3.95；tOut = outAt + i*0.15
   tOut       标签反向收回（0.2s power2.in）
   tOut+0.12  折线回吸（0.2s power2.in）
   tOut+0.28  圆点熄灭（0.15s power2.in）→ 最晚 4.53s 结束 */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const power2In = (x: number) => x * x * x;
const backOut = (s = 1.70158) => (x: number) => {
  const u = x - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};

// 折线总长（代替 getTotalLength）
const polyLen = (pts: { x: number; y: number }[]) => {
  let len = 0;
  for (let i = 1; i < pts.length; i++) len += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
  return len;
};

// —— 演示语境（不属于动效）：被标注的产品图占位，白底 + 灰阶线框 ——
const CSS = `
.phone {
  position: absolute;
  left: 380px; top: 70px;
  width: 200px; height: 400px;
  border-radius: 30px;
  background: #ffffff;
  border: 2px solid #d8d8dc;
}
.phone .screen {
  position: absolute; inset: 10px;
  border-radius: 22px;
  background: #f5f5f7;
  border: 1px solid #ececef;
}
.phone .cam {
  position: absolute; left: 20px; top: 22px;
  width: 44px; height: 44px; border-radius: 12px;
  background: #ffffff; border: 1px solid #d8d8dc;
}
.phone .cam::after {
  content: ""; position: absolute; left: 10px; top: 10px;
  width: 18px; height: 18px; border-radius: 50%;
  background: #ececef; border: 1px solid #c8c8cc;
}
.phone .btn-side {
  position: absolute; right: -6px; top: 120px;
  width: 4px; height: 56px; border-radius: 3px; background: #d8d8dc;
}
#calloutLayer { position: absolute; inset: 0; pointer-events: none; }
/* —— 动效本体 —— 文字标签：clip-path 从线端方向展开 */
.callout-label {
  position: absolute;
  padding: 10px 16px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  color: #1d1d1f;
  border-radius: 8px;
  font-size: 17px;
  line-height: 1.45;
  white-space: nowrap;
}
.callout-label b { display: block; font-size: 19px; }
.callout-label small { color: #8a8a8a; font-size: 14px; }
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


/* slug-specific portrait: phone, dots, line paths and labels share one native 1080x1920 coordinate system. */
.phone { left: 610px !important; top: 360px !important; width: 340px !important; height: 720px !important; transform: none !important; }
.phone .cam { left: 38px !important; top: 42px !important; width: 72px !important; height: 72px !important; border-radius: 18px !important; }
.phone .cam::after { left: 18px !important; top: 18px !important; width: 30px !important; height: 30px !important; }
.phone .btn-side { right: -8px !important; top: 260px !important; height: 120px !important; width: 6px !important; }
#calloutLayer { width: 1080px !important; height: 1920px !important; }
.callout-label { font-size: 34px !important; padding: 22px 28px !important; border-radius: 18px !important; }
.callout-label b { font-size: 40px !important; }
.callout-label small { font-size: 28px !important; }

`;

export default function CalloutLineLabel() {
  const t = useCurrentFrame() / FPS;

  const outAt = 0.6 + CONFIG.stagger + CONFIG.dotIn + CONFIG.lineDraw + CONFIG.labelIn + 0.1 + CONFIG.hold;

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="phone">
        <div className="screen" />
        <div className="cam" />
        <div className="btn-side" />
      </div>
      <svg id="calloutLayer" viewBox="0 0 1080 1920">
        {CONFIG.callouts.map((c, i) => {
          const t0 = 0.6 + i * CONFIG.stagger;
          const tOut = outAt + i * 0.15;

          // 1) 圆点 pop（back.out 会过冲，scale 保留过冲、opacity 封顶 1）+ 涟漪
          const dotP = t < tOut + CONFIG.out * 0.56
            ? tw(t, t0, CONFIG.dotIn, backOut(2.2))
            : 1 - tw(t, tOut + CONFIG.out * 0.56, CONFIG.out * 0.3, power2In);
          const rippleOn = t >= t0 + 0.05;   // immediateRender: false —— 起步前不画
          const rippleP = tw(t, t0 + 0.05, 0.5, power2Out);

          // 2) 折线生长 → 退场回吸（dashoffset 描画）
          const pts = [c.target, ...c.points];
          const len = polyLen(pts);
          const d = `M ${pts.map((p) => `${p.x} ${p.y}`).join(" L ")}`;
          const tLine = t0 + CONFIG.dotIn;   // 圆点亮完线才走：三拍有先后
          const dash = t < tOut + CONFIG.out * 0.24
            ? len * (1 - tw(t, tLine, CONFIG.lineDraw, power2Out))
            : len * tw(t, tOut + CONFIG.out * 0.24, CONFIG.out * 0.4, power2In);

          return (
            <g key={i}>
              {rippleOn && (
                <circle cx={c.target.x} cy={c.target.y} r={CONFIG.dotR}
                  fill="none" stroke={CONFIG.color} strokeWidth={2}
                  opacity={lerp(0.9, 0, rippleP)}
                  transform={`translate(${c.target.x} ${c.target.y}) scale(${lerp(0.4, 3.2, rippleP)}) translate(${-c.target.x} ${-c.target.y})`} />
              )}
              <circle cx={c.target.x} cy={c.target.y} r={CONFIG.dotR}
                fill={CONFIG.color} opacity={clamp01(dotP)}
                transform={`translate(${c.target.x} ${c.target.y}) scale(${dotP}) translate(${-c.target.x} ${-c.target.y})`} />
              <path d={d} fill="none" stroke={CONFIG.color} strokeWidth={2.5}
                strokeDasharray={len} strokeDashoffset={dash} />
            </g>
          );
        })}
      </svg>
      <div>
        {CONFIG.callouts.map((c, i) => {
          const t0 = 0.6 + i * CONFIG.stagger;
          const tOut = outAt + i * 0.15;
          const tLabel = t0 + CONFIG.dotIn + CONFIG.lineDraw;

          // 3) 标签：clip-path 从线端方向展开，文字滞后 0.1s 淡入
          const shown = t < tOut
            ? tw(t, tLabel, CONFIG.labelIn, power3Out)
            : 1 - tw(t, tOut, CONFIG.out * 0.4, power2In);
          // from: "right" = 从右缘向左展开（左 inset 收缩）；"left" 反之
          const clip = c.label.from === "right"
            ? `inset(0 0 0 ${(1 - shown) * 100}%)`
            : `inset(0 ${(1 - shown) * 100}% 0 0)`;
          const txtOp = tw(t, tLabel + 0.1, 0.2, power1Out);

          return (
            <div key={i} className="callout-label"
              style={{ left: c.label.x, top: c.label.y, clipPath: clip }}>
              <b style={{ opacity: txtOp }}>{c.label.lines[0]}</b>
              <small style={{ opacity: txtOp }}>{c.label.lines[1]}</small>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}
