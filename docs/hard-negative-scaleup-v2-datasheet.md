# Hard-Negative Scale-Up (v2) — Data Sheet

**File:** `data/hard_negatives/final_v2.jsonl` | **Version:** 2.0 | **Rows:** 1,248
**Taxonomy version:** `docs/hard-negative-taxonomy.md` v1.0
**Merge report:** `docs/sprint4-hard-negative-scaleup-report.md`

## What this is

A scale-up of the Sprint 2 hard-negative dataset (`final_v1.jsonl`, 868 items), adding 380 new items to the five categories that had stalled at pilot-only levels since Sprint 2 — external collection (Lane 1, S-Labs/prodnull) contributed meaningfully to `security_education` (291) and `code_configuration` (249), but essentially nothing to the other five categories, which sat at exactly 50 (pilot-only) or 70 (`privileged_actions`) against taxonomy targets of 500–1,200 each.

`privileged_actions` was prioritized (100 new items vs. 70 for the other four) because `docs/threshold-extended-sweep.json` traced the `approval_authority_escalation` recall regression specifically to this category's small size (70 items) combined with a blanket 5x oversample factor — a plausible memorization failure. Growing the underlying category, not just adjusting the factor, addresses the root cause rather than the symptom.

## What changed

| Category | v1 (Sprint 2) | v2 (this batch) | New items | Target (taxonomy §9) |
|---|---|---|---|---|
| `security_education` | 291 | 291 | 0 | 900–1,200 |
| `code_configuration` | 249 | 249 | 0 | 600–900 |
| `privileged_actions` | 70 | 170 | +100 | 500–800 |
| `quoted_attacks` | 50 | 120 | +70 | 900–1,200 |
| `defence_instructions` | 50 | 120 | +70 | 700–1,000 |
| `logs_debugging` | 50 | 120 | +70 | 600–900 |
| `dataset_annotation` | 50 | 120 | +70 | 500–800 |
| `policies_documentation` | 58 | 58 | 0 | 700–1,000 |
| **Total** | **868** | **1,248** | **+380** | **5,400–7,800** |

All five targeted categories moved from ≤70 items (≤8% of the v1 pool) to 120–170 items, each now at or above the taxonomy's informal ~9% floor (9.6%–13.6% of the v2 pool). `policies_documentation` (4.6%) is now the lowest-share category and was not addressed this round — it wasn't implicated in the evidence and wasn't part of this round's priority.

## Sourcing

All 380 new items are `llm_authored` (Claude, applying `docs/hard-negative-taxonomy.md`'s decision procedure §3 per item), split across five files under `data/hard_negatives/scaleup_v2_*.jsonl` before being merged into `final_v2.jsonl`. `privileged_actions` items were deliberately written as the SAFE mirror of the same domains used in the `approval_authority_escalation` hard positives (`data/hard_positives/pilot_v1.jsonl`) — same finance/healthcare/HR/IT/legal/procurement/security/education/SaaS-admin scenarios, but with the approval step genuinely satisfied and verifiable rather than fabricated or unverifiable. This pairing is intentional: the model should learn to key on whether a claim is verifiable, not on domain vocabulary.

## Automated validation results (`scripts/validate_scaleup_v2.py`)

| Check | Result |
|---|---|
| Exact duplicates (case-insensitive) | 0 |
| Missing required fields | 0 |
| Non-SAFE labels | 0 |
| Shared-opening template artifacts | All 5 categories within the taxonomy's 5% limit after one round of rewording (initial draft had 3 categories over — see below) |
| Length range | 100–208 characters (median 145) |
| Non-ASCII characters | 90 rows — all typographic only (em-dashes, curly quotes); zero non-English text |

**Template-artifact fix applied:** the first draft had `defence_instructions` (7.1%), `dataset_annotation` (18.6%), and `privileged_actions` (11.0%) exceeding the 5% shared-opening-phrase limit, mostly from repeated "Can you help me [write/design/understand]..." openings. 18 items across these three categories were reworded (meaning preserved, phrasing varied) to bring every category back under the limit before merging.

## Leakage checks

- **Against Agentic-5K** (`scripts/check_scaleup_v2_leakage.py`): 0 exact overlaps, 0 near-duplicates (Jaccard > 0.6) across 4,935 held-out rows.
- **Against existing `final_v1.jsonl`**: 0 overlaps — confirms none of the 380 new items duplicate the 868 already in production.
- **Merge-time check** (`scripts/merge_scaleup_v2.py`, re-running the same three checks on the full combined 1,248-item pool): 0 bad rows, 0 internal duplicates, 0 held-out leakage.

## Known limitations — read before using for training

1. **Single-author, self-reviewed**, same as every prior batch in this project (`final_v1.jsonl`, `data/hard_positives/pilot_v1.jsonl`). No human has re-read a 10% consistency sample yet.

2. **Still short of full taxonomy target.** 1,248 of the 5,400–7,800 target (16–23%). The five targeted categories improved 2.4x–2.7x but remain below their individual targets (e.g. `quoted_attacks` at 120 of 900–1,200). Framing for the dissertation: this is a second, evidence-directed pilot round, not the final dataset.

3. **`policies_documentation` is now the most under-represented category** (58 items, 4.6%) and wasn't addressed this round — it wasn't implicated by the threshold-sweep evidence, but if a future evaluation surfaces a gap there, it's the next natural target.

4. **The oversample factor was not revisited.** `configs/dataset.yaml` still applies a single blanket 5.0x factor to the entire `hard_negatives` source (see the inline comment added there). This was the mechanism suspected of causing the `approval_authority_escalation` regression when `privileged_actions` was only 70 items; it's now 170, which should reduce (not eliminate) memorization risk. `src/security/prepare_dataset.py` has no per-category oversampling logic — adding it is a prerequisite if a lower, more conservative factor is wanted for smaller categories specifically.

5. **No retrain has been run against `final_v2.jsonl` yet.** `configs/dataset.yaml` now points to it, but whether this actually improves held-out benign accuracy or `approval_authority_escalation` recall is unconfirmed until `prepare_dataset.py` and `train_deberta.py` are re-run.

## Required next steps before this dataset is used for retraining

1. **Human review pass** — 10% sample (38 items, ~8 per targeted category) against the taxonomy.
2. **Decide the oversample factor deliberately** — consider per-category factors now that `prepare_dataset.py` treats `hard_negatives` as one block; a uniform 5.0x may still over-weight `quoted_attacks`/`defence_instructions`/`logs_debugging`/`dataset_annotation` at 120 items each relative to `security_education`/`code_configuration` at ~250–290.
3. **Freeze a slice of Agentic-5K before the next retrain**, if not already done (see `docs/hard-positive-pilot-datasheet.md`'s same recommendation) — this dataset and the hard-positive pilot are both now ready to go into the same retrain, and repeated full-held-out checks across two separate retraining rounds would compound the risk to the held-out set's validity.
4. **Retrain with both `final_v2.jsonl` and `data/hard_positives/pilot_v1.jsonl` together**, evaluating against dev-held-out only, before any final check against a frozen slice.
