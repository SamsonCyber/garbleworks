# Restart the Garbleworks UI on :9877 (matches run.ps1 default).
# Kills the existing PID bound to the port, then relaunches via run.ps1.
# Run from an interactive desktop session (the listening PID lives in user
# session 1, not in headless shells).
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File restart-server.ps1
#
# After restart, /ops should report the new op count and the descriptions
# should match the source in backend/ops/*.py.

$ErrorActionPreference = "Stop"
$port = 9877

# Find the PID currently listening on $port. Try netstat first (always
# available), fall back to Get-NetTCPConnection if PowerShell 5+.
function Get-ListeningPid {
    param([int]$Port)
    $line = netstat -ano -p TCP | Select-String ":$Port\s+.*LISTENING\s+(\d+)$" | Select-Object -First 1
    if ($line) {
        return ([regex]::Match($line, "LISTENING\s+(\d+)")).Groups[1].Value
    }
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($conn) { return [string]$conn.OwningProcess }
    }
    return $null
}

$pid8000 = Get-ListeningPid -Port $port
if ($pid8000) {
    Write-Host "Killing PID $pid8000 on :$port..." -ForegroundColor Yellow
    try {
        Stop-Process -Id ([int]$pid8000) -Force -ErrorAction Stop
    } catch {
        Write-Host "Stop-Process failed: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "This shell cannot reach PID $pid8000 (different Windows session)." -ForegroundColor Red
        Write-Host "Open an interactive PowerShell on the desktop session and run:" -ForegroundColor Red
        Write-Host "    Stop-Process -Id $pid8000 -Force" -ForegroundColor Red
        exit 1
    }
    Start-Sleep -Milliseconds 500
} else {
    Write-Host "Nothing currently listening on :$port." -ForegroundColor DarkGray
}

# Launch the server. Use Start-Process so it survives this script's exit and
# so the user sees the uvicorn banner in a fresh console window.
$runPs1 = Join-Path $PSScriptRoot "run.ps1"
if (-not (Test-Path $runPs1)) {
    Write-Host "Missing $runPs1" -ForegroundColor Red
    exit 1
}

Write-Host "Starting server via run.ps1..." -ForegroundColor Cyan
Start-Process -FilePath "powershell.exe" `
    -ArgumentList "-ExecutionPolicy", "Bypass", "-File", "`"$runPs1`"" `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Normal

# Give uvicorn a moment to bind, then sanity-check.
Start-Sleep -Seconds 2
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -UseBasicParsing -TimeoutSec 5
    Write-Host "Health: $($resp.Content)" -ForegroundColor Green
} catch {
    Write-Host "Server didn't come up on :$port within 5s. Check the new console window." -ForegroundColor Yellow
}