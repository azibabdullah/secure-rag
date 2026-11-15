$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$buildPython = Join-Path $projectRoot '.build-venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $buildPython)) { throw 'Create the CPU .build-venv as described in docs/web-dashboard-guide.md first.' }
& $buildPython -c "import torch; assert torch.version.cuda is None and torch.version.hip is None, 'Use CPU torch for this release build'"
if ($LASTEXITCODE -ne 0) { throw 'CPU build environment validation failed.' }
npm --prefix frontend ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
& $buildPython -m PyInstaller --noconfirm --clean --onedir --windowed --name SecureRAG --add-data 'frontend/dist:frontend/dist' --add-data 'models/securerag-classifier-FINAL:models/securerag-classifier-FINAL' --add-data 'models/embeddings/all-MiniLM-L6-v2:models/embeddings/all-MiniLM-L6-v2' --collect-all chromadb --collect-all sentence_transformers --collect-all transformers --collect-all tokenizers desktop.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
# Qt uses the Windows ICU API. A developer PATH containing Poppler can make
# PyInstaller collect an incompatible third-party icuuc.dll with this same name.
# Leave it to the supported Windows installation instead of shipping that DLL.
$foreignIcu = Join-Path $projectRoot 'dist\SecureRAG\_internal\icuuc.dll'
if (Test-Path -LiteralPath $foreignIcu) { Remove-Item -LiteralPath $foreignIcu -Force }
Write-Output 'Test dist\SecureRAG\SecureRAG.exe before compiling the installer.'
$releaseReport = Join-Path $projectRoot 'dist\packaged-self-test.json'
$releaseProcess = Start-Process -FilePath (Join-Path $projectRoot 'dist\SecureRAG\SecureRAG.exe') -ArgumentList '--self-test', $releaseReport -WindowStyle Hidden -Wait -PassThru
if ($releaseProcess.ExitCode -ne 0) { throw "Packaged checks failed. Read $releaseReport" }
$compiler = Join-Path $projectRoot 'build\tools\inno\ISCC.exe'
if (!(Test-Path -LiteralPath $compiler)) {
    $installedCompiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($installedCompiler) { $compiler = $installedCompiler.Source }
}
if (Test-Path -LiteralPath $compiler) {
    & $compiler 'installer\SecureRAG.iss'
    if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed.' }
} else { Write-Output 'Install Inno Setup and compile installer\SecureRAG.iss to create the setup download.' }
