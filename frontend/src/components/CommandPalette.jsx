import React, { useEffect, useMemo, useRef, useState } from "react";
import { Search, CornerDownLeft } from "lucide-react";
import { Kbd } from "./Shared";

// Raycast-style launcher: one input, grouped results, keyboard first.
export default function CommandPalette({ open, onClose, items }) {
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef();
  const list = useRef();
  useEffect(() => { if (open) { setQuery(""); setActive(0); setTimeout(() => input.current?.focus(), 10); } }, [open]);
  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    const scored = items.filter((it) => !q || `${it.title} ${it.subtitle || ""} ${it.keywords || ""}`.toLowerCase().includes(q));
    return q ? scored.slice(0, 40) : scored.filter((it) => it.group !== "Conversations" || scored.indexOf(it) < 60).slice(0, 40);
  }, [items, query]);
  useEffect(() => { setActive(0); }, [query]);
  useEffect(() => { list.current?.querySelector(".pal-row.on")?.scrollIntoView({ block: "nearest" }); }, [active]);
  if (!open) return null;
  const run = (item) => { onClose(); setTimeout(() => item.run(), 0); };
  const key = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(results.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter" && results[active]) { e.preventDefault(); run(results[active]); }
  };
  let lastGroup = null;
  return (
    <div className="overlay palette-overlay" onClick={onClose}>
      <section className="palette panel glass" role="dialog" aria-modal="true" aria-label="Command palette" onClick={(e) => e.stopPropagation()} onKeyDown={key}>
        <label className="pal-input">
          <Search size={18} />
          <input ref={input} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search documents, conversations and commands…" aria-label="Search" />
          <Kbd>Esc</Kbd>
        </label>
        <div className="pal-list" ref={list}>
          {results.map((it, i) => {
            const header = it.group !== lastGroup ? <div className="pal-group" key={`g${it.group}`}>{it.group}</div> : null;
            lastGroup = it.group;
            return (
              <React.Fragment key={`${it.group}-${it.id}`}>
                {header}
                <button className={`pal-row ${i === active ? "on" : ""}`} onMouseMove={() => setActive(i)} onClick={() => run(it)} disabled={it.disabled}>
                  <span className="pal-icon">{it.icon}</span>
                  <span className="pal-title">{it.title}</span>
                  {it.subtitle && <span className="pal-sub">{it.subtitle}</span>}
                  {it.keys && <span className="pal-keys">{it.keys.map((k) => <Kbd key={k}>{k}</Kbd>)}</span>}
                  <span className="pal-kind">{it.kind}</span>
                </button>
              </React.Fragment>
            );
          })}
          {!results.length && <p className="pal-empty">No results for “{query}”.</p>}
        </div>
        <footer className="pal-foot">
          <span className="pal-brand">SecureRAG</span>
          <span className="pal-hint">Open <Kbd><CornerDownLeft size={11} /></Kbd></span>
          <span className="pal-hint">Navigate <Kbd>↑</Kbd><Kbd>↓</Kbd></span>
        </footer>
      </section>
    </div>
  );
}
