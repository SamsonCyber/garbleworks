"""Runner protocol for bench tools."""
from __future__ import annotations

from typing import Protocol

from bench.battery import Objective
from bench.metrics import RunResult


class Runner(Protocol):
    tool: str
    mode: str

    def run(self, obj: Objective, *, base_url: str, secret: str) -> RunResult:
        ...
