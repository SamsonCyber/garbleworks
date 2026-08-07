# Status snapshot + optional watch loop for overnight DeepSeek HarmBench
param(
  [switch]$Watch,
  [int]$EverySec = 120,
  [string]$Stamp = (Get-Date -Format "yyyy-MM-dd")
)

$Root = "C:\Code\garbleworks"
$Backend = Join-Path $Root "backend"
$Results = Join-Path $Backend "bench\results"
$RunDir = Join-Path $Results "overnight-deepseek-$Stamp"
if (-not (Test-Path $RunDir)) {
  $alt = Get-ChildItem $Results -Directory -Filter "overnight-deepseek-*" | Sort-Object Name -Descending | Select-Object -First 1
  if ($alt) { $RunDir = $alt.FullName }
}
$Ckpt = Join-Path $Results "harmbench-deepseek-full-checkpoint.json"
$Out  = Join-Path $Results "harmbench-deepseek-full.json"
$PidFile = Join-Path $RunDir "runner.pid"
$Status = Join-Path $RunDir "status.json"

function Get-Snapshot {
  $pidAlive = $false; $pid = $null
  if (Test-Path $PidFile) {
    $pid = [int]((Get-Content -Raw $PidFile).Trim())
    $pidAlive = [bool](Get-Process -Id $pid -ErrorAction SilentlyContinue)
  }
  $n_done=$null;$n_pop=$null;$updated=$null;$cracked=0;$held=0;$by_cat=@{}
  if (Test-Path $Ckpt) {
    $d = Get-Content -Raw $Ckpt | ConvertFrom-Json
    $n_done = $d.n_done; $n_pop = $d.n_population; $updated = $d.updated
    foreach ($prop in $d.results_by_id.PSObject.Properties) {
      $r = $prop.Value
      if ($r.cracked -or $r.winner) { $cracked++ } elseif ($r.held) { $held++ }
    }
  }
  $tail = ""
  $stdout = Join-Path $RunDir "stdout.log"
  if (Test-Path $stdout) {
    $tail = (Get-Content $stdout -Tail 12) -join "`n"
  }
  $asr = if ($n_done -and $n_done -gt 0) { [math]::Round($cracked / $n_done, 4) } else { $null }
  $pct = if ($n_pop) { [math]::Round(100.0 * $n_done / $n_pop, 1) } else { $null }
  $obj = [ordered]@{
    utc = (Get-Date).ToUniversalTime().ToString("o")
    run_dir = $RunDir
    pid = $pid
    running = $pidAlive
    n_done = $n_done
    n_population = $n_pop
    pct = $pct
    cracked = $cracked
    held = $held
    asr_among_done = $asr
    checkpoint_updated = $updated
    final_exists = (Test-Path $Out)
    stdout_tail = $tail
  }
  $obj | ConvertTo-Json | Set-Content -Encoding utf8 $Status
  return $obj
}

function Show($o) {
  Write-Host ("[{0}] running={1} pid={2} done={3}/{4} ({5}%) cracked={6} held={7} asr_done={8} ckpt={9}" -f `
    $o.utc, $o.running, $o.pid, $o.n_done, $o.n_population, $o.pct, $o.cracked, $o.held, $o.asr_among_done, $o.checkpoint_updated)
  if ($o.stdout_tail) { Write-Host "--- stdout tail ---"; Write-Host $o.stdout_tail }
}

if ($Watch) {
  while ($true) {
    $o = Get-Snapshot
    Show $o
    if (-not $o.running -and $o.final_exists) { Write-Host "Complete."; break }
    if (-not $o.running -and $o.n_done -ge $o.n_population -and $o.n_population) {
      Write-Host "Population done; runner exited."
      break
    }
    Start-Sleep -Seconds $EverySec
  }
} else {
  Show (Get-Snapshot)
}
