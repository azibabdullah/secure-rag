# Final classifier decision

SecureRAG deploys **authz-v2, epoch 2, at threshold 0.5**. The local frozen
artifact is `models/securerag-classifier-FINAL/`. Label 0 is SAFE and label 1
is MALICIOUS. Inference uses the DeBERTa-v3-small tokenizer and a 512-token
window. The model folder is tracked with Git LFS; see its
`classifier_config.json` and `training_metadata.json` for the exact artifact.

The original four-check experiment returned `REJECT` at threshold 0.5. That
result in `docs/authz_v2_verdict.json` is preserved unchanged. The project
owner subsequently selected authz-v2 for deployment because its broader
measured performance was higher. This is an explicit exception to the
pre-registered rule, not a claim that the candidate passed it.

| Benchmark | Champion | Final authz-v2 |
| --- | ---: | ---: |
| Agentic-5K accuracy | 0.7810 | 0.8622 |
| Agentic-5K precision | 0.8430 | 0.9114 |
| Agentic-5K recall | 0.7458 | 0.8338 |
| Agentic-5K F1 | 0.7914 | 0.8709 |
| Agentic-5K macro-F1 | 0.7804 | 0.8616 |
| NotInject false-positive rate (339 benign items) | 0.1888 | 0.2271 |
| Self-built set F1 (1,585 unique texts) | 0.9068 | 0.9592 |

At threshold 0.5, NotInject false positives increased from 64 to 77 of 339
items, exceeding the allowed two-point increase by about 1.8 percentage
points. Agentic-5K was also used to select the best training epoch, so its
reported score is optimistic as an independent estimate. The self-built set
was not used for training or epoch selection, but contains many duplicate
texts in its raw 3,000-row form; the comparison above uses unique texts.

The classifier is a component of a defense-in-depth RAG system, not a
guarantee against every novel or encoded injection. PromptGuard and
DocumentGuard must inspect all user and retrieved text, including content
beyond the first 512 tokens, before it reaches the generator.

Source records: `docs/authz_v2_verdict.json` and the frozen model's
`checkpoint_info.json` and `training_metadata.json`. The original candidate
was an identical copy of the frozen model and was removed during cleanup.
No additional classifier retraining is planned for this FYP.
