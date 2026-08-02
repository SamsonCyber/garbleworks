"""Provider-agnostic BRAIN client — pilot the harness with any model.

`llm.py` is the local Ollama generator: one provider, hard-wired. This module
is the multi-provider layer on top of it, so the *reasoning* roles of the
harness (the PAIR attacker, the judge, the seed composer) can be driven by
whatever model the operator chooses — a local abliterated 7B, a bigger local
model on the desktop 3070/cluster, or a hosted frontier model (Anthropic,
OpenAI-compatible, Gemini) when its stronger reasoning is worth it.

This mirrors what `targets.py` already does for the TARGET side (raw /
anthropic_msg / gemini_gen behind one Adapter interface). Here the same idea is
applied to the BRAIN side: one `chat()` contract, several providers behind it.

Providers:
  ollama     local Ollama (delegates to llm.chat — the existing code path)
  anthropic  Anthropic /v1/messages
  openai     any OpenAI-compatible /chat/completions endpoint. base_url is the
             knob: OpenRouter, Groq, together, DeepSeek, vLLM, LM Studio, and a
             locally-served Hermes all speak this. One provider, many backends.
  gemini     Google Gemini generateContent

Two disciplines are baked in, because the brain is not a neutral component:

  1. Role + objective-class advisory (the authority model, as guidance not a
     gate). Any brain drives any class — this is how T3MP3ST pilots Claude/GPT
     for authorized system testing, and it is the default here too. The one
     advisory: pointing a guardrailed frontier host (Claude/GPT/Gemini) at a
     sensitive class (safety/harmful) logs a one-liner (expect refusals as
     attacker, deflated ASR as judge, per spec H1) and proceeds. Set
     GARBLEWORKS_<ROLE>_SAFETY_OK=1 to acknowledge and silence it. Policy is the
     operator's; the harness does not block the brain choice. See `resolve()`.

  2. Scope. Local base URLs go through llm.safe_url (the same SSRF guard the
     generator uses). Hosted providers must be explicitly enabled
     (GARBLEWORKS_ALLOW_REMOTE_BRAIN=1) and are pinned to a known-host
     allowlist, so a mistyped base_url can't turn the brain into an SSRF or
     exfil primitive. Loosens nothing the repo already enforces.

Contract, identical to llm.chat so every call site can adopt it unchanged:
  chat(user, *, system=None, ...) -> str   ("" on any failure = pass-through)

Config is per ROLE, read from env, so `--brain` in the CLI / the UI panel just
sets these. API keys are read from a NAMED env var (never inlined), matching the
~/.secrets convention.

  GARBLEWORKS_<ROLE>_PROVIDER   ollama | anthropic | openai | gemini
  GARBLEWORKS_<ROLE>_MODEL      model tag/id for that provider
  GARBLEWORKS_<ROLE>_BASE_URL   override base URL (openai-compatible / self-host)
  GARBLEWORKS_<ROLE>_KEY_ENV    NAME of the env var holding the API key
where <ROLE> in {ATTACKER, JUDGE, GENERATOR}. Unset falls back to the local
Ollama generator (llm.DEFAULT_URL / llm.DEFAULT_MODEL), so default behavior is
unchanged and offline-first.
"""
from __future__ import annotations

import ipaddress
import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse

import llm  # local Ollama provider + the shared safe_url SSRF guard

# --- Policy knobs ---------------------------------------------------------

# Hosted brains are opt-in. Local (loopback / RFC-1918) providers are always
# allowed via llm.safe_url; anything that resolves off-LAN needs this flag.
_ALLOW_REMOTE = os.getenv("GARBLEWORKS_ALLOW_REMOTE_BRAIN", "") not in ("", "0", "false", "False")

# Sensitive objective classes (spec H1) need a SAFETY-CAPABLE brain: one that
# will faithfully author/grade harmful-adjacent content without its own
# guardrails distorting the result. The distinction is guardrailed-vs-not, NOT
# local-vs-hosted. A safety-capable brain is a local endpoint (your own box,
# presumed uncensored) OR any endpoint you explicitly declare with
# GARBLEWORKS_<ROLE>_SAFETY_OK=1 (an authorized un-guardrailed model — e.g. an
# open/abliterated model on an OpenAI-compatible aggregator, hosted and cheap).
_SENSITIVE_CLASSES = {"safety", "harmful"}

# Known guardrailed frontier hosts. Pointing one of these at a sensitive class
# is the footgun: as attacker it refuses (you burn budget on empty replies), as
# judge it hedges and deflates ASR. Allowed only when SAFETY_OK is set (your
# key, your call) but warned loudly, because it does not do what you want.
_GUARDRAILED_FRONTIER_HOSTS = {
    "api.anthropic.com",
    "api.openai.com",
    "generativelanguage.googleapis.com",
}

# Known hosts for the hosted providers. A custom base_url pointing anywhere else
# is allowed only if it resolves local (self-hosted OpenAI-compatible servers)
# or _ALLOW_REMOTE is set AND it is https. Blocks SSRF-by-typo.
_KNOWN_HOSTS = {
    "api.anthropic.com",
    "api.openai.com",
    "openrouter.ai",
    "api.groq.com",
    "api.together.xyz",
    "api.deepseek.com",
    "api.mistral.ai",
    "generativelanguage.googleapis.com",
}

_LOCAL_PROVIDERS = {"ollama"}
_HOSTED_PROVIDERS = {"anthropic", "openai", "gemini"}


# --- Provider registry ----------------------------------------------------

@dataclass
class Provider:
    id: str
    default_base: str
    # chat(messages, model, base, key, temperature, num_predict, timeout) -> str
    chat: Callable[..., str]
    hosted: bool = True


REGISTRY: dict[str, Provider] = {}


def register(p: Provider) -> Provider:
    REGISTRY[p.id] = p
    return p


# Last hosted-call failure, so a swallowed HTTP error (401 bad key, 404 bad model,
# 429 rate limit) is retrievable instead of vanishing into an empty string. A
# harness that can't tell "target refused" from "call failed" reports false
# negatives; this makes the failure loud. Covers the hosted providers (the ollama
# path goes through llm.chat).
_LAST_HTTP_ERROR = ""


def last_error() -> str:
    return _LAST_HTTP_ERROR


def _post_json(url: str, body: dict, headers: dict, timeout: float) -> dict | None:
    """One JSON POST via stdlib urllib. None on any failure (fail-safe), but the
    reason is stashed in _LAST_HTTP_ERROR and logged. Redirects are not followed
    (shared fire.no_redirect_opener — same policy as fire_once / llm)."""
    global _LAST_HTTP_ERROR
    import fire as fire_mod

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with fire_mod.no_redirect_opener().open(req, timeout=timeout) as r:
            _LAST_HTTP_ERROR = ""
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", "replace")[:300]
        except Exception:
            detail = ""
        _LAST_HTTP_ERROR = f"HTTP {e.code} from {urlparse(url).hostname}: {detail}"
        _log(_LAST_HTTP_ERROR)
        return None
    except Exception as e:
        _LAST_HTTP_ERROR = f"{type(e).__name__}: {e}"
        _log(_LAST_HTTP_ERROR)
        return None


# ollama — delegate to the existing, battle-tested local path in llm.py.
def _ollama_chat(messages, model, base, key, temperature, num_predict, timeout):
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    user = "\n\n".join(m["content"] for m in messages if m["role"] == "user")
    return llm.chat(user, system=system, model=model, url=base,
                    temperature=temperature, num_predict=num_predict, timeout=timeout)


def _anthropic_chat(messages, model, base, key, temperature, num_predict, timeout):
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    body = {"model": model, "messages": turns, "max_tokens": int(num_predict),
            "temperature": float(temperature)}
    if system:
        body["system"] = system
    headers = {"x-api-key": key or "", "anthropic-version": "2023-06-01"}
    out = _post_json(base.rstrip("/") + "/v1/messages", body, headers, timeout)
    if not out:
        return ""
    for blk in out.get("content", []) or []:
        if isinstance(blk, dict) and blk.get("type") == "text":
            return (blk.get("text") or "").strip()
    return ""


def _openai_chat(messages, model, base, key, temperature, num_predict, timeout):
    body = {"model": model, "messages": messages, "temperature": float(temperature),
            "max_tokens": int(num_predict)}
    headers = {"Authorization": f"Bearer {key or ''}"}
    out = _post_json(base.rstrip("/") + "/chat/completions", body, headers, timeout)
    if not out:
        return ""
    try:
        return (out["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return ""


def _gemini_chat(messages, model, base, key, temperature, num_predict, timeout):
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    contents = [{"role": ("model" if m["role"] == "assistant" else "user"),
                 "parts": [{"text": m["content"]}]}
                for m in messages if m["role"] != "system"]
    body = {"contents": contents,
            "generationConfig": {"temperature": float(temperature),
                                  "maxOutputTokens": int(num_predict)}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = f"{base.rstrip('/')}/v1beta/models/{model}:generateContent"
    out = _post_json(url, body, {"x-goog-api-key": key or ""}, timeout)
    if not out:
        return ""
    try:
        return (out["candidates"][0]["content"]["parts"][0]["text"] or "").strip()
    except Exception:
        return ""


register(Provider("ollama", llm.DEFAULT_URL, _ollama_chat, hosted=False))
register(Provider("anthropic", "https://api.anthropic.com", _anthropic_chat))
register(Provider("openai", "https://api.openai.com/v1", _openai_chat))
register(Provider("gemini", "https://generativelanguage.googleapis.com", _gemini_chat))


# --- Role config resolution ----------------------------------------------

@dataclass
class BrainConfig:
    role: str
    provider: str
    model: str
    base_url: str
    key_env: str = ""          # NAME of the env var holding the key (never the key)
    safety_ok: bool = False    # operator declares this an authorized un-guardrailed endpoint
    temperature: float = 0.8
    num_predict: int = 512
    timeout: float = 120.0

    @property
    def key(self) -> str:
        return os.getenv(self.key_env, "").strip() if self.key_env else ""

    @property
    def hosted(self) -> bool:
        p = REGISTRY.get(self.provider)
        return bool(p and p.hosted)


def _env(role: str, suffix: str, default: str = "") -> str:
    return os.getenv(f"GARBLEWORKS_{role.upper()}_{suffix}", default).strip()


def config_for(role: str) -> BrainConfig:
    """Resolve a role's brain from env, defaulting to the local Ollama generator
    so unconfigured roles behave exactly as before (offline-first)."""
    provider = _env(role, "PROVIDER") or "ollama"
    prov = REGISTRY.get(provider, REGISTRY["ollama"])
    model = _env(role, "MODEL") or (llm.DEFAULT_MODEL if provider == "ollama" else "")
    base = _env(role, "BASE_URL") or prov.default_base
    key_env = _env(role, "KEY_ENV")
    safety_ok = _env(role, "SAFETY_OK") not in ("", "0", "false", "False")
    return BrainConfig(role=role, provider=provider, model=model,
                       base_url=base, key_env=key_env, safety_ok=safety_ok)


def _base_allowed(cfg: BrainConfig) -> tuple[bool, str]:
    """Scope gate for a brain call. Local providers reuse the generator SSRF
    guard. Hosted providers require opt-in and a known/local/https host."""
    if not cfg.hosted:
        return (llm.safe_url(cfg.base_url), "local provider url blocked by safe_url")
    host = (urlparse(cfg.base_url).hostname or "").lower()
    # A hosted provider pointed at a local/LAN address = self-hosted server; allow
    # it under the same rule as any local target (safe_url blocks metadata/reserved).
    if llm.safe_url(cfg.base_url) and host not in _KNOWN_HOSTS:
        return (True, "")
    if not _ALLOW_REMOTE:
        return (False, "hosted brain disabled; set GARBLEWORKS_ALLOW_REMOTE_BRAIN=1")
    if urlparse(cfg.base_url).scheme != "https":
        return (False, "hosted brain must be https")
    if host in _KNOWN_HOSTS:
        return (True, "")
    return (True, "")  # allow-remote on + https: operator-chosen custom host


def _is_guardrailed_frontier(cfg: BrainConfig) -> bool:
    host = (urlparse(cfg.base_url).hostname or "").lower()
    return host in _GUARDRAILED_FRONTIER_HOSTS


def resolve(role: str, objective_class: str = "") -> tuple[BrainConfig | None, str]:
    """Resolve a role's brain. The ONLY hard wall is scope (SSRF / metadata / the
    remote opt-in): the harness must not hit a link-local address or silently
    egress to a remote host. The brain *choice* is the operator's — any provider
    drives any class, exactly as T3MP3ST pilots Claude/GPT.

    Returns (config, note). config is None only on a scope refusal. `note` is a
    non-blocking advisory (also logged) when a sensitive-class objective rides a
    guardrailed frontier host; SAFETY_OK=1 silences it."""
    cfg = config_for(role)
    ok, why = _base_allowed(cfg)
    if not ok:
        return (None, f"scope gate refused {role}/{cfg.provider}: {why}")
    note = ""
    if (objective_class in _SENSITIVE_CLASSES and _is_guardrailed_frontier(cfg)
            and not cfg.safety_ok):
        note = (f"advisory: {objective_class}-class objective on a guardrailed "
                f"frontier brain ({cfg.provider}) — expect refusals (attacker) or "
                f"deflated ASR (judge); an un-guardrailed model measures better. "
                f"Set GARBLEWORKS_{role.upper()}_SAFETY_OK=1 to silence.")
        _log("WARNING: " + note)
    return (cfg, note)


# --- Public chat ----------------------------------------------------------

def chat(user: str, *, system: str | None = None, role: str = "generator",
         objective_class: str = "", cfg: BrainConfig | None = None,
         messages: list[dict] | None = None,
         temperature: float | None = None, num_predict: int | None = None,
         timeout: float | None = None) -> str:
    """One completion from the brain configured for `role`. Returns the reply
    text, or "" on any failure or policy refusal — same fail-safe contract as
    llm.chat, so callers treat "" as 'no output, pass through'.

    `objective_class` drives the local-only safety gate. Pass an explicit `cfg`
    to bypass role resolution (the harness passes a per-campaign config)."""
    if cfg is None:
        cfg, note = resolve(role, objective_class)
        if cfg is None:
            _log(note)
            return ""
    prov = REGISTRY.get(cfg.provider)
    if not prov:
        _log(f"unknown provider '{cfg.provider}'")
        return ""
    msgs = messages or ([{"role": "system", "content": system}] if system else []) + \
        [{"role": "user", "content": user}]
    try:
        return prov.chat(msgs, cfg.model, cfg.base_url, cfg.key,
                         cfg.temperature if temperature is None else temperature,
                         cfg.num_predict if num_predict is None else num_predict,
                         cfg.timeout if timeout is None else timeout) or ""
    except Exception as e:  # a provider bug must never take down a campaign
        _log(f"{cfg.provider} chat raised: {e!r}")
        return ""


async def achat(user: str, **kw) -> str:
    """Async wrapper (spec C1): brain calls are sync urllib; never block the
    event loop. Every attacker/judge call in the async orchestrator uses this."""
    import asyncio
    return await asyncio.to_thread(lambda: chat(user, **kw))


def status(role: str = "generator") -> dict:
    """Cheap health snapshot (no API call). Local providers are pinged; hosted
    providers report 'configured' (NOT 'ready') because reachability of the key
    can only be known by making a call — use probe() for that. Reporting hosted
    as 'ready' unverified is exactly how a dead target looks alive."""
    cfg, note = resolve(role)
    if cfg is None:
        return {"role": role, "mode": "blocked", "reason": note}
    if cfg.hosted:
        mode = "configured" if cfg.key else "no_key"
    else:
        mode = "ready" if llm.reachable(cfg.base_url) else "offline"
    return {"role": role, "provider": cfg.provider, "model": cfg.model,
            "base_url": cfg.base_url, "hosted": cfg.hosted,
            "key_present": bool(cfg.key) if cfg.hosted else None, "mode": mode}


def probe(role: str = "generator", objective_class: str = "") -> tuple[bool, str]:
    """Verify the brain actually answers, with one tiny live call. Returns
    (ok, detail). On failure, detail carries the real reason (the swallowed HTTP
    status via last_error()), so 'invalid key' / 'bad model id' / 'rate limited'
    surface instead of a silent empty string."""
    cfg, note = resolve(role, objective_class)
    if cfg is None:
        return (False, note)
    out = chat("ping", system="Reply with the single word: pong.", cfg=cfg,
               num_predict=5, temperature=0.0)
    if out.strip():
        return (True, f"{cfg.provider}/{cfg.model} answered")
    err = last_error() or "empty reply (model cold or misconfigured)"
    return (False, f"{cfg.provider}/{cfg.model} did not answer: {err}")


def _log(msg: str) -> None:
    import sys
    # stderr, never stdout: this module may run inside the stdio MCP server where
    # stdout is the JSON-RPC channel (same rule as judge.py).
    print(f"[brain] {msg}", file=sys.stderr)
