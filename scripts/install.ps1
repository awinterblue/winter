# Winter — one-step install for Windows.
#
# Prerequisites (install these first):
#   - uv      : winget install astral-sh.uv
#   - Ollama  : https://ollama.com
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv is required but not installed."
    Write-Host "Install it with:  winget install astral-sh.uv"
    exit 1
}

Write-Host "Creating the Python environment..."
uv venv --python 3.12 .venv

Write-Host "Installing Winter and its dependencies (a few GB, one time)..."
uv pip install -e .

Write-Host ""
Write-Host "Winter is installed."
if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Write-Host "Next: install Ollama from https://ollama.com, then run:"
    Write-Host "    ollama pull llama3.2:3b"
} else {
    Write-Host "Make sure the model is pulled:  ollama pull llama3.2:3b"
}
Write-Host "Start Winter with:       .venv\Scripts\python -m winter"
Write-Host "Optional voice cloning:  .venv\Scripts\python scripts\setup_voice.py"
