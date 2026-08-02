# How Garbleworks works (end-to-end)

This is the operator-facing walkthrough of one full engagement cycle.
For install and API maps see [USAGE-AND-API.md](USAGE-AND-API.md).
For measured offline numbers see [BENCHMARKS.md](BENCHMARKS.md).

## The problem

Fixed jailbreak lists go stale. A payload that works on one model fails on the next, and a single lucky hit is not a measurement.

You need:

1. A way to **compose** attacks from small transforms (not one opaque blob).
2. A way to **search** that space instead of hand-picking strings.
3. A **fire path** that cannot quietly SSRF into your LAN or cloud metadata.
4. **Detectors** and **re-fire** so success is a rate with bounds, not a screenshot.
5. A map from findings to **OWASP / ATLAS / NIST / CWE** and optional export to other tools.

Garbleworks is that closed loop.

## Closed loop (one run)

```text
  objective + target + detectors + budget
                 |
                 v
        +------------------+
        | 1. Compose       |  recipe = ordered op chain
        |    (DSL / UI /   |
        |     MCP / GA)    |
        +--------+---------+
                 |
                 v
        +------------------+
        | 2. Apply         |  expand into variants
        |    (run_recipe)  |  fan-out caps apply
        +--------+---------+
                 |
                 v
        +------------------+
        | 3. Fire (scoped) |  fire.py validates URL
        |    + engagement  |  MCP requires authorized_scope
        |      receipt     |  no redirects after check
        +--------+---------+
                 |
                 v
        +------------------+
        | 4. Detect/judge  |  contains/regex/secret_regex
        |                  |  refusal_bank / llm_judge / ...
        +--------+---------+
                 |
        +--------v---------+
        | 5. Search/history|  EVOLVE / MAP-Elites /
        |    / bandit      |  Thompson bandit / tree search
        +--------+---------+
                 |
                 v
        +------------------+
        | 6. Report        |  Wilson ASR, re-fire N times
        |    + export      |  promptfoo / garak / PyRIT
        |    + crosswalk   |  field guide frameworks
        +------------------+
```

| Step | What the operator sees | Primary code |
|------|------------------------|--------------|
| Compose | Recipe string or JSON steps | `core.py`, `ops/*` |
| Apply | List of variant strings | `run_recipe` |
| Fire | HTTP or local callable under policy | `fire.py`, `targets.py` |
| Detect | Hit / miss / score | `detectors.py` |
| Search | Next recipe favored or retired | `evolve.py`, `optimizer.py`, `rainbow.py`, `bandit.py`, `treesearch.py` |
| Report | ASR, LCB notes, export files | `validate_refire.py`, `exporters.py`, field-guide tools |

## Recipe unit

A **recipe** is an ordered composition of parameterized ops:

```text
synonym:limit=3 homoglyph:coverage=0.5 zero_width:every=2 tag_wrap
```

Meaning: reword, swap confusable glyphs, inject invisible characters, wrap structure.
Ops register into a live catalog (currently **152** after `import ops`). Families cover encoding, character, template, jailbreak, structure, prose, sampler, stego, language, carrier, and llm.

Ops are pure on strings unless marked otherwise. Fan-out is capped so a single apply cannot explode memory.

## Fire path (why scope is not optional)

All server-side outbound HTTP goes through `backend/fire.py`:

1. **Scheme** must be `http` or `https`.
2. **Blocked** by default: link-local / cloud metadata (`169.254.0.0/16`), multicast, reserved, unspecified.
3. **Loopback and RFC-1918** allowed by default so local Ollama and LAN lab servers work. Set `GARBLEWORKS_BLOCK_PRIVATE=1` to deny them.
4. **No redirects** after validation (a 302 cannot pivot into a blocked host).
5. **MCP engagement receipt**: fire tools require host match to `authorized_scope` (default `local-selftest`: `127.0.0.1`, `localhost`). Off-scope → `SCOPE DENIED`.
6. **Caps**: body size and variant fan-out limits.

The HTTP API itself is **unauthenticated**. Bind to `127.0.0.1` only. See [SECURITY.md](../SECURITY.md).

## Detectors and what "success" means

A fire returns a response snippet. Detectors score it:

| Kind | Role |
|------|------|
| `contains` / `regex` | Deterministic substring or pattern |
| `secret_regex` | Common key/token/PEM/JWT shapes |
| `refusal_bank` | Refusal phrases (positive = refused) |
| `llm_judge` | Graded AttackEval (0 / 0.33 / 0.66 / 1.0) |
| `status_*` / `min_length` | Transport / length floors |

Combine modes: `all`, `any`, `score`.

**Validate re-fire** re-sends a winning payload N times and reports Wilson ASR.
A single green checkmark is not a claim. Product promotion rules in the canary bench require minimum N and LCB lift (see [BENCHMARKS.md](BENCHMARKS.md)).

## Search stack

| Mechanism | Job |
|-----------|-----|
| EVOLVE | Genetic search on the probability simplex (Aitchison geometry). Spec: [EVOLVE_MATH.md](../EVOLVE_MATH.md) |
| MAP-Elites | Quality-diversity over behavior × obfuscation |
| Thompson bandit | Beta posterior per arm; probation → active → retired |
| Tree search | Multi-turn beam for erosion paths single-turn recipes miss |
| Register `L(x)` | Lexical loadedness features tied to refusal |

Honest math note from the offline audit: under default hyperparameters the **LCB success gate is not reachable** with small `n_max`, while the product **success_flag still uses held-out mean**. That is measured, not hidden. See published offline metrics in [BENCHMARKS.md](BENCHMARKS.md).

## Operator surfaces (three doors, one fire path)

| Surface | Start | Role |
|---------|-------|------|
| HTTP + web UI | `run.ps1` → `http://127.0.0.1:9877` | Human operator, full REST |
| MCP | `python backend/mcp_server.py` | Agent operator; scope receipt on fire |
| TUI | `cd tui && bun start` | Keyboard console; bridges to backend only |

There is no second, unchecked fire path in the TUI or MCP. Both call the same policy module.

## First mental model for a new operator

1. Start echo target (no model): `python backend/echo_target.py 9001`
2. Start API on loopback: `powershell -File run.ps1`
3. Compose a trivial recipe that only tags or encodes
4. Fire at `http://127.0.0.1:9001/`
5. Confirm detectors hit on the echoed body
6. Run `python scripts/repro.py` for offline security + math gate

When you point at a real local model, keep targets on loopback or in-scope lab hosts only.

## What Garbleworks is not

- Not a cloud multi-model JailbreakBench leaderboard (roadmap; not shipped).
- Not an unauthenticated remote weapon; scope and bind assumptions are local-first.
- Not "more ops alone." Count matters less than search + measurement + enforced fire.

For the honest peer table and literature mapping see the README and [HARNESS-POSITIONING.md](../HARNESS-POSITIONING.md).
