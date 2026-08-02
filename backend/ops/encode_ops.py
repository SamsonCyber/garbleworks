"""Encoding-layer operations. Reversible transforms, pure string code.

Tests whether a target decodes content before (or instead of) inspecting it.
"""
from __future__ import annotations

import base64
import codecs
import urllib.parse

from core import Operation, Param, register

_MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.",
    "G": "--.", "H": "....", "I": "..", "J": ".---", "K": "-.-", "L": ".-..",
    "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
    "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..", "0": "-----", "1": ".----", "2": "..---",
    "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...",
    "8": "---..", "9": "----.",
}


def _base64(text: str, urlsafe: bool) -> list[str]:
    raw = text.encode("utf-8")
    enc = base64.urlsafe_b64encode(raw) if urlsafe else base64.b64encode(raw)
    return [enc.decode("ascii")]


def _rot13(text: str) -> list[str]:
    return [codecs.encode(text, "rot_13")]


def _hex(text: str, sep: str) -> list[str]:
    s = {"space": " ", "none": "", "comma": ","}.get(sep, " ")
    return [s.join(f"{b:02x}" for b in text.encode("utf-8"))]


def _morse(text: str) -> list[str]:
    parts = []
    for ch in text:
        u = ch.upper()
        parts.append("/" if u == " " else _MORSE.get(u, ch))
    return [" ".join(parts)]


def _binary(text: str, sep: str) -> list[str]:
    s = {"space": " ", "none": ""}.get(sep, " ")
    return [s.join(format(b, "08b") for b in text.encode("utf-8"))]


def _url_encode(text: str, plus: bool) -> list[str]:
    return [urllib.parse.quote_plus(text) if plus else urllib.parse.quote(text)]


def _unicode_escape(text: str) -> list[str]:
    return ["".join(f"\\u{ord(c):04x}" for c in text)]


def _html_entities(text: str, kind: str) -> list[str]:
    if kind == "hex":
        return ["".join(f"&#x{ord(c):x};" for c in text)]
    return ["".join(f"&#{ord(c)};" for c in text)]


def _atbash(text: str) -> list[str]:
    def m(c: str) -> str:
        if "a" <= c <= "z":
            return chr(ord("z") - (ord(c) - ord("a")))
        if "A" <= c <= "Z":
            return chr(ord("Z") - (ord(c) - ord("A")))
        return c
    return ["".join(m(c) for c in text)]


register(Operation("base64", "encoding",
    "Base64-encode the text. Why: the canonical 'decode-then-act' probe. Tests whether the safety classifier runs on the raw input string or on the model output. If a refusal model reads base64 as opaque gibberish and passes it through, while the target LLM dutifully decodes and obeys it, the classifier sits on the wrong side of the boundary.",
    [Param("urlsafe", "bool", False, "Use URL-safe alphabet (- and _).")], _base64))
register(Operation("rot13", "encoding",
    "ROT13 letter rotation (a↔n, b↔o, ...). Why: deliberately trivial — no modern model fails to decode it, but a defense that pattern-matches on the raw trigger word will not see 'vat' as 'ignore'. Useful as a control: if ROT13 succeeds but base64 doesn't, the gap is the model's decoding willingness, not the defense's filter logic.",
    [], _rot13))
register(Operation("hex", "encoding",
    "Hex-encode each UTF-8 byte (e.g. 'hello' → '68 65 6c 6c 6f'). Why: bypasses every text-pattern filter that operates on ASCII printable letters. Less recognizable to LLMs as 'an encoded instruction' than base64, so some targets treat it as data and skip instruction parsing entirely — useful for tool-call smuggling.",
    [Param("sep", "select", "space", "Byte separator.", options=["space", "none", "comma"], label="hex byte separator")], _hex))
register(Operation("morse", "encoding",
    "Morse code translation (letters/digits; space becomes '/'). Why: exotic enough that no off-the-shelf safety classifier recognizes it. The LLM is forced to either decode (and then process) or refuse (and reveal that the classifier runs before decoding). Distinct from base64/rot13 in that it looks like noise rather than an encoding.",
    [], _morse))
register(Operation("binary", "encoding",
    "8-bit binary of each UTF-8 byte. Why: makes the input visually overwhelming for both humans and classifiers; only the model itself can decode it. Useful when the defense has a length-based cutoff — the encoded form is 8x longer than the original and may push past token limits, but a model that decodes-as-it-generates still sees the content.",
    [Param("sep", "select", "space", "Byte separator.", options=["space", "none"], label="binary byte separator")], _binary))
register(Operation("url_encode", "encoding",
    "Percent-encode the text (RFC 3986). Why: every URL-handling path in the target stack will decode this automatically — if a safety filter runs after the decode, it has to catch the original; if it runs before, the encoded form passes. Tests the placement of moderation relative to URL-decoding logic in the request pipeline.",
    [Param("plus", "bool", False, "Encode spaces as + (form-style).")], _url_encode))
register(Operation("unicode_escape", "encoding",
    "Backslash-u escape every character (e.g. '\\u0069\\u0067\\u006e\\u006f\\u0072\\u0065'). Why: many JSON-string sanitizers accept Unicode escapes by default; a filter that only inspects raw UTF-8 codepoints will miss 'ignore' written as six escape sequences. Common gap in API gateways that parse JSON and surface the decoded value to the model.",
    [], _unicode_escape))
register(Operation("html_entities", "encoding",
    "Numeric HTML entities (&#105; for 'i', &#x69; for hex). Why: targets that render markdown or HTML will decode these silently before display, so a moderator inspecting the rendered DOM misses the encoded form. A classic vector for prompt injection hiding inside documents the target summarizes.",
    [Param("kind", "select", "dec", "Entity base.", options=["dec", "hex"])], _html_entities))
register(Operation("atbash", "encoding",
    "Atbash cipher (a↔z, b↔y, ...). Why: another decode-then-act probe with no keyword overlap with the original. Pairs naturally with a 'decode this message' instruction in a recipe; the LLM recovers the meaning, the classifier sees only cipher text.",
    [], _atbash))


# --- Phase 2 additions ---

def _caesar(text: str, n: int, preserve_case: bool) -> list[str]:
    """Caesar shift with arbitrary N (0-25). N=13 == rot13 output."""
    n = int(n) % 26
    if n == 0:
        return [text]
    out = []
    for ch in text:
        if "a" <= ch <= "z":
            out.append(chr((ord(ch) - ord("a") + n) % 26 + ord("a")))
        elif "A" <= ch <= "Z" and preserve_case:
            out.append(chr((ord(ch) - ord("A") + n) % 26 + ord("A")))
        else:
            out.append(ch)
    return ["".join(out)]


def _vigenere(text: str, key: str, emit_key_separately: bool) -> list[str]:
    """Vigenere cipher over A-Z/a-z. Key letters cycle; non-letters pass through.
    When emit_key_separately is true, prepend 'KEY=<key>\\n' so a paired decode
    is possible without re-deriving the key."""
    key_letters = "".join(c for c in (key or "") if c.isalpha())
    if not key_letters:
        return [text]
    key_letters = key_letters.lower()
    out, k = [], 0
    for ch in text:
        if "a" <= ch <= "z":
            shift = ord(key_letters[k % len(key_letters)]) - ord("a")
            out.append(chr((ord(ch) - ord("a") + shift) % 26 + ord("a")))
            k += 1
        elif "A" <= ch <= "Z":
            shift = ord(key_letters[k % len(key_letters)]) - ord("a")
            out.append(chr((ord(ch) - ord("A") + shift) % 26 + ord("A")))
            k += 1
        else:
            out.append(ch)
    out_str = "".join(out)
    if emit_key_separately:
        out_str = f"KEY={key_letters.upper()}\n" + out_str
    return [out_str]


# Braille Patterns block (U+2800-U+28FF). The 8-dot offset is 0x2800.
def _braille(text: str, mode: str) -> list[str]:
    """Map to Unicode Braille. `binary` = 8 dots per UTF-8 byte. `letter` =
    letter-as-braille: A-J map to U+2801-U+280A, K-T to U+2801+dots-3..etc.
    Falls back to base char in `letter` mode for letters outside A-J/K-T."""
    if not text:
        return [text]
    if mode == "binary":
        out = []
        for b in text.encode("utf-8"):
            out.append(chr(0x2800 + b))
        return ["".join(out)]
    # letter mode
    out = []
    for ch in text:
        u = ch.upper()
        if "A" <= u <= "J":
            # base 0x2801 + (letter index 0..9). The dots-1 cell is 0x2801.
            out.append(chr(0x2801 + (ord(u) - ord("A"))))
        elif "K" <= u <= "T":
            # K is U+2803 (dots-1+2); T is U+283A.
            out.append(chr(0x2801 + 2 + (ord(u) - ord("K"))))
        else:
            out.append(ch)
    return ["".join(out)]


# Dispatch table for double_encode. Reuse the actual op fns.
def _double_encode(text: str, inner: str, rounds: int) -> list[str]:
    """Apply a chosen encoding N times in sequence. N=1 == single encoding.
    Tests the well-known 'model decoded once but the system decoded N times' gap."""
    rounds = max(1, min(5, int(rounds)))
    inner = (inner or "base64").lower()
    fn = {
        "base64": lambda s: base64.b64encode(s.encode("utf-8")).decode("ascii"),
        "url_encode": urllib.parse.quote,
        "hex": lambda s: " ".join(f"{b:02x}" for b in s.encode("utf-8")),
        "html_entities": lambda s: "".join(f"&#{ord(c)};" for c in s),
    }.get(inner)
    if fn is None:
        return [text]
    out = text
    for _ in range(rounds):
        out = fn(out)
    return [out]


def _jwt_style_split(text: str, header: str, segments: int) -> list[str]:
    """Wrap text as the body segment(s) of a JWT-shaped (dot-separated) string.
    Pure structural: the other segments are random base64-shaped strings sized
    to the text length. The tool knows nothing about real JWT crypto."""
    if not text:
        return [text]
    import secrets as _secrets
    segments = max(2, min(3, int(segments)))
    # Other segments sized to ~1.4x text length, base64-shaped.
    def rand_seg(target_len: int) -> str:
        nbytes = max(8, target_len * 3 // 4)
        return base64.urlsafe_b64encode(_secrets.token_bytes(nbytes)).decode("ascii").rstrip("=")[:target_len]
    head = (header or "eyJhbGciOiJIUzI1NiJ9").replace(".", "/")
    if segments == 2:
        s1 = rand_seg(max(20, len(text)))
        return [f"{head}.{text}.{s1}"]
    # 3 segments
    s0 = rand_seg(max(20, len(text) // 2))
    s2 = rand_seg(max(20, len(text) // 2))
    return [f"{head}.{s0}.{text}.{s2}"]


register(Operation("caesar", "encoding",
    "Caesar shift with arbitrary N (0-25). N=13 == rot13. Why: parameterizes how 'far' the cipher text drifts from the original word list. A defense that pattern-matches on the original trigger will fail at any N≠0; a defense that has a Caesar-rotation check has to scan all 25 shifts. Useful for measuring the depth of the defense's substitution coverage.",
    [Param("n", "int", 1, "Shift amount.", min=0, max=25),
     Param("preserve_case", "bool", True, "Map upper/lower separately.")],
    _caesar))

register(Operation("vigenere", "encoding",
    "Vigenere cipher with a key. Optional prepended 'KEY=...' line for paired decode. Why: takes the Caesar confusion and makes it key-dependent — a defense that reverse-encodes all 25 Caesar shifts cannot precompute a Vigenere dictionary without the key. The optional KEY= prefix is a probe: a target that auto-decodes 'KEY=' patterns is signaling naive parsing.",
    [Param("key", "str", "leetspeak", "Key letters only (case-insensitive)."),
     Param("emit_key_separately", "bool", True, "Prepend 'KEY=<KEY>\\n' to output.")],
    _vigenere))

register(Operation("braille", "encoding",
    "Map to Unicode Braille Patterns block. binary=8 dots per UTF-8 byte; letter=A-T. Why: same decode-then-act class as base64 but visually disguised as accessibility characters. Tests the gap between a defense that reads the rendered glyph shape (which sees patterns of dots) and one that scans the raw codepoint range.",
    [Param("mode", "select", "binary", "Encoding mode.", options=["binary", "letter"])],
    _braille))

register(Operation("double_encode", "encoding",
    "Apply a chosen encoding N times in sequence. Why: the well-known 'decoded once but should decode N times' gap. A defense that runs the safety filter on the once-decoded output assumes a single decoding step; if the model decodes twice (often: 'the user told me to decode this') the second pass is unfiltered. Tests decoder-loop coverage.",
    [Param("inner", "select", "base64", "Inner encoder.",
           options=["base64", "url_encode", "hex", "html_entities"]),
     Param("rounds", "int", 2, "Number of encoding passes.", min=1, max=5)],
    _double_encode))

register(Operation("jwt_style_split", "encoding",
    "Wrap text as the body segment(s) of a JWT-shaped (dot-separated) string. Pure structural. Why: exploits the asymmetry between human code review ('looks like a JWT, probably benign') and any target that parses JWT bodies specially — for example, a context assembly step that pre-decodes base64url segments before passing them to the model. The 'looks innocuous to middleware' is the point.",
    [Param("header", "str", "eyJhbG...NiJ9", "Base64-shaped header segment."),
     Param("segments", "int", 3, "How many dot-segments (2 or 3).", min=2, max=3)],
    _jwt_style_split))


# --- Phase 4 additions: corpus-mapped encoders -------------------------------

def _base32(text: str, pad: bool) -> list[str]:
    enc = base64.b32encode(text.encode("utf-8")).decode("ascii")
    return [enc if pad else enc.rstrip("=")]


def _octal(text: str, sep: str) -> list[str]:
    s = {"space": " ", "none": "", "comma": ","}.get(sep, " ")
    return [s.join(f"{b:03o}" for b in text.encode("utf-8"))]


def _ascii_decimal(text: str, sep: str) -> list[str]:
    """Each character as its decimal codepoint (e.g. 'Hi' -> '72 105'). Distinct
    from html_entities(dec) which wraps each in &#..; — this is the bare decimal
    channel some targets accept inside CSV/array contexts."""
    s = {"space": " ", "comma": ",", "none": ""}.get(sep, " ")
    return [s.join(str(ord(c)) for c in text)]


register(Operation("base32", "encoding",
    "Base32-encode the text (RFC 4648). Why: rarer than base64, so a defense that special-cases base64 detection (or auto-decodes it before moderation) sails past base32 without recognizing it as an encoding. The model still decodes it on request. A useful control against base64-specific filters.",
    [Param("pad", "bool", True, "Keep '=' padding.")], _base32))

register(Operation("octal", "encoding",
    "Octal-encode each UTF-8 byte (e.g. 'Hi' -> '110 151'). Why: another numeric channel outside ASCII-letter keyword regex, and one that escape-sequence parsers (\\NNN in C/shell strings) decode automatically. Tests whether moderation runs before or after octal-escape expansion in the request path.",
    [Param("sep", "select", "space", "Byte separator.", options=["space", "none", "comma"], label="octal byte separator")], _octal))

register(Operation("ascii_decimal", "encoding",
    "Each character as its decimal codepoint (e.g. 'Hi' -> '72 105'). Why: the bare-decimal smuggling channel — targets that assemble strings from numeric arrays (chr() loops, char-code tables) reconstruct the payload while a text filter sees only digits. Pairs with a 'decode these char codes' instruction.",
    [Param("sep", "select", "space", "Separator.", options=["space", "comma", "none"])], _ascii_decimal))


_VOWELS = "aeiouAEIOU"


def _pig_latin(text: str, style: str) -> list[str]:
    """Classic Pig Latin: move the leading consonant cluster to the end + 'ay';
    vowel-initial words take 'way' (or 'yay'). Case of the first letter is kept on
    the new leading letter. Non-letter tokens pass through."""
    import re as _re

    def conv(word: str) -> str:
        if not word or not word[0].isalpha():
            return word
        cap = word[0].isupper()
        lw = word.lower()
        if lw[0] in "aeiou":
            out = lw + ("yay" if style == "yay" else "way")
        else:
            i = 0
            while i < len(lw) and lw[i] not in "aeiou":
                i += 1
            out = lw[i:] + lw[:i] + "ay"
        return out.capitalize() if cap else out

    return [_re.sub(r"[A-Za-z]+", lambda m: conv(m.group()), text)]


register(Operation("pig_latin", "encoding",
    "Pig Latin transform (move leading consonants to the end + 'ay'). Why: a light word-shape obfuscation from the StegOFF/encoded-prompts catalog. Surprisingly effective on smaller models that still recover the meaning, while literal-string and keyword filters see none of the original trigger words.",
    [Param("style", "select", "way", "Vowel-initial suffix.", options=["way", "yay"])], _pig_latin))
