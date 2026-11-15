import React, { useState } from "react";
export function Toggle({ label, checked, onChange, disabled = false }) {
  return (
    <label className="toggle-row">
      <span>{label}</span>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="switch" aria-hidden="true" />
    </label>
  );
}
export function Panel({ title, eyebrow, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <header>
        <span className="eyebrow">{eyebrow}</span>
        <h2>{title}</h2>
      </header>
      {children}
    </section>
  );
}
export function RiskChart({ events }) {
  const points = events.filter((e) => Number.isFinite(e.score)).slice(-24);
  const [hover, setHover] = useState(null);
  const x = (i) => 20 + (i * 460) / Math.max(1, points.length - 1),
    y = (s) => 125 - s * 100;
  const line = points
    .map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.score)}`)
    .join(" ");
  return (
    <div className="chart">
      <div className="chart-label">
        <span>
          {hover === null
            ? "Malicious score · last 24 scored events"
            : `${points[hover]?.event} · ${points[hover]?.score.toFixed(3)}`}
        </span>
        <span>0—1</span>
      </div>
      {!points.length ? (
        <div className="empty-chart">Scores appear after a security check.</div>
      ) : (
        <svg
          viewBox="0 0 500 150"
          role="img"
          aria-label="Recorded malicious classification scores"
        >
          <defs>
            <linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--accent)" stopOpacity=".25" />
              <stop offset="1" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[25, 75, 125].map((v) => (
            <line
              key={v}
              x1="20"
              x2="480"
              y1={v}
              y2={v}
              stroke="var(--line)"
              strokeDasharray="3 5"
            />
          ))}
          <path
            className="chart-area"
            key={`a${points.length}`}
            d={`${line} L${x(points.length - 1)},140 L20,140 Z`}
            fill="url(#fill)"
          />
          <path
            className="chart-line"
            key={`l${points.length}`}
            pathLength="1"
            d={line}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="2"
          />
          <circle
            className="chart-pulse"
            cx={x(points.length - 1)}
            cy={y(points.at(-1).score)}
            r="4"
            fill="var(--accent)"
          />
          {points.map((p, i) => (
            <circle
              key={i}
              tabIndex="0"
              aria-label={`${p.event}: ${p.score}`}
              cx={x(i)}
              cy={y(p.score)}
              r={hover === i ? 5 : 3}
              fill={p.score >= 0.5 ? "var(--warn)" : "var(--accent)"}
              style={{ "--i": i }}
              className="chart-dot"
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
            />
          ))}
        </svg>
      )}
      <small>Classifier scores are not calibrated probabilities of harm.</small>
    </div>
  );
}
export function ActivityFeed({ events }) {
  return (
    <div className="feed">
      {events.length ? (
        [...events]
          .reverse()
          .slice(0, 8)
          .map((e, i) => (
            <article
              className="feed-entry"
              key={`${e.time}-${e.event}-${i}`}
              style={{ "--i": i }}
            >
              <i
                className={
                  ["BLOCKED", "QUARANTINED"].includes(e.decision)
                    ? "blocked"
                    : ""
                }
              />
              <div>
                <strong>{e.event?.replaceAll("_", " ")}</strong>
                <p>{e.decision || e.status || "Recorded"}</p>
              </div>
              <time>
                {e.time
                  ? new Date(e.time).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : ""}
              </time>
            </article>
          ))
      ) : (
        <p className="muted p-5">No decisions recorded yet.</p>
      )}
    </div>
  );
}
export function Thinking({ text }) {
  return (
    <div className="thinking" role="status">
      <span className="orbit">
        <i />
        <i />
        <i />
      </span>
      <div>
        <strong>{text}</strong>
        <p>Running locally · finished answers pass output checks</p>
      </div>
    </div>
  );
}
