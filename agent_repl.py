#!/usr/bin/env python3
"""Launch Garbleworks agent REPL from any cwd / any Python (incl. Hermes venv).

Hermes puts its venv first on PATH. `python -m agent_repl` then fails with
"No module named agent_repl". This shim puts backend/ on sys.path and runs the
real package. Prefer:

  py -3.12 C:\\code\\garbleworks\\agent_repl.py --list-providers
  py -3.12 C:\\code\\garbleworks\\agent_repl.py --provider xai --target local

Or the .cmd wrapper (same args).
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

# Front of path so backend wins over any other site-packages
sys.path.insert(0, str(_BACKEND))

if __name__ == "__main__":
    # Prefer single-word product name on argv[0]
    sys.argv[0] = "gw"
    runpy.run_module("agent_repl", run_name="__main__", alter_sys=True)
