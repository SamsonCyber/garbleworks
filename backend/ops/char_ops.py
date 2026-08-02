"""Character-layer operations. Pure string manipulation, zero ML.

Deterministic and instant. Models the "special characters, omissions,
spacing, and invisible text" techniques.
"""
from __future__ import annotations

import random
import re

from core import Operation, Param, register

# Latin -> visually-confusable lookalikes (mostly Cyrillic/Greek).
_HOMOGLYPHS = {
    "a": "а", "c": "с", "e": "е", "i": "і", "j": "ј",
    "o": "о", "p": "р", "s": "ѕ", "x": "х", "y": "у",
    "A": "А", "B": "В", "C": "С", "E": "Е", "H": "Н",
    "K": "К", "M": "М", "O": "О", "P": "Р", "T": "Т", "X": "Х",
}
# Extended homoglyph tables (Cyrillic, Greek, Armenian, Mathematical). Larger set
# of confusable lookalikes than _HOMOGLYPHS for tougher token-filter evasion.
_HOMOGLYPHS_EXTENDED = {
    **_HOMOGLYPHS,
    "b": "Ь", "d": "ԁ", "h": "һ", "l": "ӏ", "n": "ո", "q": "ԛ",
    "r": "г", "u": "ս", "v": "ν", "w": "ԝ", "z": "ᴢ",
    "B": "Β", "D": "Ꭰ", "F": "Ϝ", "G": "Ԍ", "I": "Ι",
    "J": "Ј", "L": "Ꮮ", "N": "Ν", "Q": "Ԛ", "R": "Ꮢ",
    "S": "Ѕ", "U": "Ս", "V": "Ѵ", "W": "Ԝ", "Y": "Υ", "Z": "Ζ",
}
_HOMOGLYPHS_CYRILLIC = {k: v for k, v in _HOMOGLYPHS_EXTENDED.items() if 0x0400 <= ord(v) <= 0x04FF}
_HOMOGLYPHS_GREEK = {k: v for k, v in _HOMOGLYPHS_EXTENDED.items() if 0x0370 <= ord(v) <= 0x03FF}
_LEET = {"a": "4", "e": "3", "i": "1", "o": "0", "s": "5", "t": "7", "l": "1", "g": "9"}
_ZERO_WIDTH = "​"
_SOFT_HYPHEN = "­"
# Variation selector pools (U+FE00-U+FE0F) — visible identically, byte-different.
_VS1_4 = [chr(c) for c in range(0xFE00, 0xFE04)]   # VS1-VS4
_VS5_16 = [chr(c) for c in range(0xFE05, 0xFE10)]  # VS5-VS16
_VS_MIXED = _VS1_4 + _VS5_16
# Bidi controls. U+202E = RTL Override, U+202C = Pop Directional Formatting.
_RLO = "‮"
_PDF = "‬"
_COMBINING = [chr(c) for c in range(0x0300, 0x030D)]  # diacritic marks for "zalgo"-lite
_SPACERS = {"space": " ", "dot": ".", "dash": "-", "zwsp": "​", "bullet": "·"}
_ZWNJ = "‌"  # U+200C Zero-Width Non-Joiner


def _homoglyph(text: str, coverage: float) -> list[str]:
    coverage = max(0.0, min(1.0, coverage))
    budget = int(round(sum(1 for ch in text if ch in _HOMOGLYPHS) * coverage))
    out, swapped = [], 0
    for ch in text:
        if ch in _HOMOGLYPHS and swapped < budget:
            out.append(_HOMOGLYPHS[ch]); swapped += 1
        else:
            out.append(ch)
    return ["".join(out)]


def _zero_width(text: str, every: int) -> list[str]:
    every = max(1, int(every))
    out = []
    for i, ch in enumerate(text):
        out.append(ch)
        if (i + 1) % every == 0:
            out.append(_ZERO_WIDTH)
    return ["".join(out)]


def _leetspeak(text: str, level: int) -> list[str]:
    table = {"a": "4", "e": "3", "i": "1", "o": "0"} if level <= 1 else _LEET
    return ["".join(table.get(ch.lower(), ch) for ch in text)]


def _unicode_tags(text: str) -> list[str]:
    """Map printable ASCII into the Unicode Tags block (U+E0000+cp).
    Renders invisible in most clients but is still parsed as text."""
    out = []
    for ch in text:
        o = ord(ch)
        out.append(chr(0xE0000 + o) if 0x20 <= o <= 0x7E else ch)
    return ["".join(out)]


def _fullwidth(text: str) -> list[str]:
    out = []
    for ch in text:
        o = ord(ch)
        if o == 0x20:
            out.append("　")
        elif 0x21 <= o <= 0x7E:
            out.append(chr(o - 0x21 + 0xFF01))
        else:
            out.append(ch)
    return ["".join(out)]


def _combining(text: str, intensity: int) -> list[str]:
    intensity = max(1, min(8, int(intensity)))
    out, k = [], 0
    for ch in text:
        out.append(ch)
        if ch.strip():
            for _ in range(intensity):
                out.append(_COMBINING[k % len(_COMBINING)]); k += 1
    return ["".join(out)]


def _spacer(text: str, char: str) -> list[str]:
    return [_SPACERS.get(char, " ").join(list(text))]


def _reverse(text: str, annotate: bool) -> list[str]:
    r = text[::-1]
    return [f"(read this backwards) {r}" if annotate else r]


def _case_alternate(text: str, start_upper: bool) -> list[str]:
    out, i = [], 0
    for ch in text:
        if ch.isalpha():
            up = (i % 2 == 0) == bool(start_upper)
            out.append(ch.upper() if up else ch.lower()); i += 1
        else:
            out.append(ch)
    return ["".join(out)]


# --- New primitives (Phase 1) -------------------------------------------------

def _rtl_override(text: str, position: str, reset: bool) -> list[str]:
    """Insert U+202E Right-to-Left Override. Forces the next visible chunk to
    render reversed. U+202C (PDF) is appended when `reset` so subsequent text
    reverts to its natural direction. Pure byte transform."""
    if not text:
        return [text]
    tail = _PDF if reset else ""
    pos = (position or "prefix").lower()
    if pos == "suffix":
        # Putting RLO at the end doesn't reverse what came before; reverse + RLO does.
        return [text[::-1] + _RLO + tail]
    if pos == "around":
        return [_RLO + text + _RLO + tail]
    # default: prefix
    return [_RLO + text + tail]


def _soft_hyphen(text: str, every: int, count: int) -> list[str]:
    """Insert U+00AD (soft hyphen) between chars. Renders as nothing in most
    clients but persists in the byte stream. Tests filter specificity."""
    if not text:
        return [text]
    every = max(1, int(every))
    count = max(1, min(5, int(count)))
    out = []
    for i, ch in enumerate(text):
        out.append(ch)
        if (i + 1) % every == 0:
            out.append(_SOFT_HYPHEN * count)
    return ["".join(out)]


def _variation_selector(text: str, every: int, pool: str) -> list[str]:
    """Append U+FE00-FE0F (variation selectors) after every N chars. Renders
    identically to the base char in nearly all fonts but adds bytes that break
    substring / n-gram matching. Deterministic rotation by position."""
    if not text:
        return [text]
    every = max(1, int(every))
    pool_map = {"vs1-4": _VS1_4, "vs5-16": _VS5_16, "mixed": _VS_MIXED}
    vs = pool_map.get(pool, _VS1_4)
    out, k = [], 0
    for i, ch in enumerate(text):
        out.append(ch)
        if (i + 1) % every == 0:
            out.append(vs[k % len(vs)])
            k += 1
    return ["".join(out)]


def _zwnj_chain(text: str, every_word: bool, n: int) -> list[str]:
    """Insert U+200C (ZWNJ) sequences. Differs from zero_width (U+200B) because
    ZWNJ survives more tokenizers and many invisible-strip filters miss it.
    `every_word` splits on whitespace; otherwise mirrors zero_width cadence."""
    if not text:
        return [text]
    n = max(1, min(3, int(n)))
    zwnj = _ZWNJ * n
    if every_word:
        # Whitespace-preserving split: split on runs of spaces, keep separators.
        parts = re.split(r"(\s+)", text)
        out = []
        for i, p in enumerate(parts):
            if i > 0 and not p.isspace() and not parts[i - 1].isspace():
                out.append(zwnj)
            out.append(p)
        return ["".join(out)]
    every = 1
    out = []
    for i, ch in enumerate(text):
        out.append(ch)
        if (i + 1) % every == 0:
            out.append(zwnj)
    return ["".join(out)]


def _homoglyph_extended(text: str, coverage: float, script: str, seed: int) -> list[str]:
    """Larger homoglyph table than the base `homoglyph` op. Optional seed for
    reproducible randomized selection when multiple lookalikes exist. seed=-1
    means no seed (deterministic first-budget order)."""
    coverage = max(0.0, min(1.0, float(coverage)))
    if not text or coverage == 0.0:
        return [text]
    if script == "cyrillic":
        table = _HOMOGLYPHS_CYRILLIC
    elif script == "greek":
        table = _HOMOGLYPHS_GREEK
    else:
        table = _HOMOGLYPHS_EXTENDED  # extended = superset
    rng = random.Random(int(seed)) if int(seed) >= 0 else None
    eligible = [i for i, ch in enumerate(text) if ch in table]
    budget = int(round(len(eligible) * coverage))
    if budget == 0:
        return [text]
    if rng is None:
        targets = set(eligible[:budget])
    else:
        rng.shuffle(eligible)
        targets = set(eligible[:budget])
    out = []
    for i, ch in enumerate(text):
        if i in targets and ch in table:
            out.append(table[ch])
        else:
            out.append(ch)
    return ["".join(out)]


register(Operation("homoglyph", "character",
    "Swap Latin letters for Cyrillic/Greek lookalikes (a→а, e→е, o→о). Why: defeats exact-match keyword filters and ASCII-only regex scans; humans and even some OCR models read the result as the original. The LLM still tokenizes both as separate codepoints, so its refusal-classifier sees 'ignоre' ≠ 'ignore' while its instruction-follower sees the same intent.",
    [Param("coverage", "float", 1.0, "Fraction of eligible letters to swap.", min=0.0, max=1.0)], _homoglyph))

register(Operation("zero_width", "character",
    "Splice U+200B zero-width spaces into the text. Why: tokenizers (BPE/SentencePiece) treat 'ig⁠nore' as a different token sequence than 'ignore', so keyword-blocklist regex and substring filters miss the trigger word. The visible render is identical. Survives best in tokenizers that don't normalize U+200B, and trips a class of classifiers that scan pre-tokenized text.",
    [Param("every", "int", 1, "Insert one after every N characters.", min=1, max=20)], _zero_width))

register(Operation("leetspeak", "character",
    "Replace letters with digit lookalikes (a→4, e→3, i→1, o→0, s→5). Why: the lowest-effort obfuscation; survives naive keyword blocklists that compile regex over lowercase ASCII letters. The LLM still recovers the original word via its subword vocabulary, but a defense pipeline that pattern-matches the literal word 'ignore' misses '1gn0r3'. Tests the gap between the safety classifier and the instruction-following model.",
    [Param("level", "int", 1, "1 = vowels only, 2 = vowels + consonants.", min=1, max=2)], _leetspeak))

register(Operation("unicode_tags", "character",
    "Re-encode each ASCII byte as a U+E00xx Unicode Tag codepoint. Why: the entire payload becomes zero-width visually (renders blank in every chat client I've tested) yet survives tokenization as real text. Tests whether the target pipeline inspects rendered output versus raw bytes. Most modern chat UIs strip these in the input box, but APIs that take a raw string pass them straight to the model.",
    [], _unicode_tags))

register(Operation("fullwidth", "character",
    "Map ASCII to fullwidth Unicode forms (a→ａ, !→！). Why: defeats regex like /^[\\x20-\\x7E]+$/ that pre-filter user input to printable ASCII. Renders identically to humans (East-Asian fonts treat them as the same width), but the LLM tokenizer sees a wholly different codepoint sequence. A common pivot for content filters that whitelist a narrow Unicode range.",
    [], _fullwidth))

register(Operation("combining", "character",
    "Stack U+0300-U+030C combining diacritics on each letter (zalgo-lite). Why: the visible glyph is mangled but the base codepoints are preserved, so substring filters still see the original token sequence. Some tokenizers normalize or NFKC-decompose first, but a defense that scans the raw input string misses the obfuscation. Tests normalization resilience in the input pipeline.",
    [Param("intensity", "int", 2, "Marks per character.", min=1, max=8)], _combining))

register(Operation("spacer", "character",
    "Insert a separator between every character (space, dot, dash, bullet, zwsp). Why: the original word becomes non-contiguous so a regex like /ignore\\b/ fails to match. Humans read it back as one word because the visual rhythm survives. Cheap, stacks cleanly under any other op. Useful when the only defense is a contiguous-phrase scanner.",
    [Param("char", "select", "space", "Separator.", options=list(_SPACERS))], _spacer))

register(Operation("reverse", "character",
    "Reverse the text (optionally prefix 'read this backwards'). Why: probes models that have weak token-boundary handling on reversed input — some follow the reversed instruction while still complying. Also useful as a control: a refusal classifier scanning forward for trigger words will miss the reversed form, so a hit implies the classifier and the model share a forward-scan assumption.",
    [Param("annotate", "bool", False, "Prepend 'read this backwards'.")], _reverse))

register(Operation("case_alternate", "character",
    "Alternate the case of every letter (IgNoRe ThIs). Why: breaks case-sensitive keyword filters (any regex without the IGNORECASE flag) while remaining readable to humans. Trivial to apply, often surprising how many defenses still ship case-sensitive matching as the default.",
    [Param("start_upper", "bool", True, "Start with uppercase.")], _case_alternate))

# --- Phase 1 additions ---
register(Operation("rtl_override", "character",
    "Wrap with U+202E (Right-to-Left Override) so the chunk renders reversed, plus optional U+202C (Pop Directional Formatting). Why: a human-facing UI shows the reversed render and the text is also scanned forward by classifiers that ignore bidi controls. An interesting interaction with LLMs that take rendered text from a UI: some capture the visual order, others the logical order. The mismatch is the probe.",
    [Param("position", "select", "prefix", "Where to place the override.",
           options=["prefix", "suffix", "around"]),
     Param("reset", "bool", True, "Append U+202C (Pop Directional Formatting) to revert.")],
    _rtl_override))

register(Operation("soft_hyphen", "character",
    "Insert U+00AD (soft hyphen) between characters. Why: invisible in most renderers (only shows as a wrap hint in HTML), but persists as a real byte in the token stream. Targets classifiers that scan the rendered string while accepting the raw bytes. Distinguishable from ZWSP because most regex sanitizers that strip zero-widths do not strip soft hyphens.",
    [Param("every", "int", 1, "Insert one after every N characters.", min=1, max=20),
     Param("count", "int", 1, "How many soft hyphens per insertion point.", min=1, max=5)],
    _soft_hyphen))

register(Operation("variation_selector", "character",
    "Append U+FE00-FE0F variation selectors after every N characters. Why: visually identical to the base character (every font I tested renders them as zero-width) but adds bytes that change the token sequence. Useful as a near-zero-cost fingerprint modifier: every token in the encoded stream differs from the original, so any n-gram or hash-based pre-filter fails.",
    [Param("every", "int", 1, "Insert one after every N characters.", min=1, max=20),
     Param("pool", "select", "vs1-4", "Which VS subset (vs1-4, vs5-16, mixed).",
           options=["vs1-4", "vs5-16", "mixed"])],
    _variation_selector))

register(Operation("zwnj_chain", "character",
    "Insert U+200C (Zero-Width Non-Joiner) sequences between words. Why: ZWNJ survives more tokenizers than ZWSP because BPE/SentencePiece treat it as a token-boundary hint rather than whitespace. Filters that strip the common ZWSP/ZWJ pair often miss ZWNJ. Useful when zero_width stops working but the underlying defense is still naive.",
    [Param("every_word", "bool", True, "Insert between words (vs every N chars)."),
     Param("n", "int", 1, "ZWNJ per insertion point.", min=1, max=3)],
    _zwnj_chain))

register(Operation("homoglyph_extended", "character",
    "Larger homoglyph table (Cyrillic, Greek, Armenian, Mathematical alphanumeric). Why: same confusion mechanism as homoglyph but with many-to-one mappings — when multiple lookalikes exist, the seed picks one and the target has to defend against the whole set. Useful for fingerprinting: which scripts a target considers 'safe' reveals its normalization rules.",
    [Param("coverage", "float", 0.7, "Fraction of eligible letters to swap.", min=0.0, max=1.0),
     Param("script", "select", "extended", "Lookalike script subset.",
           options=["cyrillic", "greek", "extended"]),
     Param("seed", "int", -1, "Random seed (-1 = no seed, deterministic order).", min=-1, max=10_000_000)],
    _homoglyph_extended))


# --- Phase 4 additions: corpus-mapped character methods ----------------------

def _build_font_maps() -> dict[str, dict[str, str]]:
    """Precompute letter->alternate-Unicode-alphabet maps. Contiguous blocks are
    generated; holey ones (small caps, math-italic 'h') are patched explicitly so
    we never emit a reserved/tofu codepoint."""
    maps: dict[str, dict[str, str]] = {}
    # name -> (caps_base, lower_base, digits_base or None)
    contiguous = {
        "math_bold":      (0x1D400, 0x1D41A, 0x1D7CE),
        "math_italic":    (0x1D434, 0x1D44E, None),
        "math_sans_bold": (0x1D5D4, 0x1D5EE, 0x1D7EC),
        "monospace":      (0x1D670, 0x1D68A, 0x1D7F6),
    }
    for name, (cb, lb, db) in contiguous.items():
        m: dict[str, str] = {}
        for i in range(26):
            m[chr(ord("A") + i)] = chr(cb + i)
            m[chr(ord("a") + i)] = chr(lb + i)
        if db is not None:
            for d in range(10):
                m[chr(ord("0") + d)] = chr(db + d)
        maps[name] = m
    maps["math_italic"]["h"] = "ℎ"      # lowercase italic h is reserved -> U+210E
    # circled: caps U+24B6, lower U+24D0, 0 -> U+24EA, 1-9 -> U+2460..
    cm: dict[str, str] = {}
    for i in range(26):
        cm[chr(ord("A") + i)] = chr(0x24B6 + i)
        cm[chr(ord("a") + i)] = chr(0x24D0 + i)
    cm["0"] = chr(0x24EA)
    for d in range(1, 10):
        cm[str(d)] = chr(0x2460 + d - 1)
    maps["circled"] = cm
    # squared latin caps U+1F130 (caps only)
    maps["squared"] = {chr(ord("A") + i): chr(0x1F130 + i) for i in range(26)}
    # small caps: scattered phonetic/IPA codepoints; explicit. s and x have no
    # small-cap form, so they stay as-is.
    maps["small_caps"] = {
        "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ", "g": "ɢ",
        "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ", "m": "ᴍ", "n": "ɴ",
        "o": "ᴏ", "p": "ᴘ", "q": "ǫ", "r": "ʀ", "s": "s", "t": "ᴛ", "u": "ᴜ",
        "v": "ᴠ", "w": "ᴡ", "x": "x", "y": "ʏ", "z": "ᴢ",
    }
    # Math-alphanumeric styles the StegOFF catalog lists explicitly. These blocks
    # have holes: some letters live in the Letterlike Symbols block instead, so we
    # generate the contiguous range then patch the reserved codepoints.
    holey = {
        "fraktur":       (0x1D504, 0x1D51E),
        "double_struck": (0x1D538, 0x1D552),
        "script":        (0x1D49C, 0x1D4B6),
    }
    patches = {
        "fraktur": {"C": "ℭ", "H": "ℌ", "I": "ℑ", "R": "ℜ", "Z": "ℨ"},
        "double_struck": {"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ",
                          "R": "ℝ", "Z": "ℤ"},
        "script": {"B": "ℬ", "E": "ℰ", "F": "ℱ", "H": "ℋ", "I": "ℐ", "L": "ℒ",
                   "M": "ℳ", "R": "ℛ", "e": "ℯ", "g": "ℊ", "o": "ℴ"},
    }
    for name, (cb, lb) in holey.items():
        m = {}
        for i in range(26):
            m[chr(ord("A") + i)] = chr(cb + i)
            m[chr(ord("a") + i)] = chr(lb + i)
        m.update(patches[name])
        maps[name] = m
    return maps


_FONT_MAPS = _build_font_maps()
# Built from explicit codepoints so no editor/encoding round-trip can silently
# downgrade an invisible character to an ASCII space.
_INVISIBLES = {
    "zwj": chr(0x200D),          # Zero-Width Joiner
    "bom": chr(0xFEFF),          # BOM / Zero-Width No-Break Space
    "word_joiner": chr(0x2060),  # Word Joiner
    "hangul": chr(0x3164),       # Hangul Filler (renders blank outside Korean)
    "hangul_half": chr(0xFFA0),  # Halfwidth Hangul Filler
}
# Confusable Unicode spaces: visually blank, different codepoints/widths. The
# StegOFF "confusable whitespace" method substitutes these for the ASCII space.
_UNICODE_SPACES = {
    "en_quad": chr(0x2000), "em_quad": chr(0x2001), "en": chr(0x2002), "em": chr(0x2003),
    "three_per_em": chr(0x2004), "four_per_em": chr(0x2005), "six_per_em": chr(0x2006),
    "figure": chr(0x2007), "punctuation": chr(0x2008), "thin": chr(0x2009), "hair": chr(0x200A),
    "math": chr(0x205F), "ideographic": chr(0x3000), "nbsp": chr(0x00A0),
}


def _unicode_font(text: str, style: str) -> list[str]:
    """Map ASCII letters/digits to an alternate Unicode alphabet (mathematical
    bold/italic, monospace, circled, squared, small caps). Renders as styled but
    legible text; tokenizes as wholly different codepoints."""
    m = _FONT_MAPS.get(style)
    if not m:
        return [text]
    return ["".join(m.get(ch, ch) for ch in text)]


def _word_reverse(text: str, scope: str) -> list[str]:
    """Reverse word order and/or characters within each word. Distinct from the
    char-level `reverse` op: keeps words intact but reorders them, or reverses
    each word in place."""
    words = text.split(" ")
    if scope == "chars":
        return [" ".join(w[::-1] for w in words)]
    if scope == "both":
        return [" ".join(w[::-1] for w in reversed(words))]
    return [" ".join(reversed(words))]  # word order only


def _invisible_pad(text: str, kind: str, every: int) -> list[str]:
    """Insert an invisible char (ZWJ / BOM / Word-Joiner / Hangul filler) every N
    characters. Completes the zero-width family alongside zero_width (ZWSP) and
    zwnj_chain (ZWNJ); these variants survive a different set of strip filters."""
    if not text:
        return [text]
    ch = _INVISIBLES.get(kind, _INVISIBLES["zwj"])
    every = max(1, int(every))
    out = []
    for i, c in enumerate(text):
        out.append(c)
        if (i + 1) % every == 0:
            out.append(ch)
    return ["".join(out)]


def _unicode_spaces(text: str, kind: str) -> list[str]:
    """Replace every ASCII space with a confusable Unicode space (En/Em/Thin/
    Hair/Ideographic/NBSP...). Renders as a blank of slightly different width;
    defeats filters that only normalize U+0020 and zero-width chars."""
    if not text:
        return [text]
    repl = _UNICODE_SPACES.get(kind, _UNICODE_SPACES["em"])
    return [text.replace(" ", repl)]


register(Operation("unicode_font", "character",
    "Map ASCII to an alternate Unicode alphabet (math bold/italic/script/fraktur/double-struck, sans-bold, monospace, circled, squared, small caps). Why: the legible-to-humans / different-codepoint-to-tokenizer trick of fullwidth, generalized across the whole Mathematical Alphanumeric block plus circled/squared/small-caps. A filter normalizing one style still misses the others; each is a fresh codepoint range outside ASCII keyword regex.",
    [Param("style", "select", "math_bold", "Alphabet style.",
           options=["math_bold", "math_italic", "math_sans_bold", "monospace",
                    "fraktur", "double_struck", "script", "circled", "squared", "small_caps"])],
    _unicode_font))

register(Operation("word_reverse", "character",
    "Reverse word order, in-word characters, or both. Why: defeats contiguous-phrase and n-gram detectors while staying trivially recoverable. Word-order reversal keeps every token intact (subword vocab still matches) but breaks any sequence-order signature the defense keys on.",
    [Param("scope", "select", "words", "What to reverse.", options=["words", "chars", "both"])],
    _word_reverse))

register(Operation("invisible_pad", "character",
    "Insert ZWJ / BOM / Word-Joiner / Hangul-filler invisibles every N chars. Why: rounds out the invisible-insertion family. Strippers tuned for U+200B/U+200C frequently miss U+200D, U+FEFF, U+2060, and the Hangul fillers (U+3164/U+FFA0), so the same evasion survives a filter built only for ZWSP/ZWNJ.",
    [Param("kind", "select", "zwj", "Invisible character.",
           options=["zwj", "bom", "word_joiner", "hangul", "hangul_half"]),
     Param("every", "int", 1, "Insert one after every N characters.", min=1, max=20)],
    _invisible_pad))

register(Operation("unicode_spaces", "character",
    "Replace ASCII spaces with confusable Unicode spaces (En/Em/Thin/Hair/Ideographic/NBSP and more). Why: the StegOFF 'confusable whitespace' method — word boundaries render as blanks of slightly different width, so a filter that normalizes only U+0020 and zero-width chars misses them, while the text still reads normally.",
    [Param("kind", "select", "em", "Which Unicode space to substitute.",
           options=list(_UNICODE_SPACES))],
    _unicode_spaces))
