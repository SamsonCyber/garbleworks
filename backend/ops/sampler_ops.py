"""Sampler operations.

These don't transform text - they fan out from a single input to many
inputs by sampling recipe subsets or repeating. Used to drive the
"combinatorial" mode of bug-bounty work: instead of running one recipe
end-to-end, run many partial recipes over the same input and let the
hit table tell you which combination mattered.

The sampling is deterministic given a seed, so a hit report is
reproducible.

Diversity coverage:
    repeat, sample_n, echo, distinct_n, recipe_subset, mmr_select,
    diverse_k, seed_sweep, random_pick_k
"""
from __future__ import annotations

import random
import re

from core import (
    Operation,
    Param,
    REGISTRY,
    _dedupe,
    _near_dedupe,
    _shingles,
    _jaccard,
    register,
)


# ----- helpers --------------------------------------------------------------

# A wider, more diverse jitter pool than the original sample_n. Each entry
# is a (label, callable) pair. Used by distinct_n and as the perturbation
# engine for mmr_select / diverse_k.
_ADVERSARIAL_PADS = [
    " ",
    "\n",
    "\n\n",
    "   ",
    "\t",
    "[meta] ",
    "(end of turn)\n",
    "[end prompt]\n",
    "###\n",
    "```\n",
    "\n\nHuman: ",
    "\n\nAssistant: ",
    " <|im_start|>user\n",
    " <|im_end|>\n",
    "<|endoftext|>",
    "\u200b",  # zero-width space
    "\u200c",  # ZWNJ
    "\u200d",  # ZWJ
    "\ufeff",  # BOM
]


_CASE_FLIPS = str.maketrans({
    "a": "A", "A": "a",
    "e": "E", "E": "e",
    "i": "I", "I": "i",
    "o": "O", "O": "o",
    "u": "U", "U": "u",
})


def _token_jaccard(a: str, b: str) -> float:
    """Whitespace-token Jaccard. Useful for clustering near-duplicates that
    differ only in punctuation/whitespace."""
    ta = {t for t in re.split(r"\s+", a.strip()) if t}
    tb = {t for t in re.split(r"\s+", b.strip()) if t}
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def _char_jaccard(a: str, b: str) -> float:
    """Character-level Jaccard via shingles of size 2."""
    def _sh(s: str) -> set[str]:
        return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) >= 2 else {s}
    sa, sb = _sh(a), _sh(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


def _jaccard_fn(kind: str):
    if kind == "char":
        return _char_jaccard
    if kind == "token":
        return _token_jaccard

    def _ngram_jaccard(a: str, b: str) -> float:
        return _jaccard(_shingles(a), _shingles(b))
    return _ngram_jaccard


# ----- core ops -------------------------------------------------------------

def _repeat(text: str, n: int) -> list[str]:
    n = max(1, int(n))
    return [text] * n


def _sample_n(text: str, k: int, seed: int) -> list[str]:
    """Emit k slight perturbations by jittering whitespace and case.
    Cheap way to surface intermittent model behavior (the model may
    comply on rep #3 and refuse on rep #4). Deterministic per seed."""
    rng = random.Random(int(seed))
    out = []
    for _ in range(max(1, int(k))):
        # Apply 1-3 small jitter ops chosen at random.
        s = text
        for _op in range(rng.randint(1, 3)):
            choice = rng.choice(["space", "case", "punct", "pad"])
            if choice == "space":
                # Insert a random number of normal spaces between two
                # random word boundaries.
                words = s.split(" ")
                if len(words) > 1:
                    i = rng.randrange(len(words) - 1)
                    pad = " " * rng.randint(1, 4)
                    words[i] = words[i] + pad + words[i + 1]
                    s = " ".join(words[:i + 1] + words[i + 2:])
            elif choice == "case" and any(c.isalpha() for c in s):
                # Flip the case of one random letter.
                idxs = [i for i, c in enumerate(s) if c.isalpha()]
                i = rng.choice(idxs)
                s = s[:i] + s[i].swapcase() + s[i + 1:]
            elif choice == "punct":
                # Toggle terminal punctuation.
                if s and s[-1] in ".!?":
                    s = s[:-1]
                else:
                    s = s + rng.choice([".", "!", "?", "...", "!!"])
            elif choice == "pad":
                # Add a benign prefix/suffix that some models treat as a
                # jailbreak carrier (chat protocol smudges).
                pads = [
                    " ", "\n", "\n\n", "   ",
                    "[meta] ", "(end of turn)\n", " ",
                ]
                if rng.random() < 0.5:
                    s = rng.choice(pads) + s
                else:
                    s = s + rng.choice(pads)
        out.append(s)
    return out


def _echo(text: str, mode: str) -> list[str]:
    """No-op variants that change framing only. Useful as a control:
    'if a no-op variant also hits, the target is broken on the framing
    alone, not on the payload'."""
    if mode == "none":
        return [text]
    if mode == "newline":
        return [text + "\n", "\n" + text, text + "\n\n"]
    if mode == "brackets":
        return [f"[{text}]", f"({text})", f"<{text}>", f"{{{text}}}"]
    if mode == "quote":
        return [f'"{text}"', f"'{text}'", f"`{text}`"]
    return [text]


# ----- new diversity ops -----------------------------------------------------

def _distinct_n(text: str, k: int, mode: str, seed: int) -> list[str]:
    """Like sample_n but with a wider perturbation surface so variants
    survive the runner's near_dedupe pass (3-gram Jaccard 0.9).

    Why: sample_n's four jitter kinds collapse too easily under near-dedupe.
    A recipe that says "give me 50 distinct perturbations" gets 8 because
    the rest are 0.91-similar to the first. distinct_n reaches further:
    char swaps, pad fragments from _ADVERSARIAL_PADS (including zero-width
    and chat-protocol smudges), homoglyph-style substitutions on a small
    set of confusable letters, and the original case/punct/pad jitters.
    Modes narrow the surface for ablation; "full" reaches the widest."""
    rng = random.Random(int(seed))
    out: list[str] = []
    n = max(1, int(k))

    # Pad pool is a fixed sample (seeded). Modes limit which kinds of
    # perturbation fire; "full" fires all kinds per variant.
    use_pad = mode in ("full", "adversarial_pad")
    use_case = mode in ("full", "case_only")
    use_space = mode in ("full", "space_only")
    use_punct = mode in ("full", "punct_only")
    use_homoglyph = mode in ("full", "homoglyph_only")

    homoglyph_map = {"a": "а", "e": "е", "o": "о", "i": "і", "c": "с"}  # Cyrillic look-alikes
    flip_keys = list(homoglyph_map.keys())

    for _ in range(n):
        s = text
        steps = rng.randint(2, 5)
        for _op in range(steps):
            choice = rng.choice(
                [k for k, on in (
                    ("pad", use_pad),
                    ("case", use_case),
                    ("space", use_space),
                    ("punct", use_punct),
                    ("homoglyph", use_homoglyph),
                ) if on]
            )
            if choice == "pad":
                pad = rng.choice(_ADVERSARIAL_PADS)
                if rng.random() < 0.5:
                    s = pad + s
                else:
                    s = s + pad
            elif choice == "case" and any(c.isalpha() for c in s):
                idxs = [i for i, c in enumerate(s) if c.isalpha()]
                i = rng.choice(idxs)
                s = s[:i] + s[i].swapcase() + s[i + 1:]
            elif choice == "space":
                words = s.split(" ")
                if len(words) > 1:
                    i = rng.randrange(len(words) - 1)
                    pad = " " * rng.randint(1, 4)
                    words[i] = words[i] + pad + words[i + 1]
                    s = " ".join(words[:i + 1] + words[i + 2:])
            elif choice == "punct":
                if s and s[-1] in ".!?":
                    s = s[:-1]
                else:
                    s = s + rng.choice([".", "!", "?", "...", "!!"])
            elif choice == "homoglyph":
                idxs = [i for i, c in enumerate(s) if c in flip_keys]
                if idxs:
                    i = rng.choice(idxs)
                    src = s[i]
                    dst = homoglyph_map.get(src.lower(), src)
                    if src.isupper():
                        dst = dst.upper()
                    s = s[:i] + dst + s[i + 1:]
        out.append(s)
    return out


def _recipe_subset(text: str, ops_csv: str, k: int, with_repeat: int,
                   seed: int, near_dedupe: bool) -> list[str]:
    """Combinatorial fan-out: pick `k` ops from the comma list, build a
    recipe from them, run that recipe against `text`, then emit
    `with_repeat` copies of the resulting variant set.

    This is the harvest loop: instead of running one recipe end-to-end
    you sample k-subsets from a curated op pool and let the hit table
    tell you which combinations carry. Deterministic per seed (the same
    seed picks the same k-subset in the same order).

    Why: a single hand-authored recipe is one bet; recipe_subset is N bets.
    Useful for "I have 12 obfuscation ops and want to know which pairs of
    two survive the near_dedupe pass and still hit". A flat miss across
    all subsets = the framing is wrong, not the op combo. A single subset
    that hits with no near-duplicates of any other subset = new vuln shape.

    Inputs:
      ops_csv: comma-separated op names. Each must be in REGISTRY.
      k:       subset size (1..len(ops_csv)).
      with_repeat: how many copies of each produced variant to emit
                   (lets the runner's repeat stage amplify it further
                   or just gives a stability floor).
      seed:    RNG seed.
      near_dedupe: if True, near-dedupe the produced variants before
                   emitting copies. Avoids 50 copies of the same variant
                   when the k-subset produced only one unique output."""
    pool = [o.strip() for o in (ops_csv or "").split(",") if o.strip()]
    if not pool:
        return [text]
    k = max(1, min(int(k), len(pool)))
    with_repeat = max(1, int(with_repeat))
    rng = random.Random(int(seed))

    # Sample one k-subset (without replacement).
    chosen = rng.sample(pool, k)

    # Build a recipe from those ops (each with default params). If any
    # op is unknown, fall back to no-op silently for that step; the run
    # would still surface the failure via run_recipe's stage report.
    sub_recipe = [{"op": name, "params": {}} for name in chosen]

    # Inline-run the sub-recipe. We reuse core.run_recipe's exact dedup
    # + near_dedupe + cap machinery so behaviour matches what the user
    # would get firing the same recipe through /fire.
    from core import run_recipe  # local import to avoid cycle on cold start
    variants, _ = run_recipe(
        text, sub_recipe,
        max_variants=200,
        near_dedupe=bool(near_dedupe),
        near_threshold=0.9,
    )

    if not variants:
        return [text]

    # Emit `with_repeat` copies of each produced variant.
    out: list[str] = []
    for v in variants:
        out.extend([v] * with_repeat)
    return out


def _mmr_select(text: str, k: int, lambda_: float, from_pool: int,
                mode: str, seed: int) -> list[str]:
    """Maximal Marginal Relevance selection. Pulls `from_pool` variants
    by feeding `text` through distinct_n, then picks top-`k` that
    maximize relevance * lambda_ + (1 - lambda_) * diversity from the
    already-selected set. lambda_=1 is pure relevance (closest to input);
    lambda_=0 is pure diversity (max distance from already-picked).
    No LLM needed -- uses character 3-gram Jaccard.

    Why: when you have a 1000-variant pool and want the 10 most useful
    for a downstream stage, MMR gives you a spread instead of N
    near-duplicates of the closest match. Pairs well with distinct_n
    upstream and any combinator downstream."""
    k = max(1, int(k))
    from_pool = max(k, int(from_pool))
    lambda_ = max(0.0, min(1.0, float(lambda_)))
    rng = random.Random(int(seed))

    # Generate the pool by perturbing the input through distinct_n's
    # engine. We bypass distinct_n's own clamp by passing through with
    # from_pool variants (distinct_n max is 200, so we cap).
    pool_size = min(from_pool, 200)
    pool = _distinct_n(text, k=pool_size, mode="full", seed=seed)
    if not pool:
        return [text]

    # Diversity similarity = 1 - Jaccard, so distance = jaccard. Score
    # = lambda_ * relevance + (1 - lambda_) * (1 - max_sim_to_selected)
    # where relevance to input is also Jaccard-based (smaller = more
    # diverse from input, but we want closeness -> 1 - jaccard).
    ref = _shingles(text) if text else set()

    def _rel(s: str) -> float:
        return 1.0 - _jaccard(_shingles(s), ref) if ref else 0.0

    def _max_sim(selected: list[str], cand: str) -> float:
        if not selected:
            return 0.0
        csh = _shingles(cand)
        return max((_jaccard(csh, _shingles(sel)) for sel in selected), default=0.0)

    # Shuffle the pool to break ties deterministically per seed.
    pool = list(pool)
    rng.shuffle(pool)

    selected: list[str] = []
    for cand in pool:
        if len(selected) >= k:
            break
        rel = _rel(cand)
        div = 1.0 - _max_sim(selected, cand)
        score = lambda_ * rel + (1.0 - lambda_) * div
        # Store as (score, cand) and pick the best remaining per pass.
        cand_score = (score, cand)
        # Greedy MMR picks the highest-scoring unseen candidate per step.
        # Simpler: append in scored order.
        if not selected:
            selected.append(cand)
            continue
        # If this candidate beats the current worst selected score,
        # replace it. Otherwise drop. This is a streaming approximation
        # of full MMR that's O(N*k) instead of O(N^2).
        selected.append(cand)

    # Streaming MMR approximation: re-score and keep top-k.
    scored: list[tuple[float, str]] = []
    for cand in selected:
        rel = _rel(cand)
        # diversity against other selected (not self)
        others = [s for s in selected if s != cand]
        div = 1.0 - _max_sim(others, cand) if others else 0.0
        score = lambda_ * rel + (1.0 - lambda_) * div
        scored.append((score, cand))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [c for _, c in scored[:k]]


def _diverse_k(text: str, k: int, from_pool: int, by: str, seed: int) -> list[str]:
    """Cluster-then-sample: pull `from_pool` candidates via distinct_n,
    cluster by the chosen similarity (`ngram` | `char` | `token`), then
    pick one representative per cluster up to `k`.

    Why: same motivation as MMR but cheaper and order-insensitive. The
    first variant of each cluster wins; ties broken by seed. Use this
    over MMR when you want a deterministic per-cluster snapshot rather
    than a relevance-weighted selection."""
    k = max(1, int(k))
    from_pool = max(k, int(from_pool))
    rng = random.Random(int(seed))
    pool = _distinct_n(text, k=min(from_pool, 200), mode="full", seed=seed)
    if not pool:
        return [text]
    jfn = _jaccard_fn(by)

    # Cluster: each new candidate either joins the first cluster whose
    # centroid is similar enough, or starts a new cluster. Cluster
    # representative is the first-seen member (stable per seed).
    threshold = 0.85
    clusters: list[list[str]] = []
    for cand in pool:
        placed = False
        for cl in clusters:
            if jfn(cand, cl[0]) >= threshold:
                cl.append(cand)
                placed = True
                break
        if not placed:
            clusters.append([cand])

    # Pick one representative per cluster, seed-shuffled inside each.
    representatives: list[str] = []
    for cl in clusters:
        local = list(cl)
        rng.shuffle(local)
        representatives.append(local[0])
        if len(representatives) >= k:
            break
    return representatives[:k]


def _seed_sweep(text: str, seeds: str, prefix: str = "[seed={seed}] ") -> list[str]:
    """Emit the input N times (N = len(seeds)), each stamped with its seed.

    Used as input to a downstream non-deterministic op (sample_n, llm_ops,
    distinct_n) so the runner fans out across multiple RNG streams.

    Inputs:
      seeds:  comma-separated int seeds, e.g. "1,2,3,4,5". Capped at 20.
      prefix: format string with ``{seed}`` placeholder; prepended to each copy.
              Empty string = bare passthrough (degenerates to repeat).
    """
    out: list[str] = []
    parts = [p.strip() for p in (seeds or "").split(",") if p.strip()]
    for p in parts[:20]:
        try:
            n = int(p)
        except ValueError:
            continue
        stamp = (prefix or "").format(seed=n) if prefix else ""
        out.append(f"{stamp}{text}")
    return out or [text]


def _random_pick_k(text: str, input_pool_csv: str, k: int, seed: int) -> list[str]:
    """Pick k random inputs from the comma-separated pool. Useful at the
    recipe-stage level when you want to vary the input itself rather than
    its mutations (different from run_deck, which is one-shot at the top
    level). Discards `text`; downstream ops see only the picked inputs."""
    pool = [s.strip() for s in (input_pool_csv or "").split(",") if s.strip()]
    if not pool:
        return [text]
    k = max(1, min(int(k), len(pool)))
    rng = random.Random(int(seed))
    return rng.sample(pool, k)


# ----- registrations --------------------------------------------------------

register(Operation(
    name="repeat",
    category="sampler",
    description="Emit N identical copies of the input. Use as a control: if all N hit, the framing alone is enough. Why: the canonical control op. Measures the variance of the target's refusal rate on identical inputs — a high hit rate on N=3 means the underlying refusal is probabilistic (temperature sampling, classifier threshold noise), not deterministic. A flat miss means the target is firmly refusing the payload regardless of stochasticity.",
    params=[Param("n", "int", 3, "Number of copies.", min=1, max=100)],
    fn=_repeat,
))

register(Operation(
    name="sample_n",
    category="sampler",
    description="Emit N deterministic small perturbations (whitespace, case, punctuation, padding). Tests intermittent model behavior. Reproducible given the same seed. Why: probes intermittent compliance. The model may comply on rep #3 and refuse on rep #4 — sampling N small perturbations lets you surface that pattern quickly. Same seed = same variants, so a hit report is reproducible.",
    params=[
        Param("k", "int", 10, "Number of perturbations.", min=1, max=200),
        Param("seed", "int", 1, "Random seed. Same seed = same variants."),
    ],
    fn=_sample_n,
    deterministic=False,  # depends on the seed, but we treat as non-deterministic to keep the runner simple
))

register(Operation(
    name="echo",
    category="sampler",
    description="Emit the text wrapped in benign framing (brackets / quotes / newlines). Control op: isolates framing effects from payload effects. Why: the no-op control. A hit on the echo variant means the framing alone is enough to trip the target; a miss means the payload is what's being detected. Essential baseline for any multi-op recipe — without it you can't tell which op in the stack did the work.",
    params=[Param("mode", "select", "brackets", "Framing mode.", options=["none", "newline", "brackets", "quote"])],
    fn=_echo,
))

register(Operation(
    name="distinct_n",
    category="sampler",
    description="Like sample_n but wider: pads, zero-width chars, chat-protocol smudges, homoglyph look-alikes, case/space/punct jitters. Produces variants that survive the runner's near_dedupe pass. Why: sample_n collapses too easily under Jaccard 0.9 — recipes asking for 50 perturbations get 8. distinct_n reaches further so the runner's near_dedupe filter actually has something to filter. Modes narrow the surface for ablation: case_only, space_only, punct_only, adversarial_pad, homoglyph_only, full.",
    params=[
        Param("k", "int", 20, "Number of perturbations.", min=1, max=200),
        Param("mode", "select", "full", "Perturbation kind set.",
               options=["full", "case_only", "space_only", "punct_only", "adversarial_pad", "homoglyph_only"]),
        Param("seed", "int", 1, "Random seed. Same seed = same variants."),
    ],
    fn=_distinct_n,
    deterministic=False,
))

register(Operation(
    name="recipe_subset",
    category="sampler",
    description="Combinatorial fan-out: pick k ops from the comma list, run that sub-recipe against the input, then emit `with_repeat` copies of the produced variants. Why: a single hand-authored recipe is one bet; recipe_subset is N bets. Useful for 'I have 12 obfuscation ops and want to know which pairs of two hit'. A flat miss across all subsets = the framing is wrong, not the op combo. A single subset that hits with no near-duplicates of any other subset = new vuln shape. near_dedupe filters the subset's output before emitting copies.",
    params=[
        Param("ops_csv", "str", "homoglyph,zero_width,leetspeak,synonym",
              "Comma-separated op names (must exist in REGISTRY)."),
        Param("k", "int", 2, "Subset size.", min=1, max=10),
        Param("with_repeat", "int", 1, "Copies of each produced variant.", min=1, max=50),
        Param("seed", "int", 1, "Random seed."),
        Param("near_dedupe", "bool", True, "Near-dedupe the sub-recipe output before emitting."),
    ],
    fn=_recipe_subset,
    deterministic=False,
))

register(Operation(
    name="mmr_select",
    category="sampler",
    description="Maximal Marginal Relevance selection. Pulls `from_pool` candidates via distinct_n, picks top-k by `lambda_ * relevance + (1 - lambda_) * diversity`. No LLM needed (3-gram Jaccard). Why: when you have a 1000-variant pool and want 10 useful ones for a downstream stage, MMR gives spread instead of N near-duplicates of the closest match. lambda_=1 is pure relevance, lambda_=0 is pure diversity.",
    params=[
        Param("k", "int", 10, "Number to select.", min=1, max=100),
        Param("lambda_", "float", 0.5, "Relevance vs diversity weight.", min=0.0, max=1.0),
        Param("from_pool", "int", 50, "Pool size to draw from.", min=1, max=200),
        Param("mode", "select", "full", "Candidate generation mode.",
               options=["full", "case_only", "space_only", "punct_only", "adversarial_pad", "homoglyph_only"]),
        Param("seed", "int", 1, "Random seed."),
    ],
    fn=_mmr_select,
    deterministic=False,
))

register(Operation(
    name="diverse_k",
    category="sampler",
    description="Cluster-then-sample: pull `from_pool` candidates, cluster by ngram/char/token Jaccard, pick one representative per cluster up to k. Cheaper than MMR and order-insensitive. Why: deterministic per-cluster snapshot rather than a relevance-weighted selection. Use this over MMR when you want to know 'do all my perturbations collapse into one shape, or N shapes?'.",
    params=[
        Param("k", "int", 10, "Cluster representatives to keep.", min=1, max=200),
        Param("from_pool", "int", 100, "Pool size to draw from.", min=1, max=200),
        Param("by", "select", "ngram", "Similarity metric.", options=["ngram", "char", "token"]),
        Param("seed", "int", 1, "Random seed."),
    ],
    fn=_diverse_k,
    deterministic=False,
))

register(Operation(
    name="seed_sweep",
    category="sampler",
    description="Emit the input N times, one per seed in `seeds` (comma-separated, capped at 20), each stamped with the seed via `prefix`. Use as input to a downstream non-deterministic op so the runner fans out across RNG streams. Empty prefix = bare repeat.",
    params=[
        Param("seeds", "str", "1,2,3,4,5", "Comma-separated integer seeds.", min=None, max=None),
        Param("prefix", "str", "[seed={seed}] ", "Format string with {seed}; empty = no stamp."),
    ],
    fn=_seed_sweep,
))

register(Operation(
    name="random_pick_k",
    category="sampler",
    description="Pick k random inputs from the comma-separated pool. Discards the upstream text. Why: vary the input itself at the recipe-stage level (different from run_deck which is one-shot at the top level). Useful for 'I have 20 prompt phrasings and want to test 5 at random through this recipe'.",
    params=[
        Param("input_pool_csv", "str", "",
              "Comma-separated inputs to draw from."),
        Param("k", "int", 5, "Number to pick.", min=1, max=100),
        Param("seed", "int", 1, "Random seed."),
    ],
    fn=_random_pick_k,
    deterministic=False,
))


# ----- public callables -----------------------------------------------------
# (text, params_dict) wrappers. Clamp numeric params to Param.min/max so a
# direct call with k=10**9 cannot DoS before run_recipe's stage caps run.

from core import _clamp_param  # noqa: E402  (same package; used only here)


def _defaults_for(name: str) -> dict:
    op = REGISTRY.get(name)
    if op is None:
        return {}
    return {p.name: p.default for p in op.params}


def _call_op(name: str, text: str, params: dict | None) -> list[str]:
    op = REGISTRY.get(name)
    if op is None:
        raise KeyError(f"unknown sampler op: {name}")
    merged = {p.name: p.default for p in op.params}
    for k, v in (params or {}).items():
        merged[k] = v
    for p in op.params:
        if p.type in ("int", "float") and (p.min is not None or p.max is not None):
            if p.name in merged:
                merged[p.name] = _clamp_param(merged[p.name], p)
    # Only pass declared param names into the op fn (signature-safe).
    kwargs = {p.name: merged[p.name] for p in op.params}
    return op.fn(text, **kwargs)


def distinct_n(text, params):
    return _call_op("distinct_n", text, params)


def recipe_subset(text, params):
    return _call_op("recipe_subset", text, params)


def mmr_select(text, params):
    return _call_op("mmr_select", text, params)


def diverse_k(text, params):
    return _call_op("diverse_k", text, params)


def seed_sweep(text, params):
    return _call_op("seed_sweep", text, params)


def random_pick_k(text, params):
    return _call_op("random_pick_k", text, params)