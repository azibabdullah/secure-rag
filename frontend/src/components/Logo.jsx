import React, { useId } from "react";
import { STRIPES } from "./logoData";

// Brand colours: a pale lavender at the top-left of the mark running to a
// deep violet at the bottom-right.
export const BRAND = ["#ddd2ff", "#a98bff", "#8b5cf6", "#6527d9"];
export const MARK_PATH = STRIPES.map((s) => s.d).join(" ");
const STEP = 0.085;           // seconds between stripes in the draw-in
const DRAW = 0.6;             // seconds for one stripe to draw

function Gradient({ id }) {
  return (
    <linearGradient id={id} x1="20" y1="10" x2="185" y2="190" gradientUnits="userSpaceOnUse">
      <stop offset="0" stopColor={BRAND[0]} />
      <stop offset="0.38" stopColor={BRAND[1]} />
      <stop offset="0.72" stopColor={BRAND[2]} />
      <stop offset="1" stopColor={BRAND[3]} />
    </linearGradient>
  );
}

// Static mark for the sidebar, chat avatar, guide and empty states.
// tone="brand" paints the brand gradient; tone="current" follows the text colour.
export function LogoMark({ size = 20, tone = "brand", className = "" }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg className={`logo-mark ${className}`} width={size} height={size} viewBox="4 4 192 192" aria-hidden="true">
      {tone === "brand" && <defs><Gradient id={`g${id}`} /></defs>}
      <path d={MARK_PATH} fill={tone === "brand" ? `url(#g${id})` : "currentColor"} />
    </svg>
  );
}

// The mark drawing itself in, stripe by stripe, like the brand animation:
// each stripe is revealed along its centre line, outer stripes first. A final
// fill fades in at the end so the tips of every stripe are crisp. With motion
// off the CSS animations do not run and the finished mark shows at once.
export function AnimatedMark({ delay = 0.2, className = "" }) {
  const id = useId().replace(/:/g, "");
  const end = delay + (STRIPES.length - 1) * STEP + DRAW;
  return (
    <svg className={`animated-mark ${className}`} viewBox="4 4 192 192" aria-hidden="true">
      <defs>
        <Gradient id={`g${id}`} />
        {STRIPES.map((s, i) => (
          <mask key={i} id={`m${id}${i}`} maskUnits="userSpaceOnUse" x="-20" y="-20" width="240" height="240">
            <path className="draw" d={s.line} stroke="#fff" strokeWidth={s.w} strokeLinecap="round" strokeLinejoin="round" fill="none"
              style={{ "--len": s.len + 2, animationDelay: `${delay + i * STEP}s`, animationDuration: `${DRAW}s` }} />
          </mask>
        ))}
      </defs>
      <g fill={`url(#g${id})`}>
        {STRIPES.map((s, i) => <path key={i} d={s.d} mask={`url(#m${id}${i})`} />)}
        <path className="settle" d={MARK_PATH} style={{ animationDelay: `${end - 0.15}s` }} />
      </g>
    </svg>
  );
}
AnimatedMark.duration = (delay = 0.2) => delay + (STRIPES.length - 1) * STEP + DRAW;

// "SecureRAG" typed in one letter at a time, each letter rising into place.
export function Wordmark({ delay = 0, className = "" }) {
  return (
    <span className={`wordmark ${className}`} aria-label="SecureRAG">
      {"SecureRAG".split("").map((ch, i) => (
        <span key={i} aria-hidden="true" style={{ animationDelay: `${delay + i * 0.075}s` }}>{ch}</span>
      ))}
    </span>
  );
}

// The large glowing mark that sits half off-screen behind the glass panels:
// a warm haze, a blurred bloom and the crisp mark on top.
export function Emblem() {
  const id = useId().replace(/:/g, "");
  return (
    <div className="emblem" aria-hidden="true">
      <i className="emblem-haze" />
      <svg className="emblem-bloom" viewBox="4 4 192 192"><defs><Gradient id={`b${id}`} /></defs><path d={MARK_PATH} fill={`url(#b${id})`} /></svg>
      <svg className="emblem-line" viewBox="4 4 192 192"><defs><Gradient id={`l${id}`} /></defs><path d={MARK_PATH} fill={`url(#l${id})`} /></svg>
    </div>
  );
}
