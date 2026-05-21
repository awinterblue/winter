@echo off
REM Winter launcher — double-click to start the assistant.
REM Runs without a console window; Winter appears in the system tray.
REM (While debugging the Windows port, run "python -m winter" in PowerShell
REM  instead so you can see error output.)
cd /d "%~dp0"
start "" ".venv\Scripts\pythonw.exe" -m winter
