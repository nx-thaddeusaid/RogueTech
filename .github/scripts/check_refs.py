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


def main() -> int:
    root = Path(__file__).parent.parent.parent
    errors: list[str] = []

    # Single-pass walk: collect all data in one traversal instead of 4 separate rglobs.
    chassis_ids: set[str] = set()
    vchassis_ids: set[str] = set()
    component_stems: set[str] = set()

    # Deferred: files that need chassis/component checks after the full pass collects IDs.
    mechdefs: list[tuple[Path, dict]] = []
    vehicledefs: list[tuple[Path, dict]] = []

    for path in root.rglob("*.json"):
        parts_lower = [p.lower() for p in path.parts]
        if "advancedjsonmerge" in parts_lower:
            continue
        if any(p.startswith(".") for p in path.parts):
            continue

        stem_lower = path.stem.lower()
        prefix = stem_lower.split("_")[0]

        if prefix in COMPONENT_PREFIXES:
            component_stems.add(stem_lower)

        if stem_lower.startswith("chassisdef_"):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                id_val = data.get("Description", {}).get("Id", "")
                if id_val:
                    chassis_ids.add(id_val)
            except (json.JSONDecodeError, OSError):
                pass

        elif stem_lower.startswith("vehiclechassisdef_"):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                id_val = data.get("Description", {}).get("Id", "")
                if id_val:
                    vchassis_ids.add(id_val)
            except (json.JSONDecodeError, OSError):
                pass

        elif stem_lower.startswith("mechdef_"):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                mechdefs.append((path, data))
            except (json.JSONDecodeError, OSError):
                pass

        elif stem_lower.startswith("vehicledef_"):
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                vehicledefs.append((path, data))
            except (json.JSONDecodeError, OSError):
                pass

    mech_checked = 0
    vehicle_checked = 0
    mech_inv_items = 0
    veh_inv_items = 0

    for path, data in mechdefs:
        chassis_id = data.get("ChassisID", "")
        if chassis_id and chassis_id not in chassis_ids:
            errors.append(
                f"{path.name}: ChassisID '{chassis_id}' has no matching chassisdef"
            )
        mech_checked += 1
        for i, item in enumerate(data.get("inventory", [])):
            cid = item.get("ComponentDefID", "")
            if not cid:
                continue
            cid_lower = cid.lower()
            if cid_lower.split("_")[0] not in COMPONENT_PREFIXES:
                continue
            mech_inv_items += 1
            if cid_lower not in component_stems:
                errors.append(
                    f"{path.name}: inventory[{i}] ComponentDefID '{cid}' has no backing def"
                )

    for path, data in vehicledefs:
        chassis_id = data.get("ChassisID", "")
        if chassis_id and chassis_id not in vchassis_ids:
            errors.append(
                f"{path.name}: ChassisID '{chassis_id}' has no matching vehiclechassisdef"
            )
        vehicle_checked += 1
        for i, item in enumerate(data.get("inventory", [])):
            cid = item.get("ComponentDefID", "")
            if not cid:
                continue
            cid_lower = cid.lower()
            if cid_lower.split("_")[0] not in COMPONENT_PREFIXES:
                continue
            veh_inv_items += 1
            if cid_lower not in component_stems:
                errors.append(
                    f"{path.name}: inventory[{i}] ComponentDefID '{cid}' has no backing def"
                )

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
        f"{mech_checked + vehicle_checked} defs → {len(component_stems)} known components"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
