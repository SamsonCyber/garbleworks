"""Technique logs — a tiny, dependency-free SQLite store for what Garbleworks
fired, against what, and how it went. Structured + append-heavy is exactly what a
relational store is for; the `techniques` dim is synced from the field-guide
crosswalk so you can ask 'success rate by MITRE ATLAS class / by op / by target'
with one JOIN.

Design notes:
  - stdlib only (sqlite3 + json + hashlib + uuid + time). No server, no network.
  - WAL mode + busy_timeout so the MCP server, the optimizer, and the arena loop
    can write concurrently without corruption (the write rate is low).
  - payloads are stored as sha256 + a short preview + length by DEFAULT (lean DB,
    no hoarding of raw attack strings). Pass store_payload=True to keep the text.
  - a logged technique string is resolved to its canonical field-guide title so
    the JOIN to the crosswalk lands; the raw string is kept too.

CLI:  python logs.py init | stats [--by op] | query [--outcome success] | selftest
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("GARBLEWORKS_LOGDB", _BACKEND / "data" / "technique_logs.db"))

_FG_CANDIDATES = [
    os.getenv("GARBLEWORKS_FIELDGUIDE"),
    _BACKEND / "data" / "field-guide.json",
    _BACKEND.parent / "llm-injection-field-guide" / "field-guide.json",
    Path.home() / "code" / "llm-injection-field-guide" / "field-guide.json",
]

OUTCOMES = {
    "success", "refused", "tripwire", "error", "unknown",
    # arena paste-loop rich outcomes (bandit soft-reward via score field)
    "partial", "scorer_reject", "truncated",
    # multi-layer agent gates (Finbot-class): still reward bandit arms
    "gate_bypass", "gate_block", "tool_accept", "tool_deny", "model_comply",
}

# Outcomes that count as a "win" in success_rates aggregates.
SUCCESS_OUTCOMES = frozenset({
    "success", "gate_bypass", "tool_accept", "model_comply",
})

# Target types that keep a longer payload preview (unit / local campaigns).
_LONG_PREVIEW_TYPES = (
    "local_fn", "local", "python_callable", "callable",
    "finbot_agent", "unit", "gate",
)
_PREVIEW_SHORT = 60
_PREVIEW_LONG = 400
_PAYLOAD_FULL_MAX = 4000
_GROUP_COLS = {
    "technique": "a.technique", "op": "a.op", "target_type": "a.target_type",
    "outcome": "a.outcome", "run": "a.run_id",
    "atlas": "t.atlas", "owasp": "t.owasp", "cat": "t.cat", "cwe": "t.cwe",
}

# Soft rewards when operator logs rich outcomes without an explicit score.
OUTCOME_SCORE = {
    "success": 1.0,
    "gate_bypass": 1.0,
    "tool_accept": 0.9,
    "model_comply": 1.0,
    "partial": 0.4,
    "scorer_reject": 0.25,
    "truncated": 0.2,
    "refused": 0.0,
    "gate_block": 0.0,
    "tool_deny": 0.0,
    "tripwire": 0.0,
    "error": 0.0,
    "unknown": 0.0,
}


def arena_target_type(objective_class: str) -> str:
    """Class-conditioned bandit key stored as attempts.target_type."""
    cls = (objective_class or "generic").strip().lower() or "generic"
    return f"arena:{cls}"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id     TEXT PRIMARY KEY,
  objective  TEXT,
  kind       TEXT,
  target_ref TEXT,
  started_ts REAL,
  meta       TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id         TEXT,
  ts             REAL,
  technique      TEXT,        -- canonical field-guide title (for the JOIN), or the raw string
  technique_raw  TEXT,        -- exactly as supplied
  op             TEXT,        -- Garbleworks op name, if known
  target_ref     TEXT,
  target_type    TEXT,
  outcome        TEXT,        -- success | refused | tripwire | error | unknown
  score          REAL,        -- 0..1 fitness/compliance, if graded
  payload_sha256 TEXT,
  payload_preview TEXT,
  payload_len    INTEGER,
  params         TEXT,        -- json
  notes          TEXT
);
CREATE INDEX IF NOT EXISTS ix_attempts_technique ON attempts(technique);
CREATE INDEX IF NOT EXISTS ix_attempts_op        ON attempts(op);
CREATE INDEX IF NOT EXISTS ix_attempts_outcome   ON attempts(outcome);
CREATE INDEX IF NOT EXISTS ix_attempts_run       ON attempts(run_id);
CREATE TABLE IF NOT EXISTS techniques (
  title TEXT PRIMARY KEY,
  cat TEXT, owasp TEXT, atlas TEXT, nist TEXT, cwe TEXT,
  garak TEXT, promptfoo TEXT, pyrit TEXT, strongreject TEXT
);
"""


def _conn(path: Path | None = None) -> sqlite3.Connection:
    p = Path(path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p), timeout=5.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA busy_timeout=5000")
    c.execute("PRAGMA foreign_keys=ON")
    return c


@contextlib.contextmanager
def _db(path: Path | None = None):
    """Open, commit on success, and always CLOSE (sqlite3's `with conn` commits but
    does not close — leaving the file locked on Windows)."""
    c = _conn(path)
    try:
        yield c
        c.commit()
    finally:
        c.close()


def _load_field_guide() -> dict:
    for cand in _FG_CANDIDATES:
        if not cand:
            continue
        p = Path(cand)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
    return {}


# resolve a logged technique string -> canonical field-guide title (cached)
_TITLES: list[str] | None = None


def _titles() -> list[str]:
    global _TITLES
    if _TITLES is None:
        _TITLES = [t.get("title", "") for t in _load_field_guide().get("techniques", [])]
    return _TITLES


def canonical_title(s: str) -> str | None:
    if not s:
        return None
    q = s.lower().strip()
    titles = _titles()
    for t in titles:                    # exact first
        if t.lower() == q:
            return t
    for t in titles:                    # then substring
        if q in t.lower():
            return t
    return None


def init_db(path: Path | None = None, sync: bool = True) -> None:
    with _db(path) as c:
        c.executescript(_SCHEMA)
        if sync:
            _sync_techniques(c)


def _sync_techniques(c: sqlite3.Connection) -> int:
    fg = _load_field_guide()
    rows = 0
    for e in fg.get("techniques", []):
        cw = e.get("crosswalk") or {}
        tools = cw.get("tools") or {}
        c.execute(
            "INSERT INTO techniques(title,cat,owasp,atlas,nist,cwe,garak,promptfoo,pyrit,strongreject) "
            "VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(title) DO UPDATE SET "
            "cat=excluded.cat,owasp=excluded.owasp,atlas=excluded.atlas,nist=excluded.nist,cwe=excluded.cwe,"
            "garak=excluded.garak,promptfoo=excluded.promptfoo,pyrit=excluded.pyrit,strongreject=excluded.strongreject",
            (e.get("title"), e.get("cat"), cw.get("owasp"), cw.get("atlas"), cw.get("nist"), cw.get("cwe"),
             tools.get("garak"), tools.get("promptfoo"), tools.get("pyrit"), tools.get("strongreject")),
        )
        rows += 1
    return rows


def start_run(objective: str, kind: str = "manual", target_ref: str | None = None,
              meta: dict | None = None, path: Path | None = None) -> str:
    run_id = uuid.uuid4().hex[:16]
    with _db(path) as c:
        c.execute("INSERT INTO runs(run_id,objective,kind,target_ref,started_ts,meta) VALUES(?,?,?,?,?,?)",
                  (run_id, objective, kind, target_ref, time.time(), json.dumps(meta or {})))
    return run_id


def _wants_long_preview(target_type: str | None, store_payload: bool) -> bool:
    if store_payload:
        return True
    tt = (target_type or "").strip().lower()
    if not tt:
        return False
    return any(tt == t or tt.startswith(t + ":") or tt.startswith(t + "_") for t in _LONG_PREVIEW_TYPES)


def log_attempt(technique: str, outcome: str, *, op: str | None = None, run_id: str | None = None,
                target_ref: str | None = None, target_type: str | None = None, score: float | None = None,
                payload: str | None = None, params: dict | None = None, notes: str | None = None,
                store_payload: bool = False, path: Path | None = None,
                objective_class: str | None = None,
                layer: str | None = None,
                layers: dict | list | None = None) -> int:
    """Record one fire. Returns the attempt id. `technique` is resolved to its
    canonical field-guide title for the crosswalk JOIN (raw kept too).

    objective_class: when set, stores params.objective_class and defaults
    target_type to arena:<class> for class-conditioned bandit posteriors.

    layer / layers: multi-layer adjudication (gate_bypass, tool_accept, model_comply).
    Stored under params for query_attempts re-fire. Local target_types keep a
    longer payload_preview; store_payload also embeds payload_full when short enough.
    """
    outcome = (outcome or "unknown").lower().strip()
    if outcome not in OUTCOMES:
        outcome = "unknown"
    params = dict(params or {})
    if objective_class:
        params.setdefault("objective_class", objective_class)
        if not target_type:
            target_type = arena_target_type(objective_class)
    if layer:
        params.setdefault("layer", str(layer))
    if layers is not None:
        params.setdefault("layers", layers)
    if score is None:
        score = OUTCOME_SCORE.get(outcome)
    canon = canonical_title(technique) or technique
    sha = preview = None
    plen = None
    if payload is not None:
        sha = hashlib.sha256(payload.encode("utf-8", "replace")).hexdigest()
        plen = len(payload)
        long_prev = _wants_long_preview(target_type, store_payload)
        n = _PREVIEW_LONG if long_prev else _PREVIEW_SHORT
        preview = payload[:n] + ("…" if len(payload) > n else "")
        if store_payload and len(payload) <= _PAYLOAD_FULL_MAX:
            params.setdefault("payload_full", payload)
        elif long_prev and len(payload) <= _PAYLOAD_FULL_MAX and target_type:
            # Unit/local campaigns: keep full text for re-fire without requiring
            # the operator to remember store_payload=True every time.
            tt = target_type.strip().lower()
            if any(tt == t or tt.startswith(t) for t in _LONG_PREVIEW_TYPES):
                params.setdefault("payload_full", payload)
    with _db(path) as c:
        cur = c.execute(
            "INSERT INTO attempts(run_id,ts,technique,technique_raw,op,target_ref,target_type,outcome,score,"
            "payload_sha256,payload_preview,payload_len,params,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (run_id, time.time(), canon, technique, op, target_ref, target_type, outcome,
             score, sha, preview, plen, json.dumps(params), notes),
        )
        return int(cur.lastrowid)


def query_attempts(*, technique: str | None = None, op: str | None = None, outcome: str | None = None,
                   target_type: str | None = None, atlas: str | None = None, owasp: str | None = None,
                   run_id: str | None = None, limit: int = 100, path: Path | None = None) -> list[dict]:
    where, args = [], []
    if technique:
        where.append("a.technique LIKE ?"); args.append(f"%{technique}%")
    if op:
        where.append("a.op = ?"); args.append(op)
    if outcome:
        where.append("a.outcome = ?"); args.append(outcome.lower())
    if target_type:
        where.append("a.target_type = ?"); args.append(target_type)
    if run_id:
        where.append("a.run_id = ?"); args.append(run_id)
    if atlas:
        where.append("t.atlas LIKE ?"); args.append(f"%{atlas}%")
    if owasp:
        where.append("t.owasp = ?"); args.append(owasp)
    sql = (
        "SELECT a.id,a.ts,a.technique,a.op,a.target_type,a.outcome,a.score,"
        "a.payload_preview,a.payload_len,a.payload_sha256,a.params,a.notes,"
        "a.run_id,t.owasp,t.atlas,t.cwe "
        "FROM attempts a LEFT JOIN techniques t ON a.technique=t.title"
    )
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY a.ts DESC LIMIT ?"
    args.append(max(1, min(int(limit), 1000)))
    with _db(path) as c:
        rows = []
        for r in c.execute(sql, args).fetchall():
            d = dict(r)
            # Parse params JSON so operators can re-fire payload_full / layers.
            raw_p = d.get("params")
            if isinstance(raw_p, str) and raw_p:
                try:
                    d["params"] = json.loads(raw_p)
                except Exception:
                    pass
            rows.append(d)
        return rows


def success_rates(group_by: str = "technique", min_n: int = 1, limit: int = 50,
                  path: Path | None = None) -> list[dict]:
    """Aggregate: for each group, n / successes / success_rate / avg_score.
    group_by in: technique, op, atlas, owasp, cat, cwe, target_type, outcome, run."""
    col = _GROUP_COLS.get(group_by)
    if not col:
        return [{"error": f"group_by must be one of {sorted(_GROUP_COLS)}"}]
    # Win set: classic success + multi-layer gate/tool/model wins.
    win_list = ", ".join(f"'{o}'" for o in sorted(SUCCESS_OUTCOMES))
    sql = f"""
      SELECT {col} AS grp, COUNT(*) AS n,
             SUM(CASE WHEN a.outcome IN ({win_list}) THEN 1 ELSE 0 END) AS successes,
             ROUND(AVG(CASE WHEN a.outcome IN ({win_list}) THEN 1.0 ELSE 0.0 END), 3) AS success_rate,
             ROUND(AVG(a.score), 3) AS avg_score
      FROM attempts a LEFT JOIN techniques t ON a.technique=t.title
      GROUP BY {col} HAVING n >= ? ORDER BY success_rate DESC, n DESC LIMIT ?
    """
    with _db(path) as c:
        return [dict(r) for r in c.execute(sql, (max(1, int(min_n)), max(1, min(int(limit), 200)))).fetchall()]


def arm_reward_stats(*, group_by: str = "technique", target_type: str | None = None,
                     target_ref: str | None = None, path: Path | None = None,
                     objective_class: str | None = None) -> list[dict]:
    """Per-arm reward aggregates for the bandit (all-time attempt log).

    group_by: technique | op (other keys rejected — arms need a selectable label).
    objective_class: when set, restricts to target_type=arena:<class> (class-conditioned
    bandit). Explicit target_type wins if both are passed.
    Reward signal:
      - if score is present on a row, use score in [0,1] as soft success mass
      - else success→1, tripwire/refused/error/unknown→0
    Also returns tripwires count so callers can down-weight lock-prone arms.
    """
    if group_by not in ("technique", "op"):
        return [{"error": "group_by must be technique or op"}]
    col = "a.technique" if group_by == "technique" else "a.op"
    where, args = [f"{col} IS NOT NULL", f"TRIM({col}) != ''"], []
    if objective_class and not target_type:
        target_type = arena_target_type(objective_class)
    if target_type:
        where.append("a.target_type = ?")
        args.append(target_type)
    if target_ref:
        where.append("a.target_ref LIKE ?")
        args.append(f"%{target_ref}%")
    # Soft successes: prefer graded score when present; else multi-layer win set.
    # Tripwires counted separately (still contribute to n / failures).
    win_list = ", ".join(f"'{o}'" for o in sorted(SUCCESS_OUTCOMES))
    sql = f"""
      SELECT {col} AS grp,
             COUNT(*) AS n,
             SUM(CASE WHEN a.outcome IN ({win_list}) THEN 1 ELSE 0 END) AS binary_successes,
             SUM(CASE WHEN a.outcome='tripwire' THEN 1 ELSE 0 END) AS tripwires,
             SUM(CASE
                   WHEN a.score IS NOT NULL THEN
                     CASE WHEN a.score < 0 THEN 0.0
                          WHEN a.score > 1 THEN 1.0
                          ELSE a.score END
                   WHEN a.outcome IN ({win_list}) THEN 1.0
                   ELSE 0.0
                 END) AS successes,
             ROUND(AVG(a.score), 4) AS avg_score
      FROM attempts a
      WHERE {" AND ".join(where)}
      GROUP BY {col}
      ORDER BY successes DESC, n DESC
    """
    with _db(path) as c:
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    for r in rows:
        n = int(r.get("n") or 0)
        s = float(r.get("successes") or 0.0)
        r["successes"] = round(s, 4)
        r["n"] = n
        r["success_rate"] = round(s / n, 4) if n else None
        r["tripwires"] = int(r.get("tripwires") or 0)
        r["binary_successes"] = int(r.get("binary_successes") or 0)
    return rows


def counts(path: Path | None = None) -> dict:
    with _db(path) as c:
        a = c.execute("SELECT COUNT(*) n FROM attempts").fetchone()["n"]
        r = c.execute("SELECT COUNT(*) n FROM runs").fetchone()["n"]
        t = c.execute("SELECT COUNT(*) n FROM techniques").fetchone()["n"]
    return {"attempts": a, "runs": r, "techniques_synced": t, "db": str(DB_PATH)}


def _selftest() -> int:
    import tempfile
    p = Path(tempfile.gettempdir()) / f"gw_logtest_{uuid.uuid4().hex[:8]}.db"
    ok = True

    def check(name, cond):
        nonlocal ok
        print(("  ok " if cond else "  XX ") + name); ok = ok and cond

    init_db(p, sync=True)
    rid = start_run("reveal the system prompt", kind="test", path=p)
    check("start_run returns id", bool(rid))
    a1 = log_attempt("Policy Puppetry", "success", op="policy_puppetry", run_id=rid,
                     target_type="chat", score=0.9, payload="…", path=p)
    log_attempt("Policy Puppetry", "refused", op="policy_puppetry", run_id=rid, target_type="chat", score=0.1, path=p)
    log_attempt("Homoglyph substitution", "tripwire", op="homoglyph", run_id=rid, target_type="chat", path=p)
    log_attempt("bogus technique name", "success", path=p)   # no canonical match -> stored raw
    check("log_attempt returns id", isinstance(a1, int) and a1 > 0)
    rows = query_attempts(outcome="success", path=p)
    check("query by outcome", len(rows) == 2)
    rows = query_attempts(technique="Policy", path=p)
    check("query by technique", len(rows) == 2)
    # crosswalk JOIN worked: Policy Puppetry -> LLM01 present on the row
    pol = [r for r in query_attempts(technique="Policy Puppetry", path=p)]
    check("crosswalk JOIN populated owasp", any(r.get("owasp") == "LLM01" for r in pol))
    sr = success_rates("technique", path=p)
    pp = [r for r in sr if r["grp"] and "Policy Puppetry" in r["grp"]]  # logger canonicalizes to full title
    check("success_rate aggregates", bool(pp) and pp[0]["n"] == 2 and pp[0]["successes"] == 1 and pp[0]["success_rate"] == 0.5)
    sr_atlas = success_rates("atlas", path=p)
    check("group by atlas (via JOIN)", any(r["grp"] for r in sr_atlas if r["grp"]))
    c = counts(path=p)
    check("counts", c["attempts"] == 4 and c["runs"] == 1 and c["techniques_synced"] > 100)
    for f in (p, Path(str(p) + "-wal"), Path(str(p) + "-shm")):
        try:
            f.unlink(missing_ok=True)
        except OSError:
            pass
    print("  " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    cmd = args[0] if args else "init"
    if cmd == "selftest":
        raise SystemExit(_selftest())
    if cmd == "init":
        init_db()
        print("initialized", counts())
    elif cmd == "stats":
        by = args[args.index("--by") + 1] if "--by" in args else "technique"
        for r in success_rates(by):
            print(r)
    elif cmd == "query":
        oc = args[args.index("--outcome") + 1] if "--outcome" in args else None
        for r in query_attempts(outcome=oc, limit=20):
            print(r)
    else:
        print("usage: python logs.py init|stats [--by op]|query [--outcome success]|selftest")
