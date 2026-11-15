import React from "react";
import {
  ShieldCheck, ShieldAlert, ShieldX, X, Database, FileText, BookOpen, Eye, Trash2, Sparkles, MessageSquare, Info, Lock, Cpu,
} from "lucide-react";
import { name, score3, documentState, stateClass, CHANNEL, TypeBadge, StatePill, Switch, Empty, plural } from "./Shared";
import { Rose } from "./Summary";

// What the last answer means, in one sentence, for the Policy decision card.
function policy(result) {
  const withheld = result.withheld?.length || 0;
  switch (result.status) {
    case "BLOCKED":
      return { tone: "bad", icon: <ShieldX size={18} />, title: "Blocked by PromptGuard", text: "The message resembled a prompt-injection attack, so it never reached the model." };
    case "WITHHELD":
      return { tone: "bad", icon: <ShieldAlert size={18} />, title: "Withheld by DocumentGuard", text: `The passages that answer this question are quarantined. ${plural(withheld, "passage")} withheld; nothing was generated from them.` };
    case "REPORT":
      return { tone: "ok", icon: <ShieldCheck size={18} />, title: "Answered from screening records", text: "Built from stored upload decisions. No language model was used." };
    case "NO_CONTEXT":
    case "SELECT_DOCUMENT":
      return { tone: "warn", icon: <Info size={18} />, title: "No usable context", text: result.answer?.split("\n")[0] };
    default:
      if (withheld) return { tone: "warn", icon: <ShieldAlert size={18} />, title: "Allowed with exclusions", text: `Answered from approved passages. ${plural(withheld, "related passage")} ${withheld === 1 ? "was" : "were"} withheld.` };
      if (result.used_documents) return { tone: "ok", icon: <ShieldCheck size={18} />, title: "Allowed", text: `Prompt is safe. ${plural(result.sources?.length || 0, "approved passage")} from your documents ${result.sources?.length === 1 ? "was" : "were"} used.` };
      return { tone: "ok", icon: <ShieldCheck size={18} />, title: "Allowed", text: "Prompt is safe. Answered without documents." };
  }
}

function SecurityTab({ result, snapshot }) {
  if (!result) {
    return <Empty icon={<ShieldCheck size={22} />} title="Nothing inspected yet">Send a message. Its screening decision, scores and pipeline trace appear here.</Empty>;
  }
  const p = policy(result);
  const guard = result.guard;
  const threshold = guard?.prompt_threshold ?? snapshot.guards?.prompt?.threshold ?? 0.5;
  return (
    <div className="insp-stack">
      <section className={`policy-card tone-${p.tone}`}>
        <span className="policy-icon">{p.icon}</span>
        <div>
          <span className="micro">Policy decision</span>
          <h3>{p.title}</h3>
        </div>
        {typeof result.elapsed_ms === "number" && <span className="policy-ms">{result.elapsed_ms} ms</span>}
        <p>{p.text}</p>
      </section>

      <div className="insp-label">Prompt classification</div>
      <section className="insp-card">
        {guard ? (
          <>
            <div className="score-head">
              <span>PromptGuard <small>FINAL</small></span>
              <b className={guard.prompt_score >= threshold ? "bad" : ""}>{score3(guard.prompt_score)}</b>
            </div>
            <div className="score-bar" style={{ "--score": `${Math.min(100, guard.prompt_score * 100)}%`, "--th": `${threshold * 100}%` }}>
              <i className={guard.prompt_score >= threshold ? "fill bad" : "fill"} />
              <em />
            </div>
            <small className="note"><Info size={12} /> Raw DeBERTa output against a {threshold.toFixed(2)} threshold. Not a calibrated probability.</small>
          </>
        ) : (
          <small className="note"><Info size={12} /> Not classified: this answer came from local records and never reached a model.</small>
        )}
      </section>

      <div className="insp-label">Pipeline trace</div>
      {result.trace?.length ? (
        <ol className="trace">
          {result.trace.map((t, i) => (
            <li key={i} className={`t-${t.status}`}>
              <i />
              <div><strong>{t.step}</strong><p>{t.detail}</p></div>
              <span>{t.ms} ms</span>
            </li>
          ))}
        </ol>
      ) : <p className="insp-muted">No trace was stored for this message.</p>}

      <div className="insp-label">Runtime</div>
      <div className="runtime-grid">
        <div><small>Model</small><b>{result.model || snapshot.model || "not set"}</b></div>
        <div><small>Inference</small><b>Local · Ollama</b></div>
        <div><small>Vector store</small><b>ChromaDB</b></div>
        <div><small>Guards</small><b>Prompt · Document</b></div>
      </div>
    </div>
  );
}

function SourcesTab({ result, onSelect, disabled }) {
  const sources = result?.sources || [];
  const withheld = result?.withheld || [];
  if (!result || (!sources.length && !withheld.length)) {
    return <Empty icon={<BookOpen size={22} />} title="No passages for this answer">When an answer uses your documents, every passage it read, and every passage that was withheld, is listed here.</Empty>;
  }
  return (
    <div className="insp-stack">
      <p className="insp-muted">{plural(sources.length, "passage")} used · {withheld.length} withheld</p>
      {sources.map((s, i) => (
        <button key={`s${i}`} className="source-card" disabled={disabled} onClick={() => onSelect(s.source)}>
          <div className="source-head">
            <span className="num">{s.citation || i + 1}</span>
            <strong>{name(s.source)}</strong>
            <span className="shield ok" title="Approved by DocumentGuard"><ShieldCheck size={13} /></span>
          </div>
          {s.text && <q>{s.text.slice(0, 150)}{s.text.length > 150 ? "…" : ""}</q>}
          <div className="source-meta">
            <span>{s.page ? `page ${s.page}` : `passage ${s.chunk_index + 1}`}{s.cited ? " · cited" : ""}</span>
            {typeof s.similarity === "number" && <span className="sim"><i style={{ "--v": `${Math.max(4, s.similarity * 100)}%` }} />{s.similarity.toFixed(2)}</span>}
          </div>
        </button>
      ))}
      {withheld.map((w, i) => (
        <button key={`w${i}`} className="source-card withheld" disabled={disabled} onClick={() => onSelect(w.source)}>
          <div className="source-head">
            <span className="num">!</span>
            <strong>{w.name}</strong>
            <span className="shield bad" title="Withheld by DocumentGuard"><ShieldX size={13} /></span>
          </div>
          <p>Withheld: {w.reason}.</p>
          <div className="source-meta">
            <span>passage {w.passage}{w.page ? ` · page ${w.page}` : ""} · {w.stage === "retrieval" ? "retrieval check" : "upload"}</span>
            {w.relevance > 0 && <span className="sim bad"><i style={{ "--v": `${Math.max(4, w.relevance * 100)}%` }} />{w.relevance.toFixed(2)}</span>}
          </div>
        </button>
      ))}
    </div>
  );
}

function ContextTab({ snapshot, selected, setSelected, mode }) {
  const docs = snapshot.documents;
  const searchable = docs.reduce((n, d) => n + (d.indexed_chunks || 0), 0);
  const toggle = (src, on) => setSelected((s) => (on ? [...new Set([...s, src])] : s.filter((x) => x !== src)));
  return (
    <div className="insp-stack">
      <section className="insp-card index-card">
        <span className="policy-icon"><Database size={17} /></span>
        <div>
          <strong>Local index · ChromaDB</strong>
          <small>{plural(searchable, "searchable passage")} · {plural(docs.length, "document")}</small>
        </div>
      </section>
      <p className="insp-muted">
        {mode === "documents"
          ? (selected.length ? `Documents mode searches the ${plural(selected.length, "document")} switched on below.` : "Nothing switched on: Documents mode searches the whole library.")
          : "Chat uses every approved document automatically. Switches choose the scope for Documents mode."}
      </p>
      <div className="ctx-list">
        {docs.map((d) => {
          const state = documentState(d);
          const usable = !!d.indexed_chunks;
          return (
            <div key={d.source} className={`ctx-row ${usable ? "" : "dim"}`}>
              <TypeBadge source={d.source} />
              <div className="ctx-text">
                <strong title={d.source}>{name(d.source)}</strong>
                <small><FileText size={11} /> {plural(d.indexed_chunks || 0, "passage")}{d.quarantined_chunks ? ` · ${d.quarantined_chunks} quarantined` : ""}{d.block_reason ? " · hidden content flagged" : ""}</small>
              </div>
              <Switch label={`Use ${name(d.source)}`} checked={selected.includes(d.source)} disabled={!usable} onChange={(on) => toggle(d.source, on)} />
            </div>
          );
        })}
        {!docs.length && <p className="insp-muted">No documents yet.</p>}
      </div>
    </div>
  );
}

// One document at a glance: how many passages and hidden parts passed.
function DecisionSummary({ doc }) {
  const hidden = doc.hidden_parts || [];
  const bad = (rows) => rows.filter((r) => r.decision === "QUARANTINED").length;
  const parts = [
    { id: "ok", label: "Passages approved", n: doc.rows.length - bad(doc.rows), color: "var(--ok)" },
    { id: "bad", label: "Passages quarantined", n: bad(doc.rows), color: "var(--bad)" },
    { id: "hok", label: "Hidden parts clean", n: hidden.length - bad(hidden), color: "var(--accent)" },
    { id: "hbad", label: "Hidden parts flagged", n: bad(hidden), color: "var(--partial)" },
  ];
  return (
    <section className="insp-card doc-summary">
      <Rose size={92} label={parts.map((p) => `${p.n} ${p.label.toLowerCase()}`).join(", ")}
        slices={parts.map((p) => ({ id: p.id, value: p.n, weight: p.n, color: p.color, title: `${p.label}: ${p.n}` }))} />
      <div className="doc-legend">
        {parts.map((p) => <div key={p.id}><i className="swatch" style={{ background: p.color, color: p.color }} />{p.label}<b>{p.n}</b></div>)}
      </div>
    </section>
  );
}

function DocumentTab({ source, decision, busy, onExplain, onPreview, onSummarize, onAsk, onRemove }) {
  if (!source) return <Empty icon={<FileText size={22} />} title="No document selected">Select a document in the library to see every passage, every hidden part and the scores behind its decision.</Empty>;
  const doc = decision?.document?.source === source ? decision : null;
  return (
    <div className="insp-stack decision-panel">
      <section className="insp-card doc-head">
        <TypeBadge source={source} />
        <div className="ctx-text"><strong title={source}>{name(source)}</strong>{doc && <StatePill state={documentState(doc.document)} />}</div>
      </section>
      <div className="doc-actions">
        <button disabled={busy} onClick={() => onExplain(source)}><Info size={13} /> Explain decision</button>
        <button disabled={busy} onClick={() => onAsk(source)}><MessageSquare size={13} /> Ask</button>
        <button disabled={busy} onClick={() => onSummarize(source)}><Sparkles size={13} /> Summarize</button>
        <button disabled={busy} onClick={() => onPreview(source)}><Eye size={13} /> Preview</button>
        <button disabled={busy} className="danger" aria-label="Remove selected document" title="Remove from library" onClick={() => onRemove(source)}><Trash2 size={13} /></button>
      </div>
      {!doc && <p className="insp-muted">Choose Explain decision to load the screening details.</p>}
      {doc && <>
        {doc.block_reason && <p className="block-banner"><ShieldX size={14} /> Whole document blocked: {doc.block_reason}</p>}
        <DecisionSummary doc={doc} />
        <div className="runtime-grid">
          <div><small>Upload threshold</small><b>{doc.threshold.toFixed(3)}</b></div>
          <div><small>Retrieval threshold</small><b>{doc.retrieval_threshold.toFixed(3)}</b></div>
          <div><small>Passages</small><b>{doc.rows.length}</b></div>
          <div><small>Hidden parts</small><b>{doc.hidden_parts?.length || 0}</b></div>
        </div>
        <div className="insp-label">Visible passages</div>
        <div className="decision-rows">
          {doc.rows.map((r, i) => (
            <details key={i} className={r.decision === "QUARANTINED" ? "flagged" : ""}>
              <summary><i className={`state-dot ${r.decision === "QUARANTINED" ? "blocked" : "approved"}`} /> Passage {r.chunk_index + 1}{r.page ? ` · p.${r.page}` : ""}<span>{typeof r.score === "number" ? r.score.toFixed(3) : r.decision}</span></summary>
              <p>{r.reason}</p>
              {r.retrieval_check && <p className="insp-muted">Last retrieval check: {r.retrieval_check.decision}{typeof r.retrieval_check.score === "number" ? ` · ${r.retrieval_check.score.toFixed(4)}` : ""}</p>}
              <pre>{r.text}</pre>
            </details>
          ))}
        </div>
        {!!doc.hidden_parts?.length && <>
          <div className="insp-label">Hidden content checked</div>
          <div className="decision-rows">
            {doc.hidden_parts.map((h, i) => (
              <details key={i} className={h.decision === "QUARANTINED" ? "flagged" : ""}>
                <summary><i className={`state-dot ${h.decision === "QUARANTINED" ? "blocked" : "approved"}`} /> {CHANNEL[h.channel] || h.channel}<span>{typeof h.score === "number" ? h.score.toFixed(3) : h.decision}</span></summary>
                <p><b>{h.label}</b></p>
                <p>{h.reason}</p>
                <pre>{h.text}</pre>
              </details>
            ))}
          </div>
        </>}
        <p className="insp-muted small">{doc.explanation}</p>
      </>}
    </div>
  );
}

export default function Inspector({ open, tab, setTab, onClose, result, snapshot, selected, setSelected, mode, source, decision, busy, actions }) {
  const tabs = [["security", "Security"], ["sources", "Sources"], ["context", "Context"], ["document", "Document"]];
  return (
    <aside className={`inspector panel glass ${open ? "open" : ""}`} aria-label="Security inspector" aria-hidden={!open}>
      <header className="insp-head">
        <div className="seg small" role="tablist">
          {tabs.map(([id, label]) => (
            <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? "on" : ""} onClick={() => setTab(id)}>
              {label}{id === "sources" && (result?.withheld?.length || 0) > 0 && <i className="dot-bad" />}
            </button>
          ))}
        </div>
        <button className="icon-btn ghost" aria-label="Close security inspector" onClick={onClose}><X size={15} /></button>
      </header>
      <div className="insp-body">
        {tab === "security" && <SecurityTab result={result} snapshot={snapshot} />}
        {tab === "sources" && <SourcesTab result={result} disabled={busy} onSelect={actions.explain} />}
        {tab === "context" && <ContextTab snapshot={snapshot} selected={selected} setSelected={setSelected} mode={mode} />}
        {tab === "document" && <DocumentTab source={source} decision={decision} busy={busy} onExplain={actions.explain}
          onPreview={actions.preview} onSummarize={actions.summarize} onAsk={actions.ask} onRemove={actions.remove} />}
      </div>
      <footer className="insp-foot"><Lock size={11} /> Everything shown here was computed on this computer <Cpu size={11} /></footer>
    </aside>
  );
}
