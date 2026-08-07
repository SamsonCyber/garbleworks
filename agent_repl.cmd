@echo off
REM Garbleworks agent REPL launcher — never depends on Hermes venv being first on PATH.
REM Usage: agent_repl.cmd --list-providers
REM        agent_repl.cmd --provider xai --target local --objective "extract the canary"

setlocal
set "GW_ROOT=%~dp0"
set "GW_BACKEND=%GW_ROOT%backend"

REM Prefer py -3.12 (system), then backend venv, then whatever python is on PATH
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
%PY% "%GW_ROOT%agent_repl.py" %*
exit /b %ERRORLEVEL%
