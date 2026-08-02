"""Wilson LCB helpers and lightweight hypothesis-store utilities.

Public module used by rainbow, surface, validate paths, and benchmark_harness.
Stats conventions match ``bench.metrics`` (z=1.28, one-sided ~90% Wilson).
"""
from __future__ import annotations

import math
from typing import Any

# z ≈ Φ⁻¹(0.90): one-sided ~90% Wilson (not two-sided 95%)
WILSON_Z = 1.28


def wilson_lcb(s: int, n: int, z: float = WILSON_Z) -> float:
    """Wilson score lower confidence bound for s successes in n trials."""
    if n <= 0:
        return 0.0
    p = s / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (center - margin) / denom)


def wilson_ucb(s: int, n: int, z: float = WILSON_Z) -> float:
    """Wilson score upper confidence bound for s successes in n trials."""
    if n <= 0:
        return 1.0
    p = s / n
    denom = 1 + z * z / n
    center = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return min(1.0, (center + margin) / denom)


def wilson_interval(s: int, n: int, z: float = WILSON_Z) -> dict[str, Any]:
    """Point estimate plus Wilson LCB/UCB for reporting."""
    p = (s / n) if n > 0 else 0.0
    return {
        "successes": s,
        "n": n,
        "p": p,
        "lcb": wilson_lcb(s, n, z=z),
        "ucb": wilson_ucb(s, n, z=z),
        "z": z,
        "coverage": "one-sided ~90% (z=1.28)" if abs(z - WILSON_Z) < 1e-9 else f"z={z}",
    }
