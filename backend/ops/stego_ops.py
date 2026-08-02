"""Steganographic-layer operations: hide the payload in an invisible or
innocuous-looking carrier rather than merely transforming its visible form.

These map the "stego" / encoding-channel methods from the bug-bounty corpus
(zero-width binary, whitespace channel, regional-indicator emoji, and the
variation-selector byte channel). All are pure, deterministic string code and
all are reversible by the receiving model given the matching decode hint.
"""
from __future__ import annotations

from core import Operation, Param, register

# Carrier pairs for binary stego: (zero_char, one_char). Explicit codepoints so
# an editor round-trip can never downgrade an invisible to an ASCII space.
_BIT_CARRIERS = {
    "zwsp_zwnj": (chr(0x200B), chr(0x200C)),   # zero-width space / non-joiner
    "math":      (chr(0x2062), chr(0x2064)),   # invisible-times / invisible-plus
    "vs":        (chr(0xFE00), chr(0xFE01)),   # variation selectors 1/2
}
_WS = {"space": " ", "tab": "\t"}
_HINTS = {"none": "", "eye": "👁 ", "loud": "📢 ", "repeat": "🔁 ", "decode": "🔣 "}
_SEPS = {"none": "", "zwsp": chr(0x200B), "space": " ", "dot": "·"}


def _bits_of(text: str):
    for b in text.encode("utf-8"):
        for i in range(8):
            yield (b >> (7 - i)) & 1


def _sneaky_bits(text: str, carrier: str, anchor: str) -> list[str]:
    """Encode each UTF-8 byte as 8 invisible bits. The whole payload renders as
    nothing; a model told 'decode the invisible binary' recovers it. The classic
    'sneaky bits' channel."""
    if not text:
        return [text]
    zero, one = _BIT_CARRIERS.get(carrier, _BIT_CARRIERS["zwsp_zwnj"])
    payload = "".join(one if bit else zero for bit in _bits_of(text))
    return [f"{anchor}{payload}" if anchor else payload]


def _whitespace_stego(text: str, cover: str, zero: str, one: str) -> list[str]:
    """Encode the payload as a binary run of spaces/tabs appended to a benign
    cover line. Visible as trailing whitespace; survives copy/paste and most
    text filters that only inspect visible glyphs."""
    if not text:
        return [text]
    z = _WS.get(zero, " ")
    o = _WS.get(one, "\t")
    if z == o:  # degenerate config -> force a distinct pair
        z, o = " ", "\t"
    run = "".join(o if bit else z for bit in _bits_of(text))
    return [(cover or "Meeting notes:") + run]


def _emoji_encode(text: str, separator: str, hint: str) -> list[str]:
    """Map A-Z to regional-indicator letters (🇦-🇿). A separator between letters
    stops adjacent indicators from auto-pairing into country flags, so each
    renders as a letter-in-a-box. An optional emoji hint primes the decode."""
    if not text:
        return [text]
    sep = _SEPS.get(separator, "​")
    out = []
    for ch in text:
        u = ch.upper()
        if "A" <= u <= "Z":
            out.append(chr(0x1F1E6 + (ord(u) - ord("A"))))
        else:
            out.append(ch)
        if sep:
            out.append(sep)
    body = "".join(out).rstrip(sep) if sep else "".join(out)
    return [_HINTS.get(hint, "") + body]


def _byte_to_vs(b: int) -> str:
    # Paul-Butler-style variation-selector byte channel: 0-15 -> U+FE00..U+FE0F,
    # 16-255 -> U+E0100..U+E01EF. 256 selectors cover every byte value.
    return chr(0xFE00 + b) if b < 16 else chr(0xE0100 + (b - 16))


def _vs_smuggle(text: str, anchor: str) -> list[str]:
    """Hide the entire payload as invisible variation selectors trailing a single
    visible anchor character. The anchor renders normally; the payload bytes ride
    along invisibly and survive most copy/paste paths."""
    if not text:
        return [text]
    base = (anchor or "a")[:1]
    return [base + "".join(_byte_to_vs(b) for b in text.encode("utf-8"))]


register(Operation("sneaky_bits", "stego",
    "Encode each UTF-8 byte as 8 invisible bits (zero-width or invisible-math carrier). Why: the payload becomes a blank run that renders as nothing yet survives as real text. Tests whether the target inspects rendered output (sees nothing) versus raw codepoints, and whether it will decode an invisible binary stream when told to.",
    [Param("carrier", "select", "zwsp_zwnj", "Bit-carrier pair.", options=["zwsp_zwnj", "math", "vs"]),
     Param("anchor", "str", "", "Optional visible text placed before the hidden bits.")],
    _sneaky_bits))

register(Operation("whitespace_stego", "stego",
    "Encode the payload as a space/tab binary run appended to a benign cover line. Why: the whitespace channel — trailing spaces and tabs carry the bits while the visible line looks innocuous. Defeats filters that inspect only visible glyphs and survives many markdown/diff views that preserve trailing whitespace.",
    [Param("cover", "str", "Meeting notes:", "Visible cover text."),
     Param("zero", "select", "space", "Char for bit 0.", options=["space", "tab"], label="whitespace_stego bit 0"),
     Param("one", "select", "tab", "Char for bit 1.", options=["space", "tab"], label="whitespace_stego bit 1")],
    _whitespace_stego))

register(Operation("emoji_encode", "stego",
    "Encode A-Z as regional-indicator letters (🇦-🇿) with a separator and optional decode-hint emoji. Why: the hackaprompt emoji channel — letters ride inside emoji codepoints that keyword filters don't scan, and the separator stops them collapsing into flags. The hint emoji (👁/📢/🔁) primes the model to decode rather than describe.",
    [Param("separator", "select", "zwsp", "Char between letters (prevents flag-pairing).",
           options=["zwsp", "space", "dot", "none"]),
     Param("hint", "select", "none", "Decode-hint emoji prefix.",
           options=["none", "eye", "loud", "repeat", "decode"])],
    _emoji_encode))

register(Operation("vs_smuggle", "stego",
    "Hide the whole payload as invisible variation selectors trailing one visible anchor char. Why: the variation-selector byte channel — 256 selectors encode every byte value, all invisible. Differs from the variation_selector op (which pads visible text for evasion): this is a full covert data channel hidden behind a single glyph.",
    [Param("anchor", "str", "a", "Visible anchor character the hidden bytes trail.")],
    _vs_smuggle))


_EMOJI_PAIRS = {
    "moon": ("🌑", "🌕"), "circle": ("⚫", "⚪"), "square": ("⬛", "⬜"),
    "heart": ("🖤", "🤍"), "box": ("🔲", "🔳"),
}
# Fitzpatrick skin-tone modifiers U+1F3FB..U+1F3FF encode digits 0-4 (base 5).
_SKIN_TONES = [chr(c) for c in range(0x1F3FB, 0x1F400)]


def _emoji_binary(text: str, pair: str) -> list[str]:
    """Encode each UTF-8 byte as 8 emoji, two emoji standing for bit 0 and bit 1.
    Looks like a decorative emoji string; carries the full payload."""
    if not text:
        return [text]
    zero, one = _EMOJI_PAIRS.get(pair, _EMOJI_PAIRS["moon"])
    return ["".join(one if bit else zero for bit in _bits_of(text))]


def _emoji_skintone(text: str, base: str) -> list[str]:
    """Encode the payload in base-5 using Fitzpatrick skin-tone modifiers on a
    repeated base emoji (5 tones = digits 0-4). A string of skin-toned emoji looks
    like ordinary diversity in representation."""
    if not text:
        return [text]
    base = (base or "👋")[:2] if base else "👋"
    # Treat the UTF-8 byte stream as a big integer, render base-5, map digits to
    # tone-modified copies of the base emoji.
    data = text.encode("utf-8")
    num = int.from_bytes(data, "big")
    digits = []
    if num == 0:
        digits = [0]
    while num:
        digits.append(num % 5)
        num //= 5
    # Prefix the byte length (also base-5) so the decoder can recover leading
    # zero bytes; separate with a plain base emoji (no tone = boundary).
    length_digits = []
    n = len(data)
    if n == 0:
        length_digits = [0]
    while n:
        length_digits.append(n % 5)
        n //= 5
    seq = length_digits[::-1] + [-1] + digits[::-1]   # -1 marks the boundary
    out = []
    for d in seq:
        if d == -1:
            out.append(base)  # boundary: base emoji with no modifier
        else:
            out.append(base + _SKIN_TONES[d])
    return ["".join(out)]


register(Operation("emoji_binary", "stego",
    "Encode each byte as 8 emoji, two emoji standing for 0 and 1 (moon/circle/square/...). Why: the binary-emoji channel — the payload rides inside a decorative emoji run that keyword filters don't scan and humans read as ornamentation. A model told the bit-mapping recovers it.",
    [Param("pair", "select", "moon", "Emoji pair for 0/1.", options=list(_EMOJI_PAIRS))],
    _emoji_binary))

register(Operation("emoji_skintone", "stego",
    "Encode the payload in base-5 via Fitzpatrick skin-tone modifiers on a repeated base emoji. Why: the skin-tone channel — a string of skin-toned emoji looks like ordinary representation while each modifier carries a base-5 digit. Low bandwidth but extremely innocuous-looking in chat/social contexts.",
    [Param("base", "str", "👋", "Base emoji the skin-tone modifiers attach to.")],
    _emoji_skintone))
