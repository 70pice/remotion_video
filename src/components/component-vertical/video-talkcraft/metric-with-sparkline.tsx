import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// metric-with-sparkline · 数字带趋势 —— 自包含 Remotion 源码（与 demos/metric-with-sparkline/index.html 同画面）
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 114 };

const FPS = meta.fps;

// ===== 可摘走的核心动画参数 =====
// 语义：一个数字的"结论"要等它算完才成立 —— 滚动期间不许出现单位和箭头；
//       折线与计数同一刻起跑（数字和曲线讲的是同一件事，不是两件事）。
const CONFIG = {
  target: 67,          // 计数终值
  lead: 0.3,           // 起手静置 s：等口播念到"效率"
  labelIn: 0.16,       // 小标签淡入 s
  countAt: 0.5,        // 计数起点 s（= 折线起点，两者必须同值）
  countDur: 0.9,       // 计数时长 s：<0.5 读作硬切，>1.4 观众等结论
  lineDur: 0.6,        // 折线画出时长 s：必须 < countDur，曲线先到位、数字后落定
  unitIn: 0.2,         // 单位淡入 s（计数结束那一刻）
  arrowRise: 12,       // 箭头从下弹入的位移 px
  arrowScale: 0.8,     // 箭头起始缩放
  arrowIn: 0.2,        // 箭头弹入 s
  dotPop: 0.18,        // 数据点弹出 s
  hold: 1.8,           // 收尾定格 s
  // 折线点位（SVG 局部坐标，viewBox 0 0 400 96；改这里就换数据）
  pts: [[24, 74], [141, 60], [258, 44], [376, 16]] as [number, number][],
  color: "#2fb344",
};

/* 时间表（demo 秒）
   0.30–0.46  小标签淡入（power2.out）
   0.50–1.40  大数字计数 0→67（power2.out）
   0.50–1.10  折线 dashoffset 画出（power1.inOut）；数据点按线长比例反推时刻弹出
   1.40–1.60  单位淡入 + 上箭头从下弹入（power3.out）
   1.60–3.40  收尾 hold 1.8s */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const power1InOut = (x: number) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);
const backOut = (s = 1.70158) => (x: number) => {
  const u = x - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};
// power1.inOut 的反函数：把"线画到第 i 个点"的长度比例换算成时间比例，
// 数据点才真的是"随线的推进"弹出，而不是按均分时间假装同步。
const invPower1InOut = (y: number) =>
  y < 0.5 ? Math.sqrt(y / 2) : 1 - Math.sqrt((1 - y) / 2);

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

// —— 演示语境（不属于动效）：主持人占位在右，左侧指标区；白底零装饰 ——
const CSS = `
.host-wrap { position: absolute; right: 0; top: 0; bottom: 0; width: 47%; overflow: hidden; }
.metric-block { position: absolute; left: 96px; top: 138px; width: 400px; }
.metric-block .label { font-size: 16px; font-weight: 400; color: #8a8a8a; letter-spacing: 3px; }
/* —— 动效本体 —— 大数字 + 单位 + 涨跌箭头同一条基线 —— */
.big-row {
  display: flex; align-items: baseline; gap: 8px; margin-top: 10px;
  white-space: nowrap;                 /* 数字/单位/箭头必须同行，换行会把箭头挤下去 */
  font-variant-numeric: tabular-nums;  /* 命门：滚动计数不跳宽 */
}
.big-row .num {
  font-size: 86px; font-weight: 600; line-height: 1; letter-spacing: -0.02em;
  color: #2fb344;                      /* 唯一语义色：positive（只进数字/图表/涨跌标注） */
}
.big-row .unit { font-size: 34px; font-weight: 600; line-height: 1; color: #2fb344; }
.big-row .arrow { width: 20px; height: 34px; margin-left: 4px; transform-origin: 50% 100%; }
.big-row .arrow svg { display: block; width: 100%; height: 100%; }
/* 小折线图：与计数同时开始画 */
.spark { margin-top: 30px; width: 400px; }
.spark svg { display: block; width: 400px; height: 96px; overflow: visible; }
.spark .base { stroke: #e0e0e0; stroke-width: 1; }
.spark .xlabels {
  display: flex; justify-content: space-between; width: 400px; margin-top: 8px;
  font-size: 13px; color: #8a8a8a;
}
`;
const PORTRAIT_CSS = `

/* Native portrait adaptation: keep source timing/CONFIG, reflow stage to 1080x1920. */
.host-wrap { display: none !important; }
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

.metric-block{left:80px!important;right:80px!important;top:430px!important;width:auto!important}.metric-block .label{font-size:42px!important;letter-spacing:5px!important}.big-row{gap:18px!important;margin-top:34px!important}.big-row .num{font-size:240px!important;font-weight:800!important}.big-row .unit{font-size:88px!important}.big-row .arrow{width:54px!important;height:92px!important}.spark{margin-top:160px!important;width:860px!important}.spark svg{width:860px!important;height:300px!important}.spark path{stroke-width:8!important}.spark circle{r:10}.spark .xlabels{width:860px!important;margin-top:34px!important;font-size:34px!important}
`;

const EXTRA_PORTRAIT_CSS = `.metric-block{left:80px!important;right:80px!important;top:430px!important;width:auto!important}.metric-block .label{font-size:42px!important;letter-spacing:5px!important}.big-row{gap:18px!important;margin-top:34px!important}.big-row .num{font-size:240px!important;font-weight:800!important}.big-row .unit{font-size:88px!important}.big-row .arrow{width:54px!important;height:92px!important}.spark{margin-top:160px!important;width:860px!important}.spark svg{width:860px!important;height:300px!important}.spark path{stroke-width:8!important}.spark .xlabels{width:860px!important;margin-top:34px!important;font-size:34px!important}`;

export default function MetricWithSparkline({ hostSrc }: { hostSrc?: string }) {
  const t = useCurrentFrame() / FPS;

  // ① 小标签先淡入
  const labelP = tw(t, CONFIG.lead, CONFIG.labelIn, power2Out);
  // ② 大数字滚动计数（tabular-nums 防跳宽）
  const num = Math.round(lerp(0, CONFIG.target, tw(t, CONFIG.countAt, CONFIG.countDur, power2Out)));
  // ③ 计数结束那一刻：单位淡入 + 上箭头从下弹入（结论成立的一拍）
  const landAt = CONFIG.countAt + CONFIG.countDur;
  const unitP = tw(t, landAt, CONFIG.unitIn, power2Out);
  const arrowP = tw(t, landAt, CONFIG.arrowIn, power3Out);

  // ④ 折线 dashoffset 画出 —— 与计数同刻起跑
  const d = CONFIG.pts.map((p, i) => (i ? "L" : "M") + p[0] + "," + p[1]).join(" ");
  // 折线总长（直段折线可精确算），dashL 取整数：避免亚像素漏笔
  let L = 0;
  const cum = CONFIG.pts.map((p, i) => {
    if (i) {
      const q = CONFIG.pts[i - 1];
      L += Math.hypot(p[0] - q[0], p[1] - q[1]);
    }
    return L;
  });
  const dashL = Math.ceil(L) + 2;
  const lineP = tw(t, CONFIG.countAt, CONFIG.lineDur, power1InOut);

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS + EXTRA_PORTRAIT_CSS}</style>
      <div className="metric-block">
        <div className="label" style={{ opacity: labelP }}>本周剪辑效率</div>
        <div className="big-row">
          <span className="num">{num}</span>
          <span className="unit" style={{ opacity: unitP }}>%</span>
          <span className="arrow" style={{
            opacity: arrowP,
            transform: `translateY(${lerp(CONFIG.arrowRise, 0, arrowP)}px) scale(${lerp(CONFIG.arrowScale, 1, arrowP)})`,
          }}>
            <svg viewBox="0 0 20 34" aria-hidden="true">
              <path d="M10 2 L19 14 H13.2 V32 H6.8 V14 H1 Z" fill="#2fb344" />
            </svg>
          </span>
        </div>
        <div className="spark">
          <svg viewBox="0 0 400 96">
            <line className="base" x1="0" y1="90" x2="400" y2="90" />
            <g>
              <path d={d} fill="none" stroke={CONFIG.color} strokeWidth={3}
                strokeLinejoin="round" strokeLinecap="round"
                strokeDasharray={dashL} strokeDashoffset={dashL * (1 - lineP)} />
              {CONFIG.pts.map((p, i) => {
                // 数据点跟着线端推进依次弹出（时间由线长比例反推）
                const at = CONFIG.countAt + CONFIG.lineDur * invPower1InOut(cum[i] / L);
                const s = tw(t, at, CONFIG.dotPop, backOut(2));
                return (
                  <circle key={i} cx={p[0]} cy={p[1]} r={5} fill="#ffffff"
                    stroke={CONFIG.color} strokeWidth={3}
                    transform={`translate(${p[0]} ${p[1]}) scale(${s}) translate(${-p[0]} ${-p[1]})`} />
                );
              })}
            </g>
          </svg>
          <div className="xlabels"><span>周一</span><span>周二</span><span>周三</span><span>周四</span></div>
        </div>
      </div>
      <div className="host-wrap"><Host src={hostSrc} /></div>
    </AbsoluteFill>
  );
}
