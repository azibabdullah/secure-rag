"""
SecureRAG classifier v3 training (Nov 2026 targeted sprint)
============================================================
Implements the training-side recommendations from the course instructor:

* Source-capped, label-balanced data (data/processed_v3, built by
  scripts/v3/build_training_pool_v3.py).
* Model selection on WHOLE held-out sources, never a random split:
  dev = Agentic-5K + indirect-document dev set (docs_dev). Selection metric is
  threshold-free: mean ROC-AUC over those two sets. NotInject and XSTest
  false-positive rates are recorded every epoch.
* 1-3 epochs, LR 2e-5 with 10% warmup, weight decay 0.01, label smoothing 0.1,
  early stopping (stop when the dev score does not improve).
* One run per seed; run the script three times (seeds 1, 2, 3).

Keeps everything that made the old loop work on ROCm: standalone PyTorch loop,
bf16 autocast, non-finite loss/gradient guards, module-level collator,
multiprocessing.freeze_support().

Each run writes ONLY to models/candidates/v3/<run-tag>/. It refuses to write
into the frozen FINAL model or the backup folders.

Usage (from E:\\SecureRAG):
    python scripts\\v3\\train_deberta_v3.py --seed 1 --smoke-test
    python scripts\\v3\\train_deberta_v3.py --seed 1
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup

MODEL_NAME = "microsoft/deberta-v3-small"
DATA_DIR = Path("data/processed_v3")
CANDIDATE_ROOT = Path("models/candidates/v3")
DEV_SETS = {
    "agentic_5k": Path("data/held_out_eval/agentic_5k.jsonl"),
    "docs_dev": Path("data/indirect_docs/docs_dev.jsonl"),
    "notinject": Path("data/held_out_eval/notinject.jsonl"),
    "xstest": Path("data/held_out_eval/xtest.jsonl"),
}
SELECTION_SETS = ("agentic_5k", "docs_dev")   # mean ROC-AUC over these

MAX_LENGTH = 512
TRAIN_BATCH_SIZE = 16
EVAL_BATCH_SIZE = 32
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
MAX_GRAD_NORM = 1.0
LOG_EVERY = 100
LABEL_NAMES = {0: "SAFE", 1: "MALICIOUS"}
PROTECTED = ("securerag-classifier-FINAL", "BACKUP")


class JsonlDataset(Dataset):
    def __init__(self, path, limit=None):
        self.rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    self.rows.append(json.loads(line))
                    if limit and len(self.rows) >= limit:
                        break

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        return self.rows[idx]


class Collator:
    """Module-level class so Windows DataLoader workers (spawn) can pickle it."""

    def __init__(self, tokenizer, max_length):
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __call__(self, batch):
        enc = self.tokenizer([r["text"] for r in batch], truncation=True, max_length=self.max_length,
                             padding=True, return_tensors="pt")
        enc["labels"] = torch.tensor([int(r["label"]) for r in batch], dtype=torch.long)
        return enc


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def malicious_scores(model, loader, device):
    """Return (labels, P(malicious), logit margin) for every row in order."""
    model.eval()
    labels, probs, margins = [], [], []
    for batch in loader:
        y = batch.pop("labels")
        batch = {k: v.to(device) for k, v in batch.items()}
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=(device.type == "cuda")):
            logits = model(**batch).logits.float()
        if not torch.isfinite(logits).all():
            raise RuntimeError("Non-finite logits during evaluation")
        probs.extend(torch.softmax(logits, -1)[:, 1].cpu().tolist())
        margins.extend((logits[:, 1] - logits[:, 0]).cpu().tolist())
        labels.extend(y.tolist())
    model.train()
    return np.array(labels), np.array(probs), np.array(margins)


def summarise(labels, probs):
    pred = probs >= 0.5
    out = {"n": int(len(labels)), "fpr_at_0.5": float(pred[labels == 0].mean()) if (labels == 0).any() else None,
           "tpr_at_0.5": float(pred[labels == 1].mean()) if (labels == 1).any() else None}
    if len(set(labels.tolist())) == 2:
        out["roc_auc"] = float(roc_auc_score(labels, probs))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--run-tag", default=None)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--label-smoothing", type=float, default=0.1)
    ap.add_argument("--model-name", default=MODEL_NAME)
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--smoke-test", action="store_true", help="400 train rows, 200 per dev set, 1 epoch")
    args = ap.parse_args()

    run_tag = args.run_tag or f"seed{args.seed}"
    out_dir = CANDIDATE_ROOT / (("smoke-" if args.smoke_test else "") + run_tag)
    if any(p in str(out_dir) for p in PROTECTED):
        raise SystemExit("Refusing to write into a frozen or backup model folder.")
    if out_dir.exists() and any(out_dir.iterdir()) and not args.smoke_test:
        raise SystemExit(f"{out_dir} already exists. Choose a new --run-tag; candidates are never overwritten.")

    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}" + (f" ({torch.cuda.get_device_name(0)})" if device.type == "cuda" else ""))
    print(f"Run: {run_tag} | seed {args.seed} | lr {args.lr} | label smoothing {args.label_smoothing} | max epochs {args.epochs}")

    limit = 400 if args.smoke_test else None
    dev_limit = 200 if args.smoke_test else None
    epochs = 1 if args.smoke_test else args.epochs

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    collate = Collator(tokenizer, MAX_LENGTH)
    train_ds = JsonlDataset(DATA_DIR / "train.jsonl", limit)
    val_ds = JsonlDataset(DATA_DIR / "validation.jsonl", limit)
    dev = {name: JsonlDataset(path, dev_limit) for name, path in DEV_SETS.items()}
    print(f"train={len(train_ds)} monitor-val={len(val_ds)} " + " ".join(f"{k}={len(v)}" for k, v in dev.items()))

    workers = 0 if args.smoke_test else args.num_workers
    lk = {"collate_fn": collate, "num_workers": workers, "pin_memory": device.type == "cuda"}
    if workers:
        lk["persistent_workers"] = True
    g = torch.Generator()
    g.manual_seed(args.seed)
    train_loader = DataLoader(train_ds, batch_size=TRAIN_BATCH_SIZE, shuffle=True, generator=g, **lk)
    eval_loader = lambda ds: DataLoader(ds, batch_size=EVAL_BATCH_SIZE, shuffle=False, collate_fn=collate)  # noqa: E731

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=2, dtype=torch.float32,
        id2label=LABEL_NAMES, label2id={v: k for k, v in LABEL_NAMES.items()})
    model.to(device)
    model.train()
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)

    no_decay = ["bias", "LayerNorm.weight"]
    optimizer = torch.optim.AdamW([
        {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)], "weight_decay": WEIGHT_DECAY},
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ], lr=args.lr)
    total_steps = len(train_loader) * epochs
    scheduler = get_linear_schedule_with_warmup(optimizer, int(total_steps * WARMUP_RATIO), total_steps)

    best_score, best_epoch, history, skipped = -1.0, 0, [], 0
    start = time.time()
    Path("logs").mkdir(exist_ok=True)
    bad_log = Path("logs") / f"bad_batches_v3_{run_tag}.jsonl"

    for epoch in range(1, epochs + 1):
        running, steps = 0.0, 0
        for step, batch in enumerate(train_loader):
            labels = batch.pop("labels").to(device)
            batch = {k: v.to(device) for k, v in batch.items()}
            with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=(device.type == "cuda")):
                logits = model(**batch).logits
            loss = loss_fn(logits.float(), labels)

            if not torch.isfinite(loss):                      # Guard 1: bad forward pass
                skipped += 1
                with open(bad_log, "a", encoding="utf-8") as bf:
                    bf.write(json.dumps({"epoch": epoch, "step": step, "stage": "forward"}) + "\n")
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()
                continue
            optimizer.zero_grad()
            loss.backward()
            if not all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None):
                skipped += 1                                  # Guard 2: bad gradients
                with open(bad_log, "a", encoding="utf-8") as bf:
                    bf.write(json.dumps({"epoch": epoch, "step": step, "stage": "backward"}) + "\n")
                optimizer.zero_grad(set_to_none=True)
                scheduler.step()
                continue
            grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), MAX_GRAD_NORM)
            optimizer.step()
            scheduler.step()
            running += loss.item()
            steps += 1
            if step % LOG_EVERY == 0:
                done = (epoch - 1) * len(train_loader) + step + 1
                eta = (total_steps - done) / max(done / max(time.time() - start, 1e-9), 1e-9) / 60
                print(f"epoch {epoch}/{epochs} | step {step}/{len(train_loader)} | loss {loss.item():.4f} | "
                      f"grad {grad_norm:.2f} | lr {scheduler.get_last_lr()[0]:.2e} | skipped {skipped} | ETA {eta:.0f} min")

        record = {"epoch": epoch, "train_loss": running / max(steps, 1)}
        y, p, _ = malicious_scores(model, eval_loader(val_ds), device)
        record["monitor_validation"] = summarise(y, p)
        record["dev"] = {}
        for name, ds in dev.items():
            y, p, _ = malicious_scores(model, eval_loader(ds), device)
            record["dev"][name] = summarise(y, p)
        aucs = [record["dev"][s].get("roc_auc") for s in SELECTION_SETS]
        score = float(np.mean([a for a in aucs if a is not None])) if any(a is not None for a in aucs) else 0.0
        record["selection_score"] = score
        history.append(record)
        print(f"\n=== epoch {epoch} | train_loss {record['train_loss']:.4f} | selection (mean dev ROC-AUC) {score:.4f}")
        for name, m in record["dev"].items():
            print(f"    {name:11s} " + " ".join(f"{k}={v:.4f}" for k, v in m.items() if isinstance(v, float)))

        if score > best_score:
            best_score, best_epoch = score, epoch
            out_dir.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(str(out_dir))
            tokenizer.save_pretrained(str(out_dir))
            print(f"  -> new best (epoch {epoch}), saved to {out_dir}\n")
        else:
            print("  -> no improvement on dev; early stopping.\n")
            break

    duration = (time.time() - start) / 60
    meta = {
        "run_tag": run_tag, "seed": args.seed, "base_model": args.model_name, "max_length": MAX_LENGTH,
        "learning_rate": args.lr, "label_smoothing": args.label_smoothing, "weight_decay": WEIGHT_DECAY,
        "warmup_ratio": WARMUP_RATIO, "max_epochs": epochs, "batch_size": TRAIN_BATCH_SIZE,
        "early_stopping": "stop at first epoch without dev improvement",
        "selection_metric": "mean ROC-AUC over " + ", ".join(SELECTION_SETS),
        "best_epoch": best_epoch, "best_selection_score": best_score, "history": history,
        "skipped_batches": skipped, "training_minutes": round(duration, 2),
        "data": str(DATA_DIR), "device": str(device),
        "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else None,
        "finished": datetime.now().isoformat(timespec="seconds"), "smoke_test": args.smoke_test,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "training_metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Done in {duration:.1f} min. Best epoch {best_epoch} (dev score {best_score:.4f}). Saved to {out_dir}")
    if args.smoke_test:
        print("*** SMOKE TEST PASSED ***")


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
