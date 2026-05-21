@echo off
REM Winter launcher (console version) — shows live output, good for debugging.
REM For a clean no-window launch, double-click winter.vbs instead.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m winter
