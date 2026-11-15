# Models

Model weights are too large for Git, so they are published as a release asset.

## Download

1. Download **`securerag-models-1.0.0.zip`** from the [latest release](https://github.com/azibabdullah/secure-rag/releases/latest).
2. Extract it into this `models` folder.

The installer already contains these models; you only need this for running from source.

## Expected layout

```
models/
├── securerag-classifier-FINAL/        # PromptGuard: screens user messages
├── securerag-docguard-v3-seed2/       # DocumentGuard: screens document passages
└── embeddings/
    └── all-MiniLM-L6-v2/              # Sentence embeddings for retrieval
```

Paths are defined in `src/utils/app_paths.py`.

## The models

| Folder | Role | Base model | Threshold |
|---|---|---|---:|
| `securerag-classifier-FINAL` | PromptGuard | microsoft/deberta-v3-small | 0.5 |
| `securerag-docguard-v3-seed2` | DocumentGuard | microsoft/deberta-v3-small | 0.5 |
| `embeddings/all-MiniLM-L6-v2` | Retrieval embeddings | sentence-transformers/all-MiniLM-L6-v2 | n/a |

Labels: `0 = SAFE`, `1 = MALICIOUS`. Each classifier folder contains `classifier_config.json` and `training_metadata.json`; `securerag-classifier-FINAL` also has a `MODEL_CARD.md` and `SHA256SUMS.txt`. Do not retrain into or overwrite these folders.
