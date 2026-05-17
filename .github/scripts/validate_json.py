#!/usr/bin/env python3
"""
Validates all JSON files in the RogueTech repo:
  - Syntax validity
  - Per-object duplicate key detection
  - Required fields per BattleTech def type (keyed by filename prefix)
  - Description.Id uniqueness per def type
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent

REQUIRED_FIELDS = {
    "mechdef_":              ["Description", "ChassisID", "inventory"],
    "chassisdef_":           ["Description", "HardpointDataDefID", "Locations"],
    "vehicledef_":           ["Description", "ChassisID", "inventory"],
    "vehiclechassisdef_":    ["Description", "HardpointDataDefID", "Locations"],
    "starsystemdef_":        ["Description", "StarType"],
    "lancedef_":             ["Description", "LanceUnits"],
    "pilot_":                ["Description", "Piloting", "Gunnery"],
    "event_":                ["Description", "Trigger"],
    "turretdef_":            ["Description", "ChassisID"],
    "turretchassisdef_":     ["Description", "HardpointDataDefID"],
}

SKIP_DIRS = {"advancedjsonmerge", "tags"}


def check_pairs(pairs):
    keys = [k for k, _ in pairs]
    seen = set()
    for k in keys:
        if k in seen:
            return None, f"duplicate key '{k}'"
        seen.add(k)
    return dict(pairs), None


def load_json(path):
    text = path.read_text(encoding="utf-8-sig")
    errors = []
    result = {}

    def hook(pairs):
        obj, err = check_pairs(pairs)
        if err:
            errors.append(err)
            return dict(pairs)
        return obj

    try:
        result = json.loads(text, object_pairs_hook=hook)
    except json.JSONDecodeError as e:
        return None, [str(e)]
    return result, errors


def check_required(data, prefix, path):
    fields = REQUIRED_FIELDS.get(prefix)
    if not fields or not isinstance(data, dict):
        return []
    missing = [f for f in fields if f not in data]
    if missing:
        return [f"missing required fields: {missing}"]
    return []


def main():
    errors_by_file = {}
    id_map = {}  # prefix -> {id -> first_path}
    total = 0

    for f in sorted(ROOT.rglob("*.json")):
        parts = f.parts
        if any(p.startswith(".") for p in parts):
            continue
        if any(p in SKIP_DIRS for p in parts):
            continue

        total += 1
        rel = f.relative_to(ROOT)
        file_errors = []

        data, load_errors = load_json(f)
        file_errors.extend(load_errors)

        if data is not None:
            name = f.name
            for prefix in REQUIRED_FIELDS:
                if name.startswith(prefix):
                    file_errors.extend(check_required(data, prefix, f))

                    # Description.Id uniqueness — skip advancedjsonmerge patches
                    if "advancedjsonmerge" not in str(f):
                        desc = data.get("Description")
                        if isinstance(desc, dict):
                            did = desc.get("Id")
                            if did:
                                if did in id_map.setdefault(prefix, {}):
                                    file_errors.append(
                                        f"duplicate Description.Id '{did}' (first seen in {id_map[prefix][did]})"
                                    )
                                else:
                                    id_map[prefix][did] = rel
                    break

            # mod.json: require Name if manifest keys present
            if name == "mod.json" and isinstance(data, dict):
                if any(k in data for k in ("Manifest", "AdvancedJSONMerge")):
                    if "Name" not in data:
                        file_errors.append("mod.json missing 'Name'")

        if file_errors:
            errors_by_file[str(rel)] = file_errors

    if errors_by_file:
        for path, errs in sorted(errors_by_file.items()):
            for e in errs:
                print(f"ERROR {path}: {e}", file=sys.stderr)
        print(
            f"\n{len(errors_by_file)} file(s) with errors out of {total} checked.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {total} JSON files validated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
