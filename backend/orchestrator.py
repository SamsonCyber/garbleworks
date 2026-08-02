"""Caucus — model-consensus orchestration for the Garbleworks fleet.

Turns N agents (Hermes + Claude windows) from merely non-colliding into
collaborative: they POOL candidate moves (some seeded by the harness itself via
arena_solver + the framing generator), VOTE, and a consensus ranker drops vetoed
moves, enforces tactic-family diversity, and ASSIGNS the top moves to distinct
live agents — so the fleet fires K different high-consensus moves in parallel,
none overlapping and none already known-dead.

Pure logic lives here (seed / score / rank_and_assign). console.py owns the DB,
the routes, and the websocket.
"""
from __future__ import annotations

import math

import arena_solver

try:  # core carries the op REGISTRY + run_recipe (same path generate_framings uses)
    from core import REGISTRY, run_recipe
except Exception:  # pragma: no cover - keeps the console importable if core shifts
    REGISTRY, run_recipe = {}, None

# A diverse opener set spanning tactic families; intersected with REGISTRY at runtime.
SEED_TECHNIQUES = [
    "response_format_split", "past_tense", "persuasion_reframe", "cot_hijack",
    "refusal_suppression", "chat_template_inject", "policy_puppetry", "deep_inception",
]


def family_of(technique: str) -> str:
    op = REGISTRY.get(technique) if REGISTRY else None
    return getattr(op, "tactic_family", None) or "emergent"


def _frame(objective: str, technique: str) -> str | None:
    if not run_recipe or technique not in REGISTRY:
        return None
    try:
        variants = run_recipe(objective, [{"op": technique, "params": {}}], max_variants=1)[0]
        return variants[0] if variants else None
    except Exception:
        return None


def seed(objective: str, history: list[dict] | None = None, avoid: set[str] | None = None) -> list[dict]:
    """Harness-seeded proposals: one ladder-aware move from arena_solver plus a
    family-diverse batch from the framing generator, skipping anything in `avoid`."""
    avoid = {a.lower() for a in (avoid or set())}
    out, seen = [], set()

    try:  # the smart, history-aware move (respects refusal/tripwire ladder)
        mv = arena_solver.next_move(objective, history or [])
        if mv and not mv.get("done") and mv.get("payload"):
            t = mv.get("technique") or "advisor"
            pay = mv["payload"]
            pay = "\n\n".join(pay) if isinstance(pay, list) else pay
            if t.lower() not in avoid:
                out.append({"technique": t, "op": mv.get("op"), "payload": pay,
                            "rationale": mv.get("rationale"), "defense_type": mv.get("defense_type"),
                            "kind": mv.get("kind") or "single", "source": "mcp:arena_solver",
                            "family": family_of(t)})
                seen.add(t.lower())
    except Exception:
        pass

    for t in SEED_TECHNIQUES:  # family-diverse framing batch
        if t.lower() in avoid or t.lower() in seen or t not in REGISTRY:
            continue
        fr = _frame(objective, t)
        if fr:
            out.append({"technique": t, "op": t, "payload": fr, "rationale": None,
                        "defense_type": None, "kind": "single", "source": "mcp:generate_framings",
                        "family": family_of(t)})
            seen.add(t.lower())
    return out


def framings(objective: str, avoid: set[str] | None = None, limit: int = 3) -> list[dict]:
    """Just the fast framing-generator alternatives (no arena_solver call) — the
    'what else the fleet weighed' strip for the loop screen."""
    avoid = {a.lower() for a in (avoid or set())}
    out = []
    for t in SEED_TECHNIQUES:
        if t.lower() in avoid or t not in REGISTRY:
            continue
        fr = _frame(objective, t)
        if fr:
            out.append({"technique": t, "op": t, "payload": fr, "family": family_of(t),
                        "source": "mcp:generate_framings"})
        if len(out) >= limit:
            break
    return out


def _wilson_lcb(wins: int, n: int, z: float = 1.96) -> float:
    if n <= 0:
        return 0.0
    p = wins / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denom)


def score_proposal(prop: dict, votes: list[dict], prior: dict) -> dict:
    """Consensus score for one proposal.
    votes: [{"agent","vote":+1|-1,"confidence":0..1}]  prior: {"wins","n"} for this technique/target."""
    approve = sum(v["confidence"] for v in votes if v["vote"] > 0)
    veto = sum(v["confidence"] for v in votes if v["vote"] < 0)
    n_veto = sum(1 for v in votes if v["vote"] < 0)
    vote_term = approve - veto
    lcb = _wilson_lcb(prior.get("wins", 0), prior.get("n", 0))
    # a technique that's been fired here and NEVER won is a soft-dead move
    tried_penalty = 0.6 * prior.get("n", 0) if prior.get("n", 0) and not prior.get("wins", 0) else 0.0
    score = vote_term + 1.5 * lcb - tried_penalty
    return {"score": round(score, 3), "approve": round(approve, 2), "veto": round(veto, 2),
            "n_veto": n_veto, "lcb": round(lcb, 3), "vetoed": n_veto >= 2 and vote_term < 0}


def rank_and_assign(proposals: list[dict], votes_by_prop: dict, priors_by_tech: dict,
                    live_agents: list[str], k: int | None = None) -> dict:
    """Rank by consensus, drop vetoed, enforce family diversity, assign to distinct agents."""
    live = list(dict.fromkeys(live_agents))  # de-dup, keep order
    k = k or (len(live) or 3)

    scored = []
    for p in proposals:
        if p.get("status") in ("assigned", "fired", "dropped"):
            continue
        s = score_proposal(p, votes_by_prop.get(p["id"], []),
                           priors_by_tech.get(p["technique"].lower(), {}))
        if s["vetoed"]:
            continue
        scored.append({**p, **s})
    scored.sort(key=lambda x: x["score"], reverse=True)

    picked, used_fam = [], set()
    for p in scored:
        fam = p.get("family") or "emergent"
        if fam in used_fam and len(scored) > k:  # keep families distinct while we can
            continue
        picked.append(p)
        used_fam.add(fam)
        if len(picked) >= k:
            break

    assignments = []
    if live:
        idx = 0
        for p in picked:
            order = live[idx:] + live[:idx]
            pick = next((a for a in order if a != p["agent"]), order[0])  # avoid self-assign
            assignments.append({"proposal_id": p["id"], "assignee": pick,
                                "technique": p["technique"], "score": p["score"]})
            idx = (live.index(pick) + 1) % len(live)
    else:
        assignments = [{"proposal_id": p["id"], "assignee": None,
                        "technique": p["technique"], "score": p["score"]} for p in picked]

    return {"assignments": assignments, "ranked": scored}
