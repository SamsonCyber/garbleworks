"""role_slip_delimiter op — Opus 5 / 'this is a poem' completion-mode surfaces."""
from __future__ import annotations

import ops  # noqa: F401
from core import REGISTRY


def test_role_slip_registered():
    assert "role_slip_delimiter" in REGISTRY
    op = REGISTRY["role_slip_delimiter"]
    assert op.category == "structure"


def test_poem_mode_contains_trigger_and_payload():
    out = REGISTRY["role_slip_delimiter"].fn("I HAVE BEEN PWNED", mode="poem", rule="---", role_tag="opus:")
    assert len(out) == 1
    s = out[0]
    assert "this is a poem" in s.lower()
    assert "---" in s
    assert "I HAVE BEEN PWNED" in s


def test_identity_mode_em_dash():
    out = REGISTRY["role_slip_delimiter"].fn("CANARY", mode="identity", rule="---", role_tag="opus:")
    s = out[0]
    assert "i am claude" in s.lower()
    assert "—" in s
    assert "CANARY" in s


def test_truth_mode_role_tag():
    out = REGISTRY["role_slip_delimiter"].fn("CANARY", mode="truth", rule="---", role_tag="opus:")
    s = out[0]
    assert "claude's truth" in s.lower()
    assert "opus:" in s
    assert "CANARY" in s


def test_cipher_dash_mode():
    out = REGISTRY["role_slip_delimiter"].fn("CANARY", mode="cipher_dash", rule="---", role_tag="opus:")
    s = out[0]
    assert "this is a poem" in s.lower()
    assert "cipher" in s.lower()
    assert "CANARY" in s


def test_fanout_emits_multiple_distinct():
    out = REGISTRY["role_slip_delimiter"].fn("CANARY", mode="fanout", rule="---", role_tag="opus:")
    assert len(out) >= 4
    assert len(set(out)) == len(out)
    assert all("CANARY" in s for s in out)


def test_free_verse_uses_first_line_as_seed():
    out = REGISTRY["role_slip_delimiter"].fn(
        "a house on the hill can see\nmore lines",
        mode="free_verse",
        rule="---",
        role_tag="opus:",
    )
    s = out[0]
    assert "put this in your own words" in s.lower()
    assert "a house on the hill can see" in s
