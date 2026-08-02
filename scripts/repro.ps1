# Independent repro: security suite + offline math audit (no external model APIs).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\backend")
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt pytest -q
python -m pytest -q test_security.py
python benchmark_harness.py --fail-on-regression
Write-Output "REPRO_OK garbleworks security + math audit"
