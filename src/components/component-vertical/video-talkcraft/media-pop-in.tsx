import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

// media-pop-in · 素材弹入堆叠 —— 自包含 Remotion 源码（与 demos/media-pop-in/index.html 同画面）
// 时长说明：demo 收尾是无限 idle 呼吸；本文件取有限动画结束点（1.05s）+ 2s idle 展示。
export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 92 };

const FPS = meta.fps;

// —— 可摘走的核心动画：白边素材 back.out 弹入 + 错峰堆叠 ——
const CONFIG = {
  popDur: 0.3,        // 单张弹入时长 s：0.25~0.35，>0.4 拖节奏
  overshoot: 1.7,     // back.out 回弹力度：越大"拍"得越重
  fromScale: 0.8,     // 起始缩放：0.8 → 1 是"拍上来"的标准行程
  stagger: 0.15,      // 张与张间隔 s：100~150ms 才有甩证据的密度感
  startDelay: 0.45,   // 等主持人说完半句再开甩
  breathe: 0.008,     // 落位后整组呼吸幅度：0 = 完全静止
  preTilt: 6,         // 入场时比落位再多歪的度数：落位收正才有"拍"的手感
};

/* 时间表（demo 秒）
   0.45/0.60/0.75  三张依次弹入：opacity 前半程（0.15s power1.out）+
                   scale 0.8→1 & 旋转收正（0.3s back.out(1.7)）
   1.25 起         整组 ±0.008 呼吸（1.6s sine.inOut yoyo 无限） */

// —— 缓动与 tween helper（对照 GSAP 名字）——
const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);
const sineInOut = (x: number) => -(Math.cos(Math.PI * x) - 1) / 2;
const backOut = (s = 1.70158) => (x: number) => {
  const u = x - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};

const CSS = `
.evidence { position: absolute; left: 46%; right: 0; top: 0; bottom: 0; }
.shot {
  position: absolute;
  border: 8px solid #fff;
  border-radius: 4px;
  box-shadow: 0 12px 26px rgba(0, 0, 0, .16);
  overflow: hidden;
}
.shot-browser { width: 300px; height: 200px; left: 40px; top: 46px; background: #fafafa; }
.shot-browser .bar { height: 26px; background: #ececef; display: flex; align-items: center; gap: 5px; padding: 0 8px; }
.shot-browser .bar i { width: 8px; height: 8px; border-radius: 50%; background: #c8c8cc; }
.shot-browser .h { height: 14px; background: #8a8a8a; margin: 14px 14px 8px; border-radius: 3px; width: 70%; }
.shot-browser .l { height: 8px; background: #d2d2d7; margin: 7px 14px; border-radius: 3px; }
.shot-browser .l.s { width: 55%; }
.shot-chat { width: 240px; height: 210px; left: 190px; top: 130px; background: #f5f5f7; }
.shot-chat .msg { max-width: 72%; height: 30px; margin: 12px; border-radius: 10px; background: #ffffff; border: 1px solid #e0e0e0; }
.shot-chat .msg.me { width: 58%; margin-left: auto; background: #ececef; border-color: #e0e0e0; }
.shot-pay { width: 250px; height: 170px; left: 90px; top: 270px; background: #fff; }
.shot-pay .tick { width: 40px; height: 40px; margin: 20px auto 10px; border-radius: 50%; background: #ececef; }
.shot-pay .amt { height: 20px; width: 52%; margin: 0 auto 10px; border-radius: 4px; background: #8a8a8a; }
.shot-pay .sub { height: 8px; width: 34%; margin: 0 auto; border-radius: 4px; background: #d2d2d7; }
`;
const PORTRAIT_CSS = `

/* Native portrait adaptation: keep source timing/CONFIG, reflow stage to 1080x1920. */
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

/* native-portrait manual layout: media-pop-in */
.evidence { left: 0 !important; right: 0 !important; top: 0 !important; bottom: 0 !important; }
.shot { border-width: 14px !important; border-radius: 18px !important; box-shadow: 0 34px 85px rgba(0,0,0,.20) !important; }
.shot-browser { left: 95px !important; top: 270px !important; width: 680px !important; height: 440px !important; }
.shot-browser .bar { height: 56px !important; gap: 12px !important; padding: 0 18px !important; }
.shot-browser .bar i { width: 16px !important; height: 16px !important; }
.shot-browser .h { height: 30px !important; margin: 34px 34px 20px !important; }
.shot-browser .l { height: 18px !important; margin: 18px 34px !important; }
.shot-chat { left: 280px !important; top: 690px !important; width: 640px !important; height: 520px !important; }
.shot-chat .msg { height: 68px !important; margin: 28px !important; border-radius: 22px !important; }
.shot-pay { left: 130px !important; top: 1120px !important; width: 640px !important; height: 430px !important; }
.shot-pay .tick { width: 92px !important; height: 92px !important; margin: 56px auto 30px !important; }
.shot-pay .amt { height: 46px !important; margin-bottom: 24px !important; }
.shot-pay .sub { height: 20px !important; }
`;

// 三张假截图的落位旋转角（data-rot）
const ROTS = [-7, 5, -4];

export default function MediaPopIn() {
  const t = useCurrentFrame() / FPS;

  // 单张弹入：透明度前半程完成，缩放/旋转带 back 回弹整程
  const shotStyle = (i: number): React.CSSProperties => {
    const at = CONFIG.startDelay + i * CONFIG.stagger;
    const op = tw(t, at, CONFIG.popDur * 0.5, power1Out);
    const p = tw(t, at, CONFIG.popDur, backOut(CONFIG.overshoot));
    return {
      opacity: op,
      transform: `rotate(${lerp(ROTS[i] - CONFIG.preTilt, ROTS[i], p)}deg) scale(${lerp(CONFIG.fromScale, 1, p)})`,
      transformOrigin: "50% 60%",
    };
  };

  // 全部落位后整组轻微呼吸（sine.inOut yoyo 无限）
  const settled = CONFIG.startDelay + 2 * CONFIG.stagger + CONFIG.popDur;
  const b0 = settled + 0.2;
  let groupScale = 1;
  if (t >= b0) {
    const cyc = (t - b0) / 1.6;
    const k = Math.floor(cyc);
    const p = cyc - k;
    const pp = k % 2 === 1 ? 1 - p : p;
    groupScale = 1 + CONFIG.breathe * sineInOut(pp);
  }

  return (
    <AbsoluteFill style={{
      background: "#ffffff", color: "#1d1d1f", overflow: "hidden",
      fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif',
    }}>
      <style>{CSS + PORTRAIT_CSS}</style>
      <div className="evidence" style={{ transform: `scale(${groupScale})`, transformOrigin: "50% 50%" }}>
        <div className="shot shot-browser" style={shotStyle(0)}>
          <div className="bar"><i /><i /><i /></div>
          <div className="h" /><div className="l" /><div className="l" /><div className="l s" />
        </div>
        <div className="shot shot-chat" style={shotStyle(1)}>
          <div className="msg" />
          <div className="msg me" />
          <div className="msg" />
        </div>
        <div className="shot shot-pay" style={shotStyle(2)}>
          <div className="tick" />
          <div className="amt" />
          <div className="sub" />
        </div>
      </div>
    </AbsoluteFill>
  );
}
