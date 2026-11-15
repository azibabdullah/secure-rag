# Release verification — 21 October 2026

- Full automated suite: 32 tests passed.
- Real frozen-classifier/Ollama regression evaluation: 16 of 16 cases passed.
  These synthetic cases are development regressions, not a representative accuracy
  benchmark. Full answers and exact passages are retained in
  `e2e-regression-results.json`; citation support still needs human review.
- Frozen model weight SHA-256 matches the existing freeze manifest:
  `2f02040ca0d0defbadf542b1c3ba6bd3b8ad4d6170cdc3b233fca3d26f451b23`.
- The optional OCR workflow has loader/failure tests; real Tesseract is not installed
  on this machine, so OCR accuracy and the external executable remain unverified.
- Windows x64 CPU packaging is being verified. The final packaged diagnostic and
  installer status will be recorded below when complete.
- A clean Windows PC, signed distribution, install/upgrade/uninstall and animation
  performance have not been independently validated. Ollama and its models remain
  external prerequisites; Tesseract is optional. No macOS/Linux executable is built.

The packaged Windows x64 executable passed CPU classification, secure ingestion,
retrieval and embedded-frontend loading. See `packaged-self-test.json`. The
headless renderer test used software rendering; production keeps normal GPU
acceleration. An incompatible Poppler ICU library from the build machine PATH
was removed from the distribution, and the build script repeats that correction.
Qt resolves the native Windows ICU dependency instead.


Final installer: `dist/installer/SecureRAG-Setup-0.2.0.exe`.
The installer compiled successfully; its checksum is in `installer-sha256.json`.
The final Stop timing fix passed the embedded-browser test after the full
32-test run. Installation on a clean separate PC remains pending. This artifact
is unsigned. Do not treat compilation or local diagnostics as clean-PC certification.

## Document controls update - 0.3.0

The full 38-test suite passed. Real frozen-classifier smoke checks passed for
upload screening ON and OFF, including retrieval blocking before generation.
The packaged 0.3.0 CPU/frontend diagnostic passed; its bundled frontend hash
matched the latest build. The 0.3.0 installer compiled successfully at
`dist/installer/SecureRAG-Setup-0.3.0.exe`. Its SHA-256 is recorded in
`installer-0.3.0-sha256.json`. These checks do not certify clean-PC installation
or perfect attack detection; the artifact remains unsigned. Classifier weights,
threshold, training sources and frozen evaluation sets were not modified.
See `document-upload-modes.md` for the new controls and limitations.
