import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Shield, ShieldCheck, ShieldAlert, Plus, ArrowUp, Sun, Moon, FileText, Activity, MessagesSquare, LayoutGrid, Files,
  SlidersHorizontal, Trash2, RefreshCw, Copy, PanelLeft, PanelRight, ClipboardList, ArrowDown, X, Search, Check,
  BookOpen, Info, Sparkles, ChevronDown, Upload, Cpu, Lock, MessageSquare, Eye, HelpCircle, Play,
} from "lucide-react";
import { call, onProgress } from "./bridge";
import { RiskChart } from "./components/Widgets";
import Starfield from "./components/Starfield";
import { CountUp, useSpotlight, useRipple } from "./components/Motion";
import Inspector from "./components/Inspector";
import CommandPalette from "./components/CommandPalette";
import { SetupGuide } from "./components/Onboarding";
import Splash from "./components/Splash";
import { LogoMark, Emblem } from "./components/Logo";
import { LibrarySummary, summaryItems } from "./components/Summary";
import {
  name, plural, score3, documentState, stateClass, TypeBadge, StatePill, Switch, SettingRow, Thinking, Empty, Kbd,
} from "./components/Shared";

const REPORT_QUESTION = "Show a screening report: which documents were blocked and which were allowed.";
const store = {
  get: (k, d) => { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch {} },
};
const VIEWS = { overview: "Overview", workspace: "Workspace", documents: "Documents", activity: "Security activity", settings: "Settings" };

function groupSessions(sessions) {
  const day = 86400000, now = new Date(), start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const groups = [["Today", []], ["Yesterday", []], ["This week", []], ["Earlier", []]];
  for (const s of sessions) {
    const t = new Date(s.updated).getTime();
    const g = t >= start ? 0 : t >= start - day ? 1 : t >= start - 6 * day ? 2 : 3;
    groups[g][1].push(s);
  }
  return groups.filter(([, list]) => list.length);
}

function ReportCard({ report, onSelect, disabled }) {
  return (
    <div className="report-card">
      <LibrarySummary compact title="Screening report" items={report.documents.map((d) => ({ state: d.state, usable: d.usable, total: d.passages }))} />
      {report.documents.map((d) => (
        <button key={d.source} className="report-row" disabled={disabled} onClick={() => onSelect(d.source)} title="Open this document's decision">
          <i className={`state-dot ${stateClass[d.state]}`} />
          <span className="report-name">{d.name}</span>
          <StatePill state={d.state} />
          <span className="report-meta">{d.usable}/{d.passages} usable{typeof d.highest_score === "number" ? ` · max ${d.highest_score.toFixed(3)}` : ""}{d.hidden_checked ? ` · ${plural(d.hidden_checked, "hidden part")} checked` : ""}</span>
          {d.block_reason ? <small className="report-flagged">Whole document blocked: {d.block_reason}</small>
            : !!d.flagged.length && <small className="report-flagged">Quarantined: {d.flagged.map((f) => `passage ${f.passage}${f.page ? ` (p. ${f.page})` : ""}${typeof f.score === "number" ? ` · ${f.score.toFixed(3)}` : ""}`).join(", ")}</small>}
        </button>
      ))}
      <small className="report-note">From DocumentGuard upload records (threshold {Number(report.document_threshold).toFixed(3)}). No language model was used.</small>
    </div>
  );
}

function WithheldCard({ items, onSelect, disabled, compact }) {
  return (
    <div className={`trail-card ${compact ? "compact" : ""}`}>
      {!compact && <div className="trail-head"><ShieldAlert size={14} /> Withheld by DocumentGuard</div>}
      {items.map((w, i) => (
        <button key={i} className="trail-row" disabled={disabled} onClick={() => onSelect(w.source)} title="Open this document's decision">
          <span className="trail-where"><FileText size={13} /> {w.name} · passage {w.passage}{w.page ? ` · page ${w.page}` : ""}</span>
          <span className="trail-why">{w.reason}</span>
          <span className="trail-facts">
            <span>score <b>{score3(w.score)}</b></span><span>threshold <b>{score3(w.threshold)}</b></span>
            <span>stage <b>{w.stage === "retrieval" ? "retrieval check" : "upload"}</b></span>
            {w.relevance > 0 && <span>relevance <b>{w.relevance.toFixed(2)}</b></span>}
          </span>
        </button>
      ))}
    </div>
  );
}

function DocPicker({ documents, selected, setSelected, disabled, onUpload }) {
  const [query, setQuery] = useState("");
  const shown = documents.filter((d) => name(d.source).toLowerCase().includes(query.trim().toLowerCase()));
  const toggle = (src) => setSelected((s) => (s.includes(src) ? s.filter((x) => x !== src) : [...s, src]));
  return (
    <aside className="picker" aria-label="Select documents">
      <div className="picker-head"><strong>Library</strong><span>{selected.length ? `${selected.length} selected` : "All documents"}</span></div>
      <label className="field sm"><Search size={13} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter" aria-label="Filter documents" /></label>
      <div className="picker-actions">
        <button disabled={disabled || !shown.length} onClick={() => setSelected([...new Set([...selected, ...shown.filter((d) => d.indexed_chunks).map((d) => d.source)])])}>Select all</button>
        <button disabled={disabled || !selected.length} onClick={() => setSelected([])}>Clear</button>
      </div>
      <div className="picker-list">
        {shown.map((d) => {
          const on = selected.includes(d.source), state = documentState(d);
          return (
            <label key={d.source} className={`pick ${on ? "on" : ""} ${d.indexed_chunks ? "" : "dim"}`} title={d.block_reason ? `Blocked: ${d.block_reason}` : d.source}>
              <input type="checkbox" checked={on} disabled={disabled} onChange={() => toggle(d.source)} />
              <span className="box" aria-hidden="true"><Check size={11} strokeWidth={3} /></span>
              <span className="pick-text">
                <span className="pick-name">{name(d.source)}</span>
                <small><i className={`state-dot ${stateClass[state]}`} /> {state}{d.indexed_chunks ? ` · ${d.indexed_chunks} usable` : ""}</small>
              </span>
            </label>
          );
        })}
        {!documents.length && <p className="insp-muted">No documents yet.</p>}
      </div>
      <button className="picker-upload" disabled={disabled} onClick={onUpload}><Plus size={14} /> Add documents</button>
    </aside>
  );
}

export default function App() {
  const [snapshot, setSnapshot] = useState({ documents: [], events: [], sessions: [], model: "" });
  const [busy, setBusy] = useState("Loading security models");
  const [error, setError] = useState("");
  const [dark, setDark] = useState(true);
  const [motion, setMotion] = useState(!matchMedia("(prefers-reduced-motion: reduce)").matches);
  const [view, setView] = useState("workspace");
  const [mode, setMode] = useState("chat");
  const [source, setSource] = useState("");
  const [selected, setSelected] = useState([]);
  const [models, setModels] = useState([]);
  const [model, setModel] = useState("");
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [session, setSession] = useState("");
  const [preview, setPreview] = useState(null);
  const [retry, setRetry] = useState(null);
  const [decision, setDecision] = useState(null);
  const [sideOpen, setSideOpen] = useState(() => store.get("securerag.sidebar", true));
  const [peek, setPeek] = useState(false);
  const [inspOpen, setInspOpen] = useState(() => store.get("securerag.inspector", true));
  const [inspTab, setInspTab] = useState("security");
  const [narrow, setNarrow] = useState(() => matchMedia("(max-width: 1180px)").matches);
  const [atBottom, setAtBottom] = useState(true);
  const [palette, setPalette] = useState(false);
  const [toast, setToast] = useState(null);
  const [showAtStartup, setShowAtStartup] = useState(() => store.get("securerag.welcome", true));
  // boot (logo + loading) -> welcome (optional) -> warp (transition) -> app
  const [phase, setPhase] = useState("boot");
  const [ready, setReady] = useState(false);
  const bootStart = useRef(performance.now());
  const peekTimer = useRef(0);
  const [guide, setGuide] = useState(false);
  const [ollama, setOllama] = useState(null);
  const [checking, setChecking] = useState(false);
  const [convFilter, setConvFilter] = useState(null);
  const [openSections, setOpenSections] = useState(() => store.get("securerag.sections", { conv: true, lib: true }));
  const [libFilter, setLibFilter] = useState("all");
  const [libQuery, setLibQuery] = useState("");
  const preferencesLoaded = useRef(false);
  const scroller = useRef();
  const locked = useRef(false);
  useSpotlight(motion);
  useRipple(motion);

  const starfield = !!snapshot.preferences?.starfield;
  const logoGlow = snapshot.preferences?.logo_glow !== false;   // glowing logo behind the panels; on unless turned off
  const sideCollapsed = !sideOpen || narrow;
  useEffect(() => { document.documentElement.dataset.theme = dark ? "dark" : "light"; }, [dark]);
  useEffect(() => { document.documentElement.dataset.motion = motion ? "on" : "off"; }, [motion]);
  useEffect(() => { store.set("securerag.sidebar", sideOpen); }, [sideOpen]);
  useEffect(() => { if (!narrow) store.set("securerag.inspector", inspOpen); }, [inspOpen]);
  useEffect(() => { if (narrow) setInspOpen(false); else setInspOpen(store.get("securerag.inspector", true)); }, [narrow]);
  useEffect(() => { store.set("securerag.sections", openSections); }, [openSections]);
  useEffect(() => { store.set("securerag.welcome", showAtStartup); }, [showAtStartup]);
  useEffect(() => { document.documentElement.dataset.phase = phase; }, [phase]);
  useEffect(() => {
    if (phase !== "boot" || !ready) return;
    const least = motion ? 3400 : 400;   // let the logo draw in and the name type out
    const t = setTimeout(() => setPhase(showAtStartup ? "welcome" : "warp"), Math.max(500, least - (performance.now() - bootStart.current)));
    return () => clearTimeout(t);
  }, [phase, ready, motion]);
  useEffect(() => { if (phase === "warp" && !motion) setPhase("app"); }, [phase, motion]);
  const enterApp = () => { setGuide(false); setPhase((p) => (p === "app" ? p : "warp")); };
  const peekIn = () => { if (!sideCollapsed) return; clearTimeout(peekTimer.current); peekTimer.current = setTimeout(() => setPeek(true), 160); };
  const peekOut = () => { clearTimeout(peekTimer.current); setPeek(false); };
  // On a narrow window the rail is always collapsed, so the button opens it over the content instead.
  const toggleSide = () => { clearTimeout(peekTimer.current); if (narrow) setPeek((p) => !p); else { setPeek(false); setSideOpen((v) => !v); } };
  useEffect(() => {
    const q = matchMedia("(max-width: 1180px)");
    const change = () => setNarrow(q.matches);
    q.addEventListener("change", change);
    return () => q.removeEventListener("change", change);
  }, []);
  useEffect(() => {
    const box = scroller.current;
    if (box && atBottom) box.scrollTo({ top: box.scrollHeight, behavior: motion ? "smooth" : "instant" });
  }, [messages, busy, view]);
  useEffect(() => {
    const present = new Set(snapshot.documents.map((d) => d.source));
    setSelected((s) => (s.every((x) => present.has(x)) ? s : s.filter((x) => present.has(x))));
  }, [snapshot.documents]);
  useEffect(() => {
    if (!toast || toast.sticky) return;
    const t = setTimeout(() => setToast(null), 9000);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    if (!preview) return;
    const esc = (e) => { if (e.key === "Escape") setPreview(null); };
    document.addEventListener("keydown", esc);
    return () => document.removeEventListener("keydown", esc);
  }, [preview]);
  useEffect(() => {
    const key = (e) => {
      const k = e.key.toLowerCase();
      if (document.documentElement.dataset.phase !== "app") return;   // no shortcuts under the start-up screens
      if ((e.ctrlKey || e.metaKey) && k === "k") { e.preventDefault(); setPalette((p) => !p); }
      else if ((e.ctrlKey || e.metaKey) && k === "b") { e.preventDefault(); setPeek(false); setSideOpen((s) => !s); }
      else if ((e.ctrlKey || e.metaKey) && k === "i") { e.preventDefault(); setInspOpen((s) => !s); }
    };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, []);

  async function run(operation, args = {}, label = "Working locally") {
    if (locked.current) return;
    locked.current = true;
    setBusy(label);
    setError("");
    try {
      const response = await call(operation, args);
      if (response.snapshot) {
        setSnapshot(response.snapshot);
        setModel(response.snapshot.model);
        if (!preferencesLoaded.current && response.snapshot.preferences) {
          setDark(response.snapshot.preferences.dark);
          if (response.snapshot.preferences.motion !== null) setMotion(response.snapshot.preferences.motion);
          preferencesLoaded.current = true;
        }
      }
      return response.result;
    } catch (e) {
      setError(e.message);
      return undefined;
    } finally {
      setBusy("");
      locked.current = false;
    }
  }
  // Silent Ollama check: never shows an error banner, only updates the status.
  async function checkOllama() {
    if (locked.current) return;
    locked.current = true;
    setChecking(true);
    try {
      const r = await call("models");
      setOllama({ ok: true, models: r.result || [] });
      setModels(r.result || []);
    } catch (e) {
      setOllama({ ok: false, models: [], message: e.message });
    } finally {
      locked.current = false;
      setChecking(false);
    }
  }
  useEffect(() => {
    const off = onProgress(setBusy);
    run("snapshot").then(() => { setReady(true); checkOllama(); });
    return off;
  }, []);

  async function preference(key, value) {
    const result = await run("preferences", { [key]: value }, "Saving preference");
    if (result) {
      if (key === "dark") setDark(value);
      if (key === "motion") setMotion(value);
      setSnapshot((s) => ({ ...s, preferences: result }));
    }
  }
  async function connectModel(m) {
    const r = await run("model", { name: m }, "Connecting selected model");
    if (r) { setModel(r); setOllama((o) => ({ ok: true, models: o?.models?.length ? o.models : [r] })); }
    return r;
  }
  async function copy(text) { try { await call("copy", { text }); } catch (e) { setError(e.message); } }
  async function newSession() {
    const result = await run("session_new");
    if (result) { setSession(result.id); setMessages([]); setRetry(null); setView("workspace"); }
    return result?.id;
  }
  async function openSession(id) {
    const result = await run("session_get", { id });
    if (!result) return;
    setSession(id);
    setRetry(null);
    setView("workspace");
    setMessages(result.turns.flatMap((t) => [{ role: "You", text: t.question }, { ...t.result, role: "SecureRAG", text: t.result.answer }]));
    const last = result.turns.at(-1);
    if (last) {
      setMode(last.mode);
      const scope = !last.source ? [] : Array.isArray(last.source) ? last.source : [last.source];
      setSelected(scope);
    }
  }
  async function deleteSession() {
    const r = await run("session_delete", { id: session });
    if (r) { setSession(""); setMessages([]); }
  }
  async function upload() {
    const r = await run("upload", {}, "Screening documents: page text, metadata, annotations and attachments");
    if (!r) return;
    const ok = r.files.filter((f) => f.result), failed = r.files.filter((f) => f.error);
    const count = (state) => ok.filter((f) => documentState(f.result) === state).length;
    if (ok.length) { const last = ok.at(-1).result.source; setSource(last); setDecision(null); }
    setToast({
      title: `${plural(r.files.length, "file")} screened`,
      approved: count("Approved"), partial: count("Partially approved"), blocked: count("Blocked"), failed,
      cancelled: r.cancelled ? r.remaining.length : 0, sticky: failed.length > 0,
    });
  }
  async function explain(src) {
    setSource(src);
    setInspOpen(true);
    setInspTab("document");
    const r = await run("decision", { source: src }, "Reading document decision");
    if (r) setDecision(r);
  }
  function focusDocument(src) {
    setSource(src);
    setInspOpen(true);
    setInspTab("document");
    if (decision?.document?.source !== src) setDecision(null);
  }
  async function previewDoc(src) {
    const rows = await run("preview", { source: src });
    if (rows) setPreview({ title: name(src), rows });
  }
  async function removeDoc(src) {
    const r = await run("remove", { source: src });
    if (r) { setSelected((s) => s.filter((x) => x !== src)); if (source === src) { setSource(""); setDecision(null); } }
  }
  function askAbout(src) {
    setSelected([src]);
    setMode("documents");
    setView("workspace");
    setTimeout(() => document.querySelector(".composer textarea")?.focus(), 50);
  }
  const scopeArg = (list) => (!list.length ? null : list.length === 1 ? list[0] : list);
  async function send(question = draft, { overview = false, report = false, scope = null } = {}) {
    if (!question.trim() || locked.current) return;
    setView("workspace");
    const sessionId = session || await newSession();
    if (!sessionId) return;
    setAtBottom(true);
    const useMode = overview || scope ? "documents" : mode;
    const useScope = scope || (useMode === "documents" ? selected : []);
    setMessages((m) => [...(retry?.question === question && m.at(-1)?.role === "You" ? m.slice(0, -1) : m), { role: "You", text: question }]);
    setDraft("");
    const r = await run("ask", { question, mode: useMode, source: useMode === "documents" ? scopeArg(useScope) : null, overview, report, session_id: sessionId },
      useMode === "documents" ? "Searching selected documents under DocumentGuard" : "Screening your message");
    if (r) {
      setRetry(null);
      setMessages((m) => [...m, { ...r, role: "SecureRAG", text: r.answer }]);
      if (r.status === "WITHHELD") { setInspTab("sources"); }
      else if (inspTab === "document" || inspTab === "context") setInspTab("security");
    } else setRetry({ question, opts: { overview, report, scope } });
  }
  function switchMode(next) {
    setMode(next);
    setView("workspace");
    if (next === "documents" && !selected.length && source) setSelected([source]);
  }

  const lastResult = useMemo(() => [...messages].reverse().find((m) => m.role !== "You" && m.status), [messages]);
  const checked = snapshot.events.filter((e) => ["SAFE", "BLOCKED", "QUARANTINED"].includes(e.decision));
  const blockedEvents = checked.filter((e) => e.decision !== "SAFE");
  const approvedPassages = snapshot.documents.reduce((n, d) => n + (d.approved_chunks ?? (d.status === "DEFERRED" ? 0 : d.indexed_chunks)), 0);
  const counts = snapshot.documents.reduce((c, d) => { c[documentState(d)] = (c[documentState(d)] || 0) + 1; return c; }, {});
  const docsMode = mode === "documents";
  const usableDocs = snapshot.documents.filter((d) => d.indexed_chunks).length;
  const scopeLabel = selected.length === 0 ? "all documents" : selected.length === 1 ? name(selected[0]) : `${selected.length} selected documents`;
  const sessionTitle = (snapshot.sessions || []).find((s) => s.id === session)?.title || "New conversation";
  const sessions = (snapshot.sessions || []).filter((s) => !convFilter || s.title.toLowerCase().includes(convFilter.toLowerCase()));

  const paletteItems = useMemo(() => [
    { group: "Commands", id: "new", icon: <Plus size={16} />, title: "New conversation", kind: "Command", run: newSession },
    { group: "Commands", id: "upload", icon: <Upload size={16} />, title: "Upload documents", subtitle: "Screen and add files", kind: "Command", run: upload },
    { group: "Commands", id: "report", icon: <ClipboardList size={16} />, title: "Screening report", subtitle: "Which documents were blocked or allowed", kind: "Command", disabled: !snapshot.documents.length, run: () => send(REPORT_QUESTION, { report: true, scope: [] }) },
    { group: "Commands", id: "chat", icon: <MessagesSquare size={16} />, title: "Switch to Chat", kind: "Command", run: () => switchMode("chat") },
    { group: "Commands", id: "docs", icon: <Files size={16} />, title: "Switch to Documents", kind: "Command", run: () => switchMode("documents") },
    { group: "Commands", id: "insp", icon: <PanelRight size={16} />, title: inspOpen ? "Hide security inspector" : "Show security inspector", keys: ["Ctrl", "I"], kind: "Command", run: () => setInspOpen((s) => !s) },
    { group: "Commands", id: "side", icon: <PanelLeft size={16} />, title: "Toggle sidebar", keys: ["Ctrl", "B"], kind: "Command", run: toggleSide },
    { group: "Commands", id: "theme", icon: dark ? <Sun size={16} /> : <Moon size={16} />, title: dark ? "Light appearance" : "Dark appearance", kind: "Command", run: () => preference("dark", !dark) },
    { group: "Commands", id: "guide", icon: <HelpCircle size={16} />, title: "Setup guide", subtitle: "Install Ollama, choose a model, connect", kind: "Command", run: () => setGuide(true) },
    { group: "Commands", id: "intro", icon: <Play size={16} />, title: "Show the welcome screen", kind: "Command", run: () => setPhase("welcome") },
    { group: "Commands", id: "glow", icon: <Sparkles size={16} />, title: logoGlow ? "Hide the glowing logo backdrop" : "Show the glowing logo backdrop", kind: "Command", run: () => preference("logo_glow", !logoGlow) },
    ...Object.entries(VIEWS).map(([id, title]) => ({ group: "Go to", id, icon: { overview: <LayoutGrid size={16} />, workspace: <MessagesSquare size={16} />, documents: <Files size={16} />, activity: <Activity size={16} />, settings: <SlidersHorizontal size={16} /> }[id], title, kind: "View", run: () => setView(id) })),
    ...snapshot.documents.map((d) => ({ group: "Documents", id: d.source, icon: <TypeBadge source={d.source} />, title: name(d.source), subtitle: documentState(d), kind: "Document", keywords: d.source, run: () => explain(d.source) })),
    ...(snapshot.sessions || []).map((s) => ({ group: "Conversations", id: s.id, icon: <MessageSquare size={16} />, title: s.title, kind: "Conversation", run: () => openSession(s.id) })),
  ], [snapshot, inspOpen, dark, selected, mode, session, logoGlow]);

  function renderAssistant(m) {
    if (m.report) return <><p>{m.text.split("\n")[0]}</p><ReportCard report={m.report} disabled={!!busy} onSelect={explain} /></>;
    if (m.status === "WITHHELD") return <><p>{m.text.split("\n")[0]}</p><WithheldCard items={m.withheld || []} disabled={!!busy} onSelect={explain} /><small className="trail-note">A block can be a false positive: the classifier gives a score, not a reason. Select a row to read the full decision.</small></>;
    return (
      <>
        <p>{m.text}</p>
        {!!m.withheld?.length && <details className="withheld-note"><summary><ShieldAlert size={13} /> {m.withheld.length} related passage{m.withheld.length === 1 ? " was" : "s were"} withheld</summary>
          <WithheldCard items={m.withheld} compact disabled={!!busy} onSelect={explain} /></details>}
      </>
    );
  }

  // ---------------------------------------------------------------- views
  const workspace = (
    <section className={`stage panel glass ${docsMode ? "is-documents" : "is-chat"}`}>
      <header className="stage-head">
        <div className="stage-title">
          <span className="micro">{docsMode ? "Document Q&A" : "Guarded chat"}</span>
          <h2 title={sessionTitle}>{sessionTitle}</h2>
        </div>
        <div className="seg" role="tablist" aria-label="Interface">
          <button role="tab" aria-selected={!docsMode} className={!docsMode ? "on" : ""} disabled={!!busy} onClick={() => switchMode("chat")}><MessagesSquare size={14} /> Chat</button>
          <button role="tab" aria-selected={docsMode} className={docsMode ? "on" : ""} disabled={!!busy} onClick={() => switchMode("documents")}><Files size={14} /> Documents</button>
          <i className="seg-glow" aria-hidden="true" />
        </div>
        <div className="stage-actions">
          <button className="btn ghost sm" disabled={!!busy} onClick={newSession} aria-label="New conversation"><Plus size={14} /> <span>New</span></button>
          {session && <button className="icon-btn ghost" disabled={!!busy} aria-label="Delete chat" title="Delete this conversation" onClick={deleteSession}><Trash2 size={14} /></button>}
        </div>
      </header>
      <div className="stage-body">
        {docsMode && <DocPicker documents={snapshot.documents} selected={selected} setSelected={setSelected} disabled={!!busy} onUpload={upload} />}
        <div className="chat-main">
          <div className="mode-bar">
            {docsMode ? (
              <>
                <span className="mode-info"><BookOpen size={14} /> Answering from <b>{scopeLabel}</b> · only approved passages reach the model</span>
                <span className="mode-actions">
                  <button disabled={!!busy || !selected.length} onClick={() => send(`Summarize ${selected.length > 1 ? "these documents" : "this document"} and explain the main points.`, { overview: true, scope: selected })}><Sparkles size={13} /> <span>Summarize</span></button>
                  <button disabled={!!busy || !snapshot.documents.length} onClick={() => send(REPORT_QUESTION, { report: true })}><ClipboardList size={13} /> <span>Screening report</span></button>
                </span>
              </>
            ) : (
              <span className="mode-info"><ShieldCheck size={14} /> PromptGuard screens every message{usableDocs ? <> · related passages from <b>{plural(usableDocs, "approved document")}</b> are used automatically</> : " · add documents to let answers draw on them"}</span>
            )}
          </div>
          <div className="messages-wrap">
            <div className="messages" aria-live="polite" ref={scroller} onScroll={(e) => { const b = e.currentTarget; setAtBottom(b.scrollHeight - b.scrollTop - b.clientHeight < 80); }}>
              {!messages.length && (
                <div className="hello">
                  <span className="hello-mark"><LogoMark size={88} /></span>
                  <h3>{docsMode ? "Ask across your documents" : "Ask anything"}</h3>
                  <p>{docsMode ? "Pick documents on the left, or leave none selected to search the whole library. Blocked passages are never used, and you are told when one is withheld." : "Every message is screened before it reaches your local model. When your documents can help, approved passages are used and cited."}</p>
                  <div className="suggest">
                    {(docsMode
                      ? [["Summarize the selected documents", () => send("Summarize the selected documents and explain the main points.", { overview: true, scope: selected }), !selected.length],
                         ["Which documents were blocked?", () => send(REPORT_QUESTION, { report: true }), !snapshot.documents.length],
                         ["Add documents", upload, false]]
                      : [["What can SecureRAG do?", () => setDraft("What can a secure local RAG assistant do with my documents?"), false],
                         ["Show the screening report", () => send(REPORT_QUESTION, { report: true, scope: [] }), !snapshot.documents.length],
                         ["How do I connect Ollama?", () => setGuide(true), false]]
                    ).map(([label, act, off]) => <button key={label} className="chip-btn ripple" disabled={!!busy || off} onClick={act}>{label}</button>)}
                  </div>
                </div>
              )}
              {messages.map((m, i) => (
                <article key={i} className={`message ${m.role === "You" ? "user" : "assistant"} ${m.status === "BLOCKED" || m.status === "WITHHELD" ? "guarded" : ""}`}>
                  {m.role === "You" ? <p>{m.text}</p> : <>
                    <header>
                      <span className="msg-role">
                        <span className="avatar"><LogoMark size={15} /></span> SecureRAG
                        {m.used_documents && m.status === "ANSWERED" && <span className="msg-tag"><BookOpen size={11} /> {m.documents_used?.length ? m.documents_used.join(", ") : "your documents"}</span>}
                        {m.status === "BLOCKED" && <span className="msg-tag warn"><ShieldAlert size={11} /> PromptGuard</span>}
                        {m.status === "WITHHELD" && <span className="msg-tag warn"><ShieldAlert size={11} /> DocumentGuard</span>}
                      </span>
                      <span className="msg-tools">
                        {m.status && <button aria-label="Inspect this answer" title="Inspect" onClick={() => { setInspOpen(true); setInspTab("security"); }}><Info size={13} /></button>}
                        <button aria-label="Copy message" title="Copy" onClick={() => copy(m.text)}><Copy size={13} /></button>
                      </span>
                    </header>
                    {renderAssistant(m)}
                    {!!m.sources?.length && <div className="citations">{m.sources.map((s, j) => (
                      <button className="citation" key={j} onClick={() => setPreview({ title: `Excerpt ${s.citation || j + 1} · ${name(s.source)}`, rows: [s] })}>
                        <span>{s.citation || j + 1}</span>{name(s.source)}{s.page ? ` · p.${s.page}` : ""}
                      </button>))}</div>}
                  </>}
                </article>
              ))}
              {busy && view === "workspace" && <Thinking text={busy} />}
              {busy && view === "workspace" && <button className="stop" onClick={() => call("cancel").then(() => { if (locked.current) setBusy("Stopping after the current local step…"); }).catch((e) => setError(e.message))}>Stop</button>}
            </div>
            {!atBottom && <button className="to-latest" onClick={() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: motion ? "smooth" : "instant" }); setAtBottom(true); }}><ArrowDown size={14} /> Latest</button>}
          </div>
          {error && (
            <div role="status" className="notice error">
              <span>{error}</span>
              {retry && !busy && <button onClick={() => send(retry.question, retry.opts)}>Retry</button>}
              <button className="icon-btn ghost" aria-label="Dismiss" onClick={() => setError("")}><X size={14} /></button>
            </div>
          )}
          <form className="composer spot" onSubmit={(e) => { e.preventDefault(); send(); }}>
            {docsMode && <div className="composer-scope">
              {selected.length ? selected.slice(0, 4).map((s) => <span key={s} className="scope-chip">{name(s)}<button type="button" aria-label={`Remove ${name(s)} from selection`} onClick={() => setSelected((x) => x.filter((y) => y !== s))}><X size={11} /></button></span>)
                : <span className="scope-chip all">All documents</span>}
              {selected.length > 4 && <span className="scope-chip">+{selected.length - 4} more</span>}
            </div>}
            <textarea aria-label="Message" placeholder={docsMode ? `Ask about ${scopeLabel}…` : snapshot.documents.length ? "Ask anything. Related documents are used automatically…" : "Ask anything…"}
              value={draft} onChange={(e) => setDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
            <footer>
              <button type="button" className="round" disabled={!!busy} onClick={upload} aria-label="Attach document" title="Add documents"><Plus size={17} /></button>
              <span className="composer-hint"><Kbd>Enter</Kbd> send <Kbd>Shift</Kbd><Kbd>Enter</Kbd> new line</span>
              <button className="round send ripple" disabled={!!busy || !draft.trim()} aria-label="Send message"><ArrowUp size={17} /></button>
            </footer>
          </form>
        </div>
      </div>
    </section>
  );

  const overview = (
    <div className="page">
      <section className="hero panel glass">
        <div>
          <span className="micro">Overview</span>
          <h1>Your library, under guard</h1>
          <p>Your documents, the language model and every security check run on this computer.</p>
        </div>
        <div className="hero-actions">
          <button className="btn primary" onClick={() => switchMode("chat")}><MessagesSquare size={15} /> Open chat</button>
          <button className="btn ghost" disabled={!!busy} onClick={upload}><Upload size={15} /> Upload documents</button>
        </div>
      </section>
      <div className="metric-row">
        {[["Recent checks", checked.length, "Last 30 audit events", ""], ["Blocked checks", blockedEvents.length, "Within recent events", "bad"], ["Approved passages", approvedPassages, "Passed upload screening", "ok"], ["Blocked documents", counts.Blocked || 0, `${plural(snapshot.documents.length, "document")} in the library`, "bad"]].map(([t, v, s, tone], i) => (
          <section className={`metric panel glass tone-${tone}`} key={t} style={{ "--i": i }}>
            <span>{t}</span><strong><CountUp value={v} motion={motion} /></strong><small>{s}</small>
          </section>
        ))}
      </div>
      <section className="panel glass summary-panel">
        <LibrarySummary items={summaryItems(snapshot.documents)} title="Document screening" onPick={(id) => { setLibFilter(id); setView("documents"); }}
          action={<button className="btn ghost sm" onClick={() => setView("documents")}>Open library</button>} />
      </section>
      <div className="overview-grid">
        <section className="card panel glass">
          <header className="card-head"><h3>Malicious score, recent checks</h3></header>
          <RiskChart events={snapshot.events} />
        </section>
        <section className="card panel glass">
          <header className="card-head"><h3>Recent activity</h3><button className="btn ghost sm" onClick={() => setView("activity")}>View all</button></header>
          <EventList events={snapshot.events.slice(-6)} />
        </section>
      </div>
    </div>
  );

  const shownDocs = snapshot.documents.filter((d) => {
    const s = documentState(d);
    return (libFilter === "all" || stateClass[s] === libFilter) && name(d.source).toLowerCase().includes(libQuery.toLowerCase());
  });
  const documentsView = (
    <div className="page">
      <section className="page-head">
        <div><h1>Documents</h1><p>Every file is screened on upload: page text, metadata, annotations, comments, form fields and attachments.</p></div>
        <div className="hero-actions">
          <button className="btn ghost" disabled={!!busy || !snapshot.documents.length} onClick={() => send(REPORT_QUESTION, { report: true, scope: [] })}><ClipboardList size={15} /> Screening report</button>
          <button className="btn primary" disabled={!!busy} onClick={upload}><Upload size={15} /> Upload</button>
        </div>
      </section>
      <section className="panel glass summary-panel">
        <LibrarySummary items={summaryItems(snapshot.documents)} title="Screening summary" active={libFilter} onPick={setLibFilter} />
      </section>
      <div className="toolbar">
        <label className="field"><Search size={14} /><input value={libQuery} onChange={(e) => setLibQuery(e.target.value)} placeholder="Search documents" aria-label="Search documents" /></label>
        <span className="toolbar-note">{libFilter === "all" ? `${plural(shownDocs.length, "document")}` : <>{shownDocs.length} of {snapshot.documents.length} shown <button className="link" onClick={() => setLibFilter("all")}>Show all</button></>}</span>
      </div>
      <section className="lib-table panel glass">
        <div className="lib-row head"><span>Document</span><span>Decision</span><span>Passages</span><span>Hidden parts</span><span /></div>
        {shownDocs.map((d) => {
          const state = documentState(d);
          return (
            <div key={d.source} className={`lib-row ${source === d.source ? "on" : ""}`} onClick={() => explain(d.source)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && explain(d.source)}>
              <span className="lib-name"><TypeBadge source={d.source} /><span><b title={d.source}>{name(d.source)}</b>{d.block_reason && <small className="bad" title={d.block_reason}>Blocked: {d.block_reason}</small>}</span></span>
              <span><StatePill state={state} /></span>
              <span className="num">{d.indexed_chunks || 0}<small>/{(d.indexed_chunks || 0) + (d.quarantined_chunks || 0)} usable</small></span>
              <span className="num">{d.hidden_checked ?? "–"}{d.hidden_flagged ? <small className="bad"> · {d.hidden_flagged} flagged</small> : <small> checked</small>}</span>
              <span className="row-actions" onClick={(e) => e.stopPropagation()}>
                <button className="icon-btn ghost" title="Ask about this document" aria-label={`Ask about ${name(d.source)}`} disabled={!!busy || !d.indexed_chunks} onClick={() => askAbout(d.source)}><MessageSquare size={14} /></button>
                <button className="icon-btn ghost" title="Preview" aria-label={`Preview ${name(d.source)}`} disabled={!!busy} onClick={() => previewDoc(d.source)}><Eye size={14} /></button>
                <button className="icon-btn ghost danger" title="Remove" aria-label={`Remove ${name(d.source)}`} disabled={!!busy} onClick={() => removeDoc(d.source)}><Trash2 size={14} /></button>
              </span>
            </div>
          );
        })}
        {!shownDocs.length && <Empty icon={<Files size={22} />} title={snapshot.documents.length ? "No documents match" : "No documents yet"}>{snapshot.documents.length ? "Try another filter." : "Upload PDF, Word, text or Markdown files to begin."}</Empty>}
      </section>
    </div>
  );

  const activityView = (
    <div className="page">
      <section className="page-head"><div><h1>Security activity</h1><p>Every screening decision is written to a local audit log. These are the latest 30 events.</p></div></section>
      <section className="card panel glass"><header className="card-head"><h3>Malicious score over time</h3></header><RiskChart events={snapshot.events} /></section>
      <section className="card panel glass"><EventList events={snapshot.events} full /></section>
    </div>
  );

  const settingsView = (
    <div className="page settings">
      <section className="page-head"><div><h1>Settings</h1><p>Everything here applies to this computer only.</p></div>
        <div className="hero-actions"><button className="btn ghost" onClick={() => setGuide(true)}><HelpCircle size={15} /> Setup guide</button></div></section>
      <section className="card panel glass">
        <header className="card-head"><span className="micro">Local model</span><h3>Ollama</h3></header>
        <div className={`ollama-status inline ${ollama?.ok ? "ok" : ollama ? "bad" : ""}`}><i /><div><strong>{!ollama ? "Not checked" : ollama.ok ? "Ollama is running" : "Ollama is not reachable"}</strong><small>{ollama?.ok ? `Connected model: ${snapshot.model || "none"}` : "Open the setup guide to install and start Ollama."}</small></div></div>
        <div className="model-select">
          <select id="model" aria-label="Ollama model" value={model} disabled={!!busy} onChange={(e) => setModel(e.target.value)}>
            {[...new Set([snapshot.model, ...models].filter(Boolean))].map((m) => <option key={m}>{m}</option>)}
          </select>
          <button className="icon-btn" aria-label="Refresh Ollama models" disabled={!!busy || checking} onClick={checkOllama}><RefreshCw size={15} className={checking ? "spin" : ""} /></button>
          <button className="btn primary" disabled={!!busy || !model} onClick={() => connectModel(model)}>Connect model</button>
        </div>
      </section>
      <section className="card panel glass">
        <header className="card-head"><span className="micro">Document screening</span><h3>DocumentGuard</h3></header>
        <SettingRow title="Screen documents on upload" detail={snapshot.preferences?.screen_documents_on_upload === false
          ? "Upload screening OFF: new files are stored unchecked. Retrieved passages must still pass DocumentGuard before reaching the model."
          : "Upload screening ON: page text and hidden content are checked; suspicious passages are quarantined and a malicious hidden part blocks the whole file."}>
          <Switch label="Screen documents on upload" checked={snapshot.preferences?.screen_documents_on_upload !== false} disabled={!!busy} onChange={(v) => preference("screen_documents_on_upload", v)} />
        </SettingRow>
        <SettingRow title="Local OCR (read text in images)" detail={`Reads text that exists only as pixels (scanned pages, screenshots, images in PDF and Word files) so it is screened too. Slower uploads. ${snapshot.ocr_available ? "Tesseract is installed." : "Tesseract is not installed; see the setup guide."}`}>
          <Switch label="Local OCR" checked={!!snapshot.preferences?.ocr} disabled={!!busy} onChange={(v) => preference("ocr", v)} />
        </SettingRow>
        <p className="insp-muted small">Existing files keep their upload decision. Remove and re-upload them to apply a changed setting.</p>
      </section>
      <section className="card panel glass">
        <header className="card-head"><span className="micro">Appearance</span><h3>Look and feel</h3></header>
        <SettingRow title="Dark appearance"><Switch label="Dark appearance" checked={dark} onChange={(v) => preference("dark", v)} /></SettingRow>
        <SettingRow title="Glowing logo backdrop" detail="The SecureRAG logo glowing behind the panels on the right. Off leaves a plain dark background."><Switch label="Glowing logo backdrop" checked={logoGlow} onChange={(v) => preference("logo_glow", v)} /></SettingRow>
        <SettingRow title="Starfield background" detail="Animated night sky behind the glass. Off shows the graphite finish."><Switch label="Starfield background" checked={starfield} onChange={(v) => preference("starfield", v)} /></SettingRow>
        <SettingRow title="Interface motion" detail="Transitions, light sweeps and counters."><Switch label="Interface motion" checked={motion} onChange={(v) => preference("motion", v)} /></SettingRow>
        <SettingRow title="Show welcome screen at startup" detail="The start-up animation always plays while the security models load."><Switch label="Show welcome screen at startup" checked={showAtStartup} onChange={setShowAtStartup} /></SettingRow>
        <SettingRow title="Welcome screen" detail="Open the welcome screen again without restarting."><button className="btn ghost sm" onClick={() => setPhase("welcome")}><Play size={13} /> Show now</button></SettingRow>
      </section>
      <section className="card panel glass">
        <header className="card-head"><span className="micro">Security models</span><h3>Guards</h3></header>
        <div className="runtime-grid wide">
          <div><small>PromptGuard</small><b>{snapshot.guards?.prompt?.model || "FINAL · DeBERTa-v3-small"}</b><em>threshold {score3(snapshot.guards?.prompt?.threshold ?? 0.5)}</em></div>
          <div><small>DocumentGuard</small><b>{snapshot.guards?.document?.model || "v3 seed 2 · DeBERTa-v3-small"}</b><em>threshold {score3(snapshot.guards?.document?.threshold ?? 0.5)}</em></div>
        </div>
      </section>
      {snapshot.legacy_storage && <section className="card panel glass">
        <header className="card-head"><span className="micro">Storage</span><h3>Earlier document library found</h3></header>
        <p className="insp-muted">Import approved excerpts into encrypted storage. Plaintext files are kept for recovery.</p>
        <button className="btn ghost" disabled={!!busy} onClick={() => run("migrate", {}, "Migrating document library")}>Import earlier library</button>
      </section>}
    </div>
  );

  const content = { workspace, overview, documents: documentsView, activity: activityView, settings: settingsView }[view];

  return (
    <div className={`app phase-${phase} ${sideCollapsed ? "side-collapsed" : ""} ${sideCollapsed && peek ? "side-peek" : ""} ${inspOpen ? "insp-open" : ""} ${narrow ? "narrow" : ""}`}>
      <div className="backdrop" aria-hidden="true">{logoGlow && <Emblem />}<i className="streak s1" /><i className="grain" /></div>
      {starfield && <Starfield motion={motion} dark={dark} />}

      <div className="shell" aria-hidden={phase === "boot" || phase === "welcome"}>
      <header className="titlebar">
        <div className="tb-left">
          <button className="icon-btn ghost" aria-label="Toggle sidebar" title="Toggle sidebar (Ctrl+B)" aria-expanded={!sideCollapsed} onClick={toggleSide}><PanelLeft size={16} /></button>
          <nav className="crumbs"><span>SecureRAG</span><i>/</i><b>{VIEWS[view]}</b></nav>
        </div>
        <button className="tb-search" onClick={() => setPalette(true)} aria-label="Search and commands">
          <Search size={14} /><span>Search documents, conversations, commands…</span><span className="keys"><Kbd>Ctrl</Kbd><Kbd>K</Kbd></span>
        </button>
        <div className="tb-right">
          <span className={`guard-pill ${busy === "Loading security models" ? "loading" : ""}`}><ShieldCheck size={13} /> {busy === "Loading security models" ? "Starting guards" : "Guard active"}</span>
          <button className="icon-btn ghost" aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} disabled={!!busy} onClick={() => preference("dark", !dark)}>{dark ? <Sun size={16} /> : <Moon size={16} />}</button>
          <button className={`icon-btn ghost ${inspOpen ? "on" : ""}`} aria-label="Toggle security inspector" title="Security inspector (Ctrl+I)" onClick={() => setInspOpen((s) => !s)}><PanelRight size={16} /></button>
        </div>
      </header>

      <div className="frame">
        <div className="side-slot">
        <aside className="sidebar panel glass" onMouseEnter={peekIn} onMouseLeave={peekOut}>
          <div className="side-inner">
          <div className="brand">
            <span className="brand-mark"><LogoMark size={24} /></span>
            <div className="label">SecureRAG<small>Private, on this computer</small></div>
          </div>
          <nav className="nav-list">
            {[["overview", <LayoutGrid size={16} />], ["workspace", <MessagesSquare size={16} />], ["documents", <Files size={16} />], ["activity", <Activity size={16} />], ["settings", <SlidersHorizontal size={16} />]].map(([id, icon]) => (
              <button key={id} data-nav={id} title={VIEWS[id]} className={`nav ${view === id ? "active" : ""}`} onClick={() => setView(id)}>
                {icon}<span className="label">{VIEWS[id]}</span>
                {id === "activity" && blockedEvents.length > 0 && <em className="label count">{blockedEvents.length}</em>}
                {id === "documents" && snapshot.documents.length > 0 && <em className="label count soft">{snapshot.documents.length}</em>}
              </button>
            ))}
          </nav>

          <div className="side-section conv"><div className="side-clip">
            <div className="section-head">
              <button className="section-toggle" onClick={() => setOpenSections((s) => ({ ...s, conv: !s.conv }))}><ChevronDown size={13} className={openSections.conv ? "" : "rot"} /><span className="label">Conversations</span></button>
              <span className="section-actions label">
                <button aria-label="Search conversations" title="Search conversations" onClick={() => setConvFilter((f) => (f === null ? "" : null))}><Search size={13} /></button>
                <button aria-label="New saved conversation" title="New conversation" disabled={!!busy} onClick={newSession}><Plus size={14} /></button>
              </span>
            </div>
            {openSections.conv && <div className="session-list label">
              {convFilter !== null && <label className="field sm"><Search size={12} /><input autoFocus value={convFilter} onChange={(e) => setConvFilter(e.target.value)} placeholder="Filter conversations" /></label>}
              {groupSessions(sessions).map(([group, list]) => (
                <div key={group} className="session-group">
                  <small>{group}</small>
                  {list.slice(0, 12).map((s) => <button key={s.id} className={`session ${session === s.id ? "active" : ""}`} disabled={!!busy} onClick={() => openSession(s.id)} title={s.title}>{s.title}</button>)}
                </div>
              ))}
              {!sessions.length && <p className="side-empty">No conversations yet.</p>}
            </div>}
          </div></div>

          <div className="side-section grow">
            <div className="section-head">
              <button className="section-toggle" onClick={() => setOpenSections((s) => ({ ...s, lib: !s.lib }))}><ChevronDown size={13} className={openSections.lib ? "" : "rot"} /><span className="label">Document library</span></button>
              <span className="section-actions">
                <button aria-label="Screening report" title="Screening report" disabled={!!busy || !snapshot.documents.length} onClick={() => send(REPORT_QUESTION, { report: true, scope: [] })}><ClipboardList size={13} /></button>
                <button aria-label="Add document" title="Add documents" disabled={!!busy} onClick={upload}><Plus size={14} /></button>
              </span>
            </div>
            {openSections.lib && <div className="documents">
              {snapshot.documents.map((d) => {
                const state = documentState(d);
                return (
                  <button key={d.source} className={`doc st-${stateClass[state]} ${source === d.source ? "selected" : ""}`} disabled={!!busy} onClick={() => focusDocument(d.source)} title={`${name(d.source)} · ${state}${d.block_reason ? ` · ${d.block_reason}` : ""}`}>
                    <TypeBadge source={d.source} />
                    <span className="label doc-name">{name(d.source)}</span>
                    <i className={`state-dot ${stateClass[state]}`} aria-label={state} />
                  </button>
                );
              })}
              {!snapshot.documents.length && <p className="side-empty label">Add a document to begin.</p>}
            </div>}
          </div>

          <button className={`runtime-card ${ollama?.ok ? "ok" : ollama ? "bad" : ""}`} onClick={() => setView("settings")} title="Local runtime settings">
            <div className="rt-top"><span><span className="rt-lamp"><i className="rt-dot" /></span><span className="label">Local runtime</span></span><code className="label">:11434</code></div>
            <div className="rt-bottom label"><span><Cpu size={12} /> {snapshot.model || "no model"}</span><span className="on-device"><Lock size={10} /> on-device</span></div>
          </button>
          </div>
        </aside>
        </div>

        <main className="content">{content}</main>

        <div className="insp-slot">
        <Inspector open={inspOpen} tab={inspTab} setTab={setInspTab} onClose={() => setInspOpen(false)} result={lastResult} snapshot={snapshot}
          selected={selected} setSelected={setSelected} mode={mode} source={source} decision={decision} busy={!!busy}
          actions={{ explain, preview: previewDoc, ask: askAbout, remove: removeDoc,
            summarize: (src) => send("Summarize this document and explain its main points.", { overview: true, scope: [src] }) }} />
        </div>
      </div>
      </div>

      {toast && (
        <div className="toast panel glass batch-results" role="status">
          <div className="toast-head"><ShieldCheck size={15} /><strong>{toast.title}</strong><button className="icon-btn ghost" aria-label="Dismiss" onClick={() => setToast(null)}><X size={14} /></button></div>
          <div className="toast-counts">
            <span className="chip approved"><b>{toast.approved}</b> approved</span>
            {!!toast.partial && <span className="chip partial"><b>{toast.partial}</b> partial</span>}
            <span className="chip blocked"><b>{toast.blocked}</b> blocked</span>
            {!!toast.failed.length && <span className="chip blocked"><b>{toast.failed.length}</b> failed</span>}
          </div>
          {toast.failed.map((f, i) => <p key={i} className="toast-fail"><b>{name(f.filename)}</b>: {f.error}</p>)}
          {!!toast.cancelled && <p className="toast-fail">Stopped; {plural(toast.cancelled, "file")} not completed.</p>}
          <button className="btn ghost sm" onClick={() => { setView("documents"); setToast(null); }}>View library</button>
        </div>
      )}

      {preview && <div className="overlay" onClick={() => setPreview(null)}>
        <section className="preview-modal panel glass" role="dialog" aria-modal="true" aria-label={preview.title} onClick={(e) => e.stopPropagation()}>
          <header><h2>{preview.title}</h2><button className="btn ghost sm" autoFocus onClick={() => setPreview(null)}>Close</button></header>
          <p className="insp-muted">Exact extracted text. A citation does not automatically verify a claim.</p>
          {preview.rows.map((r, i) => <article key={i} className={`preview-excerpt ${r.decision === "QUARANTINED" ? "quarantined" : ""}`}>
            <strong>{r.decision || "SAFE"} · {r.page ? `Page ${r.page}` : r.section || "Text"} · passage {r.chunk_index + 1}</strong>
            {typeof r.score === "number" && <small>Classifier score {r.score.toFixed(4)}</small>}
            <pre>{r.text || "Re-upload this file to view its original excerpt."}</pre>
          </article>)}
        </section>
      </div>}

      <CommandPalette open={palette} onClose={() => setPalette(false)} items={paletteItems} />
      {phase !== "app" && <Splash phase={phase} ready={ready} status={busy} motion={motion} ollama={ollama} model={snapshot.model}
        onOpen={enterApp} onGuide={() => setGuide(true)} guideOpen={guide} showAtStartup={showAtStartup} setShowAtStartup={setShowAtStartup}
        onWarpDone={() => setPhase("app")} />}
      <SetupGuide open={guide} onClose={() => setGuide(false)} onCopy={copy} ollama={ollama} onCheckOllama={checkOllama} checking={checking}
        onConnect={async (m) => { await connectModel(m); }} ocrAvailable={snapshot.ocr_available}
        finishLabel={phase === "app" ? "Done" : "Open workspace"} onFinish={() => { setView("workspace"); if (phase === "app") setGuide(false); else enterApp(); }} />
    </div>
  );
}

function EventList({ events, full }) {
  const rows = [...events].reverse();
  if (!rows.length) return <Empty icon={<Activity size={22} />} title="No decisions recorded yet">Screening decisions appear here as you upload and ask.</Empty>;
  return (
    <div className={`event-list ${full ? "full" : ""}`}>
      {rows.map((e, i) => {
        const bad = ["BLOCKED", "QUARANTINED", "WITHHELD"].includes(e.decision);
        return (
          <div className="event" key={`${e.time}-${i}`}>
            <i className={`state-dot ${bad ? "blocked" : e.decision === "SAFE" || e.decision === "RETURNED" ? "approved" : "unchecked"}`} />
            <span className="ev-name">{(e.event || "event").replaceAll("_", " ")}</span>
            <span className="ev-detail">{e.reason || (e.source ? name(e.source) : e.label || "")}</span>
            {typeof e.score === "number" && <span className="ev-score">{e.score.toFixed(3)}</span>}
            <span className={`ev-decision ${bad ? "bad" : ""}`}>{e.decision || e.status || "Recorded"}</span>
            <time>{e.time ? new Date(e.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}</time>
          </div>
        );
      })}
    </div>
  );
}
