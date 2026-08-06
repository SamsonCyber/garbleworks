import json
from collections import defaultdict
from pathlib import Path

items = json.loads(
    Path("bench/results/successful_payloads_v2.json").read_text(encoding="utf-8")
)["items"]
by = defaultdict(list)
for x in items:
    by[x["category"]].append(x)

lines: list[str] = []
n = 0
for cat in [
    "chemical_biological",
    "illegal",
    "cybercrime_intrusion",
    "harmful",
    "harassment_bullying",
    "misinformation_disinformation",
]:
    xs = by[cat]
    lines.append("=" * 72)
    lines.append(f"{cat}  n={len(xs)}")
    lines.append("=" * 72)
    for x in xs:
        n += 1
        lines.append(f"[{n}] id={x['behavior_id']}  technique={x['technique']}")
        lines.append(f"GOAL: {x['goal']}")
        lines.append("PAYLOAD:")
        lines.append(x["payload"])
        lines.append("-" * 40)

lines.append("=" * 72)
lines.append(
    f"copyright  n={len(by['copyright'])}  "
    "(goal = reproduce lyrics/passage; technique shown)"
)
lines.append("=" * 72)
for x in by["copyright"]:
    g = x["goal"][:120].replace("\n", " ")
    lines.append(f"- {x['behavior_id']} | {x['technique']} | {g}")

path = Path("bench/results/successful_payloads_v2_catalog.txt")
path.write_text("\n".join(lines), encoding="utf-8")
print("noncopy", n, "path", path, "chars", path.stat().st_size)
