#!/usr/bin/env bash
# Independent repro: security suite + offline math audit (no external model APIs).
set -euo pipefail
cd "$(dirname "$0")/.."
cd backend
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt pytest -q
python -m pytest -q test_security.py
python benchmark_harness.py --fail-on-regression
echo "REPRO_OK garbleworks security + math audit"
