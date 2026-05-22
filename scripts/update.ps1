# Winter — fetch the latest version and reinstall (Windows).
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Fetching the latest Winter..."
git pull

Write-Host "Updating dependencies..."
uv pip install -e .

Write-Host ""
Write-Host "Winter is up to date. Restart it to use the new version."
