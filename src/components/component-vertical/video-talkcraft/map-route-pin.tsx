import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// map-route-pin · 地图路线图钉 —— 自包含 Remotion 源码（与 demos/map-route-pin/index.html 同画面）
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 155 };

const FPS = meta.fps;

// —— 可摘走的核心动画参数 ——
const CONFIG = {
  routeGrow: 1.1,          // 单段路线生长时长 s：>1.5 拖节奏，<0.8 看不清走向
  pinDropFrom: 60,         // 图钉下落高度 px：越大砸感越重，>100 像天降
  pinDrop: 0.25,           // 下落时长 s，power2.in 加速砸下
  squashX: 1.3,            // 落地横向压扁倍数
  squashY: 0.7,            // 落地纵向压扁倍数（一帧级 0.06s）
  rebound: 0.28,           // 压扁后回弹时长 s
  labelSlide: 0.2,         // 地名标签侧滑时长 s
  legPause: 0.4,           // 第二段路线延迟接入的停顿 s（保叙事顺序）
  planeAngle: 0,           // 线头跟随物相对路径切线的角度补正 deg（机头朝右=0°，故为 0）
};

/* 时间表（demo 秒）
   0.15  北京落钉（下落 0.25 → 压扁 0.06 → 回弹 0.28；尘圈/标签 0.41 起）
   0.85–1.95  路线① 生长（power1.inOut），飞机贴线头
   1.95  上海落钉
   2.95–4.05  路线② 生长
   4.05  深圳落钉；4.15–4.40 飞机淡出缩小 → 4.76 尘圈散尽 */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power1In = (x: number) => x * x;
const power2In = (x: number) => x * x * x;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power1InOut = (x: number) => (x < 0.5 ? 2 * x * x : 1 - Math.pow(-2 * x + 2, 2) / 2);
const backOut = (s = 1.70158) => (x: number) => {
  const u = x - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};

// —— 二次贝塞尔弧长表（代替 getTotalLength / getPointAtLength）——
type Pt = { x: number; y: number };
const buildRoute = (P0: Pt, P1: Pt, P2: Pt, N = 240) => {
  const pts: Pt[] = [];
  for (let i = 0; i <= N; i++) {
    const u = i / N, v = 1 - u;
    pts.push({ x: v * v * P0.x + 2 * v * u * P1.x + u * u * P2.x,
               y: v * v * P0.y + 2 * v * u * P1.y + u * u * P2.y });
  }
  const cum = [0];
  for (let i = 1; i <= N; i++)
    cum.push(cum[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y));
  const len = cum[N];
  const pointAt = (s: number): Pt => {
    const target = Math.max(0, Math.min(len, s));
    let lo = 0, hi = N;
    while (lo < hi) { const mid = (lo + hi) >> 1; if (cum[mid] < target) lo = mid + 1; else hi = mid; }
    const i = Math.max(1, lo);
    const seg = cum[i] - cum[i - 1] || 1;
    const f = (target - cum[i - 1]) / seg;
    return { x: lerp(pts[i - 1].x, pts[i].x, f), y: lerp(pts[i - 1].y, pts[i].y, f) };
  };
  return { len, pointAt };
};

// 城市坐标与两段路线（贝塞尔控制点照抄 demo 的 path）
const CITY = [{ x: 260, y: 520 }, { x: 770, y: 940 }, { x: 410, y: 1380 }];
const ROUTES = [
  buildRoute({ x: 260, y: 520 }, { x: 760, y: 560 }, { x: 770, y: 940 }),
  buildRoute({ x: 770, y: 940 }, { x: 840, y: 1240 }, { x: 410, y: 1380 }),
];
const ROUTE_D = ["M 260,520 Q 760,560 770,940", "M 770,940 Q 840,1240 410,1380"];
const LABELS = ["北京 · 总部", "上海 · 中转仓", "深圳 · 工厂"];

// 落钉/生长的绝对时刻（与 demo 时间线一致）
const PIN_AT = [0.15, 0.85 + CONFIG.routeGrow, 0.85 + CONFIG.routeGrow + 0.6 + CONFIG.legPause + CONFIG.routeGrow];
const ROUTE_AT = [0.85, 0.85 + CONFIG.routeGrow + 0.6 + CONFIG.legPause];

// 主持人占位：演示语境素材，不属于动效本体
const Host: React.FC<{ src?: string }> = ({ src }) => (
  <div style={{ position: "absolute", inset: 0, display: "flex",
                alignItems: "flex-end", justifyContent: "center", background: "#fff",
                borderRadius: "50%" }}>
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

// —— 演示语境（不属于动效）：灰阶线框抽象地图 + 主播小窗 ——
//    底色例外：陆地用极浅灰 #f5f5f7、海域留白，"陆/海"必须可区分路线才读得懂
const CSS = `
.host-pip {
  position: absolute;
  left: 18px; bottom: 18px;
  width: 138px; height: 138px;
  border-radius: 50%;
  border: 1px solid #e0e0e0;
  overflow: hidden;
  background: #ffffff;
  z-index: 5;
}
/* —— 动效本体 —— 图钉：anchor 定位在城市坐标，内部元素才被动 */
.pin-anchor { position: absolute; width: 0; height: 0; z-index: 4; }
.pin {
  position: absolute;
  left: -13px; bottom: 0;
  width: 26px; height: 32px;
  transform-origin: 50% 100%;   /* squash 以钉尖为轴 */
}
.pin-head {
  position: absolute;
  left: 0; top: 0;
  width: 26px; height: 26px;
  background: #d8383a;
  border-radius: 50% 50% 50% 0;
  transform: rotate(-45deg);
}
.pin-head::after {              /* 钉帽白芯 */
  content: "";
  position: absolute;
  left: 8px; top: 8px;
  width: 10px; height: 10px;
  background: #ffffff;
  border-radius: 50%;
}
.pin-anchor.start .pin-head { background: #1d1d1f; }   /* 起点用深色区分 */
/* 落地尘圈（砸下时的地面反馈） */
.ring {
  position: absolute;
  left: -16px; top: -8px;
  width: 32px; height: 16px;
  border: 2px solid rgba(29, 29, 31, .55);
  border-radius: 50%;
}
/* 地名标签：从钉侧滑出 */
.pin-label {
  position: absolute;
  left: 18px; top: -34px;
  padding: 3px 10px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 700;
  color: #1d1d1f;
  white-space: nowrap;
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

.host-pip{display:none!important}.pin{left:-36px!important;width:72px!important;height:92px!important}.pin-head{width:72px!important;height:72px!important}.pin-head::after{left:22px!important;top:22px!important;width:28px!important;height:28px!important}.pin-label{left:48px!important;top:-58px!important;padding:14px 22px!important;border-radius:18px!important;font-size:38px!important}.ring{left:-58px!important;top:-30px!important;width:116px!important;height:72px!important;border-width:5px!important}
`;

const EXTRA_PORTRAIT_CSS = `.host-pip{display:none!important}.pin{left:-36px!important;width:72px!important;height:92px!important}.pin-head{width:72px!important;height:72px!important}.pin-head::after{left:22px!important;top:22px!important;width:28px!important;height:28px!important}.pin-label{left:48px!important;top:-58px!important;padding:14px 22px!important;border-radius:18px!important;font-size:38px!important}.ring{left:-58px!important;top:-30px!important;width:116px!important;height:72px!important;border-width:5px!important}`;

export default function MapRoutePin({ hostSrc }: { hostSrc?: string }) {
  const t = useCurrentFrame() / FPS;

  // —— 图钉四拍：加速下落 → 一帧压扁 → back 回弹；尘圈 + 标签在回弹前一点起步 ——
  const pinState = (i: number) => {
    const at = PIN_AT[i];
    const y = lerp(-CONFIG.pinDropFrom, 0, tw(t, at, CONFIG.pinDrop, power2In));
    const squashAt = at + CONFIG.pinDrop;
    const reboundAt = squashAt + 0.06;
    let sx = 1, sy = 1;
    if (t >= squashAt && t < reboundAt) {
      const p = tw(t, squashAt, 0.06, power1In);
      sx = lerp(1, CONFIG.squashX, p); sy = lerp(1, CONFIG.squashY, p);
    } else if (t >= reboundAt) {
      const p = tw(t, reboundAt, CONFIG.rebound, backOut(3));
      sx = lerp(CONFIG.squashX, 1, p); sy = lerp(CONFIG.squashY, 1, p);
    }
    const fxAt = reboundAt - 0.05;                       // 尘圈 "<-0.05"
    const ringP = tw(t, fxAt, 0.45, power2Out);
    const labelP = tw(t, fxAt, CONFIG.labelSlide, power2Out);
    return { visible: t >= at, y, sx, sy, ringP, labelP };
  };

  // —— 路线生长进度（power1.inOut；mask 的 dashoffset 由它算）——
  const routeP = (i: number) => tw(t, ROUTE_AT[i], CONFIG.routeGrow, power1InOut);

  // —— 飞机贴线头飞（取点 + 切线角；p=1 时 demo 的切线取样退化为 0°，照抄）——
  let plane: { x: number; y: number; deg: number; opacity: number; scale: number } | null = null;
  if (t >= ROUTE_AT[0]) {
    const leg = t >= ROUTE_AT[1] ? 1 : 0;
    const r = ROUTES[leg];
    const p = routeP(leg);
    const pt = r.pointAt(p * r.len);
    const next = r.pointAt(Math.min(p * r.len + 2, r.len));
    const deg = (Math.atan2(next.y - pt.y, next.x - pt.x) * 180) / Math.PI;
    const fadeP = tw(t, ROUTE_AT[1] + CONFIG.routeGrow + 0.1, 0.25, power2In);
    plane = { x: pt.x, y: pt.y, deg: deg + CONFIG.planeAngle,
              opacity: 1 - fadeP, scale: lerp(1, 0.4, fadeP) };
  }

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS + EXTRA_PORTRAIT_CSS}</style>

      {/* 灰阶线框抽象地图底（非真实地图数据） */}
      <svg style={{ position: "absolute", inset: 0, display: "block" }} viewBox="0 0 1080 1920">
        <defs>
          {ROUTE_D.map((d, i) => {
            const L = ROUTES[i].len + 2;   // +2 保证走完后盖满整条路线（butt 线帽）
            return (
              <mask id={`reveal-${i + 1}`} key={i}>
                <path d={d} fill="none" stroke="#fff" strokeWidth={28} strokeLinecap="butt"
                      strokeDasharray={L} strokeDashoffset={L * (1 - routeP(i))} />
              </mask>
            );
          })}
        </defs>

        {/* 经纬网 */}
        <g stroke="#ececef" strokeWidth={4}>
          <path d="M 180,0 V 1920 M 360,0 V 1920 M 540,0 V 1920 M 720,0 V 1920 M 900,0 V 1920" />
          <path d="M 0,240 H 1080 M 0,480 H 1080 M 0,720 H 1080 M 0,960 H 1080 M 0,1200 H 1080 M 0,1440 H 1080 M 0,1680 H 1080" />
        </g>

        {/* 大陆板块 + 岛屿 */}
        <g>
          <path d="M -40,260 L 760,180 C 680,380 860,500 720,700
                   C 620,845 900,925 760,1120
                   C 650,1270 570,1330 530,1520
                   C 490,1700 380,1780 320,1980 L -40,1980 Z"
                fill="#f5f5f7" stroke="#d2d2d7" strokeWidth={2} />
          <ellipse cx={890} cy={690} rx={58} ry={30} fill="#f5f5f7" stroke="#d2d2d7" strokeWidth={1.5} transform="rotate(-18 890 690)" />
          <ellipse cx={850} cy={1390} rx={48} ry={24} fill="#f5f5f7" stroke="#d2d2d7" strokeWidth={1.5} transform="rotate(12 850 1390)" />
          {/* 内陆虚线省界 */}
          <path d="M 250,330 C 370,570 270,850 480,1080 M 560,200 C 500,500 680,680 640,860"
                fill="none" stroke="#d8d8dc" strokeWidth={3} strokeDasharray="3 6" />
        </g>

        {/* 城市基点 */}
        <g fill="#8a8a8a">
          {CITY.map((c, i) => <circle key={i} cx={c.x} cy={c.y} r={9} />)}
        </g>

        {/* 两段贝塞尔虚线路线（被 mask 逐渐揭开）；路线色为语义色 */}
        {ROUTE_D.map((d, i) => (
          <path key={i} d={d} mask={`url(#reveal-${i + 1})`}
                fill="none" stroke="#d8383a" strokeWidth={12} strokeDasharray="28 24" strokeLinecap="round" />
        ))}
      </svg>

      {/* 三枚图钉（anchor 钉在城市坐标，钉尖对准基点） */}
      {CITY.map((c, i) => {
        const s = pinState(i);
        return (
          <div key={i} className={`pin-anchor${i === 0 ? " start" : ""}`} style={{ left: c.x, top: c.y }}>
            {/* 尘圈：fromTo 默认 immediateRender —— demo 从 0 帧起就以 scale0.2/op0.9 待命，照抄 */}
            <div className="ring" style={{
              opacity: t < PIN_AT[i] + CONFIG.pinDrop + 0.01 ? 0.9 : lerp(0.9, 0, s.ringP),
              transform: `scale(${t < PIN_AT[i] + CONFIG.pinDrop + 0.01 ? 0.2 : lerp(0.2, 1.6, s.ringP)})`,
            }} />
            <div className="pin" style={{
              opacity: s.visible ? 1 : 0,
              transform: `translateY(${s.y}px) scale(${s.sx}, ${s.sy})`,
            }}><div className="pin-head" /></div>
            <div className="pin-label" style={{
              opacity: s.labelP,
              left: i === 1 ? -390 : 48,
              transform: `translateX(${lerp(i === 1 ? 14 : -14, 0, s.labelP)}px)`,
            }}>{LABELS[i]}</div>
          </div>
        );
      })}

      {/* 沿路线飞行的线头跟随物（灰阶 SVG 机头） */}
      {plane && (
        <svg viewBox="0 0 24 24" aria-hidden="true" style={{
          position: "absolute", left: 0, top: 0, width: 64, height: 64, zIndex: 3,
          opacity: plane.opacity,
          transform: `translate(${plane.x}px, ${plane.y}px) translate(-50%, -50%) rotate(${plane.deg}deg) scale(${plane.scale})`,
        }}>
          {/* 机头朝右（0°）：切线角直接用 */}
          <path d="M 21,12 L 3,4 L 8,12 L 3,20 Z" fill="#1d1d1f" />
        </svg>
      )}

      {/* 演示语境：主播小窗 */}
      <div className="host-pip"><Host src={hostSrc} /></div>
    </AbsoluteFill>
  );
}
