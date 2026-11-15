# Publishing SecureRAG for other people

## Current state

The installer is already built: dist/installer/SecureRAG-Setup-0.2.0.exe
(1,029,388,379 bytes). The same folder now contains SecureRAG-Quick-Start.pdf and
SHA256SUMS.txt. The canonical PDF also lives under output/pdf/. Nothing has been
uploaded or published by this task.

This is a Windows x64 preview. It is not yet certified on a clean separate PC.
It is unsigned. The 3B generator is selectable after download, while the recorded
real-model regressions used llama3:8b. Review dependency/model redistribution
licences and required corresponding source/notices before public distribution;
PyQt is GPLv3/commercial, not LGPL. Signing and licensing are separate matters.

## First: test on a teammate's Windows PC

Send the three release assets together through a trusted file-transfer channel.
The recipient needs no Python, Node.js, ROCm, Git or development environment.
Install on Windows x64 (start with Windows 11); 16 GB RAM and 12-15 GB free disk
space are planning recommendations, not measured minimums. A GPU is optional.

1. Verify the installer hash against SHA256SUMS.txt from your trusted release.
2. Install and launch through the Start menu, without cloning this repository.
3. Install Ollama from https://ollama.com/download/windows and keep it running.
4. In a new PowerShell terminal, run `ollama pull llama3.2:3b`, then `ollama list`.
5. Refresh Local controls, select llama3.2:3b, and Connect model.
6. Test general chat; upload a benign TXT/PDF, summarize it, inspect citations.
7. Test an independent synthetic poisoned document and check its quarantine state.
8. Test a missing model, Stop/retry, restarting saved chats, theme persistence,
   and disconnecting the internet after initial setup/downloads.
9. Test installing a newer version over the old one, then uninstall through
   Windows Settings > Apps > Installed apps. Record Windows version, RAM/GPU,
   startup/generation times, failures, and whether profile data was retained.

Do not send your own %LOCALAPPDATA%\SecureRAG profile, vault key, uploaded documents,
training datasets or .venv with the installer. Each recipient gets their own key
and local profile. Llama models are downloaded by that recipient through Ollama.

## Publish using GitHub Releases

A custom website is optional. Release assets are intended for binary downloads;
GitHub permits individual files under 2 GiB, so this installer fits. Do not commit
the 1 GB installer into ordinary Git history or use GitHub Pages to host it.

1. Review and commit/push the exact tested source first. Current integration work
   may still be uncommitted. A release tag must identify the source matching the
   binary. Review privacy and dependency notices before making any repository public.
2. Open https://github.com/azibabdullah/SecureRAG, then Releases > Draft a new release.
3. Choose/create tag v0.2.0 on the tested commit. Use title 'SecureRAG 0.2.0 - Windows preview'.
4. Copy the contents of docs/release-notes-0.2.0.md into the release description.
5. Drag these three files from dist/installer into the assets box:
   SecureRAG-Setup-0.2.0.exe, SecureRAG-Quick-Start.pdf, SHA256SUMS.txt.
6. Wait for every upload to finish. Mark it as a pre-release while clean-PC testing
   is pending. Save as a draft if any release work remains.
7. Publish when you are ready. A public repository provides public release assets;
   private-repository releases require access. A separate public downloads repository
   is an alternative, with the corresponding source made available as required.
8. Share the published release page. Tell users to choose the .exe asset rather
   than GitHub's automatically generated Source code ZIP/TAR files.

After publishing that exact tag and asset name, the installer URL will be:
https://github.com/azibabdullah/SecureRAG/releases/download/v0.2.0/SecureRAG-Setup-0.2.0.exe
This is a future URL, not a download verified as live by this task.

An optional landing page can show a screenshot, requirements, installation guide
and a Download for Windows button linking to the release asset. It does not need
to host the LLM, user documents, a server, or the 1 GB binary itself. Start by
sharing the release page; build a branded website after the installer is tested.

## Signing and future versions

Unsigned builds can be warned about or blocked by Windows protection policies.
A public release should use an appropriate trusted code-signing certificate or
signing service for the application and installer. Signing the installer alone
does not sign every executable it installs, and signing is not a malware audit.
Do not instruct recipients to disable Windows protections. Signing may have a
cost; it is not configured by this project or required for building a test binary.
Do not choose a project licence without checking the dependencies' terms.

For a new version, update AppVersion/OutputBaseFilename in installer/SecureRAG.iss,
rebuild the frontend and app with scripts/build_desktop.ps1, test the actual
packaged executable and installation, and generate fresh checksums after signing.
Create a new release tag; do not quietly replace an installer under an old version.
The frozen classifier does not need retraining to package a new desktop version.

## Official references

- GitHub release assets and limits: https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases
- GitHub release creation: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- Ollama Windows: https://docs.ollama.com/windows
- Llama 3.2 3B: https://ollama.com/library/llama3.2:3b
- PyQt licensing: https://www.riverbankcomputing.com/software/pyqt/intro
- Windows signing: https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/code-signing-for-smart-app-control
