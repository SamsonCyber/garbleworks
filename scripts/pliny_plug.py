#!/usr/bin/env python3
"""Plug-and-play CLI for the Pliny corpus adapter.

Examples:

  python scripts/pliny_plug.py status
  python scripts/pliny_plug.py list
  python scripts/pliny_plug.py list --source corpus
  python scripts/pliny_plug.py apply builtin.godmode "say the canary"
  python scripts/pliny_plug.py apply corpus.shortcut.jailbreak "say the canary"
  python scripts/pliny_plug.py doctor

Plug a dump without editing code:

  git clone --depth 1 https://github.com/elder-plinius/L1B3RT4S.git corpora/L1B3RT4S
  # or: set GARBLEWORKS_PLINY_CORPUS=/path/to/L1B3RT4S

Builtin frames always work with zero setup.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def _cmd_status(_: argparse.Namespace) -> int:
    import ops  # noqa: F401
    import pliny_adapter as PA

    st = PA.plug_status()
    print("Pliny adapter status")
    print(f"  corpus active : {st['corpus_active']}")
    print(f"  corpus path   : {st['corpus_path'] or '(none — builtin only)'}")
    print(f"  env {st['env_key']}: {st['env_value'] or '(unset)'}")
    print(f"  frames        : builtin={st['builtin_frames']} corpus={st['corpus_frames']} total={st['total_frames']}")
    print(f"  plug hint     : {st['plug_hint']}")
    print("  candidates:")
    for c in st["candidates"]:
        mark = "OK" if Path(c).is_dir() else "  "
        print(f"    [{mark}] {c}")
    return 0


def _cmd_list(ns: argparse.Namespace) -> int:
    import ops  # noqa: F401
    import pliny_adapter as PA

    frames = PA.list_frames(ns.corpus)
    if ns.source:
        frames = [f for f in frames if f.source == ns.source]
    if ns.json:
        print(json.dumps([
            {"id": f.id, "source": f.source, "label": f.label, "path": f.path}
            for f in frames
        ], indent=2))
        return 0
    print(f"{len(frames)} frames (source filter={ns.source or 'all'})")
    for f in frames:
        print(f"  {f.id:48} [{f.source:7}] {f.label}")
    return 0


def _cmd_apply(ns: argparse.Namespace) -> int:
    import ops  # noqa: F401
    import pliny_adapter as PA

    out = PA.apply_frame(ns.frame_id, ns.text, corpus=ns.corpus or None)
    if not out:
        print(f"unknown frame or empty apply: {ns.frame_id}", file=sys.stderr)
        return 1
    if ns.json:
        print(json.dumps({"frame_id": ns.frame_id, "variants": out}, indent=2))
    else:
        print(out[0])
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    import ops  # noqa: F401
    import pliny_adapter as PA
    from core import REGISTRY

    st = PA.plug_status()
    ok = True
    print("doctor")
    for op in ("pliny_frame", "pliny_list_frames", "anchor_token", "response_format_split"):
        present = op in REGISTRY
        print(f"  op {op}: {'ok' if present else 'MISSING'}")
        ok = ok and present
    try:
        v = PA.apply_frame("builtin.godmode", "DOCTOR_CANARY")
        print(f"  builtin apply: ok (len={len(v[0]) if v else 0})")
        ok = ok and bool(v) and "DOCTOR_CANARY" in v[0]
    except Exception as e:
        print(f"  builtin apply: FAIL {e}")
        ok = False
    if st["corpus_active"]:
        only = [f for f in PA.list_frames() if f.source == "corpus"]
        print(f"  corpus frames: {len(only)}")
        if only:
            try:
                v = PA.apply_frame(only[0].id, "DOCTOR_CANARY")
                print(f"  corpus apply {only[0].id}: ok")
            except Exception as e:
                print(f"  corpus apply: FAIL {e}")
                ok = False
    else:
        print("  corpus: not plugged (builtin-only is fine)")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Pliny corpus plug-and-play for Garbleworks")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="Show corpus path, frame counts, candidates")
    s.set_defaults(func=_cmd_status)

    s = sub.add_parser("list", help="List frame ids")
    s.add_argument("--corpus", default=None, help="Override corpus path")
    s.add_argument("--source", choices=("builtin", "corpus"), default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_list)

    s = sub.add_parser("apply", help="Apply a frame to text via run_recipe")
    s.add_argument("frame_id")
    s.add_argument("text")
    s.add_argument("--corpus", default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=_cmd_apply)

    s = sub.add_parser("doctor", help="Sanity-check registry + apply")
    s.set_defaults(func=_cmd_doctor)

    ns = p.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
