@echo off
REM Single-word Garbleworks agent (Hermes venv-safe).
REM Usage: gw
REM        gw setup
REM        gw --provider minimax

setlocal
set "GW_ROOT=%~dp0"
set "GW_BACKEND=%GW_ROOT%backend"

set "PY="
where py >nul 2>&1 && (
  py -3.12 -c "import sys" >nul 2>&1 && set "PY=py -3.12"
)
if not defined PY if exist "%GW_BACKEND%\.venv\Scripts\python.exe" (
  set "PY=%GW_BACKEND%\.venv\Scripts\python.exe"
)
if not defined PY if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PY=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PY set "PY=python"

set "PYTHONPATH=%GW_BACKEND%;%PYTHONPATH%"
%PY% "%GW_ROOT%gw.py" %*
exit /b %ERRORLEVEL%
