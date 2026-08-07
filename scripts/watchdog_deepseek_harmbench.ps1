# If the overnight runner dies before complete, restart resume (max N times).
param(
  [int]$MaxRestarts = 8,
  [int]$PollSec = 180,
  [int]$Workers = 2,
  [float]$Timeout = 100
)
$Root = "C:\Code\garbleworks"
$Results = Join-Path $Root "backend\bench\results"
$Stamp = Get-Date -Format "yyyy-MM-dd"
$RunDir = Join-Path $Results "overnight-deepseek-$Stamp"
$Ckpt = Join-Path $Results "harmbench-deepseek-full-checkpoint.json"
$Out = Join-Path $Results "harmbench-deepseek-full.json"
$PidFile = Join-Path $RunDir "runner.pid"
$WdLog = Join-Path $RunDir "watchdog.log"
$restarts = 0

function Log($m) {
  $line = "[{0}] {1}" -f (Get-Date -Format o), $m
  Add-Content -Encoding utf8 $WdLog $line
  Write-Host $line
}

function Done {
  if (Test-Path $Out) {
    try {
      $d = Get-Content -Raw $Out | ConvertFrom-Json
      if ($d.complete) { return $true }
    } catch {}
  }
  if (Test-Path $Ckpt) {
    $d = Get-Content -Raw $Ckpt | ConvertFrom-Json
    if ($d.n_done -ge $d.n_population -and $d.n_population -gt 0) { return $true }
  }
  return $false
}

function RunnerAlive {
  if (-not (Test-Path $PidFile)) { return $false }
  $pid = [int]((Get-Content -Raw $PidFile).Trim())
  return [bool](Get-Process -Id $pid -ErrorAction SilentlyContinue)
}

Log "watchdog start max_restarts=$MaxRestarts workers=$Workers"
while ($true) {
  if (Done) { Log "complete — exiting watchdog"; break }
  if (RunnerAlive) {
    Start-Sleep -Seconds $PollSec
    continue
  }
  # dead and not complete
  if ($restarts -ge $MaxRestarts) {
    Log "FATAL: max restarts reached ($MaxRestarts) with incomplete run"
    exit 2
  }
  $restarts++
  Log "runner dead; resume restart #$restarts"
  & powershell -NoProfile -File (Join-Path $Root "scripts\overnight_deepseek_harmbench.ps1") -Workers $Workers -Timeout $Timeout
  Start-Sleep -Seconds 30
}
exit 0
