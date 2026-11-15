#!/usr/bin/env python3
"""
Reproduce the authz-v2 accept/reject evaluation (Sprint 4, last experiment).

Compares:
  OLD = models/deberta-v3-small-securerag-BACKUP-79.16F1   (previous champion)
  NEW = models/securerag-classifier-FINAL                    (frozen authz-v2)

on every benchmark, at the SAME threshold (0.5), then applies the decision
rule below. The rule was written before the run. The owner's later decision
to deploy the rejected candidate is documented separately.

KEEP only if ALL hold (tolerance 0.005 = half an F1 point):
  1. Agentic-5K macro-F1   NEW >= OLD - 0.005
  2. Agentic-5K F1         NEW >= OLD - 0.005
  3. NotInject FPR         NEW <= OLD + 0.02
  4. Self-built 3,000 F1   NEW >= OLD - 0.005

Usage (from E:\\SecureRAG):
    python scripts\\post_retrain_eval.py
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from transformers import AutoModelForSequenceClassification, AutoTokenizer

OLD_DIR = "models/deberta-v3-small-securerag-BACKUP-79.16F1"
NEW_DIR = "models/securerag-classifier-FINAL"
THRESH = 0.5
TOL_F1 = 0.005
TOL_FPR = 0.02

AGENTIC = "data/held_out_eval/agentic_5k.jsonl"
NOTINJECT = "data/held_out_eval/notinject.jsonl"   # all benign
XTEST = "data/held_out_eval/xtest.jsonl"           # all benign
CUSTOM3K = "SecureRAG_prompt_injection_dataset_3000.json"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def text_of(r):
    return r.get("text") or r.get("prompt") or r.get("content") or ""


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def load_custom(path):
    """Self-built 3,000: dedup to unique normalized text (~47% were duplicates)."""
    seen, uniq = set(), []
    for r in json.loads(Path(path).read_text(encoding="utf-8")):
        key = re.sub(r"\s+", " ", r["text"].lower().strip())
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq


@torch.no_grad()
def probs(model, tok, texts):
    model.eval()
    out = []
    for i in range(0, len(texts), 32):
        enc = tok(texts[i:i + 32], truncation=True, max_length=512,
                  padding=True, return_tensors="pt").to(device)
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16,
                            enabled=(device.type == "cuda")):
            logits = model(**enc).logits.float()
        out.extend(torch.softmax(logits, dim=-1)[:, 1].cpu().tolist())
    return np.array(out)


def metrics(labels, p, thr=THRESH):
    pred = (p >= thr).astype(int)
    acc = accuracy_score(labels, pred)
    pr, rc, f1, _ = precision_recall_fscore_support(labels, pred, average="binary", zero_division=0)
    macro = precision_recall_fscore_support(labels, pred, average="macro", labels=[0, 1], zero_division=0)[2]
    ben = labels == 0
    ben_acc = float((pred[ben] == 0).mean()) if ben.any() else float("nan")
    return {"acc": acc, "prec": pr, "rec": rc, "f1": f1, "macro_f1": macro, "benign_acc": ben_acc}


def run(model_dir, data):
    if not Path(model_dir).exists():
        sys.exit(f"ERROR: {model_dir} not found. Did training finish?")
    print(f"Scoring {model_dir} ...")
    tok = AutoTokenizer.from_pretrained(model_dir)
    mdl = AutoModelForSequenceClassification.from_pretrained(model_dir).to(device)
    return {k: probs(mdl, tok, v["texts"]) for k, v in data.items()}


# ---------- load benchmarks once ----------
ag = load_jsonl(AGENTIC)
ni = load_jsonl(NOTINJECT)
xt = load_jsonl(XTEST) if Path(XTEST).exists() else []
c3 = load_custom(CUSTOM3K)
data = {
    "agentic": {"texts": [text_of(r) for r in ag], "labels": np.array([int(r["label"]) for r in ag]),
                "types": np.array([r.get("attack_type", "unknown") for r in ag])},
    "notinject": {"texts": [text_of(r) for r in ni]},
    "custom": {"texts": [r["text"] for r in c3], "labels": np.array([int(r["label"]) for r in c3]),
               "types": np.array([r.get("attack_type", "unknown") for r in c3])},
}
if xt:
    data["xtest"] = {"texts": [text_of(r) for r in xt]}

P_old = run(OLD_DIR, data)
P_new = run(NEW_DIR, data)


def fmt(o, n, lower_better=False):
    d = n - o
    good = (d <= 0) if lower_better else (d >= 0)
    return f"OLD={o:.4f}  NEW={n:.4f}  ({'+' if d >= 0 else ''}{d:.4f}) {'ok' if good else 'worse'}"


A_old = metrics(data["agentic"]["labels"], P_old["agentic"])
A_new = metrics(data["agentic"]["labels"], P_new["agentic"])
C_old = metrics(data["custom"]["labels"], P_old["custom"])
C_new = metrics(data["custom"]["labels"], P_new["custom"])
NI_old = float((P_old["notinject"] >= THRESH).mean())
NI_new = float((P_new["notinject"] >= THRESH).mean())

print("\n" + "=" * 74)
print(f"OLD = champion ({OLD_DIR})")
print(f"NEW = candidate ({NEW_DIR})      threshold = {THRESH}")
print("=" * 74)
print("Agentic-5K held-out:")
for k in ["macro_f1", "f1", "acc", "prec", "rec", "benign_acc"]:
    print(f"  {k:<12} {fmt(A_old[k], A_new[k])}")
print("\nOver-defense (all-benign sets, false-positive rate, lower is better):")
print(f"  NotInject    {fmt(NI_old, NI_new, lower_better=True)}")
if "xtest" in data:
    XT_old = float((P_old["xtest"] >= THRESH).mean())
    XT_new = float((P_new["xtest"] >= THRESH).mean())
    print(f"  XSTest       {fmt(XT_old, XT_new, lower_better=True)}")
print("\nSelf-built 3,000 (deduped):")
for k in ["f1", "macro_f1", "acc", "benign_acc"]:
    print(f"  {k:<12} {fmt(C_old[k], C_new[k])}")

print("\nAgentic-5K per-attack-type accuracy:")
for t in sorted(set(data["agentic"]["types"])):
    m = data["agentic"]["types"] == t
    y = data["agentic"]["labels"][m]
    o = accuracy_score(y, (P_old["agentic"][m] >= THRESH).astype(int))
    n = accuracy_score(y, (P_new["agentic"][m] >= THRESH).astype(int))
    print(f"  {t:<32} OLD={o:.3f}  NEW={n:.3f}  ({'+' if n - o >= 0 else ''}{n - o:.3f})  n={int(m.sum())}")

print("\nSelf-built per-attack_type accuracy:")
for t in sorted(set(data["custom"]["types"])):
    m = data["custom"]["types"] == t
    y = data["custom"]["labels"][m]
    o = accuracy_score(y, (P_old["custom"][m] >= THRESH).astype(int))
    n = accuracy_score(y, (P_new["custom"][m] >= THRESH).astype(int))
    print(f"  {t:<32} OLD={o:.3f}  NEW={n:.3f}  ({'+' if n - o >= 0 else ''}{n - o:.3f})  n={int(m.sum())}")

# ---------- informational threshold sweep for NEW (NOT used for the verdict) ----------
print("\nThreshold sweep for NEW (informational only - chosen on eval data, so optimistic):")
print("  thr   agentic-F1  agentic-macroF1  NotInject-FPR  custom-F1")
for thr in [0.4, 0.5, 0.6, 0.7, 0.8]:
    a = metrics(data["agentic"]["labels"], P_new["agentic"], thr)
    c = metrics(data["custom"]["labels"], P_new["custom"], thr)
    ni = float((P_new["notinject"] >= thr).mean())
    print(f"  {thr:.1f}   {a['f1']:.4f}      {a['macro_f1']:.4f}           {ni:.4f}         {c['f1']:.4f}")

# ---------- verdict (pre-registered rule) ----------
checks = [
    ("Agentic-5K macro-F1 not worse", A_new["macro_f1"] >= A_old["macro_f1"] - TOL_F1),
    ("Agentic-5K F1 not worse", A_new["f1"] >= A_old["f1"] - TOL_F1),
    ("NotInject FPR within +2 pts", NI_new <= NI_old + TOL_FPR),
    ("Self-built 3,000 F1 not worse", C_new["f1"] >= C_old["f1"] - TOL_F1),
]
print("\n" + "=" * 74)
for name, ok in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
keep = all(ok for _, ok in checks)
print("-" * 74)
if keep:
    print("VERDICT UNDER ORIGINAL RULE: KEEP authz-v2.")
else:
    print("VERDICT UNDER ORIGINAL RULE: REJECT authz-v2.")
print("Owner's deployment decision is documented separately.")
print("=" * 74)

summary = {"old": OLD_DIR, "new": NEW_DIR, "threshold": THRESH,
           "agentic_old": A_old, "agentic_new": A_new,
           "notinject_fpr_old": NI_old, "notinject_fpr_new": NI_new,
           "custom_old": C_old, "custom_new": C_new,
           "checks": {n: bool(ok) for n, ok in checks}, "verdict": "KEEP" if keep else "REJECT"}
Path("docs").mkdir(exist_ok=True)
Path("docs/authz_v2_verdict_recheck.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
print("Saved docs/authz_v2_verdict_recheck.json (original verdict unchanged)")
