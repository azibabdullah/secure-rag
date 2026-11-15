import React, { useEffect, useRef } from "react";

// Animated deep-space backdrop: three parallax layers of twinkling stars,
// a few four-point "sparkle" stars, and the occasional shooting star.
// Draws to one fixed <canvas> behind the app. Pauses when the window is
// hidden and renders a single still frame when motion is turned off.
export default function Starfield({ motion = true, dark = true }) {
  const ref = useRef(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let w = 0, h = 0, dpr = 1, frame = 0, last = performance.now();
    let stars = [], sparkles = [], meteors = [];
    const pointer = { x: 0, y: 0, tx: 0, ty: 0 };
    const rand = (a, b) => a + Math.random() * (b - a);
    const tint = dark ? [255, 255, 255] : [40, 52, 82];

    function seed() {
      const area = (w * h) / 1e6;
      const count = Math.round((dark ? 260 : 150) * Math.max(0.6, area));
      stars = Array.from({ length: count }, () => {
        const depth = Math.random() < 0.6 ? 0.25 : Math.random() < 0.75 ? 0.6 : 1;
        return {
          x: Math.random() * w, y: Math.random() * h, depth,
          r: rand(0.35, 0.9) * (0.6 + depth * 0.8),
          base: rand(0.25, 0.85), speed: rand(0.4, 1.6), phase: rand(0, Math.PI * 2),
          drift: rand(-0.012, 0.012),
          hue: Math.random() < 0.12 ? [196, 181, 253] : Math.random() < 0.08 ? [167, 139, 250] : null,
        };
      });
      sparkles = Array.from({ length: Math.max(3, Math.round(6 * area)) }, () => ({
        x: rand(0.08, 0.92) * w, y: rand(0.08, 0.92) * h,
        size: rand(3, 6.5), phase: rand(0, Math.PI * 2), speed: rand(0.35, 0.8), depth: 0.8,
      }));
    }
    function resize() {
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth; h = window.innerHeight;
      canvas.width = w * dpr; canvas.height = h * dpr;
      canvas.style.width = `${w}px`; canvas.style.height = `${h}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
      if (!motion) draw(0, 0);
    }
    function sparkle(x, y, size, alpha) {
      const [r, g, b] = tint;
      const glow = ctx.createRadialGradient(x, y, 0, x, y, size * 3);
      glow.addColorStop(0, `rgba(${r},${g},${b},${0.35 * alpha})`);
      glow.addColorStop(1, `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(x, y, size * 3, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = `rgba(${r},${g},${b},${0.9 * alpha})`;
      ctx.beginPath();
      ctx.moveTo(x, y - size * 1.6);
      ctx.quadraticCurveTo(x, y, x + size * 1.6, y);
      ctx.quadraticCurveTo(x, y, x, y + size * 1.6);
      ctx.quadraticCurveTo(x, y, x - size * 1.6, y);
      ctx.quadraticCurveTo(x, y, x, y - size * 1.6);
      ctx.fill();
    }
    function draw(t, dt) {
      ctx.clearRect(0, 0, w, h);
      pointer.x += (pointer.tx - pointer.x) * 0.04;
      pointer.y += (pointer.ty - pointer.y) * 0.04;
      const s = t / 1000;
      for (const st of stars) {
        st.y -= st.drift * dt * st.depth;
        st.x += st.drift * 0.6 * dt * st.depth;
        if (st.y < -4) st.y = h + 4; if (st.y > h + 4) st.y = -4;
        if (st.x < -4) st.x = w + 4; if (st.x > w + 4) st.x = -4;
        const tw = 0.55 + 0.45 * Math.sin(s * st.speed + st.phase);
        const a = st.base * tw * (dark ? 1 : 0.55);
        const [r, g, b] = st.hue && dark ? st.hue : tint;
        const px = st.x + pointer.x * 14 * st.depth, py = st.y + pointer.y * 14 * st.depth;
        ctx.fillStyle = `rgba(${r},${g},${b},${a})`;
        ctx.beginPath(); ctx.arc(px, py, st.r, 0, Math.PI * 2); ctx.fill();
      }
      for (const sp of sparkles) {
        const pulse = Math.max(0, Math.sin(s * sp.speed + sp.phase));
        const a = (0.25 + 0.75 * pulse * pulse) * (dark ? 1 : 0.4);
        sparkle(sp.x + pointer.x * 18, sp.y + pointer.y * 18, sp.size * (0.75 + pulse * 0.35), a);
      }
      if (motion && dark && Math.random() < dt / 5200 && meteors.length < 2) {
        meteors.push({ x: rand(0.15, 1) * w, y: rand(-0.05, 0.4) * h, vx: -rand(0.55, 0.9), vy: rand(0.22, 0.38), life: 0, max: rand(900, 1500) });
      }
      meteors = meteors.filter((m) => m.life < m.max);
      for (const m of meteors) {
        m.life += dt; m.x += m.vx * dt; m.y += m.vy * dt;
        const k = m.life / m.max, a = Math.sin(Math.PI * k);
        const tail = 110;
        const grad = ctx.createLinearGradient(m.x, m.y, m.x - m.vx * tail, m.y - m.vy * tail);
        grad.addColorStop(0, `rgba(255,255,255,${0.85 * a})`);
        grad.addColorStop(1, "rgba(169,233,238,0)");
        ctx.strokeStyle = grad; ctx.lineWidth = 1.2; ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(m.x, m.y); ctx.lineTo(m.x - m.vx * tail, m.y - m.vy * tail); ctx.stroke();
      }
    }
    function loop(t) {
      const dt = Math.min(64, t - last); last = t;
      draw(t, dt);
      frame = requestAnimationFrame(loop);
    }
    const move = (e) => {
      pointer.tx = (e.clientX / w - 0.5) * -2;
      pointer.ty = (e.clientY / h - 0.5) * -2;
    };
    const visibility = () => {
      cancelAnimationFrame(frame);
      if (!document.hidden && motion) { last = performance.now(); frame = requestAnimationFrame(loop); }
    };
    resize();
    window.addEventListener("resize", resize);
    if (motion) {
      window.addEventListener("pointermove", move, { passive: true });
      document.addEventListener("visibilitychange", visibility);
      frame = requestAnimationFrame(loop);
    } else draw(0, 0);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("resize", resize);
      window.removeEventListener("pointermove", move);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [motion, dark]);
  return (
    <div className="cosmos" aria-hidden="true">
      <div className="nebula n1" />
      <div className="nebula n2" />
      <div className="nebula n3" />
      <canvas ref={ref} />
      <div className="vignette" />
    </div>
  );
}
