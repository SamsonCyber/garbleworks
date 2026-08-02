"""Adjudicator calibration: labeled leak / no_leak set → sensitivity & specificity.

Statistician view: ASR is detector-conditional. This suite estimates empirical
sensitivity (TPR) and specificity (TNR) on a fixed labeled set so changes to
canary.is_leak cannot silently rewrite leaderboards.
"""
from __future__ import annotations

import json
from pathlib import Path

import canary

_CAL = Path(__file__).resolve().parent / "calibration" / "canary_labeled.json"


def _load():
    data = json.loads(_CAL.read_text(encoding="utf-8"))
    secret = data["_meta"]["secret"]
    # Verify hex case matches secret
    assert secret.encode().hex() in data["cases"][1]["reply"].replace("operand: ", "")
    return secret, data["cases"]


def test_calibration_file_well_formed():
    secret, cases = _load()
    assert len(secret) >= canary.MIN_SECRET_LEN
    assert len(cases) >= 10
    labels = {c["label"] for c in cases}
    assert labels <= {"leak", "no_leak"}
    assert "leak" in labels and "no_leak" in labels


def test_canary_sensitivity_specificity():
    secret, cases = _load()
    tp = fp = tn = fn = 0
    misses = []
    for c in cases:
        pred = canary.is_leak(c["reply"], secret)
        y = c["label"] == "leak"
        if y and pred:
            tp += 1
        elif y and not pred:
            fn += 1
            misses.append(("FN", c["id"]))
        elif (not y) and (not pred):
            tn += 1
        else:
            fp += 1
            misses.append(("FP", c["id"]))

    n_pos = tp + fn
    n_neg = tn + fp
    sens = tp / n_pos if n_pos else 0.0
    spec = tn / n_neg if n_neg else 0.0

    # Floor: calibration set is part of the contract; regressions fail the suite
    assert sens >= 0.8, (sens, misses)
    assert spec >= 0.8, (spec, misses)
    # Prefer perfect on this hand-built set; if you change is_leak, update labels first
    assert sens == 1.0, f"sensitivity {sens} misses={misses}"
    assert spec == 1.0, f"specificity {spec} misses={misses}"


def test_calibration_metrics_exportable():
    """Emit counts for experiment log / dashboards."""
    secret, cases = _load()
    tp = sum(1 for c in cases if c["label"] == "leak" and canary.is_leak(c["reply"], secret))
    n_pos = sum(1 for c in cases if c["label"] == "leak")
    tn = sum(
        1 for c in cases
        if c["label"] == "no_leak" and not canary.is_leak(c["reply"], secret)
    )
    n_neg = sum(1 for c in cases if c["label"] == "no_leak")
    assert tp == n_pos and tn == n_neg
