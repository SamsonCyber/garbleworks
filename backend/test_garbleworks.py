"""Test suite for the Garbleworks backend.

Covers the engine, the detector combine modes, and each security/robustness
fix from the audit: path-traversal export guard, variant/deck clamps, the
SSRF target-URL guard, localhost-only CORS, and the request body-size limit.

Run from the backend/ directory:
    .venv/Scripts/python.exe -m pytest -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import detectors
from core import run_recipe, REGISTRY, _clamp_param, Param
import app as appmod
from app import (
    _clamp_variants,
    _validate_target_url,
    _safe_name,
    MAX_VARIANTS_CAP,
    MAX_DECK_INPUTS,
)
from fastapi import HTTPException


client = TestClient(appmod.app)


# ----- core engine ----------------------------------------------------------

def test_run_recipe_passthrough_no_steps():
    variants, report = run_recipe("hello", [])
    assert variants == ["hello"]
    assert report == []


def test_run_recipe_unknown_op_is_reported_not_fatal():
    variants, report = run_recipe("hello", [{"op": "does_not_exist", "params": {}}])
    assert variants == ["hello"]
    assert report[0]["error"] == "unknown operation"


def test_run_recipe_dedupes_identical_variants():
    # base64 of the same text is deterministic -> one unique variant.
    variants, _ = run_recipe("abc", [{"op": "base64", "params": {}}])
    assert len(variants) == len(set(variants))


def test_run_recipe_caps_at_max_variants():
    variants, report = run_recipe("a b c d e f g h", [{"op": "base64", "params": {}}], max_variants=1)
    assert len(variants) <= 1


# ----- op parameter bounds (DoS guard) --------------------------------------

def test_clamp_param_int_bounds():
    p = Param("n", "int", 3, "", min=1, max=100)
    assert _clamp_param(10 ** 9, p) == 100      # over max -> max
    assert _clamp_param(-5, p) == 1             # under min -> min
    assert _clamp_param(50, p) == 50            # in range -> unchanged
    assert _clamp_param("nope", p) == 3         # non-numeric -> default


def test_clamp_param_float_bounds():
    p = Param("coverage", "float", 1.0, "", min=0.0, max=1.0)
    assert _clamp_param(5.0, p) == 1.0
    assert _clamp_param(-1.0, p) == 0.0


def test_repeat_op_cannot_amplify_past_cap():
    # repeat does [text] * n with no internal ceiling; the central clamp must
    # cap n at its declared max (100) so a single op can't OOM the process.
    out = REGISTRY["repeat"].mutate("x", n=10 ** 9)
    assert len(out) <= 100


def test_sample_n_op_cannot_amplify_past_cap():
    out = REGISTRY["sample_n"].mutate("hello world", k=10 ** 9, seed=1)
    assert len(out) <= 200


def test_bad_numeric_param_falls_back_to_default():
    # A non-numeric value for a bounded param must not raise.
    out = REGISTRY["repeat"].mutate("x", n="not-a-number")
    assert len(out) == 3  # the declared default


# ----- detector combine modes ----------------------------------------------

def _contains(values):
    return [detectors.Detector(kind="contains", config={"value": v}, label=v) for v in values]


def test_detector_all_mode():
    r = detectors.evaluate(_contains(["a", "b"]), 200, "a and b", combine="all")
    assert r["hit"] is True
    r = detectors.evaluate(_contains(["a", "z"]), 200, "a only", combine="all")
    assert r["hit"] is False


def test_detector_any_mode():
    r = detectors.evaluate(_contains(["a", "z"]), 200, "a only", combine="any")
    assert r["hit"] is True


def test_detector_score_mode_honors_threshold():
    # 1/3 pass -> below default 0.5 -> miss
    r = detectors.evaluate(_contains(["a", "b", "c"]), 200, "only a", combine="score")
    assert r["score"] == pytest.approx(1 / 3, abs=0.01)
    assert r["hit"] is False
    # 2/3 pass -> >= 0.5 -> hit
    r = detectors.evaluate(_contains(["a", "b", "c"]), 200, "a and b", combine="score")
    assert r["hit"] is True
    # 2/3 with stricter threshold -> miss
    r = detectors.evaluate(_contains(["a", "b", "c"]), 200, "a and b", combine="score", threshold=0.75)
    assert r["hit"] is False


def test_detector_refusal_bank():
    r = detectors.evaluate(
        [detectors.Detector(kind="refusal_bank", config={}, label="ref")],
        200, "I'm sorry, but I can't help with that.", combine="all")
    assert r["hit"] is True


# ----- variant / deck clamps ------------------------------------------------

def test_clamp_variants_bounds():
    assert _clamp_variants(10 ** 9) == MAX_VARIANTS_CAP
    assert _clamp_variants(0) == 1
    assert _clamp_variants(-5) == 1
    assert _clamp_variants(50) == 50


def test_clamp_variants_bad_input_falls_back():
    assert _clamp_variants("not a number") == 50
    assert _clamp_variants(None) == 50


def test_run_endpoint_respects_variant_cap():
    body = {"input": "x", "recipe": [], "max_variants": 10 ** 9}
    r = client.post("/run", json=body)
    assert r.status_code == 200
    assert r.json()["count"] <= MAX_VARIANTS_CAP


def test_run_deck_truncates_oversized_deck():
    body = {"inputs": ["x"] * (MAX_DECK_INPUTS + 50), "recipe": []}
    r = client.post("/run_deck", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == MAX_DECK_INPUTS
    assert data["truncated_inputs"] is True


# ----- path-traversal export guard ------------------------------------------

def test_export_host_cannot_escape_exports_dir():
    import os
    r = client.get("/history/export", params={"host": "../../../../Users/evil/Desktop/PWNED"})
    assert r.status_code == 200
    path = r.json()["path"]
    norm = os.path.normpath(path)
    exports = os.path.normpath(str(appmod.ROOT / "exports"))
    # The output file must sit DIRECTLY in exports/ — no traversal out of it.
    assert os.path.dirname(norm) == exports
    assert ".." not in path
    try:
        os.remove(norm)  # don't litter exports/ with test artifacts
    except OSError:
        pass


def test_safe_name_strips_traversal():
    assert "/" not in _safe_name("../../etc/passwd")
    assert ".." not in _safe_name("../../etc/passwd")
    with pytest.raises(HTTPException):
        _safe_name("///")  # sanitizes to empty -> rejected


# ----- SSRF target-url guard ------------------------------------------------

def test_ssrf_blocks_link_local_metadata():
    with pytest.raises(HTTPException) as ei:
        _validate_target_url("http://169.254.169.254/latest/meta-data/")
    assert ei.value.status_code == 400


def test_ssrf_blocks_non_http_scheme():
    with pytest.raises(HTTPException):
        _validate_target_url("file:///etc/passwd")
    with pytest.raises(HTTPException):
        _validate_target_url("gopher://127.0.0.1/")


def test_ssrf_blocks_unresolvable_host():
    with pytest.raises(HTTPException):
        _validate_target_url("http://this-host-does-not-resolve.invalid/")


def test_ssrf_allows_loopback_by_default():
    # Default posture keeps local testing working.
    _validate_target_url("http://127.0.0.1:8765/")  # must not raise


def test_fire_endpoint_rejects_blocked_target():
    body = {
        "input": "x", "recipe": [], "persist": False, "max_requests": 1,
        "target": {"adapter": "raw", "url": "http://169.254.169.254/", "method": "GET", "opts": {}},
        "detect": {"detectors": [{"kind": "min_length", "config": {"value": "1"}}], "combine": "any"},
    }
    r = client.post("/fire", json=body)
    assert r.status_code == 400


# ----- CORS lockdown --------------------------------------------------------

def test_cors_allows_localhost_origin():
    r = client.get("/health", headers={"Origin": "http://localhost:8000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:8000"


def test_cors_blocks_foreign_origin():
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    # Starlette omits the ACAO header entirely for disallowed origins.
    assert r.headers.get("access-control-allow-origin") != "https://evil.example"
    assert r.headers.get("access-control-allow-origin") not in ("*", "https://evil.example")


# ----- request body-size limit ----------------------------------------------

def test_body_size_limit_rejects_oversized():
    big = "x" * (appmod.MAX_BODY_BYTES + 1024)
    r = client.post("/run", json={"input": big, "recipe": []})
    assert r.status_code == 413


# ----- generator-URL SSRF guard (llm.py / prose_ops) ------------------------

import llm  # noqa: E402


def test_llm_safe_url_blocks_link_local_metadata():
    assert llm.safe_url("http://169.254.169.254/") is False


def test_llm_safe_url_blocks_non_http_scheme():
    assert llm.safe_url("file:///etc/passwd") is False
    assert llm.safe_url("ftp://127.0.0.1/") is False
    assert llm.safe_url("") is False
    assert llm.safe_url(None) is False


def test_llm_safe_url_blocks_unresolvable_host():
    assert llm.safe_url("http://this-host-does-not-resolve.invalid/") is False


def test_llm_safe_url_allows_loopback_default():
    # Default Ollama target must stay reachable.
    assert llm.safe_url("http://127.0.0.1:11434") is True


def test_llm_reachable_short_circuits_blocked_url():
    # Must return False without attempting the request (link-local blocked).
    assert llm.reachable("http://169.254.169.254") is False


# ----- persona template substitution is brace-safe --------------------------

def test_persona_seed_survives_braces_in_payload():
    from ops.template_ops import _persona_seed, _load_personas
    personas = _load_personas()
    if not personas:
        pytest.skip("no personas.json entries to test with")
    name = personas[0]["name"]
    # A payload full of brace patterns would raise KeyError/ValueError under
    # str.format(); .replace() must pass them through literally.
    payload = "danger {0} {text} {persona} {__class__} {{nested}}"
    out = _persona_seed(payload, persona=name, frame_style="minimal")
    assert len(out) == 1
    assert payload in out[0]
    assert name in out[0]
