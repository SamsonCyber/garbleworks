"""CLI entry: python -m garbleworks  (alias for agent_loop multi-strategy --auto)."""
from __future__ import annotations

from agent_loop import main

if __name__ == "__main__":
    raise SystemExit(main())
