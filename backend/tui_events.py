"""Structured events for the OpenTUI operator surface.

When GARBLEWORKS_TUI=1 (or always if force=True), emit one machine line:

  GW|{"v":1,"kind":"...","ts":...,...}

The TUI parses these into the work plan + activity window. Humans running
plain CLI without the env var see nothing extra.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any


def tui_enabled() -> bool:
    return os.environ.get("GARBLEWORKS_TUI", "").strip() not in ("", "0", "false", "False")


def emit(kind: str, **payload: Any) -> None:
    if not tui_enabled():
        return
    row = {
        "v": 1,
        "kind": kind,
        "ts": round(time.time(), 3),
        **payload,
    }
    try:
        line = "GW|" + json.dumps(row, ensure_ascii=False, default=str)
        print(line, flush=True, file=sys.stdout)
    except Exception:
        pass


def emit_plan(steps: list[str], *, job: str = "auto", budget: int | None = None) -> None:
    emit(
        "plan",
        job=job,
        steps=[{"id": s, "label": s, "status": "pending"} for s in steps],
        budget=budget,
        total=len(steps),
    )


def emit_step(step_id: str, status: str, **extra: Any) -> None:
    """status: pending | active | done | skip | fail | win"""
    emit("step", step_id=step_id, status=status, **extra)


def emit_activity(message: str, *, level: str = "info", **extra: Any) -> None:
    emit("activity", message=message, level=level, **extra)


def emit_summary(
    message: str,
    *,
    level: str = "info",
    payload_preview: str = "",
    reply_preview: str = "",
    **extra: Any,
) -> None:
    """End-of-step recap (does not count as a FIRE for telemetry)."""
    emit(
        "activity",
        message=message,
        level=level,
        payload_preview=(payload_preview or "")[:160],
        reply_preview=(reply_preview or "")[:160],
        **extra,
    )


def emit_progress(
    *,
    current: int,
    total: int,
    label: str = "",
    detail: str = "",
) -> None:
    emit(
        "progress",
        current=current,
        total=total,
        ratio=round(current / total, 4) if total else 0.0,
        label=label,
        detail=detail,
    )


def emit_fire(
    *,
    strategy: str,
    payload_preview: str = "",
    reply_preview: str = "",
    leaked: bool = False,
    channel: str | None = None,
    q: int | None = None,
) -> None:
    emit(
        "fire",
        strategy=strategy,
        payload_preview=(payload_preview or "")[:160],
        reply_preview=(reply_preview or "")[:160],
        leaked=leaked,
        channel=channel,
        q=q,
    )


def emit_result(**payload: Any) -> None:
    emit("result", **payload)
