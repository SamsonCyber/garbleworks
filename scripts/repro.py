"""Independent offline repro for garbleworks (security + math audit)."""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

def main() -> int:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip", "-q"])
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "pytest", "-q"],
        cwd=BACKEND,
    )
    r1 = subprocess.call([sys.executable, "-m", "pytest", "-q", "test_security.py"], cwd=BACKEND)
    if r1 != 0:
        return r1
    r2 = subprocess.call([sys.executable, "benchmark_harness.py", "--fail-on-regression"], cwd=BACKEND)
    if r2 == 0:
        print("REPRO_OK garbleworks security + math audit")
    return r2

if __name__ == "__main__":
    raise SystemExit(main())
