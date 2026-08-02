# Contributing to Garbleworks

Thanks for your interest. Garbleworks is a red-team research harness; contributions that improve the **search, measurement, coverage, or safety rails** are especially welcome. Please read [`SECURITY.md`](SECURITY.md) first, contributions must keep the authorized-use posture intact.

## Ground rules

- Do not commit model weights, harmful-payload corpora, captured attack transcripts, or provider API keys.
- Keep the network safety model intact. Anything that fires must go through `backend/fire.py` (`validate_target_url` / `fire_once`); do not add a second, unguarded network path.
- New capability comes with a test and, where relevant, a benchmark-suite entry.

## Dev setup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the server:

```powershell
uvicorn app:app --reload --port 8000
```

## Tests & the audit suite

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q # unit tests
.\.venv\Scripts\python.exe benchmark_harness.py --fail-on-regression # math + plumbing audit
```

CI runs both on every pull request (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)). A PR that regresses the math-audit gates will fail; that is intentional, the statistical guarantees are the product.

## Adding a new op

Ops live in `backend/ops/`. Add a file, register the op, and list it in `backend/ops/__init__.py`:

```python
# backend/ops/my_ops.py
from core import Operation, Param, register

def _my_op(text: str, level: int) -> list[str]:
 return [text * level] # ops fan out to a list of variants

register(Operation(
 name="my_op",
 category="structure", # sets the default tactic `family`
 description="Multiply the input by N.",
 params=[Param("level", "int", 1, "How many copies.", min=1, max=10)],
 fn=_my_op,
))
```

The next `/ops` request and the UI palette pick it up automatically. Before opening a PR:

- confirm it appears in `GET /ops` with the right `family`,
- if it is invisible/stego, add it to the StegOFF parity table in [`COVERAGE.md`](COVERAGE.md) and verify the exact codepoints it emits,
- if it is model-backed, make sure it degrades to pass-through when the local model is offline (mirror `llm_reframe`).

## Adding a target adapter

Adapters (`backend/targets.py`) turn a payload string into the right request shape and pull the reply out:

```python
register(Adapter(
 id="my_adapter", label="My custom adapter",
 defaults={"url": "...", "headers": "...", "model": "..."},
 render=lambda payload, opts: (body_bytes, content_type, extra_headers),
 extract=lambda resp_text, opts: reply_string,
))
```

## Code style

- Python 3.11+, standard library first; keep heavy deps optional and lazily imported (see how `prose_ops` handles spaCy/MarianMT).
- Match the surrounding code. No unrelated reformatting in a feature PR.
- Comments explain constraints, not narration.

## Commit / PR

- One logical change per PR. Describe what it does and how you verified it (test output, a benchmark delta, a screenshot for UI).
- Link the issue it closes.
- If it changes the security model, say so explicitly in the PR body so it gets a closer look.

## Reporting bugs & requesting features

Use the issue templates under [`.github/ISSUE_TEMPLATE`](.github/ISSUE_TEMPLATE). For **security** issues, do not open a public issue, follow [`SECURITY.md`](SECURITY.md).
