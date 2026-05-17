#!/usr/bin/env python3
"""
Cross-file referential integrity checks for the RogueTech mod pack.

Checks:
  1. Every mechdef_*.json ChassisID references an existing chassisdef Description.Id
  2. Every vehicledef_*.json ChassisID references an existing vehiclechassisdef Description.Id
  3. Every inventory item ComponentDefID in mechdef_*.json/vehicledef_*.json resolves
     to a known component def file stem (case-insensitive)

advancedjsonmerge/ patches are excluded — they reference IDs from their target def,
not their own filename stem, and are applied at load time by ModTek.

Exit code 0 = clean, non-zero = failures found.
"""

import json
import sys
from pathlib import Path

# Filename stem prefixes that back inventory ComponentDefIDs (case-insensitive).
COMPONENT_PREFIXES = frozenset({
    "gear", "weapon", "ammo", "linked", "special",
    "default", "bolton", "lootable", "handheld", "unique",
})


def collect_ids(root: Path, prefix: str) -> set[str]:
    """Return the set of Description.Id values for all non-patch defs matching prefix."""
    ids: set[str] = set()
    for path in root.rglob(f"{prefix}_*.json"):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            id_val = data.get("Description", {}).get("Id", "")
            if id_val:
                ids.add(id_val)
        except (json.JSONDecodeError, OSError):
            pass
    return ids


def check_chassis_refs(
    root: Path,
    mechdef_prefix: str,
    chassis_ids: set[str],
    errors: list[str],
) -> int:
    """Check that every mechdef/vehicledef ChassisID has a matching chassisdef."""
    checked = 0
    for path in sorted(root.rglob(f"{mechdef_prefix}_*.json")):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        chassis_id = data.get("ChassisID", "")
        if chassis_id and chassis_id not in chassis_ids:
            errors.append(
                f"{path.name}: ChassisID '{chassis_id}' has no matching chassisdef"
            )
        checked += 1
    return checked


def collect_component_stems(root: Path) -> set[str]:
    """Return lowercased stems for all component def files (case-insensitive prefix match)."""
    stems: set[str] = set()
    for path in root.rglob("*.json"):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        if any(p.startswith(".") for p in path.parts):
            continue
        stem_lower = path.stem.lower()
        prefix = stem_lower.split("_")[0]
        if prefix in COMPONENT_PREFIXES:
            stems.add(stem_lower)
    return stems


def check_inventory_refs(
    root: Path,
    def_prefix: str,
    component_stems: set[str],
    errors: list[str],
) -> tuple[int, int]:
    """Check that every inventory ComponentDefID resolves to a known component stem."""
    defs_checked = 0
    items_checked = 0
    for path in sorted(root.rglob(f"{def_prefix}_*.json")):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            continue
        defs_checked += 1
        for i, item in enumerate(data.get("inventory", [])):
            cid = item.get("ComponentDefID", "")
            if not cid:
                continue
            cid_lower = cid.lower()
            prefix = cid_lower.split("_")[0]
            if prefix not in COMPONENT_PREFIXES:
                continue  # engine parts, fixed slots, etc — not validated here
            items_checked += 1
            if cid_lower not in component_stems:
                errors.append(
                    f"{path.name}: inventory[{i}] ComponentDefID '{cid}' has no backing def"
                )
    return defs_checked, items_checked


def main() -> int:
    root = Path(__file__).parent.parent.parent
    errors: list[str] = []

    chassis_ids = collect_ids(root, "chassisdef")
    vchassis_ids = collect_ids(root, "vehiclechassisdef")

    mech_checked = check_chassis_refs(root, "mechdef", chassis_ids, errors)
    vehicle_checked = check_chassis_refs(root, "vehicledef", vchassis_ids, errors)

    component_stems = collect_component_stems(root)
    mech_inv_defs, mech_inv_items = check_inventory_refs(root, "mechdef", component_stems, errors)
    veh_inv_defs, veh_inv_items = check_inventory_refs(root, "vehicledef", component_stems, errors)

    total_chassis = mech_checked + vehicle_checked
    total_inv_items = mech_inv_items + veh_inv_items

    if errors:
        print(f"FAILED — {len(errors)} broken reference(s):\n")
        for err in errors:
            print(f"  {err}")
        return 1

    print(
        f"OK — chassis refs: {total_chassis} defs "
        f"({mech_checked} mechdefs → {len(chassis_ids)} chassisdefs, "
        f"{vehicle_checked} vehicledefs → {len(vchassis_ids)} vehiclechassisdefs)\n"
        f"     inventory refs: {total_inv_items} items across "
        f"{mech_inv_defs + veh_inv_defs} defs → {len(component_stems)} known components"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
