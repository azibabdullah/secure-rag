# Document upload and decision panel - 0.3.0

## What the labels mean

A passage (previously called an excerpt) is a small section of extracted text.
It is not a script. Approved means every extracted passage scored below the
frozen classifier threshold. Partially approved means some passages passed and
others were quarantined. Blocked means no passages were eligible for retrieval;
the extracted text is still retained in the encrypted vault for preview.
These are model decisions, not ground-truth labels or a guarantee of safety.

## Upload several documents

Use + beside Documents or Attach document. In the Windows picker, hold Ctrl to
select separate files or Shift for a range, then Open. Each file is handled in
sequence so classifier/GPU resources are not loaded multiple times. The results
list reports each file independently. A parser/model failure on one file does not
prevent later files from being processed. Stop preserves completed uploads and
lists the files not completed. Original files remain untouched.

## Screen documents on upload

The new saved toggle is in Local controls and defaults to ON.

- ON: extracted passages are classified before indexing. SAFE passages are indexed;
  malicious passages remain encrypted in quarantine and are excluded from retrieval.
  Retrieved candidates are checked again before generation.
- OFF: parsing, file limits, encryption and integrity protections remain in effect.
  New extracted passages are indexed as DEFERRED, displayed as Check on retrieval.
  They are not considered approved. Only candidates needed for a question (or all
  candidates for a selected-document summary) are classified before entering the
  LLM. Scores at/above the threshold are blocked; invalid scores stop processing.

This is upload-time screening ON/OFF, not a complete security bypass. PromptGuard,
retrieval DocumentGuard, integrity authentication and OutputGuard remain active.
Unchecked document embeddings are stored locally when screening is deferred.

Changing the toggle affects subsequent uploads. Existing documents keep their
recorded upload mode and scores; re-upload them to apply a different mode.
Content duplicate reuse only applies when the existing upload used the same mode.
Failed re-uploads preserve the previous committed generation.

## Explain decision

Select a document and choose Explain decision, or use that button in the Document
decision panel. It shows the upload decision, recorded threshold, each passage's
score, page/section, extracted text and latest retrieval decision/time when available.
Refresh the panel after a question to see the latest retrieval checks.

The operational reason is exact: the malicious score was below or at/above the
threshold, upload screening was deferred, or a stored passage failed integrity.
The classifier is a binary DeBERTa model and does not emit natural-language thoughts.
The panel therefore does not invent a reasoning trace or claim particular words
caused the classification. Scores represent the maximum across overlapping token
windows, not calibrated certainty or token-level attribution. Older imported data
may lack its original score; this is disclosed rather than reconstructed.

PDF decisions cover extracted page text. PDF metadata and embedded attachments are
not scanned by this loader; image-only content requires optional OCR. A safe test
file can be falsely blocked, and an attack can pass. Keep the threshold/model frozen
when measuring this behavior. Do not turn evaluation failures into training examples.

## Run from source

```powershell
cd E:\SecureRAG
.\.venv\Scripts\python.exe desktop.py
```

The built frontend is included locally. To rebuild frontend changes:

```powershell
npm --prefix frontend run build
```

This update targets the web desktop dashboard. The 0.2.0 installer remains the
previous release; the 0.3.0 installer now contains these new features.

When a batch uploads several files, Ask documents starts with All documents as
its scope. Use the Document scope dropdown to choose one file or the whole library.
Document summaries still require choosing a specific file.

Verification: the full 38-test suite passed, including the embedded-browser
multi-select dialog, per-file result reporting, decision panel, and preference
changes. An isolated real-classifier smoke check passed for upload screening ON
and OFF, including an attack blocked before generation in both modes. The test
report is document-modes-real-smoke.json; it is not a generalization benchmark.

