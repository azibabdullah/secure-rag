import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { BookOpen, Check } from "lucide-react";
import LogoField, { welcomeBox } from "./LogoField";
import { AnimatedMark, LogoMark, Wordmark } from "./Logo";

const LINES = ["Ask your documents anything.", "Every word is screened first.", "Nothing leaves this computer."];
const BOOT_STEPS = [
  [0, "Unlocking the encrypted library"],
  [0.3, "Loading PromptGuard"],
  [0.55, "Loading DocumentGuard"],
  [0.8, "Connecting to the local model"],
];
const MARK_DELAY = 0.35;   // the crisp logo starts drawing as the dot logo dissolves
const WORD_DELAY = 1.45;   // then the name types out

// Start-up sequence in one continuous scene.
//   boot     the dot-matrix logo assembles while the guards load (LogoField)
//   welcome  the dots dissolve and the logo draws itself in, stripe by stripe,
//            on the right behind frosted glass, while "SecureRAG" types out
//            above the description; the logo then sways slowly in 3D
//   warp     the logo rushes the camera as the stars streak past
// `phase` is owned by App: "boot" | "welcome" | "warp".
export default function Splash({ phase, ready, status, motion, ollama, model, onOpen, onGuide, guideOpen, showAtStartup, setShowAtStartup, onWarpDone }) {
  const [progress, setProgress] = useState(0);
  const [skip, setSkip] = useState(false);
  const [box, setBox] = useState(() => welcomeBox(window.innerWidth, window.innerHeight));
  const started = useRef(performance.now());
  const primary = useRef();

  useLayoutEffect(() => {
    const place = () => setBox(welcomeBox(window.innerWidth, window.innerHeight));
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, []);

  // The bar moves on its own up to 88%, then waits for the real "ready" signal.
  useEffect(() => {
    if (phase !== "boot") { setProgress(1); return; }
    if (!motion) { setProgress(ready ? 1 : 0.5); return; }
    let raf;
    const tick = () => {
      const t = (performance.now() - started.current) / 1000;
      const auto = 0.88 * (1 - Math.exp(-t / 1.1));
      setProgress((p) => (ready ? Math.min(1, p + 0.035) : Math.max(p, auto)));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [phase, ready, motion]);

  // Any key or click during the reveal jumps to the finished screen.
  useEffect(() => {
    if (phase !== "welcome") return;
    const done = setTimeout(() => setSkip(true), 5200);
    const jump = (e) => { if (e.type === "keydown" && ["Tab", "Shift", "Control", "Alt", "Meta"].includes(e.key)) return; setSkip(true); };
    window.addEventListener("keydown", jump);
    window.addEventListener("pointerdown", jump);
    return () => { clearTimeout(done); window.removeEventListener("keydown", jump); window.removeEventListener("pointerdown", jump); };
  }, [phase]);
  useEffect(() => { if (phase === "welcome" && !guideOpen) primary.current?.focus({ preventScroll: true }); }, [phase, guideOpen, skip]);

  const step = [...BOOT_STEPS].reverse().find(([at]) => progress >= at)[1];
  const bootText = ready ? "Guards ready" : status && status !== "Loading security models" ? status : step;
  let word = 0;

  return (
    <div className={`splash phase-${phase} ${skip ? "skip" : ""} ${guideOpen ? "guide-open" : ""}`} role={phase === "welcome" ? "dialog" : "status"} aria-label={phase === "welcome" ? "Welcome to SecureRAG" : "Starting SecureRAG"}>
      <LogoField phase={phase} progress={progress} motion={motion} onWarpDone={onWarpDone} />
      <i className="splash-shade" aria-hidden="true" />

      {phase !== "boot" && (
        <div className="hero-mark" aria-hidden="true" style={{ left: box.x, top: box.y, width: box.s, height: box.s }}>
          <i className="hero-haze" />
          <div className="hero-spin">
            <LogoMark className="hero-bloom" />
            <AnimatedMark delay={MARK_DELAY} />
          </div>
        </div>
      )}
      <i className="frost" aria-hidden="true" />

      <div className="boot-hud" aria-hidden={phase !== "boot"}>
        <strong className="boot-word">SecureRAG</strong>
        <div className="boot-bar"><i style={{ transform: `scaleX(${progress})` }} /></div>
        <div className="boot-line"><span>{bootText}</span><b>{Math.round(progress * 100)}%</b></div>
      </div>

      <div className="intro" aria-hidden={phase === "boot"}>
        {phase !== "boot" && <Wordmark className="intro-brand" delay={WORD_DELAY} />}
        <h1 aria-label={LINES.join(" ")}>
          {LINES.map((line, i) => (
            <span className="intro-line" key={i} aria-hidden="true">
              {line.split(" ").map((w, j) => <span className="intro-word" key={j} style={{ "--n": word++ }}>{w}&nbsp;</span>)}
            </span>
          ))}
        </h1>
        <div className="intro-rest">
          <p>SecureRAG runs a language model, two security models and an encrypted document library on this PC. Each message and each passage is checked before the model can read it.</p>
          <div className="intro-actions">
            <button ref={primary} className="btn primary xl" disabled={phase !== "welcome"} onClick={onOpen}>Open workspace</button>
            <button className="btn glassy xl" disabled={phase !== "welcome"} onClick={onGuide}><BookOpen size={16} /> Setup guide</button>
          </div>
          <div className={`runtime-line ${ollama?.ok ? "ok" : ollama ? "bad" : ""}`}>
            <i />{!ollama ? "Looking for Ollama on this computer" : ollama.ok ? `Ollama is running${model ? `, using ${model}` : ""}` : "Ollama was not found. The setup guide shows how to install it."}
          </div>
          <label className="startup-check">
            <input type="checkbox" checked={showAtStartup} disabled={phase !== "welcome"} onChange={(e) => setShowAtStartup(e.target.checked)} />
            <span className="box" aria-hidden="true"><Check size={10} strokeWidth={3} /></span>
            Show this screen at startup
          </label>
        </div>
      </div>
    </div>
  );
}
