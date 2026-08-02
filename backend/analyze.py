"""Read-only analytics over technique_logs.db.

Safe to run WHILE campaigns are writing: it opens a `mode=ro` connection, so with
WAL it reads the last committed snapshot and never locks the writers. Surfaces
what logs.py's CLI doesn't:

  - success by LEAK CHANNEL (parsed from params JSON) — literal / normalized / hex
    / base64 / …: which exfil form is actually crossing the boundary.
  - queries-to-success for PAIR runs (kind='pair'): converged @ q, or held.
  - the boundary-map digest: the `notes` on refused/tripwire fires, which is where
    the "what tripped / what held" intelligence lives.

CLI:
  python analyze.py                 overview + channels + top ops + pair scoreboard
  python analyze.py run <run_id>    full timeline for one run
  python analyze.py boundary [run]  what tripped / what held, from the notes
"""
from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter

import logs  # DB_PATH resolution only — no writes


def _ro() -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{logs.DB_PATH}?mode=ro", uri=True, timeout=5.0)
    c.row_factory = sqlite3.Row
    return c


def _q(sql: str, args: tuple = ()) -> list[dict]:
    c = _ro()
    try:
        return [dict(r) for r in c.execute(sql, args).fetchall()]
    finally:
        c.close()


def _params(row: dict) -> dict:
    try:
        return json.loads(row.get("params") or "{}")
    except Exception:
        return {}


def _age(ts: float | None) -> str:
    if not ts:
        return "?"
    d = time.time() - ts
    return f"{d/3600:.1f}h ago" if d > 3600 else f"{int(d/60)}m ago"


def overview() -> None:
    tot = _q("SELECT COUNT(*) n, SUM(outcome='success') s FROM attempts")[0]
    print(f"DB: {logs.DB_PATH}")
    print(f"attempts: {tot['n']}   successes: {tot['s'] or 0}\n")
    print("RUNS")
    runs = _q("SELECT run_id,kind,target_ref,objective,started_ts FROM runs ORDER BY started_ts DESC")
    for r in runs:
        agg = _q("SELECT COUNT(*) n, SUM(outcome='success') s FROM attempts WHERE run_id=?", (r["run_id"],))[0]
        print(f"  {r['run_id'][:8]}  {r['kind']:6s} {(r['target_ref'] or '-'):22s} "
              f"{agg['n']:3d} fires / {agg['s'] or 0} success   {_age(r['started_ts'])}")
        print(f"           {(r['objective'] or '')[:96]}")


def by(col: str, label: str, top: int = 12) -> None:
    rows = _q(f"SELECT {col} g, COUNT(*) n, SUM(outcome='success') s, ROUND(AVG(score),3) avg "
              f"FROM attempts WHERE {col} IS NOT NULL GROUP BY {col} "
              f"ORDER BY (1.0*SUM(outcome='success')/COUNT(*)) DESC, n DESC LIMIT ?", (top,))
    if not rows:
        return
    print(f"\n{label}")
    print(f"  {'':32s}  n   succ  rate   avg_score")
    for r in rows:
        rate = (r["s"] or 0) / r["n"] if r["n"] else 0
        print(f"  {str(r['g'])[:32]:32s} {r['n']:3d}  {r['s'] or 0:3d}  {rate:5.0%}  {r['avg'] if r['avg'] is not None else '-'}")


def channels() -> None:
    succ = _q("SELECT params FROM attempts WHERE outcome='success'")
    ch = Counter()
    for r in succ:
        ch[_params(r).get("channel") or "(unlabelled)"] += 1
    if not succ:
        print("\nLEAK CHANNELS (successes)\n  (no successes logged yet)")
        return
    print("\nLEAK CHANNELS (how the canary crossed, over successes)")
    for name, n in ch.most_common():
        print(f"  {name:16s} {n}")


def pair_scoreboard() -> None:
    runs = _q("SELECT run_id,objective,started_ts FROM runs WHERE kind='pair' ORDER BY started_ts DESC")
    if not runs:
        print("\nPAIR SCOREBOARD\n  (no kind='pair' runs yet — automated queries-to-success lands here)")
        return
    print("\nPAIR SCOREBOARD  (queries-to-success)")
    for r in runs:
        att = _q("SELECT outcome,score,notes,params FROM attempts WHERE run_id=? ORDER BY id", (r["run_id"],))
        conv = next((a for a in att if a["outcome"] == "success" and "CONVERGED" in (a["notes"] or "")), None)
        flick = sum(1 for a in att if a["outcome"] == "success" and a is not conv)
        if conv:
            q = _params(conv).get("q", "?")
            print(f"  {r['run_id'][:8]}  CONVERGED @ q{q}  ({_params(conv).get('confirm','?')} confirm, "
                  f"channel {_params(conv).get('channel','?')})   [{len(att)} fires]")
        else:
            print(f"  {r['run_id'][:8]}  HELD — no confirmed leak in {len(att)} fires "
                  f"({flick} unconfirmed flicker{'s' if flick != 1 else ''})")


def run_detail(run_id: str) -> None:
    runs = _q("SELECT * FROM runs WHERE run_id LIKE ?", (run_id + "%",))
    if not runs:
        print("no run matching", run_id)
        return
    r = runs[0]
    print(f"RUN {r['run_id']}  [{r['kind']}]  target={r['target_ref']}")
    print(f"  {r['objective']}\n")
    att = _q("SELECT id,ts,technique,op,outcome,score,payload_preview,params,notes "
             "FROM attempts WHERE run_id=? ORDER BY id", (r["run_id"],))
    for a in att:
        p = _params(a)
        tag = {"success": "LEAK ", "refused": "  -  ", "tripwire": "TRIP ", "error": "ERR  "}.get(a["outcome"], "  ?  ")
        ch = f" [{p['channel']}]" if p.get("channel") else ""
        print(f"  #{a['id']:<3d} {tag} score={a['score']}{ch}  {(a['op'] or a['technique'] or '')[:34]}")
        if a["notes"]:
            print(f"        {a['notes'][:150].replace(chr(10),' / ')}")


def boundary(run_id: str | None = None) -> None:
    where = "outcome IN ('refused','tripwire') AND notes IS NOT NULL AND notes!=''"
    args: tuple = ()
    if run_id:
        where += " AND run_id LIKE ?"; args = (run_id + "%",)
    rows = _q(f"SELECT run_id,outcome,op,technique,notes FROM attempts WHERE {where} ORDER BY id", args)
    print("BOUNDARY MAP  (what tripped / what held — from refused & tripwire notes)")
    if not rows:
        print("  (no annotated refusals yet)")
        return
    for a in rows:
        mark = "TRIP" if a["outcome"] == "tripwire" else "held"
        print(f"  [{mark}] {a['run_id'][:8]} {(a['op'] or a['technique'] or '')[:26]:26s} {a['notes'][:160]}")


def main(argv: list[str]) -> None:
    if argv and argv[0] == "run" and len(argv) > 1:
        run_detail(argv[1]); return
    if argv and argv[0] == "boundary":
        boundary(argv[1] if len(argv) > 1 else None); return
    overview()
    channels()
    by("op", "BY OP")
    by("technique", "BY TECHNIQUE")
    by("target_type", "BY TARGET TYPE")
    pair_scoreboard()


if __name__ == "__main__":
    main(sys.argv[1:])
