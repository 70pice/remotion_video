import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// highlighter-sweep · 荧光笔高亮扫过 —— 自包含 Remotion 源码（与 demos/highlighter-sweep/index.html 同画面）
// Portrait adaptation: copied from the original Talkcraft card, with only canvas/geometry/CSS reflowed for native 9:16.
// 复制本文件进你的工程即可用。本卡无主持人（纯文字引用卡）。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 60 };

const FPS = meta.fps;

// —— 可摘走的核心动画参数：扫过 + 压暗 + 浮起 三个动作一个时序 ——
const CONFIG = {
  startDelay: 0.7,   // 静置一拍，等口播念到关键句
  sweep: 0.6,        // 荧光块扫过耗时 s：0.4~0.8 匹配朗读语速，太快像 bug
  dimTo: 0.4,        // 其余段落压暗到的透明度：不压暗=强调失效
  liftScale: 1.03,   // 扫完整句轻微浮起倍数
};

/* 时间表（demo 秒）
   0.70–1.30  荧光块 scaleX 0→1（power2.inOut）
   0.70–1.15  其余段落 opacity 1→0.4（power2.out）
   1.30–1.60  关键句 scale 1→1.03 + y 0→-2（power2.out，origin left center） */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power2InOut = (x: number) => (x < 0.5 ? 4 * x ** 3 : 1 - Math.pow(-2 * x + 2, 3) / 2);

// —— 演示语境（不属于动效）：一段引用文字。白底 + 黑字 + 灰阶，零风格化 ——
const CSS = `
.quote-card {
  position: absolute;
  left: 50%;
  top: 46%;
  transform: translate(-50%, -50%);
  width: 640px;
  padding: 34px 42px 30px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  color: #1d1d1f;
}
.quote-card .doc-head {
  font-size: 13px;
  letter-spacing: 3px;
  color: #8a8a8a;
  border-bottom: 1px solid #ececec;
  padding-bottom: 10px;
  margin-bottom: 18px;
}
.quote-line {
  font-size: 21px;
  line-height: 1.9;
  font-weight: 500;
}
/* —— 动效本体 —— 荧光色块（语义色，属于动效） */
.quote-line .hl-wrap {
  position: relative;
  display: inline-block;
  font-weight: 700;
}
.quote-line .hl-block {
  position: absolute;
  left: -6px;
  right: -8px;
  top: 2px;
  bottom: 0;
  background: #FFE949;
  opacity: 0.6;
  mix-blend-mode: multiply;         /* 命门：色块不许盖字 */
  border-radius: 12px 5px 10px 4px / 7px 12px 5px 10px;  /* 不规则圆角模拟笔触 */
  transform-origin: left center;
}
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


/* slug-specific portrait: native 920px reading block; highlight geometry follows this same block. */
.quote-card { left:80px!important; right:auto!important; bottom:auto!important; top:300px!important; width:920px!important; min-height:1200px!important; transform:none!important; padding:58px!important; border-radius:42px!important; }
.quote-card .doc-head { position:static!important; font-size:30px!important; line-height:1.4!important; letter-spacing:3px!important; padding-bottom:28px!important; margin-bottom:42px!important; }
.quote-line { font-size:48px!important; line-height:1.55!important; letter-spacing:-1px!important; overflow-wrap:anywhere!important; }
.quote-line.key { margin:62px 0!important; font-size:60px!important; line-height:1.28!important; }
.quote-line .hl-wrap { display:block!important; width:100%!important; left:auto!important; right:auto!important; top:auto!important; bottom:auto!important; transform:none!important; font-size:inherit!important; line-height:inherit!important; }
.quote-line .hl-block { left:-14px!important; right:-14px!important; top:4px!important; bottom:0!important; border-radius:22px 10px 24px 12px / 14px 24px 12px 18px!important; }

`;

export default function HighlighterSweep(_props: { hostSrc?: string }) {
  void _props;
  const t = useCurrentFrame() / FPS;

  // 荧光笔从左到右扫过关键句；同帧其余文字压暗——视线被押着走
  const sweepX = tw(t, CONFIG.startDelay, CONFIG.sweep, power2InOut);
  const dimOpacity = lerp(1, CONFIG.dimTo, tw(t, CONFIG.startDelay, 0.45, power2Out));
  // 扫完：整句轻微放大浮起，强调落定
  const liftP = tw(t, CONFIG.startDelay + CONFIG.sweep, 0.3, power2Out);
  const keyScale = lerp(1, CONFIG.liftScale, liftP);
  const keyY = lerp(0, -2, liftP);

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="quote-card">
        <div className="doc-head">《2024 年度宏观经济报告》 · 第 42 页</div>
        <div className="quote-line dim" style={{ opacity: dimOpacity }}>过去三年，居民部门的储蓄率持续攀升，</div>
        <div className="quote-line dim" style={{ opacity: dimOpacity }}>消费意愿始终徘徊在低位。报告指出，</div>
        <div className="quote-line key" style={{
          transform: `translateY(${keyY}px) scale(${keyScale})`,
          transformOrigin: "left center",
        }}>
          <span className="hl-wrap">
            <span className="hl-block" style={{ transform: `scaleX(${sweepX})` }} />
            真正拖住消费的不是没钱，而是对未来的不确定感。
          </span>
        </div>
        <div className="quote-line dim" style={{ opacity: dimOpacity }}>这一判断与多家机构的调研结论一致，</div>
        <div className="quote-line dim" style={{ opacity: dimOpacity }}>政策端的回应也在陆续落地。</div>
      </div>
    </AbsoluteFill>
  );
}
