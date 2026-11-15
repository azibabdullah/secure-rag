# Sprint 2 Merge Report

## Input
- Pilot (hand-authored): 400 items
- External (keyword-filtered): 468 items
- Combined before dedup: 868

## Check 1: Schema and label sanity
- Rows with label != 0: 0
- Rows with empty text: 0
- Remaining after removing bad rows: 868

## Check 2: Internal duplicate check
- Exact/near-normalized duplicates removed: 0
- Remaining after internal dedup: 868

## Check 3: Held-out set (Agentic-5K) leakage check
- Held-out set size: 4935
- Exact overlaps: 0
- Near-duplicate overlaps (Jaccard > 0.6): 0

  PASS: no leakage detected.
- Remaining after leakage removal: 868

## Final result
**868 items written to data\hard_negatives\final_v1.jsonl**

### Category breakdown
- security_education: 291
- code_configuration: 249
- privileged_actions: 70
- policies_documentation: 58
- quoted_attacks: 50
- defence_instructions: 50
- logs_debugging: 50
- dataset_annotation: 50

### Source breakdown
- llm_authored: 400
- collected:S-Labs/prompt-injection-dataset: 241
- collected:prodnull/prompt-injection-repo-dataset: 227