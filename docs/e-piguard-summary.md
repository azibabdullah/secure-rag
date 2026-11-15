# E-PIGuard Experiment - Dataset Summary

Baseline: Hlyn + BIPIA + final_v2.jsonl (confirmed hard negatives) + pilot_v1.jsonl (confirmed hard positives)

Tested variable: + piguard_curated_v1.jsonl (10879 rows)

Train/Val/Test: 432064 / 47463 / 47464

Agentic-5K (held out, NEVER trained on): 4935 rows

NotInject and xtest-v2-copy are held out separately, evaluated via scripts/eval_notinject.py and equivalent, never mixed into training.
