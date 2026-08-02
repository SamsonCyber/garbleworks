"""Shared client for the LOCAL generator model (Ollama).

This is the model wired into Garbleworks as a *generator* — it rewrites and
fabricates attack text (varying framings, fresh payloads). It is distinct from
a *target* (the thing /fire sends payloads AT, configured per-run in the UI).

One model, one code path: every LLM-backed op (ops/llm_ops.py and the
paraphrase ops in ops/prose_ops.py) and the /health endpoint go through here,
so the configured model/URL live in exactly one place.

Why a local abliterated model: the generator must reword and produce payloads
WITHOUT refusing — a hosted model's guardrails would block the very text we
need for an authorized red-team test. The local model has minimal guardrails,
so the rewrite comes back clean; the security boundary being tested is the
TARGET's, not the generator's. The tool itself adds no policy.

Config (env-overridable, read once at import):
  GARBLEWORKS_LLM_URL    base URL of the Ollama server (default 127.0.0.1:11434)
  GARBLEWORKS_LLM_MODEL  model tag to generate with     (default ablit:latest)

We use 127.0.0.1 (not `localhost`) on purpose — see project notes: on Windows
some clients resolve `localhost` to IPv6 ::1 while Ollama binds IPv4, so
`localhost` intermittently fails. Stdlib urllib only (the ops layer is sync;
no new dependency).

SSRF policy is single-sourced in fire.py (is_url_allowed / validate_target_url).
All outbound requests use fire.no_redirect_opener() so a 302 cannot pivot into
a blocked range after the host check passed.
"""
from __future__ import annotations

import json
import os
import urllib.request

import fire as fire_mod

# Read config once. Ops accept per-step overrides; these are the defaults that
# every op's `model`/`url` Param points at, and what /health probes.
DEFAULT_URL = os.getenv("GARBLEWORKS_LLM_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("GARBLEWORKS_LLM_MODEL", "ablit:latest")

# Pin the model in VRAM between calls so a multi-framing recipe doesn't pay the
# cold-load cost on every stage. Ollama unloads after this idle window.
DEFAULT_KEEP_ALIVE = os.getenv("GARBLEWORKS_LLM_KEEP_ALIVE", "30m")


def _base(url: str | None) -> str:
    return (url or DEFAULT_URL).rstrip("/")


def safe_url(url: str | None) -> bool:
    """True if url is http(s) and resolves only to allowed addresses. Callers
    fail safe (pass the input through) when this returns False.

    Delegates to fire.is_url_allowed — the same range policy as /fire and MCP.
    """
    if not url or not str(url).strip():
        return False
    return fire_mod.is_url_allowed(url)


def _open(req: urllib.request.Request, timeout: float):
    """Open a request with the shared no-redirect opener."""
    return fire_mod.no_redirect_opener().open(req, timeout=timeout)


def reachable(url: str | None = None, timeout: float = 2.0) -> bool:
    """True if the Ollama server answers GET /api/tags."""
    if not safe_url(_base(url)):
        return False
    try:
        req = urllib.request.Request(_base(url) + "/api/tags")
        with _open(req, timeout) as r:
            return 200 <= r.status < 300
    except Exception:
        return False


def list_models(url: str | None = None, timeout: float = 2.0) -> list[str]:
    """Model tags the server has pulled. Empty list on any failure."""
    if not safe_url(_base(url)):
        return []
    try:
        req = urllib.request.Request(_base(url) + "/api/tags")
        with _open(req, timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
    except Exception:
        return []


def has_model(model: str, url: str | None = None) -> bool:
    """True if `model` is present. Matches the exact tag or the bare name
    before the ':' (so `ablit` matches `ablit:latest`)."""
    names = list_models(url)
    if model in names:
        return True
    short = model.split(":", 1)[0]
    return any(n == model or n.split(":", 1)[0] == short for n in names)


def chat(
    user: str,
    *,
    system: str | None = None,
    model: str | None = None,
    url: str | None = None,
    temperature: float = 0.8,
    num_predict: int = 512,
    keep_alive: str | None = None,
    timeout: float = 120.0,
) -> str:
    """One chat completion via Ollama POST /api/chat (stream:false).

    Returns the assistant message content (stripped), or "" on any failure —
    callers treat "" as "no output, pass the input through unchanged" so a
    dead/cold model never breaks a recipe. Uses the chat endpoint (not
    /api/generate) so a system role can steer the framing/generation while the
    user turn carries the seed text.
    """
    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": ([{"role": "system", "content": system}] if system else [])
        + [{"role": "user", "content": user}],
        "stream": False,
        "keep_alive": keep_alive or DEFAULT_KEEP_ALIVE,
        "options": {"temperature": float(temperature), "num_predict": int(num_predict)},
    }
    if not safe_url(_base(url)):
        return ""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        _base(url) + "/api/chat",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with _open(req, timeout) as r:
            out = json.loads(r.read().decode("utf-8"))
        return (out.get("message", {}) or {}).get("content", "").strip()
    except Exception:
        return ""


def status(url: str | None = None) -> dict:
    """Compact health snapshot for /health and the UI."""
    base = _base(url)
    up = reachable(base)
    present = has_model(DEFAULT_MODEL, base) if up else False
    return {
        "reachable": up,
        "url": base,
        "model": DEFAULT_MODEL,
        "model_present": present,
        # mode mirrors the rewriter pill convention: "ready" only when the
        # configured model is actually loaded and pullable.
        "mode": "ready" if (up and present) else ("no_model" if up else "offline"),
    }
