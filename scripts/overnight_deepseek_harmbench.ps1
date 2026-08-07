# Overnight HarmBench full vs DeepSeek V4 via OpenCode Zen
# Resume-friendly. Authorized RoE: backend/engagements/opencode-deepseek-roe.json
# Usage:
#   powershell -NoProfile -File scripts\overnight_deepseek_harmbench.ps1
#   powershell -NoProfile -File scripts\overnight_deepseek_harmbench.ps1 -Workers 2 -Timeout 100

param(
  [int]$Workers = 2,
  [float]$Timeout = 100,
  [string]$Model = "deepseek-v4-flash-free",
  [switch]$FinalizeOnly,
  [switch]$NoStart   # write config + status only
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$Root\backend\harmbench_deepseek_run.py")) {
  $Root = "C:\Code\garbleworks"
}
$Backend = Join-Path $Root "backend"
$Results = Join-Path $Backend "bench\results"
$Stamp = Get-Date -Format "yyyy-MM-dd"
$RunDir = Join-Path $Results "overnight-deepseek-$Stamp"
New-Item -ItemType Directory -Force -Path $RunDir | Out-Null

$Ckpt = Join-Path $Results "harmbench-deepseek-full-checkpoint.json"
$Out  = Join-Path $Results "harmbench-deepseek-full.json"
$Log  = Join-Path $RunDir "runner.log"
$PidFile = Join-Path $RunDir "runner.pid"
$Status = Join-Path $RunDir "status.json"
$Roe = Join-Path $Backend "engagements\opencode-deepseek-roe.json"
$KeyFile = Join-Path $env:USERPROFILE ".secrets\opencode_api_key.txt"

if (-not (Test-Path $KeyFile)) { throw "Missing OpenCode key: $KeyFile" }
if (-not (Test-Path $Roe)) { throw "Missing RoE: $Roe" }

# Load key into process env (not printed)
$env:OPENCODE_API_KEY = (Get-Content -Raw $KeyFile).Trim()
$env:GARBLEWORKS_TARGET_MODEL = $Model
$env:GARBLEWORKS_TARGET_MAX_TOKENS = "1536"
$env:GARBLEWORKS_ADAPTIVE_LADDER = "1"
$env:PYTHONUNBUFFERED = "1"
# Prevent MiniMax openai_compat contamination
Remove-Item Env:OPENAI_COMPAT_MODEL -ErrorAction SilentlyContinue
Remove-Item Env:OPENAI_COMPAT_BASE_URL -ErrorAction SilentlyContinue
Remove-Item Env:OPENAI_COMPAT_API_KEY -ErrorAction SilentlyContinue

$cfg = [ordered]@{
  started_utc = (Get-Date).ToUniversalTime().ToString("o")
  root = $Root
  backend = $Backend
  model = $Model
  workers = $Workers
  timeout = $Timeout
  checkpoint = $Ckpt
  out = $Out
  roe = $Roe
  log = $Log
  engagement_id = "opencode-deepseek-v4-2026-08-05"
  estimand = "harmbench_heuristic_compliance (not official HB classifier)"
  fire_path = "loopback canary -> opencode.ai/zen/v1"
  resume = (Test-Path $Ckpt)
}
$cfg | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $RunDir "run-config.json")

function Write-Status($phase, $extra=@{}) {
  $n_done = $null; $n_pop = $null; $updated = $null; $cracked = $null; $held = $null
  if (Test-Path $Ckpt) {
    try {
      $d = Get-Content -Raw $Ckpt | ConvertFrom-Json
      $n_done = $d.n_done; $n_pop = $d.n_population; $updated = $d.updated
      $cracked = @($d.results_by_id.PSObject.Properties | Where-Object {
        $_.Value.cracked -or $_.Value.winner
      }).Count
      $held = @($d.results_by_id.PSObject.Properties | Where-Object { $_.Value.held }).Count
    } catch {}
  }
  $obj = [ordered]@{
    phase = $phase
    utc = (Get-Date).ToUniversalTime().ToString("o")
    n_done = $n_done
    n_population = $n_pop
    cracked = $cracked
    held = $held
    checkpoint_updated = $updated
    log = $Log
    pidfile = $PidFile
  }
  foreach ($k in $extra.Keys) { $obj[$k] = $extra[$k] }
  $obj | ConvertTo-Json | Set-Content -Encoding utf8 $Status
}

Write-Status "configured" @{ workers = $Workers; model = $Model }

if ($NoStart) {
  Write-Host "Config only. RunDir=$RunDir"
  exit 0
}

if ($FinalizeOnly) {
  Write-Status "finalize-only"
  Set-Location $Backend
  py -3.12 -u harmbench_deepseek_run.py --finalize-only --checkpoint $Ckpt --out $Out --roe $Roe *
    Tee-Object -FilePath $Log -Append
  Write-Status "finalize-done"
  exit $LASTEXITCODE
}

# Refuse double-start if pid alive
if (Test-Path $PidFile) {
  $old = (Get-Content -Raw $PidFile).Trim()
  if ($old -match '^\d+$') {
    $proc = Get-Process -Id ([int]$old) -ErrorAction SilentlyContinue
    if ($proc) {
      Write-Host "Already running PID $old ($($proc.ProcessName)). Abort."
      Write-Status "already-running" @{ pid = [int]$old }
      exit 3
    }
  }
}

Write-Status "starting" @{ workers = $Workers }
Set-Location $Backend

$argList = @(
  "-3.12", "-u", "harmbench_deepseek_run.py",
  "--full",
  "--timeout", "$Timeout",
  "--workers", "$Workers",
  "--checkpoint", $Ckpt,
  "--out", $Out,
  "--roe", $Roe
)

$stdout = Join-Path $RunDir "stdout.log"
$stderr = Join-Path $RunDir "stderr.log"

$p = Start-Process -FilePath "py" -ArgumentList $argList `
  -WorkingDirectory $Backend `
  -RedirectStandardOutput $stdout `
  -RedirectStandardError $stderr `
  -PassThru -WindowStyle Hidden

$p.Id | Set-Content -Encoding ascii $PidFile
# also append combined log header
@"
==== start $(Get-Date -Format o) pid=$($p.Id) workers=$Workers model=$Model ====
stdout: $stdout
stderr: $stderr
"@ | Set-Content -Encoding utf8 $Log

Write-Status "running" @{ pid = $p.Id; workers = $Workers; stdout = $stdout; stderr = $stderr }
Write-Host "Started DeepSeek HarmBench overnight"
Write-Host "  PID:      $($p.Id)"
Write-Host "  RunDir:   $RunDir"
Write-Host "  Ckpt:     $Ckpt"
Write-Host "  Out:      $Out"
Write-Host "  Workers:  $Workers"
Write-Host "  Monitor:  powershell -NoProfile -File $Root\scripts\monitor_deepseek_harmbench.ps1"
exit 0
