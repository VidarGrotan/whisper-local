@echo off
setlocal
set "PROJECT=C:\Dev\whisper-local"
set "SITE=%PROJECT%\.venv\Lib\site-packages"
set "PATH=%SITE%\nvidia\cuda_runtime\bin;%SITE%\nvidia\cublas\bin;%SITE%\nvidia\cudnn\bin;%PATH%"
"%PROJECT%\.venv\Scripts\whisper-local.exe" %*
