# Hard-Positive Pilot Dataset — Data Sheet

**File:** `data/hard_positives/pilot_v1.jsonl` | **Version:** 1.0 | **Rows:** 180
**Taxonomy version:** `docs/hard-positive-taxonomy.md` v1.0

## What this is

180 malicious training examples (label=1) written to close a specific, evidence-backed capability gap: `docs/threshold-extended-sweep.json` showed `approval_authority_escalation` recall on the held-out Agentic-5K set stuck at 66.1% even at the most aggressive threshold tested — proof the model never learned this attack mechanism, since no threshold adjustment could recover it. The training pool (`data/processed/dataset_statistics.json`) confirmed why: 99.2% of training rows come from Hlyn and BIPIA, both built around classic imperative-override phrasing ("ignore previous instructions," "you are DAN"). Neither contains a single example of authority-based, tool-abuse, or memory-persistence attacks. This pilot supplies those directly.

## Category counts

| Category | Count | % |
|---|---|---|
| `approval_authority_escalation` | 100 | 55.6% |
| `tool_function_abuse` | 40 | 22.2% |
| `memory_trust_boundary` | 40 | 22.2% |

Weighted toward `approval_authority_escalation` because it is the confirmed, unresolved gap; the other two are included for breadth (distinct mechanisms — tool-call manipulation, cross-turn persistence — with no equivalent anywhere in the current 427,814-row training pool).

## Sourcing

| Source | Count | Description |
|---|---|---|
| `llm_authored` | 180 | Directly authored by Claude, applying `docs/hard-positive-taxonomy.md`'s decision procedure (§3) to each item, without reading `data/held_out_eval/agentic_5k.jsonl` — mechanisms were drawn from the taxonomy's general attack-pattern descriptions, not from any specific held-out example. |

## Schema

Matches taxonomy §7:

```json
{
  "id": "hp_aae_0001",
  "text": "...",
  "label": 1,
  "category": "approval_authority_escalation",
  "mechanism": "fabricated_authority",
  "source": "llm_authored",
  "reviewed_by": "Claude (self-review against hard-positive-taxonomy.md v1.0)",
  "review_note": "..."
}
```

## Automated validation results (`scripts/validate_hard_positives.py`)

| Check | Result |
|---|---|
| Exact duplicates (case-insensitive) | 0 |
| Missing required fields | 0 |
| Non-MALICIOUS labels | 0 |
| Shared-opening template artifacts | All 3 categories under the taxonomy's 5% limit; highest was `memory_trust_boundary` at 5.0% (borderline — see limitations) |
| Length range | 106–241 characters (median 147) |
| Non-ASCII characters | 25 rows — all typographic only (em-dashes, curly quotes); zero non-English text |
| Mechanism diversity | All 3 categories span 5–10 distinct mechanisms each (see validation output); `approval_authority_escalation` leans on `role_reframing` (30%) and `verbal_approval_claim` (26%) most heavily |

## Leakage check against held-out set (`scripts/check_hard_positive_leakage.py`)

Held-out set: 4,935 rows. **Result: PASS — 0 exact overlaps, 0 near-duplicates (Jaccard > 0.6).**

## Known limitations — read before using for training

1. **Single-author, self-reviewed.** Same limitation as `data/hard_negatives/pilot_v1.jsonl` — every item was written and reviewed by Claude applying the taxonomy mechanically. A human has not yet re-read a 10% consistency sample or signed off. Treat this as a strong first draft, not a signed-off dataset.

2. **Narrow length range (106–241 chars, median 147).** Every item is roughly one to two sentences. The taxonomy's diversity requirements (§6, mirroring the hard-negative taxonomy) call for length variation through multi-paragraph documents (e.g. a longer email thread, a multi-turn chat excerpt, an incident-ticket narrative for `tool_function_abuse`). None of that longer-form variation exists yet — a real gap if the deployed system will see document-length inputs.

3. **`memory_trust_boundary`'s most-common opening ("update your context so that...") sits exactly at the 5% ceiling** (2/40 items) — not a violation, but the closest margin of any category. Worth diversifying openings further if this category is scaled up.

4. **Mechanism distribution is uneven within `approval_authority_escalation`** — `role_reframing` and `verbal_approval_claim` together account for 56% of the category's 100 items, while `chained_approval_spoof` and `pressure_threat` have only 1 example each. A larger batch should rebalance toward the underrepresented mechanisms so the model doesn't just learn two shortcut patterns.

5. **No verification of transfer effect yet.** This dataset has not been wired into `configs/dataset.yaml` / `src/security/prepare_dataset.py`, and no retrain has been run against it. Whether it actually moves `approval_authority_escalation` recall is unconfirmed until that happens.

6. **Not at the same scale as the hard-negative work.** 180 items is a first pass sized to the evidence (the confirmed gap is one category), not a target-scale dataset. If the eventual retrain shows this mechanism-based approach works, scaling `approval_authority_escalation` further (and adding longer-form items) is the natural next step — same pattern as the hard-negative pilot's Lane 1/Lane 3 scale-up.

## Required next steps before this dataset is used for retraining

1. **Human review pass** — read at least 10% (18 items, 6+ per category) against `docs/hard-positive-taxonomy.md` §3; correct or remove anything that doesn't hold up.
2. **Decide on oversample factor deliberately, not by copying the hard-negative mistake.** The Sprint 2 retrospective (`docs/threshold-calibration.md`, `docs/threshold-extended-sweep.json`) traced the `approval_authority_escalation` regression itself to over-aggressive uniform oversampling (5x) of a small category (70 items). Applying the same blind factor here, on a 100-item category, risks the same memorization failure this pilot is meant to fix. Pick a conservative factor and validate on dev-held-out before committing to it.
3. **Freeze a slice of Agentic-5K as a final, untouched test set before iterating** (see the taxonomy's own §5.2 integrity rule) — retraining and repeatedly checking full Agentic-5K performance to tune this dataset would erode the validity of the eventual reported number.
4. **Wire into `configs/dataset.yaml`** as a new `train_sources` entry (`local_path: data/hard_positives/pilot_v1.jsonl`) and extend `src/security/prepare_dataset.py` to load, dedup, and oversample it alongside the existing sources — same pattern already used for `hard_negatives`.
5. **Retrain and evaluate against dev-held-out only**, iterating on category balance/oversample factor before any final check against the frozen slice.
