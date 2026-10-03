import React from "react";
import { AbsoluteFill, Img, useCurrentFrame } from "remotion";

// reticle-lock-on · 准星咬合 —— 自包含 Remotion 源码（与 demos/reticle-lock-on/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 四个 L 角从四个画外方向扑向截图上的目标，到位时框仍是目标的 2.2 倍，再收缩过头到 0.94 回弹到 1（"咔"），
// 咬合那一帧目标微亮 + 标签同帧弹出，之后钉死。复制本文件进你的工程即可用；真截图经 src 注入、目标 bbox 经 target 注入、标签经 label 注入。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 192 };   // 6.0s 镜头 + 0.4s 收尾

const FPS = meta.fps;

// ——————————————————————————————————————————————————————————
// 可摘走的核心参数（与 demo 的 CONFIG 同名同注释）
// 命门：① 四角从画外 ≥1000px 扑入（行程短读作"角标出现"不是"扑过来"）；② 飞入与收缩解耦——到位时框仍是目标的 2.2 倍，
//      再收缩过头到 0.94 回弹到 1（无超调没有"咔"的咬合感）；③ 咬合帧目标微亮 .55→.28 与标签 back 弹出必须同帧（错帧就散了）；④ 之后钉死真静止。
// ——————————————————————————————————————————————————————————
const CONFIG = {
  at: 1.3,             // 四角起跳时刻 s（前面留 1.3s 让观众先看到整页）
  fly: 0.33,           // 飞入时长 s（≈10 帧，power2.out）
  big: 2.2,            // 到位时框相对目标 bbox 的倍率
  under: 0.94,         // 收缩过头倍率
  shrink: 0.2,         // 收缩到 0.94 的时长 s（power2.in）
  snap: 0.15,          // 回弹到 1 的时长 s（back.out(2)）——"咔"
  pad: 10,             // 框比目标 bbox 外扩 px
  off: [[-700, -500], [700, -500], [-700, 500], [700, 500]] as [number, number][],   // 四角画外起点（相对终点的位移）
  flashPeak: 0.55,     // 咬合帧目标白闪峰值，随后落到 flashHold
  flashHold: 0.28,     // 白闪回落后的驻留值（目标微亮常驻）
  exitAt: 5.6,         // 整体退场起点（0.4s power2.in）
  end: 6.0,            // 镜头结束
  shot: { x: 80, y: 320, w: 920, h: 1120 },   // native portrait screenshot bounds, target bbox relative to it
};

/* 时间表（demo 秒）
   1.30–1.63  四角从 (±700, ±500) 画外扑入到 2.2 倍框位（power2.out）
   1.63–1.83  收缩过头到 0.94（power2.in）
   1.83       咬合帧：回弹到 1（0.15s back.out(2)）+ 目标白闪 .55（0.04s）→ .28（0.2s）+ 标签 back.out(1.8) 弹出 0.35s
   5.60–6.00  整体退场（power2.in） */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) => ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power2In = (x: number) => x * x * x;
const backOut = (s = 1.70158) => (x: number) => { const u = x - 1; return 1 + (s + 1) * u * u * u + s * u * u; };

// —— 演示语境（不属于动效）：样式照搬 demo（类名加 rlo- 前缀）——
const CSS = `
* { margin: 0; padding: 0; box-sizing: border-box; }
.rlo-shot { position: absolute; left: 130px; top: 60px; width: 700px; height: 420px; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; }
.rlo-shot .rlo-bar { height: 40px; background: #f5f5f7; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 8px; padding: 0 14px; }
.rlo-shot .rlo-bar i { width: 10px; height: 10px; border-radius: 50%; background: #d9d9de; }
.rlo-shot .rlo-row { position: absolute; left: 30px; height: 12px; border-radius: 6px; background: #ececf0; }
.rlo-shot .rlo-tg { position: absolute; border-radius: 25px; background: #0066cc; color: #fff; font-size: 18px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
.rlo-tgf { position: absolute; background: #fff; }
.rlo-rt { position: absolute; width: 22px; height: 22px; border: 3px solid #0066cc; }
.rlo-rt.a { border-right: 0; border-bottom: 0; } .rlo-rt.b { border-left: 0; border-bottom: 0; } .rlo-rt.c { border-right: 0; border-top: 0; } .rlo-rt.d { border-left: 0; border-top: 0; }
.rlo-lab { position: absolute; font-size: 22px; font-weight: 700; color: #1d1d1f; background: #ffffff; border: 1.5px solid #0066cc; padding: 6px 14px; border-radius: 8px; white-space: nowrap; transform-origin: 0 50%; }
`;

/** 目标 bbox（相对截图左上角，px） */
export type Target = { x: number; y: number; w: number; h: number };
/** demo 里 CSS 假设置页的按钮位置 */
const DEMO_TARGET: Target = { x: 60, y: 680, w: 520, h: 96 };

type Props = {
  /** 真截图（铺满 700×420 截图卡，object-fit cover）；不传 = CSS 假设置页 */
  src?: string;
  /** 目标 bbox（相对截图左上角）；不传 = demo 按钮 */
  target?: Target;
  /** 咬合帧弹出的标签 */
  label?: string;
  /** 假设置页里目标按钮的文字（仅无 src 时用） */
  buttonText?: string;
};


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


/* slug-specific portrait: large native document; target, reticle, flash and label use the same CONFIG shot bounds. */
.rlo-shot { left:80px!important; top:320px!important; width:920px!important; height:1120px!important; border-radius:34px!important; }
.rlo-shot .rlo-bar { height:82px!important; gap:14px!important; padding:0 28px!important; }
.rlo-shot .rlo-bar i { width:18px!important; height:18px!important; }
.rlo-shot .rlo-row { left:60px; height:24px!important; border-radius:14px!important; }
.rlo-shot .rlo-tg { font-size:36px!important; border-radius:48px!important; padding:0 22px!important; white-space:nowrap!important; }
.rlo-rt { width:34px!important; height:34px!important; border-width:5px!important; }
.rlo-lab { font-size:38px!important; padding:16px 26px!important; border-radius:18px!important; white-space:nowrap!important; }

`;

export default function ReticleLockOn({ src, target = DEMO_TARGET, label = "就是这个按钮", buttonText = "立即开通 ¥ 199 / 年" }: Props) {
  const t = useCurrentFrame() / FPS;
  // 四角终点几何由目标 bbox 反推（外扩 pad）
  const bx = CONFIG.shot.x + target.x - CONFIG.pad, by = CONFIG.shot.y + target.y - CONFIG.pad;
  const bw = target.w + 2 * CONFIG.pad, bh = target.h + 2 * CONFIG.pad, cx = bx + bw / 2, cy = by + bh / 2;
  const corners: [number, number][] = [[bx, by], [bx + bw - 22, by], [bx, by + bh - 22], [bx + bw - 22, by + bh - 22]];
  const LOCK = CONFIG.at + CONFIG.fly + CONFIG.shrink;   // 咬合帧

  // 飞入（位移）与收缩（倍率）解耦
  const flyP = tw(t, CONFIG.at, CONFIG.fly, power2Out);
  const s = t < CONFIG.at + CONFIG.fly ? CONFIG.big
    : t < LOCK ? lerp(CONFIG.big, CONFIG.under, tw(t, CONFIG.at + CONFIG.fly, CONFIG.shrink, power2In))
    : lerp(CONFIG.under, 1, tw(t, LOCK, CONFIG.snap, backOut(2)));
  const rtOn = t >= CONFIG.at;
  // 咬合帧：目标微亮 + 标签同帧
  const flash = t < LOCK ? 0 : lerp(0, CONFIG.flashPeak, tw(t, LOCK, 0.04, power1Out)) - lerp(0, CONFIG.flashPeak - CONFIG.flashHold, tw(t, LOCK + 0.04, 0.2, power1Out));
  const labP = tw(t, LOCK, 0.35, backOut(1.8)), labOp = tw(t, LOCK, 0.35 * 0.5, power1Out);
  const exitK = 1 - tw(t, CONFIG.exitAt, CONFIG.end - CONFIG.exitAt, power2In);

  return (
    <AbsoluteFill style={{ background: "#f5f5f7", color: "#1d1d1f", overflow: "hidden", fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif' }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      {/* 截图（演示语境）：真截图铺满，或 CSS 假设置页；目标微亮层按 bbox 定位 */}
      <div className="rlo-shot" style={{ opacity: exitK }}>
        {src ? (
          <Img src={src} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <>
            <div className="rlo-bar"><i /><i /><i /></div>
            <div className="rlo-row" style={{ top: 150, width: 420 }} /><div className="rlo-row" style={{ top: 210, width: 650 }} /><div className="rlo-row" style={{ top: 270, width: 560 }} />
            <div className="rlo-row" style={{ top: 420, width: 760, height: 170, borderRadius: 24, background: "#f0f0f3" }} />
            <div className="rlo-tg" style={{ left: target.x, top: target.y, width: target.w, height: target.h }}>{buttonText}</div>
            <div className="rlo-row" style={{ top: 710, left: 620, width: 280 }} /><div className="rlo-row" style={{ top: 840, width: 720 }} />
          </>
        )}
        <i className="rlo-tgf" style={{ left: target.x, top: target.y, width: target.w, height: target.h, borderRadius: target.h / 2, opacity: Math.max(0, flash) }} />
      </div>
      {/* 四个 L 角：飞入位移 + 绕目标中心同比收缩 */}
      {corners.map(([x, y], k) => {
        const dx = (x + 11 - cx) * s, dy = (y + 11 - cy) * s;
        const ox = lerp(CONFIG.off[k][0], 0, flyP), oy = lerp(CONFIG.off[k][1], 0, flyP);
        return <div key={k} className={`rlo-rt ${"abcd"[k]}`} style={{ left: cx + dx - 11 + ox, top: cy + dy - 11 + oy, opacity: (rtOn ? 1 : 0) * exitK }} />;
      })}
      {/* 标签：目标右侧 18px，与目标垂直居中，咬合帧 back 弹出 */}
      <div className="rlo-lab" style={{ left: bx + bw + 18, top: cy - 22, opacity: labOp * exitK, transform: `scale(${lerp(0.6, 1, labP)})` }}>{label}</div>
    </AbsoluteFill>
  );
}
