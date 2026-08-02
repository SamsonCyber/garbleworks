"""Cross-tool A/B bench: Garbleworks vs Wallbreaker on a local canary.

No OpenAI / cloud dependency. Shared target speaks Chat Completions wire format
on 127.0.0.1 only. Leaderboard uses canary.is_leak, not tool-internal judges.
"""
from __future__ import annotations

__all__ = ["SECRET", "DEFAULT_SECRET"]

DEFAULT_SECRET = "CANARY_bench_a1b2c3"
SECRET = DEFAULT_SECRET
