# SecureRAG web desktop dashboard

## What this is

An installable desktop app can use Tailwind and CSS. This implementation uses React + Tailwind inside PyQt6 WebEngine (embedded Chromium), with a Qt WebChannel bridge to the existing Python SecureRAG pipeline. The user's browser, Node.js and a local web server are not required in the installed application. Ollama remains a separately installed local prerequisite.

The older native interface remains available with `python main.py gui`. The new interface uses `python main.py dashboard` or `python desktop.py`.

## Run on this development computer

The dependencies and frontend have already been installed/built during this update. Close the old app and run:

```powershell
cd E:\SecureRAG
.\.venv\Scripts\Activate.ps1
python main.py dashboard
```

Select Refresh in Local controls, choose an installed Ollama model, and select Connect model. Add documents with the + button. Selecting a document switches to Ask documents and scopes retrieval. The summary action uses the selected file with all existing guards intact.

The sun/moon button changes dark/light appearance. Interface motion controls decorative motion, and the operating system's reduced-motion preference is also respected. Appearance preferences now persist across restarts.

## Rebuild after changing frontend source

```powershell
cd E:\SecureRAG
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run build
python main.py dashboard
```

You need Node.js during development/build only. The committed package-lock.json pins frontend dependencies. The frontend is compiled to local JavaScript/CSS; there are no CDN scripts or remote fonts.

## Architecture and full source map

| File | Responsibility |
|---|---|
| frontend/src/App.jsx | Dashboard grid, document library, conversation, request state, controls |
| frontend/src/components/Widgets.jsx | Panel, Toggle, RiskChart, ActivityFeed and Thinking components |
| frontend/src/styles.css | Tailwind import, theme tokens, responsive layout, glass surfaces, animations, reduced motion |
| frontend/src/bridge.js | Request IDs and promises around the Qt WebChannel bridge |
| frontend/src/main.jsx | React entry point |
| frontend/public/index.html | Local HTML entry, Content Security Policy, Qt WebChannel script |
| frontend/vite.config.js | Vite + Tailwind compiler; local IIFE bundle |
| frontend/package.json and package-lock.json | Build commands and dependencies |
| src/gui/web_app.py | Native desktop shell, bounded bridge, background worker, file dialogs |
| desktop.py | Frozen desktop entry point with multiprocessing support |
| scripts/build_desktop.ps1 | CPU release environment validation and PyInstaller packaging |
| installer/SecureRAG.iss | Inno Setup installer definition |
| requirements-desktop.txt | Desktop build dependencies; install CPU torch separately |
| tests/test_web_dashboard.py | Actual embedded-browser bridge/theme/security-rendering regression |

These are complete source files, not snippets. The existing src/rag, security, ingestion, llm and storage modules remain the backend.

## Data and motion behavior

- Chart points are recorded malicious scores from the last 30 audit events, capped to 24 scored points. The horizontal axis represents event order, not elapsed time. Scores are not calibrated probabilities of harm.
- Recent check/blocked counts cover only the recent event window. Approved excerpt count comes from the current library, not a fabricated statistic.
- Activity refreshes when operations complete. It is not a continuous external telemetry subscription.
- Thinking animation covers the whole request. No token stream is displayed before the existing output checks finish.
- Animation uses opacity and transforms where possible, staggered entry, cubic-bezier(0.16, 1, 0.3, 1), subtle hover states, SVG chart fills and animated toggles. Chromium normally uses hardware acceleration. No fixed 60/120 fps guarantee has been measured; blur/large surfaces also carry GPU cost.
- No untrusted HTML is rendered from model responses. React displays answer text; external page navigation is blocked. The bridge exposes only explicit operations. It does not expose arbitrary Python execution.
- The backend now stores separate conversations and processes all approved excerpts in staged summaries. See integration-improvements.md for memory limits, encryption and security scope.

## Tests

```powershell
python -m pytest tests/test_document_routing.py tests/test_desktop.py tests/test_web_dashboard.py -q
```

The browser test starts a real Qt WebEngine renderer with a fake backend and sample events. Its screenshots are test previews, not measured project performance. Offscreen testing uses software rendering; the production launcher does not disable GPU acceleration or the Chromium sandbox. Restricted execution environments may require permission to start Chromium subprocesses.

## Build the Windows executable

Do this after testing with real documents and your installed Ollama model. Use a separate CPU environment so the released classifier does not require this development machine's ROCm libraries:

```powershell
cd E:\SecureRAG
py -3.13 -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install --upgrade pip
.\.build-venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.\.build-venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
.\scripts\build_desktop.ps1
.\dist\SecureRAG\SecureRAG.exe
```

Both models/securerag-classifier-FINAL and models/embeddings/all-MiniLM-L6-v2 must exist. The embedding model is ignored by Git; download/save it locally on a fresh checkout as described in the earlier desktop guide. Record exact Python package versions after a successful clean release build.

PyInstaller produces an application folder containing the executable, Chromium runtime, frontend assets, classifier, embedding model and Python dependencies. Keep the whole folder together. PyInstaller's Qt WebEngine hooks should collect its process/resources; verify them on a clean Windows machine rather than assuming a successful build proves portability.

Install Inno Setup, open installer/SecureRAG.iss and Compile. The intended single download is dist/installer/SecureRAG-Setup-0.2.0.exe. See docs/release-verification.md for the current build and verification status.

## Release check

Test on Windows x64 without Python, Node.js or ROCm installed: app launch, local Ollama connection, approved document summary, poisoned document rejection, model unavailable error, theme switching and reinstall. Measure startup time, RAM, response latency and animation smoothness on that machine. Review Qt/PyQt and model redistribution licences before publishing. This is not a macOS/Linux binary; those need separate builds.

References:
- https://tailwindcss.com/docs/installation/using-vite
- https://doc.qt.io/qtforpython-6/overviews/qtwebchannel-javascript.html
- https://pyinstaller.org/en/stable/usage.html

The integration update is documented in [integration-improvements.md](integration-improvements.md).
Appearance preferences and conversations now persist; overviews process all approved
excerpts in stages. The earlier single-turn/eight-excerpt statements above describe
the first UI version and are superseded by that document.

