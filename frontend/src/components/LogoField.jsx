import React, { useEffect, useRef } from "react";
import { BRAND } from "./Logo";
import { STRIPES } from "./logoData";

// One canvas carries the start-up scene:
//   boot     the striped logo assembles out of a dot matrix, a lens sweeps
//            across it and turns it from white to purple, and a ring around
//            it fills as the security models load
//   welcome  the dot logo dissolves outward while the crisp logo draws itself
//            in on top (see AnimatedMark); a slowly turning cloud of points
//            and drifting stars surround it
//   warp     the cloud and stars burst outward past the camera
// With motion off it paints a single still frame for each phase.

const TAU = Math.PI * 2;
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = (a, b, v) => { const t = clamp((v - a) / (b - a)); return t * t * (3 - 2 * t); };
const outExpo = (t) => (t >= 1 ? 1 : t <= 0 ? 0 : 1 - Math.pow(2, -10 * t));
const inOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const STOPS = [[0, hex(BRAND[0])], [0.38, hex(BRAND[1])], [0.72, hex(BRAND[2])], [1, hex(BRAND[3])]];
const SHADES = 20;
const PALETTE = Array.from({ length: SHADES }, (_, i) => {
  const t = i / (SHADES - 1);
  let k = 0;
  while (k < STOPS.length - 2 && t > STOPS[k + 1][0]) k++;
  const [t0, c0] = STOPS[k], [t1, c1] = STOPS[k + 1];
  const u = clamp((t - t0) / (t1 - t0));
  return `rgb(${c0.map((v, j) => Math.round(lerp(v, c1[j], u))).join(",")})`;
});
export const WARP_MS = 1700;
const GRID = 0.0125;                       // dot pitch, in logo units (the logo spans -1..1)
const RING = { r: 1.1, arcs: [[-52, 28], [68, 148], [188, 268]] };

// Rasterise the logo stripes and the loading ring, then keep one point per
// grid cell that lands on ink: the regular grid gives the dot-matrix look.
function sampleLogo() {
  const S = 3, PAD = 24, box = 200 + PAD * 2, size = box * S;
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d", { willReadFrequently: true });
  const step = GRID * 100 * S;
  const arc = (r, a0, a1) => { const p = new Path2D(); p.arc(100, 100, r, (a0 - 90) * Math.PI / 180, (a1 - 90) * Math.PI / 180); return p; };
  const layers = [
    ["mark", () => STRIPES.forEach((s) => g.fill(new Path2D(s.d)))],
    ["ring", () => { g.lineWidth = 4.2; g.lineCap = "round"; RING.arcs.forEach(([a, b]) => g.stroke(arc(RING.r * 100, a, b))); }],
  ];
  const points = [];
  for (const [layer, draw] of layers) {
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, size, size);
    g.setTransform(S, 0, 0, S, PAD * S, PAD * S);
    g.strokeStyle = g.fillStyle = "#fff";
    draw();
    const data = g.getImageData(0, 0, size, size).data;
    for (let py = step / 2; py < size; py += step) {
      for (let px = step / 2; px < size; px += step) {
        if (data[(Math.round(py) * size + Math.round(px)) * 4 + 3] < 120) continue;
        const x = (px / S - PAD) / 100 - 1, y = (py / S - PAD) / 100 - 1;
        points.push({
          layer, x, y, z: layer === "ring" ? 0.08 : 0,
          shade: Math.round(clamp((x + y + 1.6) / 3.2) * (SHADES - 1)),
          ang: (Math.atan2(x, -y) + TAU) % TAU, rad: Math.hypot(x, y),
          sx: x * 2.8 + (Math.random() - 0.5) * 2.6, sy: y * 2.8 + (Math.random() - 0.5) * 2.6, sz: (Math.random() - 0.5) * 6,
          delay: Math.random() * 0.5 + (layer === "ring" ? 0.15 : 0),
        });
      }
    }
  }
  return points;
}

function makeCloud(n) {
  const golden = Math.PI * (3 - Math.sqrt(5));
  return Array.from({ length: n }, (_, i) => {
    const y = 1 - (i / (n - 1)) * 2, r = Math.sqrt(1 - y * y), a = golden * i, j = 1.32 + (Math.random() - 0.5) * 0.08;
    return { x: Math.cos(a) * r * j, y: y * j, z: Math.sin(a) * r * j, tw: Math.random() * TAU, big: Math.random() < 0.06 };
  });
}

function makeStars(n) {
  return Array.from({ length: n }, () => ({
    a: Math.random() * TAU, r: 1.6 + Math.pow(Math.random(), 0.7) * 8.5, z: -0.5 + Math.random() * 5,
    tw: Math.random() * TAU, s: 0.5 + Math.random() * 1.1, tint: Math.random() < 0.18 ? Math.floor(Math.random() * SHADES) : -1,
  }));
}

// Where the logo sits on the welcome screen; Splash places the crisp mark here too.
export const welcomeBox = (w, h) => ({ x: w * 0.665, y: h * 0.5, s: Math.min(h * 0.52, w * 0.37) });

export default function LogoField({ phase, progress = 0, motion = true, onWarpDone }) {
  const ref = useRef(null);
  const live = useRef({ phase, progress, motion, onWarpDone });
  live.current = { phase, progress, motion, onWarpDone };

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas.getContext("2d");
    const logo = sampleLogo(), cloud = makeCloud(1100), stars = makeStars(520);
    let w = 0, h = 0, dpr = 1, raf = 0, prev = performance.now();
    const born = prev;
    let welcomeAt = 0, warpAt = 0, warpDone = false, lastPhase = "", anchor = "boot";
    const cam = { cx: 0, cy: 0, R: 0, cloud: 0, set: false };

    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      if (!live.current.motion) draw(performance.now());
    }
    function target(ph) {
      if (ph === "boot") return { cx: w / 2, cy: h * 0.42, R: Math.min(w, h) * 0.18, cloud: 0 };
      const b = welcomeBox(w, h);
      return { cx: b.x, cy: b.y, R: b.s * 0.48, cloud: 1 };
    }

    function draw(now) {
      const { phase: ph, progress: prog, motion: mo } = live.current;
      const dt = Math.min(0.05, (now - prev) / 1000);
      prev = now;
      if (ph !== lastPhase) {
        if (ph === "welcome") welcomeAt = now;
        if (ph === "warp") { warpAt = now; warpDone = false; if (!welcomeAt) welcomeAt = now - 5000; } else anchor = ph;
        lastPhase = ph;
      }
      const t = (now - born) / 1000;
      const tb = mo ? t : 99;                                   // boot clock
      const tw = anchor === "boot" ? 0 : mo ? (now - welcomeAt) / 1000 : 99;   // welcome clock
      const wt = ph === "warp" ? (mo ? clamp((now - warpAt) / WARP_MS) : 1) : 0;
      const goal = target(anchor);
      const ease = !cam.set || !mo ? 1 : 1 - Math.exp(-dt * 3.4);
      cam.cx = lerp(cam.cx, goal.cx, ease); cam.cy = lerp(cam.cy, goal.cy, ease); cam.R = lerp(cam.R, goal.R, ease);
      cam.cloud = lerp(cam.cloud, goal.cloud, !cam.set || !mo ? 1 : 1 - Math.exp(-dt * 1.8));
      cam.set = true;

      const F = 3.2, burst = wt * wt * wt;
      const sweep = clamp((tb - 1.05) / 0.95), band = lerp(-1.7, 1.7, inOut(sweep)), sweeping = sweep > 0 && sweep < 1;
      const dissolve = anchor === "boot" ? 0 : inOut(clamp(tw / 1.1));  // dots fly apart as the crisp mark draws in
      const fly = Math.pow(wt, 4) * 9;                       // when the welcome screen is skipped, the dot logo rushes the camera
      const logoAlpha = (1 - dissolve) * (1 - smooth(0.32, 0.78, wt));

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      ctx.globalCompositeOperation = "lighter";

      // ---- stars: drift outward from the logo, streak during the warp
      const starAlpha = (anchor !== "boot" ? 1 : 0.45 * smooth(0.2, 1.6, tb)) * (1 - smooth(0.82, 1, wt));
      if (starAlpha > 0.01) {
        ctx.lineCap = "round";
        for (const s of stars) {
          if (mo && ph !== "warp") { s.r += dt * 0.035 * (0.4 + s.r * 0.25); if (s.r > 10.5) s.r = 1.6; }
          const per = F / (F + Math.max(-2.6, s.z - burst * 6)), rr = s.r * (1 + burst * 13);
          const x = cam.cx + Math.cos(s.a) * rr * cam.R * per, y = cam.cy + Math.sin(s.a) * rr * cam.R * per * 0.92;
          if (x < -40 || x > w + 40 || y < -40 || y > h + 40) continue;
          const twinkle = mo ? 0.55 + 0.45 * Math.sin(t * 1.3 + s.tw) : 0.8;
          ctx.globalAlpha = starAlpha * twinkle * clamp(0.25 + per * 0.6) * smooth(1.5, 2.6, s.r);
          ctx.fillStyle = ctx.strokeStyle = s.tint < 0 ? "#fff" : PALETTE[s.tint];
          if (wt > 0.04) {
            const back = 1 + Math.pow(Math.max(0, wt - 0.05), 3) * 13;
            ctx.lineWidth = s.s * (1 + wt);
            ctx.beginPath();
            ctx.moveTo(cam.cx + Math.cos(s.a) * s.r * back * cam.R * per, cam.cy + Math.sin(s.a) * s.r * back * cam.R * per * 0.92);
            ctx.lineTo(x, y); ctx.stroke();
          } else {
            const size = s.s * (0.7 + per * 0.6);
            ctx.fillRect(x - size / 2, y - size / 2, size, size);
          }
        }
      }

      // ---- point cloud around the logo on the welcome screen (back half first)
      const cyaw = mo ? t * 0.16 : 0.6, tilt = 0.38;
      const cc = Math.cos(cyaw), cs = Math.sin(cyaw), tc = Math.cos(tilt), ts = Math.sin(tilt);
      const cloudAlpha = cam.cloud * (1 - smooth(0.7, 1, wt));
      const cloudPass = (front) => {
        if (cloudAlpha < 0.01) return;
        const grow = 1 + burst * 20;
        for (const p of cloud) {
          const x1 = p.x * cc + p.z * cs, z1 = -p.x * cs + p.z * cc;
          const y2 = p.y * tc - z1 * ts, z2 = p.y * ts + z1 * tc;
          if (front !== z2 < 0) continue;
          const per = F / (F + z2 * (1 - burst));
          const x = cam.cx + x1 * grow * cam.R * per, y = cam.cy + y2 * grow * cam.R * per;
          const size = (p.big ? 3.2 : 1.7) * per * (1 + burst * 2);
          ctx.globalAlpha = cloudAlpha * (front ? 0.85 : 0.3) * (mo ? 0.7 + 0.3 * Math.sin(t * 0.9 + p.tw) : 0.85);
          ctx.fillStyle = p.big ? PALETTE[Math.floor(((p.y + 1.32) / 2.64) * (SHADES - 1))] : "#e4ddff";
          if (wt > 0.04) {
            const back = 1 + Math.pow(Math.max(0, wt - 0.05), 3) * 20;
            ctx.strokeStyle = ctx.fillStyle; ctx.lineWidth = size;
            ctx.beginPath(); ctx.moveTo(cam.cx + x1 * back * cam.R * per, cam.cy + y2 * back * cam.R * per); ctx.lineTo(x, y); ctx.stroke();
          } else ctx.fillRect(x - size / 2, y - size / 2, size, size);
        }
      };
      cloudPass(false);

      // ---- the dot-matrix logo and its loading ring
      if (logoAlpha > 0.01) {
        const dot = Math.max(1.1, GRID * cam.R * 0.62);
        const ringSpin = mo && anchor !== "boot" ? tw * 0.6 : 0;
        for (const p of logo) {
          const a = outExpo((tb - 0.12 - p.delay) / 1.15);
          if (a <= 0.001) continue;
          let x = p.x, y = p.y, z = p.z;
          if (p.layer === "ring") {
            if (anchor === "boot" && p.ang / TAU > prog + 0.002) continue;
            const ang = p.ang + ringSpin;
            x = Math.sin(ang) * p.rad; y = -Math.cos(ang) * p.rad;
          }
          if (a < 1) { x = lerp(p.sx, x, a); y = lerp(p.sy, y, a); z = lerp(p.sz, z, a); }
          if (dissolve > 0) { x = lerp(x, p.sx * 0.9, dissolve); y = lerp(y, p.sy * 0.9, dissolve); z = lerp(z, p.sz * 0.4, dissolve); }
          let lens = 0;
          if (sweeping) {
            const d = x - band;
            if (Math.abs(d) < 0.34) { lens = 1 - Math.abs(d) / 0.34; x += d * lens * 0.85; y += y * 0.12 * lens; }
          }
          const per = F / (F + z);
          const X = cam.cx + x * cam.R * per * (1 + fly), Y = cam.cy + y * cam.R * per * (1 + fly);
          const size = dot * per * (1 + lens * 0.9) * (1 + fly * 0.5);
          const coloured = sweep >= 1 || p.x < band;
          const alpha = logoAlpha * a * (p.layer === "ring" ? 0.85 : 1);
          if (lens > 0.02) {                               // colour split inside the lens band
            const off = 3.5 * lens;
            ctx.globalAlpha = alpha * 0.8;
            ctx.fillStyle = "#e879f9"; ctx.fillRect(X - size / 2 - off, Y - size / 2, size, size);
            ctx.fillStyle = "#818cf8"; ctx.fillRect(X - size / 2 + off, Y - size / 2, size, size);
          }
          ctx.fillStyle = coloured ? PALETTE[p.shade] : "#f4f2ff";
          ctx.globalAlpha = alpha * 0.045;
          ctx.fillRect(X - size * 2, Y - size * 2, size * 4, size * 4);
          ctx.globalAlpha = alpha;
          ctx.fillRect(X - size / 2, Y - size / 2, size, size);
        }
      }
      cloudPass(true);

      // ---- violet flash as the logo passes the camera
      if (wt > 0.25 && wt < 0.85) {
        const k = Math.sin(Math.PI * (wt - 0.25) / 0.6);
        const g = ctx.createRadialGradient(cam.cx, cam.cy, 0, cam.cx, cam.cy, Math.max(w, h) * 0.9);
        g.addColorStop(0, `rgba(214,200,255,${0.5 * k})`); g.addColorStop(0.35, `rgba(139,92,246,${0.18 * k})`); g.addColorStop(1, "rgba(0,0,0,0)");
        ctx.globalAlpha = 1; ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = "source-over";
      if (ph === "warp" && wt >= 1 && !warpDone) { warpDone = true; live.current.onWarpDone?.(); }
    }

    function loop(now) {
      draw(now);
      if (live.current.motion && !document.hidden) raf = requestAnimationFrame(loop);
      else raf = 0;
    }
    const wake = () => { if (!raf) { prev = performance.now(); raf = requestAnimationFrame(loop); } };
    canvas.__redraw = wake;
    resize();
    wake();
    window.addEventListener("resize", resize);
    document.addEventListener("visibilitychange", wake);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", wake);
    };
  }, []);

  useEffect(() => { ref.current?.__redraw?.(); }, [phase, progress, motion]);

  return <canvas ref={ref} className="logo-field" aria-hidden="true" />;
}
