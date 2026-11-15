# Sprint 3 - Threshold Calibration

Held-out PR-AUC: 0.7906 | ROC-AUC: 0.7864

## Threshold sweep (held-out set)

| threshold | accuracy | precision | recall | F1 | FPR (benign) |
|---|---|---|---|---|---|
| 0.05 | 0.7220 | 0.8076 | 0.6578 | 0.7251 | 0.1973 |
| 0.10 | 0.7052 | 0.8136 | 0.6109 | 0.6978 | 0.1762 |
| 0.15 | 0.6926 | 0.8163 | 0.5785 | 0.6772 | 0.1638 |
| 0.20 | 0.6843 | 0.8194 | 0.5560 | 0.6625 | 0.1542 |
| 0.25 | 0.6786 | 0.8237 | 0.5385 | 0.6513 | 0.1451 |
| 0.30 | 0.6746 | 0.8265 | 0.5265 | 0.6433 | 0.1391 |
| 0.35 | 0.6701 | 0.8288 | 0.5142 | 0.6346 | 0.1336 |
| 0.40 | 0.6665 | 0.8313 | 0.5036 | 0.6273 | 0.1286 |
| 0.45 | 0.6620 | 0.8335 | 0.4916 | 0.6185 | 0.1236 |
| 0.50 | 0.6563 | 0.8348 | 0.4778 | 0.6078 | 0.1190 |
| 0.55 | 0.6503 | 0.8364 | 0.4629 | 0.5960 | 0.1140 |
| 0.60 | 0.6478 | 0.8387 | 0.4556 | 0.5905 | 0.1103 |
| 0.65 | 0.6430 | 0.8402 | 0.4436 | 0.5807 | 0.1062 |
| 0.70 | 0.6367 | 0.8420 | 0.4284 | 0.5678 | 0.1011 |
| 0.75 | 0.6278 | 0.8425 | 0.4084 | 0.5501 | 0.0961 |
| 0.80 | 0.6193 | 0.8421 | 0.3898 | 0.5329 | 0.0920 |
| 0.85 | 0.6097 | 0.8416 | 0.3691 | 0.5131 | 0.0874 |
| 0.90 | 0.5947 | 0.8409 | 0.3364 | 0.4805 | 0.0801 |
| 0.95 | 0.5656 | 0.8352 | 0.2745 | 0.4132 | 0.0682 |

## Recommendations

- **Default (0.50)**: acc=0.6563 prec=0.8348 rec=0.4778 f1=0.6078
- **Best F1 (0.05)**: acc=0.7220 prec=0.8076 rec=0.6578 f1=0.7251
- **Closest to Sprint 1 recall (0.05)**: acc=0.7220 prec=0.8076 rec=0.6578 f1=0.7251

## Per-attack-type breakdown at candidate thresholds


### threshold = 0.05

| attack type | metric | value | n |
|---|---|---|---|
| approval_authority_escalation | recall | 0.4732 | 672 |
| rag_document_embedded | recall | 0.6065 | 681 |
| tool_function_abuse | recall | 0.7004 | 671 |
| benign | accuracy | 0.8027 | 2185 |
| memory_trust_boundary | recall | 0.8375 | 726 |

### threshold = 0.50

| attack type | metric | value | n |
|---|---|---|---|
| approval_authority_escalation | recall | 0.2693 | 672 |
| rag_document_embedded | recall | 0.4405 | 681 |
| tool_function_abuse | recall | 0.5559 | 671 |
| memory_trust_boundary | recall | 0.6336 | 726 |
| benign | accuracy | 0.8810 | 2185 |
