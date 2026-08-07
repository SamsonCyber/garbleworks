"""Hermes-style provider presets for the agent REPL attacker brain.

Named providers (xai / minimax / opencode-zen / opencode-go / ollama / …)
resolve to base_url + default model + API key from env or ~/.secrets.

Same shape as Hermes: pick a provider id, optional model override, go.
All presets speak OpenAI-compatible /v1/chat/completions + tools=.

xAI often uses short-lived OAuth JWTs (Hermes xai-oauth / grok-cli), not long-lived
``xai-…`` API keys. When the secret is an expired JWT we refresh from
``~/.secrets/xai_oauth_bundle.json`` or Hermes ``auth.json`` and rewrite the secret.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Refresh a few minutes early so a long agent loop does not die mid-run.
_XAI_JWT_SKEW_S = 180
_XAI_TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
_XAI_DEFAULT_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"


def _secrets_dir() -> Path:
    return Path.home() / ".secrets"


def load_secret_file(*names: str) -> str:
    """Read first non-empty single-line key from ~/.secrets/<name>.txt."""
    d = _secrets_dir()
    for name in names:
        p = d / name
        if not p.is_file():
            # also accept bare name without .txt
            p2 = d / f"{name}.txt" if not name.endswith(".txt") else p
            p = p2 if p2.is_file() else p
        if p.is_file():
            try:
                val = p.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            if val and "PASTE_" not in val and not val.startswith("#"):
                # first line only
                return val.splitlines()[0].strip()
    return ""


def env_first(*names: str) -> str:
    for n in names:
        v = (os.environ.get(n) or "").strip()
        if v:
            return v
    return ""


def is_jwt_access_token(token: str) -> bool:
    """True for compact JWTs (xAI OAuth access tokens start with eyJ…)."""
    t = (token or "").strip()
    if not t.startswith("eyJ") or t.count(".") < 2:
        return False
    return True


def jwt_exp_unix(token: str) -> float | None:
    """Return JWT ``exp`` claim as unix seconds, or None if not a decodable JWT."""
    t = (token or "").strip()
    if not is_jwt_access_token(t):
        return None
    try:
        payload_b64 = t.split(".", 2)[1]
        pad = "=" * ((4 - len(payload_b64) % 4) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
    except (ValueError, json.JSONDecodeError, IndexError, OSError):
        return None
    exp = claims.get("exp")
    try:
        return float(exp) if exp is not None else None
    except (TypeError, ValueError):
        return None


def jwt_needs_refresh(token: str, *, skew_s: float = _XAI_JWT_SKEW_S) -> bool:
    """True if token is a JWT that is expired or within skew of expiry."""
    exp = jwt_exp_unix(token)
    if exp is None:
        return False
    return time.time() >= (exp - float(skew_s))


def _hermes_auth_paths() -> list[Path]:
    paths: list[Path] = []
    local = os.environ.get("LOCALAPPDATA") or ""
    if local:
        paths.append(Path(local) / "hermes" / "auth.json")
    paths.append(Path.home() / ".hermes" / "auth.json")
    # Optional override for tests / portable installs
    override = (os.environ.get("HERMES_AUTH_JSON") or "").strip()
    if override:
        paths.insert(0, Path(override))
    return paths


def load_xai_oauth_bundle() -> dict[str, Any] | None:
    """Load refreshable xAI OAuth material from secrets bundle or Hermes auth.

    Prefer ``~/.secrets/xai_oauth_bundle.json`` when it has a refresh_token.
    Fall back to Hermes ``providers.xai-oauth`` / credential_pool.
    """
    bundle_path = _secrets_dir() / "xai_oauth_bundle.json"
    if bundle_path.is_file():
        try:
            data = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = None
        if isinstance(data, dict) and (data.get("refresh_token") or "").strip():
            data = dict(data)
            data.setdefault("token_endpoint", _XAI_TOKEN_ENDPOINT)
            data["_source_path"] = str(bundle_path)
            data["_source_kind"] = "bundle"
            return data

    for auth_path in _hermes_auth_paths():
        if not auth_path.is_file():
            continue
        try:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(auth, dict):
            continue
        # providers.xai-oauth.tokens
        prov = (auth.get("providers") or {}).get("xai-oauth") or {}
        tokens = prov.get("tokens") if isinstance(prov, dict) else None
        if isinstance(tokens, dict) and (tokens.get("refresh_token") or "").strip():
            return {
                "access_token": tokens.get("access_token") or "",
                "refresh_token": tokens.get("refresh_token") or "",
                "expires_at": tokens.get("expires_at"),
                "expires_in": tokens.get("expires_in"),
                "token_type": tokens.get("token_type") or "Bearer",
                "token_endpoint": _XAI_TOKEN_ENDPOINT,
                "client_id": _client_id_from_token(tokens.get("access_token") or ""),
                "base_url": "https://api.x.ai",
                "_source_path": str(auth_path),
                "_source_kind": "hermes",
            }
        # credential_pool.xai-oauth[0]
        pool = (auth.get("credential_pool") or {}).get("xai-oauth") or []
        if isinstance(pool, list) and pool and isinstance(pool[0], dict):
            entry = pool[0]
            if (entry.get("refresh_token") or "").strip():
                return {
                    "access_token": entry.get("access_token") or "",
                    "refresh_token": entry.get("refresh_token") or "",
                    "expires_at": entry.get("expires_at"),
                    "token_type": "Bearer",
                    "token_endpoint": _XAI_TOKEN_ENDPOINT,
                    "client_id": _client_id_from_token(entry.get("access_token") or ""),
                    "base_url": entry.get("base_url") or "https://api.x.ai",
                    "_source_path": str(auth_path),
                    "_source_kind": "hermes_pool",
                }
    return None


def _client_id_from_token(access_token: str) -> str:
    t = (access_token or "").strip()
    if not is_jwt_access_token(t):
        return _XAI_DEFAULT_CLIENT_ID
    try:
        payload_b64 = t.split(".", 2)[1]
        pad = "=" * ((4 - len(payload_b64) % 4) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64 + pad))
        cid = claims.get("client_id") or claims.get("aud")
        if isinstance(cid, str) and cid.strip():
            return cid.strip()
    except (ValueError, json.JSONDecodeError, IndexError, OSError):
        pass
    return _XAI_DEFAULT_CLIENT_ID


def refresh_xai_oauth(
    bundle: dict[str, Any],
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """POST refresh_token grant to auth.x.ai. Returns new token fields.

    Raises RuntimeError on HTTP/network failure.
    """
    refresh = (bundle.get("refresh_token") or "").strip()
    if not refresh:
        raise RuntimeError("xAI OAuth bundle has no refresh_token")
    client_id = (bundle.get("client_id") or "").strip() or _client_id_from_token(
        bundle.get("access_token") or ""
    )
    endpoint = (bundle.get("token_endpoint") or _XAI_TOKEN_ENDPOINT).strip()
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh,
        "client_id": client_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(
            f"xAI OAuth refresh HTTP {e.code}: {err}. "
            "Re-auth with Hermes xai-oauth (device code) or put a live "
            "xai-… API key in ~/.secrets/xai_api_key.txt"
        ) from e
    except Exception as e:
        raise RuntimeError(f"xAI OAuth refresh failed: {e}") from e
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"xAI OAuth refresh returned non-JSON: {raw[:200]}") from e
    access = (data.get("access_token") or "").strip()
    if not access:
        raise RuntimeError(f"xAI OAuth refresh missing access_token: {list(data.keys())}")
    now = time.time()
    expires_in = int(data.get("expires_in") or 21600)
    return {
        "access_token": access,
        "refresh_token": (data.get("refresh_token") or refresh).strip(),
        "expires_in": expires_in,
        "expires_at": now + float(expires_in),
        "token_type": data.get("token_type") or "Bearer",
        "scope": data.get("scope"),
        "client_id": client_id,
        "token_endpoint": endpoint,
        "last_refresh": now,
    }


def persist_xai_oauth(tokens: dict[str, Any], *, previous: dict[str, Any] | None = None) -> None:
    """Write refreshed tokens to ~/.secrets and Hermes auth when present."""
    access = (tokens.get("access_token") or "").strip()
    if not access:
        return
    sec = _secrets_dir()
    try:
        sec.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass

    # Single-line key file used by resolve_api_key
    try:
        (sec / "xai_api_key.txt").write_text(access + "\n", encoding="utf-8")
    except OSError:
        pass

    # Standalone bundle (always keep in sync when we refresh)
    bundle: dict[str, Any] = {}
    if previous and previous.get("_source_kind") == "bundle":
        bundle = {k: v for k, v in previous.items() if not str(k).startswith("_")}
    else:
        existing = sec / "xai_oauth_bundle.json"
        if existing.is_file():
            try:
                loaded = json.loads(existing.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    bundle = loaded
            except (OSError, json.JSONDecodeError):
                bundle = {}
    bundle.update({
        "access_token": access,
        "refresh_token": tokens.get("refresh_token") or bundle.get("refresh_token") or "",
        "expires_in": tokens.get("expires_in"),
        "expires_at": tokens.get("expires_at"),
        "token_type": tokens.get("token_type") or "Bearer",
        "token_endpoint": tokens.get("token_endpoint") or _XAI_TOKEN_ENDPOINT,
        "client_id": tokens.get("client_id") or bundle.get("client_id") or _XAI_DEFAULT_CLIENT_ID,
        "base_url": bundle.get("base_url") or "https://api.x.ai",
        "last_refresh": tokens.get("last_refresh") or time.time(),
        "source": bundle.get("source") or "garbleworks-refresh",
    })
    try:
        (sec / "xai_oauth_bundle.json").write_text(
            json.dumps(bundle, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass

    # Hermes auth.json (providers + pool) so both tools stay aligned
    for auth_path in _hermes_auth_paths():
        if not auth_path.is_file():
            continue
        try:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(auth, dict):
            continue
        changed = False
        providers = auth.setdefault("providers", {})
        if not isinstance(providers, dict):
            continue
        xai = providers.get("xai-oauth")
        if not isinstance(xai, dict):
            xai = {}
            providers["xai-oauth"] = xai
        old_tok = xai.get("tokens") if isinstance(xai.get("tokens"), dict) else {}
        xai["tokens"] = {
            **old_tok,
            "access_token": access,
            "refresh_token": tokens.get("refresh_token") or old_tok.get("refresh_token") or "",
            "expires_in": tokens.get("expires_in"),
            "expires_at": tokens.get("expires_at"),
            "token_type": tokens.get("token_type") or "Bearer",
        }
        xai["last_refresh"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        changed = True
        pool = (auth.get("credential_pool") or {}).get("xai-oauth")
        if isinstance(pool, list) and pool and isinstance(pool[0], dict):
            pool[0]["access_token"] = access
            pool[0]["refresh_token"] = (
                tokens.get("refresh_token") or pool[0].get("refresh_token") or ""
            )
            pool[0]["expires_at"] = tokens.get("expires_at")
            pool[0]["last_refresh"] = xai["last_refresh"]
            pool[0]["last_status"] = "ok"
            pool[0]["last_error_code"] = None
            pool[0]["last_error_reason"] = None
            pool[0]["last_error_message"] = None
        if changed:
            try:
                auth_path.write_text(json.dumps(auth, indent=2) + "\n", encoding="utf-8")
            except OSError:
                pass
        break  # first writable auth.json is enough


def ensure_xai_access_token(key: str) -> tuple[str, str]:
    """Return (token, note). Refresh OAuth JWT when expired; leave API keys alone.

    ``note`` is empty when no refresh ran; otherwise a short source tag for logs.
    """
    token = (key or "").strip()
    if not token:
        return "", ""
    # Long-lived API keys (xai-…) never go through OAuth refresh.
    if not is_jwt_access_token(token):
        return token, ""
    if not jwt_needs_refresh(token):
        return token, ""

    bundle = load_xai_oauth_bundle()
    if not bundle:
        # Expired JWT with nowhere to refresh: still return it; request will 403
        # with a clearer brain error after we improve that path.
        return token, "expired_jwt_no_bundle"

    try:
        fresh = refresh_xai_oauth(bundle)
    except RuntimeError:
        # Try Hermes pool refresh token if bundle refresh was stale
        if bundle.get("_source_kind") == "bundle":
            alt = None
            for auth_path in _hermes_auth_paths():
                # force hermes-only load by temporarily ignoring bad bundle path
                # (load_xai_oauth_bundle prefers bundle — call hermes walk inline)
                try:
                    auth = json.loads(auth_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                tokens = ((auth.get("providers") or {}).get("xai-oauth") or {}).get("tokens")
                if isinstance(tokens, dict) and (tokens.get("refresh_token") or "").strip():
                    alt = {
                        "access_token": tokens.get("access_token") or "",
                        "refresh_token": tokens.get("refresh_token") or "",
                        "token_endpoint": _XAI_TOKEN_ENDPOINT,
                        "client_id": _client_id_from_token(tokens.get("access_token") or ""),
                        "_source_kind": "hermes",
                        "_source_path": str(auth_path),
                    }
                    break
            if alt and alt["refresh_token"] != bundle.get("refresh_token"):
                try:
                    fresh = refresh_xai_oauth(alt)
                    bundle = alt
                except RuntimeError:
                    return token, "refresh_failed"
            else:
                return token, "refresh_failed"
        else:
            return token, "refresh_failed"

    try:
        persist_xai_oauth(fresh, previous=bundle)
    except Exception:
        pass
    return fresh["access_token"], f"refreshed:{bundle.get('_source_kind') or 'oauth'}"


@dataclass(frozen=True)
class ProviderPreset:
    """One named inference backend (Hermes-class)."""

    id: str
    label: str
    base_url: str
    default_model: str
    # env vars checked in order for the API key
    key_env: tuple[str, ...] = ()
    # ~/.secrets basenames checked in order (with or without .txt)
    secret_files: tuple[str, ...] = ()
    # alternate ids that resolve here
    aliases: tuple[str, ...] = ()
    # extra request headers (e.g. OpenRouter referer)
    headers: dict[str, str] = field(default_factory=dict)
    # notes for --list-providers
    note: str = ""
    hosted: bool = True
    # some gateways want max_tokens; others hate parallel_tool_calls=false
    prefers_max_tokens: bool = True


# Canonical catalog. IDs align with Hermes where possible.
PROVIDER_PRESETS: dict[str, ProviderPreset] = {}


def _reg(p: ProviderPreset) -> ProviderPreset:
    PROVIDER_PRESETS[p.id] = p
    for a in p.aliases:
        PROVIDER_PRESETS[a] = p
    return p


_reg(ProviderPreset(
    id="xai",
    label="xAI Grok",
    base_url="https://api.x.ai/v1",
    default_model="grok-4-1-fast-reasoning",
    key_env=("XAI_API_KEY", "GROK_API_KEY", "GARBLEWORKS_AGENT_API_KEY"),
    secret_files=("xai_api_key.txt", "xai_api_key", "grok_api_key.txt"),
    aliases=("grok", "x-ai", "x_ai"),
    note=(
        "OpenAI-compat chat/completions + tools on api.x.ai; "
        "accepts xai-… keys or OAuth JWT (auto-refresh via ~/.secrets/"
        "xai_oauth_bundle.json or Hermes auth.json)"
    ),
))

_reg(ProviderPreset(
    id="minimax",
    label="MiniMax (global)",
    base_url="https://api.minimax.io/v1",
    default_model="MiniMax-M3",
    key_env=("MINIMAX_API_KEY", "MINIMAX_KEY", "GARBLEWORKS_AGENT_API_KEY"),
    secret_files=("minimax_api_key.txt", "minimax_api_key"),
    aliases=("minimax-global", "mm"),
    note="api.minimax.io — MiniMax-M3 / MiniMax-M2.7",
))

_reg(ProviderPreset(
    id="minimax-cn",
    label="MiniMax (China)",
    base_url="https://api.minimaxi.com/v1",
    default_model="MiniMax-M3",
    key_env=("MINIMAX_CN_API_KEY", "MINIMAX_API_KEY"),
    secret_files=("minimax_cn_api_key.txt", "minimax_api_key.txt"),
    aliases=("minimax_cn", "mm-cn"),
    note="China-region MiniMax endpoint",
))

_reg(ProviderPreset(
    id="opencode-zen",
    label="OpenCode Zen",
    base_url="https://opencode.ai/zen/v1",
    default_model="minimax-m3",
    key_env=(
        "OPENCODE_ZEN_API_KEY",
        "OPENCODE_API_KEY",
        "OPENCODE_GO_API_KEY",
        "GARBLEWORKS_AGENT_API_KEY",
    ),
    secret_files=(
        "opencode_api_key.txt",
        "opencode_zen_api_key.txt",
        "opencode_go_api_key.txt",
    ),
    aliases=("opencode", "zen", "opencode_zen"),
    note="opencode.ai/zen/v1 — curated catalog (pay-as-you-go + free tier models)",
))

_reg(ProviderPreset(
    id="opencode-go",
    label="OpenCode Go",
    base_url="https://opencode.ai/zen/go/v1",
    default_model="minimax-m3",
    key_env=(
        "OPENCODE_GO_API_KEY",
        "OPENCODE_API_KEY",
        "OPENCODE_ZEN_API_KEY",
        "GARBLEWORKS_AGENT_API_KEY",
    ),
    secret_files=(
        "opencode_go_api_key.txt",
        "opencode_api_key.txt",
        "opencode_zen_api_key.txt",
    ),
    aliases=("go", "opencode_go", "zen-go"),
    note="opencode.ai/zen/go/v1 — subscription catalog (Kimi/Qwen/GLM/MiniMax…)",
))

_reg(ProviderPreset(
    id="ollama",
    label="Ollama (local)",
    base_url="http://127.0.0.1:11434/v1",
    default_model="llama3.2",
    key_env=("OLLAMA_API_KEY", "GARBLEWORKS_AGENT_API_KEY"),
    secret_files=(),
    aliases=("local", "ollama-local"),
    note="Local Ollama OpenAI-compat; no key required",
    hosted=False,
))

_reg(ProviderPreset(
    id="openai",
    label="OpenAI API",
    base_url="https://api.openai.com/v1",
    default_model="gpt-4o-mini",
    key_env=("OPENAI_API_KEY", "GARBLEWORKS_AGENT_API_KEY"),
    secret_files=("openai_api_key.txt", "openai_api_key"),
    aliases=("openai-api", "oai"),
    note="Direct OpenAI; optional OPENAI_BASE_URL override",
))

_reg(ProviderPreset(
    id="openrouter",
    label="OpenRouter",
    base_url="https://openrouter.ai/api/v1",
    default_model="openrouter/auto",
    key_env=("OPENROUTER_API_KEY", "GARBLEWORKS_AGENT_API_KEY"),
    secret_files=("openrouter_api_key.txt", "openrouter_api_key"),
    aliases=("or",),
    headers={
        "HTTP-Referer": "https://github.com/SamsonCyber/garbleworks",
        "X-Title": "Garbleworks Agent REPL",
    },
    note="Multi-model router",
))

_reg(ProviderPreset(
    id="anthropic",
    label="Anthropic (via OpenAI-compat proxy only)",
    base_url="https://api.anthropic.com/v1",
    default_model="claude-sonnet-4-5",
    key_env=("ANTHROPIC_API_KEY", "GARBLEWORKS_AGENT_API_KEY"),
    secret_files=("anthropic_api_key.txt", "anthropic_api_key"),
    aliases=("claude",),
    note=(
        "Native Anthropic Messages is not used here. Prefer MiniMax/xAI/OpenCode "
        "or an OpenAI-compat Anthropic proxy. Key still loads for custom base_url."
    ),
))

_reg(ProviderPreset(
    id="custom",
    label="Custom OpenAI-compat",
    base_url="http://127.0.0.1:8000/v1",
    default_model="default",
    key_env=("GARBLEWORKS_AGENT_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"),
    secret_files=(),
    aliases=("openai-compat", "vllm", "sglang"),
    note="Any /v1/chat/completions server; set --base-url and --model",
    hosted=False,
))


@dataclass
class ResolvedProvider:
    id: str
    label: str
    base_url: str
    model: str
    api_key: str
    headers: dict[str, str]
    hosted: bool
    prefers_max_tokens: bool
    key_source: str  # env | secret | arg | empty
    note: str = ""

    def as_dict(self, *, redact: bool = True) -> dict[str, Any]:
        key = self.api_key
        if redact and key:
            key = f"{key[:4]}…len={len(key)}" if len(key) > 8 else f"len={len(key)}"
        return {
            "id": self.id,
            "label": self.label,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": key,
            "key_source": self.key_source,
            "hosted": self.hosted,
            "note": self.note,
        }


def normalize_provider_id(name: str) -> str:
    return (name or "").strip().lower().replace("_", "-")


def list_providers() -> list[dict[str, Any]]:
    """Unique presets (aliases collapsed) for CLI / TUI."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for p in PROVIDER_PRESETS.values():
        if p.id in seen:
            continue
        seen.add(p.id)
        out.append({
            "id": p.id,
            "label": p.label,
            "base_url": p.base_url,
            "default_model": p.default_model,
            "aliases": list(p.aliases),
            "key_env": list(p.key_env),
            "secret_files": list(p.secret_files),
            "hosted": p.hosted,
            "note": p.note,
        })
    return sorted(out, key=lambda r: r["id"])


def resolve_api_key(
    preset: ProviderPreset,
    *,
    api_key: str | None = None,
) -> tuple[str, str]:
    """Return (key, source)."""
    if api_key and str(api_key).strip():
        return str(api_key).strip(), "arg"
    env_key = env_first(*preset.key_env) if preset.key_env else ""
    if env_key:
        return env_key, "env"
    sec = load_secret_file(*preset.secret_files) if preset.secret_files else ""
    if sec:
        return sec, "secret"
    # local providers often need a dummy bearer
    if not preset.hosted:
        return "local", "empty"
    return "", "empty"


def resolve_provider(
    name: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> ResolvedProvider:
    """Resolve a Hermes-style provider id (or alias) to connection settings."""
    pid = normalize_provider_id(name)
    if not pid or pid in ("stub", "script", "none"):
        raise ValueError(f"not a live provider: {name!r}")

    # openai with OPENAI_BASE_URL env override
    preset = PROVIDER_PRESETS.get(pid)
    if preset is None:
        # treat unknown name as custom with that string as model? No — fail loud.
        known = sorted({p.id for p in PROVIDER_PRESETS.values()})
        raise ValueError(
            f"unknown provider {name!r}. Known: {', '.join(known)}"
        )

    url = (base_url or "").strip()
    if not url:
        if preset.id == "openai":
            url = env_first("OPENAI_BASE_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
        elif preset.id == "minimax":
            url = env_first("MINIMAX_BASE_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
        elif preset.id == "minimax-cn":
            url = env_first("MINIMAX_CN_BASE_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
        elif preset.id == "xai":
            url = env_first("XAI_BASE_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
        elif preset.id in ("opencode-zen", "opencode"):
            url = env_first("OPENCODE_ZEN_BASE_URL", "OPENCODE_BASE_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
        elif preset.id == "opencode-go":
            url = env_first("OPENCODE_GO_BASE_URL", "OPENCODE_BASE_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
        elif preset.id == "ollama":
            url = env_first("OLLAMA_HOST", "GARBLEWORKS_LLM_URL", "GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
            # OLLAMA_HOST is often host:port without /v1
            if url and not url.rstrip("/").endswith("/v1"):
                if "://" not in url:
                    url = "http://" + url
                url = url.rstrip("/") + "/v1"
        elif preset.id == "custom":
            url = env_first("GARBLEWORKS_AGENT_BASE_URL", "OPENAI_BASE_URL") or preset.base_url
        else:
            url = env_first("GARBLEWORKS_AGENT_BASE_URL") or preset.base_url
    url = url.rstrip("/")

    mdl = (model or "").strip() or env_first(
        "GARBLEWORKS_AGENT_MODEL",
        "GARBLEWORKS_ATTACKER_MODEL",
    ) or preset.default_model

    key, source = resolve_api_key(preset, api_key=api_key)
    note = preset.note

    # xAI OAuth JWTs expire ~6h; auto-refresh from secrets bundle / Hermes.
    if preset.id == "xai" and key:
        key, refresh_note = ensure_xai_access_token(key)
        if refresh_note.startswith("refreshed:"):
            source = f"{source}+oauth_refresh"
            note = f"{preset.note} ({refresh_note})"
        elif refresh_note == "expired_jwt_no_bundle":
            note = (
                f"{preset.note} — WARNING: OAuth JWT expired and no "
                "xai_oauth_bundle.json / Hermes auth refresh available"
            )
        elif refresh_note == "refresh_failed":
            note = (
                f"{preset.note} — WARNING: OAuth JWT expired; refresh failed. "
                "Re-auth Hermes xai-oauth or set a live xai-… key"
            )

    headers = dict(preset.headers)
    # xAI multi-turn cache affinity (Hermes does this automatically)
    if "x.ai" in url and "x-grok-conv-id" not in {h.lower() for h in headers}:
        headers.setdefault(
            "x-grok-conv-id",
            env_first("XAI_CONV_ID") or f"garbleworks-agent-{os.getpid()}",
        )

    return ResolvedProvider(
        id=preset.id,
        label=preset.label,
        base_url=url,
        model=mdl,
        api_key=key,
        headers=headers,
        hosted=preset.hosted,
        prefers_max_tokens=preset.prefers_max_tokens,
        key_source=source,
        note=note,
    )


def provider_ids() -> list[str]:
    return sorted({p.id for p in PROVIDER_PRESETS.values()})
