# One-shot setup + launch for the Garbleworks backend.
# Calls the venv python directly, so it does NOT depend on PowerShell
# execution policy or Activate.ps1.
#
# No --reload on purpose: the reloader spawns a parent + worker, and if the
# parent dies the worker orphans the socket -> an unkillable "phantom"
# LISTENING port (this is why 8000 got stuck). Single process = clean exit.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File run.ps1            # port 9877
#   powershell -ExecutionPolicy Bypass -File run.ps1 -Port 9000 # custom port
param([int]$Port = 9877)

$ErrorActionPreference = "Stop"
$backend = Join-Path $PSScriptRoot "backend"
$py = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    python -m venv (Join-Path $backend ".venv")
}
& $py -m pip install -q -r (Join-Path $backend "requirements.txt")

# Kill any existing app server first, so re-running never piles up duplicate
# instances on different ports.
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -match 'uvicorn' -and $_.CommandLine -match 'app:app' } |
  ForEach-Object {
    Write-Host "stopping existing app server (PID $($_.ProcessId))" -ForegroundColor DarkYellow
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Write-Host "Serving at http://127.0.0.1:$Port  (Ctrl+C to stop)" -ForegroundColor Cyan
& $py -m uvicorn app:app --host 127.0.0.1 --port $Port --app-dir $backend
