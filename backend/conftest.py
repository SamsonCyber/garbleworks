"""Pytest collection hooks for the Garbleworks backend suite."""
from __future__ import annotations

# Live integration script — requires a running uvicorn + echo target.
# Keep it out of automated collection so `pytest` works offline.
collect_ignore = ["test_strategy_fire.py"]
