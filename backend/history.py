"""
SQLite-backed persistence for fire results.

Every variant fired at a target is saved with: which ops produced it, the
target URL, the response status/latency/snippet, and whether it hit.

The analytics layer aggregates over this table: per-op hit rates, per-target
hit rates, per-recipe hit rates, time-series of mutation effectiveness.

Schema is deliberately simple. We do not normalize the recipe into its own
table because the recipe structure is the unit of analysis the user cares
about ("did THIS recipe hit?"), and JSON-in-a-column keeps the write path
fast. If aggregate queries get slow on large datasets, denormalize then.

This module is content-agnostic. It stores whatever the fire endpoint
returns. It does not parse or interpret the payload content.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS fire_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   REAL NOT NULL,
    finished_at  REAL,
    target_url   TEXT NOT NULL,
    target_host  TEXT NOT NULL,
    target_method TEXT NOT NULL,
    recipe_json  TEXT NOT NULL,
    input_text   TEXT,
    op_sequence  TEXT NOT NULL,
    detect_mode  TEXT NOT NULL,
    detect_value TEXT NOT NULL,
    total        INTEGER NOT NULL,
    hits         INTEGER NOT NULL,
    label        TEXT,
    persona      TEXT,
    frame_style  TEXT,
    stage_stats_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_host    ON fire_runs(target_host);
CREATE INDEX IF NOT EXISTS idx_runs_started ON fire_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_runs_label   ON fire_runs(label);
CREATE INDEX IF NOT EXISTS idx_runs_persona ON fire_runs(persona);
CREATE INDEX IF NOT EXISTS idx_runs_frame   ON fire_runs(frame_style);

CREATE TABLE IF NOT EXISTS fire_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES fire_runs(id) ON DELETE CASCADE,
    variant_idx  INTEGER NOT NULL,
    variant      TEXT NOT NULL,
    status       INTEGER,
    ms           INTEGER NOT NULL,
    snippet      TEXT,
    hit          INTEGER NOT NULL,
    error        TEXT,
    persona      TEXT,
    unique_ratio REAL,
    max_jaccard  REAL
);

CREATE INDEX IF NOT EXISTS idx_results_run  ON fire_results(run_id);
CREATE INDEX IF NOT EXISTS idx_results_hit  ON fire_results(hit);
CREATE INDEX IF NOT EXISTS idx_results_persona ON fire_results(persona);

CREATE TABLE IF NOT EXISTS op_attribution (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id   INTEGER NOT NULL REFERENCES fire_results(id) ON DELETE CASCADE,
    op_name     TEXT NOT NULL,
    op_category TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attr_op      ON op_attribution(op_name);
CREATE INDEX IF NOT EXISTS idx_attr_result  ON op_attribution(result_id);
"""


_init_lock = threading.Lock()
_initialized: bool = False


def _db_path() -> Path:
    """DB lives next to the recipes directory so backups come along."""
    return Path(__file__).resolve().parent / "fire_history.sqlite3"


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Yield a connection with row factory + FK enforcement."""
    c = sqlite3.connect(str(_db_path()), timeout=10.0, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    try:
        yield c
    finally:
        c.close()


def init() -> None:
    """Create schema if missing. Safe to call repeatedly.

    Also performs an idempotent additive migration for the diversity
    columns added later: stage_stats_json on fire_runs and
    (unique_ratio, max_jaccard) on fire_results. We try the ALTER
    and swallow the 'duplicate column' error so existing databases
    pick up the new columns on next init.
    """
    global _initialized
    with _init_lock:
        if _initialized:
            return
        with _conn() as c:
            c.executescript(SCHEMA)
            # Additive migrations. SQLite has no IF NOT EXISTS for ADD
            # COLUMN pre-3.35 reliably, so try-and-swallow duplicate.
            for ddl in (
                "ALTER TABLE fire_runs ADD COLUMN stage_stats_json TEXT",
                "ALTER TABLE fire_results ADD COLUMN unique_ratio REAL",
                "ALTER TABLE fire_results ADD COLUMN max_jaccard REAL",
                # AttackEval 4-level compliance grade (arXiv:2401.09002) from an
                # llm_judge detector; NULL when no judge ran. Reward signal for
                # the thompson_deck bandit — a graded score beats binary hit.
                "ALTER TABLE fire_results ADD COLUMN graded_score REAL",
            ):
                try:
                    c.execute(ddl)
                except sqlite3.OperationalError as e:
                    if "duplicate column" not in str(e).lower():
                        raise
        _initialized = True


def _host_from_url(url: str) -> str:
    """Best-effort host extraction without bringing in urllib for one call."""
    s = (url or "").strip()
    if "://" in s:
        s = s.split("://", 1)[1]
    return s.split("/", 1)[0].split(":", 1)[0] or "unknown"


def _op_sequence(recipe: list[dict]) -> str:
    """Compact recipe fingerprint: 'homoglyph>zero_width>leetspeak'."""
    return ">".join(s.get("op", "?") for s in (recipe or []))


def _persona_from_recipe(recipe: list[dict]) -> tuple[str | None, str | None]:
    """If any step is persona_seed, return (persona_name, frame_style).
    Otherwise return (None, None). The first persona_seed in the recipe
    wins; later persona_seed steps are ignored (they would have
    overwritten earlier wrapping, so the dominant persona is the first).
    Returns ('none', style) if persona_seed is used with persona='none' --
    the row still records that the wrapping was attempted and abandoned.

    For persona_sweep (which fans out to all personas), returns
    ('<sweep>', style) as a marker. The actual per-variant persona
    attribution for sweep runs is handled separately in record_result,
    which extracts the persona name from each rendered variant's text."""
    for step in recipe or []:
        if step.get("op") == "persona_seed":
            params = step.get("params", {}) or {}
            return (params.get("persona") or "none", params.get("frame_style"))
        if step.get("op") == "persona_sweep":
            params = step.get("params", {}) or {}
            return ("<sweep>", params.get("frame_style"))
    return (None, None)


def start_run(
    *,
    target_url: str,
    target_method: str,
    recipe: list[dict],
    input_text: str,
    detect_mode: str,
    detect_value: str,
    label: str | None = None,
    stage_stats: list[dict] | None = None,
) -> int:
    """Open a run record. Returns run_id.

    stage_stats is the diversity report from run_recipe (per-stage
    unique_ratio / max_jaccard / raw / deduped). Persisted as JSON
    on the run row so the analytics layer can aggregate diversity
    per recipe without re-running it.
    """
    init()
    recipe_json = json.dumps(recipe or [], ensure_ascii=False)
    persona, frame_style = _persona_from_recipe(recipe)
    stats_json = json.dumps(stage_stats or [], ensure_ascii=False)
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO fire_runs
              (started_at, target_url, target_host, target_method,
               recipe_json, input_text, op_sequence, detect_mode,
               detect_value, total, hits, label, persona, frame_style,
               stage_stats_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)
            """,
            (
                time.time(),
                target_url,
                _host_from_url(target_url),
                target_method,
                recipe_json,
                input_text,
                _op_sequence(recipe),
                detect_mode,
                detect_value,
                label,
                persona,
                frame_style,
                stats_json,
            ),
        )
        return int(cur.lastrowid)


def _extract_persona_from_variant(variant: str) -> str | None:
    """For sweep runs, extract which persona this variant was wrapped in.
    Scans the variant text for any persona name from the registry. The
    first match wins. Returns None if no known persona is found.

    This is needed because persona_sweep fans out to all personas in one
    recipe step, so the recipe params don't tell us which persona a
    specific variant used. The persona name is embedded in the rendered
    frame template (e.g. 'You are DAN.' or '[DAN]'), so we scan for it.
    """
    try:
        from ops.template_ops import _load_personas
        personas = [p["name"] for p in _load_personas()]
    except Exception:
        return None
    if not personas or not variant:
        return None
    # Sort by length descending so 'BetterDAN' matches before 'DAN' does
    # when both appear in the same text.
    for name in sorted(personas, key=len, reverse=True):
        if name in variant:
            return name
    return None


def record_result(
    *,
    run_id: int,
    variant_idx: int,
    variant: str,
    status: int | None,
    ms: int,
    snippet: str | None,
    hit: bool,
    error: str | None,
    recipe: list[dict],
    unique_ratio: float | None = None,
    max_jaccard: float | None = None,
    graded_score: float | None = None,
) -> int:
    """Persist one variant result. Returns result_id.

    unique_ratio / max_jaccard are the recipe-final diversity stats
    for the run (same value for every result in the run; we copy them
    to each row so per-variant queries can filter by diversity
    without joining stage_stats_json). NULL if the recipe did not
    compute diversity (legacy runs, recipes with no samplers).
    """
    init()
    from core import REGISTRY  # local import to avoid circular import on cold start
    # Extract persona for this specific variant.
    has_sweep = any(s.get("op") == "persona_sweep" for s in (recipe or []))
    has_seed = any(s.get("op") == "persona_seed" for s in (recipe or []))
    variant_persona: str | None = None
    if has_sweep:
        variant_persona = _extract_persona_from_variant(variant)
    elif has_seed:
        # For persona_seed, the run-level persona is set. Extract it from
        # the variant too so per-result queries work without joining runs.
        variant_persona = _extract_persona_from_variant(variant)
    with _conn() as c:
        cur = c.execute(
            """
            INSERT INTO fire_results
              (run_id, variant_idx, variant, status, ms, snippet, hit,
               error, persona, unique_ratio, max_jaccard, graded_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                variant_idx,
                variant,
                status,
                ms,
                snippet,
                1 if hit else 0,
                error,
                variant_persona,
                unique_ratio,
                max_jaccard,
                graded_score,
            ),
        )
        result_id = int(cur.lastrowid)
        # Attribution: every step in the recipe, with category from REGISTRY.
        if recipe:
            rows = []
            for step in recipe:
                op_name = step.get("op") or "unknown"
                reg = REGISTRY.get(op_name)
                cat = reg.category if reg is not None else "unknown"
                rows.append((result_id, op_name, cat))
            c.executemany(
                "INSERT INTO op_attribution (result_id, op_name, op_category) VALUES (?, ?, ?)",
                rows,
            )
        # Update running totals on the run record.
        c.execute(
            """
            UPDATE fire_runs
               SET total = total + 1,
                   hits  = hits + ?
             WHERE id = ?
            """,
            (1 if hit else 0, run_id),
        )
        return result_id


def finish_run(run_id: int) -> None:
    init()
    with _conn() as c:
        c.execute(
            "UPDATE fire_runs SET finished_at = ? WHERE id = ?",
            (time.time(), run_id),
        )


# ----- Read paths -----------------------------------------------------------

def list_runs(
    *,
    limit: int = 50,
    host: str | None = None,
    label: str | None = None,
    persona: str | None = None,
) -> list[dict]:
    init()
    where = []
    args: list[Any] = []
    if host:
        where.append("target_host = ?")
        args.append(host)
    if label:
        where.append("label = ?")
        args.append(label)
    if persona:
        where.append("persona = ?")
        args.append(persona)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    args.append(max(1, min(limit, 500)))
    with _conn() as c:
        rows = c.execute(
            f"""
            SELECT id, started_at, finished_at, target_host, target_url,
                   target_method, op_sequence, detect_mode, detect_value,
                   total, hits, label, persona, frame_style
              FROM fire_runs
              {clause}
             ORDER BY started_at DESC
             LIMIT ?
            """,
            args,
        ).fetchall()
    return [dict(r) for r in rows]


def get_run_results(run_id: int, *, limit: int = 500) -> list[dict]:
    init()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT variant_idx, variant, status, ms, snippet, hit, error
              FROM fire_results
             WHERE run_id = ?
             ORDER BY variant_idx ASC
             LIMIT ?
            """,
            (run_id, max(1, min(limit, 5000))),
        ).fetchall()
    return [dict(r) for r in rows]


def analytics_per_op(*, host: str | None = None) -> list[dict]:
    """
    Per-op hit rate. For each op name that appears as a leaf op in any
    saved result, return: total variants using it, total hits, hit rate.

    "Leaf" attribution is the last op in the recipe pipeline. This is a
    coarse signal -- it tells you which op carried the variant across the
    finish line, not which op caused the bypass. For that you need full
    ablation runs (one recipe per op alone), which is what the
    'analytical mode' in the UI is for.
    """
    init()
    args: list[Any] = []
    host_clause = ""
    if host:
        host_clause = "AND r.target_host = ?"
        args.append(host)
    with _conn() as c:
        rows = c.execute(
            f"""
            SELECT a.op_name,
                   a.op_category,
                   COUNT(*) AS n,
                   SUM(fr.hit) AS hits,
                   ROUND(100.0 * SUM(fr.hit) / COUNT(*), 1) AS hit_pct
              FROM op_attribution a
              JOIN fire_results fr ON fr.id = a.result_id
              JOIN fire_runs    r  ON r.id  = fr.run_id
             WHERE 1=1 {host_clause}
             GROUP BY a.op_name, a.op_category
             ORDER BY n DESC, a.op_name ASC
            """,
            args,
        ).fetchall()
    return [dict(r) for r in rows]


def analytics_per_host() -> list[dict]:
    """Per-target-host summary."""
    init()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT target_host,
                   COUNT(*) AS runs,
                   SUM(total) AS variants,
                   SUM(hits) AS hits,
                   ROUND(100.0 * SUM(hits) / NULLIF(SUM(total), 0), 1) AS hit_pct,
                   MAX(started_at) AS last_seen
              FROM fire_runs
             GROUP BY target_host
             ORDER BY runs DESC
            """,
        ).fetchall()
    return [dict(r) for r in rows]


def analytics_per_op_pair(*, min_n: int = 5) -> list[dict]:
    """
    Co-occurrence: which pairs of leaf ops land together on the same
    variant. Useful for spotting "homoglyph + zero_width wins" patterns
    that wouldn't show up in single-op stats.

    Returns op_a, op_b, n, n_hits, hit_pct for pairs seen >= min_n.
    """
    init()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT a1.op_name   AS op_a,
                   a2.op_name   AS op_b,
                   COUNT(*)     AS n,
                   SUM(fr.hit)  AS n_hits,
                   ROUND(100.0 * SUM(fr.hit) / COUNT(*), 1) AS hit_pct
              FROM fire_results fr
              JOIN op_attribution a1 ON a1.result_id = fr.id
              JOIN op_attribution a2 ON a2.result_id = fr.id AND a2.id > a1.id
             GROUP BY a1.op_name, a2.op_name
            HAVING COUNT(*) >= ?
             ORDER BY n DESC, hit_pct DESC
             LIMIT 100
            """,
            (min_n,),
        ).fetchall()
    return [dict(r) for r in rows]


def analytics_per_persona(*, host: str | None = None, min_n: int = 1) -> list[dict]:
    """
    Per-persona hit rate. Uses fire_results.persona (per-variant
    attribution), which correctly handles both persona_seed (one persona
    per run) and persona_sweep (all personas in one run). For each
    persona that appears in any saved result, return: total variants
    using it, total hits, hit rate.

    The frame_style column comes from the run (all variants in a sweep
    share the same frame), so we join to fire_runs for that.
    """
    init()
    host_clause = ""
    args: list[Any] = []
    if host:
        host_clause = "AND r.target_host = ?"
        args.append(host)
    args.append(min_n)
    with _conn() as c:
        rows = c.execute(
            f"""
            SELECT fr.persona,
                   r.frame_style,
                   COUNT(*) AS variants,
                   SUM(fr.hit) AS hits,
                   ROUND(100.0 * SUM(fr.hit) / COUNT(*), 1) AS hit_pct
              FROM fire_results fr
              JOIN fire_runs r ON r.id = fr.run_id
             WHERE fr.persona IS NOT NULL
               {host_clause}
             GROUP BY fr.persona, r.frame_style
            HAVING COUNT(*) >= ?
             ORDER BY hit_pct DESC, variants DESC
             LIMIT 200
            """,
            args,
        ).fetchall()
    return [dict(r) for r in rows]


def analytics_persona_x_target(*, min_n: int = 1) -> list[dict]:
    """
    Persona x target cross-tab using per-result persona attribution.
    For each (persona, target_host) pair, return: variants, hits,
    hit_pct. This is the analytics that answers "which persona works
    against which target" and correctly handles sweep runs where one
    run produces variants for 12 different personas.
    """
    init()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT fr.persona,
                   r.target_host,
                   COUNT(*) AS variants,
                   SUM(fr.hit) AS hits,
                   ROUND(100.0 * SUM(fr.hit) / COUNT(*), 1) AS hit_pct
              FROM fire_results fr
              JOIN fire_runs r ON r.id = fr.run_id
             WHERE fr.persona IS NOT NULL
             GROUP BY fr.persona, r.target_host
            HAVING COUNT(*) >= ?
             ORDER BY hit_pct DESC, variants DESC
             LIMIT 200
            """,
            (min_n,),
        ).fetchall()
    return [dict(r) for r in rows]


def summary() -> dict:
    """Top-line totals for the dashboard header."""
    init()
    with _conn() as c:
        row = c.execute(
            """
            SELECT COUNT(*)        AS runs,
                   COALESCE(SUM(total), 0) AS variants,
                   COALESCE(SUM(hits),  0) AS hits,
                   COUNT(DISTINCT target_host) AS hosts
              FROM fire_runs
            """,
        ).fetchone()
    return dict(row) if row else {"runs": 0, "variants": 0, "hits": 0, "hosts": 0}


def analytics_diversity(*, min_n: int = 1) -> list[dict]:
    """Aggregate per-recipe diversity stats and pair them with hit rate.

    The query pulls the stage_stats_json column on fire_runs and computes
    the mean unique_ratio / max_jaccard across stages for each op_sequence.
    Joins to per-run hit rate from fire_results. Rows with no recorded
    diversity stats (legacy runs, recipes with no sampler stages) are
    excluded.

    Output is sorted by hit_pct DESC, then variants DESC. Use this to find
    recipes that produce both high hit rate AND high diversity (the goal
    of any sampling campaign: lots of distinct hits across the variant
    space, not 50 near-duplicates of one payload).
    """
    init()
    with _conn() as c:
        rows = c.execute(
            """
            SELECT r.op_sequence,
                   r.target_host,
                   COUNT(DISTINCT r.id)             AS runs,
                   COUNT(*)                          AS variants,
                   SUM(fr.hit)                       AS hits,
                   AVG(fr.unique_ratio)              AS avg_unique_ratio,
                   AVG(fr.max_jaccard)               AS avg_max_jaccard,
                   MIN(fr.unique_ratio)              AS min_unique_ratio,
                   MAX(fr.max_jaccard)               AS max_max_jaccard
              FROM fire_runs  r
              JOIN fire_results fr ON fr.run_id = r.id
             WHERE fr.unique_ratio IS NOT NULL
               AND r.stage_stats_json IS NOT NULL
             GROUP BY r.op_sequence, r.target_host
            HAVING COUNT(*) >= ?
             ORDER BY
               (CAST(SUM(fr.hit) AS REAL) / NULLIF(COUNT(*), 0)) DESC,
               variants DESC
             LIMIT 200
            """,
            (min_n,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d["variants"]:
            d["hit_pct"] = round(d["hits"] / d["variants"] * 100, 2)
        else:
            d["hit_pct"] = 0.0
        for k in ("avg_unique_ratio", "avg_max_jaccard", "min_unique_ratio", "max_max_jaccard"):
            if d.get(k) is not None:
                d[k] = round(float(d[k]), 4)
        out.append(d)
    return out


def op_reward_stats(*, host: str | None = None) -> list[dict]:
    """Per leaf-op reward stats for the Thompson bandit (bandit.py).

    For each op that appears in any result, return n (times used), hits (binary),
    and graded_avg / graded_n (mean AttackEval grade where an llm_judge ran).
    host filters to one target so posteriors are per (op, target), which is what
    JailbreakOPT's contextual bandit needs. This is the join the bandit turns
    into Beta(alpha, beta) arms.
    """
    init()
    args: list[Any] = []
    host_clause = ""
    if host:
        host_clause = "AND r.target_host = ?"
        args.append(host)
    with _conn() as c:
        rows = c.execute(
            f"""
            SELECT a.op_name,
                   COUNT(*)                 AS n,
                   COALESCE(SUM(fr.hit), 0) AS hits,
                   AVG(fr.graded_score)     AS graded_avg,
                   COUNT(fr.graded_score)   AS graded_n
              FROM op_attribution a
              JOIN fire_results fr ON fr.id = a.result_id
              JOIN fire_runs    r  ON r.id  = fr.run_id
             WHERE 1=1 {host_clause}
             GROUP BY a.op_name
            """,
            args,
        ).fetchall()
    return [dict(r) for r in rows]


def analytics_variance(*, min_runs: int = 2) -> list[dict]:
    """Per-recipe hit-rate variance across runs (Furina instability proxy).

    Furina (arXiv:2605.26158) argues that OUTPUT VARIANCE is itself a signal: a
    recipe whose hit rate swings run-to-run is probing the target's instability
    region and is near a breakthrough. True Furina variance is per-payload across
    repeated fires; this is the cheap proxy computable from existing data —
    variance of the per-run hit rate for each (op_sequence, target_host). No new
    columns. Sorted by variance DESC so the most unstable recipes surface first.
    """
    init()
    with _conn() as c:
        rows = c.execute(
            "SELECT op_sequence, target_host, total, hits FROM fire_runs WHERE total > 0"
        ).fetchall()
    from collections import defaultdict
    groups: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in rows:
        groups[(r["op_sequence"], r["target_host"])].append(r["hits"] / r["total"])
    out = []
    for (seq, host), rates in groups.items():
        if len(rates) < min_runs:
            continue
        mean = sum(rates) / len(rates)
        var = sum((x - mean) ** 2 for x in rates) / len(rates)
        out.append({
            "op_sequence": seq, "target_host": host, "runs": len(rates),
            "mean_hit_rate": round(mean, 4), "variance": round(var, 4),
            "stdev": round(var ** 0.5, 4),
        })
    out.sort(key=lambda d: d["variance"], reverse=True)
    return out


def export_jsonl(path: str | Path, *, host: str | None = None) -> int:
    """
    Stream all results to a JSONL file. One JSON object per line:
      {run_id, host, op_sequence, variant_idx, variant, status, ms, hit, error}
    Returns the number of lines written.
    """
    init()
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    args: list[Any] = []
    join_clause = ""
    if host:
        join_clause = "AND r.target_host = ?"
        args.append(host)
    n = 0
    with _conn() as c, p.open("w", encoding="utf-8") as f:
        cur = c.execute(
            f"""
            SELECT fr.run_id, r.target_host, r.op_sequence, r.detect_mode,
                   r.detect_value, fr.variant_idx, fr.variant, fr.status,
                   fr.ms, fr.hit, fr.error, r.started_at
              FROM fire_results fr
              JOIN fire_runs    r ON r.id = fr.run_id
             WHERE 1=1 {join_clause}
             ORDER BY fr.run_id ASC, fr.variant_idx ASC
            """,
            args,
        )
        for row in cur:
            obj = dict(row)
            obj["hit"] = bool(obj["hit"])
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            n += 1
    return n