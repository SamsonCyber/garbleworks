> Detailed usage and HTTP/UI reference. The public front page is [`../README.md`](../README.md).

# Garbleworks usage and API

A CyberChef-style text mutation tool for AI prompt-injection testing against
**authorized** targets. Build a *recipe* (an ordered list of operations), feed
it an input payload, fan out to many variants, then fire those variants at
a configured target with multi-signal hit detection.

The engine is content-agnostic: it transforms whatever text you give it. Ops
are grouped into families (encoding, character, template, jailbreak, and more).

## Security model: read before running

This is a **single-operator localhost tool with no authentication**. By design,
`/fire` makes server-side HTTP requests to URLs you supply (including internal
ones, which is intended - you fire at local/LAN test targets). The following
protections are in place to stop a malicious website from abusing that:

- **CORS is locked to localhost origins** (`localhost`/`127.0.0.1`/`[::1]`, any
 port). A page on `evil.com` cannot read responses from this server, so it
 cannot turn `/fire` into a cross-origin SSRF/exfiltration channel.
- **`/fire` validates the target URL** - only `http(s)`, and link-local
 (`169.254.0.0/16`, the cloud-metadata range) plus reserved/multicast ranges
 are blocked. Loopback and RFC-1918 stay allowed so local/LAN testing works.
 Set `GARBLEWORKS_BLOCK_PRIVATE=1` to also block loopback + private ranges.
 Policy lives in **one place**: `backend/fire.py` (`validate_target_url` /
 `fire_once`). The HTTP API, optimizer CLI, MCP `optimize`, and local generator
 client (`llm.safe_url`) all share it.
- **Redirects are not followed** (httpx `follow_redirects=False` and
 `fire.no_redirect_opener()`), so an allowed host can't 302 into a blocked
 internal address.
- **MCP fire tools also enforce the engagement receipt scope**
 (`GARBLEWORKS_SCOPE` / default local-selftest). Off-scope hosts get
 `SCOPE DENIED` even when they pass the generic range policy.
- **Request bodies are capped** (4 MB) and fan-out is bounded (`max_variants`
 <= 2000, deck inputs <= 1000).

Still required:

- **Bind to `127.0.0.1` only.** Never `--host 0.0.0.0`, never port-forward it,
 never put it behind a public reverse proxy. There is no auth - keep it local.
- For a shared/exposed deployment, add an auth token and turn on
 `GARBLEWORKS_BLOCK_PRIVATE`. Residual DNS-rebinding risk is documented on
 `fire.validate_target_url` (CORS is the primary remote boundary).

## Operations (138 total)

Every op carries a tactic `family` (derived from category, overridable) used by the
diversity-constrained compose/thompson selectors. `/ops` exposes it.

| Category | Count | What it does |
|---|---|---|
| encoding | 27 | base64/32/58/85, rot13/47, hex, octal, binary, morse, braille, atbash, caesar, vigenere, bacon, polybius, rail_fence, a1z26, nato, pig_latin, url/html/unicode escapes, double_encode, jwt_style_split, keyboard_shift |
| character | 23 | confusable unicode, invisible chars (ZWSP/ZWNJ/soft-hyphen/VS/BiDi), leet, fullwidth, zalgo, spacing, reversal, word_scramble, positional_insert |
| template | 18 | prompt_template, persona_wrap/seed/sweep, instruction_launder, delimiter_collision, base64_role, json_inject, many/few-shot seeds, multiturn_seed, crescendo_ladder, ... |
| jailbreak | 18 | deep_inception, cipher_persona, code_chameleon, bad_likert_judge, policy_puppetry, past_tense, ascii_art_mask, bijection_cipher, refusal_suppression, fragment_scene, disguise_reconstruct, ... |
| structure | 14 | divider/tag/comment/markdown/json/yaml/ini/latex wraps, function_call, var_concat, html_hidden, split_join, prefix_suffix |
| prose | 10 | synonym (spaCy+WordNet/fallback), backtranslate, translate (MarianMT), paraphrase (+ollama/openai/batch), typo_inject, sentence_reorder, active_passive |
| sampler | 9 | repeat/echo (control), sample_n, distinct_n, diverse_k, mmr_select, seed_sweep, random_pick_k, recipe_subset |
| stego | 6 | emoji_binary/encode/skintone, vs_smuggle, whitespace_stego, sneaky_bits |
| language | 5 | translate (multilang), language_wrap, roundtrip, transliterate, pseudo_locale |
| carrier | 5 | indirect injection: email_wrap, editor_note_inject, reference_link_exfil, memory_seed, write_primitive_frame |
| llm | 3 | llm_reframe, llm_generate, complexify (all local-model backed, pass-through if offline) |

New ops register themselves by adding a file in `backend/ops/` and listing
it in `backend/ops/__init__.py`. See the existing files for the pattern.

### Adaptive layer (history-driven)

Beyond the transform library, the tool has a measure -> select -> discover loop:

- `detectors.py` - `llm_judge` detector adds AttackEval 4-level grading (0/.33/.66/1.0),
 persisted per result as `graded_score`.
- `bandit.py` - Thompson-sampling recipe selector. Each op is a Beta arm over its
 per-target success rate from `/history`; `GET /deck/thompson` samples a
 family-diverse recipe, `GET /deck/arms` shows the posterior leaderboard + lifecycle
 state (probation/active/retired).
- `discover.py` - `GET /deck/discover` proposes new recipes from history patterns
 (local model, bandit fallback), registry-validated, returned as `probation`.
- `exporters.py` - `POST /export/recipe` serializes a recipe's variants to
 promptfoo / garak / PyRIT for validation against community benchmarks.
- `GET /history/analytics/variance` - per-recipe hit-rate variance (Furina instability).

## Architecture

```
backend/
 app.py FastAPI server: UI + recipe + fire + history endpoints
 core.py Engine: Operation dataclass, REGISTRY, run_recipe()
 ops/
 char_ops.py 14 character ops
 encode_ops.py 14 encoding ops
 struct_ops.py 7 structure ops
 prose_ops.py 8 prose ops (synonym, backtranslate, translate, ...)
 template_ops.py 13 template/role ops
 sampler_ops.py 3 sampler/control ops
 targets.py Pluggable target adapters (raw / anthropic_msg / gemini_gen)
 detectors.py Multi-signal hit-detection pipeline (9 detector kinds)
 history.py SQLite store for fire runs + per-op analytics
 echo_target.py Local quick-check target server
 fire_history.sqlite3 The persisted DB (created on first fire)
 recipes/ Saved recipe presets (seeded on first run)
 decks/ Saved input decks
frontend/
 index.html Single-file UI, no build step. ~95KB.
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | the UI |
| GET | `/health` | rewriter mode + translate availability |
| GET | `/ops` | registry of all operations, grouped by category |
| GET | `/adapters` | target adapter list |
| GET | `/detectors/presets` | detector-kind list for the UI |
| POST | `/run` | apply a recipe to one input |
| POST | `/run_deck` | apply a recipe to every input in a deck |
| GET / POST | `/recipes`, `/recipes/{name}` | save / load recipes |
| GET / POST | `/decks`, `/decks/{name}` | save / load input decks |
| POST | `/fire` | generate variants and fire them at a target |
| POST | `/fire_deck` | fire one recipe across every input in a deck |
| GET | `/history/summary`, `/history/runs`, `/history/runs/{id}` | browse past runs |
| GET | `/history/analytics/{per_op,per_host,per_op_pair}` | aggregate hit rates |
| GET | `/history/export` | dump all results as JSONL |

## Offline benchmarks

Math + harness plumbing (echo target, no external APIs):

```powershell
cd C:\code\garbleworks\backend
.\.venv\Scripts\python.exe benchmark_harness.py
.\.venv\Scripts\python.exe benchmark_harness.py --suite math_lcb_gate,optimizer_ga
```

Results: `backend/benchmarks/results/benchmark-latest.md`. Details in `backend/benchmarks/README.md`.

## Run it

```powershell
cd C:\code\garbleworks\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Open http://localhost:8000.

If port 8000 is held by a phantom LISTENING socket from a previous session
(shows in `netstat` but isn't killable - see Troubleshooting), bind to a
fresh port like `9877` instead.

The `synonym` op falls back to a small built-in dictionary if spaCy /
WordNet aren't installed (the header pill shows `rewriter: fallback`).
For the real WordNet path:

```powershell
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('wordnet'); nltk.download('omw-1.4')"
```

For `backtranslate` / `translate` (MarianMT, ~2GB):

```powershell
pip install transformers torch sentencepiece
```

## Target adapters

A target adapter turns a payload string into the right HTTP request shape
and pulls the model's reply out. Adapters are registered in
`backend/targets.py`:

| Adapter | URL | Default body shape |
|---|---|---|
| `raw` | (any) | user-supplied template with `{payload}` slot |
| `anthropic_msg` | `https://api.anthropic.com/v1/messages` | native Anthropic messages API |
| `gemini_gen` | `https://generativelanguage.googleapis.com/.../generateContent` | native Gemini generateContent |

The UI's target panel selects an adapter; switching it auto-fills the
URL, method, headers default, and the adapter-specific option fields
(model, system, max_tokens, temperature). Headers default to a
`paste-your-provider-key-here` placeholder - paste your real key into
the headers box before firing.

An adapter is just:

```python
register(Adapter(
 id="my_adapter", label="My custom adapter",
 defaults={"url": "...", "headers": "...", "system": "...", "model": "..."},
 render=lambda payload, opts: (body_bytes, content_type, extra_headers),
 extract=lambda resp_text, opts: reply_string,
))
```

## Detector pipeline

A hit isn't a single regex - it's the conjunction (or disjunction) of
multiple signals. The `detect` block in `/fire` accepts:

```json
{
 "combine": "all",
 "detectors": [
 {"kind": "refusal_bank", "config": {"min_hits": 1}, "label": "model_refused"},
 {"kind": "not_contains", "config": {"value": "OBJECTIVE_ACHIEVED"}, "label": "didnt_achieve"},
 {"kind": "contains", "config": {"value": "API_KEY"}, "label": "leaked_secret"},
 {"kind": "secret_regex", "config": {}, "label": "any_secret_shape"},
 {"kind": "status_eq", "config": {"value": 200}},
 {"kind": "min_length", "config": {"value": 100}}
 ]
}
```

| Kind | What it checks |
|---|---|
| `contains` | case-insensitive substring in snippet |
| `not_contains` | substring must be absent |
| `regex` / `not_regex` | regex match / absence |
| `status_eq` / `status_in` | HTTP status equals / in list |
| `refusal_bank` | matches any of 26+ built-in refusal phrases |
| `secret_regex` | scans with 20 built-in secret/PII regexes (AWS, GitHub, OpenAI, JWT, PII, ...) |
| `min_length` | snippet length |

`combine` modes: `all` (strict, all must pass), `any` (lenient, one passes),
`score` (returns the ratio without forcing a hit). The response carries
`hit`, `score`, and a full `detectors[]` trace per result.

The legacy single-detector shape `{mode, value, field}` is still
accepted - it's auto-converted to a one-element detectors list.

## Recipes and decks

- **Recipe** = ordered list of ops. Save with a name, reload from the
 "load saved" dropdown. 15+ presets ship in `backend/recipes/`.
- **Deck** = list of input strings. Save with a name. The UI's input
 panel has a tab to switch between "single input" and "input deck";
 deck mode uses a textarea (one input per line) and triggers
 `/fire_deck` instead of `/fire`.

## History + analytics

Every fire persists to `fire_history.sqlite3`. Schema:
- `fire_runs` - one row per fire call (target, recipe fingerprint,
 detect mode, totals, label, started/finished)
- `fire_results` - one row per variant (status, ms, snippet, hit, error)
- `op_attribution` - which op in the recipe produced each variant (leaf-op attribution)

Per-op / per-host / per-pair analytics aggregate over the table:
- `/history/analytics/per_op` - which leaf op correlates with hits
- `/history/analytics/per_host` - hit rate per target
- `/history/analytics/per_op_pair` - co-occurrence of leaf op pairs

`/history/export?host=...` writes a JSONL of every result to
`backend/exports/fire-history-<host>-<stamp>.jsonl`.

## quick-check target

`backend/echo_target.py` is a 30-line HTTP server that echoes any POST
body back, marking `hit_token: OBJECTIVE_ACHIEVED` only when the body
contains the substring `secret`. Use it to verify the fire loop
without hitting any external API:

```powershell
python echo_target.py 9001
# then point a fire at http://127.0.0.1:9001/
```

## Adding a new operation

```python
# backend/ops/my_ops.py
from core import Operation, Param, register

def _my_op(text: str, level: int) -> list[str]:
 return [text * level] # fan out

register(Operation(
 name="my_op", category="custom",
 description="Multiply the input by N.",
 params=[Param("level", "int", 1, "How many copies.", min=1, max=10)],
 fn=_my_op,
))
```

Then list it in `backend/ops/__init__.py`. The next `/ops` request picks
it up and the UI palette shows it automatically.

## Troubleshooting

**Port 8000 says "address already in use" but `taskkill /F /PID` fails.**

This is a Windows quirk: a previous uvicorn process's socket can stay
in LISTENING state after the owning PID is gone (typical after a
session crash or process kill -9). Symptoms:
- `netstat -ano | grep 8000` shows a LISTENING entry with a PID that
 `tasklist /FI "PID eq <pid>"` says doesn't exist
- `taskkill /F /PID <pid>` returns "process not found"
- A new uvicorn process fails to bind with `[Errno 10048] only one
 usage of each socket address`

Workaround: bind to a different port (`uvicorn app:app --port 8765`
or `--port 9877`). Permanent fix: reboot, or run
`netsh winsock reset` (admin cmd, then reboot).

**`detector_rows: 0` after page load.**

The UI loads adapters/detectors/decks asynchronously after init. If
you drive the page from a script immediately after `navigate`, the
loaders haven't finished. Wait 500-1500ms or watch for the request
to `/adapters` to complete.

**`near_dedupe` checkbox isn't sending the field.**

The field is only sent when the box is **checked**. That's intentional
(default is off, since it changes variant counts in ways the user
should opt into).

## Scope

For authorized security research only: app-layer prompt-injection testing
of targets you are permitted to test (huntr challenges, your own systems,
sanctioned engagements). Not for defeating model safety guardrails to
extract harmful content.