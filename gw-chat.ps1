# Launch Garbleworks red-team chat on the pi TUI.
# Prefer native gw-chat.exe when present (build: scripts\build-gw-chat.ps1).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $Root "gw-chat.exe"
if (Test-Path $exe) {
    & $exe @args
    exit $LASTEXITCODE
}

Set-Location $Root

# Prefer pi.cmd (avoids PowerShell execution-policy blocks on pi.ps1)
$piCmd = $null
$npmPi = Join-Path $env:APPDATA "npm\pi.cmd"
if (Test-Path $npmPi) { $piCmd = $npmPi }
elseif (Get-Command pi.cmd -ErrorAction SilentlyContinue) {
    $piCmd = (Get-Command pi.cmd).Source
}
elseif (Get-Command pi -ErrorAction SilentlyContinue) {
    $piCmd = (Get-Command pi).Source
}
if (-not $piCmd) {
    Write-Host "pi not found on PATH."
    Write-Host "Install: npm i -g --ignore-scripts @earendil-works/pi-coding-agent"
    exit 1
}

$pkg = Join-Path $Root "pi-garbleworks"
if (-not (Test-Path $pkg)) {
    Write-Host "missing pi-garbleworks at $pkg"
    exit 1
}

# Prefer system py -3.12 over Hermes venv `python` (missing agent_repl)
if (-not $env:GARBLEWORKS_PYTHON) {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { $env:GARBLEWORKS_PYTHON = "py" }
}
$env:PYTHONIOENCODING = "utf-8"
Write-Host "Garbleworks · pi red-team chat"
Write-Host "  package: $pkg"
Write-Host "  pi: $piCmd"
Write-Host "  /gw for status · talk normally · tools fire for real"
Write-Host ""

# --no-builtin-tools: only gw_* tools (Finbot-style), not read/edit/bash
# Pass --coding after -- to re-enable coding tools via /gw mode inside session
& $piCmd -e $pkg --no-builtin-tools @args
exit $LASTEXITCODE
