import React, { useState } from "react";
import { documentState } from "./Shared";

export const STATES = [
  { id: "approved", state: "Approved", color: "var(--ok)", note: "Every passage can be used" },
  { id: "partial", state: "Partially approved", color: "var(--partial)", note: "Flagged passages are quarantined" },
  { id: "blocked", state: "Blocked", color: "var(--bad)", note: "Nothing reaches the model" },
  { id: "unchecked", state: "Unchecked", color: "var(--idle)", note: "Screened when retrieved" },
];

// Rose chart: the angle of a slice is its share of `value`, and its length
// grows with `weight`. Slices are drawn largest-radius first so the short
// ones stay visible on top.
export function Rose({ slices, size = 220, hover, onHover, label }) {
  const total = slices.reduce((n, s) => n + s.value, 0);
  const maxW = Math.max(1, ...slices.map((s) => s.weight ?? s.value));
  const c = size / 2, rMax = c - 4, rMin = rMax * 0.52;
  let a = -Math.PI / 2;
  const wedges = slices.filter((s) => s.value > 0).map((s) => {
    const span = (s.value / total) * Math.PI * 2;
    const r = rMin + (rMax - rMin) * Math.sqrt((s.weight ?? s.value) / maxW);
    const a0 = a, a1 = a + span;
    a = a1;
    const p = (ang, rad) => `${(c + Math.cos(ang) * rad).toFixed(2)} ${(c + Math.sin(ang) * rad).toFixed(2)}`;
    const d = span >= Math.PI * 2 - 1e-6
      ? `M${c - r} ${c} a${r} ${r} 0 1 0 ${r * 2} 0 a${r} ${r} 0 1 0 ${-r * 2} 0 Z`
      : `M${c} ${c} L${p(a0, r)} A${r} ${r} 0 ${span > Math.PI ? 1 : 0} 1 ${p(a1, r)} Z`;
    return { ...s, d, r };
  }).sort((x, y) => y.r - x.r);
  return (
    <svg className="rose" width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
      <circle cx={c} cy={c} r={rMax} className="rose-guide" />
      <circle cx={c} cy={c} r={rMin} className="rose-guide" />
      {!wedges.length && <circle cx={c} cy={c} r={rMin} className="rose-empty" />}
      {wedges.map((s) => (
        <path key={s.id} d={s.d} fill={s.color} className={`rose-slice ${hover && hover !== s.id ? "dim" : ""}`}
          onMouseEnter={() => onHover?.(s.id)} onMouseLeave={() => onHover?.(null)}>
          <title>{s.title}</title>
        </path>
      ))}
      <circle cx={c} cy={c} r={2.5} className="rose-pin" />
    </svg>
  );
}

// Screening summary: one row per decision, with the rose chart beside it.
// `items` is a list of { state, usable, total }. Rows become filter buttons
// when `onPick` is given.
export function LibrarySummary({ items, active, onPick, compact = false, title = "Screening summary", action }) {
  const [hover, setHover] = useState(null);
  const rows = STATES.map((s) => {
    const mine = items.filter((d) => d.state === s.state);
    return { ...s, docs: mine.length, usable: mine.reduce((n, d) => n + d.usable, 0), total: mine.reduce((n, d) => n + d.total, 0) };
  }).filter((r) => r.docs || r.id !== "unchecked");
  const docs = items.length, usable = rows.reduce((n, r) => n + r.usable, 0), total = rows.reduce((n, r) => n + r.total, 0);
  const pct = (n) => (docs ? `${Math.round((n / docs) * 100)} %` : "0 %");
  const slices = rows.map((r) => ({ id: r.id, value: r.docs, weight: Math.max(1, r.total), color: r.color, title: `${r.state}: ${r.docs} of ${docs} documents, ${r.total} passages` }));
  const Row = onPick ? "button" : "div";
  return (
    <section className={`summary ${compact ? "compact" : ""}`}>
      <div className="summary-table">
        <header className="summary-title"><h3>{title}</h3>{action}</header>
        <div className="summary-row head"><span>Decision</span><span>Share</span><span>Documents</span><span>Passages usable</span>{!compact && <span>What it means</span>}</div>
        {rows.map((r) => (
          <Row key={r.id} className={`summary-row ${active === r.id ? "on" : ""} ${hover && hover !== r.id ? "dim" : ""}`}
            {...(onPick ? { onClick: () => onPick(active === r.id ? "all" : r.id), "aria-pressed": active === r.id, title: active === r.id ? "Show all documents" : `Show only ${r.state.toLowerCase()} documents` } : {})}
            onMouseEnter={() => setHover(r.id)} onMouseLeave={() => setHover(null)}>
            <span className="summary-name">{onPick && <i className="tick" aria-hidden="true" />}<i className="swatch" style={{ background: r.color, color: r.color }} />{r.state}</span>
            <span>{pct(r.docs)}</span>
            <span>{r.docs}</span>
            <span>{r.usable}<small> of {r.total}</small></span>
            {!compact && <span className="summary-note">{r.note}</span>}
          </Row>
        ))}
        <div className="summary-row total"><span>Total</span><span>{docs ? "100 %" : "0 %"}</span><span>{docs}</span><span>{usable}<small> of {total}</small></span>{!compact && <span />}</div>
      </div>
      <figure className="summary-chart">
        <Rose slices={slices} size={compact ? 132 : 216} hover={hover} onHover={setHover} label={`Documents by screening decision: ${rows.map((r) => `${r.docs} ${r.state.toLowerCase()}`).join(", ")}`} />
        {!compact && <figcaption>Slice width shows documents, slice length shows passages</figcaption>}
      </figure>
    </section>
  );
}

export const summaryItems = (documents) => documents.map((d) => ({
  state: documentState(d), usable: d.indexed_chunks || 0, total: (d.indexed_chunks || 0) + (d.quarantined_chunks || 0),
}));
