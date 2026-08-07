## What this does

Brief description. Link the issue it closes (`Closes #...`).

## Type

- [ ] New op / adapter
- [ ] Search or measurement change
- [ ] Bug fix
- [ ] Docs
- [ ] Other

## How I verified it

Test output, a benchmark delta, or a screenshot. New capability should come with a test.

```
# paste: pytest -q and/or benchmark_harness.py --fail-on-regression
```

## Checklist

- [ ] No model weights, harmful-payload corpora, transcripts, or API keys committed.
- [ ] Anything that fires still goes through `backend/fire.py` (no second unguarded network path).
- [ ] If model-backed, it degrades to pass-through when the local model is offline.
- [ ] New op is listed in `backend/ops/__init__.py` and shows the right `family` in `GET /ops`.
- [ ] Docs updated (`COVERAGE.md` / `README.md`) if behavior or coverage changed.

## Security impact

Does this touch the fire path, scope enforcement, CORS, or caps? If yes, describe it
explicitly so it gets a closer review.
