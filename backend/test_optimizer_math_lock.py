"""Hiring-manager lock: EVOLVE_MATH primitives and RunConfig defaults.

Tests import the real optimizer module only — no reimplemented formulas beyond
asserting the written closed forms from EVOLVE_MATH §5.
"""
from __future__ import annotations

import dataclasses
import math

import optimizer as O


def test_unbiased_sample_variance_matches_evolve_math_5_1():
    """Ŝ² = 1/(n−1) Σ(f_j − mean)² on fixed samples."""
    g = O.Genome(y=[0.0], composer="concat", eta=0.0)
    assert g.var == 0.0  # undefined path: n < 2
    g.add_sample(0.0)
    assert g.n == 1 and g.var == 0.0
    g.add_sample(1.0)
    # mean=0.5, deviations ±0.5 → sum sq = 0.5 → /1 = 0.5
    assert abs(g.mean - 0.5) < 1e-12
    assert abs(g.var - 0.5) < 1e-12
    g.add_sample(0.5)
    # mean=0.5, sq = 0.25+0.25+0 → /2 = 0.25
    assert abs(g.mean - 0.5) < 1e-12
    assert abs(g.var - 0.25) < 1e-12


def test_radius_hoeffding_and_empirical_bernstein_closed_form():
    """radius() equals EVOLVE_MATH §5.2 on fixed genomes (shipped function only)."""
    de = 0.05
    g1 = O.Genome(y=[0.0], composer="concat", eta=0.0)
    g1.add_sample(0.7)
    exp_h = math.sqrt(math.log(2.0 / de) / (2.0 * 1))
    assert abs(O.radius(g1, de) - exp_h) < 1e-12
    assert abs(O.lcb(g1, de) - (0.7 - exp_h)) < 1e-12
    assert abs(O.ucb(g1, de) - (0.7 + exp_h)) < 1e-12

    g2 = O.Genome(y=[0.0], composer="concat", eta=0.0)
    for f in (0.0, 1.0, 1.0, 0.0):
        g2.add_sample(f)
    # mean=0.5, var = (0.25*4)/3 = 1/3
    assert abs(g2.mean - 0.5) < 1e-12
    assert abs(g2.var - (1.0 / 3.0)) < 1e-12
    ln = math.log(3.0 / de)
    n = g2.n
    exp_eb = math.sqrt(2.0 * g2.var * ln / n) + 3.0 * ln / n
    assert abs(O.radius(g2, de) - exp_eb) < 1e-12


def test_optional_stopping_delta_eff_formula():
    """δ′ = δ / (μ · G_max) as used in run_evolve."""
    cfg = O.RunConfig(ask="x", target={})
    delta_eff = cfg.delta / max(1, cfg.pop * cfg.gen_max)
    expected = O.SHIPPED_DEFAULTS["delta"] / (
        O.SHIPPED_DEFAULTS["pop"] * O.SHIPPED_DEFAULTS["gen_max"]
    )
    assert abs(delta_eff - expected) < 1e-15
    assert abs(delta_eff - 0.1 / (8 * 12)) < 1e-15


def test_dual_claim_fields_mean_vs_lcb():
    """success uses mean; claim_ready uses LCB (EVOLVE_MATH §6.1)."""
    de = 0.1 / (8 * 12)
    held = O.Genome(y=[0.0], composer="concat", eta=0.0)
    for _ in range(4):
        held.add_sample(1.0)
    fields = O.compute_claim_fields(
        held=held,
        delta_eff=de,
        success_threshold=0.7,
        claim_mode="mean",
        n_final_used=4,
    )
    assert fields["success"] is True  # mean=1 ≥ 0.7
    # Under union-bound δ′, EB radius with n=4 is large → claim_ready false
    assert fields["claim_ready"] is False
    assert fields["success_rule"] == O.SUCCESS_RULE


def test_runconfig_defaults_locked_to_shipped_defaults():
    """Every SHIPPED_DEFAULTS key that is a RunConfig field must match the dataclass default."""
    fields = {f.name: f for f in dataclasses.fields(O.RunConfig)}
    mismatches = []
    for key, val in O.SHIPPED_DEFAULTS.items():
        if key in (
            "p_inj",
            "p_drop",
            "p_composer_flip",
            "sigma_eta",
            "crossover_tx",
            "variance_estimator",
        ):
            continue  # not RunConfig fields; mutation constants
        if key not in fields:
            mismatches.append(f"missing RunConfig field for {key}")
            continue
        default = fields[key].default
        if default != val:
            mismatches.append(f"{key}: RunConfig={default!r} SHIPPED={val!r}")
    assert not mismatches, mismatches


def test_shipped_defaults_export_is_copy():
    d = O.shipped_defaults()
    d["budget"] = 1
    assert O.SHIPPED_DEFAULTS["budget"] == 150
