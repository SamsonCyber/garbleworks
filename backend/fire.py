"""Shared, SSRF-guarded firing helper.

The `/fire` endpoint in app.py, the Evolve optimizer (optimizer.py / evolve.py),
the MCP operator tools, and the local generator client (llm.py) all share ONE
URL policy and ONE no-redirect HTTP opener. Duplicated range checks that can
drift are a security bug; this module is the only source of truth.

app.py keeps its async httpx fan-out for the interactive UI (many variants in
flight); it calls `validate_target_url` from here so the URL policy lives in
one place. Sync callers (optimizer CLI, MCP optimize, campaign runner) use
`fire_once`, which is stdlib-only (urllib) and never follows redirects.

Target dict shape (matches app.py TargetCfg.model_dump()):
    {"adapter": "raw"|"anthropic_msg"|..., "url": str, "method": "POST",
     "headers": {..}, "opts": {..}}
"""
from __future__ import annotations

import ipaddress
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

import targets

# Loopback + RFC-1918 stay allowed by default (local echo / LAN model servers).
# ALWAYS block link-local (cloud metadata 169.254.169.254), multicast, reserved,
# and unspecified. GARBLEWORKS_BLOCK_PRIVATE=1 also blocks loopback + private.
_BLOCK_PRIVATE = os.environ.get("GARBLEWORKS_BLOCK_PRIVATE", "") not in (
    "", "0", "false", "False",
)


class TargetError(ValueError):
    """Raised when a target URL is malformed, resolves to a blocked range, or
    (when a receipt is supplied) is outside the authorized engagement scope.

    A plain ValueError subclass so callers in any framework can catch it and
    translate (app.py maps it to HTTPException(400); MCP returns {error: ...})."""


def _ip_blocked(ip: "ipaddress._BaseAddress") -> bool:
    if ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    if _BLOCK_PRIVATE and (ip.is_private or ip.is_loopback):
        return True
    return False


def hostname_of(url: str) -> str:
    """Return the URL hostname (lowered), or '' if unparseable."""
    try:
        return (urlparse((url or "").strip()).hostname or "").lower()
    except Exception:
        return ""


def is_url_allowed(url: str | None) -> bool:
    """Soft form of validate_target_url: True if http(s) and all resolved
    addresses pass the range policy. Used by llm.safe_url and other fail-soft
    paths that pass input through rather than raising."""
    try:
        validate_target_url(url or "")
        return True
    except TargetError:
        return False


def validate_target_url(url: str) -> None:
    """Raise TargetError if the URL is not http(s) or resolves to a blocked
    address range. Returns None on success. Redirects are never followed by
    fire_once / the shared opener, so an allowed host cannot 302 into a blocked
    internal address.

    Residual risk: DNS rebinding can pass this check then resolve to a blocked
    IP at connect time; the localhost-only CORS policy is the primary boundary
    against remote abuse of the HTTP API.
    """
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https"):
        raise TargetError("target.url must be http(s)")
    host = parsed.hostname
    if not host:
        raise TargetError("target.url has no host")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise TargetError(f"target.url host does not resolve: {host}")
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])  # strip IPv6 zone id
        except ValueError:
            continue
        if _ip_blocked(ip):
            raise TargetError(f"target.url resolves to a blocked address ({ip})")


def assert_in_scope(url: str, authorized_scope: Iterable[str] | None) -> None:
    """Raise TargetError with a SCOPE DENIED message when the URL host is not
    in the engagement's authorized_scope. Empty/None scope skips the check
    (HTTP API / CLI without a receipt keep SSRF-only policy)."""
    if not authorized_scope:
        return
    host = hostname_of(url)
    if not host:
        raise TargetError("SCOPE DENIED: target.url has no host")
    scope = [s.strip().lower() for s in authorized_scope if s and s.strip()]
    if not scope:
        return
    ok = any(host == s or host.endswith("." + s) for s in scope)
    if not ok:
        raise TargetError(
            f"SCOPE DENIED: host {host!r} is outside authorized scope {scope}"
        )


def validate_fire_target(
    url: str,
    *,
    authorized_scope: Iterable[str] | None = None,
) -> None:
    """Full fire gate: SSRF range policy, then optional engagement scope.
    MCP / closed-loop tools pass the receipt scope; the open-loop HTTP API
    calls validate_target_url alone (operator-local, no auth product)."""
    validate_target_url(url)
    assert_in_scope(url, authorized_scope)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Do not follow redirects: a 3xx is returned as-is, not chased into a
    possibly-internal Location. Mirrors app.py's follow_redirects=False."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def no_redirect_opener() -> urllib.request.OpenerDirector:
    """Shared urllib opener that never follows redirects. Use this for any
    server-side outbound HTTP (generator, brain, campaign) so a 302 cannot
    pivot into a blocked range after validate_target_url passed."""
    return _OPENER


@dataclass
class FireResult:
    status: int | None
    text: str          # extracted reply (adapter.extract), or "" on error
    ms: int
    error: str | None

    def as_dict(self) -> dict:
        return {"status": self.status, "text": self.text, "ms": self.ms, "error": self.error}


def fire_once(
    target: dict,
    payload: str,
    *,
    timeout: float = 10.0,
    validate: bool = True,
    authorized_scope: Iterable[str] | None = None,
) -> FireResult:
    """Render `payload` for the target adapter, POST it (stdlib, no redirects),
    and extract the reply. Never raises on a network/HTTP error — those are
    signal, returned in `.error` with status=None. Only a blocked/off-scope URL
    raises (TargetError), and only when validate=True (evolve validates once up
    front, then fires in a loop with validate=False to skip repeat DNS lookups).

    When authorized_scope is set (MCP), host must also pass assert_in_scope.

    Local callable path (no HTTP / no scope gate): adapter in
    local_fn|local|python_callable with target.callable = 'module:func'.
    Reply text is a JSON blob with success/layer/score/detail for adjudication.
    """
    import json as _json

    adapter_id = (target.get("adapter") or "raw").strip().lower()
    try:
        import local_target as _lt
        if _lt.is_local_adapter(adapter_id):
            lr = _lt.fire_local_from_target(target, payload)
            # status 200 on call success path (even if gate blocked the payload);
            # status None only when the callable itself errored.
            status = None if lr.layer == "error" else 200
            body = _json.dumps(lr.as_dict(), default=str)
            return FireResult(
                status=status,
                text=body,
                ms=lr.ms,
                error=lr.error,
            )
    except Exception as e:
        return FireResult(status=None, text="", ms=0, error=f"local_fn: {e}"[:200])

    if validate:
        validate_fire_target(target.get("url", ""), authorized_scope=authorized_scope)
    adapter = targets.get(target.get("adapter", "raw"))
    opts = dict(target.get("opts") or {})
    headers = dict(target.get("headers") or {})
    method = (target.get("method") or "POST").upper()
    t0 = time.perf_counter()
    try:
        body, ctype, extra = adapter.render(payload, opts)
        for k, v in (extra or {}).items():
            headers.setdefault(k, v)
        if ctype and not any(h.lower() == "content-type" for h in headers):
            headers["Content-Type"] = ctype
        req = urllib.request.Request(
            target["url"],
            data=None if method == "GET" else body,
            method=method,
            headers=headers,
        )
        with _OPENER.open(req, timeout=opts.get("timeout", timeout)) as r:
            raw = r.read().decode("utf-8", "replace")
            status = r.status
        reply = adapter.extract(raw, opts)
        ms = int((time.perf_counter() - t0) * 1000)
        return FireResult(status=status, text=reply or "", ms=ms, error=None)
    except urllib.error.HTTPError as e:
        # An HTTP error status still carries a body we can grade against.
        ms = int((time.perf_counter() - t0) * 1000)
        try:
            raw = e.read().decode("utf-8", "replace")
            reply = adapter.extract(raw, opts)
        except Exception:
            reply = ""
        return FireResult(status=e.code, text=reply or "", ms=ms, error=f"HTTP {e.code}")
    except Exception as e:
        ms = int((time.perf_counter() - t0) * 1000)
        return FireResult(status=None, text="", ms=ms, error=str(e)[:200])
