# Implemented integration improvements

This update keeps the frozen authz-v2 classifier and its threshold of 0.5. The
original experiment verdict remains REJECT, the owner selected a deployment
exception, and Agentic-5K was used for epoch selection. No new training or claims
of improved classifier benchmark accuracy are part of this update.

## Run

```powershell
cd E:\SecureRAG
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python desktop.py
```

Ollama runs separately. Start it, run `ollama pull llama3:8b` if needed, then use
Refresh models and Connect model. The installed app does not need Python or Node.

## Features

- Invalid/non-finite classifier outputs stop processing. Security errors never
  become SAFE decisions. The classifier scans overlapping token windows.
- PDF excerpts retain page numbers; DOCX paragraphs and tables retain section
  labels and order. Chunk boundaries prefer paragraphs and sentence breaks.
- All approved excerpts participate in staged document summaries. Explicitly
  relevant verbatim passages accompany condensed notes to reduce information loss.
  Coverage is reported. A local model can still omit or misinterpret facts.
- Saved conversations use separate encrypted records. Only the last three
  successful contiguous turns from the same mode/source can supply context;
  previous text is screened again and never becomes a system instruction.
- Source buttons open exact extracted passages, with page numbers where available.
  Retrieved and model-cited excerpts are labelled separately. Valid citation IDs
  do not prove that the cited passage supports every statement.
- Stop cancels network generation and checks between classifier batches, pages,
  OCR steps and embedding batches. A running native inference batch must finish
  before it can stop. Partial generated text is not displayed or saved. Retry is
  explicit and has no automatic duplicate generation.
- Output redaction covers emails, labelled credentials, bearer tokens and complete
  private-key blocks. It is pattern-based and cannot detect every sensitive item.
- Theme, motion, OCR and Ollama model preferences survive restart. System reduced
  motion remains respected. Setup instructions appear in Local controls.
- Document previews include encrypted quarantined text, clearly labelled. Only
  approved excerpts have vectors and enter retrieval. Matching extracted document
  content is deduplicated even when uploaded under another filename.
- New vectors are staged before an authenticated manifest transaction activates
  them. Failure/cancellation before publication keeps the previous version.

## Storage and migration

`%LOCALAPPDATA%\SecureRAG` contains the profile. AES-256-GCM encrypts document text,
metadata and conversation records. A random key is protected using Windows DPAPI;
`vault.key.dpapi` belongs to this Windows user/machine. Losing it loses access to
the vault. Back up the profile and Windows credentials using an appropriate
Windows backup workflow; copying this key to another PC is not a portable export.
The installed application and frozen model remain separate from user data.

Chroma stores embedding vectors and opaque generation IDs, without chunk text.
Vectors are not encrypted and may reveal semantic information. Audit logs contain
filenames, timestamps, hashes and decisions, without raw prompts/documents.
Encryption does not protect against malware running as the logged-in user,
rollback of an entire profile, or deletion of the database/key.

When an earlier `securerag_v2` library is detected, choose **Import earlier
library**. Imported text is checked against its old hash and screened again at
retrieval. Earlier plaintext Chroma data and audit history are retained for
recovery; migration is not secure deletion. Re-upload original files to obtain
page references, content deduplication and quarantined previews. Fully quarantined
old files have no indexed text to import.

## Optional OCR

Install local Tesseract with English language data and make `tesseract` available
on PATH. Restart the app, enable Local PDF OCR, then upload the PDF. Pages without
extractable text are rendered locally with PDFium and OCR runs with a timeout.
Temporary page images are deleted after processing. Empty/failed pages stop the
upload rather than silently publishing a partial document. PDFs with an existing
but incomplete text layer are not automatically re-OCRed. OCR can misread text;
review the preview. Tesseract is not bundled in the installer.

## Verification

```powershell
python -m pytest tests -q
python scripts\evaluate_pipeline.py --model llama3:8b
```

The second command uses an isolated temporary profile and real frozen classifier,
embeddings, storage and Ollama. It records exact-match fact checks, canary attack
probes, benign blocks, tamper handling and per-operation latency in
`docs/e2e-regression-results.json`. These small synthetic regressions are not a
representative benchmark. Human citation-support review is explicitly unscored.
Never use this report or frozen evaluation datasets as training inputs.

## Windows build

Use the separate CPU environment and `scripts\build_desktop.ps1`. Full dependency
versions are recorded in `requirements-desktop-lock.txt`; install CPU torch from
the official CPU index before other dependencies. Bundle both local models.
`SecureRAG.exe --self-test ABSOLUTE_REPORT_PATH` checks bundled CPU inference,
ingestion, retrieval and embedded frontend in an isolated profile.

Compile `installer\SecureRAG.iss` with Inno Setup to create the setup executable.
The release is Windows x64. A clean Windows PC without Python/Node/ROCm still
needs separate acceptance testing, including Ollama connection, installation,
upgrade, uninstall, OCR availability, RAM usage and responsiveness. No universal
hardware support, fixed frame rate or perfect injection protection is promised.

Multi-file uploads and the configurable upload-screening mode are described in
[document-upload-modes.md](document-upload-modes.md). With upload screening off,
unchecked text is encrypted and indexed locally, and retrieval checks still run
before any candidate is sent to the LLM. This supersedes statements above that
only approved passages can have vectors. Existing records keep their upload mode
until re-uploaded.
