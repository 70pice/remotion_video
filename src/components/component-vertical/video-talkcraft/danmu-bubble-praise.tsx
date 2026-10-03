import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// danmu-bubble-praise · 弹幕气泡 —— 自包含 Remotion 源码（与 demos/danmu-bubble-praise/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 131 };

const FPS = meta.fps;

// ——————————————————————————————————————————————————————————
// 可摘走的核心动画：弹幕气泡（进—停—走，四枚进出交叠成"评论在滚"）
// 命门：每枚的"停留"必须短到让第 3 枚进场时第 1 枚正在走 —— 交叠是本卡的全部语义。
// ——————————————————————————————————————————————————————————
const CONFIG = {
  startDelay: 0.40,   // 起手静置：等口播念到"评论都在说"
  stagger: 0.55,      // 枚与枚的进场错峰 s：本卡第一命门（配合 hold 决定交叠量）
  inDur: 0.30,        // 单枚进场耗时 s（power3.out）
  hold: 0.75,         // 单枚在屏停留 s：+inDur 后必须 ≤ 2×stagger，否则四枚挤成一墙
  outDur: 0.40,       // 单枚飘走耗时 s（power1.in，出场比入场轻）
  inX: 26,            // 进场横向位移 px（各自从最近的边缘外侧推入，左侧 −、右侧 +）
  inScale: 0.88,      // 进场起始缩放
  outY: -18,          // 飘走上移 px（弹幕是往上滚出去的）
  tailHold: 0.45,     // 末枚走后留白：读作"这一波评论过去了"
  tilt: [-1.5, 1.5, 1.2, -1.8],   // 各枚的静态倾斜（贴歪感靠形状，全程不抖）
};

/* 时间表（demo 秒）
   第 i 枚：tIn = 0.40 + i·0.55 进场 0.30s（power3.out）
            tOut = tIn + 0.30 + 0.75 飘走 0.40s（power1.in）
   末枚出完 3.50 + 0.45 留白 → 总 3.95s */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const power1In = (x: number) => x * x;

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

// —— 演示语境（不属于动效）：主持人占位铺满舞台，气泡绕在人物两侧 ——
const CSS = `
* { margin: 0; padding: 0; box-sizing: border-box; }   /* demo-shell 的全局 reset，布局依赖它 */
.host-full { position: absolute; inset: 0; z-index: 1; }

/* —— 动效本体 —— 四枚评论气泡。
   只有一枚带强调色（红 #e0452c），其余走灰阶实色（不叠 opacity，design-language §1 红线）。
   气泡 = 纯圆角胶囊，无尾巴三角（用户 2026-08-25 定版）、无描边、无投影。 */
.db-b {
  position: absolute;
  z-index: 3;
  padding: 11px 20px;
  border-radius: 999px;              /* 单行评论 = 胶囊，一屏只用这一档圆角 */
  font-size: 21px;
  font-weight: 600;
  line-height: 1.25;
  white-space: nowrap;
}
/* 四枚的落位与配色：一枚强调红，三枚灰阶（深/中/浅三级实色，靠明度分层） */
#b1 { left: 96px;  top: 92px;  background: #e8e8ec; color: #1d1d1f; }
#b2 { left: 700px; top: 158px; background: #e0452c; color: #ffffff; }   /* 唯一强调色 */
#b3 { left: 62px;  top: 296px; background: #f2f2f4; color: #6e6e73; }
#b4 { left: 686px; top: 372px; background: #e8e8ec; color: #545458; }
`;

// side-l / side-r 只决定**进场方向**（从最近的边缘外侧推入），不再画尾巴三角
const BUBBLES = [
  { id: "b1", dir: -1, text: "说得太对了" },
  { id: "b2", dir: 1, text: "干货满满 👍" },
  { id: "b3", dir: -1, text: "收藏了" },
  { id: "b4", dir: 1, text: "已经在用了" },
];


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

export default function DanmuBubblePraise({ hostSrc }: { hostSrc?: string }) {
  void hostSrc;
  void Host;
  const t = useCurrentFrame() / FPS;

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      

      {BUBBLES.map((b, i) => {
        const tIn = CONFIG.startDelay + i * CONFIG.stagger;
        const tOut = tIn + CONFIG.inDur + CONFIG.hold;
        // 进：飘入落定（opacity/x/scale 同一条 power3.out）
        const pIn = tw(t, tIn, CONFIG.inDur, power3Out);
        // 走：上移淡出（出场永远比入场轻——只走 opacity + y，不再动 scale）
        const pOut = tw(t, tOut, CONFIG.outDur, power1In);
        const opacity = t < tOut ? pIn : 1 - pOut;
        const x = lerp(b.dir * CONFIG.inX, 0, pIn);
        const y = lerp(0, CONFIG.outY, pOut);
        const scale = lerp(CONFIG.inScale, 1, pIn);
        return (
          <div key={b.id} id={b.id} className="db-b" style={{
            opacity,
            transform: `translate(${x}px, ${y}px) rotate(${CONFIG.tilt[i]}deg) scale(${scale})`,
            transformOrigin: "50% 50%",
          }}>
            {b.text}
          </div>
        );
      })}
    </AbsoluteFill>
  );
}
