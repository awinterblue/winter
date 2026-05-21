' Winter launcher — double-click to start the assistant with no window.
' Winter appears in the system tray. If it does NOT appear, open the file
' "winter.log" in this folder — it captures any startup error.
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
py = dir & "\.venv\Scripts\python.exe"
logFile = dir & "\winter.log"
sh.Run "cmd /c """ & py & """ -m winter > """ & logFile & """ 2>&1", 0, False
