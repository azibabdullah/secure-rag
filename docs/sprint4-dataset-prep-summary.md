# Sprint 4 - Dataset Preparation Summary

Training pool: 467764 rows (Hlyn + BIPIA + hard negatives v2 + hard positives v1)

Train/Val/Test: 429953 / 46776 / 46777

Hard negatives: 1,248 unique items (final_v2), oversampled per-category - see configs/dataset.yaml

Hard positives: 180 unique items (pilot_v1), oversampled per-category - see configs/dataset.yaml

Agentic-5K (held out, NEVER trained on, reserved for final testing only): 4935 rows
