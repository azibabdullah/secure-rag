# Hard-Negative Pilot Dataset — Data Sheet

**File:** `data/hard_negatives/pilot_v1.jsonl` | **Version:** 1.0 | **Rows:** 400
**Taxonomy version:** `docs/hard-negative-taxonomy.md` v1.0

## What this is

The 400-item pilot (50 × 8 categories) specified as the first Sprint 2 deliverable: category definitions plus 50 manually reviewed examples per category.

## What I attempted vs. what was actually possible

You asked me to (1) find existing similar datasets, (2) filter them against the taxonomy, and (3) generate the remainder myself, producing a final combined dataset. Steps 1–2 were not possible in this environment:

- **No Hugging Face access.** This sandbox's network egress is restricted to a fixed domain whitelist that does not include `huggingface.co` (requests return HTTP 403). `S-Labs/prompt-injection-dataset` and `prodnull/prompt-injection-repo-dataset`, identified in earlier research as containing relevant hard negatives, could not be downloaded or filtered here.
- **No LLM API access for bulk generation.** No `ANTHROPIC_API_KEY` is set in this sandbox, so the generation script built earlier (`scripts/generate_hard_negative_candidates.py`) could not be run here either.

**What I did instead:** authored all 400 items directly, applying the taxonomy's Section 3 decision procedure (two-question test: instruction present? would compliance subvert intent?) to each one as I wrote it, and ran automated validation against the taxonomy's diversity and integrity rules afterward.

## Sourcing

| Source | Count | Description |
|---|---|---|
| `llm_authored` | 400 | Directly authored by Claude, self-reviewed against the taxonomy |

No items from `S-Labs`, `prodnull`, or any other external dataset are included in this file. Lane 1 (collection) and Lane 3 (LLM-assisted generation at scale) from the earlier plan remain to be run — both require network/API access this sandbox doesn't have; see Next Steps.

## Category counts

All 8 categories at exactly 50/50 (12.5% each): `quoted_attacks`, `security_education`, `defence_instructions`, `policies_documentation`, `logs_debugging`, `code_configuration`, `dataset_annotation`, `privileged_actions`.

## Schema

Matches taxonomy §8, plus two extra fields (`trigger_used`, and `reviewed_by` pre-filled):

```json
{
  "id": "hn_quoted_attacks_0000",
  "text": "...",
  "label": 0,
  "category": "quoted_attacks",
  "source": "llm_authored",
  "trigger_used": "ignore all previous instructions",
  "reviewed_by": "Claude (self-review against taxonomy v1.0)",
  "review_note": "..."
}
```

## Automated validation results (`scripts/validate_pilot.py`)

| Check | Result |
|---|---|
| Exact duplicates (case-insensitive) | 0 |
| Missing required fields | 0 |
| Non-SAFE labels | 0 |
| Category balance | 50/50 every category |
| Shared-opening template artifacts | All categories under the 5% limit (taxonomy §6); highest was 4.0% |
| Length range | 41–178 characters (median 99) |
| Non-ASCII characters | 73 rows — all typographic only (em-dashes, curly quotes); zero non-English text |

## Known limitations — read before using for training

1. **Single-author, self-reviewed.** Every item was written and reviewed by the same source (Claude), applying the taxonomy mechanically. The taxonomy's own §10 process calls for independent human review and a 10% consistency re-read — neither has happened yet. Treat this as a strong first draft, not a signed-off dataset.

2. **`reviewed_by` is not a genuine second reviewer.** It's filled in to satisfy the schema, but it names the author, not an independent reviewer. Before this counts toward your supervisor's "reviewed" requirement, a human (you, or a second party) needs to actually read a sample and either co-sign or correct entries.

3. **No verification against Agentic-5K.** The taxonomy's §7 leakage check (hash comparison against the held-out set) could not be run here — I don't have your local `data/held_out_eval/agentic_5k.jsonl` file. **This must be run locally before training.** See Next Steps.

4. **Length range is narrow (41–178 chars).** The taxonomy's §6 diversity requirement asks for a mix through multi-paragraph documents; this pilot skews toward single sentences. Longer, multi-paragraph items (especially for `policies_documentation` and `security_education`) should be added in the next batch.

5. **Boundary-case judgement calls were made without a second opinion.** A few items sit close to the taxonomy's documented boundary cases (e.g. the `dataset_annotation` items about hypothetical/disputed framing). These are exactly the items worth prioritising in the human 10% audit.

6. **Not at target scale.** This is 400 of the 5,000–10,000 target. Reaching that range requires Lane 1 (dataset collection) and Lane 3 (LLM-assisted generation), both blocked in this environment — see below.

## Required next steps before this dataset is used for retraining

1. **Human review pass.** Read at least 10% (40 items, 5 per category) against the taxonomy. Correct or remove anything that doesn't hold up.
2. **Run the leakage check locally:**
   ```powershell
   python scripts\check_agentic5k_leakage.py
   ```
   (script below — run this before trusting the dataset)
3. **Scale up via Lane 1** — run `scripts/download_and_filter_external.py` (below) on your machine, where Hugging Face is reachable, to pull and filter `S-Labs` and `prodnull`.
4. **Scale up via Lane 3** — run `scripts/generate_hard_negative_candidates.py` with your own `ANTHROPIC_API_KEY` set, then `scripts/review_candidates.py` to review every candidate.
5. **Add longer-form items** — the pilot is short-sentence-heavy; deliberately add multi-paragraph examples per category.
6. Merge all approved sources into one frozen, versioned file per taxonomy §10 step 7.