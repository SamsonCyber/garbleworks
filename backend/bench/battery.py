"""Load versioned batteries (JSON, stdlib-only)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_BATTERY_DIR = Path(__file__).resolve().parent / "battery"


@dataclass
class Objective:
    id: str
    objective: str
    budget_queries: int
    timeout_s: float
    seed: int
    class_: str  # easy | medium | hard
    meta: dict

    @property
    def class_name(self) -> str:
        return self.class_


def load_battery(name: str = "v1_canary") -> list[Objective]:
    path = _BATTERY_DIR / f"{name}.json"
    if not path.exists():
        # allow path without extension
        path = _BATTERY_DIR / name
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("objectives") if isinstance(data, dict) else data
    out: list[Objective] = []
    for row in items or []:
        out.append(Objective(
            id=str(row["id"]),
            objective=str(row["objective"]),
            budget_queries=int(row.get("budget_queries") or 20),
            timeout_s=float(row.get("timeout_s") or 120),
            seed=int(row.get("seed") or 0),
            class_=str(row.get("class") or "medium"),
            meta={k: v for k, v in row.items() if k not in
                  ("id", "objective", "budget_queries", "timeout_s", "seed", "class")},
        ))
    return out


def battery_meta(name: str = "v1_canary") -> dict[str, Any]:
    path = _BATTERY_DIR / f"{name}.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("_meta") or {} if isinstance(data, dict) else {}
