import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// converging-arrows · 双箭头聚焦 —— 自包含 Remotion 源码（与 demos/converging-arrows/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 89 };

const FPS = meta.fps;

// ─────────────────────────────────────────────────────────────────────────
// 可摘走的核心动画：双箭头聚焦（两支手绘箭头从对角画向关键词，词后换色）
//   ① 命门①：箭头**先到、词后变**。两支箭尖都到位的那一帧关键词才换成强调色。
//      关键词**不做缩放**（用户 2026-08-25 定版：变色就够，放大缩小多余）
//   ② 命门②：箭尖要留白（离词 14~18px）。戳到字上就成了"划掉"不是"指向"
//   ③ 两支错峰只有 0.06s —— 几乎同时，制造"夹住"感
//   ④ 手绘感：杆是带弧度的三次贝塞尔（bow）+ 起笔粗收笔细（三层 stroke 共用一个笔尖）
//   ⑤ 画完干净静置：不做 line boil / 定格抖动
//   ★ demo 里箭尖坐标由 DOM 量出；tsx 纯函数渲染，把量好的关键词盒子固化进 CONFIG.box
// ─────────────────────────────────────────────────────────────────────────
const CONFIG = {
  startDelay: 0.42,     // 起手静置：等口播念到"记住"
  color: "#e8720c",     // 唯一语义色（橙，取自参考图②）
  tiers: [{ w: 4.8, frac: 0.16 }, { w: 3.8, frac: 0.46 }, { w: 2.8, frac: 1 }],
  shaft: 0.26,          // 画杆耗时 s
  headDur: 0.11,        // 箭头须：收笔快扫，>0.25s 箭头会"迟到"
  tipGap: 16,           // 命门②：箭尖离关键词盒子多远 px（14~18）
  // 关键词「这 3 点」的盒子（stage 坐标，量自 demo 运行时 boxOf(word)）
  box: { x: 240, y: 900, w: 300, h: 126 },
  arrows: [
    { // 右上来的那支：尖指关键词右上角
      at: 0, corner: "topRight" as const,
      fromDX: 300, fromDY: -260,        // 起笔点相对箭尖的位移（画外方向）
      bow: 24,                          // 杆的弧度（正 = 向外凸）
      headLen: 21, headSpread: 27,
    },
    { // 左下来的那支：错峰 0.06s，更短，弧向相反
      at: 0.06, corner: "bottomLeft" as const,
      fromDX: -280, fromDY: 245,
      bow: -20,
      headLen: 18, headSpread: 25,
    },
  ],
  colorDur: 0.1,        // 关键词换色时长 s：命门①的落点（硬切，不做颜色渐变）
  hold: 1.6,            // 收尾定格：箭头保留在屏上，观众看清"夹住的是这三个字"
};

/* 时间表（demo 秒）
   0.42–0.68  箭头 A 画杆（power3.out）；0.68–0.79 箭头须（power2.out）
   0.48–0.74  箭头 B 画杆；0.74–0.85 箭头须
   0.85–0.95  关键词换色 黑→橙（linear）
   0.95–2.55  收尾 hold 1.6s */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const lerpColor = (a: [number, number, number], b: [number, number, number], p: number) =>
  `rgb(${Math.round(lerp(a[0], b[0], p))}, ${Math.round(lerp(a[1], b[1], p))}, ${Math.round(lerp(a[2], b[2], p))})`;

const n = (v: number) => Math.round(v * 100) / 100;

// ② 一支箭头：杆（带弧度的三次贝塞尔）+ 头（两根须，按杆末端切线算，永远朝目标）
type ArrowSpec = (typeof CONFIG.arrows)[number];
function arrowPaths(box: typeof CONFIG.box, o: ArrowSpec, tipGap: number) {
  const right = box.x + box.w, bottom = box.y + box.h;
  // 箭尖落在目标盒子外的对角方向上，离盒子 tipGap（命门②：留白，不戳字）
  const g = tipGap / Math.SQRT2;
  const tip = {
    topRight: [right + g, box.y - g],
    bottomLeft: [box.x - g, bottom + g],
  }[o.corner];
  const s = [tip[0] + o.fromDX, tip[1] + o.fromDY];
  // 弧度：两个控制点垂直于弦方向偏 bow —— 直线杆读作 UI 引线，不是手画的箭头
  const dx = tip[0] - s[0], dy = tip[1] - s[1], L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L, ny = dx / L;                        // 弦的法向
  const c1 = [s[0] + dx * 0.3 + nx * o.bow, s[1] + dy * 0.3 + ny * o.bow];
  const c2 = [s[0] + dx * 0.68 + nx * o.bow * 0.55, s[1] + dy * 0.68 + ny * o.bow * 0.55];
  const shaftD = `M ${n(s[0])} ${n(s[1])} C ${n(c1[0])} ${n(c1[1])} ${n(c2[0])} ${n(c2[1])} ${n(tip[0])} ${n(tip[1])}`;
  // 贝塞尔长度：数值采样（与 getTotalLength 等价，误差 <0.01%）
  let shaftLen = 0;
  let px = s[0], py = s[1];
  for (let i = 1; i <= 256; i++) {
    const u = i / 256, v = 1 - u;
    const qx = v * v * v * s[0] + 3 * v * v * u * c1[0] + 3 * v * u * u * c2[0] + u * u * u * tip[0];
    const qy = v * v * v * s[1] + 3 * v * v * u * c1[1] + 3 * v * u * u * c2[1] + u * u * u * tip[1];
    shaftLen += Math.hypot(qx - px, qy - py);
    px = qx; py = qy;
  }
  // 末端切线（c2→tip）反向 ±headSpread 就是两根须；两须长度略不等 = 手作感
  const ang = Math.atan2(tip[1] - c2[1], tip[0] - c2[0]) + Math.PI;
  const barb = (dev: number, len: number) => [
    n(tip[0] + Math.cos(ang + (dev * Math.PI) / 180) * len),
    n(tip[1] + Math.sin(ang + (dev * Math.PI) / 180) * len),
  ];
  const b1 = barb(o.headSpread, o.headLen), b2 = barb(-o.headSpread - 5, o.headLen - 2.5);
  const headD = `M ${b1[0]} ${b1[1]} L ${n(tip[0])} ${n(tip[1])} L ${b2[0]} ${b2[1]}`;
  const headLen2 = Math.hypot(b1[0] - tip[0], b1[1] - tip[1]) + Math.hypot(b2[0] - tip[0], b2[1] - tip[1]);
  return { shaftD, shaftLen, headD, headLen: headLen2 };
}

// ③ 起笔粗收笔细的一笔：同一 d 叠 N 层线宽，共用一个弧长笔尖（三层绝不互相超车）
const InkStroke: React.FC<{
  d: string; len: number; color: string;
  tiers: { w: number; frac: number }[]; progress: number;
}> = ({ d, len, color, tiers, progress }) => (
  <>
    {tiers.map((tier, i) => {
      const span = len * tier.frac;
      return (
        <path key={i} d={d} fill="none" stroke={color} strokeWidth={tier.w}
          strokeLinecap="round" strokeLinejoin="round"
          strokeDasharray={`${n(span)} ${n(len + 4)}`}
          strokeDashoffset={n(Math.max(0, span - progress * len))} />
      );
    })}
  </>
);

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

// 演示语境（不属于动效）：主持人占右一列，左侧是口播正在念的一句话
const CSS = `
.host-wrap { position: absolute; right: 0; top: 0; bottom: 0; width: 47%; overflow: hidden; }
.say {
  position: absolute;
  left: 118px; top: 50%;
  transform: translateY(-50%);
  color: #1d1d1f;
  text-align: left;
}
.say-line { font-size: 32px; line-height: 1.9; font-weight: 400; white-space: nowrap; }
.say-line.lead { color: #8a8a8a; }
/* 被夹住的关键词：单独 inline-block（换色只作用在它自己身上，不带动整行） */
.say-line .focus { display: inline-block; font-size: 40px; font-weight: 600; will-change: color; }
/* 箭头层（动效本体）盖在文字之上 */
#arrowLayer { position: absolute; inset: 0; pointer-events: none; }
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


/* slug-specific portrait: keyword text and arrow targets share native 1080x1920 coordinates. */
.arrows { transform: none !important; }
#arrowLayer { position: absolute !important; inset: 0 !important; width: 1080px !important; height: 1920px !important; }
.say { left: 96px !important; right: 96px !important; top: 720px !important; transform: none !important; text-align: left !important; }
.say-line { font-size: 72px !important; line-height: 1.55 !important; white-space: normal !important; }
.say-line .focus { font-size: 104px !important; font-weight: 900 !important; }

`;

export default function ConvergingArrows({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  const arrows = CONFIG.arrows.map((a) => arrowPaths(CONFIG.box, a, CONFIG.tipGap));
  const allTipsAt = Math.max(
    ...CONFIG.arrows.map((a) => CONFIG.startDelay + a.at + CONFIG.shaft + CONFIG.headDur));

  // 命门①：两支箭尖都到位那一帧，关键词才换成强调色（不缩放）
  const colorP = tw(t, allTipsAt, CONFIG.colorDur, (x) => x);
  const wordColor = lerpColor([29, 29, 31], [232, 114, 12], colorP);

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      {/* 排版留白是本卡的前提：箭头要从对角**空白处**画进来 */}
      <div className="say">
        <div className="say-line lead">今天只要你</div>
        <div className="say-line">记住<span className="focus" style={{ color: wordColor }}>这 3 点</span>就够了</div>
      </div>
      
      <svg id="arrowLayer" viewBox="0 0 1080 1920">
        {arrows.map((paths, i) => {
          const at = CONFIG.startDelay + CONFIG.arrows[i].at;
          const shaftP = tw(t, at, CONFIG.shaft, power3Out);
          // 先杆后头的两笔笔顺（头在杆到位那一刻接上）
          const headP = tw(t, at + CONFIG.shaft, CONFIG.headDur, power2Out);
          return (
            <g key={i}>
              <InkStroke d={paths.shaftD} len={paths.shaftLen} color={CONFIG.color}
                tiers={CONFIG.tiers} progress={shaftP} />
              <InkStroke d={paths.headD} len={paths.headLen} color={CONFIG.color}
                tiers={[{ w: CONFIG.tiers[1].w, frac: 1 }]} progress={headP} />
            </g>
          );
        })}
      </svg>
    </AbsoluteFill>
  );
}


