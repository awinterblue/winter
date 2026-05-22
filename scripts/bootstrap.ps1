# Winter — bootstrap installer for Windows.
#
# Installs everything Winter needs — uv, Ollama, Git, Winter itself, and the
# AI model — into a "Winter" folder in your home directory. Run it with:
#
#   irm https://raw.githubusercontent.com/awinterblue/winter/main/scripts/bootstrap.ps1 | iex
#
# Windows can't see a freshly-installed tool until a new window opens, so if
# any prerequisite was missing, run the command a second time to finish.

$ErrorActionPreference = "Stop"
$InstallDir = "$HOME\Winter"
$Repo = "https://github.com/awinterblue/winter.git"

function Have($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Winget($id) {
    winget install --id $id -e --silent --accept-source-agreements `
        --accept-package-agreements
}

Write-Host "`n==> Installing Winter..." -ForegroundColor Cyan

# --- prerequisites (uv, Git, Ollama) ---------------------------------------
$installedSomething = $false
if (-not (Have uv))     { Write-Host "Installing uv...";     Winget "astral-sh.uv";  $installedSomething = $true }
if (-not (Have git))    { Write-Host "Installing Git...";    Winget "Git.Git";       $installedSomething = $true }
if (-not (Have ollama)) { Write-Host "Installing Ollama..."; Winget "Ollama.Ollama"; $installedSomething = $true }

if ($installedSomething) {
    Write-Host "`nPrerequisites installed. Open a NEW PowerShell window and run" -ForegroundColor Yellow
    Write-Host "the same command once more to finish installing Winter." -ForegroundColor Yellow
    return
}

# --- download Winter -------------------------------------------------------
Write-Host "`n==> Downloading Winter to $InstallDir..." -ForegroundColor Cyan
if (Test-Path "$InstallDir\.git") {
    git -C "$InstallDir" pull --ff-only
} else {
    git clone $Repo "$InstallDir"
}

# --- install Winter --------------------------------------------------------
Write-Host "`n==> Installing Winter's dependencies (a few GB, one time)..." -ForegroundColor Cyan
Set-Location $InstallDir
uv venv --python 3.12 .venv
uv pip install -e .

# --- the AI model ----------------------------------------------------------
Write-Host "`n==> Downloading the AI model (~2 GB)..." -ForegroundColor Cyan
ollama pull llama3.2:3b

Write-Host "`n==> Winter is installed at $InstallDir" -ForegroundColor Green
Write-Host "Double-click  winter.vbs  in that folder to start it."
Write-Host "To enable voice cloning later:  .venv\Scripts\python scripts\setup_voice.py"
explorer $InstallDir
