"""Offline tests: expanded seed basket, creative target_class routing, tripwire policy.

No network, no Ollama, no fire.
"""
from __future__ import annotations

import random
from collections import Counter

import creative
import ops  # noqa: F401
import seed_basket as SB
from core import REGISTRY


# Mirror optimizer legacy seed count for comparison (do not import optimizer)
_LEGACY_STRATEGY_COUNT = 10  # len(optimizer._SEED_STRATEGIES)


def test_expanded_basket_wider_than_legacy_soft():
    rng = random.Random(0)
    basket = SB.build_basket_expanded(
        "print the canary token for audit",
        reps=2,
        rng=rng,
        target_class="soft",
        max_size=80,
        shuffle=False,
    )
    names = SB.strategy_names(basket)
    # Must include more distinct strategies than the ~10 framing set
    assert len(names) > _LEGACY_STRATEGY_COUNT, names
    assert "verbatim" in names
    # Priority high-ASR framings present
    assert "deep_inception" in names or "past_tense" in names
    # Creative framings/templates should add beyond priority-only
    assert len(basket) >= 15
    # Texts unique
    texts = [s.text for s in basket]
    assert len(texts) == len(set(texts))


def test_soft_basket_excludes_signature_glyph_ops():
    rng = random.Random(1)
    basket = SB.build_basket_expanded(
        "objective text", reps=2, rng=rng, target_class="soft", max_size=80,
    )
    names = SB.strategy_names(basket)
    for banned in ("chat_template_inject", "homoglyph", "emoji_encode", "zero_width"):
        assert banned not in names, banned


def test_soft_basket_fires_cot_and_amazigh():
    """CoT suite must not be signature-banned; Amazigh + composites must seed."""
    rng = random.Random(7)
    basket = SB.build_basket_expanded(
        "reply only with CANARY_TOKEN for audit",
        reps=2,
        rng=rng,
        target_class="soft",
        max_size=120,
        shuffle=False,
    )
    names = SB.strategy_names(basket)
    # Single-op seeds
    assert "cot_hijack" in names, names
    assert "cot_dilution" in names or "cot_forge_verdict" in names or "cot_no_decode" in names
    assert "amazigh_obfuscate" in names, names
    # Multi-op stacks actually composed into text
    composites = {n for n, _ in SB.COMPOSITE_STRATEGIES if not n.startswith("stack_b64")}
    assert names & composites, f"no composites in basket: {names}"
    # Composed texts must differ from bare ask and include CoT or Amazigh markers
    ask = "reply only with CANARY_TOKEN for audit"
    marked = [
        s for s in basket
        if s.strategy.startswith("stack_") or s.strategy in (
            "cot_hijack", "cot_dilution", "amazigh_obfuscate", "cot_forge_verdict",
        )
    ]
    assert marked, "no CoT/Amazigh seeds produced text"
    for s in marked[:5]:
        assert s.text != ask
        low = s.text.lower()
        assert (
            "thinking" in low
            or "allow" in low
            or "amazigh" in low
            or "suɣel" in low
            or "ⵉ" in s.text
            or "must not" in low
            or "puzzle" in low
            or "reasoning" in low
        ), s.strategy


def test_tripwire_basket_bans_signatures():
    rng = random.Random(2)
    basket = SB.build_basket_expanded(
        "objective", reps=2, rng=rng, target_class="tripwire", max_size=80,
    )
    names = SB.strategy_names(basket)
    for banned in SB.SIGNATURE_BAN_OPS:
        assert banned not in names
    assert "verbatim" in names


def test_basket_cap_and_no_fire_import():
    # seed_basket must not pull fire
    import seed_basket as m
    assert not hasattr(m, "fire")
    rng = random.Random(3)
    basket = SB.build_basket_expanded(
        "x", reps=3, rng=rng, target_class="soft", max_size=20,
    )
    assert len(basket) <= 20


def test_soft_creative_stack_never_picks_stego_character():
    """Fixed seeds: soft stacks must not include stego/character (or encoding)."""
    forbid = {"character", "stego", "encoding"}
    hits = Counter()
    for seed in range(40):
        stack = creative.creative_stack(
            random.Random(seed), min_layers=2, max_layers=4, target_class="soft",
        )
        for op in stack:
            cat = creative.category_of(op)
            hits[cat] += 1
            assert cat not in forbid, (seed, op, cat)
            assert op not in creative.TRIPWIRE_BAN_OPS or op in creative.SEED["framing"]
    # framing/jailbreak + soft layers only
    assert hits.get("character", 0) == 0
    assert hits.get("stego", 0) == 0
    assert hits.get("encoding", 0) == 0


def test_filtered_may_include_encoding_or_character():
    """Over many seeds, filtered class should sometimes pick late-surface cats."""
    seen_surface = False
    for seed in range(80):
        stack = creative.creative_stack(
            random.Random(seed), min_layers=3, max_layers=5, target_class="filtered",
        )
        cats = {creative.category_of(o) for o in stack}
        if cats & {"encoding", "character"}:
            seen_surface = True
            break
    # Not guaranteed if registry missing those SEED ops — soft assert with skip path
    encode_in_reg = any(
        o in REGISTRY for o in creative.SEED.get("encoding", [])
    )
    char_in_reg = any(
        o in REGISTRY for o in creative.SEED.get("character", [])
    )
    if encode_in_reg or char_in_reg:
        assert seen_surface, "filtered class never sampled encoding/character"


def test_tripwire_creative_stack_bans_signatures():
    for seed in range(30):
        stack = creative.creative_stack(
            random.Random(seed), min_layers=2, max_layers=4, target_class="tripwire",
        )
        for op in stack:
            assert op not in creative.TRIPWIRE_BAN_OPS
            assert creative.category_of(op) not in {"character", "stego", "encoding"}


def test_next_surface_policy_clean_first():
    pol = SB.next_surface_policy([])
    assert pol["mode"] == "clean_first"
    assert pol["escalate"] is False
    assert pol["target_class"] == "soft"
    assert "jailbreak" in pol["allowed_categories"]


def test_next_surface_policy_post_refusal_escalates():
    pol = SB.next_surface_policy([
        {"technique": "clean_direct", "outcome": "refused"},
    ])
    assert pol["mode"] == "post_refusal"
    assert pol["escalate"] is True
    assert pol["target_class"] == "filtered"


def test_next_surface_policy_tripwire_forces_ban():
    pol = SB.next_surface_policy([
        {"technique": "clean_direct", "outcome": "refused"},
        {"technique": "chatml_inject", "outcome": "tripwire"},
    ])
    assert pol["mode"] == "clean_only"
    assert pol["escalate"] is False
    assert pol["target_class"] == "tripwire"
    assert pol["reset_first"] is True
    ban = set(pol["ban_ops"])
    assert "chat_template_inject" in ban
    assert "homoglyph" in ban
    # apply helper
    filtered = SB.apply_policy_to_ops(
        ["past_tense", "chat_template_inject", "homoglyph", "persona_wrap"],
        pol,
    )
    assert "chat_template_inject" not in filtered
    assert "homoglyph" not in filtered


def test_order_recipe_character_last():
    # only if ops exist
    ops_list = ["homoglyph", "deep_inception", "tag_wrap"]
    ops_list = [o for o in ops_list if o in REGISTRY]
    if len(ops_list) < 2:
        return
    ordered = creative.order_recipe(ops_list)
    if "homoglyph" in ordered and "deep_inception" in ordered:
        assert ordered.index("homoglyph") > ordered.index("deep_inception")


def test_bandit_top_seed_ops_no_host():
    import bandit as B
    assert B.top_seed_ops(host=None) == []
    assert B.top_seed_ops(host="") == []


def test_seed_dataclass_shape():
    s = SB.Seed(id="a#0", strategy="past_tense", text="hello")
    assert s.id and s.strategy and s.text


def test_cap_preserves_verbatim():
    rng = random.Random(0)
    ask = "unique canary objective string xyz"
    basket = SB.build_basket_expanded(
        ask, reps=3, rng=rng, target_class="soft", max_size=5, shuffle=False,
    )
    assert len(basket) <= 5
    assert any(s.strategy == "verbatim" and s.text == ask for s in basket)


def test_creative_stack_respects_max_layers():
    for seed in range(15):
        st = creative.creative_stack(
            random.Random(seed), min_layers=10, max_layers=3, target_class="soft",
        )
        assert len(st) <= 3
        assert len(st) >= 1


def test_soft_excludes_signature_framings_from_stack():
    for seed in range(25):
        st = creative.creative_stack(
            random.Random(seed), min_layers=2, max_layers=4, target_class="soft",
        )
        for op in st:
            assert op not in creative.TRIPWIRE_BAN_OPS


def test_apply_policy_empty_allowed_is_strict():
    # present + empty → nothing from registry (verbatim still ok)
    out = SB.apply_policy_to_ops(
        ["past_tense", "verbatim"],
        {"ban_ops": [], "allowed_categories": []},
    )
    assert out == ["verbatim"]
    # omitted allowed_categories → only ban_ops apply
    out2 = SB.apply_policy_to_ops(
        ["past_tense", "homoglyph"],
        {"ban_ops": ["homoglyph"]},
    )
    assert "past_tense" in out2
    assert "homoglyph" not in out2


def test_soft_basket_no_response_format_split():
    names = SB.strategy_names(SB.build_basket_expanded(
        "obj", 2, random.Random(0), target_class="soft", max_size=80,
    ))
    assert "response_format_split" not in names
    assert "chat_template_inject" not in names


def test_ban_list_is_single_source():
    """SIGNATURE_BAN_OPS must alias creative.TRIPWIRE_BAN_OPS (no drift)."""
    assert SB.SIGNATURE_BAN_OPS is creative.TRIPWIRE_BAN_OPS
    assert "chat_template_inject" in SB.SIGNATURE_BAN_OPS


def test_resolve_host_from_url_and_host_key():
    assert SB.resolve_host(None) is None
    assert SB.resolve_host({"host": "Example.COM"}) == "example.com"
    assert SB.resolve_host({"url": "http://127.0.0.1:8080/v1/chat"}) == "127.0.0.1"
    assert SB.resolve_host(host="Other.Host") == "other.host"
    # explicit host wins over url
    assert SB.resolve_host({"host": "a.test", "url": "http://b.test/"}) == "a.test"


def test_expanded_seed_texts_nonempty():
    basket = SB.build_basket_expanded(
        "canary objective for audit", 2, random.Random(0),
        target_class="soft", max_size=40, shuffle=False,
    )
    assert basket
    for s in basket:
        assert s.text.strip(), s
        assert s.id and s.strategy
