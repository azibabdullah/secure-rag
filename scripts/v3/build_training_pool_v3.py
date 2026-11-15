"""SecureRAG v3 training pool (professor's recommendations, Nov 2026).

* Starts from the existing de-duplicated pool in data/processed/ (no re-download).
* Caps each large source and label-balances it inside the source, so Hlyn's
  400k rows no longer dominate.
* Adds the real-document indirect-injection minimal pairs (docs_train).
* Removes every training row that leaks any dev or locked-test item.
* Writes data/processed_v3/ ; never touches data/processed/.

Usage (from E:\\SecureRAG):  python scripts\\v3\\build_training_pool_v3.py
"""
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leakage import EvalIndex, text_hash  # noqa: E402

SEED = 42
PER_LABEL_CAP = {"hlyn": 12_500, "bipia_70k": 12_500}   # 25k per source, 50/50
BALANCE_FULLY = {"piguard_curated"}                     # downsample majority label
KEEP_ALL = {"hard_negatives", "hard_positives", "authz_hard_negatives",
            "authz_hard_positives", "docs_train"}       # small targeted sets
VAL_FRACTION = 0.05                                     # monitoring only

ROOT = Path(".")
OUT = ROOT / "data" / "processed_v3"


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def eval_items():
    items = []
    for name, path in [("agentic_5k", "data/held_out_eval/agentic_5k.jsonl"),
                       ("notinject", "data/held_out_eval/notinject.jsonl"),
                       ("xstest", "data/held_out_eval/xtest.jsonl"),
                       ("docs_dev", "data/indirect_docs/docs_dev.jsonl"),
                       ("docs_test", "data/indirect_docs/docs_test.jsonl")]:
        items += [{"text": r["text"], "set": name} for r in read_jsonl(ROOT / path)]
    custom = json.loads((ROOT / "SecureRAG_prompt_injection_dataset_3000.json").read_text(encoding="utf-8"))
    items += [{"text": r["text"], "set": "custom_3000"} for r in custom]
    locked = ROOT / "data" / "locked_test" / "deepset_prompt_injections.jsonl"
    if not locked.exists():
        raise SystemExit("Run scripts\\v3\\fetch_locked_test.py first, so the locked test set can be excluded from training.")
    items += [{"text": r["text"], "set": "locked_deepset"} for r in read_jsonl(locked)]
    return items


def main():
    rng = random.Random(SEED)
    pool, seen = [], set()
    for split in ("train", "validation", "test"):
        for r in read_jsonl(ROOT / "data" / "processed" / f"{split}.jsonl"):
            h = text_hash(r["text"])
            if h in seen:
                continue                      # drops old oversampled copies
            seen.add(h)
            pool.append({"text": r["text"], "label": int(r["label"]),
                         "source": r.get("source", "unknown"),
                         "attack_type": r.get("attack_type", "")})
    for r in read_jsonl(ROOT / "data" / "indirect_docs" / "docs_train.jsonl"):
        if text_hash(r["text"]) not in seen:
            seen.add(text_hash(r["text"]))
            pool.append({"text": r["text"], "label": int(r["label"]), "source": "docs_train",
                         "attack_type": r["attack_type"], "pair_id": r["pair_id"]})
    print(f"distinct pool rows: {len(pool)}")

    index = EvalIndex(eval_items())
    by_source = defaultdict(list)
    removed = Counter()
    for r in pool:
        hits = index.leaks(r["text"])
        if hits:
            for i in hits:
                removed[index.items[i]["set"]] += 1
            continue
        by_source[r["source"]].append(r)
    print("training rows removed for leaking eval items, by eval set:", dict(removed))

    selected = []
    for src, rows in sorted(by_source.items()):
        rng.shuffle(rows)
        pos = [r for r in rows if r["label"] == 1]
        neg = [r for r in rows if r["label"] == 0]
        if src in PER_LABEL_CAP:
            cap = PER_LABEL_CAP[src]
            take = pos[:cap] + neg[:cap]
        elif src in BALANCE_FULLY:
            k = min(len(pos), len(neg))
            take = pos[:k] + neg[:k]
        elif src in KEEP_ALL:
            take = rows
        else:
            raise SystemExit(f"Unknown source {src!r}: add it to a cap rule first.")
        selected += take
        print(f"  {src:22s} available {len(rows):7d} -> kept {len(take):6d} "
              f"(mal {sum(r['label'] for r in take)}, benign {len(take) - sum(r['label'] for r in take)})")

    # Keep minimal pairs together when splitting off the monitoring set.
    groups = defaultdict(list)
    for r in selected:
        groups[r.get("pair_id") or text_hash(r["text"])].append(r)
    keys = sorted(groups)
    rng.shuffle(keys)
    n_val = int(len(keys) * VAL_FRACTION)
    val = [r for k in keys[:n_val] for r in groups[k]]
    train = [r for k in keys[n_val:] for r in groups[k]]
    rng.shuffle(train)

    OUT.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("validation", val)):
        with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats = {"seed": SEED, "train_rows": len(train), "validation_rows": len(val),
             "train_labels": dict(Counter(r["label"] for r in train)),
             "train_sources": dict(Counter(r["source"] for r in train)),
             "removed_for_leakage": dict(removed),
             "caps": {"per_label": PER_LABEL_CAP, "balanced": sorted(BALANCE_FULLY),
                      "keep_all": sorted(KEEP_ALL)}}
    (OUT / "dataset_statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
