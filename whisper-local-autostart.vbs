Option Explicit

Dim shell, launcher
Set shell = CreateObject("WScript.Shell")
launcher = Chr(34) & "C:\Dev\whisper-local\whisper-local-user.cmd" & Chr(34)

' Run the proven CUDA-aware launcher without leaving a console window open.
shell.Run launcher, 0, False
