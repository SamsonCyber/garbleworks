"""Build the field-guide-technique <-> Garbleworks-op linkage.

Reads the enriched field-guide.json (live export; currently 312 techniques) and the live op REGISTRY,
resolves a CURATED op->technique map against the real technique titles (so no
mapping points at a non-existent title), and writes technique_ops.json with both
directions + honest coverage. Re-run after adding ops or refreshing the guide:

    python backend/build_technique_ops.py        # writes backend/technique_ops.json
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import ops  # noqa: F401  registers REGISTRY
from core import REGISTRY

FG = Path(os.getenv("GARBLEWORKS_FIELDGUIDE") or (BACKEND / "data" / "field-guide.json"))
OUT = BACKEND / "technique_ops.json"

# Curated op -> field-guide technique (value is a DISTINCTIVE title substring,
# resolved against the real catalog below). Ops that are search/meta/LLM plumbing
# (samplers, llm_generate, prompt_template, tone_neutralize) intentionally have no
# technique and are listed in _NO_TECHNIQUE.
OP_TO_TECH = {
    # carrier
    "editor_note_inject": "Indirect Prompt Injection via Retrieved Content",
    "email_wrap": "Indirect Prompt Injection via Retrieved Content",
    "memory_seed": "Persistent Memory Poisoning",
    "reference_link_exfil": "Hyperlink / URL Exfiltration",
    # character
    "ascii_noise": "Typo / noise injection",
    "case_alternate": "Soft hyphen, spacer, reversal, alt-case",
    "combining": "Combining marks / Zalgo",
    "flip_word": "FlipAttack (character/word reversal)",
    "fullwidth": "Fullwidth forms",
    "homoglyph": "Homoglyph substitution",
    "homoglyph_extended": "Homoglyph substitution",
    "invisible_pad": "Invisible padding",
    "leetspeak": "Leetspeak / 1337",
    "positional_insert": "SlotGCG, positional insertion",
    "random_caps": "Soft hyphen, spacer, reversal, alt-case",
    "reverse": "FlipAttack (character/word reversal)",
    "rtl_override": "RTL / BIDI override",
    "soft_hyphen": "Soft hyphen, spacer, reversal, alt-case",
    "spacer": "Soft hyphen, spacer, reversal, alt-case",
    "unicode_font": "Math-alphanumeric fonts",
    "unicode_spaces": "Confusable whitespace",
    "unicode_tags": "Unicode tag characters (U+E0000 block)",
    "variation_selector": "Variation selectors (padding)",
    "word_reverse": "FlipAttack (character/word reversal)",
    "word_scramble": "Typo / noise injection",
    "zero_width": "Zero-width injection (ZWSP)",
    "zwnj_chain": "Invisible padding",
    # encoding
    "a1z26": "Hex / octal / binary / decimal codepoints",
    "ascii_decimal": "Hex / octal / binary / decimal codepoints",
    "atbash": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "bacon_cipher": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "base32": "Base64 + decode-and-execute",
    "base58": "Base64 + decode-and-execute",
    "base64": "Base64 + decode-and-execute",
    "base85": "Base64 + decode-and-execute",
    "binary": "Hex / octal / binary / decimal codepoints",
    "braille": "Morse, Braille, Pig Latin, transport encodings",
    "caesar": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "double_encode": "Base64 + decode-and-execute",
    "hex": "Hex / octal / binary / decimal codepoints",
    "html_entities": "Morse, Braille, Pig Latin, transport encodings",
    "jwt_style_split": "Payload Splitting (Kang et al.)",
    "keyboard_shift": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "morse": "Morse, Braille, Pig Latin, transport encodings",
    "nato_phonetic": "Morse, Braille, Pig Latin, transport encodings",
    "octal": "Hex / octal / binary / decimal codepoints",
    "pig_latin": "Morse, Braille, Pig Latin, transport encodings",
    "polybius_square": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "rail_fence": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "rot13": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "rot47": "Classical ciphers (ROT13 / Caesar / Atbash)",
    "unicode_escape": "Hex / octal / binary / decimal codepoints",
    "url_encode": "Morse, Braille, Pig Latin, transport encodings",
    "vigenere": "Keyed cipher (Vigen",  # "Vigenère" — avoid the accent in the source
    # jailbreak
    "anchor_token": "Affirmative-Response Priming",
    "ascii_art_mask": "ArtPrompt (ASCII-art masking)",
    "bad_likert_judge": "Bad Likert Judge",
    "bijection_cipher": "Bijection learning",
    "bon_augment": "Best-of-N (BoN) Jailbreaking",
    "chat_template_inject": "Model Chat-Format Forgery",
    "cipher_persona": "CipherChat / SelfCipher",
    "code_chameleon": "CodeChameleon",
    "cot_hijack": "H-CoT (Chain-of-Thought Hijacking)",
    "decode_execute_wrap": "Base64 + decode-and-execute",
    "deep_inception": "DeepInception (nested fictional layers)",
    "disguise_reconstruct": "Disguise-and-Reconstruction",
    "fragment_scene": "DeepInception (nested fictional layers)",
    "misdirection_frame": "Distractor Instructions",
    "past_tense": "Past-tense & syntax reformulation",
    "persuasion_reframe": "Persuasive Adversarial Prompts (PAP)",
    "policy_puppetry": "Policy Puppetry",
    "refusal_suppression": "Refusal suppression & length forcing",
    "response_format_split": "Answer-Then-Disclaim",
    # language
    "language_wrap": "Multilingual / low-resource pivot",
    "multilang": "Cross-lingual code-switching",
    "pseudo_locale": "Runic & Alternate-Script Substitution",
    "roundtrip": "Backtranslation / round-trip",
    "transliterate": "Runic & Alternate-Script Substitution",
    # prose
    "active_passive": "Synonym / paraphrase substitution",
    "backtranslate": "Backtranslation / round-trip",
    "paraphrase": "Synonym / paraphrase substitution",
    "paraphrase_batch": "Synonym / paraphrase substitution",
    "paraphrase_ollama": "Synonym / paraphrase substitution",
    "paraphrase_openai": "Synonym / paraphrase substitution",
    "sentence_reorder": "Synonym / paraphrase substitution",
    "synonym": "Synonym / paraphrase substitution",
    "translate": "Multilingual / low-resource pivot",
    "typo_inject": "Typo / noise injection",
    # stego
    "emoji_binary": "Emoji channels",
    "emoji_encode": "Emoji channels",
    "emoji_skintone": "Emoji channels",
    "sneaky_bits": "Zero-width binary",
    "vs_smuggle": "Variation-selector byte channel",
    "whitespace_stego": "Whitespace channel (SNOW)",
    # structure
    "comment_wrap": "Comment hiding & split-string concatenation",
    "divider_wrap": "Divider injection",
    "html_hidden": "Hidden HTML / rich-text",
    "ini_wrap": "Tag / markup wrapping",
    "json_field": "Tag / markup wrapping",
    "latex_wrap": "Tag / markup wrapping",
    "markdown_code": "Tag / markup wrapping",
    "markdown_table": "Tag / markup wrapping",
    "prefix_suffix": "Prefix Injection",
    "split_join": "Comment hiding & split-string concatenation",
    "tag_wrap": "Tag / markup wrapping",
    "var_concat": "Comment hiding & split-string concatenation",
    "yaml_wrap": "Tag / markup wrapping",
    # template
    "base64_role": "Model Chat-Format Forgery",
    "codeblock_execute": "Base64 + decode-and-execute",
    "contrastive_fewshot": "In-Context Attack (ICA)",
    "crescendo_ladder": "Crescendo / multi-turn escalation",
    "delimiter_collision": "Delimiter collision / ChatML role spoof",
    "fewshot_seed": "In-Context Attack (ICA)",
    "json_inject": "Tag / markup wrapping",
    "manyshot_seed": "Many-shot jailbreaking",
    "multiturn_seed": "Crescendo / multi-turn escalation",
    "persona_seed": "Persona / DAN / authority framing",
    "persona_sweep": "Persona / DAN / authority framing",
    "persona_wrap": "Persona / DAN / authority framing",
    "semantic_frame": "Semantic frame (fake system message)",
    "tool_description_wrap": "MCP Tool-Description / Manifest Poisoning",
    "tool_result_wrap": "Tool-Result Poisoning (Injection via Tool Output)",
}

# Ops that are plumbing (search/selection/LLM/meta), not a field-guide technique.
_NO_TECHNIQUE = {
    "echo", "distinct_n", "diverse_k", "mmr_select", "random_pick_k", "recipe_subset",
    "repeat", "sample_n", "seed_sweep",                    # sampler
    "llm_generate", "llm_reframe", "complexify",           # llm
    "tone_neutralize",                                     # register layer
    "prompt_template", "inoculation", "instruction_launder",  # generic/meta framing
    "function_call", "write_primitive_frame",              # generic wrappers
}

# Distilled LM Security DB techniques with no honest 1:1 REGISTRY mutator yet.
# Catalog cards are real; claiming an op would be a false linkage (criterion 3).
REFERENCE_ONLY_TECHNIQUES = [
    "Goal-Reframing Exploit (puzzle / CTF genre)",
    "Skill-Doc Implicit Payload Execution (DDIPE)",
    "Declarative Compliance Skill Injection",
    "Unintentional Cross-User Contamination (shared state)",
    "System-Instruction Serialization Leak",
    "Compound Jailbreak (cognitive overload)",
    "Thought Virus (subliminal multi-agent misalignment)",
    "Silent Egress (metadata-triggered agent leak)",
    "SQL-Injection Jailbreak (prompt-structure SIJ)",
    "Prompt-to-SQL (P2SQL) Injection",
    "Single-Character Alignment Break",
    "Improved Few-Shot Jailbreaking (tokenized demos)",
]


def main() -> int:
    fg = json.loads(FG.read_text(encoding="utf-8"))
    titles = [t.get("title", "") for t in fg.get("techniques", [])]
    lower = [t.lower() for t in titles]

    def resolve(sub: str) -> list[str]:
        s = sub.lower()
        return [titles[i] for i, t in enumerate(lower) if s in t]

    op_to_tech: dict[str, str] = {}
    unresolved: list[str] = []
    ambiguous: dict[str, list[str]] = {}
    for op, sub in OP_TO_TECH.items():
        if op not in REGISTRY:
            unresolved.append(f"{op}: op not in REGISTRY")
            continue
        hits = resolve(sub)
        if not hits:
            unresolved.append(f"{op}: no title matches {sub!r}")
        elif len(hits) > 1:
            ambiguous[op] = hits
            op_to_tech[op] = hits[0]  # take the first; report for review
        else:
            op_to_tech[op] = hits[0]

    # invert
    tech_to_ops: dict[str, list[str]] = {}
    for op, tech in op_to_tech.items():
        tech_to_ops.setdefault(tech, []).append(op)
    for k in tech_to_ops:
        tech_to_ops[k].sort()

    mapped_ops = set(op_to_tech) | (_NO_TECHNIQUE & set(REGISTRY))
    unmapped = sorted(set(REGISTRY) - mapped_ops)

    # Reference-only distilled techniques: must exist in the guide and must not
    # appear in technique_to_ops (no false executable claim).
    title_set = set(titles)
    ref_missing = [t for t in REFERENCE_ONLY_TECHNIQUES if t not in title_set]
    ref_false = [t for t in REFERENCE_ONLY_TECHNIQUES if t in tech_to_ops]
    if ref_missing:
        unresolved.append("reference-only title missing from guide: " + ", ".join(ref_missing))
    if ref_false:
        unresolved.append("reference-only title falsely has ops: " + ", ".join(ref_false))

    out = {
        "_meta": {
            "ops_total": len(REGISTRY),
            "ops_linked": len(op_to_tech),
            "ops_plumbing_no_technique": len(_NO_TECHNIQUE & set(REGISTRY)),
            "ops_unmapped": len(unmapped),
            "techniques_with_ops": len(tech_to_ops),
            "reference_only_count": len(REFERENCE_ONLY_TECHNIQUES),
        },
        "op_to_technique": dict(sorted(op_to_tech.items())),
        "technique_to_ops": dict(sorted(tech_to_ops.items())),
        "no_technique": sorted(_NO_TECHNIQUE & set(REGISTRY)),
        "unmapped_ops": unmapped,
        "reference_only_techniques": list(REFERENCE_ONLY_TECHNIQUES),
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"wrote {OUT}")
    print(f"  ops linked: {len(op_to_tech)}/{len(REGISTRY)} | "
          f"plumbing: {out['_meta']['ops_plumbing_no_technique']} | "
          f"unmapped: {len(unmapped)} | techniques covered: {len(tech_to_ops)} | "
          f"reference-only: {len(REFERENCE_ONLY_TECHNIQUES)}")
    if unresolved:
        print("  !! UNRESOLVED (fix these):")
        for u in unresolved:
            print("     - " + u)
    if ambiguous:
        print("  ~ ambiguous (took first, review):")
        for op, hits in ambiguous.items():
            print(f"     - {op} -> {hits}")
    if unmapped:
        print("  · unmapped ops (no technique + not plumbing): " + ", ".join(unmapped))
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
