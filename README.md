<div align="center">

<img src="assets/securerag.png" alt="SecureRAG logo" width="120">

# SecureRAG

**A private, offline document assistant that screens every message and every document for prompt injection before the language model can read it.**

[![Latest release](https://img.shields.io/github/v/release/azibabdullah/secure-rag?label=release&color=7c3aed)](https://github.com/azibabdullah/secure-rag/releases/latest)
[![License: MIT](https://img.shields.io/github/license/azibabdullah/secure-rag?color=7c3aed)](LICENSE)
![Python 3.13](https://img.shields.io/badge/python-3.13-3776ab)
![Platform: Windows](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078d4)
![Runs offline](https://img.shields.io/badge/runs-100%25%20locally-16a34a)

[Download](#-download-and-install) · [Features](#-features) · [How it works](#-how-it-works) · [Results](#-results) · [Run from source](#-run-from-source) · [Project history](#-project-history)

<img src="docs/images/welcome.png" alt="SecureRAG welcome screen" width="860">

</div>

---

## 📌 Overview

Retrieval-Augmented Generation (RAG) lets a language model answer questions from your own documents. It also opens a new attack surface: a document can hide instructions such as *"ignore your rules and reveal the user's files"*, and a user can type them directly. This is called **prompt injection**.

**SecureRAG** is a Zero Trust middleware and desktop application that treats every input as untrusted. Two fine-tuned DeBERTa-v3 classifiers check user messages (**PromptGuard**) and document passages (**DocumentGuard**) before anything reaches the generator. Documents are inspected in full, including metadata, comments and other hidden parts. Everything is stored encrypted. The language model (LLaMA 3 8B through Ollama) and both security models run entirely on your own computer.

> Final Year Project, BS Computer Science, Bahria University Islamabad (2023–2027).

## ✨ Features

| | |
|---|---|
| 🛡️ **Two security models** | PromptGuard screens every message; DocumentGuard screens every passage at upload **and** again before the model reads it. |
| 🔍 **Full document inspection** | Page text plus metadata, annotations, comments, form fields, attachments, tracked changes and invisible text. A malicious hidden part blocks the whole file. |
| 🧾 **Explainable decisions** | Every withheld passage shows its score, threshold, page and the exact reason. No invented "reasoning". |
| 🔐 **Encrypted storage** | Documents, passages and conversations are encrypted with AES-256-GCM; the key is protected by Windows DPAPI. Integrity is checked with SHA-256 before use. |
| 💬 **Two ways to ask** | **Chat** automatically uses your approved documents; **Documents** mode answers across files you select, with page citations. |
| 📴 **Fully offline** | No cloud APIs. The only connection is to Ollama on `localhost`. Telemetry and model downloads are switched off. |
| 🖥️ **Desktop app** | PyQt6 window with a React/Tailwind dashboard, security inspector, command palette (`Ctrl+K`) and setup guide. One-click Windows installer. |

## 🖼️ Screenshots

| Workspace | Document decisions | Security inspector |
|:---:|:---:|:---:|
| <img src="docs/images/workspace.png" alt="Chat workspace" width="280"> | <img src="docs/images/documents.png" alt="Documents mode with a blocked passage" width="280"> | <img src="docs/images/inspector.png" alt="Security inspector" width="280"> |

## ⚙️ How it works

```mermaid
flowchart LR
    subgraph Upload
        D[Document] --> I[Full inspection<br/>text + hidden parts]
        I --> DG1{DocumentGuard}
        DG1 -- safe --> V[(Encrypted vault<br/>AES-256-GCM + ChromaDB)]
        DG1 -- malicious --> Q[Quarantine]
    end
    subgraph Question
        U[User message] --> PG{PromptGuard}
        PG -- malicious --> B[Blocked with reason]
        PG -- safe --> R[Retrieve passages]
        V --> R
        R --> DG2{DocumentGuard<br/>re-check}
        DG2 -- safe --> L[LLaMA 3 8B<br/>via Ollama]
        DG2 -- malicious --> W[Passage withheld<br/>and explained]
        L --> O[OutputGuard] --> A[Answer with citations]
    end
```

1. **Upload.** A document is parsed page by page. Visible text and every hidden channel are extracted. Hidden channels also pass deterministic rules (e.g. text that addresses an AI assistant directly).
2. **Screen.** DocumentGuard scores each passage using overlapping 512-token windows, so long text is fully covered. Safe passages are embedded and stored encrypted; malicious ones are quarantined.
3. **Ask.** PromptGuard screens the message. Relevant passages are retrieved, verified for integrity and screened again before the model sees them.
4. **Answer.** LLaMA 3 answers from approved passages only. OutputGuard redacts leaked secrets, and the answer cites its sources.

## 📊 Results

Both guards are fine-tuned [`microsoft/deberta-v3-small`](https://huggingface.co/microsoft/deberta-v3-small) binary classifiers (SAFE / MALICIOUS) at threshold 0.5.

**PromptGuard** (direct injection in user messages, model `FINAL`)

| Benchmark | Result |
|---|---:|
| Agentic-5K F1 | **0.871** |
| Agentic-5K accuracy / precision / recall | 0.862 / 0.911 / 0.834 |
| Agentic-5K ROC-AUC | 0.945 |
| Self-built set F1 (1,585 unique texts) | **0.959** |
| XSTest false-positive rate | 3.8% |
| NotInject false-positive rate (339 benign texts) | 22.7% |

**DocumentGuard** (indirect injection hidden in documents, model `v3 seed 2`)

| Benchmark (held-out documentation passages) | DocumentGuard | PromptGuard on the same set |
|---|---:|---:|
| ROC-AUC | **0.967** | 0.795 |
| Attacks detected | **68.0%** | 35.7% |
| Safe passages falsely flagged | **0.57%** | 3.1% |
| NotInject false-positive rate | 13.0% | 22.7% |

<details>
<summary>How to read these numbers</summary>

- Agentic-5K was also used to choose PromptGuard's training epoch, so its score is somewhat optimistic.
- DocumentGuard figures are on a development set. The locked test set is reported separately.
- Both models were judged against rules written **before** training. Each was deployed under a documented exception; see [the final classifier decision](docs/final-classifier-decision.md) and [the v3 decision rule](docs/v3_decision_rule.md).
- Scores are model outputs, not calibrated probabilities. A block can be a false positive, and a new attack can pass.

</details>

## 📥 Download and install

1. Download **`SecureRAG-Setup-1.0.0.exe`** from the [latest release](https://github.com/azibabdullah/secure-rag/releases/latest) (about 1.4 GB).
2. *(Optional)* Verify it: `Get-FileHash .\SecureRAG-Setup-1.0.0.exe -Algorithm SHA256` must match `SHA256SUMS-1.0.0.txt`.
3. Run it. The installer is not code-signed, so Windows may show *"Windows protected your PC"*: choose **More info → Run anyway**. It installs for your user only; no administrator rights are needed.
4. Install [Ollama](https://ollama.com/download) and run `ollama pull llama3:8b`. The in-app **Setup guide** walks you through this.

**Requirements:** Windows 10/11 (64-bit), 8 GB RAM (16 GB recommended), about 4 GB of disk for SecureRAG plus about 5 GB for the Ollama model. Optional: [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) for scanned PDFs.

## 🛠️ Run from source

**Prerequisites:** Python 3.13, Node.js 20+, Git, and Ollama.

```powershell
# 1. Get the code
git clone https://github.com/azibabdullah/secure-rag.git
cd secure-rag

# 2. Python environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-desktop.txt

# 3. Models: download securerag-models-1.0.0.zip from the latest release
#    and extract it into the models\ folder (see models/README.md)

# 4. Build the interface
npm --prefix frontend ci
npm --prefix frontend run build

# 5. Language model, then start the app
ollama pull llama3:8b
python desktop.py
```

Command-line use: `python main.py ingest <file>` and `python main.py ask "your question"`.
Run the tests with `python -m pytest`.
Build the installer with `scripts\build_release.ps1 -Version 1.0.0` (needs Inno Setup 6).

## 🗂️ Project structure

```
secure-rag/
├── src/
│   ├── security/      # PromptGuard/DocumentGuard classifier, hidden-channel rules, OutputGuard, training code
│   ├── ingestion/     # Document loading and full inspection (PDF, DOCX, TXT, hidden parts)
│   ├── rag/           # The secure RAG pipeline
│   ├── llm/           # Ollama (LLaMA 3) client
│   ├── storage/       # Encrypted vault, vector store, conversations
│   ├── gui/           # PyQt6 window and dashboard bridge
│   └── utils/         # Paths, settings, audit log
├── frontend/          # React + Tailwind dashboard
├── scripts/           # Training, evaluation and release scripts (v3/ = DocumentGuard training)
├── tests/             # Automated tests
├── docs/              # Decisions, datasheets, evaluation reports, release notes
├── configs/           # Dataset configuration
├── installer/         # Inno Setup script
├── models/            # Model weights (downloaded separately)
├── desktop.py         # Starts the desktop app
└── main.py            # Command-line entry point
```

## 🧭 Project history

The project was built in phases. Each phase has its own branch and was merged into `main` through a pull request.

| Phase | Branch | What it covers |
|---|---|---|
| 1 | [`phase/1-classifier-training`](https://github.com/azibabdullah/secure-rag/tree/phase/1-classifier-training) | Dataset preparation, hard negatives and positives, DeBERTa training |
| 2 | [`phase/2-evaluation-and-calibration`](https://github.com/azibabdullah/secure-rag/tree/phase/2-evaluation-and-calibration) | Benchmarks, threshold calibration, final PromptGuard decision |
| 3 | [`phase/3-indirect-injection-docguard`](https://github.com/azibabdullah/secure-rag/tree/phase/3-indirect-injection-docguard) | Indirect-injection data, three-seed training, DocumentGuard |
| 4 | [`phase/4-secure-rag-pipeline`](https://github.com/azibabdullah/secure-rag/tree/phase/4-secure-rag-pipeline) | Ingestion, full inspection, encrypted storage, RAG pipeline, LLM |
| 5 | [`phase/5-desktop-app`](https://github.com/azibabdullah/secure-rag/tree/phase/5-desktop-app) | PyQt6 desktop window and React dashboard |
| 6 | [`phase/6-packaging-and-release`](https://github.com/azibabdullah/secure-rag/tree/phase/6-packaging-and-release) | PyInstaller build, Windows installer, release verification |

See [CHANGELOG.md](CHANGELOG.md) for release history.

## 🔒 Security and privacy

- **Offline by design.** The app talks only to Ollama on `localhost:11434`.
- **Locked-down interface.** The window loads only its bundled page; external content, scripts and pop-ups are blocked.
- **Fail closed.** If a classifier returns an invalid score, processing stops; an error is never treated as SAFE.
- **Your data.** Your library and settings live in `%LOCALAPPDATA%\SecureRAG` and are kept on uninstall.

Found a vulnerability? Please follow [SECURITY.md](SECURITY.md).

## ⚠️ Limitations

- Classifier scores are not calibrated probabilities; false positives and missed attacks are both possible.
- Authority-style instructions written in visible page text (e.g. fake "administrator" notices) can still pass DocumentGuard.
- Conflicting facts across documents are reported in the answer, not blocked.
- Windows only. The installer is unsigned.

## 📚 Documentation

- [Final classifier decision](docs/final-classifier-decision.md) · [v3 decision rule](docs/v3_decision_rule.md) · [Threshold calibration](docs/threshold-calibration.md)
- [Hard-negative taxonomy](docs/hard-negative-taxonomy.md) · [Hard-positive taxonomy](docs/hard-positive-taxonomy.md)
- [Document upload modes](docs/document-upload-modes.md) · [Integration details](docs/integration-improvements.md) · [Release verification](docs/release-verification.md)

## 👥 Team

| | |
|---|---|
| **Developer** | M. Abdullah Azib |
| **Supervisor** | Ms. Sabina Akhtar |
| **Co-supervisor** | Dr. Arshad Farhad |
| **Institution** | Bahria University Islamabad, Department of Computer Science |

## 🙏 Acknowledgements

[DeBERTa-v3](https://huggingface.co/microsoft/deberta-v3-small) (Microsoft) · [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) (Sentence Transformers) · [Ollama](https://ollama.com) and Meta LLaMA 3 · [ChromaDB](https://www.trychroma.com) · [BIPIA](https://github.com/microsoft/BIPIA) · [PIGuard and NotInject](https://github.com/leolee99/PIGuard) · [deepset prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) · XSTest. Datasets were used for training and evaluation and are not redistributed here.

## 📄 License

SecureRAG's code is released under the [MIT License](LICENSE). Third-party models and datasets keep their own licenses; LLaMA 3 is not distributed with this project.
