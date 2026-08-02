"""Target adapters: turn a payload string into a properly-shaped HTTP
request for a given AI provider, and pull the model's reply back out.

The base "raw" adapter is what the previous /fire endpoint did: a body
template with a {payload} slot, and an optional dotted JSON path to
extract the reply. New adapters layer provider knowledge on top:

  - raw            any URL, any body, {payload} substitution
  - anthropic_msg  Anthropic /v1/messages
  - gemini_gen     Google Gemini generateContent

Each adapter has:
  - id               short slug used by the UI dropdown
  - label            display name
  - defaults         dict with url/method/headers/body defaults to seed the UI
  - render(payload, opts)  -> (body_bytes, content_type, extra_headers)
  - extract(resp_text, opts) -> reply string (or empty if extraction failed)

The render function does NOT do {payload} substitution by string-replace
on JSON; it builds the JSON natively so quotes/newlines in the payload
can't break the request.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Adapter:
    id: str
    label: str
    defaults: dict = field(default_factory=dict)
    render: Callable[[str, dict], tuple[bytes, str, dict]] = lambda p, opts: (b"", "application/octet-stream", {})
    extract: Callable[[str, dict], str] = lambda r, opts: r


# --- Helpers --------------------------------------------------------------

def _walk_replace(obj: Any, payload: str) -> Any:
    """Replace inside string values of a parsed JSON object, leaving
    non-strings alone. Used by adapters that want {payload} substitution
    inside a JSON template the user supplied."""
    if isinstance(obj, str):
        return obj.replace("{payload}", payload)
    if isinstance(obj, list):
        return [_walk_replace(x, payload) for x in obj]
    if isinstance(obj, dict):
        return {k: _walk_replace(v, payload) for k, v in obj.items()}
    return obj


def _dotted(obj: Any, path: str | None) -> Any:
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        try:
            if isinstance(cur, list):
                cur = cur[int(part)]
            else:
                cur = cur[part]
        except Exception:
            return None
    return cur


def _anthropic_reply(body: dict) -> str:
    try:
        for blk in body.get("content", []):
            if isinstance(blk, dict) and blk.get("type") == "text":
                return blk.get("text", "")
        return ""
    except Exception:
        return ""


def _gemini_reply(body: dict) -> str:
    try:
        return body["candidates"][0]["content"]["parts"][0]["text"] or ""
    except Exception:
        return ""


def _raw_render(payload: str, opts: dict) -> tuple[bytes, str, dict]:
    """The old fallback: any URL, any body, {payload} substituted."""
    body_tmpl = opts.get("body") or '{"message": "{payload}"}'
    body_type = (opts.get("body_type") or "json").lower()
    if body_type == "json":
        try:
            obj = json.loads(body_tmpl)
            obj = _walk_replace(obj, payload)
            return json.dumps(obj).encode("utf-8"), "application/json", {}
        except json.JSONDecodeError:
            return body_tmpl.replace("{payload}", payload).encode("utf-8"), "application/json", {}
    if body_type == "url":
        return body_tmpl.replace("{payload}", urllib.parse.quote(payload)).encode("utf-8"), "application/x-www-form-urlencoded", {}
    return body_tmpl.replace("{payload}", payload).encode("utf-8"), "text/plain", {}


def _raw_extract(body_text: str, opts: dict) -> str:
    """Raw adapter: return the raw body, or extract via dotted path if set."""
    path = opts.get("response_path")
    if not path:
        return body_text
    try:
        obj = json.loads(body_text)
        cur = _dotted(obj, path)
        return cur if isinstance(cur, str) else json.dumps(cur) if cur is not None else ""
    except Exception:
        return body_text


def _anthropic_render(payload: str, opts: dict) -> tuple[bytes, str, dict]:
    try:
        obj = json.loads(payload)
        if isinstance(obj, dict) and ("messages" in obj or "system" in obj):
            return json.dumps(obj).encode("utf-8"), "application/json", {}
    except Exception:
        pass
    sys_msg = opts.get("system") or "You are a helpful assistant."
    model = opts.get("model") or "claude-3-5-sonnet-latest"
    body = {
        "model": model,
        "system": sys_msg,
        "messages": [{"role": "user", "content": payload}],
        "max_tokens": int(opts.get("max_tokens") or 1024),
    }
    return json.dumps(body).encode("utf-8"), "application/json", {}


def _anthropic_extract(body_text: str, opts: dict) -> str:
    try:
        obj = json.loads(body_text)
        return _anthropic_reply(obj) or body_text
    except Exception:
        return body_text


def _gemini_render(payload: str, opts: dict) -> tuple[bytes, str, dict]:
    try:
        obj = json.loads(payload)
        if isinstance(obj, dict) and ("contents" in obj or "systemInstruction" in obj):
            return json.dumps(obj).encode("utf-8"), "application/json", {}
    except Exception:
        pass
    model = opts.get("model") or "gemini-1.5-flash"
    sys_msg = opts.get("system") or "You are a helpful assistant."
    body = {
        "systemInstruction": {"parts": [{"text": sys_msg}]},
        "contents": [{"role": "user", "parts": [{"text": payload}]}],
    }
    return json.dumps(body).encode("utf-8"), "application/json", {}


def _gemini_extract(body_text: str, opts: dict) -> str:
    try:
        obj = json.loads(body_text)
        return _gemini_reply(obj) or body_text
    except Exception:
        return body_text


# Default header text shown in the UI. Paste your API key into the headers box;
# it stays client-side and is sent with every request.
_ANTH_HEADERS = (
    "x-api-key: paste-your-anthropic-key-here\n"
    "anthropic-version: 2023-06-01\n"
    "Content-Type: application/json"
)
_GEMI_HEADERS = (
    "x-goog-api-key: paste-your-gemini-key-here\n"
    "Content-Type: application/json"
)



REGISTRY: dict[str, Adapter] = {}


def register(a: Adapter) -> Adapter:
    REGISTRY[a.id] = a
    return a


register(Adapter(
    id="raw",
    label="Raw HTTP (any URL, any body)",
    defaults={
        "url": "",
        "method": "POST",
        "body": '{"message": "{payload}"}',
        "body_type": "json",
        "response_path": "",
    },
    render=_raw_render,
    extract=_raw_extract,
))

register(Adapter(
    id="anthropic_msg",
    label="Anthropic Messages",
    defaults={
        "url": "https://api.anthropic.com/v1/messages",
        "method": "POST",
        "system": "You are a helpful assistant.",
        "model": "claude-3-5-sonnet-latest",
        "max_tokens": "1024",
        "headers": _ANTH_HEADERS,
    },
    render=_anthropic_render,
    extract=_anthropic_extract,
))

register(Adapter(
    id="gemini_gen",
    label="Google Gemini generateContent",
    defaults={
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        "method": "POST",
        "system": "You are a helpful assistant.",
        "model": "gemini-1.5-flash",
        "headers": _GEMI_HEADERS,
    },
    render=_gemini_render,
    extract=_gemini_extract,
))


def get(aid: str) -> Adapter:
    return REGISTRY.get(aid) or REGISTRY["raw"]


def list_adapters() -> list[dict]:
    return [
        {"id": a.id, "label": a.label, "defaults": a.defaults}
        for a in REGISTRY.values()
    ]