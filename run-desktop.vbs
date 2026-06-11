Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "F:\Project\Image-to-Text"
WshShell.Run "cmd /c .venv\Scripts\pythonw.exe desktop_launcher.py", 0, False
