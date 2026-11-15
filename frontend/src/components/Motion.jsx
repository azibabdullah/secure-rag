import React, { useEffect, useRef, useState } from "react";

// Numbers roll up to their new value with an ease-out curve.
export function CountUp({ value, pad = 2, duration = 1100, motion = true }) {
  const [shown, setShown] = useState(motion ? 0 : value);
  const from = useRef(0);
  useEffect(() => {
    if (!motion) { setShown(value); from.current = value; return; }
    const start = performance.now(), a = from.current, b = value;
    let id;
    const tick = (t) => {
      const k = Math.min(1, (t - start) / duration);
      const e = 1 - Math.pow(1 - k, 4);
      setShown(Math.round(a + (b - a) * e));
      if (k < 1) id = requestAnimationFrame(tick);
      else from.current = b;
    };
    id = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(id);
  }, [value, motion]);
  return <>{shown.toString().padStart(pad, "0")}</>;
}

// Headline words fade up out of a soft blur, one after another.
export function RevealText({ text, className = "", delay = 0 }) {
  return (
    <span className={`reveal ${className}`} aria-label={text}>
      {text.split(" ").map((word, i) => (
        <span key={i} aria-hidden="true" style={{ "--d": `${delay + i * 90}ms` }}>
          {word}
          {" "}
        </span>
      ))}
    </span>
  );
}

// One document-level listener feeds the cursor position to whatever glass
// surface is under the pointer, so each panel can paint its own spotlight.
export function useSpotlight(enabled) {
  useEffect(() => {
    if (!enabled) return;
    let current = null, raf = 0, last = null;
    const apply = () => {
      raf = 0;
      if (!last) return;
      const el = last.target.closest?.(".panel, .spot");
      if (current && current !== el) current.classList.remove("lit");
      current = el;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${last.clientX - r.left}px`);
      el.style.setProperty("--my", `${last.clientY - r.top}px`);
      el.classList.add("lit");
    };
    const move = (e) => { last = e; if (!raf) raf = requestAnimationFrame(apply); };
    const leave = () => { current?.classList.remove("lit"); current = null; };
    document.addEventListener("pointermove", move, { passive: true });
    document.addEventListener("pointerleave", leave);
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerleave", leave);
      leave();
    };
  }, [enabled]);
}

// Material-style ink ripple from the click point on buttons that opt in.
export function useRipple(enabled) {
  useEffect(() => {
    if (!enabled) return;
    const down = (e) => {
      const el = e.target.closest?.(".ripple");
      if (!el || el.disabled) return;
      const r = el.getBoundingClientRect();
      const size = Math.max(r.width, r.height) * 2.2;
      const ink = document.createElement("span");
      ink.className = "ink";
      ink.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
      el.appendChild(ink);
      ink.addEventListener("animationend", () => ink.remove());
    };
    document.addEventListener("pointerdown", down);
    return () => document.removeEventListener("pointerdown", down);
  }, [enabled]);
}
