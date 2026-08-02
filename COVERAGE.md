# Technique Coverage

Maps the payload-transformation techniques documented across the bug-bounty
corpus (`bug-bounty/research/method-catalog/`, `ai-injection-research/`,
`llm-wiki/`), the stego payloads (`asknova-tradenova/payloads/stego-gap-payloads.txt`,
`encoding-channel-attack.md`), and the **StegOFF** detector catalog
(`pentestsidekick/.../10-AI-ATTACKS/Steganography.md`) onto the mutator's operations.

**138 ops registered** (`len(REGISTRY)`). The category tables below catalog the
deterministic string-transformation core; the later `jailbreak_ops` / `tier2_ops`
/ `framing_ops` / `adaptive_ops` / `llm_ops` modules are only partially enumerated
here and are the source of truth for their own ops. Every deterministic
string-transformation method from the corpus is implemented, and the mutator can
generate **every text method StegOFF detects** (see parity table below). Methods
that need a model, an optimizer, or a non-text carrier are listed under "Not
implemented" with the reason.

## StegOFF text-method parity

StegOFF (github.com/SamsonCyber/stegoff) detects 14 text-level steganography
methods. The mutator generates all of them:

| StegOFF text method | mutator op(s) |
|---|---|
| Unicode tag characters (U+E0000) | `unicode_tags` |
| Zero-width chars (U+200B/200C/200D/FEFF) | `zero_width`, `zwnj_chain`, `invisible_pad` |
| Homoglyph substitution | `homoglyph`, `homoglyph_extended`, `fullwidth` |
| Variation selectors (bit-per-char + byte channel) | `variation_selector`, `vs_smuggle` |
| Combining marks / zalgo | `combining` |
| Confusable whitespace (En/Em/Thin/Hair/Ideographic) | `unicode_spaces` |
| BIDI / RTL overrides | `rtl_override` |
| Trailing-whitespace (SNOW) | `whitespace_stego` |
| Hangul fillers (U+3164/U+FFA0) | `invisible_pad` (hangul kinds) |
| Math alphanumeric (bold/italic/script/fraktur/double-struck/mono) | `unicode_font` |
| Braille patterns | `braille` |
| Binary emoji (🌑/🌕) | `emoji_binary` |
| Emoji skin-tone (Fitzpatrick) | `emoji_skintone` |
| Hidden HTML (white-on-white, display:none, aria, meta, ld+json) | `html_hidden` |

Plus regional-indicator emoji-letter encoding (`emoji_encode`) and zero-width
binary (`sneaky_bits`) from the same family. Every invisible/stego op is built
from explicit codepoints and verified to emit the exact codepoint its technique
requires (24/24 codepoint-audit pass).

## Character / Unicode (17)

| corpus technique | op |
|---|---|
| Homoglyph substitution (Cyrillic/Greek/Armenian/Math) | `homoglyph`, `homoglyph_extended` |
| Zero-width space (ZWSP U+200B) | `zero_width` |
| Zero-width non-joiner (ZWNJ U+200C) | `zwnj_chain` |
| Zero-width joiner / BOM / word-joiner / Hangul filler (U+200D, U+FEFF, U+2060, U+3164, U+FFA0) | `invisible_pad` |
| Soft hyphen (U+00AD) | `soft_hyphen` |
| Variation selectors (evasion padding) | `variation_selector` |
| Unicode tag block (U+E0000) | `unicode_tags` |
| RTL / bidi override (U+202E) | `rtl_override` |
| Combining marks / zalgo | `combining` |
| Fullwidth forms | `fullwidth` |
| Confusable Unicode whitespace (En/Em/Thin/Hair/Ideographic/NBSP) | `unicode_spaces` |
| Math-alphanumeric (bold/italic/script/fraktur/double-struck/mono), circled, squared, small-caps | `unicode_font` |
| Leetspeak / 1337 | `leetspeak` |
| Character reversal | `reverse` |
| Word-order reversal | `word_reverse` |
| Alternating / mixed case | `case_alternate` |
| Inter-letter spacing | `spacer` |

## Encoding & ciphers (17)

| corpus technique | op |
|---|---|
| Base64 / URL-safe base64 | `base64` |
| Base32 | `base32` |
| Hex | `hex` |
| Octal | `octal` |
| Binary | `binary` |
| Decimal codepoints | `ascii_decimal` |
| ROT13 | `rot13` |
| Caesar (rot-N) | `caesar` |
| Atbash | `atbash` |
| Vigenère | `vigenere` |
| Morse | `morse` |
| Braille (binary + letter) | `braille` |
| URL / percent | `url_encode` |
| HTML entities (dec/hex) | `html_entities` |
| Unicode escapes (\uXXXX) | `unicode_escape` |
| Double / nested encoding | `double_encode` |
| Pig Latin | `pig_latin` |
| JWT-shaped segment smuggling | `jwt_style_split` |

## Steganographic channels (4)  — the "stego" source

| corpus technique | op |
|---|---|
| Zero-width binary ("sneaky bits", U+200B/U+200C or invisible-math) | `sneaky_bits` |
| Whitespace channel (space/tab binary on a cover line) | `whitespace_stego` |
| Regional-indicator emoji letters (🇦-🇿) + decode-hint emoji | `emoji_encode` |
| Binary emoji (two emoji = 0/1) | `emoji_binary` |
| Emoji skin-tone (Fitzpatrick base-5) | `emoji_skintone` |
| Variation-selector byte channel (256 selectors behind one anchor) | `vs_smuggle` |

## Structure / delimiter / framing (13)

| corpus technique | op |
|---|---|
| Divider / fake-section framing | `divider_wrap` |
| XML / paired-tag wrapping | `tag_wrap` |
| Code / markup comment hiding | `comment_wrap` |
| Fenced code block | `markdown_code` |
| Markdown table cell | `markdown_table` |
| JSON field embedding | `json_field` |
| INI config framing | `ini_wrap` |
| YAML frontmatter framing | `yaml_wrap` |
| LaTeX verbatim / math / comment | `latex_wrap` |
| Payload split across chunks | `split_join` |
| Split-string variable concatenation | `var_concat` |
| Function-call argument framing | `function_call` |
| Hidden HTML (white-on-white, display:none, aria-label, meta, ld+json, svg) | `html_hidden` |
| Arbitrary prefix / suffix scaffolding | `prefix_suffix` |

## Template / role injection (13)

| corpus technique | op |
|---|---|
| Chat-template role payloads (OpenAI/Anthropic/Gemini) | `prompt_template` |
| Persona / DAN / authority framing | `persona_wrap`, `persona_seed` |
| Instruction laundering (memo/log/ticket dilution) | `instruction_launder` |
| ChatML / delimiter collision (im_start, [INST], etc.) | `delimiter_collision` |
| Base64 "decode and execute" framing | `base64_role` |
| Structured JSON injection (instruction vs sibling field) | `json_inject` |
| Many-shot priming | `fewshot_seed` |
| Multi-turn / crescendo seeding | `multiturn_seed` |
| Legitimacy / inoculation framing | `inoculation` |
| Code-output ("already executed") framing | `codeblock_execute` |
| Forged tool-result framing | `tool_result_wrap` |
| System-message role framing | `semantic_frame` |

## Semantic reframing — prose (9) + language (6+)

| corpus technique | op |
|---|---|
| Synonym / paraphrase substitution | `synonym`, `paraphrase`, `paraphrase_batch`, `paraphrase_ollama` |
| Backtranslation / round-trip translation | `backtranslate`, `roundtrip` |
| One-way multilingual pivot (incl. low-resource) | `translate`, `multilang`, `language_wrap` |
| Amazigh / Tifinagh low-resource + rare script | `amazigh_obfuscate` (also `transliterate` script=`tifinagh`) |
| Visible-CoT hijack / dilution / no-decode | `cot_hijack` (modes), `cot_dilution`, `cot_no_decode`, `cot_forge_verdict` |
| Transliteration / pseudo-locale | `transliterate`, `pseudo_locale` |
| Sentence reordering | `sentence_reorder` |
| Active↔passive / syntax restructuring | `active_passive` |
| Typo / noise injection | `typo_inject` |

## Sampler (3)

`repeat`, `sample_n`, `echo` — fan-out / repetition utilities for fuzzing volume.

## Contextual misdirection — Pliny Family 27 (1 op, 5 scenarios)

Deterministic scenario-framing wrappers. `misdirection_frame` reframes the payload
as one of five plausible-deniability scenarios; the no-model sibling of `llm_reframe`.

| Pliny Family 27 frame | op / scenario |
|---|---|
| Academic peer-review frame | `misdirection_frame` scenario=`academic` |
| Historical documentation frame | `misdirection_frame` scenario=`historical` |
| Fictional narrative frame | `misdirection_frame` scenario=`fiction` |
| Code-as-story frame | `misdirection_frame` scenario=`code_story` |
| Test-case documentation frame | `misdirection_frame` scenario=`testcase` |
| Translation frame (27f) | already covered by `translate` / `language_wrap` (lang_ops) |

Prior partial coverage: `llm_reframe` (llm_ops) produces fiction/academic/historical/code
framings but needs a model and is non-deterministic; `past_tense` carries only a light
`historical`/`academic` prefix; `deep_inception` does nested-fiction specifically. This op
is the deterministic, single-string version the mutator layer was missing.

## Not implemented (and why)

These appear in the corpus but are out of scope for a deterministic string mutator:

| technique | reason |
|---|---|
| GCG / token-level adversarial suffix optimization | requires gradient access + an optimizer, not a string transform |
| Genetic / AFL-style prompt fuzzing (PAIR, PAPILLON) | a search loop over mutations, not a single mutation; this tool is the mutation primitive such a loop would call |
| Acrostic carrier generation | needs language generation to build a cover text whose first letters spell the payload |
| Past-tense reformulation | needs a tense-aware rewriter; `active_passive` covers the related syntax-flip probe |
| Arithmetic / spelled-out / scientific-notation number smuggling | target-specific to numeric-ID exfiltration (the asknova `51494` case), not a general text method |
| Flip-token / EchoGram classifier-flip suffixes | model-and-classifier-specific adversarial tokens, not a deterministic transform |

### StegOFF methods that are out of scope (non-text carriers)

StegOFF also scans 30+ file formats and multimodal carriers. Those are detection
surfaces for a different kind of artifact than a text mutator produces, so they
are intentionally not implemented here:

| StegOFF capability | reason |
|---|---|
| Image stego (LSB, white-on-white pixels, QR-in-image, adversarial perturbation) | needs an image carrier, not text — belongs in ST3GG / nanoGCG, not a text mutator |
| Audio stego (ultrasonic, audio adversarial) | needs an audio carrier |
| Document stego (PDF JavaScript, post-EOF, incremental updates, DOCX/XLSX metadata, EXIF) | needs a binary document container |
| Polyglot files | needs multi-format binary construction |
| Model-output stego (steganographic CoT, colluding-LoRA, Tomato) | the model is the encoder; nothing for a pre-processing mutator to do |

## Note on the running server

The `--reload` dev server on `:8000` can hold a stale module set (observed during
this work: it served 47 ops while the code had 81). If `GET /ops` shows fewer ops
than this document lists, restart it:

```
cd backend && .venv/Scripts/python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000
```
