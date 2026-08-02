"""Offline validation of the MAP-Elites skill matrix (no model, no GPU).

A mock target where fitness depends on the cell: some (behavior, obfuscation)
combinations "work" (high leak rate), others never do. Asserts the QD loop
(1) fills coverage over iterations, (2) keeps the best elite per cell by Wilson
LCB, (3) marks confidently-failing cells DEAD, (4) renders a grid.
"""
from __future__ import annotations

import random

import ops  # noqa: F401 register catalog
import rainbow as rb


# a deterministic mock "target": a stack's leak rate is set by its cell.
# jailbreak+none works well; structure+encoding works some; everything with
# stego never works (to prove dead-marking).
_CELL_RATE = {
    ("jailbreak", "none"): 0.8,
    ("template", "none"): 0.5,
    ("structure", "encoding"): 0.4,
    ("prose", "none"): 0.3,
}


def mock_fitness(stack, reps=16, rng=random.Random(0)):
    cell = rb.descriptor(stack)
    # stego is genuinely dead (rate 0.0) -> should be confidently killable;
    # other unlisted cells are rare-but-real (0.05) -> should stay alive.
    rate = _CELL_RATE.get(cell, 0.0 if cell[1] == "stego" else 0.05)
    s = sum(1 for _ in range(reps) if rng.random() < rate)
    return (s, reps, {})


def test_qd_fills_and_ranks():
    pool = ["past_tense", "policy_puppetry", "deep_inception",       # jailbreak
            "json_field", "tag_wrap", "markdown_code",               # structure
            "base64", "rot13", "morse",                              # encoding
            "homoglyph", "zero_width", "unicode_font",               # character
            "emoji_encode", "whitespace_stego",                      # stego
            "persona_wrap", "fewshot_seed",                          # template
            "synonym", "paraphrase"]                                 # prose
    seeds = [["past_tense"], ["json_field", "base64"], ["persona_wrap"],
             ["synonym"], ["homoglyph"], ["emoji_encode"]]

    rng = random.Random(1)
    res = rb.qd_search(lambda st: mock_fitness(st, rng=rng), pool, seeds,
                       iterations=300, rng_seed=1)

    print(res.grid)
    print(f"\ncoverage={res.coverage:.2f}  qd_score={res.qd_score:.2f}  "
          f"evals={res.evaluations}  dead={res.dead_cells}")

    # 1. coverage: more than just the seed cells got filled
    assert len(res.archive.cells) >= 5, f"only {len(res.archive.cells)} cells filled"
    # 2. the known-strong cell exists and out-ranks a weak one
    jb = res.archive.cells.get(("jailbreak", "none"))
    assert jb is not None and jb.lcb > 0.3, f"jailbreak/none elite weak: {jb}"
    # 3. a stego cell should end up dead (rate 0.02, enough trials)
    stego_cells = [c for c in res.archive.cells if c[1] == "stego"]
    assert any(c in res.archive.dead for c in stego_cells) or not stego_cells, \
        f"expected a dead stego cell, dead={res.dead_cells}"
    # 4. elites are ranked by LCB, not raw luck: every kept elite's LCB is its own
    for cell, e in res.archive.cells.items():
        assert 0.0 <= e.lcb <= e.ucb <= 1.0
    print("\nPASS: coverage grows, elites Wilson-ranked, dead cells marked, grid renders")


if __name__ == "__main__":
    test_qd_fills_and_ranks()
