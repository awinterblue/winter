' Winter launcher — double-click to start Winter with no window.
' Winter then appears in the system tray (notification area).
' If it does NOT appear, run winter-troubleshoot.bat to see the error.
Dim fso, sh, dir, q
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
q = Chr(34)
sh.Run q & dir & "\.venv\Scripts\python.exe" & q & " -m winter", 0, False
