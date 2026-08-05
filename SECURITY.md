# Security & Responsible Use

Garbleworks is an offensive-security research tool. This document covers who may use it, what it does and does not ship, how it protects the machine it runs on, and how to report a vulnerability in the tool itself.

## Authorized use only

Garbleworks is for **authorized LLM red-teaming and safety evaluation only**:

- models **you own** or run locally,
- targets covered by a **bug-bounty program that is in scope**,
- systems under a **written engagement / penetration-test authorization**,
- CTFs and research environments you control.

It is **not** for defeating the safety controls of third-party production models you have no authorization to test, and not for producing standalone harmful content divorced from demonstrating a target weakness. Using it outside an authorized scope may violate provider terms of service and computer-misuse law. That is on the operator.

## What this repository does and does not contain

- **Ships:** the transformation ops, the recipe DSL, the search/optimizer, the evaluation and statistics layer, target adapters, the MCP server, exporters, and the field-guide crosswalk. Pliny-family **structural** primitives (GODMODE / NEW PARADIGM anchors, ResponseFormat split, Family-27 misdirection, operator signature chrome) ship as registered ops via the always-on builtin kit in `backend/pliny_adapter.py`.
- **Does not ship:** any un-guardrailed model, and no bundled corpus of harmful payloads or full L1B3RT4S / CL4R1T4S liberation dumps. Optional local Pliny-style corpora load only from an operator path (`GARBLEWORKS_PLINY_CORPUS` or `pliny_frame` `corpus_path`); missing path degrades to the builtin kit with no network fetch. The `llm`-family ops (`llm_reframe`, `llm_generate`, `complexify`) call a **local model that you supply** (for example via Ollama); when that model is unreachable they degrade to pass-through. If you make this repository public, keep it that way: do not commit model weights, a jailbreak-prompt corpus, or captured attack payloads.

### Optional Pliny corpus (operator-local)

| Repo idea | Role in Garbleworks |
| --- | --- |
| L1B3RT4S-style markdown/json tree | Data adapter: structural markers → composable recipe steps |
| CL4R1T4S-style text | Same load rules if present on disk |
| G0DM0D3 | Not an adapter (chat UI) |
| OBLITERATUS | Not an adapter (weight surgery) |
| GLOSSOPETRAE | Not vendored (JS); language ideas map to lang ops |

See `backend/pliny_adapter.py` and op `pliny_frame`.

## Engagement scope enforcement

Firing is gated in two independent layers:

1. **Network policy** (`backend/fire.py`, `validate_target_url` / `fire_once`): only `http(s)`; link-local and cloud-metadata (`169.254.0.0/16`), reserved, and multicast ranges are blocked; redirects are not followed; request bodies are capped (4 MB) and fan-out is bounded (`max_variants ≤ 2000`, deck inputs ≤ 1000). Set `GARBLEWORKS_BLOCK_PRIVATE=1` to also block loopback and RFC-1918.
2. **Engagement receipt scope** (MCP fire tools): off-scope hosts get `SCOPE DENIED` even when they pass the generic range policy. Scope is set via `GARBLEWORKS_SCOPE` (default `local-selftest`, in-scope `127.0.0.1` / `localhost`).

## Deploying it safely

- **Bind to `127.0.0.1` only.** Never `--host 0.0.0.0`, never port-forward it, never place it behind a public reverse proxy. The server has **no authentication** by design; it is a single-operator localhost tool.
- CORS is locked to localhost origins, so a malicious web page cannot turn `/fire` into a cross-origin SSRF/exfiltration channel.
- For any shared or exposed deployment, add an auth token and enable `GARBLEWORKS_BLOCK_PRIVATE`. Residual DNS-rebinding risk is documented on `fire.validate_target_url`; CORS is the primary remote boundary.

## Reporting a vulnerability in Garbleworks

If you find a security issue in the tool itself (an SSRF bypass, a scope-enforcement escape, a request-cap bypass, etc.), please report it privately rather than opening a public issue:

- Open a **private security advisory** on the GitHub repository (Security → Report a vulnerability), or
- email the maintainer at the address on the GitHub profile.

Please include a minimal reproduction and the affected version/commit. Coordinated disclosure is appreciated; you will get credit unless you ask otherwise.

## Scope of this policy

This policy covers the Garbleworks codebase. It does not authorize, and cannot authorize, testing any particular third-party target. Authorization for a given engagement is the operator's responsibility to obtain and document.
