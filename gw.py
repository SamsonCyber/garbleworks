#!/usr/bin/env python3
"""Single-word launcher: gw → Garbleworks agent app (any cwd / Hermes venv-safe).

  py -3.12 C:\\code\\garbleworks\\gw.py
  gw                          (after pip install -e .)
"""
from __future__ import annotations

import runpy
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"
if not _BACKEND.is_dir():
    sys.stderr.write(f"garbleworks backend missing: {_BACKEND}\n")
    raise SystemExit(2)

sys.path.insert(0, str(_BACKEND))

if __name__ == "__main__":
    sys.argv[0] = "gw"
    runpy.run_module("agent_repl", run_name="__main__", alter_sys=True)
