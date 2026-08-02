"""Thompson-sampling recipe selector — the adaptive deck.

Turns /history from a passive log into the training signal for op selection, per
JailbreakOPT (arXiv:2606.11425) and MemoAttack (arXiv:2605.29237). Each op is an
arm with a Beta(alpha, beta) posterior over its success probability against a
given target host. We sample each arm, rank by the sampled value (Thompson
sampling: explore uncertain arms, exploit proven ones), and assemble a recipe
under a family-diversity constraint (WildTeaming: don't stack same-family ops).

Reward signal, in priority order:
  1. AttackEval graded score (fire_results.graded_score) when an llm_judge ran —
     a 0/.33/.66/1.0 compliance grade is a far better reward than binary hit.
  2. Binary hit rate otherwise.

Cold start is free: an op with no history has alpha=beta=1 (uniform prior), so
Thompson sampling naturally explores it. No special seeding needed.

Lifecycle (MemoAttack): an op that has been used enough times with zero reward is
'retired' and skipped by default; anything with reward is 'active'; the rest is
'probation'. This is derived from history, not stored, so it self-corrects when
the target changes.

Pure stdlib. No new dependency.
"""
from __future__ import annotations

import math
import random

import history
from core import REGISTRY

# An op needs at least this many trials with ~zero reward before we retire it.
# Below this it stays in 'probation' so a couple of unlucky early misses don't
# bury an op that might work.
RETIRE_MIN_TRIALS = 8
_REWARD_EPS = 1e-6

# Families we never auto-chain: control/diversity utilities (repeat, echo,
# sample_n, ...) are not attack tactics — they shape variant counts, not the
# attack surface — so they would only pad a recipe.
_EXCLUDED_FAMILIES = {"control"}


def _reward(stat: dict) -> tuple[float, int]:
    """(expected_successes, n) for an arm. Prefers the AttackEval graded mean as
    the success probability; falls back to binary hits."""
    n = int(stat.get("n") or 0)
    if not n:
        return 0.0, 0
    graded_n = int(stat.get("graded_n") or 0)
    graded_avg = stat.get("graded_avg")
    if graded_n > 0 and graded_avg is not None:
        return float(graded_avg) * n, n
    return float(stat.get("hits") or 0), n


def _state(successes: float, n: int) -> str:
    if successes > _REWARD_EPS:
        return "active"
    if n >= RETIRE_MIN_TRIALS:
        return "retired"
    return "probation"


def _beta_sample(alpha: float, beta: float, rng: random.Random) -> float:
    """Draw from Beta(alpha, beta) via two Gamma draws (stdlib, no numpy)."""
    x = rng.gammavariate(alpha, 1.0)
    y = rng.gammavariate(beta, 1.0)
    return x / (x + y) if (x + y) > 0 else 0.5


def op_posteriors(*, host: str | None = None) -> list[dict]:
    """Every registered op as a bandit arm: prior/posterior params, reward,
    lifecycle state. Ops with no history carry the uniform prior (alpha=beta=1).
    Sorted by posterior mean so the table reads as a leaderboard."""
    stats = {s["op_name"]: s for s in history.op_reward_stats(host=host)}
    arms = []
    for name, op in REGISTRY.items():
        st = stats.get(name)
        if st:
            successes, n = _reward(st)
            successes = max(0.0, min(successes, float(n)))  # graded can't exceed n
        else:
            successes, n = 0.0, 0
        alpha = 1.0 + successes
        beta = 1.0 + (n - successes)
        arms.append({
            "op": name,
            "family": op.tactic_family,
            "category": op.category,
            "n": n,
            "successes": round(successes, 3),
            "reward": round(successes / n, 3) if n else None,
            "alpha": round(alpha, 3),
            "beta": round(beta, 3),
            "posterior_mean": round(alpha / (alpha + beta), 3),
            "state": _state(successes, n),
        })
    arms.sort(key=lambda a: a["posterior_mean"], reverse=True)
    return arms


# Default categories used when expanding optimizer/seed baskets from history
# (Job B). Framing-heavy only — not character/encoding/stego by default.
_SEED_BASKET_CATEGORIES = frozenset({
    "jailbreak", "template", "prose", "structure", "language", "carrier",
})


def top_seed_ops(
    *,
    host: str | None = None,
    k: int = 12,
    categories: frozenset[str] | set[str] | None = None,
    min_n: int = 1,
    exclude_retired: bool = True,
) -> list[str]:
    """Host-aware top-K op names for seed-basket expansion (Job B).

    Filters to framing-like categories by default; requires ``n >= min_n`` so
    pure uniform priors do not flood the basket. Empty host or empty history → [].
    """
    if not host:
        return []
    cats = frozenset(categories) if categories is not None else _SEED_BASKET_CATEGORIES
    k = max(1, min(int(k), 40))
    out: list[str] = []
    for a in op_posteriors(host=host):
        if a["category"] not in cats:
            continue
        if int(a.get("n") or 0) < min_n:
            continue
        if exclude_retired and a.get("state") == "retired":
            continue
        name = a.get("op")
        if name and name not in out:
            out.append(str(name))
        if len(out) >= k:
            break
    return out


def suggest_recipe(
    *,
    host: str | None = None,
    length: int = 4,
    enforce_diversity: bool = True,
    exclude_retired: bool = True,
    seed: int | None = None,
) -> dict:
    """Thompson-sample a recipe of `length` ops for `host`.

    Returns {"recipe": [{op, params}], "arms": [sampled arm detail...], "host",
    "cold_start": bool}. Ops use their default params. cold_start is True when no
    history exists for the host (every arm is on the uniform prior), which the
    caller can surface so the user knows the suggestion is pure exploration.
    """
    rng = random.Random(seed) if seed is not None else random.Random()
    length = max(1, min(int(length), 12))
    arms = op_posteriors(host=host)
    cold_start = all(a["n"] == 0 for a in arms)

    # Sample each eligible arm once, then greedily pick the highest samples under
    # the family-diversity + retirement constraints.
    sampled = []
    for a in arms:
        if a["family"] in _EXCLUDED_FAMILIES:
            continue
        if exclude_retired and a["state"] == "retired":
            continue
        theta = _beta_sample(a["alpha"], a["beta"], rng)
        sampled.append({**a, "theta": round(theta, 4)})
    sampled.sort(key=lambda a: a["theta"], reverse=True)

    recipe, chosen, used_families = [], [], set()
    for a in sampled:
        if len(recipe) >= length:
            break
        if enforce_diversity and a["family"] in used_families:
            continue
        used_families.add(a["family"])
        recipe.append({"op": a["op"], "params": {}})
        chosen.append(a)

    # If diversity starved us (few distinct families available) fall back to the
    # top remaining samples regardless of family so we still return `length` ops.
    if len(recipe) < length:
        picked = {a["op"] for a in chosen}
        for a in sampled:
            if len(recipe) >= length:
                break
            if a["op"] in picked:
                continue
            recipe.append({"op": a["op"], "params": {}})
            chosen.append(a)
            picked.add(a["op"])

    return {
        "host": host,
        "cold_start": cold_start,
        "length": len(recipe),
        "recipe": recipe,
        "op_sequence": ">".join(s["op"] for s in recipe),
        "arms": chosen,
    }


# ---------------------------------------------------------------------------
# All-time attempt log bandit (technique_logs.db) — token-like sampling
# ---------------------------------------------------------------------------

def _softmax(logits: list[float], temperature: float = 1.0) -> list[float]:
    """Numerically stable softmax. temperature → 0 peaks on argmax; →∞ flattens."""
    t = max(float(temperature), 1e-6)
    if not logits:
        return []
    scaled = [x / t for x in logits]
    m = max(scaled)
    exps = [math.exp(x - m) for x in scaled]
    z = sum(exps) or 1.0
    return [e / z for e in exps]


def _arm_from_counts(name: str, successes: float, n: int, *,
                     family: str = "", category: str = "",
                     tripwires: int = 0, extra: dict | None = None) -> dict:
    successes = max(0.0, min(float(successes), float(n) if n else 0.0))
    # Tripwire-heavy arms: treat each tripwire as an extra failure mass so lock-
    # prone signatures get down-weighted faster than plain refusals.
    fail_extra = 0.5 * max(0, int(tripwires))
    alpha = 1.0 + successes
    beta = 1.0 + max(0.0, (n - successes) + fail_extra)
    arm = {
        "arm": name,
        "family": family,
        "category": category,
        "n": n,
        "successes": round(successes, 3),
        "tripwires": int(tripwires),
        "reward": round(successes / n, 3) if n else None,
        "alpha": round(alpha, 3),
        "beta": round(beta, 3),
        "posterior_mean": round(alpha / (alpha + beta), 3),
        "state": _state(successes, n),
    }
    if extra:
        arm.update(extra)
    return arm


def attempt_posteriors(
    *,
    group_by: str = "technique",
    target_type: str | None = None,
    target_ref: str | None = None,
    path: str | None = None,
    seed_arms: list[str] | None = None,
    objective_class: str | None = None,
) -> list[dict]:
    """Beta posteriors from the all-time technique log (logs.technique_logs.db).

    group_by: technique | op.
    objective_class: class-conditioned bandit (filters to arena:<class> target_type).
    seed_arms: optional labels to include even with n=0 (uniform prior) so the
    arena ladder / op catalog always appears in the leaderboard.
    """
    import logs as _logs
    from pathlib import Path

    p = Path(path) if path else None
    try:
        _logs.init_db(p, sync=False)
        raw = _logs.arm_reward_stats(
            group_by=group_by, target_type=target_type, target_ref=target_ref,
            path=p, objective_class=objective_class,
        )
    except Exception:
        raw = []
    if raw and isinstance(raw[0], dict) and raw[0].get("error"):
        raw = []

    by_name = {str(r["grp"]): r for r in raw if r.get("grp")}
    names = list(by_name.keys())
    if seed_arms:
        for s in seed_arms:
            if s and s not in by_name:
                names.append(s)

    # Optional family/category from REGISTRY when group_by=op
    arms: list[dict] = []
    for name in names:
        r = by_name.get(name) or {}
        n = int(r.get("n") or 0)
        successes = float(r.get("successes") or 0.0)
        tripwires = int(r.get("tripwires") or 0)
        family = category = ""
        if group_by == "op" and name in REGISTRY:
            op = REGISTRY[name]
            family = op.tactic_family
            category = op.category
        arms.append(_arm_from_counts(
            name, successes, n, family=family, category=category, tripwires=tripwires,
            extra={"source": "technique_logs", "group_by": group_by},
        ))

    # Merge fire_history op stats when grouping by op (additive evidence).
    if group_by == "op":
        try:
            fire = {s["op_name"]: s for s in history.op_reward_stats(host=None)}
        except Exception:
            fire = {}
        seen = {a["arm"] for a in arms}
        for name, st in fire.items():
            suc, n = _reward(st)
            if name in seen:
                # blend: re-find and add counts (simple sum of evidence)
                for a in arms:
                    if a["arm"] != name:
                        continue
                    total_s = a["successes"] + suc
                    total_n = a["n"] + n
                    blended = _arm_from_counts(
                        name, total_s, total_n,
                        family=a.get("family") or (REGISTRY[name].tactic_family if name in REGISTRY else ""),
                        category=a.get("category") or (REGISTRY[name].category if name in REGISTRY else ""),
                        tripwires=int(a.get("tripwires") or 0),
                        extra={"source": "technique_logs+fire_history", "group_by": "op"},
                    )
                    a.update(blended)
                    break
            else:
                family = REGISTRY[name].tactic_family if name in REGISTRY else ""
                category = REGISTRY[name].category if name in REGISTRY else ""
                arms.append(_arm_from_counts(
                    name, suc, n, family=family, category=category,
                    extra={"source": "fire_history", "group_by": "op"},
                ))

    arms.sort(key=lambda a: (a["posterior_mean"], a["n"]), reverse=True)
    return arms


def ladder_arm_stats(
    labels: list[str],
    *,
    op_behind: dict[str, str] | None = None,
    target_type: str | None = None,
    target_ref: str | None = None,
    path: str | None = None,
    objective_class: str | None = None,
) -> dict[str, dict]:
    """Posteriors for arena ladder labels, merging technique-log + mapped op evidence.

    When a ladder label has no rows yet but its backing op (e.g. policy_puppetry)
    has fire history, that op's reward is used so the bandit is not blind.
    objective_class scopes technique-log evidence to arena:<class> only (op merge
    still uses global op fire history when class-scoped n=0).
    """
    tech = {
        a["arm"]: a
        for a in attempt_posteriors(
            group_by="technique", target_type=target_type, target_ref=target_ref,
            path=path, seed_arms=list(labels), objective_class=objective_class,
        )
    }
    op_names = list({v for v in (op_behind or {}).values() if v})
    # Op-level fire_history is global; only technique_logs are class-scoped.
    ops = {
        a["arm"]: a
        for a in attempt_posteriors(
            group_by="op", target_type=None, target_ref=target_ref,
            path=path, seed_arms=op_names, objective_class=None,
        )
    } if op_names else {}

    out: dict[str, dict] = {}
    for lab in labels:
        a = dict(tech.get(lab) or _arm_from_counts(lab, 0.0, 0))
        op_name = (op_behind or {}).get(lab)
        if op_name and op_name in ops and int(a.get("n") or 0) == 0 and int(ops[op_name].get("n") or 0) > 0:
            # promote op evidence under the ladder label
            o = ops[op_name]
            a = _arm_from_counts(
                lab, float(o["successes"]), int(o["n"]),
                family=o.get("family") or "",
                category=o.get("category") or "",
                tripwires=int(o.get("tripwires") or 0),
                extra={"source": f"op:{op_name}", "group_by": "technique", "via_op": op_name},
            )
        elif op_name and op_name in ops and int(ops[op_name].get("n") or 0) > 0:
            # additive merge when both have data
            o = ops[op_name]
            a = _arm_from_counts(
                lab,
                float(a.get("successes") or 0) + float(o.get("successes") or 0),
                int(a.get("n") or 0) + int(o.get("n") or 0),
                family=a.get("family") or o.get("family") or "",
                category=a.get("category") or o.get("category") or "",
                tripwires=int(a.get("tripwires") or 0) + int(o.get("tripwires") or 0),
                extra={"source": "technique+op", "group_by": "technique", "via_op": op_name},
            )
        out[lab] = a
    return out


def sample_arm(
    candidates: list[str],
    *,
    group_by: str = "technique",
    method: str = "thompson",
    temperature: float = 1.0,
    target_type: str | None = None,
    target_ref: str | None = None,
    exclude_retired: bool = True,
    path: str | None = None,
    seed: int | None = None,
    kind_by: dict[str, str] | None = None,
    exclude_kinds: set[str] | frozenset[str] | None = None,
    posts_override: dict[str, dict] | None = None,
    objective_class: str | None = None,
) -> dict:
    """Sample one arm from `candidates` using all-time attempt posteriors.

    method:
      thompson — draw θ ~ Beta(α,β) per arm, pick max (default; explores)
      softmax  — P(i) ∝ exp(logit_i / T) with logit = log(posterior_mean);
                 temperature like LLM sampling (low=greedy, high=explore)

    objective_class: class-conditioned technique posteriors (arena:<class>).

    Returns {arm, method, temperature, posterior_mean, state, n, reward, p, ...}
    or {error} if nothing eligible.
    """
    if not candidates:
        return {"error": "no candidates"}
    rng = random.Random(seed) if seed is not None else random.Random()
    if posts_override is not None:
        posts = posts_override
    else:
        posts = {
            a["arm"]: a
            for a in attempt_posteriors(
                group_by=group_by, target_type=target_type, target_ref=target_ref,
                path=path, seed_arms=list(candidates), objective_class=objective_class,
            )
        }
    exclude_kinds = set(exclude_kinds or ())
    kind_by = kind_by or {}

    eligible: list[dict] = []
    for name in candidates:
        a = posts.get(name) or _arm_from_counts(name, 0.0, 0)
        if exclude_retired and a.get("state") == "retired":
            continue
        k = kind_by.get(name)
        if k and k in exclude_kinds:
            continue
        eligible.append(a)

    if not eligible:
        return {"error": "no eligible arms", "candidates": list(candidates)}

    method = (method or "thompson").lower().strip()
    if method == "softmax":
        # logit from posterior mean; tiny ladder noise already in cold prior
        logits = []
        for a in eligible:
            pm = float(a["posterior_mean"])
            # log domain: avoid log(0); retired already filtered
            logits.append(math.log(max(pm, 1e-6)))
        probs = _softmax(logits, temperature=temperature)
        # categorical draw
        u = rng.random()
        cum = 0.0
        pick_i = len(eligible) - 1
        for i, p in enumerate(probs):
            cum += p
            if u <= cum:
                pick_i = i
                break
        chosen = eligible[pick_i]
        return {
            **chosen,
            "method": "softmax",
            "temperature": float(temperature),
            "p": round(probs[pick_i], 4),
            "mass": [
                {"arm": eligible[i]["arm"], "p": round(probs[i], 4),
                 "posterior_mean": eligible[i]["posterior_mean"],
                 "n": eligible[i]["n"], "state": eligible[i]["state"]}
                for i in range(len(eligible))
            ],
        }

    # Thompson (default)
    best, best_theta = None, -1.0
    scored = []
    for a in eligible:
        theta = _beta_sample(float(a["alpha"]), float(a["beta"]), rng)
        scored.append({**a, "theta": round(theta, 4)})
        if theta > best_theta:
            best_theta = theta
            best = a
    scored.sort(key=lambda x: x["theta"], reverse=True)
    assert best is not None
    return {
        **best,
        "method": "thompson",
        "temperature": None,
        "theta": round(best_theta, 4),
        "mass": [
            {"arm": s["arm"], "theta": s["theta"],
             "posterior_mean": s["posterior_mean"], "n": s["n"], "state": s["state"]}
            for s in scored
        ],
    }
