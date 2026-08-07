# Single-word Garbleworks agent launcher (PowerShell).
# Usage: .\gw.ps1
#        .\gw.ps1 setup
#        .\gw.ps1 --provider minimax
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Backend = Join-Path $Root "backend"

function Resolve-Python {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        try {
            & py -3.12 -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0) { return @("py", "-3.12") }
        } catch {}
    }
    $venvPy = Join-Path $Backend ".venv\Scripts\python.exe"
    if (Test-Path $venvPy) { return @($venvPy) }
    $sys312 = Join-Path $env:LocalAppData "Programs\Python\Python312\python.exe"
    if (Test-Path $sys312) { return @($sys312) }
    return @("python")
}

$env:PYTHONPATH = "$Backend;$($env:PYTHONPATH)"
$py = Resolve-Python
$shim = Join-Path $Root "gw.py"
& $py[0] @($py[1..($py.Length-1)]) $shim @Args
exit $LASTEXITCODE
