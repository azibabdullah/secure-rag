import React from "react";

export const name = (path) => path?.split(/[\\/]/).pop() || "";
export const ext = (path) => (name(path).split(".").pop() || "").toUpperCase().slice(0, 4);
export const plural = (n, word, many = `${word}s`) => `${n} ${n === 1 ? word : many}`;
export const score3 = (v) => (typeof v === "number" ? v.toFixed(3) : "n/a");
export const documentState = (d) =>
  d.status === "DEFERRED" ? "Unchecked" : !d.indexed_chunks ? "Blocked" : d.quarantined_chunks ? "Partially approved" : "Approved";
export const stateClass = { Blocked: "blocked", "Partially approved": "partial", Approved: "approved", Unchecked: "unchecked" };
export const CHANNEL = {
  metadata: "Metadata", annotation: "Annotation", comment: "Comment", form_field: "Form field", attachment: "Attachment",
  javascript: "Script", bookmark: "Bookmark", header: "Header", footer: "Footer", footnote: "Footnote", link: "Link target",
  tracked_change: "Tracked change", unrendered: "Hidden body text", field_code: "Field code", alt_text: "Alt text",
  image_text: "Image text (OCR)", invisible_text: "Invisible text", glossary: "Glossary", unreadable: "Unreadable part",
};

export function Kbd({ children }) {
  return <kbd className="kbd">{children}</kbd>;
}

export function TypeBadge({ source }) {
  const kind = ext(source);
  return <span className={`type-badge t-${kind.toLowerCase()}`}>{kind || "DOC"}</span>;
}

export function StatePill({ state }) {
  return <span className={`state-pill ${stateClass[state] || "unchecked"}`}>{state}</span>;
}

export function Switch({ checked, onChange, disabled, label }) {
  return (
    <label className={`switch ${checked ? "on" : ""} ${disabled ? "disabled" : ""}`}>
      <input type="checkbox" role="switch" aria-label={label} checked={!!checked} disabled={disabled}
        onChange={(e) => onChange(e.target.checked)} />
      <i aria-hidden="true" />
    </label>
  );
}

// Settings-style row: label + description on the left, control on the right.
export function SettingRow({ title, detail, children, className = "" }) {
  return (
    <div className={`setting-row toggle-row ${className}`}>
      <div className="setting-text">
        <span>{title}</span>
        {detail && <small>{detail}</small>}
      </div>
      <div className="setting-control">{children}</div>
    </div>
  );
}

export function Thinking({ text }) {
  return (
    <div className="thinking" role="status">
      <span className="orbit"><i /><i /><i /></span>
      <div>
        <strong>{text}</strong>
        <p>Running on this computer · answers are checked before display</p>
      </div>
    </div>
  );
}

export function Empty({ icon, title, children }) {
  return (
    <div className="empty">
      {icon && <span className="empty-icon">{icon}</span>}
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
