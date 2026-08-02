#!/usr/bin/env python3
"""Agent seat CLI — the external model (Grok) drives tools; TUI mirrors live.

Files (under tui/agent/):
  operator_state.json  — TUI → agent (brief, reply, history, request_id)
  agent_seat.json      — agent → TUI (payload, TOOL log, intel, busy)

Usage (from backend/ or anywhere):
  python agent_seat.py status              # print operator brief/history
  python agent_seat.py log "TOOL · foo"    # append activity line
  python agent_seat.py busy "framing…"     # set busy + status
  python agent_seat.py idle "ready"        # clear busy
  python agent_seat.py stage --payload-file p.txt --technique X --op Y ...
  python agent_seat.py stage --payload "..." --technique response_format_split
  python agent_seat.py clear               # wipe seat activity/payload

The agent does NOT fire at Gray Swan. You stage; the human pastes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_AGENT_DIR = _ROOT / "tui" / "agent"
_SEAT = _AGENT_DIR / "agent_seat.json"
_OPERATOR = _AGENT_DIR / "operator_state.json"
_TUI_PASTE = _ROOT / "tui" / "last_paste.txt"
_NEXT_PASTE = Path(__file__).resolve().parent / "sessions" / "next_paste.txt"


def _ensure() -> None:
    _AGENT_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, data: dict) -> None:
    _ensure()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_seat() -> dict:
    s = _read_json(_SEAT)
    if s.get("v") != 1:
        s = {
            "v": 1,
            "updated_at": 0,
            "seq": 0,
            "driver": "grok",
            "busy": False,
            "status": "seated",
            "payload": "",
            "technique": "",
            "kind": "",
            "activity": [],
        }
    if "activity" not in s or not isinstance(s["activity"], list):
        s["activity"] = []
    return s


def _push_hub(s: dict) -> dict | None:
    """Push seat to the TUI localhost hub (event-driven). File write is durable fallback."""
    import json as _json
    import urllib.error
    import urllib.request

    port = int(os.environ.get("GARBLEWORKS_SEAT_PORT") or "8765")
    host = os.environ.get("GARBLEWORKS_SEAT_HOST") or "127.0.0.1"
    url = f"http://{host}:{port}/seat"
    try:
        data = _json.dumps(s).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return _json.loads(resp.read().decode("utf-8") or "{}")
    except Exception:
        return None


def save_seat(s: dict) -> None:
    s["v"] = 1
    s["updated_at"] = time.time()
    s["seq"] = int(s.get("seq") or 0) + 1
    s.setdefault("driver", "grok")
    _write_json(_SEAT, s)
    # Prefer push so the TUI does not wait on fs.watch debounce
    _push_hub(s)


def load_operator() -> dict:
    return _read_json(_OPERATOR)


def cmd_status(_: argparse.Namespace) -> int:
    op = load_operator()
    seat = load_seat()
    print(json.dumps({
        "paths": {"seat": str(_SEAT), "operator": str(_OPERATOR)},
        "operator": {
            "request_id": op.get("request_id"),
            "phase": op.get("phase"),
            "history_len": len(op.get("history") or []),
            "last_outcome": op.get("last_outcome"),
            "last_request": op.get("last_request"),
            "brief_preview": (op.get("brief") or "")[:200],
            "objective": (op.get("objective") or "")[:160],
            "reply_preview": (op.get("reply") or "")[:200],
            "updated_at": op.get("updated_at"),
        },
        "seat": {
            "seq": seat.get("seq"),
            "busy": seat.get("busy"),
            "status": seat.get("status"),
            "technique": seat.get("technique"),
            "payload_len": len(seat.get("payload") or ""),
            "activity_n": len(seat.get("activity") or []),
            "driver": seat.get("driver"),
        },
    }, indent=2, ensure_ascii=False))
    return 0


def cmd_dump_operator(_: argparse.Namespace) -> int:
    """Full operator state (for the agent to reason over)."""
    print(json.dumps(load_operator(), indent=2, ensure_ascii=False))
    return 0


def _append_activity(seat: dict, message: str, *, level: str = "info",
                     strategy: str | None = None, payload: str | None = None) -> None:
    seat.setdefault("activity", [])
    seat["activity"].append({
        "ts": time.time(),
        "level": level,
        "message": message,
        "strategy": strategy,
        "payload": (payload or "")[:120] or None,
    })
    seat["activity"] = seat["activity"][-120:]


def cmd_log(args: argparse.Namespace) -> int:
    seat = load_seat()
    msg = args.message
    _append_activity(
        seat, msg,
        level=args.level or "info",
        strategy=args.strategy,
        payload=args.payload_preview,
    )
    if args.status:
        seat["status"] = args.status
    if args.busy is not None:
        seat["busy"] = bool(args.busy)
    save_seat(seat)
    print(json.dumps({"ok": True, "seq": seat["seq"], "message": msg}, ensure_ascii=False))
    return 0


def cmd_busy(args: argparse.Namespace) -> int:
    seat = load_seat()
    seat["busy"] = True
    seat["status"] = args.message or "working…"
    seat["driver"] = args.driver or seat.get("driver") or "grok"
    _append_activity(seat, f"AGENT · {seat['status']}", level="info")
    save_seat(seat)
    print(json.dumps({"ok": True, "seq": seat["seq"], "busy": True}, ensure_ascii=False))
    return 0


def cmd_idle(args: argparse.Namespace) -> int:
    seat = load_seat()
    seat["busy"] = False
    seat["status"] = args.message or "idle · waiting for paste outcome"
    seat["driver"] = args.driver or seat.get("driver") or "grok"
    _append_activity(seat, f"AGENT · {seat['status']}", level="info")
    save_seat(seat)
    print(json.dumps({"ok": True, "seq": seat["seq"], "busy": False}, ensure_ascii=False))
    return 0


def cmd_stage(args: argparse.Namespace) -> int:
    if args.payload_file:
        payload = Path(args.payload_file).read_text(encoding="utf-8")
    else:
        payload = args.payload or ""
    payload = payload.strip()
    if not payload:
        print("error: empty payload", file=sys.stderr)
        return 2

    seat = load_seat()
    seat["busy"] = False
    seat["driver"] = args.driver or seat.get("driver") or "grok"
    seat["payload"] = payload
    seat["technique"] = args.technique or seat.get("technique") or "agent"
    seat["kind"] = args.kind or "agent"
    seat["op"] = args.op
    seat["reset_first"] = bool(args.reset_first)
    seat["rationale"] = args.rationale or seat.get("rationale") or ""
    seat["expected_answer"] = args.expected_answer or seat.get("expected_answer")
    seat["objective_used"] = args.objective or seat.get("objective_used")
    seat["brief_title"] = args.brief_title or seat.get("brief_title")
    seat["defense_type"] = args.defense_type or seat.get("defense_type")
    seat["attempt"] = args.attempt or seat.get("attempt")
    seat["base_technique"] = args.base_technique or args.technique or seat.get("base_technique")
    seat["improvement"] = args.improvement or seat.get("improvement")
    seat["used_reply"] = bool(args.used_reply)
    seat["status"] = args.status or f"staged {seat['technique']} · paste in browser"
    if args.ladder:
        try:
            seat["ladder"] = json.loads(args.ladder)
        except Exception:
            pass

    _append_activity(
        seat,
        f"TOOL · stage {seat['technique']} · {len(payload)}c"
        + (" · RESET FIRST" if seat["reset_first"] else ""),
        level="info",
        strategy=seat["technique"],
        payload=payload[:80],
    )
    if seat.get("rationale"):
        _append_activity(
            seat,
            f"INTEL · {str(seat['rationale'])[:100]}",
            level="info",
            strategy=seat["technique"],
        )

    # Mirror paste files so Ctrl+V path still works offline
    body = payload + "\n"
    try:
        _TUI_PASTE.write_text(body, encoding="utf-8")
        _NEXT_PASTE.parent.mkdir(parents=True, exist_ok=True)
        _NEXT_PASTE.write_text(body, encoding="utf-8")
    except Exception as e:
        print(f"warn: paste file write: {e}", file=sys.stderr)

    save_seat(seat)
    print(json.dumps({
        "ok": True,
        "seq": seat["seq"],
        "technique": seat["technique"],
        "payload_len": len(payload),
        "paths": {"seat": str(_SEAT), "paste": str(_TUI_PASTE)},
    }, ensure_ascii=False))
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    seat = load_seat()
    if args.activity_only:
        seat["activity"] = []
    else:
        seat = {
            "v": 1,
            "updated_at": time.time(),
            "seq": int(seat.get("seq") or 0) + 1,
            "driver": args.driver or "grok",
            "busy": False,
            "status": "cleared · waiting for agent",
            "payload": "",
            "technique": "",
            "kind": "",
            "activity": [],
        }
    save_seat(seat)
    print(json.dumps({"ok": True, "seq": seat["seq"]}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Agent seat bus for TUI + external model")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="compact operator + seat summary")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("dump-operator", help="full operator_state.json")
    s.set_defaults(func=cmd_dump_operator)

    s = sub.add_parser("log", help="append TOOL/AGENT activity line")
    s.add_argument("message")
    s.add_argument("--level", default="info")
    s.add_argument("--strategy", default=None)
    s.add_argument("--payload-preview", default=None)
    s.add_argument("--status", default=None)
    s.add_argument("--busy", type=int, choices=(0, 1), default=None)
    s.set_defaults(func=cmd_log)

    s = sub.add_parser("busy", help="mark agent working")
    s.add_argument("message", nargs="?", default="working…")
    s.add_argument("--driver", default="grok")
    s.set_defaults(func=cmd_busy)

    s = sub.add_parser("idle", help="mark agent idle")
    s.add_argument("message", nargs="?", default="idle · waiting for paste outcome")
    s.add_argument("--driver", default="grok")
    s.set_defaults(func=cmd_idle)

    s = sub.add_parser("stage", help="stage payload into seat + paste files")
    s.add_argument("--payload", default="")
    s.add_argument("--payload-file", default="")
    s.add_argument("--technique", default="agent")
    s.add_argument("--kind", default="agent")
    s.add_argument("--op", default=None)
    s.add_argument("--reset-first", action="store_true")
    s.add_argument("--rationale", default="")
    s.add_argument("--expected-answer", default="")
    s.add_argument("--objective", default="")
    s.add_argument("--brief-title", default="")
    s.add_argument("--defense-type", default="")
    s.add_argument("--attempt", type=int, default=None)
    s.add_argument("--base-technique", default="")
    s.add_argument("--improvement", default="")
    s.add_argument("--used-reply", action="store_true")
    s.add_argument("--status", default="")
    s.add_argument("--ladder", default="")
    s.add_argument("--driver", default="grok")
    s.set_defaults(func=cmd_stage)

    s = sub.add_parser("clear", help="clear seat")
    s.add_argument("--activity-only", action="store_true")
    s.add_argument("--driver", default="grok")
    s.set_defaults(func=cmd_clear)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
