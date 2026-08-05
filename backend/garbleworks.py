"""Primary package-style entry: python -m garbleworks → harness_cli.

Advanced multi-strategy auto remains: python harness_cli.py auto …
or python agent_loop.py (non-primary).
"""
from __future__ import annotations

from harness_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
