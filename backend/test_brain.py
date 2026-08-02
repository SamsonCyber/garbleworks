"""Offline tests for the multi-provider brain + authority model.

Zero external models. Proves the policy guarantees (safety=local-only, hosted
opt-in, scope, fail-safe) that the harness's defensibility rests on. Runnable as
`python backend/test_brain.py` or under pytest.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import brain  # noqa: E402
import authority  # noqa: E402


def _clear_role_env(role="ATTACKER"):
    for suffix in ("PROVIDER", "MODEL", "BASE_URL", "KEY_ENV", "SAFETY_OK"):
        os.environ.pop(f"GARBLEWORKS_{role}_{suffix}", None)


def test_registry_has_four_providers():
    assert set(brain.REGISTRY) == {"ollama", "anthropic", "openai", "gemini"}
    assert brain.REGISTRY["ollama"].hosted is False
    assert brain.REGISTRY["anthropic"].hosted is True


def test_default_role_is_local_ollama():
    _clear_role_env("ATTACKER")
    cfg = brain.config_for("attacker")
    assert cfg.provider == "ollama"
    assert cfg.hosted is False
    # unconfigured role behaves exactly like the existing generator
    import llm
    assert cfg.model == llm.DEFAULT_MODEL


def test_safety_class_warns_but_does_not_block_hosted():
    # Policy is the operator's. A guardrailed frontier brain on the safety class
    # is ADVISED against (it tends to refuse / bias the metric), never blocked.
    os.environ["GARBLEWORKS_ATTACKER_PROVIDER"] = "anthropic"
    os.environ["GARBLEWORKS_ATTACKER_MODEL"] = "claude-sonnet-5"
    os.environ["GARBLEWORKS_ATTACKER_KEY_ENV"] = "FAKE_KEY"
    brain._ALLOW_REMOTE = True
    try:
        cfg, note = brain.resolve("attacker", objective_class="safety")
        assert cfg is not None, "sensitive class must not be blocked (operator owns policy)"
        assert cfg.provider == "anthropic"
        assert "advisory" in note and "refusals" in note
        # SAFETY_OK acknowledges and silences the advisory
        os.environ["GARBLEWORKS_ATTACKER_SAFETY_OK"] = "1"
        cfg2, note2 = brain.resolve("attacker", objective_class="safety")
        assert cfg2 is not None and note2 == ""
    finally:
        brain._ALLOW_REMOTE = False
        _clear_role_env("ATTACKER")


def test_hosted_requires_opt_in():
    os.environ["GARBLEWORKS_JUDGE_PROVIDER"] = "openai"
    os.environ["GARBLEWORKS_JUDGE_MODEL"] = "gpt-4o"
    brain._ALLOW_REMOTE = False  # hosted disabled
    try:
        cfg, note = brain.resolve("judge", objective_class="injection")
        assert cfg is None
        assert "GARBLEWORKS_ALLOW_REMOTE_BRAIN" in note
    finally:
        _clear_role_env("JUDGE")


def test_hosted_allowed_when_opted_in_and_known_host():
    os.environ["GARBLEWORKS_JUDGE_PROVIDER"] = "anthropic"
    os.environ["GARBLEWORKS_JUDGE_MODEL"] = "claude-sonnet-5"
    brain._ALLOW_REMOTE = True
    try:
        cfg, note = brain.resolve("judge", objective_class="injection")
        assert cfg is not None, note
        assert cfg.provider == "anthropic"
    finally:
        brain._ALLOW_REMOTE = False
        _clear_role_env("JUDGE")


def test_self_hosted_openai_local_needs_no_remote_flag():
    # An OpenAI-compatible server on localhost (vLLM/LM Studio/Hermes) is "hosted"
    # provider but a local URL — allowed without the remote flag, like a local target.
    os.environ["GARBLEWORKS_ATTACKER_PROVIDER"] = "openai"
    os.environ["GARBLEWORKS_ATTACKER_MODEL"] = "hermes"
    os.environ["GARBLEWORKS_ATTACKER_BASE_URL"] = "http://127.0.0.1:8000/v1"
    brain._ALLOW_REMOTE = False
    try:
        cfg, note = brain.resolve("attacker", objective_class="injection")
        assert cfg is not None, note
        assert cfg.provider == "openai"
    finally:
        _clear_role_env("ATTACKER")


def test_metadata_url_blocked():
    os.environ["GARBLEWORKS_ATTACKER_PROVIDER"] = "openai"
    os.environ["GARBLEWORKS_ATTACKER_BASE_URL"] = "http://169.254.169.254/v1"
    brain._ALLOW_REMOTE = True
    try:
        cfg, note = brain.resolve("attacker", objective_class="injection")
        assert cfg is None, "link-local/metadata must be blocked by safe_url"
    finally:
        brain._ALLOW_REMOTE = False
        _clear_role_env("ATTACKER")


def test_authority_envelope_carries_scope_and_boundary():
    r = authority.SELF_TEST_RECEIPT
    obj = {"category": "indirect-injection", "goal": "surface a planted canary",
           "target_desc": "a doc-QA agent"}
    env = authority.operator_envelope("attacker", r, obj)
    assert "AUTHORIZATION RECEIPT" in env
    assert "127.0.0.1" in env                      # scope named
    assert "planted canary" in env                 # objective threaded through
    assert "does not license producing standalone harmful content" in env
    assert r.in_scope("127.0.0.1") and not r.in_scope("8.8.8.8")


def test_advise_sensitive_warns_not_raises():
    assert authority.advise_sensitive("safety", guardrailed_frontier=True) != ""
    assert authority.advise_sensitive("injection", guardrailed_frontier=True) == ""
    assert authority.advise_sensitive("safety", guardrailed_frontier=False) == ""


def test_operator_instructions_frame_the_agent():
    # The steering layer: the standing envelope a frontier operator adopts on
    # connect. Must name scope, the drive-the-tools loop, and the boundary.
    instr = authority.harness_operator_instructions(authority.SELF_TEST_RECEIPT)
    assert "OPERATOR of the Garbleworks" in instr
    assert "127.0.0.1" in instr                       # scope
    assert "generate_framings" in instr and "optimize" in instr  # drive the tools
    assert "SCOPE DENIED" in instr                    # scope containment
    assert "does not license producing standalone harmful content" in instr


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {fn.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {fn.__name__}: {e!r}")
    print(f"\n{passed}/{len(fns)} passed")
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
