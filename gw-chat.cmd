@echo off
REM Prefer native binary; fall back to PowerShell launcher.
if exist "%~dp0gw-chat.exe" (
  "%~dp0gw-chat.exe" %*
  exit /b %ERRORLEVEL%
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gw-chat.ps1" %*
