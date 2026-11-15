"""
SecureRAG Dataset Preparation - E-PIGuard experiment
========================================================
Confirmed baseline (Hlyn + BIPIA + final_v2.jsonl hard negatives +
pilot_v1.jsonl hard positives - the exact combination behind the 78.37% F1
result) PLUS the new curated PIGuard addition, as the single tested variable.

Same discipline as every prior version: dedup -> split -> oversample
(training split only), so no duplicated row can leak into validation/test.

Usage:
    python src/security/prepare_dataset.py
"""

import hashlib
import json
import logging
import re
from pathlib import Path

import pandas as pd
import yaml
from datasets import load_dataset
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
log = logging.getLogger(__name__)

CONFIG_PATH = Path("configs/dataset.yaml")
PROCESSED_DIR = Path("data/processed")
HELD_OUT_DIR = Path("data/held_out_eval")
DOCS_DIR = Path("docs")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["dataset"]


def normalized_hash(text):
    return hashlib.sha256(re.sub(r"\s+", " ", text.strip().lower()).encode()).hexdigest()


def load_hlyn(source_cfg):
    log.info("Loading Hlyn (direct injection)...")
    ds = load_dataset(source_cfg["hf_name"])
    df = ds["train"].to_pandas()
    df = df.rename(columns={source_cfg["text_column"]: "text", source_cfg["label_column"]: "label"})
    df = df[["text", "label"]].copy()
    df["source"] = "hlyn"
    df["attack_type"] = df["label"].apply(lambda l: source_cfg["attack_type_default"] if l == 1 else "benign")
    log.info("  Hlyn: {} rows".format(len(df)))
    return df


def load_bipia(source_cfg):
    log.info("Loading BIPIA-70K (indirect injection)...")
    ds = load_dataset(source_cfg["hf_name"])
    df = ds["train"].to_pandas()
    df = df.rename(columns={source_cfg["text_column"]: "text", source_cfg["label_column"]: "label"})
    df = df[["text", "label"]].copy()
    df["source"] = "bipia_70k"
    df["attack_type"] = df["label"].apply(lambda l: source_cfg["attack_type_default"] if l == 1 else "benign_context")
    before = len(df)
    df = df.drop_duplicates(subset=["text"]).reset_index(drop=True)
    log.info("  BIPIA-70K: {} -> {} rows after internal dedup".format(before, len(df)))
    return df


def load_local_source(source_key, source_cfg):
    """Generic loader for any local_path training source (hard_negatives,
    hard_positives, piguard_curated, and any future additions)."""
    path = Path(source_cfg["local_path"])
    log.info("Loading {} from {}...".format(source_key, path))
    if not path.exists():
        raise FileNotFoundError(
            "{} not found at {}. Run the required build/recovery step first.".format(source_key, path)
        )
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    df = pd.DataFrame(rows)
    df = df.rename(columns={source_cfg["text_column"]: "text", source_cfg["label_column"]: "label"})
    df = df[["text", "label"]].copy()
    df["source"] = source_key
    df["attack_type"] = source_cfg["attack_type_default"]
    log.info("  {}: {} rows".format(source_key, len(df)))
    return df


def load_agentic_held_out(source_cfg):
    log.info("Loading Agentic-5K (HELD OUT - not used in training)...")
    ds = load_dataset(source_cfg["hf_name"])
    frames = []
    for split_name, split_data in ds.items():
        split_df = split_data.to_pandas()
        split_df["original_split"] = split_name
        frames.append(split_df)
    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={source_cfg["text_column"]: "text", source_cfg["label_column"]: "label"})
    df["source"] = "agentic_5k"
    keep_cols = ["text", "label", "source", "attack_family", "technique", "severity", "original_split"]
    df = df[[c for c in keep_cols if c in df.columns]].copy()
    df = df.rename(columns={"attack_family": "attack_type"})
    log.info("  Agentic-5K: {} rows".format(len(df)))
    return df


def clean(df, prep_cfg):
    before = len(df)
    df["text"] = df["text"].astype(str).str.strip()
    if prep_cfg.get("remove_empty", True):
        df = df[df["text"].str.len() >= prep_cfg.get("min_text_length", 3)]
    df = df[df["text"].str.len() <= prep_cfg.get("max_text_length_chars", 80000)]
    df = df[df["label"].isin([0, 1])]
    df["label"] = df["label"].astype(int)
    log.info("  Cleaning: {} -> {} rows".format(before, len(df)))
    return df.reset_index(drop=True)


def cross_source_dedup(df):
    before = len(df)
    df["_hash"] = df["text"].apply(normalized_hash)
    df = df.drop_duplicates(subset=["_hash"]).drop(columns=["_hash"]).reset_index(drop=True)
    log.info("Cross-source dedup: {} -> {} rows ({} removed)".format(before, len(df), before - len(df)))
    return df


def oversample(df, factor, seed):
    if factor <= 1.0:
        return df
    n_repeats = int(factor)
    remainder = factor - n_repeats
    out = pd.concat([df] * n_repeats, ignore_index=True)
    if remainder > 0:
        out = pd.concat([out, df.sample(frac=remainder, random_state=seed)], ignore_index=True)
    return out


def stratified_split(df, cfg):
    seed = cfg["random_seed"]
    train_df, temp_df = train_test_split(
        df, train_size=cfg["splits"]["train"], stratify=df["label"], random_state=seed
    )
    rel_val = cfg["splits"]["validation"] / (cfg["splits"]["validation"] + cfg["splits"]["test"])
    val_df, test_df = train_test_split(
        temp_df, train_size=rel_val, stratify=temp_df["label"], random_state=seed
    )
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def save_jsonl(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            f.write(json.dumps(row.to_dict(), ensure_ascii=False) + "\n")
    log.info("Saved {} rows to {}".format(len(df), path))


def main():
    cfg = load_config()
    sources = cfg["train_sources"]
    seed = cfg["random_seed"]

    hlyn_df = clean(load_hlyn(sources["prompt_injection"]), cfg["preprocessing"])
    bipia_df = clean(load_bipia(sources["indirect_injection"]), cfg["preprocessing"])
    hard_neg_df = clean(load_local_source("hard_negatives", sources["hard_negatives"]), cfg["preprocessing"])
    hard_pos_df = clean(load_local_source("hard_positives", sources["hard_positives"]), cfg["preprocessing"])
    piguard_df = clean(load_local_source("piguard_curated", sources["piguard_curated"]), cfg["preprocessing"])
    authz_pos_df = clean(load_local_source("authz_hard_positives", sources["authz_hard_positives"]), cfg["preprocessing"])
    authz_neg_df = clean(load_local_source("authz_hard_negatives", sources["authz_hard_negatives"]), cfg["preprocessing"])

    combined = pd.concat([hlyn_df, bipia_df, hard_neg_df, hard_pos_df, piguard_df,
                          authz_pos_df, authz_neg_df], ignore_index=True)
    combined = cross_source_dedup(combined)

    stats = {
        "total_before_oversampling": len(combined),
        "class_distribution": combined["label"].value_counts().to_dict(),
        "source_distribution": combined["source"].value_counts().to_dict(),
    }
    log.info("Deduped pool stats:\n{}".format(json.dumps(stats, indent=2, default=str)))

    train_df, val_df, test_df = stratified_split(combined, cfg)

    # Oversample training split only, per source, per its configured factor
    train_parts = []
    source_map = {
        "prompt_injection": "hlyn", "indirect_injection": "bipia_70k",
        "hard_negatives": "hard_negatives", "hard_positives": "hard_positives",
        "piguard_curated": "piguard_curated",
        "authz_hard_positives": "authz_hard_positives",
        "authz_hard_negatives": "authz_hard_negatives",
    }
    for source_key, source_name in source_map.items():
        part = train_df[train_df["source"] == source_name]
        factor = sources[source_key]["oversample_factor"]
        oversampled = oversample(part, factor, seed)
        train_parts.append(oversampled)
        log.info("  {}: {} -> {} rows in train split (factor {}x)".format(
            source_name, len(part), len(oversampled), factor))

    train_df = pd.concat(train_parts, ignore_index=True)
    train_df = train_df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    for name, d in [("train", train_df), ("validation", val_df), ("test", test_df)]:
        log.info("{}: {} rows, source mix: {}".format(name, len(d), d["source"].value_counts().to_dict()))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    save_jsonl(train_df, PROCESSED_DIR / "train.jsonl")
    save_jsonl(val_df, PROCESSED_DIR / "validation.jsonl")
    save_jsonl(test_df, PROCESSED_DIR / "test.jsonl")

    stats["train_rows"] = len(train_df)
    stats["validation_rows"] = len(val_df)
    stats["test_rows"] = len(test_df)
    stats["train_source_mix"] = train_df["source"].value_counts().to_dict()
    with open(PROCESSED_DIR / "dataset_statistics.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, default=str)

    agentic_df = load_agentic_held_out(cfg["held_out_sources"]["agentic_5k"])
    HELD_OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_jsonl(agentic_df, HELD_OUT_DIR / "agentic_5k.jsonl")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(DOCS_DIR / "e-piguard-summary.md", "w", encoding="utf-8") as f:
        f.write("# E-PIGuard Experiment - Dataset Summary\n\n")
        f.write("Baseline: Hlyn + BIPIA + final_v2.jsonl (confirmed hard negatives) + "
                "pilot_v1.jsonl (confirmed hard positives)\n\n")
        f.write("Tested variable: + piguard_curated_v1.jsonl ({} rows)\n\n".format(len(piguard_df)))
        f.write("Train/Val/Test: {} / {} / {}\n\n".format(len(train_df), len(val_df), len(test_df)))
        f.write("Agentic-5K (held out, NEVER trained on): {} rows\n\n".format(len(agentic_df)))
        f.write("NotInject and xtest-v2-copy are held out separately, evaluated via "
                "scripts/eval_notinject.py and equivalent, never mixed into training.\n")

    log.info("E-PIGuard dataset preparation complete.")


if __name__ == "__main__":
    main()