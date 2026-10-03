import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// magnifier-detail · 局部放大镜 —— 自包含 Remotion 源码（与 demos/magnifier-detail/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用。目标框 + 连接线 + 圆形放大镜（镜内轻微扫视防死）。
// demo 录制 32.25s 是录制上限截断（镜内扫视 repeat:-1 无限 idle）；
// tsx 按有限动画结束点（0.95s）+ 2s idle 展示收尾。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 101 };

const FPS = meta.fps;

// —— 可摘走的核心动画（复制 CONFIG + 组件内动画段即可复用）——
const CONFIG = {
  zoom: 1.8,            // 放大倍数：1.5~2，再大内容糊
  magSize: 210,         // 放大镜直径 px
  magX: 745, magY: 252, // 放大镜落位中心（截图旁的空白区，别盖住目标本体）
  popIn: 0.3,           // 弹出耗时 s
  dimTo: 0.8,           // 底图压暗 brightness：白底截图取 0.75~0.85（0.6 会把白压成大灰块）
  startDelay: 0.45,     // 截图先看清一拍再弹镜
  panPx: 7,             // hold 期间镜内轻微扫视幅度 px
};

// 目标点（#magTarget「4 小时 32 分」）在截图内的坐标：demo 运行时读 DOM，移植按同版式实测定值
const TARGET = { px: 468.6, py: 218, w: 92.8 };
const SHOT = { x: 56, y: 116, w: 540 };   // 与 .shot 的 left/top/width 保持一致

/* 时间表（demo 秒）
   0.45–0.75  放大镜从目标点弹出到落位（power3.out）；底图压暗 1→0.8；目标框淡入（0.45–0.65）
   0.70–0.95  连接线从目标点向放大镜描出（power2.out）
   0.95–∞     hold：镜内内容 ±12.6px 扫视（sine.inOut yoyo repeat:-1，1.4s 半程） */

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);   // GSAP 缺省 ease
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const sineInOut = (x: number) => -(Math.cos(Math.PI * x) - 1) / 2;

// —— 演示语境（不属于动效）：假评测截图。白底 + 灰阶线框，零风格化 ——
const CSS = `
/* 与 demo 外壳一致的全局 reset（demo-shell.css）：不带它 UA 缺省 margin/content-box 会让版式整体走样 */
* { margin: 0; padding: 0; box-sizing: border-box; }
.shot {
  position: absolute;
  left: 56px;
  top: 116px;
  width: 540px;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  overflow: hidden;
  color: #1d1d1f;
}
.shot .bar { display:flex; gap:6px; padding:10px 14px; border-bottom:1px solid #ececec; }
.shot .bar i { width:10px; height:10px; border-radius:50%; background:#e0e0e0; }
.shot .body { padding: 16px 22px 20px; }
.shot h3 { font-size: 20px; margin-bottom: 4px; }
.shot .sub { font-size: 12px; color:#8a8a8a; margin-bottom: 14px; }
.shot .row {
  display:flex; justify-content:space-between; align-items:center;
  padding: 10px 2px; border-bottom: 1px solid #ececec;
  font-size: 16px;
}
.shot .row .lab { color:#8a8a8a; }
.shot .row .val { font-weight: 700; }
/* —— 动效本体 —— 目标框 + 连接线 + 圆形镜。指示红是语义色（"看这里"），只用在动效本体上 */
.target-box {
  position:absolute; border:2px solid #ff4d4d; border-radius:6px;
  pointer-events:none;
}
#link-line { position:absolute; inset:0; width:100%; height:100%; pointer-events:none; }
#magnifier {
  position:absolute; left:0; top:0;
  width: 210px; height: 210px;
  border-radius: 50%;
  border: 2px solid #1d1d1f;
  overflow: hidden;
  background: #ffffff;
}
#magnifier .mag-inner { position:absolute; left:0; top:0; transform-origin: 0 0; }
/* 放大副本：与 .shot 同结构，抹掉定位与边框 */
.mag-inner .shot { left:0; top:0; border:0; border-radius:0; }
`;

// 截图内容（底图与镜内副本共用一份结构，保证像素一致）
const ShotContent = () => (
  <>
    <div className="bar"><i /><i /><i /></div>
    <div className="body">
      <h3>星舟 Pro 14 · 实测数据</h3>
      <div className="sub">本站实验室 · 同一负载连续三轮取均值</div>
      <div className="row"><span className="lab">性能释放</span><span className="val">45W 持续</span></div>
      <div className="row"><span className="lab">屏幕亮度</span><span className="val">612 nit</span></div>
      <div className="row"><span className="lab">续航测试</span><span className="val">4 小时 32 分</span></div>
      <div className="row"><span className="lab">整机重量</span><span className="val">1.38 kg</span></div>
    </div>
  </>
);


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


/* slug-specific portrait: detail card and lens enlarge into central phone region. */
.mag-inner { left: 80px !important; right: 80px !important; top: 420px !important; transform: scale(1.25) !important; transform-origin: 0 0 !important; }


/* slug-specific portrait pass 2: enlarge source .shot and magnifier together. */
.shot { left: 80px !important; top: 390px !important; transform: scale(1.5) !important; transform-origin: 0 0 !important; }
.mag-inner { width: 390px !important; height: 390px !important; }

`;

export default function MagnifierDetail(_props: { hostSrc?: string }) {
  void _props;
  const t = useCurrentFrame() / FPS;
  const C = CONFIG;

  // 目标点/落位点的舞台坐标
  const px = TARGET.px, py = TARGET.py;
  const tx = SHOT.x + px, ty = SHOT.y + py;
  const lineLen = Math.hypot(C.magX - tx, C.magY - ty);
  const dashTotal = Math.ceil(lineLen) + 10;

  // 放大镜弹出：从目标点原位起跳到落位（power3.out）
  const popP = tw(t, C.startDelay, C.popIn, power3Out);
  const magOpacity = popP;
  const magScale = lerp(0.3, 1, popP);
  const magX = lerp(tx, C.magX, popP);
  const magY = lerp(ty, C.magY, popP);

  // 底图同步压暗 + 目标框淡入（缺省 power1.out）
  const dim = lerp(1, C.dimTo, tw(t, C.startDelay, 0.3, power1Out));
  const boxOpacity = tw(t, C.startDelay, 0.2, power1Out);

  // 连接线从目标点向放大镜描出——告诉观众"放大的是这里"
  const lineP = tw(t, C.startDelay + C.popIn - 0.05, 0.25, power2Out);
  const dashOn = dashTotal * lineP, dashOff = dashTotal * (1 - lineP);

  // hold：镜内内容轻微平移扫视（sine.inOut yoyo repeat:-1），画面不呆
  const panT0 = C.startDelay + C.popIn + 0.2;
  let pan = 0;
  if (t > panT0) {
    const cyc = (t - panT0) / 1.4;
    const k = Math.floor(cyc);
    const p = cyc - k;
    const pp = k % 2 === 1 ? 1 - p : p;
    pan = -C.panPx * C.zoom * sineInOut(pp);
  }
  // 放大副本定位：让目标点正好落在镜心（pan 叠加在 x 上）
  const innerX = C.magSize / 2 - C.zoom * px + pan;
  const innerY = C.magSize / 2 - C.zoom * py;

  // 目标点细描边框几何
  const boxL = px - TARGET.w / 2 - 8, boxT = py - 16, boxW = TARGET.w + 16;

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="shot" style={{ filter: `brightness(${dim})` }}>
        <ShotContent />
        <div className="target-box" style={{
          left: boxL, top: boxT, width: boxW, height: 32, opacity: boxOpacity,
        }} />
      </div>
      <svg id="link-line">
        <line x1={tx} y1={ty} x2={C.magX} y2={C.magY} stroke="#ff4d4d" strokeWidth={2}
          strokeDasharray={`${dashOn} ${dashOff}`} />
      </svg>
      <div id="magnifier" style={{
        opacity: magOpacity,
        transform: `translate(${magX - C.magSize / 2}px, ${magY - C.magSize / 2}px) scale(${magScale})`,
      }}>
        <div className="mag-inner" style={{
          transform: `translate(${innerX}px, ${innerY}px) scale(${CONFIG.zoom})`,
        }}>
          <div className="shot" style={{ position: "absolute", width: SHOT.w }}>
            <ShotContent />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
}
