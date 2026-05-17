#!/usr/bin/env python3
"""
Cross-repo referential integrity check: RogueTech → InnerSphereMap system IDs.

Collects valid starsystemdef IDs from:
  1. InnerSphereMap (all 3 eras via Description.Id)
  2. RogueTech's own starsystemdef_*.json files (Description.Id)

Then walks all non-starsystemdef JSON files in RogueTech and extracts every
string value that starts with "starsystemdef_". Any such reference that is not
in the valid set is a dangling reference (broken contract generation).

Usage:
  python check_system_refs.py [<roguetech_root> [<innerspheremap_root>]]

  Defaults: roguetech_root = ../../.. (relative to this script)
            innerspheremap_root = ../../../InnerSphereMap

Exit code 0 = clean, non-zero = failures found.
"""

import json
import sys
from pathlib import Path


def collect_description_ids(root: Path, prefix: str) -> set[str]:
    """Return Description.Id values from all non-patch files matching prefix."""
    ids: set[str] = set()
    for path in root.rglob(f"{prefix}_*.json"):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        if any(p.startswith(".") for p in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            id_val = data.get("Description", {}).get("Id", "")
            if id_val:
                ids.add(id_val)
        except (json.JSONDecodeError, OSError):
            pass
    return ids


def collect_ism_ids(ism_root: Path) -> set[str]:
    """Collect starsystemdef IDs from all ISM eras."""
    ids: set[str] = set()
    data_dir = ism_root / "InnerSphereMap_data"
    if not data_dir.exists():
        return ids
    for path in data_dir.rglob("starsystemdef_*.json"):
        if any(p.startswith(".") for p in path.parts):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            id_val = data.get("Description", {}).get("Id", "")
            if id_val:
                ids.add(id_val)
        except (json.JSONDecodeError, OSError):
            pass
    return ids


def extract_system_refs(obj, refs: set[str]) -> None:
    """Recursively extract all string values starting with 'starsystemdef_'."""
    if isinstance(obj, str):
        if obj.startswith("starsystemdef_") and obj != "starsystemdef_":
            # Skip fragment suffixes that appear in path-like strings
            if not (obj.endswith(".json") or obj.endswith(".Details")
                    or obj.endswith(".Name") or obj.endswith(".Id")):
                refs.add(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            extract_system_refs(v, refs)
    elif isinstance(obj, list):
        for item in obj:
            extract_system_refs(item, refs)


def check_system_refs(rt_root: Path, valid_ids: set[str]) -> list[tuple[str, str]]:
    """
    Walk all non-starsystemdef JSON files in RogueTech and collect dangling refs.
    Returns list of (ref_id, source_file) pairs.
    """
    errors: list[tuple[str, str]] = []
    for path in sorted(rt_root.rglob("*.json")):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        if any(p.startswith(".") for p in path.parts):
            continue
        stem_lower = path.stem.lower()
        if stem_lower.startswith("starsystemdef_"):
            continue  # definitions, not references
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        refs: set[str] = set()
        extract_system_refs(data, refs)
        for ref in refs:
            if ref and ref not in valid_ids:
                errors.append((ref, str(path.relative_to(rt_root))))
    return errors


def main() -> int:
    script_dir = Path(__file__).parent
    rt_root = Path(sys.argv[1]) if len(sys.argv) > 1 else script_dir.parent.parent.parent
    ism_root = Path(sys.argv[2]) if len(sys.argv) > 2 else rt_root.parent / "InnerSphereMap"

    ism_ids = collect_ism_ids(ism_root)
    rt_ids = collect_description_ids(rt_root, "starsystemdef")
    valid_ids = ism_ids | rt_ids

    print(f"Valid system IDs: {len(valid_ids)} "
          f"({len(ism_ids)} from InnerSphereMap, {len(rt_ids)} from RogueTech)")

    errors = check_system_refs(rt_root, valid_ids)

    if not errors:
        print("OK — all starsystemdef references resolve to a known system")
        return 0

    # Group by ref ID for cleaner output
    by_ref: dict[str, list[str]] = {}
    for ref, src in errors:
        by_ref.setdefault(ref, []).append(src)

    print(f"\nFAILED — {len(by_ref)} dangling starsystemdef reference(s):\n")
    for ref in sorted(by_ref):
        files = by_ref[ref]
        print(f"  '{ref}' ({len(files)} occurrence(s)):")
        for f in sorted(files)[:5]:
            print(f"    {f}")
        if len(files) > 5:
            print(f"    ... and {len(files) - 5} more")
    return 1


if __name__ == "__main__":
    sys.exit(main())
