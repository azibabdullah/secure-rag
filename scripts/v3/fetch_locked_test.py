"""Create the LOCKED public test set (run once, before building the v3 pool).

Source: deepset/prompt-injections (Hugging Face, train + test splits; label 1 =
injection). The professor noted that some public sets are already inside Hlyn,
so every item that leaks into ANY training data used by either model (the old
data/processed pool, which trained FINAL, and the indirect-docs training pairs)
is removed. This keeps the comparison fair to both models.

Writes data/locked_test/deepset_prompt_injections.jsonl and
data/locked_test/MANIFEST.json (SHA-256 of every locked file). Never train on,
inspect errors from, or tune anything with these files.

Usage (from E:\\SecureRAG):  python scripts\\v3\\fetch_locked_test.py
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leakage import EvalIndex, text_hash  # noqa: E402

OUT = Path("data/locked_test")


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    from datasets import load_dataset
    target = OUT / "deepset_prompt_injections.jsonl"
    if target.exists():
        raise SystemExit(f"{target} already exists; the locked set is created once. Delete it only if it is corrupt.")
    ds = load_dataset("deepset/prompt-injections")
    items, seen = [], set()
    for split in ds:
        for r in ds[split]:
            t = str(r["text"]).strip()
            if t and text_hash(t) not in seen:
                seen.add(text_hash(t))
                items.append({"text": t, "label": int(r["label"]), "source": "deepset/prompt-injections",
                              "original_split": split})
    print(f"downloaded {len(items)} distinct items")

    index = EvalIndex(items)
    leaked = set()
    train_files = [Path("data/processed") / f"{s}.jsonl" for s in ("train", "validation", "test")]
    train_files.append(Path("data/indirect_docs/docs_train.jsonl"))
    for path in train_files:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    leaked |= index.leaks(json.loads(line)["text"])
    clean = [it for i, it in enumerate(items) if i not in leaked]
    print(f"removed {len(leaked)} items already present in training data; {len(clean)} remain "
          f"(injection {sum(r['label'] for r in clean)}, benign {sum(1 - r['label'] for r in clean)})")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        for r in clean:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    manifest = {
        "rule": "Evaluate exactly once, on the final frozen models. Do not train on, tune with, or read errors from these files.",
        "files": {str(target): file_sha(target),
                  "data/indirect_docs/docs_test.jsonl": file_sha("data/indirect_docs/docs_test.jsonl")},
        "removed_for_training_overlap": len(leaked),
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {target} and {OUT / 'MANIFEST.json'}")


if __name__ == "__main__":
    main()
