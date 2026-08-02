# NOTICE

Garbleworks is an authorized LLM red-team and safety-evaluation harness.

## Copyright

Copyright (c) 2026 SamsonCyber and contributors.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).

## Third-party and related work

- **Field guide data** shipped under `backend/data/field-guide.json` is adapted from the public catalog [SamsonCyber/llm-injection-field-guide](https://github.com/SamsonCyber/llm-injection-field-guide) (Dark Promptery). Prefer updating from that repo when the catalog moves.
- Evaluation ideas and benchmark shapes draw on public research (HarmBench, AttackEval-style graded judges, Wilson intervals, MAP-Elites / quality-diversity literature). Paper references live in docs and the field guide.
- Transform catalogs and safety literature (garak, PyRIT, promptfoo, h4rm3l, WildTeaming, and others) are cited for positioning, not vendored as code unless listed here.

## What this release deliberately excludes

- Virtualenvs, `node_modules`, live session dumps, fire history databases
- Live Anthropic/OpenAI bench runner scripts that require operator API keys
- Lab hostnames, private LAN IPs, and absolute machine paths
- Captured attack payloads and research attempt JSONL from local runs

## Responsible use

See [SECURITY.md](SECURITY.md). Authorized testing only.
