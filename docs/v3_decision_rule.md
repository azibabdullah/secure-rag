# Classifier v3: pre-registered decision rule

Fixed on **11 November 2026**, before any v3 model was trained or scored. Implemented
exactly in `scripts/v3/analyze_v3.py`. Do not change these numbers after seeing results.

## Why v3 exists

The owner reopened the frozen classifier (authz-v2, threshold 0.5) for one bounded
experiment after the review by course instructor Adnan Younas (2 Oct 2026) and
continued false blocks of benign content. FINAL stays untouched in
`models/securerag-classifier-FINAL/` and remains the deployed model unless v3 passes.

## What changed (one configuration, three seeds)

| Recommendation | v3 implementation |
|---|---|
| Balance by source | Hlyn and BIPIA capped at 12,500 rows per label each; PIGuard label-balanced; small targeted sets kept in full. 53k rows instead of 432k. |
| Targeted indirect data | 1,117 real GitHub documentation passages, each as a benign/injected minimal pair (`data/indirect_docs/docs_train.jsonl`). |
| Validate on whole held-out sources | Epoch selection and early stopping on Agentic-5K + docs_dev (mean ROC-AUC). No random-split selection. |
| Regularisation | ≤3 epochs, LR 2e-5, 10% warmup, weight decay 0.01, label smoothing 0.1, stop at first epoch without dev improvement. |
| Three seeds | Seeds 1, 2, 3; mean ± SD reported. Deploy seed = best dev selection score. |
| Threshold-independent metrics | ROC-AUC, PR-AUC, TPR at 1% and 5% FPR on every set. |
| Statistics | Paired bootstrap 95% CIs (2,000 resamples) and exact McNemar tests vs FINAL. |
| Calibration and separate thresholds | Temperature scaling reported; separate PromptGuard and DocumentGuard thresholds. |
| Locked test, evaluated once | deepset/prompt-injections (overlap with any training data removed) + docs_test. Scored once after the decision, with an access log. |

## Sets and their roles

- **Dev (used for decisions):** Agentic-5K, docs_dev (GitHub projects and hand-written business documents not in training, unseen payload phrasings), NotInject, XSTest, self-built 3,000. Agentic-5K and NotInject have already influenced earlier decisions, so they are dev sets, not unbiased tests.
- **Locked test (reported once):** deepset/prompt-injections, docs_test (different projects and payloads again).
- **Never used for training or tuning:** all of the above, plus the owner's 17-document corpus.

## Accept v3 only if ALL checks pass on dev

FINAL is always scored at its deployed threshold of 0.5.

| Check | Condition |
|---|---|
| **A. Indirect documents improve (goal)** | Mean docs_dev ROC-AUC over 3 seeds ≥ FINAL + 0.01, and the paired bootstrap 95% CI of (deploy seed − FINAL) is above 0. |
| **B. Agentic-5K not worse** | Mean Agentic-5K ROC-AUC over seeds ≥ FINAL − 0.005. |
| **C. PromptGuard operating point** | Threshold set so the deploy seed's Agentic-5K benign FPR ≤ FINAL's at 0.5. At that threshold: Agentic-5K TPR ≥ FINAL − 0.01; NotInject FPR ≤ FINAL + 0.02; XSTest FPR ≤ FINAL + 0.02. |
| **D. DocumentGuard operating point** | Threshold set for docs_dev benign FPR ≤ 2%. Deploy seed's docs_dev TPR ≥ FINAL's TPR at FINAL's own 2%-FPR threshold. |
| **E. Seed stability** | SD of docs_dev and Agentic-5K ROC-AUC across seeds ≤ 0.02. |
| **F. Self-built set** | Macro-F1 on the unique self-built texts at the PromptGuard threshold ≥ FINAL − 0.02. |

If any check fails, the verdict is **REJECT**. FINAL stays deployed and the v3
results are reported as a negative result. If all pass, the deploy seed is scored once on
the locked test together with FINAL, and that result is reported whatever it shows.

## Known limitations to state in the report

- FINAL is a single training run; it cannot be compared across seeds without retraining it three times.
- docs_dev/docs_test injected passages are synthetic insertions into real documents. The business passages are hand-written for this project.
- Hlyn contained XSTest prompts verbatim (136 training rows were removed in v3), so XSTest figures reported for earlier models are optimistic.
- A TF-IDF + logistic-regression baseline reached 95.6% in-distribution vs 0.65 accuracy on Agentic-5K, confirming surface shortcuts in the old training mix.
