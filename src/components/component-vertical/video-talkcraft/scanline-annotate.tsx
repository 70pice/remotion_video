import React from "react";
import { AbsoluteFill, Img, useCurrentFrame } from "remotion";

// scanline-annotate · 扫描线逐处点名 —— 自包含 Remotion 源码（与 demos/scanline-annotate/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 一条亮扫描线匀速掠过截图，越过每个目标下缘那一刻取景框 1.75→1 收拢对准 + 对焦确认闪，滞后 5 帧右侧标注淡入并常驻；
// 右上状态行实时数 0/4 → 4/4 → 分析完成。复制本文件进你的工程即可用；真截图经 src 注入、目标 bbox 经 targets 注入、标注文案经 labels 注入。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 180 };   // 5.6s 镜头 + 0.4s 收尾

const FPS = meta.fps;

// ——————————————————————————————————————————————————————————
// 可摘走的核心参数（与 demo 的 CONFIG 同名同注释）
// 命门：① 扫描线零缓动匀速（加 ease 读作有人在拖进度条）；② 触发时刻由目标 bbox 反算——扫描线越过目标**下缘**那一刻取景框才弹；
//      ③ 取景框 1.75→1 back.out 收拢对准 + 7% 对焦确认闪；④ 标注滞后取景框 5 帧（框稳了才命名），落位后常驻不撤；⑤ 计数行实时数 fired，不写死。
// ——————————————————————————————————————————————————————————
const CONFIG = {
  t0: 0.5,             // 扫描线起点 s
  dur: 2.4,            // 扫描线走完全程的时长 s（零缓动）
  yFrom: -30,          // 扫描线起始 y（相对截图顶，先从画外进）
  yTo: 416,            // 扫描线终点 y（越过截图底 396 再淡出）
  gap: 0.15,           // 两个目标触发的最小间隔 s（y 接近的目标钳开逐个弹）
  pad: 8,              // 取景框比目标外扩 px
  bkScale: 1.75,       // 取景框收拢起点倍率（1.2 看不出对准）
  bkDur: 0.4,          // 取景框收拢时长 s（back.out(2)）
  flashPeak: 0.07,     // 对焦确认闪峰值（>0.15 读作选中高亮）
  labelLag: 0.17,      // 标注滞后取景框的时间 s（≈5 帧："框稳了才命名"）
  doneLag: 0.2,        // 扫描结束后多久切"分析完成"
  exitAt: 5.2,         // 整体退场起点（0.4s power2.in）
  end: 5.6,            // 镜头结束
  shot: { x: 80, y: 48, w: 600, h: 396 },   // 截图左上角与尺寸（舞台坐标），目标 bbox 相对它
};

/* 时间表（demo 秒）
   0.35–0.50  扫描线淡入；0.50–2.90 匀速 y −30→416；2.90–3.10 淡出
   1.22 / 2.07 / 2.36 / 2.67  四个取景框依次收拢（0.4s back.out(2)）→ +0.12 对焦闪 → +0.17 标注淡入 → 计数 +1
   3.10       状态行切"分析完成 · 4 处"并转强调色
   5.20–5.60  整体退场（power2.in） */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) => ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const linear = (x: number) => x;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power2In = (x: number) => x * x * x;
const backOut = (s = 1.70158) => (x: number) => { const u = x - 1; return 1 + (s + 1) * u * u * u + s * u * u; };

// —— 演示语境（不属于动效）：样式照搬 demo（类名加 sla- 前缀）——
const CSS = `
* { margin: 0; padding: 0; box-sizing: border-box; }
.sla-shot { position: absolute; left: 80px; top: 48px; width: 600px; height: 396px; background: #ffffff; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,.08); }
.sla-shot .sla-bar { height: 38px; background: #f5f5f7; border-bottom: 1px solid #e0e0e0; display: flex; align-items: center; gap: 8px; padding: 0 14px; }
.sla-shot .sla-bar i { width: 10px; height: 10px; border-radius: 50%; background: #d9d9de; }
.sla-shot .sla-row { position: absolute; left: 26px; height: 12px; border-radius: 6px; background: #ececf0; }
.sla-shot .sla-tgt { position: absolute; border-radius: 8px; background: #e3e3e8; }
.sla-scan { position: absolute; left: 80px; top: 48px; width: 600px; height: 2px;
  background: linear-gradient(90deg, transparent, #0066cc 18%, #0066cc 82%, transparent); box-shadow: 0 0 14px rgba(0,102,204,.55); }
.sla-bk { position: absolute; }
.sla-bk i { position: absolute; width: 14px; height: 14px; border: 2px solid #0066cc; }
.sla-bk i.tl { left: -2px; top: -2px; border-right: 0; border-bottom: 0; }
.sla-bk i.tr { right: -2px; top: -2px; border-left: 0; border-bottom: 0; }
.sla-bk i.bl { left: -2px; bottom: -2px; border-right: 0; border-top: 0; }
.sla-bk i.br { right: -2px; bottom: -2px; border-left: 0; border-top: 0; }
.sla-bk b { position: absolute; inset: 0; background: #0066cc; border-radius: 6px; }
.sla-lab { position: absolute; left: 712px; width: 200px; padding-left: 14px; border-left: 2px solid #0066cc; font-size: 20px; font-weight: 600; color: #1d1d1f; line-height: 1.25; }
.sla-lab small { display: block; font-size: 14px; color: #7a7a7a; font-weight: 500; margin-top: 4px; }
.sla-status { position: absolute; right: 80px; top: 22px; font-family: "SF Mono", Menlo, monospace; font-size: 14px; letter-spacing: 1.5px; color: #7a7a7a; }
`;

/** 目标 bbox（相对截图左上角，px） */
export type Target = { x: number; y: number; w: number; h: number; /** 仅演示占位用：灰块底色 / 圆角 */ bg?: string; radius?: number };

/** demo 里 CSS 假落地页的四个目标：标题块 / 首图 / CTA 按钮 / 价格 */
const DEMO_TARGETS: Target[] = [
  { x: 26, y: 62, w: 320, h: 42 },
  { x: 26, y: 162, w: 548, h: 100, bg: "#dcdce2" },
  { x: 26, y: 274, w: 150, h: 42, bg: "#0066cc", radius: 21 },
  { x: 26, y: 338, w: 170, h: 36 },
];
const DEMO_LABELS = [
  { text: "标题没说清是什么", sub: "01 · 首屏" },
  { text: "首图占了六成视口", sub: "02 · 图片" },
  { text: "按钮文案\"了解更多\"", sub: "03 · CTA" },
  { text: "价格藏在最底下", sub: "04 · 定价" },
];

type Props = {
  /** 真截图（铺满 600×396 截图卡，object-fit cover）；不传 = CSS 假落地页 */
  src?: string;
  /** 目标 bbox 列表（相对截图左上角），按 y 从上到下；不传 = demo 四个 */
  targets?: Target[];
  /** 每个目标的标注（与 targets 一一对应）：主行 + 副行 */
  labels?: { text: string; sub?: string }[];
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


/* slug-specific portrait: real source nodes are sla-* scanner elements. Geometry is handled inline so scanline, target boxes and labels share one coordinate system. */
.sla-shot { border-radius: 30px !important; box-shadow: 0 28px 90px rgba(0,0,0,.10) !important; }
.sla-scan { height: 4px !important; }
.sla-bk i { width: 28px !important; height: 28px !important; border-width: 4px !important; }
.sla-lab { width: auto !important; border-left-width: 4px !important; font-size: 38px !important; line-height: 1.18 !important; padding-left: 22px !important; }
.sla-lab small { font-size: 24px !important; margin-top: 10px !important; }
.sla-status { right: 76px !important; top: 120px !important; font-size: 30px !important; }

`;

export default function ScanlineAnnotate({ src, targets = DEMO_TARGETS, labels = DEMO_LABELS }: Props) {
  const t = useCurrentFrame() / FPS;
  const n = targets.length;

  // 触发时刻 = 扫描线越过目标下缘那一刻；再按顺序钳最小间隔
  const travel = CONFIG.yTo - CONFIG.yFrom;
  const fts: number[] = [];
  targets.forEach((tg, i) => {
    const raw = CONFIG.t0 + ((tg.y + tg.h - CONFIG.yFrom) / travel) * CONFIG.dur;
    fts.push(i ? Math.max(raw, fts[i - 1] + CONFIG.gap) : raw);
  });
  const fired = fts.filter((f) => t >= f).length;
  const done = t >= CONFIG.t0 + CONFIG.dur + CONFIG.doneLag;

  // 扫描线：淡入 → 匀速 → 淡出
  const scanY = lerp(CONFIG.yFrom, CONFIG.yTo, tw(t, CONFIG.t0, CONFIG.dur, linear));
  const scanOp = tw(t, CONFIG.t0 - 0.15, 0.15, power1Out) - tw(t, CONFIG.t0 + CONFIG.dur, 0.2, power1Out);

  // 整体退场
  const exitK = 1 - tw(t, CONFIG.exitAt, CONFIG.end - CONFIG.exitAt, power2In);

  const portrait = { x: 70, y: 350, scale: 1.55 };
  const shotW = CONFIG.shot.w * portrait.scale;
  const shotH = CONFIG.shot.h * portrait.scale;
  const targetLeft = (tg: Target) => portrait.x + (tg.x - CONFIG.pad) * portrait.scale;
  const targetTop = (tg: Target) => portrait.y + (tg.y - CONFIG.pad) * portrait.scale;
  const targetWidth = (tg: Target) => (tg.w + 2 * CONFIG.pad) * portrait.scale;
  const targetHeight = (tg: Target) => (tg.h + 2 * CONFIG.pad) * portrait.scale;

  return (
    <AbsoluteFill style={{ background: "#ffffff", color: "#1d1d1f", overflow: "hidden", fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif' }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      {/* 截图（演示语境）：真截图铺满，或 CSS 假落地页 */}
      <div className="sla-shot" style={{ opacity: exitK, left: portrait.x, top: portrait.y, width: CONFIG.shot.w, height: CONFIG.shot.h, transform: `scale(${portrait.scale})`, transformOrigin: "0 0" }}>
        {src ? (
          <Img src={src} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
        ) : (
          <>
            <div className="sla-bar"><i /><i /><i /></div>
            {targets.map((tg, i) => (
              <div key={i} className="sla-tgt" style={{ left: tg.x, top: tg.y, width: tg.w, height: tg.h, background: tg.bg, borderRadius: tg.radius }} />
            ))}
            <div className="sla-row" style={{ top: 118, width: 420 }} /><div className="sla-row" style={{ top: 138, width: 360 }} />
          </>
        )}
      </div>
      {/* 扫描线 */}
      <div className="sla-scan" style={{ left: portrait.x, top: portrait.y, width: shotW, opacity: scanOp * exitK, transform: `translateY(${scanY * portrait.scale}px)` }} />
      {/* 取景框 + 标注：几何由目标 bbox 反推 */}
      {targets.map((tg, i) => {
        const ft = fts[i];
        const bkP = tw(t, ft, CONFIG.bkDur, backOut(2));
        const bkOp = tw(t, ft, CONFIG.bkDur * 0.5, power1Out);          // 与 demo 一致：opacity 与 scale 同一条 tween，前半程已满亮
        const flash = tw(t, ft + 0.12, 0.12, power1Out) * CONFIG.flashPeak - tw(t, ft + 0.24, 0.35, power1Out) * CONFIG.flashPeak;
        const labP = tw(t, ft + CONFIG.labelLag, 0.35, power2Out);
        const lab = labels[i] || { text: "" };
        return (
          <React.Fragment key={i}>
            <div className="sla-bk" style={{
              left: targetLeft(tg), top: targetTop(tg), width: targetWidth(tg), height: targetHeight(tg),
              opacity: Math.min(1, bkOp * 1.6) * exitK, transform: `scale(${lerp(CONFIG.bkScale, 1, bkP)})`, transformOrigin: "50% 50%",
            }}>
              <i className="tl" /><i className="tr" /><i className="bl" /><i className="br" />
              <b style={{ opacity: Math.max(0, flash) }} />
            </div>
            <div className="sla-lab" style={{ left: 108, right: 108, top: portrait.y + shotH + 92 + i * 132, opacity: labP * exitK, transform: `translateY(${lerp(10, 0, labP)}px)` }}>
              {lab.text}{lab.sub ? <small>{lab.sub}</small> : null}
            </div>
          </React.Fragment>
        );
      })}
      {/* 状态行：实时计数 */}
      <div className="sla-status" style={{ opacity: exitK, color: done ? "#0066cc" : "#7a7a7a" }}>
        {done ? `分析完成 · ${n} 处` : `扫描 · ${fired}/${n}`}
      </div>
    </AbsoluteFill>
  );
}
