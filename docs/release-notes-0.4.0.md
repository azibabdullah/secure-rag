## SecureRAG 0.4.0

A private document assistant for Windows. Your files, the language model and every security check run on your own computer.

### Download and install
1. Download **SecureRAG-Setup-0.4.0.exe** below (about 1.5 GB).
2. Run it. Windows may show "Windows protected your PC" because the installer is not code-signed: choose **More info → Run anyway**.
3. Install for your user (no administrator rights needed) and launch SecureRAG.
4. Click **How to set up** on the welcome screen. It walks you through installing [Ollama](https://ollama.com/download) and downloading a model (`ollama pull llama3:8b`), then connects it.

### Requirements
- Windows 10 or 11, 64-bit
- 8 GB RAM minimum (16 GB recommended)
- About 4 GB free for SecureRAG plus about 5 GB for one Ollama model
- Optional: Tesseract OCR for scanned PDFs (`winget install UB-Mannheim.TesseractOCR`)

### What's new
- Two security models: PromptGuard (FINAL) screens messages; DocumentGuard (v3 seed 2) screens documents.
- Full document inspection: metadata, annotations, comments, form fields, attachments, tracked changes and invisible text. A malicious hidden part blocks the whole file.
- Chat uses your approved documents automatically; Documents mode answers across selected files and explains every withheld passage.
- New interface: security inspector (decision, scores, sources, pipeline trace), command palette (Ctrl+K), welcome screen and setup guide.

### Verify the download (optional)
```powershell
Get-FileHash .\SecureRAG-Setup-0.4.0.exe -Algorithm SHA256
```
Compare with `SHA256SUMS-0.4.0.txt`.

Limitations: classifier scores are not calibrated probabilities, and a block can be a false positive. Authority-style instructions in visible page text can still pass. See the project report.
