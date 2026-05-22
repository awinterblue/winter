# Creates a "Winter" shortcut on your Desktop, pointing at winter.vbs.
#
# Resolves the real Desktop folder via [Environment]::GetFolderPath, so it
# works even when OneDrive has redirected the Desktop. Run it any time with:
#
#   powershell -ExecutionPolicy Bypass -File scripts\make-shortcut.ps1
#
$ErrorActionPreference = "Stop"

$root = Split-Path $PSScriptRoot -Parent
$desktop = [Environment]::GetFolderPath('Desktop')

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut((Join-Path $desktop 'Winter.lnk'))
$shortcut.TargetPath = Join-Path $root 'winter.vbs'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Winter - AI desktop assistant'
$shortcut.Save()

Write-Host "Created a Winter shortcut on your Desktop:"
Write-Host "  $(Join-Path $desktop 'Winter.lnk')"
