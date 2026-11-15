import React, { useEffect, useState } from "react";
import {
  ShieldCheck, FileSearch, Cpu, BookOpen, Copy, Check, RefreshCw, X, ChevronLeft, ChevronRight,
  HardDrive, MemoryStick, Monitor, Wifi, Download, Boxes, Plug, ScanText, Sparkles,
} from "lucide-react";
import { Kbd } from "./Shared";
import { LogoMark } from "./Logo";

function CopyLine({ text, onCopy, label }) {
  const [done, setDone] = useState(false);
  return (
    <div className="copy-line">
      <code>{text}</code>
      <button type="button" aria-label={label || `Copy ${text}`} onClick={async () => { await onCopy(text); setDone(true); setTimeout(() => setDone(false), 1400); }}>
        {done ? <Check size={13} /> : <Copy size={13} />} {done ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

function OllamaStatus({ status, onCheck, checking }) {
  return (
    <div className={`ollama-status ${status?.ok ? "ok" : status ? "bad" : ""}`}>
      <i />
      <div>
        <strong>{!status ? "Ollama not checked yet" : status.ok ? `Ollama is running · ${status.models.length} model${status.models.length === 1 ? "" : "s"} installed` : "Ollama is not reachable"}</strong>
        <small>{!status ? "Check whether Ollama is running on this computer." : status.ok ? (status.models.length ? status.models.join(" · ") : "No model downloaded yet. Run the pull command above.") : "Install Ollama and make sure it is running (look for the llama icon near the clock)."}</small>
      </div>
      <button type="button" disabled={checking} onClick={onCheck}><RefreshCw size={13} className={checking ? "spin" : ""} /> {checking ? "Checking" : "Check"}</button>
    </div>
  );
}

const MODELS = [
  { id: "llama3:8b", tag: "Recommended", size: "4.7 GB download", ram: "8 GB RAM or more", text: "The model SecureRAG was tested with. Best balance of answer quality and speed for document questions." },
  { id: "llama3.2:3b", tag: "Lightweight", size: "2.0 GB download", ram: "Laptops with 8 GB RAM", text: "Faster and smaller. Good for older or low-memory computers; answers are shorter and less precise." },
  { id: "qwen2.5:7b", tag: "Alternative", size: "4.7 GB download", ram: "8 GB RAM or more", text: "Strong at following instructions and keeping citations. Try it if answers ignore the excerpt numbers." },
];

// The guide is a sheet that slides in from the right edge. It opens over
// whatever is on screen (the welcome screen or the app) and never navigates.
export function SetupGuide({ open, onClose, onCopy, ollama, onCheckOllama, checking, onConnect, onFinish, ocrAvailable, finishLabel = "Done" }) {
  const [step, setStep] = useState(0);
  const [shown, setShown] = useState(open);
  useEffect(() => {
    if (open) { setShown(true); return; }
    const t = setTimeout(() => setShown(false), 380);   // let the sheet slide out first
    return () => clearTimeout(t);
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const esc = (e) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    window.addEventListener("keydown", esc, true);
    return () => window.removeEventListener("keydown", esc, true);
  }, [open, onClose]);
  if (!shown) return null;
  const steps = [
    { icon: <Monitor size={15} />, title: "Before you start" },
    { icon: <Download size={15} />, title: "Install Ollama" },
    { icon: <Boxes size={15} />, title: "Choose a model" },
    { icon: <Plug size={15} />, title: "Connect SecureRAG" },
    { icon: <ScanText size={15} />, title: "Optional: OCR" },
    { icon: <Sparkles size={15} />, title: "You're ready" },
  ];
  const body = [
    <>
      <h2>What you need</h2>
      <p className="lead">SecureRAG runs completely on this computer. Your documents, the language model and both security models never leave it.</p>
      <div className="req-grid">
        <div><Monitor size={18} /><strong>Windows 10 or 11</strong><small>64-bit</small></div>
        <div><MemoryStick size={18} /><strong>8 GB RAM minimum</strong><small>16 GB recommended</small></div>
        <div><HardDrive size={18} /><strong>About 6 GB free</strong><small>for one language model</small></div>
        <div><Cpu size={18} /><strong>Graphics card optional</strong><small>it makes answers faster</small></div>
      </div>
      <p className="hint"><Wifi size={14} /> Internet is needed only once, to download Ollama and a model. After that SecureRAG works offline.</p>
    </>,
    <>
      <h2>Install Ollama</h2>
      <p className="lead">Ollama is the free program that runs the language model on your computer. SecureRAG talks to it locally.</p>
      <ol className="steps-list">
        <li>Open this address in your browser and download the Windows installer:<CopyLine text="https://ollama.com/download" onCopy={onCopy} label="Copy Ollama download link" /></li>
        <li>Run <b>OllamaSetup.exe</b> and follow the installer. Ollama starts automatically and keeps running in the background (llama icon near the clock).</li>
        <li>Check it installed: open <b>PowerShell</b> and run<CopyLine text="ollama --version" onCopy={onCopy} /></li>
      </ol>
    </>,
    <>
      <h2>Choose a model</h2>
      <p className="lead">Download one model with the command on its card. You can install more later and switch between them in Settings.</p>
      <div className="model-cards">
        {MODELS.map((m) => (
          <div key={m.id} className={`model-card ${m.tag === "Recommended" ? "rec" : ""}`}>
            <div className="model-top"><strong>{m.id}</strong><span>{m.tag}</span></div>
            <p>{m.text}</p>
            <small>{m.size} · {m.ram}</small>
            <CopyLine text={`ollama pull ${m.id}`} onCopy={onCopy} />
          </div>
        ))}
      </div>
    </>,
    <>
      <h2>Connect SecureRAG</h2>
      <p className="lead">With Ollama running and a model downloaded, connect it here. You can also do this later in Settings, under Local model.</p>
      <OllamaStatus status={ollama} onCheck={onCheckOllama} checking={checking} />
      {ollama?.ok && ollama.models.length > 0 && (
        <div className="connect-list">
          {ollama.models.map((m) => (
            <button key={m} type="button" onClick={() => onConnect(m)}><Cpu size={14} /> Use {m}</button>
          ))}
        </div>
      )}
      <p className="hint">If the check fails: start Ollama from the Start menu, wait a few seconds, then choose Check again.</p>
    </>,
    <>
      <h2>Optional: read text inside images</h2>
      <p className="lead">Scanned pages and screenshots contain text only as pixels. With OCR on, SecureRAG reads that text locally and screens it too. Without OCR, a PDF page with no selectable text is refused.</p>
      <ol className="steps-list">
        <li>Install Tesseract OCR from PowerShell:<CopyLine text="winget install UB-Mannheim.TesseractOCR" onCopy={onCopy} /></li>
        <li>Restart SecureRAG, then turn on <b>Local OCR</b> in Settings.</li>
      </ol>
      <p className={`hint ${ocrAvailable ? "ok" : ""}`}><ScanText size={14} /> {ocrAvailable ? "Tesseract is installed on this computer." : "Tesseract is not installed yet. You can skip this step."}</p>
    </>,
    <>
      <h2>You're ready</h2>
      <p className="lead">A quick tour of how SecureRAG works.</p>
      <div className="tour">
        <div><ShieldCheck size={18} /><strong>Chat</strong><small>Ask anything. PromptGuard screens every message, and approved passages from your documents are used when they help.</small></div>
        <div><FileSearch size={18} /><strong>Documents</strong><small>Pick one or more files and ask questions about them. Blocked passages are never used, and you are told why.</small></div>
        <div><BookOpen size={18} /><strong>Security inspector</strong><small>The panel on the right shows the decision, scores, sources and pipeline trace for every answer.</small></div>
        <div><Kbd>Ctrl</Kbd><Kbd>K</Kbd><small>Search documents and conversations, or run any command.</small></div>
      </div>
    </>,
  ];
  const last = step === steps.length - 1;
  return (
    <div className={`sheet-scrim ${open ? "open" : "closing"}`} onClick={onClose}>
      <section className="guide" role="dialog" aria-modal="true" aria-label="Setup guide" onClick={(e) => e.stopPropagation()}>
        <aside className="guide-steps">
          <div className="guide-brand"><LogoMark size={22} /> Setup guide</div>
          {steps.map((s, i) => (
            <button key={i} className={`guide-step ${i === step ? "on" : ""} ${i < step ? "done" : ""}`} aria-current={i === step ? "step" : undefined} onClick={() => setStep(i)}>
              <span className="n">{i < step ? <Check size={12} /> : i + 1}</span>{s.title}
            </button>
          ))}
        </aside>
        <div className="guide-main">
          <button className="icon-btn ghost guide-close" aria-label="Close setup guide" onClick={onClose}><X size={16} /></button>
          <div className="guide-icon">{steps[step].icon}<span>Step {step + 1} of {steps.length}</span></div>
          <div className="guide-body" key={step}>{body[step]}</div>
          <footer className="guide-foot">
            <button className="btn ghost" disabled={step === 0} onClick={() => setStep(step - 1)}><ChevronLeft size={14} /> Back</button>
            <div className="dots">{steps.map((_, i) => <i key={i} className={i === step ? "on" : ""} />)}</div>
            {last
              ? <button className="btn primary" onClick={() => { setStep(0); onFinish(); }}>{finishLabel}</button>
              : <button className="btn primary" onClick={() => setStep(step + 1)}>Next <ChevronRight size={14} /></button>}
          </footer>
        </div>
      </section>
    </div>
  );
}
