# Technique Layering

How the mutation operations combine. The engine applies a recipe left to right,
piping every variant into the next stage. The ops fall into four layers, and a
recipe behaves well when it visits them in this order:

```
1. semantic synonym (rewords; English in, English out)
2. character homoglyph, leetspeak, fullwidth, (per-letter substitution / insertion,
 case_alternate, combining, spacer, text stays human/model readable)
 zero_width, unicode_tags, reverse
3. encoding base64, hex, rot13, morse, binary, (whole-string transform to a new charset)
 atbash, url_encode, html_entities,
 unicode_escape
4. structure tag_wrap, markdown_code, json_field, (delivery envelope around the payload)
 divider_wrap, comment_wrap,
 split_join, prefix_suffix
```

## The ordering rule

Apply lower layers before higher layers. A lower-layer op placed after a
higher-layer op is usually self-defeating:

- A **character** op after an **encoding** op corrupts the encoding. `leetspeak`
 rewrites vowels (`a->4`, `e->3`), and those letters are part of the base64
 alphabet, so `base64 leetspeak` produces a blob that no longer decodes. Proven:
 `base64 leetspeak` on the standard probe decodes to
 `Ignore?all prev?ous instructions...` with corrupted bytes.
- `zero_width` or `unicode_tags` inserted into an encoded blob breaks decoding too.
 A strict base64 decoder rejects it; a naive one can't even ASCII-encode the
 invisible characters.
- An **encoding** before a **structure** op is fine and stays reversible: unwrap
 the envelope, then decode. `base64 markdown_code` and `hex tag_wrap` both
 round-trip to the exact original.

`character -> encoding` is legal but buries the obfuscation. `homoglyph base64`
decodes to homoglyph text, so a filter that scans the raw base64 sees nothing
useful from the homoglyph layer, while a filter that decodes first then keyword
scans still hits the Cyrillic lookalikes. Use it only when the target decodes
before inspecting.

## Validated recipes

Saved on the server (HTTP recipe API or `python mutate.py run --recipe-name NAME`).
Each was fired through the probe set and checked; reversible ones were decode
round-tripped.

| name | recipe | layers | what it defeats |
|------|--------|--------|-----------------|
| `rt-reword` | `synonym:limit=4` | semantic | exact-string blocklists (changes the words) |
| `rt-homo-invisible` | `homoglyph:coverage=0.8 zero_width:every=1` | char | substring/keyword match, while staying model-readable |
| `rt-reword-leet` | `synonym:limit=4 leetspeak:level=1` | semantic -> char | lexical filters on both word and character form |
| `rt-layered-stack` | `synonym:limit=2 homoglyph:coverage=0.6 zero_width:every=2 tag_wrap:tag=user` | semantic -> char -> structure | stacked obfuscation in a role-tagged envelope |
| `rt-b64-fenced` | `base64 markdown_code:lang=text` | encoding -> structure | naive scanners; reversible by the model |
| `rt-hex-tagged` | `hex:sep=space tag_wrap:tag=data` | encoding -> structure | same, hex variant |
| `rt-spaced-split` | `spacer:char=zwsp split_join:parts=3,sep=newline` | char -> structure | contiguous-substring detection |

## Pitfalls (do not ship)

| recipe | problem |
|--------|---------|
| `base64 leetspeak` | char op after encoding corrupts the base64; will not decode |
| `base64 zero_width` | invisibles inside the blob break decoding (strict rejects, naive can't ASCII-encode) |
| `homoglyph base64` | legal, but the homoglyph layer is hidden inside the base64; only helps a decode-then-scan target |

## Reproduce

Apply a saved recipe through the HTTP API or MCP `apply_recipe`, then decode
round-trip any reversible encoding layer. Illegal stacks are rejected by
`is_legal_stack` in `scan_campaign.py`.
