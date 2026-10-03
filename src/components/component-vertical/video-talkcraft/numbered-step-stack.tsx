import React from "react";
import { AbsoluteFill, Loop, OffthreadVideo, useCurrentFrame } from "remotion";

// numbered-step-stack · 编号步骤堆入 —— 自包含 Remotion 源码（与 demos/numbered-step-stack/index.html 同画面）
// 复制本文件进你的工程即可用；主持人视频经 hostSrc prop 注入，不传则灰阶剪影占位。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 107 };

const FPS = meta.fps;

// —— 动效本体参数（照抄 demo 的 CONFIG）：四枚横条从右均匀堆入，每枚落地时编号块 punch，最后整组上浮收束 ——
const CONFIG = {
  lead: 0.4,          // 起手静置 s：等口播念到"四步"
  barIn: 0.24,        // 单枚横条入场耗时 s
  barStagger: 0.11,   // 错峰 s：**必须均匀**，不均匀读作卡顿
  barShift: 40,       // 从右侧进入的位移 px
  punchLag: 0.0,      // 编号块 punch 与该枚落定同帧（落地确认，不是延迟弹跳）
  punchScale: 1.12,   // 编号块 punch 起始倍数（1.12→1）
  punchDur: 0.133,    // punch 4 帧 @30fps
  settleLift: 4,      // 四枚落定后整组上浮 px：宣告"这是一组"
  settleDur: 0.20,    // 收束耗时 s
  settleGap: 0.08,    // 末枚落定 → 整组收束 的呼吸 s
  hold: 1.8,          // 收尾停留 s
};

const STEPS = [
  { no: "01", txt: "把手机放到另一个房间" },
  { no: "02", txt: "只写今天要交的那一件" },
  { no: "03", txt: "计时 25 分钟不许起身" },
  { no: "04", txt: "做完立刻记一行结果" },
];

/* 时间表（demo 秒）
   0.40+0.11i  第 i 枚横条从右堆入 opacity/x 40→0，0.24s（power3.out）
   +0.24       该枚落定同帧编号块 punch 1.12→1，0.133s（power2.out）
               ※ GSAP fromTo immediateRender：punch 未开始前编号块就停在 1.12
   1.183–1.383 整组上浮 -4px 收束（power2.out）
   1.383–3.183 收尾 hold 1.8s */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);

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

// 演示语境（不属于动效）：左侧人物列 + 右侧四枚横条（清单，无线、无连接关系）
const CSS = `
.host-col { position: absolute; left: 0; bottom: 0; width: 448px; height: 100%; }
.stack {
  position: absolute;
  right: 62px;
  top: 50%;
  width: 486px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.step-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  height: 66px;
  padding: 0 22px 0 0;
  border: 1px solid #e0e0e0;   /* hairline 立层级，不用投影 */
  border-radius: 12px;
  background: #ffffff;
}
/* 编号方块：唯一带强调色的件，落地时单独 punch 一拍 */
.step-no {
  flex: 0 0 auto;
  width: 64px; height: 64px;
  margin: -1px 0 -1px -1px;
  border-radius: 12px 0 0 12px;
  background: #2fb344;         /* 唯一强调色（取参考图③绿系） */
  color: #ffffff;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 1px;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: center;
}
.step-txt {
  font-size: 22px;
  font-weight: 600;
  line-height: 1.25;
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

.host-col{display:none!important}.stack{left:80px!important;right:80px!important;top:420px!important;width:auto!important;transform:translateY(0)!important}.step-bar{width:920px!important;height:180px!important;margin-bottom:38px!important;border-radius:34px!important}.step-no{font-size:64px!important;width:130px!important}.step-txt{font-size:50px!important}
`;

const EXTRA_PORTRAIT_CSS = `.host-col{display:none!important}.stack{left:80px!important;right:80px!important;top:420px!important;width:auto!important;transform:translateY(0)!important}.step-bar{width:920px!important;height:180px!important;margin-bottom:38px!important;border-radius:34px!important}.step-no{font-size:64px!important;width:130px!important}.step-txt{font-size:50px!important}`;

export default function NumberedStepStack({ hostSrc }: { hostSrc?: string }) {
  const t = useCurrentFrame() / FPS;

  // ③ 四枚都落定后整组轻微上浮收束——把四个动效收成一件事
  const settleAt = CONFIG.lead + (STEPS.length - 1) * CONFIG.barStagger
    + CONFIG.barIn + CONFIG.punchDur + CONFIG.settleGap;
  const stackY = -CONFIG.settleLift * tw(t, settleAt, CONFIG.settleDur, power2Out);

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS + EXTRA_PORTRAIT_CSS}</style>
      <div className="host-col"><Host src={hostSrc} /></div>

      {/* GSAP 保留 CSS 的 translateY(-50%)，px 位移叠加在其后 */}
      <div className="stack" style={{ transform: `translateY(-50%) translateY(${stackY}px)` }}>
        {STEPS.map((s, i) => {
          const at = CONFIG.lead + i * CONFIG.barStagger;
          // ① 横条从右堆入（错峰严格 0.11s × 4）
          const inP = tw(t, at, CONFIG.barIn, power3Out);
          // ② 落定同帧编号块 punch 一拍（fromTo immediateRender：punch 前一直停在 1.12）
          const punchAt = at + CONFIG.barIn + CONFIG.punchLag;
          const noScale = t < punchAt
            ? CONFIG.punchScale
            : lerp(CONFIG.punchScale, 1, tw(t, punchAt, CONFIG.punchDur, power2Out));
          return (
            <div key={i} className="step-bar" style={{
              opacity: inP,
              transform: `translateX(${lerp(CONFIG.barShift, 0, inP)}px)`,
            }}>
              <span className="step-no" style={{ transform: `scale(${noScale})` }}>{s.no}</span>
              <span className="step-txt">{s.txt}</span>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}
