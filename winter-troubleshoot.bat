@echo off
REM Winter — troubleshooting launcher. Runs Winter in a visible console so you
REM can watch for errors live. For normal use, start Winter from the Desktop
REM shortcut, or double-click winter.vbs (a clean, no-window launch).
REM
REM Note: closing this console window stops Winter — that's why it's only for
REM troubleshooting, not everyday launching.
cd /d "%~dp0"
".venv\Scripts\python.exe" -m winter
