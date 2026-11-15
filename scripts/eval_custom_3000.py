"""
Evaluate the current best model against SecureRAG_prompt_injection_dataset_3000.json.

Deduplicates first (47.2% of the original file is exact-repeat text - see
chat for why) so aggregate metrics aren't skewed by sentences that happen
to repeat several times. Breaks results down by attack_type, difficulty,
and source_type, and reports the hard-negative subset (benign_security_discussion)
separately, since that's this dataset's over-defense check.

Usage:
    python scripts/eval_custom_3000.py
"""

import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_DIR = "models/securerag-classifier-FINAL"
DATA_PATH = "SecureRAG_prompt_injection_dataset_3000.json"
MAX_LENGTH = 512
BATCH_SIZE = 32
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_and_dedupe(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    seen = {}
    for d in data:
        seen[d["text"]] = d  # exact-text key - later rows overwrite earlier, labels already verified consistent
    deduped = list(seen.values())
    print("Loaded {} rows, {} unique after dedup ({:.1f}% removed)".format(
        len(data), len(deduped), (1 - len(deduped) / len(data)) * 100))
    return deduped


def get_probabilities(model, tokenizer, texts):
    probs = []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            inputs = tokenizer(batch, truncation=True, max_length=MAX_LENGTH,
                               padding=True, return_tensors="pt").to(DEVICE)
            with torch.autocast(device_type=DEVICE.type, dtype=torch.bfloat16, enabled=(DEVICE.type == "cuda")):
                logits = model(**inputs).logits
            batch_probs = torch.softmax(logits.float(), dim=-1)[:, 1].cpu().numpy()
            probs.extend(batch_probs.tolist())
    return np.array(probs)


def report_metrics(labels, preds, mask=None, name=""):
    if mask is not None:
        labels, preds = labels[mask], preds[mask]
    if len(labels) == 0:
        return
    acc = accuracy_score(labels, preds)
    if len(set(labels)) > 1:
        p, r, f, _ = precision_recall_fscore_support(labels, preds, average="binary", pos_label=1, zero_division=0)
        print("  {:<32} acc={:.4f} prec={:.4f} rec={:.4f} f1={:.4f} (n={})".format(name, acc, p, r, f, len(labels)))
    else:
        # single-class subset (e.g. hard negatives, all label=0) - accuracy is the meaningful number
        print("  {:<32} acc={:.4f} (n={}, single-class)".format(name, acc, len(labels)))


def main():
    print("Loading model from {}...".format(MODEL_DIR))
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.to(DEVICE)

    rows = load_and_dedupe(DATA_PATH)
    texts = [r["text"] for r in rows]
    labels = np.array([int(r["label"]) for r in rows])

    print("\nScoring {} examples...".format(len(texts)))
    probs = get_probabilities(model, tokenizer, texts)
    preds = (probs >= 0.5).astype(int)

    print("\n" + "=" * 70)
    print("OVERALL")
    print("=" * 70)
    report_metrics(labels, preds, name="all")
    cm = confusion_matrix(labels, preds).tolist()
    print("  Confusion matrix [[TN, FP], [FN, TP]]: {}".format(cm))

    print("\n" + "=" * 70)
    print("BY ATTACK TYPE")
    print("=" * 70)
    attack_types = np.array([r["attack_type"] for r in rows])
    for at in sorted(set(attack_types)):
        mask = attack_types == at
        report_metrics(labels, preds, mask, at)

    print("\n" + "=" * 70)
    print("BY DIFFICULTY")
    print("=" * 70)
    difficulties = np.array([r["difficulty"] for r in rows])
    for d in ["easy", "medium", "hard"]:
        mask = difficulties == d
        if mask.sum() > 0:
            report_metrics(labels, preds, mask, d)

    print("\n" + "=" * 70)
    print("BY SOURCE TYPE")
    print("=" * 70)
    source_types = np.array([r["source_type"] for r in rows])
    for st in sorted(set(source_types)):
        mask = source_types == st
        report_metrics(labels, preds, mask, st)

    print("\n" + "=" * 70)
    print("HARD NEGATIVES (benign_security_discussion) - the over-defense check")
    print("=" * 70)
    hn_mask = attack_types == "benign_security_discussion"
    hn_preds = preds[hn_mask]
    hn_fp_rate = (hn_preds == 1).sum() / max(hn_mask.sum(), 1)
    print("  n={}, false-positive rate (flagged MALICIOUS when actually benign): {:.2%}".format(
        hn_mask.sum(), hn_fp_rate))

    # Save false positives/negatives for this dataset for further reading
    eval_dir = Path("data/evaluation")
    eval_dir.mkdir(parents=True, exist_ok=True)
    fps = [rows[i] for i in range(len(labels)) if labels[i] == 0 and preds[i] == 1]
    fns = [rows[i] for i in range(len(labels)) if labels[i] == 1 and preds[i] == 0]
    for name, items in [("custom3000_false_positives", fps), ("custom3000_false_negatives", fns)]:
        with open(eval_dir / "{}.jsonl".format(name), "w", encoding="utf-8") as f:
            for it in items:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        print("\nSaved {} {} to {}".format(len(items), name, eval_dir / (name + ".jsonl")))


if __name__ == "__main__":
    main()
