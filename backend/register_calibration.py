"""Live refusal calibration driver (EVOLVE_MATH §3.8).

This module is the concrete implementation of the missing piece:
we now actually fit p_refuse(L) on real observations and use it to
adjust fitness, selection, and reporting.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import register
from register import RefusalCalibrator, text_loadedness


@dataclass
class CalibratedFitness:
    raw_f: float
    L: float
    p_refuse: float
    adj_f: float          # raw_f * pass_prob
    effective_mult: float


class LiveCalibrator:
    """Per-target live calibrator that the optimizer can use."""

    def __init__(self):
        self.cal = RefusalCalibrator()
        self.obs_by_target: Dict[str, List[Tuple[float, bool]]] = {}

    def observe(self, target_host: str, L: float, refused: bool) -> None:
        self.cal.update(L, refused)
        self.obs_by_target.setdefault(target_host, []).append((L, refused))

    def adjusted_fitness(self, raw_f: float, L: float) -> CalibratedFitness:
        pr = self.cal.p_refuse(L)
        adj = raw_f * (1.0 - pr)
        return CalibratedFitness(
            raw_f=raw_f,
            L=L,
            p_refuse=pr,
            adj_f=adj,
            effective_mult=(1.0 - pr),
        )

    def summary(self, target_host: str | None = None) -> Dict:
        base = self.cal.summary()
        base["targets_seen"] = len(self.obs_by_target)
        if target_host and target_host in self.obs_by_target:
            base["obs_for_target"] = len(self.obs_by_target[target_host])
        return base


# Convenience: global singleton for simple single-target runs
_global_cal = LiveCalibrator()


def get_global_calibrator() -> LiveCalibrator:
    return _global_cal
