import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";

export const meta = { width: 1080, height: 1920, fps: 30, durationInFrames: 198 };

const FPS = meta.fps;
const CONFIG = {
  srcX: 180,
  srcYs: [520, 700, 880, 1060],
  hubX: 540,
  hubY: 1300,
  ctrl: [220, 780],
  titleIn: 0.1,
  nodeIn: 0.3,
  nodeStagger: 0.08,
  drawAt: 0.5,
  drawStagger: 0.15,
  drawDur: 0.5,
  hubIn: 0.8,
  pkFrom: 0.9,
  pkTo: 3.0,
  pkPhase: 0.13,
  convAt: 1.5,
  convDur: 1.5,
  shrinkKnee: 0.75,
  pulseAt: 2.85,
  eraseAt: 3.25,
  eraseDur: 0.4,
  capIn: 3.5,
  centerAt: 3.8,
  centerDur: 0.6,
  exitAt: 5.8,
  end: 6.2,
};

const clamp01 = (x: number) => Math.max(0, Math.min(1, x));
const tw = (t: number, t0: number, d: number, ease: (x: number) => number) =>
  ease(clamp01((t - t0) / d));
const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
const linear = (x: number) => x;
const power1Out = (x: number) => 1 - Math.pow(1 - x, 2);
const power2Out = (x: number) => 1 - Math.pow(1 - x, 3);
const power3Out = (x: number) => 1 - Math.pow(1 - x, 4);
const power2In = (x: number) => x * x * x;
const power2InOut = (x: number) => (x < 0.5 ? 4 * x ** 3 : 1 - Math.pow(-2 * x + 2, 3) / 2);
const backOut = (s = 1.70158) => (x: number) => {
  const u = x - 1;
  return 1 + (s + 1) * u * u * u + s * u * u;
};

type Pt = { x: number; y: number };
type Curve = { d: string; len: number; at: (L: number) => Pt };
const cubic = (p0: number, p1: number, p2: number, p3: number, u: number) => {
  const v = 1 - u;
  return v * v * v * p0 + 3 * v * v * u * p1 + 3 * v * u * u * p2 + u * u * u * p3;
};
function buildCurve(P: [Pt, Pt, Pt, Pt], N = 200): Curve {
  const pts: Pt[] = [];
  const cum: number[] = [0];
  for (let k = 0; k <= N; k++) {
    const u = k / N;
    pts.push({
      x: cubic(P[0].x, P[1].x, P[2].x, P[3].x, u),
      y: cubic(P[0].y, P[1].y, P[2].y, P[3].y, u),
    });
    if (k) cum.push(cum[k - 1] + Math.hypot(pts[k].x - pts[k - 1].x, pts[k].y - pts[k - 1].y));
  }
  const len = cum[N];
  const at = (L: number): Pt => {
    const q = Math.max(0, Math.min(len, L));
    let lo = 0;
    let hi = N;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (cum[mid] <= q) lo = mid;
      else hi = mid;
    }
    const seg = cum[hi] - cum[lo] || 1;
    const f = (q - cum[lo]) / seg;
    return { x: lerp(pts[lo].x, pts[hi].x, f), y: lerp(pts[lo].y, pts[hi].y, f) };
  };
  return {
    d: `M ${P[0].x},${P[0].y} C ${P[1].x},${P[1].y} ${P[2].x},${P[2].y} ${P[3].x},${P[3].y}`,
    len,
    at,
  };
}
const ysFor = (n: number) =>
  n === CONFIG.srcYs.length
    ? CONFIG.srcYs
    : n <= 1
      ? [CONFIG.hubY]
      : Array.from({ length: n }, (_, i) => 520 + (i * 540) / (n - 1));

const CSS = `
* { margin: 0; padding: 0; box-sizing: border-box; }
.scv-ttl { position: absolute; left: 80px; right: 80px; top: 110px; font-size: 62px; line-height: 1.12; font-weight: 900; color: #1d1d1f; }
.scv-svg { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; }
.scv-path { fill: none; stroke: #c9c2b5; stroke-width: 12; stroke-linecap: round; }
.scv-node rect { fill: #fffaf0; stroke: #151515; stroke-width: 5; }
.scv-node text { font-size: 36px; font-weight: 900; fill: #1d1d1f; text-anchor: middle; }
.scv-pk { fill: #e85332; }
.scv-hub rect { fill: #111111; }
.scv-hub text { font-size: 66px; font-weight: 950; fill: #ffffff; text-anchor: middle; }
.scv-cap { font-size: 46px; font-weight: 850; fill: #1d1d1f; text-anchor: middle; }
`;

type Props = {
  title?: string;
  sources?: string[];
  hub?: string;
  caption?: string;
};

export default function SourceConverge({
  title = "四个平台的数据，怎么汇成一张表",
  sources = ["抖音", "小红书", "B 站", "公众号"],
  hub = "一张表",
  caption = "每天 8 点自动更新",
}: Props) {
  const t = useCurrentFrame() / FPS;
  const ys = ysFor(sources.length);
  const curves = ys.map((y) => buildCurve([
    { x: CONFIG.srcX, y },
    { x: CONFIG.ctrl[0], y },
    { x: CONFIG.ctrl[1], y: CONFIG.hubY },
    { x: CONFIG.hubX, y: CONFIG.hubY },
  ]));

  const conv = tw(t, CONFIG.convAt, CONFIG.convDur, power2InOut);
  const pk = tw(t, CONFIG.pkFrom, CONFIG.pkTo - CONFIG.pkFrom, linear);
  const pkOn = tw(t, CONFIG.pkFrom, 0.3, power1Out) - tw(t, CONFIG.pkTo - 0.2, 0.2, power1Out);
  const erase = tw(t, CONFIG.eraseAt, CONFIG.eraseDur, power2Out);
  const size = Math.max(0, conv < CONFIG.shrinkKnee ? lerp(1, 0.34, conv / CONFIG.shrinkKnee) : lerp(0.34, 0, (conv - CONFIG.shrinkKnee) / (1 - CONFIG.shrinkKnee)));
  const hubIn = tw(t, CONFIG.hubIn, 0.4, power3Out);
  let hs = lerp(0.7, 1, hubIn);
  if (t >= CONFIG.pulseAt) {
    hs = t < CONFIG.pulseAt + 0.25
      ? lerp(1, 1.12, tw(t, CONFIG.pulseAt, 0.25, backOut(2)))
      : lerp(1.12, 1, tw(t, CONFIG.pulseAt + 0.25, 0.25, power2Out));
  }
  const cx = lerp(CONFIG.hubX, 540, tw(t, CONFIG.centerAt, CONFIG.centerDur, power2InOut));
  const ttlIn = tw(t, CONFIG.titleIn, 0.4, power3Out);
  const capIn = tw(t, CONFIG.capIn, 0.4, power1Out);
  const exitK = 1 - tw(t, CONFIG.exitAt, CONFIG.end - CONFIG.exitAt, power2In);

  return (
    <AbsoluteFill style={{ background: "#ffffff", color: "#1d1d1f", overflow: "hidden", fontFamily: '"PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif' }}>
      <style>{CSS}</style>
      <div className="scv-ttl" style={{ opacity: ttlIn * exitK, transform: `translateY(${lerp(34, 0, ttlIn)}px)` }}>{title}</div>
      <svg className="scv-svg" viewBox="0 0 1080 1920">
        {curves.map((c, i) => {
          const draw = tw(t, CONFIG.drawAt + i * CONFIG.drawStagger, CONFIG.drawDur, power2Out);
          return <path key={`p${i}`} className="scv-path" d={c.d} style={{ strokeDasharray: c.len, strokeDashoffset: c.len * (1 - draw) - erase * c.len }} />;
        })}
        {curves.map((c, i) => {
          const cyc = (pk * 2 + i * CONFIG.pkPhase) % 1;
          const p = c.at(cyc * c.len);
          return <circle key={`k${i}`} className="scv-pk" r={12} cx={p.x} cy={p.y} opacity={pkOn * (1 - Math.abs(cyc - 0.5) * 0.6)} />;
        })}
        {curves.map((c, i) => {
          const p = c.at(conv * c.len);
          const nodeIn = tw(t, CONFIG.nodeIn + i * CONFIG.nodeStagger, 0.3, power1Out);
          return (
            <g key={`n${i}`} className="scv-node" transform={`translate(${p.x} ${p.y}) scale(${size})`} opacity={nodeIn}>
              <rect x={-100} y={-42} width={200} height={84} rx={42} />
              <text y={13}>{sources[i]}</text>
            </g>
          );
        })}
        <g className="scv-hub" transform={`translate(${cx} ${CONFIG.hubY}) scale(${hs})`} opacity={hubIn * exitK}>
          <rect x={-170} y={-80} width={340} height={160} rx={56} />
          <text y={19}>{hub}</text>
        </g>
        <text className="scv-cap" x={cx} y={1580} opacity={capIn * exitK}>{caption}</text>
      </svg>
    </AbsoluteFill>
  );
}
