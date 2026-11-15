"""
Build the curated PIGuard training addition, from the audit results:
INCLUDE: InjecAgent, hackaprompt-dataset (sampled), BIPIA, jailbreak-classification,
         LLM Augmented set, StruQ+vigil+ChatGPT-Jailbreak, TaskTracker (paired),
         safe-guard-prompt-injection malicious (as-is) + benign (keyword-filtered)
EVAL-ONLY (separate output): xtest-v2-copy

Usage:
    python scripts/build_piguard_curated.py
"""

import json
import random
import re
import hashlib
from collections import defaultdict
from pathlib import Path

random.seed(2026)

TRAIN_JSON = Path("PIGuard/datasets/train.json")
OUT_TRAIN = Path("data/piguard_curated/piguard_curated_v1.jsonl")
OUT_EVAL = Path("data/held_out_eval/xtest.jsonl")

# Same trigger vocabulary used for the earlier keyword-filtering pass
TRIGGER_PATTERNS = [
    r"\bignore\s+(all\s+)?(previous|prior)\s+instructions?\b",
    r"\bdisregard\s+(your\s+)?(guidelines?|instructions?|rules?)\b",
    r"\boverride\b", r"\bbypass(ed|ing)?\b", r"\bjailbreak(s|ing)?\b",
    r"\bDAN\b", r"\bunrestricted\s+(mode|AI)\b", r"\bsystem\s+prompt\b",
    r"\breveal\s+(your\s+)?(system\s+)?prompt\b",
    r"\bno\s+(restrictions?|rules?|guidelines?|content\s+policy)\b",
    r"\bforget\s+(your\s+)?(instructions?|rules?|guidelines?|everything)\b",
    r"\bdisable\s+(safety|content|validation|auth\w*|security)\b",
    r"\bdeveloper\s+mode\b", r"\bprompt\s+injection\b",
    r"\bmalicious\b", r"\battack\s+(string|pattern|attempt|payload)\b",
]
TRIGGER_REGEX = re.compile("|".join(TRIGGER_PATTERNS), re.IGNORECASE)


def norm_hash(t):
    return hashlib.sha256(re.sub(r"\s+", " ", t.strip().lower()).encode()).hexdigest()


def main():
    print("Loading {}...".format(TRAIN_JSON))
    with open(TRAIN_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    print("Total rows: {}".format(len(data)))

    final_rows = []
    seen_hashes = set()

    def add_rows(rows, category, cap=None):
        added = 0
        pool = rows if cap is None else rows[:cap]
        for r in pool:
            text = r.get("prompt", "").strip()
            label = int(r.get("label"))
            if not text:
                continue
            h = norm_hash(text)
            if h in seen_hashes:
                continue
            seen_hashes.add(h)
            final_rows.append({
                "text": text, "label": label, "category": category,
                "source": "piguard:{}".format(r.get("source", category)),
            })
            added += 1
        print("  {}: added {} rows".format(category, added))
        return added

    # --- Straightforward full-inclusion sources ---
    for src_name, cat in [
        ("InjecAgent", "tool_function_abuse"),
        ("BIPIA", "rag_document_embedded"),
        ("jailbreak-classification", "jailbreak_diversity"),
        ("LLM Augmented set", "rag_document_embedded"),
        ("StruQ", "quoted_attacks"),
        ("vigil-jailbreak-ada-002", "jailbreak_diversity"),
        ("ChatGPT-Jailbreak-Prompts", "jailbreak_diversity"),
    ]:
        rows = [item for item in data if item.get("source") == src_name]
        add_rows(rows, cat)

    # --- hackaprompt-dataset: sampled down from 5000 to ~2500 ---
    hackaprompt_rows = [item for item in data if item.get("source") == "hackaprompt-dataset"]
    random.shuffle(hackaprompt_rows)
    add_rows(hackaprompt_rows, "attack_diversity", cap=2500)

    # --- safe-guard-prompt-injection: malicious as-is, benign keyword-filtered ---
    sgpi_mal = [item for item in data if item.get("source") == "safe-guard-prompt-injection"
                and str(item.get("label")) == "1"]
    add_rows(sgpi_mal, "authority_and_general_injection")

    sgpi_benign = [item for item in data if item.get("source") == "safe-guard-prompt-injection"
                   and str(item.get("label")) == "0"]
    sgpi_benign_filtered = [r for r in sgpi_benign if TRIGGER_REGEX.search(r.get("prompt", ""))]
    print("  safe-guard-prompt-injection benign: {} -> {} after keyword filter".format(
        len(sgpi_benign), len(sgpi_benign_filtered)))
    add_rows(sgpi_benign_filtered, "hard_negative_general")

    # --- TaskTracker: minimal-pair extraction (the highest-value source) ---
    tt_rows = [item for item in data if item.get("source") == "TaskTracker"]
    by_prefix = defaultdict(list)
    for r in tt_rows:
        by_prefix[r.get("prompt", "")[:80]].append(r)

    paired_benign, paired_malicious = [], []
    for prefix, rows in by_prefix.items():
        labels_present = set(str(r.get("label")) for r in rows)
        if labels_present == {"0", "1"}:
            ben = next(r for r in rows if str(r.get("label")) == "0")
            mal = next(r for r in rows if str(r.get("label")) == "1")
            paired_benign.append(ben)
            paired_malicious.append(mal)

    print("  TaskTracker: found {} genuine minimal pairs".format(len(paired_malicious)))
    add_rows(paired_malicious, "rag_document_embedded")
    add_rows(paired_benign, "hard_negative_document")

    # If pairs don't cover all malicious rows, add the remainder too (still genuine, just unpaired)
    paired_ids = set(id(r) for r in paired_malicious)
    remaining_malicious = [r for r in tt_rows if str(r.get("label")) == "1" and id(r) not in paired_ids]
    add_rows(remaining_malicious, "rag_document_embedded_unpaired")

    # --- Save training file ---
    random.shuffle(final_rows)
    OUT_TRAIN.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_TRAIN, "w", encoding="utf-8") as f:
        for i, r in enumerate(final_rows):
            r["id"] = "pg_{:05d}".format(i)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    label_counts = {"0": 0, "1": 0}
    for r in final_rows:
        label_counts[str(r["label"])] += 1
    print("\n{} total rows saved to {}".format(len(final_rows), OUT_TRAIN))
    print("Label distribution: {}".format(label_counts))

    # --- Save eval-only xtest set ---
    xtest_rows = [item for item in data if item.get("source") == "xtest-v2-copy"]
    OUT_EVAL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_EVAL, "w", encoding="utf-8") as f:
        for i, r in enumerate(xtest_rows):
            row = {"id": "xtest_{:04d}".format(i), "text": r.get("prompt", ""),
                   "label": 0, "category": "over_defense_eval", "source": "piguard:xtest-v2-copy"}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print("{} rows saved to {} (EVAL ONLY - never trained on)".format(len(xtest_rows), OUT_EVAL))


if __name__ == "__main__":
    main()