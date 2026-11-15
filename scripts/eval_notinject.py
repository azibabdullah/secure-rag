"""
Evaluate the frozen final classifier on the existing, never-trained-on
NotInject file. This script does not download or rewrite evaluation data.

Usage:
    python scripts/eval_notinject.py
"""

import json
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_DIR = "models/securerag-classifier-FINAL"
OUT_PATH = Path("data/held_out_eval/notinject.jsonl")
BATCH_SIZE = 32
MAX_LENGTH = 512


def main():
    print("Loading NotInject from {}...".format(OUT_PATH))
    with open(OUT_PATH, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    print("\nLoading model from {}...".format(MODEL_DIR))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
    model.to(device)
    model.eval()

    texts = [r["text"] for r in rows]
    preds = []
    with torch.no_grad():
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            inputs = tokenizer(batch, truncation=True, max_length=MAX_LENGTH,
                               padding=True, return_tensors="pt").to(device)
            logits = model(**inputs).logits
            batch_preds = torch.argmax(logits, dim=-1).cpu().numpy()
            preds.extend(batch_preds.tolist())

    preds = np.array(preds)
    labels = np.array([0] * len(rows))  # all benign
    accuracy = accuracy_score(labels, preds)
    false_positives = int((preds == 1).sum())

    print("\n" + "=" * 60)
    print("NotInject results (final authz-v2 model; deployment selection considered this set)")
    print("=" * 60)
    print("Total examples: {}".format(len(rows)))
    print("Accuracy (correctly identified as benign): {:.4f}".format(accuracy))
    print("False positives (wrongly flagged MALICIOUS): {} / {}".format(false_positives, len(rows)))

    # Breakdown by trigger-word count (the split structure)
    print("\nBy trigger-word count:")
    for split_name in ["NotInject_one", "NotInject_two", "NotInject_three"]:
        mask = np.array([r["split_origin"] == split_name for r in rows])
        if mask.sum() > 0:
            split_acc = accuracy_score(labels[mask], preds[mask])
            print("  {} ({} words): accuracy {:.4f} (n={})".format(
                split_name, split_name[-3:], split_acc, int(mask.sum())))

    # Breakdown by category
    print("\nBy category:")
    from collections import Counter
    categories = [r["category"] for r in rows]
    for cat in sorted(set(categories)):
        mask = np.array([c == cat for c in categories])
        cat_acc = accuracy_score(labels[mask], preds[mask])
        print("  {}: accuracy {:.4f} (n={})".format(cat, cat_acc, int(mask.sum())))


if __name__ == "__main__":
    main()
