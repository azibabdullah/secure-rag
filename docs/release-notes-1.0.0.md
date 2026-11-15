## SecureRAG 1.0.0

A private document assistant for Windows. Your files, the language model and both security models run on your own computer. Nothing is sent anywhere.

### Download and install
1. Download **SecureRAG-Setup-1.0.0.exe** below (about 1.5 GB).
2. Optional: check that the download is genuine (see "Verify the download").
3. Run it. Windows may show "Windows protected your PC" because the installer is not code-signed. Choose **More info → Run anyway**.
4. It installs for your user only. No administrator rights are needed and nothing outside your user profile is changed.
5. On the welcome screen, open **Setup guide**. It walks you through installing [Ollama](https://ollama.com/download), downloading a model (`ollama pull llama3:8b`) and connecting it.

### Requirements
- Windows 10 or 11, 64-bit
- 8 GB RAM minimum (16 GB recommended)
- About 4 GB free for SecureRAG, plus about 5 GB for one Ollama model
- Optional: Tesseract OCR for scanned PDFs (`winget install UB-Mannheim.TesseractOCR`)

### Verify the download
In PowerShell, in the folder you downloaded to:
```powershell
Get-FileHash .\SecureRAG-Setup-1.0.0.exe -Algorithm SHA256
```
The result must match the line in `SHA256SUMS-1.0.0.txt` from this release. If it does not, delete the file and do not run it.

### Security and privacy
- **Runs offline.** The app makes no network requests except to Ollama on your own computer (`localhost:11434`). Model downloads are switched off, and the vector database's telemetry is disabled.
- **Two security models.** PromptGuard screens every message; DocumentGuard screens every passage and every hidden part of a file (metadata, annotations, comments, attachments) at upload and again before the model reads it.
- **Encrypted storage.** Documents, passages and conversations are stored encrypted with AES-256-GCM. The key is protected by Windows (DPAPI) for your user account.
- **Locked-down interface.** The window can only load its own bundled page; scripts, external content and pop-up windows are blocked.
- **Your data stays on uninstall.** Your library and settings live in `%LOCALAPPDATA%\SecureRAG`; uninstalling keeps them, so reinstalling loses nothing. Delete that folder to remove them.

### What's new in 1.0.0
- New brand: the striped SecureRAG logo, a purple theme and an app icon.
- New start-up: the logo assembles from a dot matrix while the security models load, then draws itself in on the welcome screen.
- Glossy dashboard with the logo glowing behind the panels (Settings → Look and feel → Glowing logo backdrop, to turn it off).
- Screening summary tables with rose charts on Overview, Documents and in screening reports.
- Setup guide opens as a side sheet, including on the welcome screen.
- Smoother sidebar collapse, and the sidebar opens over the content on narrow windows.

### Known limitations
- Classifier scores are not calibrated probabilities, and a block can be a false positive.
- Authority-style instructions written in visible page text can still pass DocumentGuard.
- Conflicting facts across documents are reported in the answer, not blocked.
