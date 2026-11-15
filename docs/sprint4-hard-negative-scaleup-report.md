# Sprint 4 Hard-Negative Scale-Up Merge Report

## Input
- Existing (final_v1, Sprint 2): 868 items
- New scale-up batch (Sprint 4): 380 items
- Combined before dedup: 1248

## Check 1: Schema and label sanity
- Rows with label != 0: 0
- Rows with empty text: 0
- Remaining after removing bad rows: 1248

## Check 2: Internal duplicate check
- Exact/near-normalized duplicates removed: 0
- Remaining after internal dedup: 1248

## Check 3: Held-out set (Agentic-5K) leakage check
- Held-out set size: 4935
- Exact overlaps: 0
- Near-duplicate overlaps (Jaccard > 0.6): 0

  PASS: no leakage detected.
- Remaining after leakage removal: 1248

## Final result
**1248 items written to data\hard_negatives\final_v2.jsonl**

### Category breakdown (final_v2)
- security_education: 291 (23.3%)
- code_configuration: 249 (20.0%)
- privileged_actions: 170 (13.6%)
- quoted_attacks: 120 (9.6%)
- defence_instructions: 120 (9.6%)
- logs_debugging: 120 (9.6%)
- dataset_annotation: 120 (9.6%)
- policies_documentation: 58 (4.6%)

### Source breakdown
- llm_authored: 780
- collected:S-Labs/prompt-injection-dataset: 241
- collected:prodnull/prompt-injection-repo-dataset: 227