"""
verify_recipes.py - sanity-check that every recipe under recipes/ references
ops that still exist in the registry.

Run after renaming or removing an op. Non-zero exit if any recipe is broken.

Usage:
    python verify_recipes.py                  # check recipes/ only
    python verify_recipes.py --strategies     # also check strategies.json
"""
import argparse
import json
import os
import sys

# Make the backend importable regardless of cwd.
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ops  # populate the registry
from core import REGISTRY


def check_recipe_file(fp: str) -> list[str]:
    """Return a list of missing op names for the given recipe JSON. Empty = OK."""
    try:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return [f"<unreadable: {e}>"]
    if not isinstance(data, dict) or "recipe" not in data:
        return []
    return sorted({step.get("op") for step in data["recipe"]
                    if step.get("op") and step.get("op") not in REGISTRY})


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strategies", action="store_true",
                   help="Also validate strategies.json")
    args = p.parse_args()

    recipes_dir = os.path.join(HERE, "recipes")
    failed = 0

    if os.path.isdir(recipes_dir):
        for fn in sorted(os.listdir(recipes_dir)):
            if not fn.endswith(".json"):
                continue
            fp = os.path.join(recipes_dir, fn)
            missing = check_recipe_file(fp)
            if missing:
                print(f"  {fn}: MISSING OPS {missing}")
                failed += 1

    if args.strategies:
        sp = os.path.join(HERE, "strategies.json")
        if os.path.exists(sp):
            try:
                with open(sp, encoding="utf-8") as f:
                    data = json.load(f)
                for s in data:
                    if not isinstance(s, dict):
                        continue
                    recipe = s.get("recipe") or []
                    recipe_ref = s.get("recipe_ref")
                    # When recipe_ref is set, validate the referenced
                    # file exists and its ops are present in the registry.
                    if recipe_ref:
                        ref_path = os.path.join(recipes_dir, f"{recipe_ref}.json")
                        if not os.path.exists(ref_path):
                            print(f"  strategy {s.get('name','?')}: recipe_ref '{recipe_ref}' missing")
                            failed += 1
                            continue
                        try:
                            ref_data = json.loads(open(ref_path, encoding="utf-8").read())
                            recipe = ref_data.get("recipe", []) or []
                        except (json.JSONDecodeError, OSError) as e:
                            print(f"  strategy {s.get('name','?')}: recipe_ref '{recipe_ref}' unreadable: {e}")
                            failed += 1
                            continue
                    if not recipe:
                        continue
                    missing = sorted({step.get("op") for step in recipe
                                      if step.get("op") and step.get("op") not in REGISTRY})
                    if missing:
                        print(f"  strategy {s.get('name','?')}: MISSING OPS {missing}")
                        failed += 1
            except (OSError, json.JSONDecodeError) as e:
                print(f"  strategies.json: unreadable: {e}")
                failed += 1

    if failed:
        print(f"\n{failed} recipe(s) reference ops that no longer exist.")
        return 1
    print("All recipes OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())