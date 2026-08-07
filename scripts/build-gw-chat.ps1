# Build gw-chat.exe (native launcher) into the repo root.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Out = Join-Path $Root "gw-chat.exe"
$Src = Join-Path $Root "cmd\gw-chat"

if (-not (Get-Command go -ErrorAction SilentlyContinue)) {
    Write-Host "go not found on PATH. Install Go 1.22+."
    exit 1
}

Push-Location $Src
try {
    go build -ldflags="-s -w" -o $Out .
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Write-Host "built $Out"
Get-Item $Out | Format-List Name, Length, LastWriteTime
