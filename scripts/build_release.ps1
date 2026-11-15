<#
  SecureRAG release build.

  Run from E:\SecureRAG (PowerShell or the Antigravity terminal):
      powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1

  Produces two things:
    dist\SecureRAG\SecureRAG.exe                   the app itself; runs from this folder or a terminal
    dist\installer\SecureRAG-Setup-<version>.exe   one installer to upload to GitHub Releases
    dist\installer\SHA256SUMS-<version>.txt        checksum so downloaders can verify the installer

  Steps: preflight checks -> web interface -> PyInstaller -> packaged self-test -> installer -> checksum.
  Uses .build-venv (CPU PyTorch), so the packaged app runs on any 64-bit Windows PC without a GPU.
  Your development environment (.venv, ROCm) is not touched.
#>
param(
    [string]$Version = "1.0.0",
    [string]$Iscc = "",
    [switch]$SkipFrontend,
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root
function Step($text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
$python = Join-Path $Root ".build-venv\Scripts\python.exe"

Step "1/6 Preflight checks"
foreach ($m in "models\securerag-classifier-FINAL", "models\securerag-docguard-v3-seed2", "models\embeddings\all-MiniLM-L6-v2") {
    if (-not (Test-Path -LiteralPath $m)) { throw "Missing $m. Copy it into place before building." }
}
foreach ($f in "models\securerag-classifier-FINAL\model.safetensors", "models\securerag-docguard-v3-seed2\model.safetensors",
               "models\securerag-docguard-v3-seed2\classifier_config.json", "assets\securerag.ico") {
    if (-not (Test-Path -LiteralPath $f)) { throw "Missing $f." }
}
if ((Get-Item "models\securerag-classifier-FINAL\model.safetensors").Length -lt 100MB) {
    throw "FINAL model.safetensors is tiny: it is probably a Git LFS pointer. Run 'git lfs pull' first."
}
if (-not (Test-Path -LiteralPath $python)) { throw "Build environment .build-venv not found (expected $python)." }

# CPU-only PyTorch keeps the app portable and the installer under GitHub's 2 GiB limit.
& $python -c "import torch, sys; ok = torch.version.cuda is None and torch.version.hip is None; print('torch', torch.__version__, '(CPU)' if ok else '(GPU build)'); sys.exit(0 if ok else 1)"
if ($LASTEXITCODE) { throw ".build-venv has a GPU build of PyTorch. Install the CPU wheel there: pip install torch --index-url https://download.pytorch.org/whl/cpu" }

# Every package the app imports must be importable before PyInstaller runs.
& $python -c "import PyQt6.QtWebEngineWidgets, chromadb, sentence_transformers, transformers, tokenizers, safetensors, pypdf, pypdfium2, docx, httpx, cryptography, PyInstaller; print('Dependencies OK | PyInstaller', PyInstaller.__version__)"
if ($LASTEXITCODE) { throw "A dependency is missing in .build-venv. Run: .build-venv\Scripts\python -m pip install -r requirements-desktop.txt" }

if (-not $SkipInstaller) {
    $candidates = @($Iscc, "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
                    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", (Join-Path $Root "build\tools\inno\ISCC.exe"))
    $Iscc = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $Iscc) { $found = Get-Command ISCC.exe -ErrorAction SilentlyContinue; if ($found) { $Iscc = $found.Source } }
    if (-not $Iscc) { throw "Inno Setup 6 not found. Install it with: winget install JRSoftware.InnoSetup  (or rerun with -SkipInstaller)" }
    Write-Host "Inno Setup: $Iscc"
}

Step "2/6 Building the web interface"
if ($SkipFrontend) { Write-Host "Skipped (using existing frontend\dist)" }
elseif ((Get-Command npm -ErrorAction SilentlyContinue) -and (Test-Path -LiteralPath "frontend\node_modules")) {
    npm --prefix frontend run build
    if ($LASTEXITCODE) { throw "Frontend build failed" }
}
else { Write-Host "npm or frontend\node_modules not found; using the existing frontend\dist" -ForegroundColor Yellow }
if (-not (Test-Path -LiteralPath "frontend\dist\index.html")) { throw "frontend\dist is missing." }

Step "3/6 Packaging with PyInstaller (10-20 minutes)"
& $python -m PyInstaller SecureRAG.spec --noconfirm --clean
if ($LASTEXITCODE) { throw "PyInstaller failed" }
foreach ($m in "securerag-classifier-FINAL", "securerag-docguard-v3-seed2") {
    if (-not (Get-ChildItem -Recurse "dist\SecureRAG" -Filter "model.safetensors" | Where-Object { $_.DirectoryName -like "*$m" })) {
        throw "$m was not bundled. Check the datas list in SecureRAG.spec."
    }
}
# Qt uses the Windows ICU library. A developer PATH containing Poppler can make PyInstaller
# collect an incompatible icuuc.dll with the same name; leave it to Windows instead.
$foreignIcu = Join-Path $Root "dist\SecureRAG\_internal\icuuc.dll"
if (Test-Path -LiteralPath $foreignIcu) { Remove-Item -LiteralPath $foreignIcu -Force; Write-Host "Removed a conflicting icuuc.dll" }

Step "4/6 Self-test of the packaged app (CPU, throwaway profile; your data is not touched)"
$report = Join-Path $Root "dist\selftest.json"
Remove-Item -LiteralPath $report -ErrorAction SilentlyContinue
$p = Start-Process -FilePath (Join-Path $Root "dist\SecureRAG\SecureRAG.exe") -ArgumentList "--self-test", "`"$report`"" -WindowStyle Hidden -Wait -PassThru
if (-not (Test-Path -LiteralPath $report)) { throw "The packaged app did not write $report (exit code $($p.ExitCode))." }
$result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if (-not $result.passed) { Get-Content -LiteralPath $report; throw "Packaged self-test failed. See dist\selftest.json" }
Write-Host "Self-test passed: device=$($result.device), PromptGuard=$($result.classifier.label), DocumentGuard=$($result.document_guard.label), indexed=$($result.ingestion.indexed_chunks), interface loaded=$($result.frontend_loaded)" -ForegroundColor Green

if ($SkipInstaller) {
    Write-Host "`nDone (installer skipped). Run the app with: .\dist\SecureRAG\SecureRAG.exe" -ForegroundColor Green
    return
}

Step "5/6 Building the installer with Inno Setup"
& $Iscc "/DAppVersion=$Version" "installer\SecureRAG.iss"
if ($LASTEXITCODE) { throw "Inno Setup failed" }
$exe = "dist\installer\SecureRAG-Setup-$Version.exe"

Step "6/6 Checksum and size"
$hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLower()
"$hash  SecureRAG-Setup-$Version.exe" | Set-Content -LiteralPath "dist\installer\SHA256SUMS-$Version.txt" -Encoding ascii
$size = (Get-Item -LiteralPath $exe).Length
"{0}  {1:N2} GB" -f $exe, ($size / 1GB) | Write-Host
if ($size -ge 2GB) { Write-Host "WARNING: over 2 GiB. GitHub Releases rejects files this large." -ForegroundColor Red }
else { Write-Host "Under GitHub's 2 GiB per-file limit." -ForegroundColor Green }
Write-Host "SHA-256: $hash"
Write-Host "`nDone." -ForegroundColor Green
Write-Host "  Run on this PC:        .\dist\SecureRAG\SecureRAG.exe   (or install with $exe)"
Write-Host "  Upload to GitHub:      $exe  and  dist\installer\SHA256SUMS-$Version.txt"
Write-Host "  Release notes:         docs\release-notes-$Version.md"
