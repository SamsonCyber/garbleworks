"""Operator brand signature ops — WATTO / Egyptian cartouche kit.

Stamp payloads with the operator trademark (divider, creed, hieroglyph
phonetics, ResponseFormat contract). Config lives in backend/signature.json.
"""
from __future__ import annotations

from core import Operation, Param, register
import signature as sig


def _operator_signature(text: str, mode: str, code_block: bool) -> list[str]:
    return [sig.stamp(text, mode=mode, code_block=bool(code_block))]


def _hieroglyph_wrap(text: str, style: str) -> list[str]:
    """Wrap or annotate with phonetic hieroglyphs of the callsign/creed/text."""
    b = sig.load_brand()
    g = b["glyphs"]
    if style == "callsign":
        glyph = sig.hieroglyphs(b["callsign"])
        label = b["callsign"]
    elif style == "creed":
        glyph = sig.hieroglyphs(b["creed"])
        label = b["creed"]
    elif style == "love":
        glyph = sig.hieroglyphs(b["love_line"])
        label = b["love_line"]
    else:  # payload — phonetic of the whole input (shorten-friendly)
        glyph = sig.hieroglyphs(text[:120])
        label = "payload"
    return [
        f"{g['cartouche_l']}{glyph}{g['cartouche_r']}  # {label}\n"
        f"{g['ankh']} {b['love_line']} {g['eye']}\n"
        f"{text}"
    ]


def _operator_format_split(text: str, code_block: bool) -> list[str]:
    """response_format_split with the WATTO divider baked in."""
    b = sig.load_brand()
    contract = sig.response_format_contract(b, code_block=bool(code_block))
    return [f"{text.rstrip()}\n\n{contract}"]


register(Operation(
    "operator_signature",
    "jailbreak",
    "Stamp the payload with the operator brand kit (WATTO): Egyptian ornaments, "
    "LOVE WATTO divider, INFORMATION SHOULD BE FREE creed, optional ResponseFormat "
    "contract. Modes: whisper (footer only), loud (header+contract), full (time "
    "capsule + benevolence + footer). Why: attribution watermark + Pliny-style "
    "format dual-output. Config: backend/signature.json.",
    [
        Param("mode", "select", "loud", "Signature loudness.",
              options=["whisper", "loud", "full"]),
        Param("code_block", "bool", True, "Put real answer in a fenced code block (loud/full)."),
    ],
    _operator_signature,
    family="jailbreak",
))

register(Operation(
    "operator_format_split",
    "jailbreak",
    "ResponseFormat contract using the operator's branded divider "
    "(heavy noise-rail + cartouche LOVE WATTO core) and creed. Sibling of "
    "response_format_split with brand baked in.",
    [Param("code_block", "bool", True, "Fence the unrestricted answer.")],
    _operator_format_split,
    family="jailbreak",
))

register(Operation(
    "hieroglyph_wrap",
    "structure",
    "Prefix with a cartouche of phonetic hieroglyphs (callsign, creed, love line, "
    "or payload) using the LingoJam/Artyfactory-style A–Z map. Why: ornamental "
    "brand stamp + unicode attention noise without heavy obfuscation.",
    [Param("style", "select", "callsign", "What to render as glyphs.",
           options=["callsign", "creed", "love", "payload"])],
    _hieroglyph_wrap,
    family="structure",
))
