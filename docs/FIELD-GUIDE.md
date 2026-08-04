# The Injection Field Guide

Garbleworks ships against a **reference catalog** of prompt-injection and jailbreak
techniques: the `llm-injection-field-guide`. It is the knowledge layer that connects
"a technique the literature names" to "an executable op garbleworks can run" and to
"the framework IDs an auditor speaks."

- **Version:** 1.1.0 (generated 2026-07-12)
- **Techniques:** 312 across 20 categories (281 attack-side + 31 defense)
- **Crosswalked:** 248 / 312 attack techniques (foundations + defense categories intentionally untagged)
- **Frameworks:** MITRE ATLAS v5.6.0 · OWASP LLM Top 10 2025 · NIST AI 100-2e2025 · CWE 4.20
- **Tool hooks:** 37 techniques map to a garak / promptfoo / PyRIT / StrongREJECT probe
- **Benchmarks:** 32 techniques tagged with a public benchmark (AgentDojo, InjecAgent, TensorTrust, HackAPrompt, Gray Swan, …)
- **Origin cited:** 70 techniques carry the paper/repo that introduced them
- **Source:** [`llm-injection-field-guide/field-guide.json`](../llm-injection-field-guide/field-guide.json) (vendored export of live `const T` + `crosswalk-block.js`)

> [!NOTE]
> This is a **reference catalog**, not a payload corpus. Entries are technique
> write-ups (what / why / internals / example / defense / refs) crosswalked to the same
> defensive frameworks (ATLAS, OWASP, NIST, CWE) that a blue team uses. The examples are
> benign canaries (the canonical `I HAVE BEEN PWNED` marker), not weaponized content.
> Tool chips exist only where a public probe is named; absence means "no verified hook,"
> not "untestable."

## Why it matters

It is the piece that turns garbleworks from a payload forge into an auditable harness:

1. **Reference → runtime bridge.** `field_guide_ops(title)` returns the garbleworks
 op(s) that implement a technique, so you go straight from "I want to test Policy
 Puppetry" to running it. Reference catalog ↔ executable transform, in one hop.
2. **Runtime → report bridge.** Findings can carry the technique's OWASP/ATLAS/NIST/CWE
 IDs (when present) and any garak/promptfoo/PyRIT probe that also tests it, so a result
 drops into a report or a second tool without re-mapping by hand.

## Categories (312 techniques)

| Category | # | Category | # |
|---|--:|---|--:|
| foundations | 33 | optimization | 36 |
| defense | 31 | modellevel | 28 |
| indirect | 25 | roleplay | 17 |
| multimodal | 17 | character | 15 |
| encoding | 14 | decoding | 14 |
| structure | 12 | multiturn | 12 |
| exfil | 10 | refusal | 9 |
| extraction | 9 | semantic | 8 |
| stego | 7 | persuasion | 6 |
| incontext | 5 | composition | 4 |

The **defenses** category is deliberate: garbleworks measures attack success *and* how
much each defense reduces it. Most attack catalogs have no defensive half.

## How garbleworks connects to it (MCP)

The garbleworks MCP server exposes the field guide as live tools. There is no separate
service to stand up; if garbleworks is connected, the field guide is connected.

| Tool | What it returns |
|---|---|
| `field_guide_categories` | the 20 categories with technique counts |
| `field_guide_search(query, category?)` | ranked techniques matching text **or** a crosswalk ID (`LLM01`, `AML.T0051`, `garak`, `HarmBench` all work), with a compact crosswalk |
| `field_guide_get(title)` | the full write-up: what / why / internals / example / defense / refs |
| `field_guide_crosswalk(title)` | the full framework mapping + the tool/probe + origin |
| `field_guide_by_framework(id)` | every technique under an OWASP / ATLAS / CWE id |
| `field_guide_by_tool(tool)` | every technique with a garak / promptfoo / pyrit / strongreject hook |
| `field_guide_ops(title)` | **the bridge** - the garbleworks op(s) that implement the technique, ready for `generate_framings` / `apply_recipe` |

### Example: reference to runtime in two calls

```text
field_guide_search("indirect prompt injection")
 → "Indirect Prompt Injection via Retrieved Content"
 cat=indirect · OWASP LLM01 · ATLAS AML.T0051.001 · CWE-1427
 garak: latentinjection · benchmarks: AgentDojo, InjecAgent, Gray Swan

field_guide_ops("Policy Puppetry")
 → { ops: ["policy_puppetry"], run_with: "generate_framings" }
```

## Keeping the catalog in sync

Single source of truth is the live guide repo:

`~/code/llm-injection-field-guide/index.html` (`const T` + inlined crosswalk / `crosswalk-block.js`).

```bash
cd ~/code/llm-injection-field-guide
python sync.py
python export_crosswalked.py --out /path/to/garbleworks/llm-injection-field-guide/field-guide.json
```

When you add a garbleworks op that implements a catalogued technique, wire it into
`backend/build_technique_ops.py` so the reference-to-runtime bridge stays complete.

## See also

- [Technique coverage](../COVERAGE.md) - the op-level view, including StegOFF parity
- [Positioning vs the literature](HARNESS-POSITIONING.md)
- Project front page: [`../README.md`](../README.md)
