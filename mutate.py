#!/usr/bin/env python3
"""mutate.py - a thin CLI over the Garbleworks HTTP API.

The backend (uvicorn app:app) already does the work. This wraps it so text
can be mutated in one line instead of hand-built curl + JSON.

  python mutate.py health
  python mutate.py ops                       # list operations + params
  python mutate.py recipes                    # list saved recipes
  python mutate.py run --text "hello" --recipe "homoglyph:coverage=0.5 base64"
  python mutate.py run --recipe-name obfuscate-light --text "hello"
  echo "hello" | python mutate.py run --recipe "leetspeak zero_width:every=2"

Recipe mini-language: space-separated steps. Each step is

    op
    op:key=value
    op:key=value,key2=value2

Values are coerced to the parameter's declared type (int/float/bool/str),
which the tool learns from the live /ops registry. Unknown ops or params are
reported before anything is sent.

No third-party deps - stdlib urllib only, so any Python 3.8+ runs it.
The server URL defaults to http://127.0.0.1:9877 (override with --url or the
GARBLEWORKS_URL / MUTATOR_URL environment variable).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

# This tool deals in homoglyphs, zero-width chars, and invisible Unicode-tag
# bytes. On Windows the console defaults to cp1252, which can't encode them and
# would crash on print. Force UTF-8 on the output streams so variants survive.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

DEFAULT_URL = os.environ.get('GARBLEWORKS_URL') or os.environ.get('MUTATOR_URL', "http://127.0.0.1:9877")

# Truthy/falsey spellings accepted for bool params.
_TRUE = {"true", "1", "yes", "on", "y"}
_FALSE = {"false", "0", "no", "off", "n"}


def _api(url: str, path: str, method: str = "GET", payload: dict | None = None) -> object:
    """Call the API and return parsed JSON, or raise SystemExit with a clear msg."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    # The dev server runs with --reload, so a recent file change can refuse
    # connections for ~1s while it restarts. Retry a few times before giving up.
    last_err = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            sys.exit(f"error: {method} {path} -> HTTP {e.code}: {body[:300]}")
        except urllib.error.URLError as e:
            last_err = e
            time.sleep(0.4 * (attempt + 1))
    sys.exit(f"error: cannot reach {url} ({last_err.reason}). Is the server running? "
             f"(uvicorn app:app --host 127.0.0.1 --port 9877)")


def _coerce(value: str, ptype: str | None):
    """Turn a raw string value into the type the op declares."""
    if ptype == "int":
        return int(value)
    if ptype == "float":
        return float(value)
    if ptype == "bool":
        low = value.lower()
        if low in _TRUE:
            return True
        if low in _FALSE:
            return False
        raise ValueError(f"expected a boolean, got {value!r}")
    return value  # str / select / unknown -> leave as-is


def _load_ops(url: str) -> dict:
    """Return {op_name: {param_name: type}} from the live registry."""
    raw = _api(url, "/ops")
    index: dict[str, dict[str, str]] = {}
    for ops in raw.values():
        for op in ops:
            index[op["name"]] = {p["name"]: p["type"] for p in op["params"]}
    return index


def parse_recipe(spec: str, op_index: dict[str, dict[str, str]]) -> list[dict]:
    """Parse the mini-language into [{op, params}], validating against op_index."""
    steps: list[dict] = []
    for token in spec.split():
        name, _, paramstr = token.partition(":")
        if name not in op_index:
            near = ", ".join(sorted(n for n in op_index if name in n)) or "(none similar)"
            sys.exit(f"error: unknown operation {name!r}. similar: {near}\n"
                     f"       run 'python mutate.py ops' to see them all.")
        known = op_index[name]
        params: dict[str, object] = {}
        if paramstr:
            for pair in paramstr.split(","):
                if "=" not in pair:
                    sys.exit(f"error: bad param {pair!r} in step {token!r} (use key=value)")
                key, _, val = pair.partition("=")
                key = key.strip()
                if key not in known:
                    allowed = ", ".join(known) or "(no params)"
                    sys.exit(f"error: {name!r} has no param {key!r}. allowed: {allowed}")
                try:
                    params[key] = _coerce(val.strip(), known[key])
                except ValueError as e:
                    sys.exit(f"error: param {name}.{key}: {e}")
        steps.append({"op": name, "params": params})
    return steps


def _read_text(args, fallback: str | None = None) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            return f.read().rstrip("\n")
    if args.text is not None:
        return args.text
    if not sys.stdin.isatty():
        return sys.stdin.read().rstrip("\n")
    if fallback is not None:
        return fallback  # e.g. the input stored with a saved recipe
    sys.exit("error: no input. use --text, --file, or pipe via stdin.")


def cmd_health(args):
    h = _api(args.url, "/health")
    print(json.dumps(h, indent=2))


def cmd_ops(args):
    raw = _api(args.url, "/ops")
    for cat, ops in raw.items():
        print(f"\n# {cat}")
        for op in ops:
            ps = ", ".join(
                f"{p['name']}={p['default']}" + (f" {p['options']}" if p.get("options") else "")
                for p in op["params"]
            )
            print(f"  {op['name']:<14} {op['description']}")
            if ps:
                print(f"  {'':<14}   params: {ps}")


def cmd_recipes(args):
    names = _api(args.url, "/recipes")
    if not names:
        print("(no saved recipes)")
        return
    for n in names:
        print(n)


def cmd_run(args):
    # Resolve the recipe first so a saved recipe's stored input can serve as the
    # fallback when no --text/--file/stdin is supplied.
    if args.recipe_name:
        saved = _api(args.url, "/recipes/" + args.recipe_name)
        steps = saved.get("recipe", [])
        text = _read_text(args, fallback=saved.get("input"))
    else:
        if not args.recipe:
            sys.exit("error: provide --recipe \"...\" or --recipe-name NAME")
        steps = parse_recipe(args.recipe, _load_ops(args.url))
        text = _read_text(args)

    res = _api(args.url, "/run", "POST",
               {"input": text, "recipe": steps, "max_variants": args.max})

    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
        return

    stages = res.get("stages", [])
    if stages:
        chain = "  |  ".join(
            f"{s.get('op')}->{s.get('out')}"
            + ("*" if s.get("capped") else "")
            + (f"({s['error']})" if s.get("error") else "")
            for s in stages
        )
        print(f"pipeline: {chain}"
              + ("   (* = capped)" if any(s.get("capped") for s in stages) else ""))
    variants = res.get("variants", [])
    print(f"variants: {res.get('count', len(variants))}\n")
    for i, v in enumerate(variants, 1):
        print(f"--- {i} ---")
        print(v)


def cmd_save(args):
    """Validate a recipe spec against the live registry, then persist it by name."""
    steps = parse_recipe(args.recipe, _load_ops(args.url))
    res = _api(args.url, "/recipes", "POST",
               {"name": args.name, "recipe": steps, "input": args.text})
    print(f"saved: {res.get('saved')} ({len(steps)} step(s))")


def main():
    p = argparse.ArgumentParser(prog="mutate", description="CLI for the Garbleworks API")
    p.add_argument("--url", default=DEFAULT_URL, help=f"server base URL (default {DEFAULT_URL})")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health", help="show backend status").set_defaults(func=cmd_health)
    sub.add_parser("ops", help="list operations and params").set_defaults(func=cmd_ops)
    sub.add_parser("recipes", help="list saved recipes").set_defaults(func=cmd_recipes)

    r = sub.add_parser("run", help="mutate text through a recipe")
    r.add_argument("--text", help="input text (or use --file / stdin)")
    r.add_argument("--file", help="read input text from a file")
    r.add_argument("--recipe", help="recipe spec, e.g. \"homoglyph:coverage=0.5 base64\"")
    r.add_argument("--recipe-name", help="run a saved recipe by name")
    r.add_argument("--max", type=int, default=50, help="max_variants cap per stage (default 50)")
    r.add_argument("--json", action="store_true", help="print raw JSON response")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("save", help="validate and persist a recipe by name")
    s.add_argument("name", help="recipe name")
    s.add_argument("--recipe", required=True, help="recipe spec to save")
    s.add_argument("--text", help="optional default input text to store with it")
    s.set_defaults(func=cmd_save)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
