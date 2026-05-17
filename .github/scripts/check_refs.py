#!/usr/bin/env python3
"""
Cross-file referential integrity checks for the RogueTech mod pack.

Checks:
  1. Every mechdef_*.json ChassisID references an existing chassisdef Description.Id
  2. Every vehicledef_*.json ChassisID references an existing vehiclechassisdef Description.Id

advancedjsonmerge/ patches are excluded — they reference IDs from their target def,
not their own filename stem, and are applied at load time by ModTek.

Exit code 0 = clean, non-zero = failures found.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path


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


def main() -> int:
    root = Path(__file__).parent.parent.parent
    errors: list[str] = []

    chassis_ids = collect_ids(root, "chassisdef")
    vchassis_ids = collect_ids(root, "vehiclechassisdef")

    mech_checked = check_chassis_refs(root, "mechdef", chassis_ids, errors)
    vehicle_checked = check_chassis_refs(root, "vehicledef", vchassis_ids, errors)

    total = mech_checked + vehicle_checked

    if errors:
        print(f"FAILED — {len(errors)} broken reference(s) across {total} defs checked:\n")
        for err in errors:
            print(f"  {err}")
        return 1

    print(
        f"OK — {total} defs checked "
        f"({mech_checked} mechdefs → {len(chassis_ids)} chassisdefs, "
        f"{vehicle_checked} vehicledefs → {len(vchassis_ids)} vehiclechassisdefs)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
