import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// hand-drawn-ellipse · 手绘圈重点 —— 自包含 Remotion 源码（与 demos/hand-drawn-ellipse/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 102 };

const FPS = meta.fps;

// ─────────────────────────────────────────────────────────────────────────
// 可摘走的核心动画：手绘圈重点（一笔画 1.08 圈的歪椭圆 + 圈完才 punch）
//   ① 不是完美椭圆：长短轴比 3.4:1、整体倾斜 -3.5°、半径带确定性正弦起伏，
//      逆时针一笔画到 1.08 圈：尾巴过头 8% 与起笔交叉
//   ② 单条 path、恒定线宽（3.2px，linecap round）：手作感只做在形状上，不模拟笔压
//   ③ 圈到位之后被圈短语才 punch scale 1.06→1（同时发生读作"字被圈撞了一下"）
//   ④ 画完干净静置：不做 line boil / 定格抖动（design-language.md §4）
//   ★ demo 里 path 是运行时量 DOM 算出来的；tsx 是纯函数渲染，故把 demo 运行时
//     算出的 path 原样照抄进 ELLIPSE（960×540 设计坐标，含 getTotalLength 实测长度）
// ─────────────────────────────────────────────────────────────────────────
const CONFIG = {
  startDelay: 0.42,     // 起手静置：等口播念到这个短语
  color: "#e8720c",     // 唯一语义色（橙）
  draw: 0.50,           // 画圈耗时 s：<0.3 看不出笔顺、>0.8 观众在等
  width: 3.2,           // 恒定线宽 px（3~3.5）：全程一个值，不做笔压粗细变化
  punchGap: 0.06,       // 圈画完到 punch 之间的呼吸（必须 >0）
  punchScale: 1.06,     // punch 幅度：>1.12 读作弹跳不是重音
  punchDur: 0.22,
  hold: 1.8,            // 收尾定格：圈住的短语就是落点
};

/* 时间表（demo 秒）
   0.42–0.92  画圈：dashoffset L→0（power2.out，起笔快收笔缓）
   0.98–1.20  punch：短语 scale 1.06→1（power3.out，origin 50% 55%）
   1.20–3.00  hold 定格 */

// demo 运行时 ellipsePath(inkBoxOf(word), CONFIG) 的输出（原样照抄）
const ELLIPSE = {
  len: 760,
  d: "M 86 1018 C 110 982 184 968 270 976 C 370 985 438 1024 416 1064 C 392 1106 292 1124 188 1112 C 104 1102 54 1064 86 1018 C 112 982 190 968 286 978 C 382 988 436 1027 410 1066",
};

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const n = (v: number) => Math.round(v * 100) / 100;

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

// —— 演示语境（不属于动效）：主持人占右一列，左侧是口播正在念的一句话 ——
const CSS = `
.host-wrap { position: absolute; right: 0; top: 0; bottom: 0; width: 47%; overflow: hidden; }
.say {
  position: absolute;
  left: 100px; right: 410px;
  top: 50%;
  transform: translateY(-50%);
  color: #1d1d1f;
}
/* 行距要给圈留地方：圈的上下沿会外扩 padY，行距太密圈会咬到上一行 */
.say-line { font-size: 28px; line-height: 2.4; font-weight: 400; white-space: nowrap; }
.say-line.lead { color: #8a8a8a; }
/* 被圈的短语单独成一个 inline-block —— punch 要作用在它自己身上，不能带动整行 */
.say-line .ring-word {
  display: inline-block;
  font-weight: 600;
  will-change: transform;
}
/* 圈层（动效本体）盖在文字之上 */
#inkLayer { position: absolute; inset: 0; pointer-events: none; }
#inkLayer path { fill: none; stroke-linecap: round; stroke-linejoin: round; }
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

export default function HandDrawnEllipse({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  // ④ 一笔：单条 path、恒定线宽，dasharray 描画（起笔快收笔缓）
  const v = tw(t, CONFIG.startDelay, CONFIG.draw, power2Out);
  const L = ELLIPSE.len;

  // 命门②：圈到位之后（+punchGap）短语才 punch 一拍（scale 1.06→1，power3.out）
  const punchAt = CONFIG.startDelay + CONFIG.draw + CONFIG.punchGap;
  const scale = t < punchAt
    ? 1
    : lerp(CONFIG.punchScale, 1, tw(t, punchAt, CONFIG.punchDur, power3Out));

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="say">
        <div className="say-line lead">要求可以再高一点，但对自己</div>
        <div className="say-line">
          <span className="ring-word" style={{
            transform: `scale(${scale})`, transformOrigin: "50% 55%",
          }}>更松弛一点</span>
        </div>
      </div>
      
      <svg id="inkLayer" viewBox="0 0 1080 1920">
        <path d={ELLIPSE.d} stroke={CONFIG.color} strokeWidth={CONFIG.width}
              strokeDasharray={`${n(L)} ${n(L + 4)}`}
              strokeDashoffset={n(Math.max(0, L * (1 - v)))} />
      </svg>
    </AbsoluteFill>
  );
}
