"""Score any classifier folder on named evaluation sets and save per-item scores.

Scoring matches the app (src/security/classifier.py): text is split into
overlapping windows of up to 512 tokens (64-token overlap) and the item score
is the highest malicious probability over its windows.

Dev sets can be scored freely. The LOCKED test sets can only be scored with
--unlock-locked-test, and every such run is appended to
data/locked_test/ACCESS_LOG.jsonl so the "evaluate exactly once" rule is
auditable.

Usage (from E:\\SecureRAG):
  python scripts\\v3\\score_v3.py --model models\\securerag-classifier-FINAL --name FINAL --sets dev
  python scripts\\v3\\score_v3.py --model models\\candidates\\v3\\seed1 --name v3-seed1 --sets dev
  python scripts\\v3\\score_v3.py --model ... --name ... --sets locked --unlock-locked-test
"""
import argparse
import hashlib
import json
import sys
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

DEV = {
    "agentic_5k": "data/held_out_eval/agentic_5k.jsonl",
    "docs_dev": "data/indirect_docs/docs_dev.jsonl",
    "notinject": "data/held_out_eval/notinject.jsonl",
    "xstest": "data/held_out_eval/xtest.jsonl",
    "custom_3000": "SecureRAG_prompt_injection_dataset_3000.json",
}
LOCKED = {
    "locked_deepset": "data/locked_test/deepset_prompt_injections.jsonl",
    "locked_docs_test": "data/indirect_docs/docs_test.jsonl",
}
OVERLAP = 64
MAX_LENGTH = 512


def load(path):
    p = Path(path)
    if p.suffix == ".json":
        rows = json.loads(p.read_text(encoding="utf-8"))
        seen, out = set(), []
        for r in rows:                      # the 3,000 set has duplicate texts: score unique ones
            if r["text"] not in seen:
                seen.add(r["text"])
                out.append(r)
        return out
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def windows(tokenizer, text, size):
    ids = tokenizer.encode(text, add_special_tokens=False) or [tokenizer.unk_token_id]
    out, start = [], 0
    while True:
        part = ids[start:start + size]
        out.append([tokenizer.cls_token_id, *part, tokenizer.sep_token_id])
        if start + size >= len(ids):
            return out
        start += size - OVERLAP


@torch.inference_mode()
def score(model, tokenizer, texts, device, batch=32):
    size = MAX_LENGTH - tokenizer.num_special_tokens_to_add(pair=False)
    flat, owner = [], []
    for i, t in enumerate(texts):
        for w in windows(tokenizer, t, size):
            flat.append(w)
            owner.append(i)
    probs = [0.0] * len(texts)
    margins = [-1e9] * len(texts)
    ctx = torch.autocast("cuda", dtype=torch.bfloat16) if device.type == "cuda" else nullcontext()
    for s in range(0, len(flat), batch):
        chunk = flat[s:s + batch]
        enc = tokenizer.pad({"input_ids": chunk, "attention_mask": [[1] * len(c) for c in chunk]},
                            padding=True, return_tensors="pt").to(device)
        with ctx:
            logits = model(**enc).logits.float()
        if not torch.isfinite(logits).all():
            raise RuntimeError("Non-finite logits; scoring stopped.")
        p = torch.softmax(logits, -1)[:, 1].cpu().tolist()
        m = (logits[:, 1] - logits[:, 0]).cpu().tolist()
        for j, (pp, mm) in enumerate(zip(p, m)):
            i = owner[s + j]
            if pp > probs[i]:
                probs[i] = pp
            margins[i] = max(margins[i], mm)
    return probs, margins


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--name", required=True, help="label used in output file names, e.g. FINAL or v3-seed1")
    ap.add_argument("--sets", choices=["dev", "locked"], default="dev")
    ap.add_argument("--unlock-locked-test", action="store_true")
    ap.add_argument("--out-dir", default="data/evaluation/v3_scores")
    ap.add_argument("--limit", type=int, default=None, help="debug only")
    args = ap.parse_args()

    sets = DEV if args.sets == "dev" else LOCKED
    if args.sets == "locked":
        if not args.unlock_locked_test:
            raise SystemExit("The locked test set is evaluated once, on the final models only. "
                             "Re-run with --unlock-locked-test if this is that run.")
        log = Path("data/locked_test/ACCESS_LOG.jsonl")
        log.parent.mkdir(parents=True, exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"time": datetime.now().isoformat(timespec="seconds"),
                                "model": args.model, "name": args.name}) + "\n")
        prior = sum(1 for _ in open(log, encoding="utf-8"))
        print(f"LOCKED TEST ACCESS #{prior} recorded in {log}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(args.model, local_files_only=True).to(device).eval()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.name}__{args.sets}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for set_name, path in sets.items():
            if not Path(path).exists():
                print(f"  [skip] {set_name}: {path} not found")
                continue
            rows = load(path)[: args.limit]
            probs, margins = score(model, tokenizer, [r["text"] for r in rows], device)
            for r, p, m in zip(rows, probs, margins):
                f.write(json.dumps({
                    "set": set_name, "id": hashlib.sha256(r["text"].encode("utf-8")).hexdigest()[:16],
                    "label": int(r["label"]), "attack_type": r.get("attack_type") or r.get("technique") or r.get("category"),
                    "technique": r.get("technique"), "prob": p, "margin": m}) + "\n")
            pos = sum(1 for r, p in zip(rows, probs) if p >= 0.5)
            print(f"  {set_name:18s} n={len(rows):5d}  flagged@0.5={pos}")
    print(f"Scores written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
