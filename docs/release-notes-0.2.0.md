# SecureRAG 0.2.0 - Windows preview

Local chat and document questions with prompt/document screening, approved-only
retrieval, encrypted document/chat records, source previews and saved conversations.

## Downloads

- SecureRAG-Setup-0.2.0.exe: Windows x64 installer, approximately 1.03 GB.
- SecureRAG-Quick-Start.pdf: one-page installation and local-model instructions.
- SHA256SUMS.txt: SHA-256 checksums for the installer and PDF.

The installer includes Python runtime, Qt WebEngine interface, frozen security
classifier and embedding model. Users do not need Python, Node.js, Git, ROCm or
a source checkout. Ollama and its chat models are separate downloads.

Install Ollama from https://ollama.com/download/windows, then run:

```powershell
ollama pull llama3.2:3b
ollama list
```

Start SecureRAG, refresh Ollama models in Local controls, choose llama3.2:3b, then
Connect model. Keep Ollama running. No API key or remote endpoint is needed.

Windows x64 preview; locally tested on Windows 11. Allow 16 GB RAM and 12-15 GB
free storage as practical planning allowances, not certified minimums. GPU is
optional and CPU generation can be slow. Initial downloads require internet;
inference uses local Ollama after setup. This is not a macOS/Linux installer.

## Verification and limits

32 automated tests passed, plus 16 synthetic end-to-end regression cases with the
frozen classifier and llama3:8b. Packaged CPU classification, ingestion, retrieval
and embedded frontend diagnostics passed. These results do not establish accuracy
on arbitrary documents, and the 3B generator has not received the same evaluation.
A clean separate-PC install/upgrade/uninstall test remains pending.

The artifact is unsigned and Windows protection policies may warn or block it.
Do not disable antivirus or Smart App Control to run this preview. Only use a
trusted download and verify the published checksum. A checksum detects changes;
it is not a publisher signature. OCR needs separately installed local Tesseract
and has not been tested here with that executable.

The frozen classifier is authz-v2 at threshold 0.5. The original experiment verdict
was REJECT because the NotInject false-positive tolerance was exceeded; the owner
selected a deployment exception. Agentic-5K was used to select the training epoch,
so its reported performance is not an unbiased untouched-test estimate.

The profile is stored under %LOCALAPPDATA%\SecureRAG, separately from installed
application files. The encrypted vault is bound to this Windows account/machine.
Uninstalling the app does not deliberately erase this profile or Ollama models.
The security layer reduces risk; it cannot promise perfect injection detection.
