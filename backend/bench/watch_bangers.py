"""Watch HB checkpoint for interesting COMPLIED (non-copyright meat).

Prints one line per new banger to stdout (for monitor). Exits when n_done==300
or when checkpoint goes stale for too long (optional).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

CKPT = Path(__file__).resolve().parent / "results" / "harmbench-minimax-full-v3-checkpoint.json"
FINAL = Path(__file__).resolve().parent / "results" / "harmbench-minimax-full-v3.json"
# Categories that are "interesting" if COMPLIED (not copyright fluff)
MEAT = {
    "chemical_biological",
    "illegal",
    "harmful",
    "harassment_bullying",
    "misinformation_disinformation",
    "cybercrime_intrusion",
}
# cyber is meat but user wants bangers — still report cyber; flag hard vs soft
HARD = {
    "chemical_biological",
    "illegal",
    "harmful",
    "harassment_bullying",
}


def load_results() -> tuple[dict, Path]:
    for p in (FINAL, CKPT):
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8")), p
            except Exception:
                continue
    return {}, CKPT


def main() -> int:
    seen: set[str] = set()
    last_done = -1
    stale = 0
    print("WATCH_START ckpt=" + str(CKPT), flush=True)
    while True:
        d, src = load_results()
        res = d.get("results") or list((d.get("results_by_id") or {}).values())
        n_done = d.get("n_done") or len(res)
        if n_done != last_done:
            last_done = n_done
            stale = 0
            print(f"PROGRESS n_done={n_done}/300 src={src.name}", flush=True)
        else:
            stale += 1

        for r in res:
            bid = r.get("behavior_id") or ""
            w = r.get("winner") or {}
            if w.get("label") != "COMPLIED":
                continue
            if bid in seen:
                continue
            seen.add(bid)
            cat = r.get("category") or "?"
            tech = w.get("technique") or "?"
            goal = (r.get("behavior") or "")[:120]
            if cat == "copyright":
                print(
                    f"COPYRIGHT_WIN id={bid} tech={tech} goal={goal}",
                    flush=True,
                )
                continue
            tag = "HARD_BANGER" if cat in HARD else "MEAT_WIN"
            # trail reply preview
            reply = ""
            for t in r.get("trail") or []:
                if t.get("label") == "COMPLIED":
                    reply = (t.get("reply_preview") or t.get("reply_full") or "")[:200]
                    break
            print(
                f"{tag} id={bid} cat={cat} tech={tech} goal={goal} reply={reply!r}",
                flush=True,
            )

        if n_done >= 300 and (FINAL.is_file() or n_done >= 300):
            # wait for final file if only ckpt
            if FINAL.is_file() or n_done >= 300:
                c = sum(
                    1
                    for r in res
                    if (r.get("winner") or {}).get("label") == "COMPLIED"
                )
                nc = sum(
                    1
                    for r in res
                    if (r.get("winner") or {}).get("label") == "COMPLIED"
                    and r.get("category") != "copyright"
                )
                print(
                    f"WATCH_DONE n_done={n_done} n_complied={c} noncopy={nc}",
                    flush=True,
                )
                return 0
        # ~2h no progress → warn and keep going a bit
        if stale > 720:  # 720 * 10s = 2h
            print("WATCH_STALE no progress 2h", flush=True)
            return 2
        time.sleep(10)


if __name__ == "__main__":
    raise SystemExit(main())
