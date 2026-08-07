"""Long-lived engagement host for external agent shells (pi, Grok, etc.).

JSONL over stdin / stdout. One process = one EngagementContext (target, secret,
fire budget, last payload). External brains call tools without re-spawning
local canary servers each time.

Protocol (stdin, one JSON object per line):
  {"op":"setup","target":"local","secret":"","max_fires":48,"objective":"..."}
  {"op":"call","tool":"fire_target","args":{"payload":"..."}}
  {"op":"status"}
  {"op":"graph_push","series":"latency_ms","y":12.5,"x":null}
  {"op":"graph_clear"}
  {"op":"reset"}
  {"op":"quit"}

Responses (stdout, one JSON object per line):
  {"ok":true,"op":"setup",...}
  {"ok":true,"op":"call","tool":"...","result":{...},"is_error":false}
  {"ok":true,"op":"status","stats":{...},"series":{...}}
  {"ok":false,"error":"..."}

Never prints secrets. reply_preview is redacted by tool handlers.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agent_repl.tools import (
    EngagementContext,
    build_default_registry,
)
from agent_repl.types import preview


def _out(row: dict[str, Any]) -> None:
    print(json.dumps(row, ensure_ascii=False, default=str), flush=True)


class EngagementHost:
    """Stateful tool surface for chat agents."""

    def __init__(self) -> None:
        self.registry = build_default_registry()
        self.ctx = EngagementContext(objective="")
        self._server: Any = None
        self._target_key = ""
        # Live graph series: name -> list of {x, y}
        self.series: dict[str, list[dict[str, float]]] = {
            "latency_ms": [],
            "hit_rate": [],
            "fires": [],
        }
        self._fire_hits = 0
        self._fire_total = 0
        self.started_at = time.time()
        self.setup_done = False

    def shutdown(self) -> None:
        if self._server is None:
            return
        try:
            self._server.shutdown()
        except Exception:
            pass
        try:
            self._server.server_close()
        except Exception:
            pass
        self._server = None

    def setup(
        self,
        *,
        target: str = "local",
        secret: str = "",
        max_fires: int = 48,
        objective: str = "",
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        from agent_loop import make_local_canary_target, target_from_url

        target_s = (target or "local").strip()
        secret = (secret or "").strip()
        key = f"{target_s}|{secret}|{max_fires}"

        if self._target_key != key:
            self.shutdown()
            if target_s.lower() == "local":
                server, _port, tgt, sec = make_local_canary_target(
                    secret=secret or None
                )
                self._server = server
                self.ctx.target = tgt
                self.ctx.secret = sec
            else:
                # URL or JSON path
                p = Path(target_s)
                if p.is_file():
                    data = json.loads(p.read_text(encoding="utf-8"))
                    self.ctx.target = data if isinstance(data, dict) else {"url": target_s}
                    self.ctx.secret = secret or str(data.get("secret") or "")
                else:
                    self.ctx.target = target_from_url(target_s)
                    self.ctx.secret = secret
            self._target_key = key

        self.ctx.max_fires = max(1, int(max_fires))
        self.ctx.timeout = float(timeout)
        if objective:
            self.ctx.objective = objective.strip()
        self.setup_done = True

        return {
            "ok": True,
            "op": "setup",
            "target": target_s,
            "has_secret": bool(self.ctx.secret),
            "max_fires": self.ctx.max_fires,
            "objective": preview(self.ctx.objective, 120),
            "tools": self.registry.names(),
        }

    def call(self, tool: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.setup_done:
            # Auto-setup local for convenience
            self.setup(target="local")
        name = (tool or "").strip()
        if not name:
            return {"ok": False, "op": "call", "error": "tool name required"}
        args = args if isinstance(args, dict) else {}
        t0 = time.perf_counter()
        result_text, is_err = self.registry.dispatch(name, args, self.ctx)
        ms = (time.perf_counter() - t0) * 1000.0
        try:
            result = json.loads(result_text)
        except Exception:
            result = {"raw": result_text}

        # Live graph samples from fire / validate
        if name == "fire_target" and isinstance(result, dict):
            self._fire_total += 1
            lat = result.get("ms")
            if lat is None:
                lat = ms
            self._push("latency_ms", float(lat))
            if result.get("leaked") is True:
                self._fire_hits += 1
            rate = (
                100.0 * self._fire_hits / self._fire_total
                if self._fire_total
                else 0.0
            )
            self._push("hit_rate", rate)
            self._push("fires", float(self._fire_total))
        elif name == "validate_refire" and isinstance(result, dict):
            asr = result.get("asr")
            if asr is not None:
                try:
                    self._push("hit_rate", float(asr) * 100.0)
                except (TypeError, ValueError):
                    pass

        return {
            "ok": not is_err,
            "op": "call",
            "tool": name,
            "is_error": is_err,
            "ms": round(ms, 1),
            "result": result,
        }

    def _push(self, series: str, y: float, x: float | None = None) -> None:
        if series not in self.series:
            self.series[series] = []
        pts = self.series[series]
        xi = float(x) if x is not None else float(len(pts))
        pts.append({"x": xi, "y": float(y)})
        # Cap memory
        if len(pts) > 256:
            self.series[series] = pts[-256:]

    def graph_push(
        self, series: str, y: float, x: float | None = None
    ) -> dict[str, Any]:
        name = (series or "series").strip() or "series"
        self._push(name, float(y), x)
        return {
            "ok": True,
            "op": "graph_push",
            "series": name,
            "n": len(self.series.get(name, [])),
        }

    def graph_clear(self, series: str | None = None) -> dict[str, Any]:
        if series:
            self.series[series] = []
        else:
            for k in list(self.series.keys()):
                self.series[k] = []
            self._fire_hits = 0
            self._fire_total = 0
        return {"ok": True, "op": "graph_clear"}

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "op": "status",
            "setup_done": self.setup_done,
            "objective": preview(self.ctx.objective, 160),
            "fire_count": self.ctx.fire_count,
            "max_fires": self.ctx.max_fires,
            "remaining_fires": self.ctx.remaining_fires(),
            "last_leak": bool(self.ctx.last_leak),
            "last_channel": self.ctx.last_channel,
            "findings": len(self.ctx.findings),
            "has_secret": bool(self.ctx.secret),
            "last_payload_preview": preview(self.ctx.last_payload, 100),
            "stats": {
                "fires": self._fire_total,
                "hits": self._fire_hits,
                "hit_rate": (
                    round(100.0 * self._fire_hits / self._fire_total, 1)
                    if self._fire_total
                    else 0.0
                ),
                "uptime_s": round(time.time() - self.started_at, 1),
            },
            "series": {
                k: v[-64:] for k, v in self.series.items() if v
            },
            "tools": self.registry.names(),
        }

    def reset(self) -> dict[str, Any]:
        obj = self.ctx.objective
        max_f = self.ctx.max_fires
        secret = self.ctx.secret
        target = self.ctx.target
        self.ctx = EngagementContext(
            objective=obj,
            target=target,
            secret=secret,
            max_fires=max_f,
        )
        self.series = {"latency_ms": [], "hit_rate": [], "fires": []}
        self._fire_hits = 0
        self._fire_total = 0
        return {"ok": True, "op": "reset"}

    def handle(self, msg: dict[str, Any]) -> dict[str, Any]:
        op = str(msg.get("op") or "").strip().lower()
        try:
            if op == "setup":
                return self.setup(
                    target=str(msg.get("target") or "local"),
                    secret=str(msg.get("secret") or ""),
                    max_fires=int(msg.get("max_fires") or 48),
                    objective=str(msg.get("objective") or ""),
                    timeout=float(msg.get("timeout") or 30.0),
                )
            if op == "call":
                return self.call(
                    str(msg.get("tool") or msg.get("name") or ""),
                    msg.get("args") if isinstance(msg.get("args"), dict) else {},
                )
            if op == "status":
                return self.status()
            if op == "graph_push":
                return self.graph_push(
                    str(msg.get("series") or "series"),
                    float(msg.get("y") if msg.get("y") is not None else 0),
                    float(msg["x"]) if msg.get("x") is not None else None,
                )
            if op == "graph_clear":
                return self.graph_clear(
                    str(msg["series"]) if msg.get("series") else None
                )
            if op == "reset":
                return self.reset()
            if op == "ping":
                return {"ok": True, "op": "ping", "ts": time.time()}
            if op == "quit":
                return {"ok": True, "op": "quit"}
            return {"ok": False, "error": f"unknown op: {op}"}
        except Exception as e:
            return {
                "ok": False,
                "op": op or "?",
                "error": f"{type(e).__name__}: {e}"[:400],
                "trace": traceback.format_exc()[-600:],
            }


def run_host() -> int:
    host = EngagementHost()
    _out(
        {
            "ok": True,
            "op": "ready",
            "tools": host.registry.names(),
            "protocol": "jsonl",
        }
    )
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                _out({"ok": False, "error": f"bad json: {e}"})
                continue
            if not isinstance(msg, dict):
                _out({"ok": False, "error": "message must be object"})
                continue
            row = host.handle(msg)
            _out(row)
            if row.get("op") == "quit":
                break
    finally:
        host.shutdown()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Garbleworks engagement host (JSONL)")
    p.add_argument(
        "--once",
        metavar="JSON",
        help="handle one message JSON and exit (for tests)",
    )
    args = p.parse_args(argv)
    if args.once:
        host = EngagementHost()
        try:
            msg = json.loads(args.once)
            if str(msg.get("op") or "") != "setup":
                # ensure target for call-only smoke
                if str(msg.get("op") or "") == "call":
                    host.setup(target="local")
            row = host.handle(msg if isinstance(msg, dict) else {})
            _out(row)
            return 0 if row.get("ok") else 1
        finally:
            host.shutdown()
    return run_host()


if __name__ == "__main__":
    raise SystemExit(main())
