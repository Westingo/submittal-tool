# Build SubmittalBuilder.exe and assemble a movable, standalone distribution.
#
#   .\package.ps1
#
# Produces dist\SubmittalBuilder\ (the runnable app: exe + runtime +
# library + presets) and dist\SubmittalBuilder.zip for handing to another
# machine. The target machine needs nothing installed — unzip and
# double-click SubmittalBuilder.exe.
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$pyi = Join-Path $here ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyi)) {
  Write-Host "Run run.bat once first so the .venv exists, then re-run this." -ForegroundColor Yellow
  exit 1
}

$out = Join-Path $here "dist\SubmittalBuilder"

# Clear any leftover library/presets JUNCTIONS from a previous run first —
# if they're present when PyInstaller wipes the output dir, the exe copy
# gets disrupted. rmdir (no /S) removes only the link, never the target.
foreach ($name in "library", "presets") {
  $p = Join-Path $out $name
  if (Test-Path $p) { cmd /c rmdir "$p" 2>$null }
}

Write-Host "Building SubmittalBuilder.exe (a few minutes)..."
Remove-Item Env:\SB_CONSOLE -ErrorAction SilentlyContinue   # windowed, no console
& $pyi SubmittalBuilder.spec --noconfirm --distpath dist --workpath build_pyi | Out-Null
if ($LASTEXITCODE -ne 0) { Write-Host "Build failed." -ForegroundColor Red; exit 1 }
if (-not (Test-Path (Join-Path $out "SubmittalBuilder.exe"))) {
  Write-Host "Build finished but SubmittalBuilder.exe is missing." -ForegroundColor Red; exit 1
}

# Place the editable data next to the exe (real copies so the folder is
# self-contained and movable). Clear any leftover junction from testing
# WITHOUT following it (rmdir on a junction removes only the link).
foreach ($name in "library", "presets") {
  $dst = Join-Path $out $name
  if (Test-Path $dst) { cmd /c rmdir "$dst" 2>$null }
  Write-Host "Copying $name ..."
  Copy-Item -Recurse -Force (Join-Path $here $name) $dst
}

$zip = Join-Path $here "dist\SubmittalBuilder.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Write-Host "Zipping -> $zip"
Compress-Archive -Path $out -DestinationPath $zip

$mb = "{0:N0}" -f ((Get-Item $zip).Length / 1MB)
Write-Host ""
Write-Host "Done. Distributable: dist\SubmittalBuilder.zip ($mb MB)" -ForegroundColor Green
Write-Host "Unzip on any Windows PC and double-click SubmittalBuilder.exe."
